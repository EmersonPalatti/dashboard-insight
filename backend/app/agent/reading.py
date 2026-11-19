"""Comanda da leitura: título, diagnóstico, ação, drill-down e rótulos das consultas.

O texto livre do modelo não vira filtro. Drill-down só entra se o hub, a loja
ou o outro valor existe no recorte que o servidor já consultou.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import get_args

from app import semantic
from app.filters import ChannelType, Filters, Modal, OrderStatus, Segment
from app.repository import VALUE_LABELS, Repository
from app.schemas import ChatResponse, DrillDown, ReadingBase

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


# Parêntese com argumentos de ferramenta copiados ("(window=jantar, sort=production_p50)").
_TOOL_ARGS = re.compile(r"\s*\((?=[^()]*\b[a-z_]+=)[^()]*\)")


# Chamada de ferramenta escrita na prosa ("investiga query_metrics group_by=["store"], sort="x"").
_ARG = r"""[a-z_]+=(?:\[[^\]]*\]|"[^"]*"|'[^']*'|[^\s,;.]+)"""
_BARE_ARGS = re.compile(rf"(?:,?\s*{_ARG})+")


@lru_cache(maxsize=1)
def _tool_call() -> re.Pattern[str]:
    from app.agent.llm import TOOLS  # import tardio: llm carrega a camada semântica e o repositório

    names = "|".join(sorted((t["function"]["name"] for t in TOOLS), key=len, reverse=True))
    return re.compile(rf"`?\b(?:{names})\b`?(?:\([^()]*\))?(?:,?\s*{_ARG})*")


def _pt_internal(text: str) -> str:
    pattern, terms = _internal_terms()
    text = _tool_call().sub("uma consulta", _TOOL_ARGS.sub("", text))
    text = _BARE_ARGS.sub("", text)
    return pattern.sub(lambda m: terms[m.group(1)], text)


def _pt_severity(text: str) -> str:
    """Troca severidade em inglês (`high`/`medium`/`low`) e chaves internas das tools por pt-BR."""
    for pattern, repl in _SEVERITY_PT:
        text = pattern.sub(
            lambda m, r=repl: (r[0].upper() + r[1:]) if m.group(0)[0].isupper() else r,
            text,
        )
    return _pt_internal(text)


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


# "Ação:", "**Ação**:", "__Ação:__", "Acao:" no começo da linha: modelos diferentes formatam a marca
# de jeitos diferentes. Sem normalizar, uma resposta boa sem o negrito vira leitura local.
_ACTION_LINE = re.compile(r"(?im)^[ \t]*(?:\*\*|__)?[ \t]*a[çc][ãa]o[ \t]*(?:\*\*|__)?[ \t]*:[ \t]*(?:\*\*|__)?[ \t]*")


def normalize_action(text: str) -> str:
    """Padroniza a linha de ação em `**Ação:**`; sem a linha, usa a ação do bloco `leitura` se houver."""
    text = _ACTION_LINE.sub("**Ação:** ", text)
    if "**Ação:**" in text:
        return text
    parsed = parse_leitura(text)
    if parsed is None or not parsed.action.strip():
        return text
    fence = text.find("```")
    body = (text[:fence] if fence >= 0 else text).rstrip()
    rest = text[fence:] if fence >= 0 else ""
    return f"{body}\n\n**Ação:** {parsed.action.strip()}\n\n{rest}".rstrip()


def split_markdown(text: str) -> tuple[str, str]:
    """Separa o corpo da última linha que é só a ação. Sem ação, o segundo item vem vazio."""
    stripped = _strip_fence(text).rstrip()
    marker = "**Ação:**"
    index = stripped.rfind(marker)
    if index == -1:
        return stripped, ""
    line_start = stripped.rfind("\n", 0, index) + 1
    if stripped[line_start:index].strip() or "\n" in stripped[index:]:
        return stripped, ""
    body = stripped[:line_start].rstrip()
    action = stripped[index + len(marker):].strip()
    return body, action


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
    """Fecha a comanda do modelo. Sem JSON válido, usa o texto e os atalhos das regras."""
    parsed = parse_leitura(text)
    clean_text = _pt_severity(text)
    if parsed is None:
        clean_text = _strip_fence(clean_text)
        diagnosis, action = split_markdown(clean_text)
        if not action:
            fallback = response_local(local)
            return fallback.model_copy(update={"answer": local.answer})
        drills = local.drilldowns
        title = clip_title(diagnosis) if diagnosis else local.title
        diagnosis = diagnosis or local.diagnosis
    else:
        title = _pt_severity(parsed.title)[:_TITLE_CAP]
        diagnosis = _pt_severity(parsed.diagnosis)
        action = _pt_severity(parsed.action)
        validated = validate_drilldowns(repo, filters, parsed.drilldowns)
        drills = local.drilldowns if not parsed.sent_drilldowns else validated
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
