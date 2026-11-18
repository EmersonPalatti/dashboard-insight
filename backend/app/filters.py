"""Recorte (filtros) compartilhado por todos os endpoints.

Os nomes dos campos são os mesmos da query string do frontend
(`?start=2021-03-01&city=São Paulo&hub=8`), então a URL do navegador e a
chamada à API usam o mesmo contrato.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Segment = Literal["food", "good"]
ChannelType = Literal["marketplace", "own"]
Modal = Literal["moto", "bike"]
OrderStatus = Literal["delivered", "canceled"]
CityStr = Annotated[str, Field(max_length=80)]

_MAX_ITEMS = 200


class Filters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: date | None = Field(default=None, description="Data inicial (inclusiva, horário de Brasília)")
    end: date | None = Field(default=None, description="Data final (inclusiva)")
    city: list[CityStr] = Field(default_factory=list, max_length=_MAX_ITEMS)
    hub: list[int] = Field(default_factory=list, max_length=_MAX_ITEMS)
    store: list[int] = Field(default_factory=list, max_length=_MAX_ITEMS)
    segment: list[Segment] = Field(default_factory=list)
    channel_type: list[ChannelType] = Field(default_factory=list)
    modal: list[Modal] = Field(default_factory=list, description="Pedidos sem entregador saem do recorte")
    status: list[OrderStatus] = Field(default_factory=list, description="Status do pedido: delivered ou canceled")

    @model_validator(mode="after")
    def _check_range(self) -> Filters:
        if self.start and self.end and self.end < self.start:
            raise ValueError("end deve ser maior ou igual a start")
        return self

    def where(self) -> tuple[str, list]:
        """Cláusula WHERE parametrizada. Nunca interpola valores do usuário."""
        clauses: list[str] = []
        params: list = []
        if self.start:
            clauses.append("created_date >= ?")
            params.append(self.start)
        if self.end:
            clauses.append("created_date <= ?")
            params.append(self.end)
        for column, values in (
            ("city", self.city),
            ("hub_id", self.hub),
            ("store_id", self.store),
            ("segment", self.segment),
            ("channel_type", self.channel_type),
            ("modal", self.modal),
            ("status", self.status),
        ):
            if values:
                clauses.append(f"list_contains(?, {column})")
                params.append(list(values))
        sql = " and ".join(clauses) if clauses else "true"
        return sql, params

    def cache_key(self) -> str:
        canonical = {
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "city": sorted(set(self.city)),
            "hub": sorted(set(self.hub)),
            "store": sorted(set(self.store)),
            "segment": sorted(set(self.segment)),
            "channel_type": sorted(set(self.channel_type)),
            "modal": sorted(set(self.modal)),
            "status": sorted(set(self.status)),
        }
        return json.dumps(canonical, ensure_ascii=False, separators=(",", ":"))

    def with_period(self, start: date, end: date) -> Filters:
        return self.model_copy(update={"start": start, "end": end})
