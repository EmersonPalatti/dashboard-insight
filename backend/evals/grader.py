"""Corretor de uma resposta do agente contra as expectativas de um caso.

Cada verificação tem nome, peso, nota de 0 a 1 e motivo quando falha. Verificações de nível
`warn` (formato pt-BR, latência) descontam da nota, mas não reprovam o caso. O caso passa
quando nenhuma verificação de nível `error` fica abaixo de 1.
"""

from __future__ import annotations

import re
import unicodedata
import weakref
from dataclasses import dataclass, field
from typing import Literal, get_args

from app.filters import ChannelType, Filters, Modal, OrderStatus, Segment
from app.repository import Repository
from app.schemas import ChatResponse

Unit = Literal["pct", "brl", "min", "count", "pp"]
Level = Literal["error", "warn"]

ACTION_MARKER = "**Ação:**"

# Sempre proibidos: severidade em inglês, nome de ferramenta (atual ou removida), flag e campo
# interno das tools, valor nulo vazado. Casa termo inteiro (`_` conta como letra): "amostra pequena"
# em português passa, `low_sample` cru reprova.
DEFAULT_FORBID: tuple[str, ...] = (
    "high", "medium", "low",
    "get_kpis", "get_alerts", "get_timeseries", "query_metrics", "explain_change", "drill_cause",
    "get_breakdown", "get_heatmap", "compare_slices",
    "low_sample", "volume_low_sample", "sla_below", "cancel_above", "cancel_pct", "sla_pct",
    "etapa_mais_lenta_vs_anterior", "etapa_mais_lenta_vs_resto", "variacao_vs_anterior",
    "periodo_anterior", "range_shown",
    "None", "NaN", "null", "undefined",
)

WEIGHTS: dict[str, float] = {
    "action": 2.0,
    "entities": 3.0,
    "numbers": 3.0,
    "mentions": 1.0,
    "forbidden": 2.0,
    "drilldowns": 1.0,
    "scope": 2.0,
    "format_ptbr": 1.0,
    "latency": 1.0,
}


# ----------------------------------------------------------------- expectativas
@dataclass(frozen=True)
class Entity:
    """Hub, loja, cidade, hora… que a resposta precisa nomear (no texto) ou oferecer como atalho."""

    dimension: str
    key: str | int
    label: str


@dataclass(frozen=True)
class NumberFact:
    """Número que precisa aparecer no texto. `value` na unidade de exibição (pct = 0–100, pp = pontos).

    Compara em valor absoluto: o sinal costuma vir em palavra ("caiu 1,6 p.p.").
    `tol` nulo usa a tolerância padrão da unidade; número escrito com menos casas ganha meia unidade
    da última casa ("86%" casa com 86,2%).
    `near` (rótulo de uma entidade) exige o número na mesma linha da entidade, ou a até
    NEAR_CHARS caracteres dela num parágrafo longo: "SLA de 80%" solto não prova o SLA do hub.
    """

    label: str
    value: float
    unit: Unit
    tol: float | None = None
    near: str | None = None


EntityReq = Entity | tuple[Entity, ...]
NumberReq = NumberFact | tuple[NumberFact, ...]
MentionReq = str | tuple[str, ...]


@dataclass
class Expectations:
    entities: list[EntityReq] = field(default_factory=list)  # tupla = qualquer uma serve
    numbers: list[NumberReq] = field(default_factory=list)  # tupla = qualquer um serve
    must_mention: list[MentionReq] = field(default_factory=list)  # tupla = qualquer termo serve
    forbid: list[str] = field(default_factory=list)  # termo inteiro, ou "re:<regex>" sobre o texto normalizado
    require_action: bool = True
    specific_action: bool = True  # a ação cita entidade ou faixa de horário
    max_latency_s: float | None = None


class CaseNotApplicable(Exception):
    """Os dados não sustentam o caso (ex.: não há período anterior). O caso sai do placar."""


# ----------------------------------------------------------------- texto
def norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").lower())
    out = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return out.replace("−", "-").replace("–", "-").replace("—", "-")


_FENCE = re.compile(r"```(?:leitura|json)?[^\n]*\n.*?```", re.DOTALL)
_RAW_JSON = re.compile(r"\{\s*\"[A-Za-z_]+\"\s*:")


def strip_fence(text: str) -> str:
    """Tira o bloco ```leitura``` (contrato da comanda, não é texto para o operador)."""
    return _FENCE.sub("", text or "")


def visible_text(resp: ChatResponse) -> str:
    """O que o operador lê: resposta sem o bloco leitura, mais título, diagnóstico e ação."""
    return "\n".join([strip_fence(resp.answer), resp.title or "", resp.diagnosis or "", resp.action or ""])


def _word_pattern(term: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9_])" + re.escape(norm(term)) + r"(?![a-z0-9_])")


# ----------------------------------------------------------------- números pt-BR
@dataclass(frozen=True)
class ParsedNumber:
    value: float
    unit: str  # pct, pp, min, brl, count, km, h
    half_unit: float  # meia unidade da última casa escrita (já com o multiplicador)
    raw: str


_NUMBER = re.compile(
    r"(?P<sign>[-+−]\s?)?(?P<num>\d+(?:[.,]\d+)*)"
    r"(?:\s*(?P<mult>mil\b|milh(?:ao|oes|ão|ões)\b|bilh(?:ao|oes|ão|ões)\b|mi\b|bi\b|k\b))?"
    r"(?:\s*(?P<unit>%|p\.\s?p\.?|pp\b|pontos?\s+percentuais|pontos?\b|minutos?\b|min\b|km\b|h\b|horas?\b))?",
    re.IGNORECASE,
)
_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
_MULT = {"mil": 1e3, "k": 1e3, "mi": 1e6, "bi": 1e9}


def parse_token(token: str) -> tuple[float, int] | None:
    """Converte '1.234,56', '82,4', '1.234', '82.4' ou '1,234.5' em (valor, casas decimais).

    Ponto seguido de exatamente três dígitos é milhar (pt-BR). Vírgula é decimal, salvo quando
    aparece mais de uma vez (milhar en-US).
    """
    tok = token.strip()
    if not tok:
        return None
    if "," in tok and "." in tok:
        if tok.rfind(",") > tok.rfind("."):
            integer, decimals = tok.replace(".", "").split(",", 1)
        else:
            integer, decimals = tok.replace(",", "").rsplit(".", 1)
    elif "," in tok:
        parts = tok.split(",")
        if len(parts) == 2:
            integer, decimals = parts
        else:
            integer, decimals = "".join(parts), ""
    elif "." in tok:
        parts = tok.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            integer, decimals = "".join(parts), ""
        elif len(parts) == 2:
            integer, decimals = parts
        else:
            return None
    else:
        integer, decimals = tok, ""
    if not integer.isdigit() or (decimals and not decimals.isdigit()):
        return None
    value = float(f"{integer}.{decimals}") if decimals else float(integer)
    return value, len(decimals)


def _unit_of(raw_unit: str | None, brl: bool) -> str:
    if brl:
        return "brl"
    if not raw_unit:
        return "count"
    u = norm(raw_unit).replace(" ", "")
    if u == "%":
        return "pct"
    if u.startswith(("p.p", "ponto")) or u == "pp":
        return "pp"
    if u.startswith("min"):
        return "min"
    if u == "km":
        return "km"
    return "h"


def extract_numbers(text: str) -> list[ParsedNumber]:
    cleaned = _DATE.sub(" ", text or "")
    out: list[ParsedNumber] = []
    for match in _NUMBER.finditer(cleaned):
        parsed = parse_token(match.group("num"))
        if parsed is None:
            continue
        value, decimals = parsed
        mult_raw = norm(match.group("mult") or "")
        mult = 1.0
        if mult_raw:
            mult = _MULT.get(mult_raw, 1e6 if mult_raw.startswith("milh") else 1e9 if mult_raw.startswith("bilh") else 1e3)
        before = cleaned[max(0, match.start() - 5):match.start()]
        brl = "r$" in before.lower()
        sign = -1.0 if (match.group("sign") or "").strip() in {"-", "−"} else 1.0
        out.append(ParsedNumber(
            value=sign * value * mult,
            unit=_unit_of(match.group("unit"), brl),
            half_unit=0.5 * (10 ** -decimals) * mult,
            raw=match.group(0).strip(),
        ))
    return out


def default_tol(fact: NumberFact) -> float:
    if fact.tol is not None:
        return fact.tol
    v = abs(fact.value)
    return {
        "pct": 0.15,
        "pp": 0.15,
        "min": 0.15,
        "brl": max(0.011, 0.005 * v),
        "count": max(0.5, 0.005 * v),
    }[fact.unit]


NEAR_CHARS = 120


def near_snippets(text: str, label: str) -> str:
    """Trechos do texto (normalizado) que ficam junto do rótulo: a linha inteira, ou uma janela se a linha é longa."""
    pattern = _word_pattern(label)
    out: list[str] = []
    for line in norm(text).splitlines():
        hits = list(pattern.finditer(line))
        if not hits:
            continue
        if len(line) <= 2 * NEAR_CHARS:
            out.append(line)
            continue
        out += [line[max(0, h.start() - NEAR_CHARS):h.end() + NEAR_CHARS] for h in hits]
    return "\n".join(out)


def number_found(fact: NumberFact, numbers: list[ParsedNumber], text: str | None = None) -> bool:
    if fact.near is not None and text is not None:
        numbers = extract_numbers(near_snippets(text, fact.near))
    tol = default_tol(fact)
    for n in numbers:
        if n.unit != fact.unit:
            continue
        if abs(abs(n.value) - abs(fact.value)) <= max(tol, n.half_unit) + 1e-9:
            return True
    return False


# ----------------------------------------------------------------- formato en-US
_EN_US = [
    (re.compile(r"(?<![\d.,])\d{1,3}\.\d{1,2}\s?%"), "percentual com ponto decimal"),
    (re.compile(r"R\$\s?\d{1,3}(?:,\d{3})+(?:\.\d+)?"), "R$ com vírgula de milhar"),
    (re.compile(r"R\$\s?\d+\.\d{1,2}(?!\d)"), "R$ com ponto decimal"),
    (re.compile(r"(?<![\d.,])\d+\.\d\s?min\b"), "minutos com ponto decimal"),
    (re.compile(r"(?<![\d.,])\d+\.\d\s?p\.p\."), "p.p. com ponto decimal"),
]


def en_us_hits(text: str) -> list[str]:
    hits: list[str] = []
    for pattern, label in _EN_US:
        found = pattern.search(text or "")
        if found:
            hits.append(f"{label} ('{found.group(0)}')")
    return hits


# ----------------------------------------------------------------- entidades
_WEEKDAYS = ("segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo")


def entity_in_text(entity: Entity, text_norm: str) -> bool:
    if entity.dimension == "hour":
        # "19h", "19:00", "19 horas", "19h–21h"; "9h" não casa dentro de "19h".
        return re.search(rf"(?<![\d:])0?{int(entity.key)}(?:h|:00|\s?horas?)(?![a-z])", text_norm) is not None
    if entity.dimension == "weekday":
        return _WEEKDAYS[int(entity.key)] in text_norm
    return _word_pattern(entity.label).search(text_norm) is not None


def entity_in_drills(entity: Entity, resp: ChatResponse) -> bool:
    for drill in resp.drilldowns:
        values = drill.filters.get(entity.dimension) or []
        if any(str(v) == str(entity.key) for v in values):
            return True
    return False


def entity_found(entity: Entity, text_norm: str, resp: ChatResponse) -> bool:
    return entity_in_text(entity, text_norm) or entity_in_drills(entity, resp)


def _describe(req: EntityReq | NumberReq) -> str:
    if isinstance(req, tuple):
        return " ou ".join(_describe(r) for r in req)
    if isinstance(req, Entity):
        return f"{req.dimension} '{req.label}'"
    near = f" junto de '{req.near}'" if req.near else ""
    return f"{req.label} = {req.value:.2f} {req.unit}{near}"


# ----------------------------------------------------------------- catálogo do repo
@dataclass(frozen=True)
class Catalog:
    hubs: frozenset[int]
    stores: frozenset[int]
    cities: frozenset[str]
    label_patterns: tuple[re.Pattern, ...]  # hubs, lojas, cidades, canais e pagamentos, para a ação específica
    label_words: frozenset[str]  # termos que já são parte de um nome do dado


_CATALOGS: weakref.WeakKeyDictionary[Repository, Catalog] = weakref.WeakKeyDictionary()


def catalog(repo: Repository) -> Catalog:
    cached = _CATALOGS.get(repo)
    if cached is not None:
        return cached
    meta = repo.meta()
    labels = [str(o["label"]) for key in ("hubs", "stores", "cities") for o in meta[key]]
    for dim in ("channel", "payment_method"):
        labels += [str(r["label"]) for r in repo.breakdown(Filters(), dim, limit=1000) if r["key"] is not None]
    words = frozenset(w for label in labels for w in re.findall(r"[a-z0-9_]+", norm(label)))
    built = Catalog(
        hubs=frozenset(int(o["value"]) for o in meta["hubs"]),
        stores=frozenset(int(o["value"]) for o in meta["stores"]),
        cities=frozenset(str(o["value"]) for o in meta["cities"]),
        label_patterns=tuple(_word_pattern(label) for label in sorted(set(labels), key=len, reverse=True)),
        label_words=words,
    )
    _CATALOGS[repo] = built
    return built


# ----------------------------------------------------------------- verificações
@dataclass
class Check:
    name: str
    score: float  # 0–1
    weight: float
    level: Level = "error"
    reason: str = ""

    @property
    def passed(self) -> bool:
        return self.score >= 1.0 - 1e-9


@dataclass
class Grade:
    checks: list[Check]

    @property
    def score(self) -> float:
        total = sum(c.weight for c in self.checks)
        return sum(c.weight * c.score for c in self.checks) / total if total else 1.0

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.level == "error")

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


_TIME_BAND = re.compile(r"(?<!\d)\d{1,2}h(?![a-z])|(?<!\d)\d{1,2}:\d{2}|\b(?:almoco|jantar)\b")
_DIMENSION_WORDS = re.compile(r"\b(?:moto|bike|marketplace|canal proprio|food|goods?)\b")


def check_action(resp: ChatResponse, exp: Expectations, repo: Repository) -> Check | None:
    if not exp.require_action:
        return None
    problems: list[str] = []
    parts = 0.0
    if ACTION_MARKER in (resp.answer or ""):
        parts += 1
    else:
        problems.append("resposta sem a linha **Ação:**")
    action = (resp.action or "").strip()
    if action:
        parts += 1
    else:
        problems.append("campo action vazio")
    total = 2.0
    if exp.specific_action:
        total += 1
        action_norm = norm(action)
        cat = catalog(repo)
        specific = (
            any(p.search(action_norm) for p in cat.label_patterns)
            or _TIME_BAND.search(action_norm) is not None
            or any(day in action_norm for day in _WEEKDAYS)
            or _DIMENSION_WORDS.search(action_norm) is not None
        )
        if specific:
            parts += 1
        else:
            problems.append(f"ação genérica, sem entidade nem faixa de horário: '{action[:120]}'")
    return Check("action", parts / total, WEIGHTS["action"], reason="; ".join(problems))


def check_entities(resp: ChatResponse, exp: Expectations, text_norm: str) -> Check | None:
    if not exp.entities:
        return None
    missing: list[str] = []
    for req in exp.entities:
        options = req if isinstance(req, tuple) else (req,)
        if not any(entity_found(e, text_norm, resp) for e in options):
            missing.append(_describe(req))
    score = 1 - len(missing) / len(exp.entities)
    return Check("entities", score, WEIGHTS["entities"], reason=("não cita " + "; ".join(missing)) if missing else "")


def check_numbers(exp: Expectations, text: str) -> Check | None:
    if not exp.numbers:
        return None
    numbers = extract_numbers(text)
    missing: list[str] = []
    for req in exp.numbers:
        options = req if isinstance(req, tuple) else (req,)
        if not any(number_found(f, numbers, text) for f in options):
            missing.append(_describe(req))
    score = 1 - len(missing) / len(exp.numbers)
    return Check("numbers", score, WEIGHTS["numbers"], reason=("faltou " + "; ".join(missing)) if missing else "")


def check_mentions(exp: Expectations, text_norm: str) -> Check | None:
    if not exp.must_mention:
        return None
    missing: list[str] = []
    for req in exp.must_mention:
        options = req if isinstance(req, tuple) else (req,)
        if not any(norm(term) in text_norm for term in options):
            shown = list(dict.fromkeys(norm(t).strip() for t in options))
            missing.append("/".join(shown[:4]) + ("/…" if len(shown) > 4 else ""))
    score = 1 - len(missing) / len(exp.must_mention)
    return Check("mentions", score, WEIGHTS["mentions"], reason=("não menciona " + "; ".join(missing)) if missing else "")


def forbidden_hits(text: str, terms: list[str] | tuple[str, ...], skip_words: frozenset[str] = frozenset()) -> list[str]:
    text_norm = norm(text)
    hits: list[str] = []
    for term in terms:
        if term.startswith("re:"):
            found = re.search(term[3:], text_norm)
            if found:
                hits.append(f"'{found.group(0)}'")
            continue
        if norm(term) in skip_words:
            continue
        if _word_pattern(term).search(text_norm):
            hits.append(f"'{term}'")
    return hits


def check_forbidden(resp: ChatResponse, exp: Expectations, text: str, repo: Repository) -> Check:
    hits = forbidden_hits(text, [*DEFAULT_FORBID, *exp.forbid], skip_words=catalog(repo).label_words)
    if _RAW_JSON.search(text):
        hits.append("JSON cru fora do bloco leitura")
    return Check(
        "forbidden",
        0.0 if hits else 1.0,
        WEIGHTS["forbidden"],
        reason=("termo proibido: " + ", ".join(hits)) if hits else "",
    )


_FILTER_KEYS = set(Filters.model_fields) - {"start", "end"}
_LITERALS = {
    "segment": set(get_args(Segment)),
    "channel_type": set(get_args(ChannelType)),
    "modal": set(get_args(Modal)),
    "status": set(get_args(OrderStatus)),
}


def drilldown_problems(resp: ChatResponse, repo: Repository) -> list[str]:
    cat = catalog(repo)
    problems: list[str] = []
    for drill in resp.drilldowns:
        for key, values in (drill.filters or {}).items():
            if key not in _FILTER_KEYS:
                problems.append(f"chave '{key}' fora do recorte")
                continue
            for v in values:
                if key == "hub" and (not str(v).isdigit() or int(v) not in cat.hubs):
                    problems.append(f"hub {v} não existe")
                elif key == "store" and (not str(v).isdigit() or int(v) not in cat.stores):
                    problems.append(f"loja {v} não existe")
                elif key == "city" and str(v) not in cat.cities:
                    problems.append(f"cidade '{v}' não existe")
                elif key in _LITERALS and str(v) not in _LITERALS[key]:
                    problems.append(f"{key} '{v}' inválido")
    return problems


def check_drilldowns(resp: ChatResponse, repo: Repository) -> Check:
    problems = drilldown_problems(resp, repo)
    return Check("drilldowns", 0.0 if problems else 1.0, WEIGHTS["drilldowns"], reason="; ".join(problems))


def check_scope(resp: ChatResponse, repo: Repository, f: Filters) -> Check:
    expected = int(repo.metrics(f)["orders"])
    ok = resp.base.n == expected
    return Check(
        "scope",
        1.0 if ok else 0.0,
        WEIGHTS["scope"],
        reason="" if ok else f"base.n = {resp.base.n}, recorte tem {expected} pedidos",
    )


def check_format(text: str) -> Check:
    hits = en_us_hits(text)
    return Check(
        "format_ptbr",
        0.0 if hits else 1.0,
        WEIGHTS["format_ptbr"],
        level="warn",
        reason=("formato en-US: " + ", ".join(hits)) if hits else "",
    )


def check_latency(latency_s: float | None, limit: float | None) -> Check | None:
    if limit is None or latency_s is None:
        return None
    ok = latency_s <= limit
    return Check(
        "latency",
        1.0 if ok else 0.0,
        WEIGHTS["latency"],
        level="warn",
        reason="" if ok else f"{latency_s:.1f}s acima do teto de {limit:.1f}s",
    )


def grade(
    resp: ChatResponse,
    exp: Expectations,
    repo: Repository,
    f: Filters,
    latency_s: float | None = None,
    default_max_latency_s: float | None = None,
) -> Grade:
    text = visible_text(resp)
    text_norm = norm(text)
    limit = exp.max_latency_s if exp.max_latency_s is not None else default_max_latency_s
    checks = [
        check_action(resp, exp, repo),
        check_entities(resp, exp, text_norm),
        check_numbers(exp, text),
        check_mentions(exp, text_norm),
        check_forbidden(resp, exp, text, repo),
        check_drilldowns(resp, repo),
        check_scope(resp, repo, f),
        check_format(text),
        check_latency(latency_s, limit),
    ]
    return Grade([c for c in checks if c is not None])


def error_grade(message: str) -> Grade:
    """Exceção na chamada do agente: caso reprovado com nota zero."""
    return Grade([Check("exception", 0.0, 1.0, reason=message[:300])])
