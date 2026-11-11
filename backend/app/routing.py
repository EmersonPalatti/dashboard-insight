"""Destinatário e mensagem de cada alerta, por template. Sem LLM.

O papel sai dos ids que o próprio alerta já carrega (drill-down, evidência ou
o sufixo do id). Não há nome de hub, loja ou cidade fixo aqui.
"""

from __future__ import annotations

import re

from collections.abc import Mapping

from app.schemas import Alert, AlertRoute

DEFAULT_RECIPIENT = "Time de operações da praça"
_STORE_IN_ID = re.compile(r"(?:^|-)store-(\d+)$")
_HUB_IN_ID = re.compile(r"(?:^|-)hub-(\d+)$")


Names = Mapping[int, str]


def route_alerts(
    alerts: list[Alert], hub_names: Names | None = None, store_names: Names | None = None
) -> list[AlertRoute]:
    """`hub_names`/`store_names` (id → nome, vindos dos dados) deixam o destinatário legível."""
    return [
        AlertRoute(
            alert_id=alert.id,
            severity=alert.severity,
            recipient=recipient_for(alert, hub_names, store_names),
            message=message_for(alert),
        )
        for alert in alerts
    ]


def message_for(alert: Alert) -> str:
    """Problema (números já em pt-BR no detalhe) e a ação esperada, prontos para enviar."""
    return f"{alert.title}. {alert.detail} Ação: {alert.action}"


def recipient_for(alert: Alert, hub_names: Names | None = None, store_names: Names | None = None) -> str:
    stores = _store_ids(alert)
    if stores:
        return _role("Loja", "Lojas", stores, store_names)
    hubs = _hub_ids(alert)
    if hubs:
        return _role("Líder do hub", "Líder dos hubs", hubs, hub_names)
    return DEFAULT_RECIPIENT


def _role(one: str, many: str, ids: list[int], names: Names | None = None) -> str:
    # Nome e id juntos: a mensagem cita o nome, e o id é o que o filtro do painel usa.
    named = [f"{names[item]} ({item})" if names and names.get(item) else str(item) for item in ids]
    if len(named) == 1:
        return f"{one} {named[0]}"
    listed = ", ".join(named[:-1]) + f" e {named[-1]}"
    return f"{many} {listed}"


def _store_ids(alert: Alert) -> list[int]:
    ids: list[int] = []
    if alert.drilldown is not None:
        ids.extend(_ints(alert.drilldown.filters.get("store")))
    if alert.evidence is not None:
        ids.extend(alert.evidence.stores)
    if not ids:
        match = _STORE_IN_ID.search(alert.id)
        if match:
            ids.append(int(match.group(1)))
    return _unique(ids)


def _hub_ids(alert: Alert) -> list[int]:
    ids: list[int] = []
    if alert.drilldown is not None:
        ids.extend(_ints(alert.drilldown.filters.get("hub")))
    if alert.evidence is not None:
        ids.extend(alert.evidence.hubs)
    if not ids:
        match = _HUB_IN_ID.search(alert.id)
        if match:
            ids.append(int(match.group(1)))
    return _unique(ids)


def _ints(values: list[str | int] | None) -> list[int]:
    found: list[int] = []
    for value in values or []:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            found.append(value)
        elif isinstance(value, str) and value.isdecimal():
            found.append(int(value))
    return found


def _unique(ids: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
