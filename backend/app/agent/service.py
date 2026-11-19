"""Orquestra o modo dual: LLM com tools → LLM com contexto → regras locais."""

from __future__ import annotations

import logging
import time

from app.agent import llm, local
from app.agent.reading import response_llm, response_local
from app.config import Settings
from app.repository import Repository
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

# Reserva do modo contexto: sai do prazo das tools e é o mínimo que precisa sobrar para tentar o
# contexto (uma chamada sem tools a um modelo gratuito raramente fecha em menos de ~3 s). Com o
# orçamento padrão de 12 s, as tools ficam com 9 s e o contexto com 3 s. Orçamentos pequenos (testes)
# reservam só 25%, senão a reserva comeria o prazo inteiro.
CONTEXT_MIN_S = 3.0
_CONTEXT_SHARE = 0.25
_ACTION = "**Ação:**"


def _acceptable(text: str | None) -> bool:
    return bool(text) and _ACTION in text


def context_reserve(budget_s: float) -> float:
    return min(CONTEXT_MIN_S, budget_s * _CONTEXT_SHARE)


def chat(req: ChatRequest, repo: Repository, settings: Settings, use_llm: bool = True) -> ChatResponse:
    """`use_llm=False` (cota esgotada ou engine=local) responde só com as regras locais."""
    f = req.filters
    local_reading = local.build_reading(req.question, repo, f, history=req.history)
    # engine=local não entra na cadeia: a leitura já está pronta e a cota fica intacta.
    if use_llm and req.engine != "local" and settings.llm_enabled and local_reading.n > 0:
        deadline = time.monotonic() + settings.chat_budget_s
        reserve = context_reserve(settings.chat_budget_s)
        tools_deadline = deadline - reserve
        try:
            result = llm.answer_with_tools(
                req.question, req.history, repo, f, settings, deadline=tools_deadline
            )
            if result and _acceptable(result[0]):
                text, used = result
                return response_llm(text, "llm-tools", settings.openrouter_model, used, local_reading, repo, f)
            if result:
                log.warning("LLM com tools respondeu sem **Ação:**; tentando contexto")
        except Exception as exc:  # noqa: BLE001 — falha do LLM cai no próximo modo, não derruba a resposta
            log.warning("LLM com tools falhou, tentando contexto: %s", exc)

        # None (texto vazio, rodadas esgotadas ou resposta sem ação) ainda tenta contexto se sobrou
        # pelo menos a reserva. Menos que isso, a chamada não fecha a tempo: vai a leitura local.
        if deadline - time.monotonic() >= reserve:
            try:
                context = llm.answer_with_context(req.question, req.history, repo, f, settings, deadline=deadline)
                if context and _acceptable(context[0]):
                    text, used = context
                    return response_llm(text, "llm-context", settings.openrouter_model, used, local_reading, repo, f)
                if context and context[0]:
                    log.warning("LLM com contexto respondeu sem **Ação:**; usando agente local")
            except Exception as exc:  # noqa: BLE001 — falha do LLM cai nas regras locais
                log.warning("LLM com contexto falhou, usando agente local: %s", exc)
        else:
            log.warning("Prazo restante abaixo da reserva (%.1f s); pulando o modo contexto", reserve)

    return response_local(local_reading)
