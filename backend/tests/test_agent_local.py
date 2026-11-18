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

QUESTIONS_AND_HANDLERS = [
    ("quais os alertas e problemas no recorte?", "_alerts"),
    ("onde esta o gargalo das etapas de entrega?", "_stages"),
    ("quais lojas cancelam mais pedidos?", "_cancel"),
    ("quanto estamos gastando de frete e subsidio?", "_freight"),
    ("como esta o pico do jantar?", "_peak"),
    ("como esta o sla de entrega no prazo?", "_sla"),
    ("qual o volume por canal marketplace ou proprio?", "_channels"),
    ("qual o tempo de transito por modal moto e bike?", "_modal"),
    ("quais as lojas com maior faturamento?", "_stores"),
    ("quais os hubs com maior volume na praca?", "_hubs"),
    ("qual o gmv e faturamento da operacao?", "_revenue"),
    ("me de um briefing com a visao geral", "briefing"),
    ("como estao as formas de pagamento?", "_payments"),
    ("quantos pedidos presos no fluxo existem?", "_stuck"),
    ("houve queda de volume na semana?", "_volume"),
]


def test_no_hardcoded_names_in_source():
    """Garante que nenhum nome de hub, loja ou cidade foi fixado no código de local.py."""
    source_path = Path(__file__).resolve().parent.parent / "app" / "agent" / "local.py"
    content = source_path.read_text(encoding="utf-8")
    for name in DISALLOWED_STATIC_NAMES:
        assert f'"{name}"' not in content, f"Nome fixo encontrado em local.py: {name}"
        assert f"'{name}'" not in content, f"Nome fixo encontrado em local.py: {name}"


@pytest.mark.parametrize("question,handler_name", QUESTIONS_AND_HANDLERS)
def test_every_handler_returns_action(repo, question, handler_name):
    """Todo handler do agente deve bater na rota certa, fechar com '**Ação:**' e não usar nomes fixos."""
    handler = local.resolve_handler(question)
    assert handler is not None and handler.__name__ == handler_name
    f = Filters()
    res = local.answer(question, repo, f)
    assert "**Ação:**" in res, f"Handler {handler_name} para a pergunta '{question}' não incluiu '**Ação:**'."
    assert len(res.strip().splitlines()) >= 2


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("como melhorar o sla?", "_sla"),
        ("qual a situacao dos hubs?", "_hubs"),
        ("como estao os canais?", "_channels"),
        ("como estao os modais?", "_modal"),
        ("No ranking por forma de pagamento, quem está pior e o que fazer?", "_payments"),
        ('Sobre a comanda "Pedidos presos no fluxo": o que explica isso neste recorte e o que fazer hoje?', "_stuck"),
        ('Sobre a comanda "Queda de volume na última semana": o que explica isso neste recorte e o que fazer hoje?', "_volume"),
        ('Sobre a comanda "Loja crítica: Loja 25": o que explica isso neste recorte e o que fazer hoje?', "_stores"),
    ],
)
def test_route_word_boundaries_and_panel_prompts(repo, question, expected):
    handler = local.resolve_handler(question)
    assert handler is not None and handler.__name__ == expected
    res = local.answer(question, repo, Filters())
    assert "**Ação:**" in res


def test_status_filter_honest_responses(repo):
    f_canc = Filters(status=["canceled"])
    for q in ("onde esta o gargalo?", "como esta o sla?", "quanto custa o frete?", "como estao os modais?"):
        res = local.answer(q, repo, f_canc)
        assert "status cancelado" in res.lower()
        assert "ampliar o período" not in res.lower()
        assert "**Ação:**" in res

    res_canc = local.answer("quais lojas cancelam mais?", repo, f_canc)
    assert "100,0%" not in res_canc
    assert "**Ação:**" in res_canc

    res_deliv = local.answer("quais lojas cancelam mais?", repo, Filters(status=["delivered"]))
    assert "0,0%" in res_deliv
    assert "remover o filtro" in res_deliv.lower()
    assert "**Ação:**" in res_deliv


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
    """Pergunta não reconhecida cai no briefing com sugestões e ação."""
    f = Filters()
    res = local.answer("algo completamente aleatorio sem rota", repo, f)
    assert "**Ação:**" in res
    assert "Tente perguntar:" in res
