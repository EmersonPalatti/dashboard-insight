"""Comanda da leitura: título, diagnóstico, ação, drill-down e rótulos das consultas.

O texto livre do modelo não vira filtro. Drill-down só entra se o hub, a loja
ou o outro valor existe no recorte que o servidor já consultou.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import get_args

from app import semantic
from app.filters import ChannelType, Filters, Modal, OrderStatus, Segment
from app.repository import VALUE_LABELS, Repository
from app.schemas import ChatResponse, DrillDown, ReadingBase

log = logging.getLogger(__name__)

_MAX_DRILLS = 3
_LIST_CAP = 50
_TITLE_CAP = 80

_DIMENSION_LABEL = {
    "hour": "Quebra por hora",
    "weekday": "Quebra por dia da semana",
    "hub": "Quebra por hub",
    "store": "Quebra por loja",
    "city": "Quebra por cidade",
    "channel": "Quebra por canal",
    "channel_type": "Quebra por tipo de canal",
    "segment": "Quebra por segmento",
    "modal": "Quebra por modal",
    "driver_type": "Quebra por tipo de entregador",
    "payment_method": "Quebra por pagamento",
}
_TOOL_LABEL = {
    "get_kpis": "KPIs do recorte",
    "get_alerts": "Alertas do recorte",
    "get_timeseries": "Série do recorte",
    "query_metrics": "Consulta do recorte",
    "explain_change": "Por que mudou",
    "drill_cause": "Etapa que explica o atraso",
}
_DRILL_LABEL = {"sla_rate": "Etapa que explica o atraso", "cycle_p50": "Etapa que explica o ciclo"}
_CALL = re.compile(r"^(\w+)\((.*)\)$")
_FENCE = re.compile(r"```(?:leitura|json)?[^\n]*\n(\{.*?\})\s*```", re.DOTALL)
_OPEN_FENCE = re.compile(r"\n?```(?:leitura|json)\b[\s\S]*$", re.IGNORECASE)
_MARKS = re.compile(r"[*_#`]")
_SEVERITY_PT = [
    (re.compile(r"\balertas\s+high\b", re.IGNORECASE), "alertas críticos"),
    (re.compile(r"\balerta\s+high\b", re.IGNORECASE), "alerta crítico"),
    (re.compile(r"\bseveridade\s+high\b", re.IGNORECASE), "severidade crítica"),
    (re.compile(r"\balertas\s+medium\b", re.IGNORECASE), "alertas em atenção"),
    (re.compile(r"\balerta\s+medium\b", re.IGNORECASE), "alerta em atenção"),
    (re.compile(r"\bseveridade\s+medium\b", re.IGNORECASE), "severidade média"),
    (re.compile(r"\balertas\s+low\b", re.IGNORECASE), "alertas para observar"),
    (re.compile(r"\balerta\s+low\b", re.IGNORECASE), "alerta para observar"),
    (re.compile(r"\bseveridade\s+low\b", re.IGNORECASE), "severidade baixa"),
    (re.compile(r"\(\s*high\s*\)", re.IGNORECASE), "(crítico)"),
    (re.compile(r"\(\s*medium\s*\)", re.IGNORECASE), "(em atenção)"),
    (re.compile(r"\(\s*low\s*\)", re.IGNORECASE), "(observar)"),
]


# Flags e chaves internas que o modelo gratuito às vezes copia das tools para o texto.
_FLAG_PT = {
    "volume_low_sample": "volume pequeno",
    "low_sample": "amostra pequena",
    "sla_below": "SLA abaixo do recorte",
    "cancel_above": "cancelamento acima do recorte",
    "sla_pct": "SLA",
    "cancel_pct": "cancelamento",
    "stuck_pct": "pedidos presos",
}


@lru_cache(maxsize=1)
def _internal_terms() -> tuple[re.Pattern[str], dict[str, str]]:
    """Chave interna → rótulo pt-BR. Métricas vêm da camada semântica, nunca de lista duplicada aqui."""
    terms = {key: metric.label for key, metric in semantic.load().metrics.items() if "_" in key}
    terms.update(_FLAG_PT)
    # Mais longa primeiro: `volume_low_sample` antes de `low_sample`. Crase em volta sai junto.
    alternation = "|".join(sorted(map(re.escape, terms), key=len, reverse=True))
    return re.compile(rf"`?\b({alternation})\b`?"), terms


# Nomes de argumento que o parser das tools aceita além dos declarados no schema (`llm._parse_*`).
_ARG_ALIASES = ("window", "windows", "janela", "ascending", "desc", "worst")
_ARG_VALUE = r"""(?:\[[^\]]*\]|"[^"]*"|'[^']*'|[^\s,;.]+)"""


@lru_cache(maxsize=1)
def _arg_patterns() -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    """Argumentos e chamadas de tool copiados para a prosa. Só nomes reais de argumento contam:
    `(n=42 pedidos)` ou `taxa=80%` é texto do modelo e fica."""
    from app.agent.llm import TOOLS  # import tardio: llm carrega a camada semântica e o repositório

    keys = set(_ARG_ALIASES)
    for tool in TOOLS:
        keys.update(tool["function"]["parameters"].get("properties", {}))
    arg_names = "|".join(sorted(map(re.escape, keys), key=len, reverse=True))
    arg = rf"\b(?:{arg_names})={_ARG_VALUE}"
    # Parêntese com argumentos de ferramenta ("(window=jantar, sort=production_p50)").
    tool_args = re.compile(rf"\s*\((?=[^()]*\b(?:{arg_names})=)[^()]*\)")
    # Chamada escrita na prosa ("investiga query_metrics group_by=["store"], sort="x"").
    bare_args = re.compile(rf"(?:,?\s*{arg})+")
    names = "|".join(sorted((t["function"]["name"] for t in TOOLS), key=len, reverse=True))
    tool_call = re.compile(rf"`?\b(?:{names})\b`?(?:\([^()]*\))?(?:,?\s*{arg})*")
    return tool_args, bare_args, tool_call


def _pt_internal(text: str) -> str:
    pattern, terms = _internal_terms()
    tool_args, bare_args, tool_call = _arg_patterns()
    text = tool_call.sub("uma consulta", tool_args.sub("", text))
    text = bare_args.sub("", text)
    return pattern.sub(lambda m: terms[m.group(1)], text)


# Número em formato en-US que o modelo às vezes devolve. Só formas sem ambiguidade: decimal com ponto
# seguido de unidade (82.4%, 38.5 min, 1.2 p.p.) e valor em reais (R$ 1,234.56, R$ 9.90). Data, hora,
# Nº de hub/loja e "1.200 pedidos" (milhar pt-BR) não casam. Código entre crases fica como está.
_EN_UNIT = re.compile(r"(?<![\d.,])(\d+)\.(\d{1,2})(\s?(?:%|min\b|p\.\s?p\.|pp\b|km\b))")
_EN_BRL_THOUSANDS = re.compile(r"(R\$\s?)(\d{1,3}(?:,\d{3})+)(?:\.(\d{1,2}))?(?![\d,]|\.\d)")
_EN_BRL_DECIMAL = re.compile(r"(R\$\s?)(\d+)\.(\d{1,2})(?![\d.,]\d|\d)")
_CODE = re.compile(r"(```[\s\S]*?```|`[^`\n]*`)")


def _brl_thousands(m: re.Match[str]) -> str:
    cents = f",{m.group(3)}" if m.group(3) else ""
    return f"{m.group(1)}{m.group(2).replace(',', '.')}{cents}"


def _pt_numbers(text: str) -> str:
    """82.4% → 82,4%; R$ 1,234.56 → R$ 1.234,56. Fora de trechos de código."""

    def fix(part: str) -> str:
        part = _EN_BRL_THOUSANDS.sub(_brl_thousands, part)
        part = _EN_BRL_DECIMAL.sub(r"\1\2,\3", part)
        return _EN_UNIT.sub(r"\1,\2\3", part)

    return "".join(part if i % 2 else fix(part) for i, part in enumerate(_CODE.split(text)))


def _pt_severity(text: str) -> str:
    """Troca severidade em inglês (`high`/`medium`/`low`), chaves internas das tools e número en-US
    por pt-BR. Recebe prosa, nunca o JSON da leitura."""
    for pattern, repl in _SEVERITY_PT:
        text = pattern.sub(
            lambda m, r=repl: (r[0].upper() + r[1:]) if m.group(0)[0].isupper() else r,
            text,
        )
    return _pt_numbers(_pt_internal(text))


@dataclass
class Reading:
    answer: str
    title: str
    diagnosis: str
    action: str
    drilldowns: list[DrillDown]
    n: int
    measured: int
    low_sample: bool
    tools: list[str]


@dataclass
class ParsedReading:
    title: str
    diagnosis: str
    action: str
    drilldowns: list[DrillDown]
    sent_drilldowns: bool


def _metric_label(key: str) -> str | None:
    """'SLA (no prazo)' -> 'SLA'; 'Cancelamento' -> 'cancelamento' (sigla fica maiúscula)."""
    metric = semantic.load().metrics.get(key)
    if metric is None:
        return None
    label = metric.label.split(" (")[0].strip()
    return label if label[:2].isupper() else label[:1].lower() + label[1:]


def _dim_label(key: str) -> str | None:
    dim = semantic.load().dimensions.get(key)
    return dim.label.lower() if dim else None


def _labels(keys: str, lookup) -> list[str]:
    return [label for key in keys.split(",") if key and (label := lookup(key.strip()))]


def label_for(name: str) -> str:
    """Rótulo pt-BR. Nome de função desconhecido não vaza para a tela.

    O ToolRunner registra a chamada como `nome(args)`: `query_metrics(sla_rate,cancel_rate:hub,hour)`,
    `explain_change(cancel_rate:store)`, `drill_cause(sla_rate)`; o agente local usa `get_breakdown(dim)`.
    """
    if name in _TOOL_LABEL:
        return _TOOL_LABEL[name]
    match = _CALL.match(name)
    if not match:
        return "Consulta do recorte"
    tool, args = match.groups()
    if tool == "get_breakdown":
        return _DIMENSION_LABEL.get(args, "Quebra do recorte")
    if tool == "drill_cause":
        return _DRILL_LABEL.get(args, _TOOL_LABEL["drill_cause"])
    metric_part, _, dim_part = args.partition(":")
    metrics = _labels(metric_part, _metric_label)
    dims = _labels(dim_part, _dim_label)
    if tool == "explain_change" and metrics:
        return f"Por que mudou: {metrics[0]}" + (f" por {dims[0]}" if dims else "")
    if tool == "query_metrics" and metrics:
        if len(metrics) > 3:
            shown = f"{', '.join(metrics[:2])} e mais {len(metrics) - 2}"
        else:
            shown = " e ".join([", ".join(metrics[:-1]), metrics[-1]]) if len(metrics) > 1 else metrics[0]
        where = f" por {' × '.join(dims)}" if dims else " no recorte"
        return f"Consulta: {shown}{where}"
    return _TOOL_LABEL.get(tool, "Consulta do recorte")


def labels_for(names: list[str]) -> list[str]:
    out: list[str] = []
    for name in names:
        label = label_for(name)
        if label not in out:
            out.append(label)
    return out


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _catalog(repo: Repository, f: Filters) -> dict[str, set]:
    """Valores que existem no recorte. O que não está aqui foi inventado."""

    def keys(dimension: str) -> set:
        found = set()
        for row in repo.breakdown(f, dimension, limit=1000):
            key = row.get("key")
            if key is None:
                continue
            found.add(key)
        return found

    metrics = repo.metrics(f)
    status: set[str] = set()
    if (metrics.get("delivered") or 0) > 0:
        status.add("delivered")
    if (metrics.get("canceled") or 0) > 0:
        status.add("canceled")
    return {
        "hub": {_as_int(key) for key in keys("hub") if _as_int(key) is not None},
        "store": {_as_int(key) for key in keys("store") if _as_int(key) is not None},
        "city": {str(key) for key in keys("city")},
        "segment": {str(key) for key in keys("segment")},
        "channel_type": {str(key) for key in keys("channel_type")},
        "modal": {str(key) for key in keys("modal")},
        "status": status,
    }


def _keep(key: str, value: object, known: dict[str, set]) -> str | int | None:
    if key in {"hub", "store"}:
        number = _as_int(value)
        if number is None or number not in known[key]:
            return None
        return number
    if not isinstance(value, str):
        return None
    text = value.strip()
    if key == "segment" and text not in _literal_values(Segment):
        return None
    if key == "channel_type" and text not in _literal_values(ChannelType):
        return None
    if key == "modal" and text not in _literal_values(Modal):
        return None
    if key == "status" and text not in _literal_values(OrderStatus):
        return None
    if key == "city":
        if text in known["city"]:
            return text
        folded = text.casefold()
        return next((c for c in known["city"] if isinstance(c, str) and c.casefold() == folded), None)
    if text not in known[key]:
        return None
    return text


def _literal_values(kind: object) -> set[str]:
    return set(get_args(kind))


def _auto_label(filters: dict[str, list]) -> str:
    for key in ("store", "hub", "city", "modal", "channel_type", "segment", "status"):
        values = filters.get(key)
        if not values:
            continue
        shown = VALUE_LABELS.get(str(values[0]), str(values[0]))
        return f"Ver só {shown}"
    return "Ver no recorte"


def validate_drilldowns(repo: Repository, f: Filters, drills: list[DrillDown]) -> list[DrillDown]:
    """Tira hub, loja ou valor que não está no recorte. Sem filtro válido, o atalho sai."""
    known = _catalog(repo, f)
    out: list[DrillDown] = []
    for drill in drills:
        clean: dict[str, list[str | int]] = {}
        for key, values in (drill.filters or {}).items():
            if key not in known or not isinstance(values, list):
                continue
            kept: list[str | int] = []
            for value in values[:_LIST_CAP]:
                item = _keep(key, value, known)
                if item is None or item in kept:
                    continue
                kept.append(item)
            if kept:
                clean[key] = kept
        if not clean:
            continue
        label = (drill.label or "").strip()[:_TITLE_CAP] or _auto_label(clean)
        out.append(DrillDown(label=label, filters=clean))
        if len(out) == _MAX_DRILLS:
            break
    return out


def _coerce_drill(item: object) -> DrillDown | None:
    if not isinstance(item, dict):
        return None
    raw_filters = item.get("filters")
    if not isinstance(raw_filters, dict):
        return None
    filters: dict[str, list[str | int]] = {}
    for key, values in raw_filters.items():
        if not isinstance(key, str) or not isinstance(values, list):
            continue
        kept: list[str | int] = []
        for value in values[:_LIST_CAP]:
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                kept.append(value)
            elif isinstance(value, float) and value.is_integer():
                kept.append(int(value))
            elif isinstance(value, str) and value.strip():
                kept.append(value.strip()[:80])
        if kept:
            filters[key] = kept
    if not filters:
        return None
    label = item.get("label")
    return DrillDown(label=label.strip()[:_TITLE_CAP] if isinstance(label, str) else "", filters=filters)


def parse_leitura(text: str) -> ParsedReading | None:
    """JSON da leitura, se estiver completo. Texto solto ou JSON quebrado devolve None."""
    candidates = list(_FENCE.findall(text))
    start = text.rfind("{")
    if start != -1:
        candidates.append(text[start:])
    for raw in candidates:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        title = data.get("title")
        diagnosis = data.get("diagnosis")
        action = data.get("action")
        if not all(isinstance(part, str) and part.strip() for part in (title, diagnosis, action)):
            continue
        sent = "drilldowns" in data
        raw_drills = data.get("drilldowns") if sent else []
        if not isinstance(raw_drills, list):
            raw_drills = []
        drills = [drill for item in raw_drills if (drill := _coerce_drill(item)) is not None]
        return ParsedReading(
            title=title.strip()[:_TITLE_CAP],
            diagnosis=diagnosis.strip(),
            action=action.strip(),
            drilldowns=drills,
            sent_drilldowns=sent,
        )
    return None


def _strip_fence(text: str) -> str:
    return _OPEN_FENCE.sub("", _FENCE.sub("", text)).strip()


# "Ação:", "**Ação**:", "__Ação:__", "Acao:", "- **Ação:**", "### Ação:" no começo da linha: modelos
# diferentes formatam a marca de jeitos diferentes. Sem normalizar, uma resposta boa vira leitura local.
_ACTION_LINE = re.compile(
    r"(?im)^[ \t]*(?:[-*•+][ \t]+|#{1,4}[ \t]*)?(?:\*\*|__)?[ \t]*a[çc][ãa]o[ \t]*(?:\*\*|__)?[ \t]*:[ \t]*"
    r"(?:\*\*|__)?[ \t]*"
)
# Marca em negrito no meio da linha ("Corpo. **Ação:** Líder revisa hoje."): vai para parágrafo próprio.
_INLINE_ACTION = re.compile(
    r"(?i)(?<=\S)[ \t]*(?:\*\*|__)[ \t]*a[çc][ãa]o[ \t]*(?:\*\*|__)?[ \t]*:[ \t]*(?:\*\*|__)?[ \t]*"
)
_LEITURA_FENCE = re.compile(r"```(?:leitura|json)\b", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^[ \t]*(?:[-*•+]|\d{1,2}[.)])[ \t]+")
_MARKER = "**Ação:**"


def _mark_action(text: str) -> str:
    """Marca de ação canônica em linha própria. O bloco `leitura` fica intacto (é JSON)."""
    fence = _LEITURA_FENCE.search(text)
    cut = fence.start() if fence else len(text)
    prose = _ACTION_LINE.sub(_MARKER + " ", text[:cut])
    prose = _INLINE_ACTION.sub("\n\n" + _MARKER + " ", prose)
    return prose + text[cut:]


def normalize_action(text: str) -> str:
    """Padroniza a linha de ação em `**Ação:**`; sem a linha, usa a ação do bloco `leitura` se houver."""
    text = _mark_action(text)
    if _MARKER in text:
        return text
    parsed = parse_leitura(text)
    if parsed is None or not parsed.action.strip():
        return text
    fence = text.find("```")
    body = (text[:fence] if fence >= 0 else text).rstrip()
    rest = text[fence:] if fence >= 0 else ""
    return f"{body}\n\n{_MARKER} {parsed.action.strip()}\n\n{rest}".rstrip()


def _action_lines(lines: list[str]) -> tuple[str, list[str]]:
    """Primeira linha é a ação; seguem junto passos em lista, linha recuada ou frase que não fechou.
    O resto (nota depois da ação) volta para o corpo."""
    action = _LIST_ITEM.sub("", lines[0]).strip()
    steps: list[str] = []
    rest_at = len(lines)
    for i, line in enumerate(lines[1:], start=1):
        open_sentence = not (steps[-1] if steps else action).endswith((".", "!", "?"))
        if _LIST_ITEM.match(line):
            steps.append(_LIST_ITEM.sub("", line).strip())
        elif line[:1] in (" ", "\t") or open_sentence:
            if steps:
                steps[-1] = f"{steps[-1]} {line.strip()}"
            else:
                action = f"{action} {line.strip()}".strip()
        else:
            rest_at = i
            break
    for step in steps:
        action = f"{action}{' ' if action.endswith(('.', '!', '?', ';', ':')) else '; '}{step}".strip()
    return action, lines[rest_at:]


def split_markdown(text: str) -> tuple[str, str]:
    """Separa o corpo da última marca de ação. Passos em lista entram na ação; nota depois dela volta
    para o corpo. Sem ação, o segundo item vem vazio."""
    stripped = _mark_action(_strip_fence(text)).strip()
    index = stripped.rfind(_MARKER)
    if index == -1:
        return stripped, ""
    head = stripped[:index].rstrip()
    paragraphs = [p for p in re.split(r"\n[ \t]*\n", stripped[index + len(_MARKER):].strip()) if p.strip()]
    if not paragraphs:
        return head, ""
    lines = [line for line in paragraphs[0].splitlines() if line.strip()]
    rest = paragraphs[1:]
    # "**Ação:** Líder do hub:" seguido de lista em parágrafo próprio: a lista é a ação.
    while lines and lines[-1].rstrip().endswith(":") and rest and _LIST_ITEM.match(rest[0]):
        lines += [line for line in rest.pop(0).splitlines() if line.strip()]
    action, trailing = _action_lines(lines)
    tail = "\n\n".join(part for part in ["\n".join(trailing), *rest] if part.strip())
    body = "\n\n".join(part for part in (head, tail) if part)
    return body, action


def has_extractable_action(text: str | None) -> bool:
    """Mesma regra de `response_llm`: a resposta só é aceita se dela sai uma ação não vazia."""
    if not text:
        return False
    parsed = parse_leitura(text)
    if parsed is not None and _pt_severity(parsed.action).strip():
        return True
    return bool(split_markdown(_pt_severity(_strip_fence(text)))[1])


def clip_title(diagnosis: str) -> str:
    line = ""
    for raw in diagnosis.splitlines():
        cleaned = _MARKS.sub("", raw).strip(" -")
        if cleaned:
            line = cleaned
            break
    if len(line) > _TITLE_CAP:
        line = line[: _TITLE_CAP - 1].rstrip() + "…"
    return line or "Leitura do recorte"


def _base(reading: Reading) -> ReadingBase:
    return ReadingBase(n=reading.n, measured=reading.measured, low_sample=reading.low_sample)


def response_local(reading: Reading) -> ChatResponse:
    return ChatResponse(
        answer=reading.answer,
        mode="local",
        model=None,
        tools_used=list(reading.tools),
        title=reading.title,
        diagnosis=reading.diagnosis,
        action=reading.action,
        drilldowns=list(reading.drilldowns),
        base=_base(reading),
        source="local",
        tool_labels=labels_for(reading.tools),
    )


def response_llm(
    text: str,
    mode: str,
    model: str | None,
    tools_used: list[str],
    local: Reading,
    repo: Repository,
    filters: Filters,
) -> ChatResponse:
    """Fecha a comanda do modelo. Sem JSON válido, usa o texto e os atalhos das regras.

    O bloco `leitura` nunca fica em `answer`: ele volta como histórico na próxima pergunta.
    """
    parsed = parse_leitura(text)
    # Tira o bloco antes de traduzir: a tradução é para prosa, não para o JSON.
    clean_text = _pt_severity(_strip_fence(text))
    if parsed is not None and not _pt_severity(parsed.action).strip():
        parsed = None
    if parsed is None:
        diagnosis, action = split_markdown(clean_text)
        if not action:
            # `service` só chega aqui com `has_extractable_action`; se escapar, a queda não é silenciosa.
            log.warning("Resposta do modelo sem ação extraível; usando agente local")
            return response_local(local).model_copy(update={"fallback_reason": "error"})
        drills = local.drilldowns
        title = clip_title(diagnosis) if diagnosis else local.title
        diagnosis = diagnosis or local.diagnosis
    else:
        title = _pt_severity(parsed.title)[:_TITLE_CAP]
        diagnosis = _pt_severity(parsed.diagnosis)
        action = _pt_severity(parsed.action)
        validated = validate_drilldowns(repo, filters, parsed.drilldowns)
        drills = local.drilldowns if not parsed.sent_drilldowns else validated
        # Só o bloco (ou só a ação que `normalize_action` tirou dele): a resposta vira diagnóstico + ação.
        if not split_markdown(clean_text)[0]:
            clean_text = f"{diagnosis}\n\n{_MARKER} {action}"
    return ChatResponse(
        answer=clean_text,
        mode=mode,  # type: ignore[arg-type]
        model=model,
        tools_used=list(tools_used),
        title=title,
        diagnosis=diagnosis,
        action=action,
        drilldowns=list(drills),
        base=_base(local),
        source="llm",
        tool_labels=labels_for(tools_used),
    )
