"""Comanda da leitura: título, diagnóstico, ação, drill-down e rótulos das consultas.

O texto livre do modelo não vira filtro. Drill-down só entra se o hub, a loja
ou o outro valor existe no recorte que o servidor já consultou.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import get_args

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
}
_FENCE = re.compile(r"```(?:leitura|json)?[^\n]*\n(\{.*?\})\s*```", re.DOTALL)
_MARKS = re.compile(r"[*_#`]")


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


def label_for(name: str) -> str:
    """Rótulo pt-BR. Nome de função desconhecido não vaza para a tela."""
    if name in _TOOL_LABEL:
        return _TOOL_LABEL[name]
    if name.startswith("get_breakdown(") and name.endswith(")"):
        dim = name[len("get_breakdown("):-1]
        return _DIMENSION_LABEL.get(dim, "Quebra do recorte")
    return "Consulta do recorte"


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
    return _FENCE.sub("", text).strip()


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
    if parsed is None:
        diagnosis, action = split_markdown(text)
        if not action:
            fallback = response_local(local)
            return fallback.model_copy(update={"answer": local.answer})
        drills = local.drilldowns
        title = clip_title(diagnosis) if diagnosis else local.title
        diagnosis = diagnosis or local.diagnosis
    else:
        title = parsed.title
        diagnosis = parsed.diagnosis
        action = parsed.action
        validated = validate_drilldowns(repo, filters, parsed.drilldowns)
        drills = local.drilldowns if not parsed.sent_drilldowns else validated
    return ChatResponse(
        answer=text,
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
