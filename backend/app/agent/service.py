"""Orquestra o modo dual: LLM com tools → LLM com contexto → regras locais."""

from __future__ import annotations

import logging
import time

from app.agent import llm, local
from app.config import Settings
from app.repository import Repository
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

# Parte do orçamento fica para o modo contexto. Sem isso, llm_timeout_s (45) maior que
# chat_budget_s (20) deixa a primeira chamada de tools consumir o prazo inteiro.
_CONTEXT_RESERVE = 0.25
_ACTION = "**Ação:**"


def _acceptable(text: str | None) -> bool:
    return bool(text) and _ACTION in text


def chat(req: ChatRequest, repo: Repository, settings: Settings, use_llm: bool = True) -> ChatResponse:
    """`use_llm=False` (cota do cliente esgotada) responde só com as regras locais."""
    f = req.filters
    if use_llm and settings.llm_enabled and repo.metrics(f)["orders"] > 0:
        deadline = time.monotonic() + settings.chat_budget_s
        tools_deadline = deadline - settings.chat_budget_s * _CONTEXT_RESERVE
        try:
            result = llm.answer_with_tools(
                req.question, req.history, repo, f, settings, deadline=tools_deadline
            )
            if result and _acceptable(result[0]):
                text, used = result
                return ChatResponse(answer=text, mode="llm-tools", model=settings.openrouter_model, tools_used=used)
            if result:
                log.warning("LLM com tools respondeu sem **Ação:**; tentando contexto")
        except Exception as exc:  # noqa: BLE001 — falha do LLM cai no próximo modo, não derruba a resposta
            log.warning("LLM com tools falhou, tentando contexto: %s", exc)

        # None (texto vazio, rodadas esgotadas ou resposta sem ação) ainda tenta contexto
        # se o prazo real não acabou. Só o deadline encerra a cadeia.
        if time.monotonic() < deadline:
            try:
                text = llm.answer_with_context(req.question, req.history, repo, f, settings, deadline=deadline)
                if _acceptable(text):
                    return ChatResponse(
                        answer=text, mode="llm-context", model=settings.openrouter_model, tools_used=[]
                    )
                if text:
                    log.warning("LLM com contexto respondeu sem **Ação:**; usando agente local")
            except Exception as exc:  # noqa: BLE001 — falha do LLM cai nas regras locais
                log.warning("LLM com contexto falhou, usando agente local: %s", exc)
        else:
            log.warning("Budget de tempo esgotado antes do modo contexto")

    return ChatResponse(
        answer=local.answer(req.question, repo, f, history=req.history),
        mode="local",
        model=None,
        tools_used=[],
    )
