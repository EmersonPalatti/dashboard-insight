"""Orquestra o modo dual: LLM com tools → LLM com contexto → regras locais.

Pergunta "por que mudou" com período anterior troca o loop de tools pelo grafo de investigação
(`investigate.py`); o resto da cadeia e os motivos de fallback são os mesmos.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta

import openai

from app.agent import investigate, llm, local
from app.agent.reading import normalize_action, response_llm, response_local
from app.config import Settings
from app.repository import Repository
from app.schemas import ChatRequest, ChatResponse

log = logging.getLogger(__name__)

# Reserva do modo contexto: sai do prazo das tools e é o mínimo que precisa sobrar para tentar o
# contexto (uma chamada sem tools a um modelo gratuito raramente fecha em menos de ~3 s). Com o
# orçamento padrão de 20 s, as tools ficam com 17 s e o contexto com 3 s. Orçamentos pequenos (testes)
# reservam só 25%, senão a reserva comeria o prazo inteiro.
CONTEXT_MIN_S = 3.0
_CONTEXT_SHARE = 0.25
_ACTION = "**Ação:**"


FallbackReason = str  # "quota" | "busy" | "timeout" | "error"


class _QuotaBreaker:
    """Depois de um 429 o LLM fica desligado até a cota voltar, sem gastar a chamada do modo contexto.

    Sem créditos, o OpenRouter dá 50 chamadas gratuitas por dia (zera à meia-noite UTC). Cada
    pergunta faz 2 ou 3 chamadas, então a cota acaba cedo e insistir só atrasa a leitura local.
    """

    MINUTE_COOLDOWN_S = 60.0

    def __init__(self) -> None:
        self._until = 0.0
        self._lock = threading.Lock()

    def open_for(self, exc: Exception) -> None:
        if "per-day" in str(exc):
            now = datetime.now(UTC)
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait = (midnight - now).total_seconds()
        else:
            wait = self.MINUTE_COOLDOWN_S
        with self._lock:
            self._until = max(self._until, time.monotonic() + wait)
        log.warning("Cota do LLM esgotada; regras locais pelos próximos %.0f s", wait)

    def is_open(self) -> bool:
        with self._lock:
            return time.monotonic() < self._until

    def reset(self) -> None:
        with self._lock:
            self._until = 0.0


quota_breaker = _QuotaBreaker()


def _reason(exc: Exception) -> FallbackReason:
    if isinstance(exc, openai.RateLimitError):
        if llm.is_account_quota(exc):
            quota_breaker.open_for(exc)
            return "quota"
        return "busy"
    if isinstance(exc, (llm.LLMDeadlineExceeded, openai.APITimeoutError)):
        return "timeout"
    return "error"


def _local(local_reading: local.Reading, reason: FallbackReason | None) -> ChatResponse:
    response = response_local(local_reading)
    return response.model_copy(update={"fallback_reason": reason}) if reason else response


def _acceptable(text: str | None) -> bool:
    return bool(text) and _ACTION in text


def context_reserve(budget_s: float) -> float:
    return min(CONTEXT_MIN_S, budget_s * _CONTEXT_SHARE)


def chat(req: ChatRequest, repo: Repository, settings: Settings, use_llm: bool = True) -> ChatResponse:
    """`use_llm=False` (cota esgotada ou engine=local) responde só com as regras locais."""
    f = req.filters
    local_reading = local.build_reading(req.question, repo, f, history=req.history)
    # engine=local não entra na cadeia: a leitura já está pronta e a cota fica intacta.
    if not (use_llm and req.engine != "local" and settings.llm_enabled and local_reading.n > 0):
        return response_local(local_reading)
    if quota_breaker.is_open():
        return _local(local_reading, "quota")

    graph = settings.investigation_enabled and investigate.should_investigate(req.question, req.history, repo, f)
    budget = settings.investigation_budget_s if graph else settings.chat_budget_s
    deadline = time.monotonic() + budget
    reserve = context_reserve(budget)
    tools_deadline = deadline - reserve
    reason: FallbackReason = "error"
    first = "investigação" if graph else "LLM com tools"
    try:
        if graph:
            result = investigate.investigate(req.question, req.history, repo, f, settings, deadline=tools_deadline)
        else:
            result = llm.answer_with_tools(req.question, req.history, repo, f, settings, deadline=tools_deadline)
        if result:
            result = (normalize_action(result[0]), result[1])
        if result and _acceptable(result[0]):
            text, used = result
            # A investigação sai como "llm-tools" (o schema da API não muda); o log separa os modos.
            log.info("agent_chat mode=%s", "investigate" if graph else "llm-tools")
            return response_llm(text, "llm-tools", settings.openrouter_model, used, local_reading, repo, f)
        if result:
            log.warning("%s respondeu sem **Ação:**; tentando contexto", first)
        elif time.monotonic() >= tools_deadline:
            reason = "timeout"
    except Exception as exc:  # noqa: BLE001 — falha do LLM cai no próximo modo, não derruba a resposta
        reason = _reason(exc)
        log.warning("%s falhou (%s): %s", first, reason, exc)

    # Cota esgotada ou provedor congestionado não tentam o contexto: a segunda chamada também volta 429.
    # None (texto vazio, rodadas esgotadas ou resposta sem ação) ainda tenta contexto se sobrou
    # pelo menos a reserva. Menos que isso, a chamada não fecha a tempo: vai a leitura local.
    if reason in ("quota", "busy"):
        return _local(local_reading, reason)
    if deadline - time.monotonic() < reserve:
        log.warning("Prazo restante abaixo da reserva (%.1f s); pulando o modo contexto", reserve)
        return _local(local_reading, "timeout")
    try:
        context = llm.answer_with_context(req.question, req.history, repo, f, settings, deadline=deadline)
        if context and context[0]:
            context = (normalize_action(context[0]), context[1])
        if context and _acceptable(context[0]):
            text, used = context
            return response_llm(text, "llm-context", settings.openrouter_model, used, local_reading, repo, f)
        if context and context[0]:
            log.warning("LLM com contexto respondeu sem **Ação:**; usando agente local")
    except Exception as exc:  # noqa: BLE001 — falha do LLM cai nas regras locais
        reason = _reason(exc)
        log.warning("LLM com contexto falhou (%s), usando agente local: %s", reason, exc)
    return _local(local_reading, reason)
