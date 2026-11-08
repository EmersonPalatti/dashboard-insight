"""Orquestra o modo dual: LLM com tools → LLM com contexto → regras locais."""

from __future__ import annotations

import logging

from app.agent import llm, local
from app.config import Settings
from app.repository import Repository
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)


def chat(req: ChatRequest, repo: Repository, settings: Settings) -> ChatResponse:
    f = req.filters
    if settings.llm_enabled and repo.metrics(f)["orders"] > 0:
        try:
            result = llm.answer_with_tools(req.question, req.history, repo, f, settings)
            if result:
                text, used = result
                return ChatResponse(answer=text, mode="llm-tools", model=settings.openrouter_model, tools_used=used)
        except Exception as exc:
            log.warning("LLM com tools falhou, tentando contexto: %s", exc)
        try:
            text = llm.answer_with_context(req.question, req.history, repo, f, settings)
            if text:
                return ChatResponse(answer=text, mode="llm-context", model=settings.openrouter_model, tools_used=[])
        except Exception as exc:
            log.warning("LLM com contexto falhou, usando agente local: %s", exc)

    return ChatResponse(answer=local.answer(req.question, repo, f), mode="local", model=None, tools_used=[])
