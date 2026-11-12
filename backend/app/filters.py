"""Recorte (filtros) compartilhado por todos os endpoints.

Os nomes dos campos são os mesmos da query string do frontend
(`?start=2021-03-01&city=São Paulo&hub=8`), então a URL do navegador e a
chamada à API usam o mesmo contrato.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Segment = Literal["food", "good"]
ChannelType = Literal["marketplace", "own"]
Modal = Literal["moto", "bike"]
OrderStatus = Literal["delivered", "canceled"]

# Teto de cada lista e de cada texto. A URL do painel usa as mesmas chaves.
_MAX_LIST = 50
_MAX_TEXT = 80
_DATE_MIN = date(2000, 1, 1)
_DATE_MAX = date(2100, 12, 31)

ShortText = Annotated[str, Field(max_length=_MAX_TEXT)]


class Filters(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: date | None = Field(
        default=None,
        ge=_DATE_MIN,
        le=_DATE_MAX,
        description="Data inicial (inclusiva, horário de Brasília)",
    )
    end: date | None = Field(default=None, ge=_DATE_MIN, le=_DATE_MAX, description="Data final (inclusiva)")
    city: list[ShortText] = Field(default_factory=list, max_length=_MAX_LIST)
    hub: list[int] = Field(default_factory=list, max_length=_MAX_LIST)
    store: list[int] = Field(default_factory=list, max_length=_MAX_LIST)
    segment: list[Segment] = Field(default_factory=list, max_length=_MAX_LIST)
    channel_type: list[ChannelType] = Field(default_factory=list, max_length=_MAX_LIST)
    modal: list[Modal] = Field(
        default_factory=list,
        max_length=_MAX_LIST,
        description="Pedidos sem entregador saem do recorte",
    )
    status: list[OrderStatus] = Field(
        default_factory=list,
        max_length=_MAX_LIST,
        description="Status do pedido: delivered ou canceled",
    )

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
        return self.model_dump_json()

    def with_period(self, start: date, end: date) -> Filters:
        return self.model_copy(update={"start": start, "end": end})
