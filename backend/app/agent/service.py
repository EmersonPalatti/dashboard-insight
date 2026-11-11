"""Orquestra o modo dual: LLM com tools → LLM com contexto → regras locais."""

from __future__ import annotations

import logging
import time

from app.agent import llm, local
from app.config import Settings
from app.repository import Repository
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)


def chat(req: ChatRequest, repo: Repository, settings: Settings, use_llm: bool = True) -> ChatResponse:
    """`use_llm=False` (cota do cliente esgotada) responde só com as regras locais."""
    f = req.filters
    if use_llm and settings.llm_enabled and repo.metrics(f)["orders"] > 0:
        deadline = time.monotonic() + settings.chat_budget_s
        skip_context = False
        try:
            result = llm.answer_with_tools(req.question, req.history, repo, f, settings, deadline=deadline)
            if result:
                text, used = result
                return ChatResponse(answer=text, mode="llm-tools", model=settings.openrouter_model, tools_used=used)
            # Retornou None: esgotou rounds ou esgotou o budget no caminho de tools
            skip_context = True
        except Exception as exc:  # noqa: BLE001 — falha do LLM cai no próximo modo, não derruba a resposta
            log.warning("LLM com tools falhou, tentando contexto: %s", exc)
            if time.monotonic() >= deadline:
                skip_context = True

        if not skip_context and time.monotonic() < deadline:
            try:
                text = llm.answer_with_context(req.question, req.history, repo, f, settings, deadline=deadline)
                if text:
                    return ChatResponse(answer=text, mode="llm-context", model=settings.openrouter_model, tools_used=[])
            except Exception as exc:  # noqa: BLE001 — falha do LLM cai nas regras locais
                log.warning("LLM com contexto falhou, usando agente local: %s", exc)

    return ChatResponse(answer=local.answer(req.question, repo, f), mode="local", model=None, tools_used=[])
