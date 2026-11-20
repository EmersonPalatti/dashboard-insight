"""Camada semântica do agente: métricas, dimensões, conceitos, mapa causal e exemplos.

A fonte é `semantic.toml`. Aqui ela vira dataclasses imutáveis, validadas na carga, com três
usos: `resolve()` liga o texto do operador às chaves do recorte, `prompt_block()` entrega o
glossário compacto para o system prompt e `describe()` responde a definição de uma chave.
"""

from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings

SOURCE = Path(__file__).with_name("semantic.toml")

UNITS = {"pct": "%", "brl": "R$", "min": "min", "km": "km", "count": "nº"}
KINDS = {"rate", "median", "quantile", "avg", "count", "sum"}
BETTER = {"up": "↑", "down": "↓"}
BASES = ("orders", "delivered", "measured", "valid", "priced", "sale")
WEEKDAY_SHORT = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
PROMPT_LIMIT = 6000
# Prazos de SLA saem de Settings (SLA_FOOD_MIN / SLA_GOOD_MIN): o TOML escreve `{sla_food_min}`.
SLA_PLACEHOLDERS = ("sla_food_min", "sla_good_min")


class SemanticError(ValueError):
    """TOML da camada semântica inconsistente. É ValueError para quem só quer saber que falhou."""


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    kind: str
    better: str | None
    base: str
    definition: str
    synonyms: tuple[str, ...]
    extra: bool = False
    numerator: str | None = None


@dataclass(frozen=True)
class Dimension:
    key: str
    label: str
    definition: str
    synonyms: tuple[str, ...]
    has_id: bool
    values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Concept:
    key: str
    label: str
    definition: str
    synonyms: tuple[str, ...]
    related: tuple[str, ...]
    # Janela de tempo (almoço, jantar, fim de semana...) usada como `where.window` em query_metrics
    # e drill_cause. Vazia nos demais.
    hours: tuple[int, ...] = ()
    weekdays: tuple[int, ...] = ()


@dataclass(frozen=True)
class CausalLink:
    effect: str
    drivers: tuple[str, ...]
    dimensions: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class Example:
    question: str
    plan: str


@dataclass(frozen=True)
class Match:
    kind: str
    key: str
    term: str


# ------------------------------------------------------------------ normalização


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _stem(word: str) -> str:
    """Plural simples do português, igual nos dois lados: 'lojas' = 'loja', 'canais' = 'canal'."""
    if len(word) <= 3:
        return word
    if word.endswith(("oes", "aes")):
        return word[:-3] + "ao"
    if word.endswith("ais"):
        return word[:-2] + "l"
    if word.endswith(("res", "zes")) and len(word) > 4:
        return word[:-2]
    if word.endswith("s"):
        return word[:-1]
    return word


def _tokens(text: str) -> tuple[str, ...]:
    # `_` separa palavra: a chave `sla_rate` vira a frase "sla rate".
    return tuple(_stem(w) for w in re.findall(r"[a-z0-9]+", _fold(text)))


# ------------------------------------------------------------------ camada


class SemanticLayer:
    def __init__(
        self,
        bases: dict[str, str],
        metrics: dict[str, Metric],
        dimensions: dict[str, Dimension],
        concepts: dict[str, Concept],
        causal: dict[str, CausalLink],
        examples: tuple[Example, ...],
    ) -> None:
        self.bases = bases
        self.metrics = metrics
        self.dimensions = dimensions
        self.concepts = concepts
        self.causal = causal
        self.examples = examples
        self._index = _build_index(metrics, dimensions, concepts)
        self._longest = max((len(t) for t in self._index), default=0)

    def metric_keys(self, *, kind: str | None = None, include_extra: bool = True) -> list[str]:
        return [
            m.key for m in self.metrics.values()
            if (kind is None or m.kind == kind) and (include_extra or not m.extra)
        ]

    def resolve(self, text: str) -> list[Match]:
        """Termos do texto que apontam para métrica, dimensão ou conceito, na ordem em que aparecem.

        Palavra inteira ou frase, sem acento nem caixa; a frase mais longa vence no mesmo ponto,
        então "tempo de trânsito" casa a etapa e não "tempo". Cada chave sai uma vez só.
        """
        words = _tokens(text)
        found: list[Match] = []
        seen: set[tuple[str, str]] = set()
        i = 0
        while i < len(words):
            for span in range(min(self._longest, len(words) - i), 0, -1):
                hits = self._index.get(words[i:i + span])
                if hits:
                    for kind, key, term in hits:
                        if (kind, key) not in seen:
                            seen.add((kind, key))
                            found.append(Match(kind, key, term))
                    i += span
                    break
            else:
                i += 1
        return found

    def value_code(self, dimension: str, term: str) -> str | None:
        """Código cru de um valor citado ('sexta' em weekday -> '4'), para montar filtro ou fatia."""
        dim = self.dimensions.get(dimension)
        if dim is None:
            return None
        wanted = _tokens(term)
        for code, label in dim.values.items():
            if wanted in (_tokens(code), _tokens(label)):
                return code
        return None

    def describe(self, key: str) -> str | None:
        if metric := self.metrics.get(key):
            better = {"up": ", maior é melhor", "down": ", menor é melhor"}.get(metric.better or "", "")
            return (
                f"{metric.label} (`{key}`, {UNITS[metric.unit]}, base: {self.bases[metric.base]}{better}): "
                f"{metric.definition}"
            )
        if dim := self.dimensions.get(key):
            values = f" Valores: {_values_text(dim)}." if dim.values else ""
            return f"{dim.label} (`{key}`): {dim.definition}{values}"
        if concept := self.concepts.get(key):
            return f"{concept.label}: {concept.definition}"
        return None

    def prompt_block(self) -> str:
        """Glossário para o system prompt. Curto de propósito: cada caractere é token pago."""
        lines = [
            "## Glossário do recorte",
            "Bases: " + " · ".join(f"{k} = {v}" for k, v in self.bases.items()) + ".",
            "Métricas (`chave` unidade base, ↑/↓ = melhor; * = só query_metrics):",
        ]
        for m in self.metrics.values():
            tag = f"{UNITS[m.unit]} {m.base}{BETTER.get(m.better or '', '')}"
            lines.append(f"- `{m.key}`{'*' if m.extra else ''} {tag}: {m.definition}")
        lines.append("Dimensões (`by`): " + "; ".join(_dimension_text(d) for d in self.dimensions.values()) + ".")
        windows = [c for c in self.concepts.values() if c.hours or c.weekdays]
        lines.append("Conceitos:")
        for c in self.concepts.values():
            if c not in windows:
                lines.append(f"- {c.label}: {c.definition}")
        if windows:
            lines.append("- Janelas: " + " · ".join(f"{c.label.lower()} {_window_text(c)}" for c in windows) + ".")
        lines.append("Mapa causal (efeito ← checar, em ordem | onde concentra):")
        for link in self.causal.values():
            drivers = ", ".join(link.drivers) or "—"
            lines.append(f"- `{link.effect}` ← {drivers} | {', '.join(link.dimensions)}: {link.note}")
        return "\n".join(lines)


def _values_text(dim: Dimension) -> str:
    return ", ".join(code if code == label else f"{code} = {label}" for code, label in dim.values.items())


def _dimension_text(dim: Dimension) -> str:
    if dim.key == "weekday":
        return "weekday (0 = seg … 6 = dom)"
    if dim.key == "hour":
        return "hour (0–23)"
    detail = "id" if dim.has_id else (_values_text(dim) if dim.values and len(dim.values) <= 3 else "")
    return f"{dim.key} ({detail})" if detail else dim.key


def _window_text(concept: Concept) -> str:
    parts: list[str] = []
    if concept.hours:
        parts.append(f"{min(concept.hours)}h–{max(concept.hours) + 1}h")
    if concept.weekdays:
        days = sorted(concept.weekdays)
        contiguous = days == list(range(days[0], days[-1] + 1))
        names = [WEEKDAY_SHORT[d] for d in days]
        parts.append(f"{names[0]}–{names[-1]}" if contiguous and len(days) > 2 else "/".join(names))
    return " ".join(parts)


def _build_index(
    metrics: dict[str, Metric], dimensions: dict[str, Dimension], concepts: dict[str, Concept]
) -> dict[tuple[str, ...], list[tuple[str, str, str]]]:
    """Frase normalizada -> (tipo, chave, termo). Rótulo e chave também valem como termo.

    Sinônimo entra antes do rótulo e da chave, então o termo devolvido é o mais natural.
    Valores crus numéricos (hora, dia) ficam de fora: '4' no texto não é sexta-feira.
    """
    index: dict[tuple[str, ...], list[tuple[str, str, str]]] = {}
    owner: dict[tuple[str, tuple[str, ...]], tuple[str, str]] = {}

    def add(kind: str, key: str, term: str) -> None:
        tokens = _tokens(term)
        if not tokens:
            raise SemanticError(f"{kind} {key}: termo vazio {term!r}")
        previous = owner.get((kind, tokens))
        if previous is not None:
            if previous[0] != key:
                raise SemanticError(
                    f"sinônimo {term!r} aponta para dois {kind}s: {previous[0]} ({previous[1]!r}) e {key}"
                )
            return
        owner[(kind, tokens)] = (key, term)
        index.setdefault(tokens, []).append((kind, key, term))

    for m in metrics.values():
        for term in (*m.synonyms, m.label.lower(), m.key):
            add("metric", m.key, term)
    for d in dimensions.values():
        for term in (*d.synonyms, d.label.lower(), d.key):
            add("dimension", d.key, term)
        for code, label in d.values.items():
            add("dimension", d.key, label)
            if not code.isdigit():
                add("dimension", d.key, code)
    for c in concepts.values():
        for term in (*c.synonyms, c.label.lower(), c.key):
            add("concept", c.key, term)
    return index


# ------------------------------------------------------------------ carga e validação

_METRIC_FIELDS = {"label", "unit", "kind", "better", "base", "definition", "synonyms", "extra", "numerator"}
_DIMENSION_FIELDS = {"label", "definition", "synonyms", "has_id", "values"}
_CONCEPT_FIELDS = {"label", "definition", "synonyms", "related", "hours", "weekdays"}
_CAUSAL_FIELDS = {"drivers", "dimensions", "note"}
_EXAMPLE_FIELDS = {"question", "plan"}
_SECTIONS = {"bases", "metrics", "dimensions", "concepts", "causal", "examples"}


def _check_fields(where: str, raw: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise SemanticError(f"{where}: esperava tabela")
    unknown = set(raw) - allowed
    if unknown:
        raise SemanticError(f"{where}: campo desconhecido {sorted(unknown)}")
    missing = required - set(raw)
    if missing:
        raise SemanticError(f"{where}: faltam {sorted(missing)}")
    return raw


def _text(where: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SemanticError(f"{where}: esperava texto não vazio")
    return value.strip()


def _texts(where: str, value: Any, *, lower: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SemanticError(f"{where}: esperava lista")
    items = tuple(_text(where, v) for v in value)
    if lower and any(v != v.lower() for v in items):
        raise SemanticError(f"{where}: sinônimo deve estar em minúsculas")
    return items


def _ints(where: str, value: Any, hi: int) -> tuple[int, ...]:
    if not isinstance(value, list) or any(type(v) is not int or not 0 <= v <= hi for v in value):
        raise SemanticError(f"{where}: esperava inteiros de 0 a {hi}")
    return tuple(value)


def _flag(where: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise SemanticError(f"{where}: esperava booleano")
    return value


def _choice(where: str, value: Any, allowed: set[str] | tuple[str, ...]) -> str:
    if value not in allowed:
        raise SemanticError(f"{where}: {value!r} fora de {sorted(allowed)}")
    return value


def _metric(key: str, raw: Any) -> Metric:
    where = f"metrics.{key}"
    raw = _check_fields(where, raw, _METRIC_FIELDS, {"label", "unit", "kind", "base", "definition", "synonyms"})
    metric = Metric(
        key=key,
        label=_text(f"{where}.label", raw["label"]),
        unit=_choice(f"{where}.unit", raw["unit"], set(UNITS)),
        kind=_choice(f"{where}.kind", raw["kind"], KINDS),
        better=_choice(f"{where}.better", raw["better"], set(BETTER)) if "better" in raw else None,
        base=_choice(f"{where}.base", raw["base"], BASES),
        definition=_text(f"{where}.definition", raw["definition"]),
        synonyms=_texts(f"{where}.synonyms", raw["synonyms"], lower=True),
        extra=_flag(f"{where}.extra", raw.get("extra", False)),
        numerator=_text(f"{where}.numerator", raw["numerator"]) if "numerator" in raw else None,
    )
    # Taxa é fração 0..1 exibida em %; mediana e quantil são de tempo ou distância.
    if (metric.kind == "rate") != (metric.unit == "pct"):
        raise SemanticError(f"{where}: kind 'rate' e unit 'pct' andam juntos")
    if metric.kind in ("median", "quantile") and metric.unit not in ("min", "km"):
        raise SemanticError(f"{where}: {metric.kind} só em min ou km")
    if metric.numerator is not None and metric.kind != "rate":
        raise SemanticError(f"{where}: numerator só vale para kind 'rate'")
    return metric


def _dimension(key: str, raw: Any) -> Dimension:
    where = f"dimensions.{key}"
    raw = _check_fields(where, raw, _DIMENSION_FIELDS, {"label", "definition", "synonyms"})
    values = raw.get("values", {})
    if not isinstance(values, dict):
        raise SemanticError(f"{where}.values: esperava tabela")
    return Dimension(
        key=key,
        label=_text(f"{where}.label", raw["label"]),
        definition=_text(f"{where}.definition", raw["definition"]),
        synonyms=_texts(f"{where}.synonyms", raw["synonyms"], lower=True),
        has_id=_flag(f"{where}.has_id", raw.get("has_id", False)),
        values={str(code): _text(f"{where}.values.{code}", label) for code, label in values.items()},
    )


def _concept(key: str, raw: Any) -> Concept:
    where = f"concepts.{key}"
    raw = _check_fields(where, raw, _CONCEPT_FIELDS, {"label", "definition", "synonyms"})
    return Concept(
        key=key,
        label=_text(f"{where}.label", raw["label"]),
        definition=_text(f"{where}.definition", raw["definition"]),
        synonyms=_texts(f"{where}.synonyms", raw["synonyms"], lower=True),
        related=_texts(f"{where}.related", raw.get("related", [])),
        hours=_ints(f"{where}.hours", raw.get("hours", []), 23),
        weekdays=_ints(f"{where}.weekdays", raw.get("weekdays", []), 6),
    )


def _causal(effect: str, raw: Any) -> CausalLink:
    where = f"causal.{effect}"
    raw = _check_fields(where, raw, _CAUSAL_FIELDS, _CAUSAL_FIELDS)
    return CausalLink(
        effect=effect,
        drivers=_texts(f"{where}.drivers", raw["drivers"]),
        dimensions=_texts(f"{where}.dimensions", raw["dimensions"]),
        note=_text(f"{where}.note", raw["note"]),
    )


def _example(i: int, raw: Any) -> Example:
    where = f"examples[{i}]"
    raw = _check_fields(where, raw, _EXAMPLE_FIELDS, _EXAMPLE_FIELDS)
    return Example(question=_text(f"{where}.question", raw["question"]), plan=_text(f"{where}.plan", raw["plan"]))


def _table(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise SemanticError(f"{name}: esperava tabela")
    return value


def _build(data: dict[str, Any]) -> SemanticLayer:
    """Monta e valida a camada a partir do TOML já lido. Qualquer inconsistência vira SemanticError."""
    unknown = set(data) - _SECTIONS
    if unknown:
        raise SemanticError(f"seção desconhecida {sorted(unknown)}")
    bases = {k: _text(f"bases.{k}", v) for k, v in _table(data, "bases").items()}
    if set(bases) != set(BASES):
        raise SemanticError(f"bases: esperava exatamente {list(BASES)}")

    metrics = {k: _metric(k, v) for k, v in _table(data, "metrics").items()}
    dimensions = {k: _dimension(k, v) for k, v in _table(data, "dimensions").items()}
    concepts = {k: _concept(k, v) for k, v in _table(data, "concepts").items()}
    causal = {k: _causal(k, v) for k, v in _table(data, "causal").items()}
    raw_examples = data.get("examples", [])
    if not isinstance(raw_examples, list):
        raise SemanticError("examples: esperava lista de tabelas")
    examples = tuple(_example(i, v) for i, v in enumerate(raw_examples))
    if not metrics or not dimensions:
        raise SemanticError("metrics e dimensions não podem ficar vazios")

    # describe() procura a chave nos três tipos: a mesma chave em dois deles seria ambígua.
    clash = (set(metrics) & set(dimensions)) | (set(metrics) & set(concepts)) | (set(dimensions) & set(concepts))
    if clash:
        raise SemanticError(f"chave repetida entre métricas, dimensões e conceitos: {sorted(clash)}")

    for m in metrics.values():
        if m.numerator is not None:
            target = metrics.get(m.numerator)
            if target is None or target.kind != "count":
                raise SemanticError(f"metrics.{m.key}.numerator: {m.numerator!r} não é métrica de contagem")
    known = set(metrics) | set(dimensions) | set(concepts)
    for c in concepts.values():
        missing = [r for r in c.related if r not in known]
        if missing:
            raise SemanticError(f"concepts.{c.key}.related: chave desconhecida {missing}")
    for link in causal.values():
        if link.effect not in metrics:
            raise SemanticError(f"causal.{link.effect}: efeito não é métrica")
        bad = [d for d in link.drivers if d not in metrics or d == link.effect]
        if bad:
            raise SemanticError(f"causal.{link.effect}.drivers: métrica desconhecida ou o próprio efeito {bad}")
        bad = [d for d in link.dimensions if d not in dimensions]
        if bad or not link.dimensions:
            raise SemanticError(f"causal.{link.effect}.dimensions: dimensão desconhecida ou lista vazia {bad}")

    layer = SemanticLayer(bases, metrics, dimensions, concepts, causal, examples)
    size = len(layer.prompt_block())
    if size > PROMPT_LIMIT:
        raise SemanticError(f"prompt_block com {size} caracteres passa do teto de {PROMPT_LIMIT}")
    return layer


def parse(text: str, *, sla_food_min: int | None = None, sla_good_min: int | None = None) -> SemanticLayer:
    """TOML em texto -> camada validada. Erro de sintaxe também sai como ValueError.

    `{sla_food_min}` / `{sla_good_min}` viram os prazos recebidos (padrão: os de Settings).
    """
    given = {"sla_food_min": sla_food_min, "sla_good_min": sla_good_min}
    for name in SLA_PLACEHOLDERS:
        value = given[name] if given[name] is not None else Settings.model_fields[name].default
        text = text.replace("{" + name + "}", str(int(value)))
    return _build(tomllib.loads(text))


@lru_cache
def load() -> SemanticLayer:
    settings = get_settings()
    return parse(
        SOURCE.read_text(encoding="utf-8"),
        sla_food_min=settings.sla_food_min,
        sla_good_min=settings.sla_good_min,
    )
