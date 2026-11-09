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
    """Todo handler do agente deve fechar com '**Ação:**' e não usar nomes fixos."""
    f = Filters()
    res = local.answer(question, repo, f)
    assert "**Ação:**" in res, f"Handler {handler_name} para a pergunta '{question}' não incluiu '**Ação:**'."
    assert len(res.strip().splitlines()) >= 2


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
