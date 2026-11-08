"""Recorte (filtros) compartilhado por todos os endpoints.

Os nomes dos campos são os mesmos da query string do frontend
(`?start=2021-03-01&city=São Paulo&hub=8`), então a URL do navegador e a
chamada à API usam o mesmo contrato.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Segment = Literal["food", "good"]
ChannelType = Literal["marketplace", "own"]
Modal = Literal["moto", "bike"]

_MAX_ITEMS = 200


class Filters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: date | None = Field(default=None, description="Data inicial (inclusiva, horário de Brasília)")
    end: date | None = Field(default=None, description="Data final (inclusiva)")
    city: list[str] = Field(default_factory=list, max_length=_MAX_ITEMS)
    hub: list[int] = Field(default_factory=list, max_length=_MAX_ITEMS)
    store: list[int] = Field(default_factory=list, max_length=_MAX_ITEMS)
    segment: list[Segment] = Field(default_factory=list)
    channel_type: list[ChannelType] = Field(default_factory=list)
    modal: list[Modal] = Field(default_factory=list, description="Pedidos sem entregador saem do recorte")

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
        ):
            if values:
                clauses.append(f"list_contains(?, {column})")
                params.append(list(values))
        sql = " and ".join(clauses) if clauses else "true"
        return sql, params

    def cache_key(self) -> str:
        return self.model_dump_json()

    def with_period(self, start: date, end: date) -> Filters:
        return self.model_copy(update={"start": start, "end": end})
