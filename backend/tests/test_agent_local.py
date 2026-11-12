"""Testes do agente local: ações operacionais, sem nomes fixos e tratamento de amostra pequena."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.agent import local
from app.filters import Filters

# Nomes que jamais podem estar hardcoded no código do agente
DISALLOWED_STATIC_NAMES = [
    "Hub Centro",
    "Hub Lento",
    "Hub Preso",
    "Hub Goods",
    "Loja Quebrada",
    "São Paulo",
    "Curitiba",
    "Rio de Janeiro",
    "Porto Alegre",
]

# Cada frase abaixo só aparece na resposta daquele handler.
QUESTIONS_AND_MARKERS = [
    ("quais os alertas e problemas no recorte?", "alerta(s) no recorte"),
    ("onde esta o gargalo das etapas de entrega?", "Mediana por etapa"),
    ("quais lojas cancelam mais pedidos?", "Cancelamento no recorte"),
    ("quanto estamos gastando de frete e subsidio?", "Frete médio cobrado"),
    ("como esta o pico do jantar?", "Horários de maior volume"),
    ("como esta o sla de entrega no prazo?", "SLA do recorte"),
    ("qual o volume por canal marketplace ou proprio?", "Canais por volume"),
    ("qual o tempo de transito por modal moto e bike?", "Entregas por modal"),
    ("quais as lojas do recorte?", "Lojas com maior GMV"),
    ("quais os hubs com maior volume na praca?", "Hubs por volume"),
    ("qual o gmv e faturamento da operacao?", "entregas · ticket"),
    ("me de um briefing com a visao geral", "**Briefing do recorte**"),
]

# Substring antigo mandava estas frases para o handler errado.
FALSE_POSITIVES = [
    ("qual a situação da operação?", "**Briefing do recorte**", "alerta(s) no recorte"),
    ("como está a operação hoje?", "**Briefing do recorte**", "alerta(s) no recorte"),
    ("qual a duração média?", "**Briefing do recorte**", "alerta(s) no recorte"),
    ("preciso de mais informação", "**Briefing do recorte**", "alerta(s) no recorte"),
    ("quero uma avaliação do recorte", "**Briefing do recorte**", "alerta(s) no recorte"),
    ("como melhorar o resultado?", "**Briefing do recorte**", "Horários de maior volume"),
    ("cadê o motorista?", "**Briefing do recorte**", "Entregas por modal"),
    ("tempo de trânsito por modal", "Entregas por modal", "Mediana por etapa"),
]

MISSED_QUESTIONS = [
    ("entrega atrasada", "SLA do recorte"),
    ("lentidão na entrega", "SLA do recorte"),
    ("quais os dias da semana mais fortes?", "Horários de maior volume"),
]

THIN_INTENTS = [
    ("resumo", "**Briefing do recorte**"),
    ("quais os hubs", "Hubs por volume"),
    ("pico do jantar", "Horários de maior volume"),
    ("subsídio de frete", "Frete médio cobrado"),
    ("volume por canal", "Canais por volume"),
    ("qual o modal", "Entregas por modal"),
    ("gmv e receita", "entregas · ticket"),
]


def test_no_hardcoded_names_in_source():
    """Garante que nenhum nome de hub, loja ou cidade foi fixado no código de local.py."""
    source_path = Path(__file__).resolve().parent.parent / "app" / "agent" / "local.py"
    content = source_path.read_text(encoding="utf-8")
    for name in DISALLOWED_STATIC_NAMES:
        assert f'"{name}"' not in content, f"Nome fixo encontrado em local.py: {name}"
        assert f"'{name}'" not in content, f"Nome fixo encontrado em local.py: {name}"


@pytest.mark.parametrize("question,marker", QUESTIONS_AND_MARKERS)
def test_every_handler_returns_its_own_phrase(repo, question, marker):
    """Cada intenção devolve a frase daquele handler e fecha com ação."""
    res = local.answer(question, repo, Filters())
    assert marker in res, f"Pergunta '{question}' não produziu '{marker}'."
    assert "**Ação:**" in res
    assert len(res.strip().splitlines()) >= 2


@pytest.mark.parametrize("question,expected,forbidden", FALSE_POSITIVES)
def test_ambiguous_words_do_not_steal_the_route(repo, question, expected, forbidden):
    res = local.answer(question, repo, Filters())
    assert expected in res
    assert forbidden not in res


@pytest.mark.parametrize("question,marker", MISSED_QUESTIONS)
def test_previously_missed_questions_hit_the_right_handler(repo, question, marker):
    assert marker in local.answer(question, repo, Filters())


def test_stages_single_hub(repo):
    """Testa _stages com apenas 1 hub no recorte."""
    f = Filters(hub=[2])
    res = local.answer("onde esta o gargalo do preparo e transito?", repo, f)
    assert "**Ação:**" in res
    assert "Hub Lento" in res  # veio dos dados do repo, não fixo no código


def test_low_sample_recorte(repo):
    """Recorte com amostra pequena (low_sample) deve orientar ampliação do período."""
    # Recorte estreito com pedidos medidos < 100
    f = Filters(start=date(2021, 1, 1), end=date(2021, 1, 1), hub=[1], store=[10])
    m = repo.metrics(f)
    assert m["orders"] > 0
    assert m["low_sample"] is True

    # Teste no SLA
    res_sla = local.answer("como esta o sla?", repo, f)
    assert "**Ação:**" in res_sla
    assert "ampliar o período" in res_sla.lower() or "amostra reduzida" in res_sla.lower()

    # Teste no Cancelamento
    res_cancel = local.answer("quais lojas cancelam mais?", repo, f)
    assert "**Ação:**" in res_cancel
    assert "ampliar o período" in res_cancel.lower() or "amostra reduzida" in res_cancel.lower()


def test_unmatched_question_fallback_to_briefing(repo):
    """Pergunta não reconhecida cai no briefing, sugere perguntas e termina na ação."""
    res = local.answer("algo completamente aleatorio sem rota", repo, Filters())
    assert "**Briefing do recorte**" in res
    action_at = res.rfind("**Ação:**")
    assert action_at != -1
    assert "Tente perguntar:" in res[:action_at]
    assert "Tente perguntar:" not in res[action_at:]
    assert "\n" not in res[action_at:].rstrip()


def test_empty_recorte_ends_on_action(repo):
    res = local.answer("resumo", repo, Filters(city=["Nenhuma"]))
    assert "Nenhum pedido" in res
    assert res.rstrip().endswith("carregar dados da operação.")
    assert res.rfind("**Ação:**") > res.find("Nenhum pedido")


def test_briefing_without_alerts_names_the_busiest_hub(repo, monkeypatch):
    monkeypatch.setattr(local, "detect_alerts", lambda *_args, **_kwargs: [])
    top = repo.breakdown(Filters(), "hub", sort="orders", limit=1)[0]
    res = local.briefing(repo, Filters())
    action = res[res.rfind("**Ação:**"):]
    assert top["label"] in action
    assert "hub de maior volume" not in res


def test_channel_and_revenue_actions_use_real_metrics(repo):
    channels = local.answer("qual o volume por canal?", repo, Filters())
    assert "conversão" not in channels.lower() and "conversao" not in channels.lower()
    revenue = local.answer("qual o gmv?", repo, Filters())
    assert "campanhas de incentivo" not in revenue.lower()
    action = revenue[revenue.rfind("**Ação:**"):].lower()
    assert "ticket" in action or "cancelamento" in action


@pytest.mark.parametrize("question,marker", THIN_INTENTS)
def test_thin_sample_widens_period_for_every_intent(repo, question, marker):
    f = Filters(start=date(2021, 1, 1), end=date(2021, 1, 1), hub=[1], store=[10])
    metrics = repo.metrics(f)
    assert metrics["orders"] > 0 and metrics["low_sample"] is True
    res = local.answer(question, repo, f)
    assert res.startswith("Atenção: amostra reduzida")
    assert marker in res
    action = res[res.rfind("**Ação:**"):]
    assert "ampliar o período" in action
    assert "acionar alguém hoje" in action
    assert "\n" not in action.rstrip()


def test_followup_reuses_the_previous_user_intent(repo):
    history = [
        {"role": "user", "content": "quais lojas cancelam mais?"},
        {"role": "assistant", "content": "já te respondi"},
    ]
    res = local.answer("e agora?", repo, Filters(), history=history)
    assert "Cancelamento no recorte" in res
    alone = local.answer("e agora?", repo, Filters())
    assert "**Briefing do recorte**" in alone
    assert "Cancelamento no recorte" not in alone
