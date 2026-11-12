"""Uma fatia plantada por regra de alerta, com o contraponto saudável, mais os casos de auditoria.

As fatias estão descritas na tabela do conftest.py. Lojas 13..46 são as plantadas em março.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.alerts import THIN_SLA_ACTION, _hours_label, _weighted_sla, detect_alerts
from app.filters import Filters
from app.repository import MIN_MEASURED

HEALTHY_STORES = [18, 26]  # lojas no prazo, sem cancelamento: hub 1 e hub 2
BANNED_ANALYSIS_ACTIONS = ("Separar cancelamento", "Cruzar a queda", "Revisar frete mínimo nas lojas")


def _by_id(repo, f: Filters) -> dict:
    return {a.id: a for a in detect_alerts(repo, f)}


# Uma regra por teste: dispara na fatia dela e não dispara na fatia saudável -----------------


def test_sla_recorte_fires_on_late_store_not_on_healthy(repo):
    assert _by_id(repo, Filters(store=[16]))["sla-recorte"].severity == "high"
    assert "sla-recorte" not in _by_id(repo, Filters(store=[18]))


def test_sla_hub_fires_on_slow_hub_not_on_healthy(repo):
    alerts = _by_id(repo, Filters(segment=["food"]))
    assert "sla-hub-2" in alerts
    assert not any(a.startswith("sla-hub") for a in _by_id(repo, Filters(store=HEALTHY_STORES)))


def test_cancel_recorte_fires_on_hot_slice_not_on_healthy(repo):
    assert _by_id(repo, Filters(store=[25, 18]))["cancel-recorte"].severity == "high"
    assert "cancel-recorte" not in _by_id(repo, Filters(store=[18]))


def test_single_broken_store_takes_offline_instead_of_cancel_recorte(repo):
    # Loja 30 cancela tudo. Sozinha, a ação é tirar do ar — sem o recorte de ruptura.
    alone = _by_id(repo, Filters(store=[30]))
    assert alone["cancel-store-30"].severity == "high"
    assert alone["cancel-store-30"].title.startswith("Loja sem entregas")
    assert "Tirar" in alone["cancel-store-30"].action
    assert "cancel-recorte" not in alone
    assert "cancel-recorte" not in _by_id(repo, Filters(store=[18]))


def test_cancel_hub_fires_on_hot_hub_not_on_healthy(repo):
    assert "cancel-hub-3" in _by_id(repo, Filters())
    assert not any(a.startswith("cancel-hub") for a in _by_id(repo, Filters(store=HEALTHY_STORES)))


def test_critical_store_branch_fires_on_non_broken_store(repo):
    # Loja 25 cancela 45%, abaixo de 90%, então é "loja crítica" e não "sem entregas".
    alert = _by_id(repo, Filters(store=[25, 18]))["cancel-store-25"]
    assert alert.title.startswith("Loja crítica")
    assert alert.severity == "high"
    assert not any(a.startswith("cancel-store") for a in _by_id(repo, Filters(store=HEALTHY_STORES)))


def test_sla_pico_fires_on_peak_hours_not_on_healthy(repo):
    alert = _by_id(repo, Filters(store=[17]))["sla-pico"]
    assert alert.severity == "medium"
    assert "12h–14h e 19h–21h" in alert.detail  # item 4 de ponta a ponta
    assert "sla-pico" not in _by_id(repo, Filters(store=[18]))


def test_dados_presos_fires_on_stuck_hub_not_on_healthy(repo):
    assert "dados-presos" in _by_id(repo, Filters())
    assert "dados-presos" not in _by_id(repo, Filters(hub=[1]))


def test_volume_queda_fires_on_dropping_store_not_on_healthy(repo):
    alert = _by_id(repo, Filters(store=[19]))["volume-queda"]
    assert "Hub Centro" in alert.action and "Food Place" in alert.action  # item 6: alvo vem dos dados
    assert "volume-queda" not in _by_id(repo, Filters(store=[18]))


def test_custo_frete_fires_on_subsidised_store_not_on_healthy(repo):
    alert = _by_id(repo, Filters(store=[45]))["custo-frete"]
    assert "Loja 45" in alert.action and "Hub Goods" in alert.action
    assert "custo-frete" not in _by_id(repo, Filters(store=[18]))


# Item 1: baixa amostra rebaixa SLA e cancelamento para "low" --------------------------------


def test_small_sample_downgrades_sla_and_cancel_to_low(repo):
    f = Filters(start=date(2021, 3, 2), end=date(2021, 3, 2), store=[15])
    base = repo.metrics(f)
    assert base["measured"] == 17 and base["low_sample"] is True  # um dia, uma loja: 17 pedidos medidos
    alerts = _by_id(repo, f)

    sla = alerts["sla-recorte"]
    assert sla.severity == "low"
    assert "amostra pequena (17 pedidos medidos)" in sla.detail
    assert sla.action == THIN_SLA_ACTION
    assert not sla.action.startswith("Ligar hoje")

    cancel = alerts["cancel-recorte"]
    assert cancel.severity == "low"
    assert "amostra pequena" in cancel.detail


def test_cancel_gate_uses_total_orders_not_measured(repo):
    # Loja 13: 280 cancelados e 40 medidos. low_sample é verdadeiro, mas o total passa de 100
    # e a taxa fica abaixo de 90%, então o cancelamento do recorte segue alto.
    f = Filters(store=[13])
    metrics = repo.metrics(f)
    assert metrics["low_sample"] is True
    assert metrics["orders"] >= MIN_MEASURED
    assert metrics["cancel_rate"] < 0.9
    assert _by_id(repo, f)["cancel-recorte"].severity == "high"


# Item 2: hub com base medida pequena não vira "hub lento" ----------------------------------


def test_thin_hub_is_not_called_slow(repo):
    f = Filters(store=[13, 26])
    hubs = {h["label"]: h for h in repo.breakdown(f, "hub", min_orders=300)}
    assert len(hubs) == 2
    assert hubs["Hub Centro"]["low_sample"] is True  # 320 pedidos, só 40 medidos
    assert hubs["Hub Centro"]["orders"] >= 300
    assert not any(a.startswith("sla-hub") for a in _by_id(repo, f))


# Item 3: sem etapa acima da mediana, não há "+0,0 min" nem gargalo -------------------------


def test_hub_without_stage_gap_has_no_zero_minutes(repo):
    f = Filters(store=[46, 14])
    hub_alert = _by_id(repo, f)["sla-hub-4"]
    assert "+0,0 min" not in hub_alert.detail
    assert "Maior desvio" not in hub_alert.detail
    assert "Nenhuma etapa passa da mediana do recorte" in hub_alert.detail
    assert "nenhuma etapa passa da mediana do recorte" in hub_alert.action
    assert "Gargalo" not in hub_alert.action and "Trânsito longo" not in hub_alert.action


# Item 4: horas de pico em faixas contínuas -------------------------------------------------


@pytest.mark.parametrize(
    ("hours", "label"),
    [
        ([12, 13, 19, 20], "12h–14h e 19h–21h"),
        ([9], "09h–10h"),
        ([22, 23], "22h–24h"),
        ([], "sem pico definido"),
    ],
)
def test_hours_label_renders_contiguous_runs(hours, label):
    assert _hours_label(hours) == label


# Item 5: SLA do pico ponderado pela base medida --------------------------------------------


def test_weighted_sla_uses_measured_not_delivered():
    rows = [
        {"sla_rate": 0.5, "measured": 10, "delivered": 100},
        {"sla_rate": 1.0, "measured": 100, "delivered": 10},
    ]
    assert _weighted_sla(rows) == pytest.approx(105 / 110)  # por entregues daria 60/110


# Item 6: ações de análise viram ação operacional com alvo dos dados --------------------------


def test_cancel_action_names_worst_store_from_data(repo):
    f = Filters()
    alert = _by_id(repo, f)["cancel-recorte"]
    worst = repo.breakdown(f, "store", sort="cancel_rate", limit=1, min_orders=150)[0]
    assert worst["label"] in alert.action and worst["parent"] in alert.action
    assert "Ligar hoje" in alert.action


def test_freight_action_names_store_from_data(repo):
    f = Filters(store=[45])
    alert = _by_id(repo, f)["custo-frete"]
    worst = repo.breakdown(f, "store", sort="subsidy", limit=1, min_orders=150)[0]
    assert worst["label"] in alert.action
    assert "Ligar esta semana" in alert.action


@pytest.mark.parametrize(
    "f",
    [Filters(), Filters(store=[15]), Filters(store=[19]), Filters(store=[45]), Filters(store=[13, 26])],
)
def test_no_analysis_only_actions(repo, f):
    for alert in detect_alerts(repo, f):
        assert not any(phrase in alert.action for phrase in BANNED_ANALYSIS_ACTIONS), alert.id


# Loja a 90% sai do ar mesmo sozinha e mesmo com o recorte já alto -------------------


def test_broken_store_is_absolute_even_when_the_slice_is_that_store(repo):
    alone = _by_id(repo, Filters(store=[33]))
    metrics = repo.metrics(Filters(store=[33]))
    assert metrics["orders"] >= 150 and metrics["cancel_rate"] == pytest.approx(1.0)
    assert alone["cancel-store-33"].title.startswith("Loja sem entregas")
    assert "Tirar" in alone["cancel-store-33"].action
    assert "cancel-recorte" not in alone


def test_broken_store_survives_when_two_and_a_half_times_exceeds_100_percent(repo):
    # 33 a 100% e 34 a 50%: o recorte cancela 75%, e 2,5× passa de 100%.
    both_f = Filters(store=[33, 34])
    metrics = repo.metrics(both_f)
    assert metrics["cancel_rate"] == pytest.approx(0.75)
    assert 2.5 * metrics["cancel_rate"] > 1
    both = _by_id(repo, both_f)
    assert "Tirar" in both["cancel-store-33"].action
    assert "cancel-store-34" not in both
    assert "cancel-recorte" in both


# Segmento concentrado: base mínima e participação nos cancelamentos -----------------


def test_tiny_segment_is_not_called_concentrated(repo):
    # Food 20/150 cancelados, goods 2/2. A maior taxa é goods; os cancelamentos estão no food.
    f = Filters(store=[27, 47])
    alert = _by_id(repo, f)["cancel-recorte"]
    assert "Concentrado" not in alert.detail
    assert "goods" not in alert.detail


def test_only_segment_in_the_slice_is_not_called_concentrated(repo):
    alert = _by_id(repo, Filters(store=[27]))["cancel-recorte"]
    assert "Concentrado" not in alert.detail


def test_full_dataset_still_names_the_segment_that_concentrates_cancels(repo):
    assert "Concentrado no segmento food" in _by_id(repo, Filters())["cancel-recorte"].detail


# Amostra fina: taxa extrema não rebaixa; período fechado não manda ampliar --------


def test_extreme_thin_cancel_is_not_downgraded(repo):
    f = Filters(store=[35])
    metrics = repo.metrics(f)
    assert metrics["orders"] == 89 and metrics["delivered"] == 0
    alert = _by_id(repo, f)["cancel-recorte"]
    assert alert.severity == "high"
    assert "ampliar o período" not in alert.action
    assert "Ligar hoje" in alert.action
    dated = _by_id(repo, Filters(store=[35], start=date(2021, 3, 3), end=date(2021, 3, 3)))
    assert dated["cancel-recorte"].severity == "high"
    assert "ampliar o período" not in dated["cancel-recorte"].action


def test_thin_sample_with_no_date_filter_does_not_ask_to_widen(repo):
    f = Filters(store=[36])
    metrics = repo.metrics(f)
    assert metrics["orders"] < MIN_MEASURED
    assert 0 < metrics["cancel_rate"] < 0.9
    assert metrics["delivered"] > 0
    alerts = _by_id(repo, f)
    assert alerts["cancel-recorte"].severity == "low"
    assert alerts["sla-recorte"].severity == "low"
    assert "ampliar o período" not in alerts["cancel-recorte"].action
    assert "ampliar o período" not in alerts["sla-recorte"].action
    assert "todo o período dos dados" in alerts["cancel-recorte"].action
    assert "todo o período dos dados" in alerts["sla-recorte"].action

    closed = Filters(store=[36], start=repo.min_date, end=repo.max_date)
    closed_alerts = _by_id(repo, closed)
    assert "ampliar o período" not in closed_alerts["cancel-recorte"].action

    one_day = _by_id(repo, Filters(store=[36], start=date(2021, 3, 3), end=date(2021, 3, 3)))
    assert one_day["cancel-recorte"].action.startswith("Não ligar")
    assert "ampliar o período" in one_day["cancel-recorte"].action
    assert one_day["sla-recorte"].action == THIN_SLA_ACTION


# Recorte preso: o SLA não pede frota; o alerta de dado leva o número ---------------


def test_stuck_recorte_folds_sla_into_the_data_alert(repo):
    f = Filters(store=[28])
    metrics = repo.metrics(f)
    assert metrics["stuck_rate"] > 0.30
    assert metrics["measured"] >= MIN_MEASURED
    assert metrics["sla_rate"] < 0.80
    alerts = _by_id(repo, f)
    assert "sla-recorte" not in alerts
    assert "sla-pico" not in alerts
    data = alerts["dados-presos"]
    assert data.severity == "medium"
    assert "finalização" in data.action
    assert "frota" not in data.action.lower()
    assert "reforçar" not in data.action.lower()
    assert "SLA medido" in data.detail
    assert "não cobrar prazo nem reforçar frota" in data.detail


# Fator do hub usa vírgula decimal --------------------------------------------------


def test_hub_cancel_ratio_uses_decimal_comma(repo):
    f = Filters(store=[38, 43])
    alert = _by_id(repo, f)["cancel-hub-3"]
    factor = alert.detail.split("×")[0].rsplit("(", 1)[-1]
    assert factor == "1,7"
    assert "." not in factor


# Bordas: mais de 5 pontos, acima de 1,6× e pelo menos 6% ---------------------------


def test_hub_exactly_five_points_below_is_not_a_slow_hub(repo):
    f = Filters(store=[24, 44])
    base = repo.metrics(f)
    hubs = {int(h["key"]): h for h in repo.breakdown(f, "hub", min_orders=300)}
    assert hubs[2]["sla_rate"] == pytest.approx(0.75)
    assert base["sla_rate"] == pytest.approx(0.80)
    assert hubs[2]["sla_rate"] == pytest.approx(base["sla_rate"] - 0.05)
    assert "sla-hub-2" not in _by_id(repo, f)
    assert hubs[2]["sla_below"] is False


def test_hub_exactly_one_point_six_times_is_not_a_cancel_outlier(repo):
    f = Filters(store=[37, 49])
    base = repo.metrics(f)
    hubs = {int(h["key"]): h for h in repo.breakdown(f, "hub", min_orders=300)}
    assert hubs[3]["cancel_rate"] == pytest.approx(base["cancel_rate"] * 1.6)
    assert hubs[3]["cancel_rate"] > 0.06
    assert "cancel-hub-3" not in _by_id(repo, f)
    assert hubs[3]["cancel_above"] is False


def test_cancel_of_exactly_six_percent_is_flagged_when_the_ratio_is_higher(repo):
    f = Filters(store=[39, 48])
    base = repo.metrics(f)
    hubs = {int(h["key"]): h for h in repo.breakdown(f, "hub", min_orders=0)}
    assert hubs[3]["cancel_rate"] == pytest.approx(0.06)
    assert base["cancel_rate"] * 1.6 < 0.06
    assert hubs[3]["cancel_above"] is True
    assert hubs[4]["cancel_above"] is False
