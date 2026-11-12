"""Contratos de resposta. O frontend gera os tipos TypeScript a partir do OpenAPI."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.filters import Filters

Dimension = Literal[
    "city", "hub", "store", "channel", "channel_type", "segment",
    "modal", "driver_type", "payment_method", "hour", "weekday",
]
SortKey = Literal["orders", "gmv", "ticket", "cancel_rate", "cycle_p50", "sla_rate", "stuck_rate", "subsidy"]
Grain = Literal["hour", "day", "week"]


class Option(BaseModel):
    value: str | int
    label: str
    parent: str | int | None = None
    orders: int


class Meta(BaseModel):
    min_date: date
    max_date: date
    total_orders: int
    sla_food_min: int
    sla_good_min: int
    cities: list[Option]
    hubs: list[Option]
    stores: list[Option]
    segments: list[Option]
    channel_types: list[Option]
    modals: list[Option]
    llm_enabled: bool
    llm_model: str | None


class Metrics(BaseModel):
    """Agregados de um recorte. Campos ficam nulos quando não há pedido elegível."""

    orders: int
    delivered: int
    canceled: int
    gmv: float
    ticket: float | None
    cancel_rate: float | None
    measured: int = Field(description="Entregues com ciclo e sem presos: base do SLA e da mediana")
    low_sample: bool = Field(
        description="Base medida abaixo do mínimo do painel (MIN_MEASURED): SLA e ciclo mediano não são firmes",
    )
    cycle_p50: float | None = Field(description="Mediana do ciclo (min), sem pedidos presos")
    cycle_p90: float | None
    sla_rate: float | None = Field(description="Entregues dentro do SLA do segmento (sem pedidos presos)")
    stuck_rate: float | None = Field(description="Entregues com ciclo > 4h (presos no fluxo)")
    production_p50: float | None
    collected_p50: float | None
    expedition_p50: float | None
    transit_p50: float | None
    distance_p50_km: float | None
    fee_avg: float | None
    cost_avg: float | None
    subsidy: float | None = Field(
        description="Custo logístico menos frete cobrado, por entrega com os dois valores preenchidos",
    )


class Period(BaseModel):
    start: date
    end: date


class KpiResponse(BaseModel):
    period: Period
    current: Metrics
    previous_period: Period | None
    previous: Metrics | None


class TimePoint(BaseModel):
    t: datetime
    orders: int
    delivered: int
    gmv: float
    cancel_rate: float | None
    cycle_p50: float | None
    sla_rate: float | None


class HeatCell(BaseModel):
    weekday: int = Field(description="0 = segunda")
    hour: int
    orders: int
    cancel_rate: float | None
    cycle_p50: float | None
    sla_rate: float | None


class BreakdownRow(Metrics):
    key: str | int | None
    label: str
    parent: str | None
    sla_below: bool = Field(
        default=False,
        description="No prazo abaixo do SLA do recorte em mais de 5 pontos percentuais",
    )
    cancel_above: bool = Field(
        default=False,
        description="Cancelamento acima de 1,6x o do recorte e de pelo menos 6%",
    )


class BreakdownResponse(BaseModel):
    by: Dimension
    rows: list[BreakdownRow]


class OrderRow(BaseModel):
    order_id: int
    created_at: datetime
    status: Literal["delivered", "canceled"]
    city: str
    hub_name: str
    store_name: str
    segment: str
    channel: str
    modal: str | None
    payment_method: str | None
    amount: float
    delivery_fee: float
    cycle_min: float | None
    production_min: float | None
    transit_min: float | None
    distance_m: int | None
    on_time: bool | None


class OrdersPage(BaseModel):
    total: int
    offset: int
    limit: int
    rows: list[OrderRow]


class DrillDown(BaseModel):
    label: str
    filters: dict[str, list[str | int]]


class Evidence(BaseModel):
    """Onde a comanda se prova na tela. Enquanto ela está aberta, o painel destaca isto (sem mudar o recorte)."""

    view: Literal["kpi", "stages", "heatmap", "scatter"]
    kpi: Literal["sla_rate", "cycle_p50", "cancel_rate", "orders", "gmv", "ticket"] | None = Field(
        default=None, description="Cartão de KPI que sustenta a comanda (view=kpi)."
    )
    metric: Literal["orders", "sla_rate", "cancel_rate", "cycle_p50"] | None = Field(
        default=None, description="Métrica que o gráfico deve mostrar para a evidência aparecer (heatmap, scatter)."
    )
    hubs: list[int] = Field(default_factory=list, description="Hubs a destacar (stages).")
    hub_label: str | None = Field(default=None, description="Hub cujas lojas se destacam no gráfico de lojas (scatter).")
    stores: list[int] = Field(default_factory=list, description="Lojas a destacar (scatter).")
    hours: list[int] = Field(default_factory=list, description="Horas a destacar (heatmap).")


class Alert(BaseModel):
    id: str
    severity: Literal["high", "medium", "low"]
    category: Literal["sla", "cancelamento", "loja", "frota", "dados", "volume", "custo"]
    title: str
    detail: str
    action: str
    drilldown: DrillDown | None = None
    evidence: Evidence | None = None


class AlertsResponse(BaseModel):
    alerts: list[Alert]
    orders: int = Field(description="Pedidos no recorte; 0 significa que não há base para afirmar SLA ou cancelamento.")


class BriefingResponse(BaseModel):
    markdown: str
    start: date | None = Field(
        description="Início do período efetivo. Null se o recorte não tem essa data nem pedidos.",
    )
    end: date | None = Field(
        description="Fim do período efetivo. Null se o recorte não tem essa data nem pedidos.",
    )
    alert_count: int


class AlertRoute(BaseModel):
    alert_id: str
    severity: Literal["high", "medium", "low"]
    recipient: str
    message: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=800)
    filters: Filters = Field(default_factory=Filters)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)


class ChatResponse(BaseModel):
    answer: str
    mode: Literal["llm-tools", "llm-context", "local"]
    model: str | None
    tools_used: list[str]


class Health(BaseModel):
    status: Literal["ok"]
    orders: int
