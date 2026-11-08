"""Agente LLM via OpenRouter (API compatível com OpenAI) com tool calling.

As ferramentas consultam o DuckDB com o recorte do operador já aplicado no
servidor: o modelo escolhe *o que* consultar, nunca *sobre quais dados*.
Se o modelo não suportar tools, cai para um prompt único com contexto; se a
chamada falhar, o chamador usa o agente local.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, get_args

from app.alerts import detect_alerts
from app.config import Settings
from app.filters import Filters
from app.repository import Repository
from app.schemas import ChatTurn, Dimension, Grain, SortKey

log = logging.getLogger(__name__)
SYSTEM_PROMPT = (Path(__file__).with_name("prompts.md")).read_text(encoding="utf-8")
MAX_ROUNDS = 5

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_kpis",
            "description": "KPIs do recorte atual e do período anterior de mesmo tamanho (quando existe).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_breakdown",
            "description": (
                "Quebra o recorte por uma dimensão e devolve, por grupo: pedidos, GMV, ticket, cancelamento, "
                "SLA, ciclo e medianas de cada etapa. hour = hora local (0–23) e weekday (0 = segunda) "
                "sempre voltam completos e em ordem, ignorando sort/limit."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "by": {"type": "string", "enum": list(get_args(Dimension))},
                    "sort": {"type": "string", "enum": list(get_args(SortKey)), "default": "orders"},
                    "ascending": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 15, "default": 8},
                    "min_orders": {"type": "integer", "minimum": 0, "default": 0,
                                   "description": "Use 150+ para lojas e 300+ para hubs ao comparar taxas."},
                },
                "required": ["by"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_alerts",
            "description": "Alertas automáticos do recorte com detalhe numérico e ação sugerida.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeseries",
            "description": "Série temporal do recorte (pedidos, GMV, cancelamento, ciclo, SLA).",
            "parameters": {
                "type": "object",
                "properties": {"grain": {"type": "string", "enum": ["day", "week"], "default": "week"}},
            },
        },
    },
]

_KEEP = {
    "key", "label", "parent", "orders", "delivered", "canceled", "gmv", "ticket", "cancel_rate", "cycle_p50",
    "cycle_p90", "sla_rate", "stuck_rate", "production_p50", "collected_p50", "expedition_p50", "transit_p50",
    "distance_p50_km", "fee_avg", "cost_avg", "subsidy",
}


def _compact(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k not in _KEEP and k != "t":
            continue
        if isinstance(v, float):
            v = round(v, 4 if abs(v) < 1 else 1)
        elif k == "t":
            v = str(v)[:10]
        out[k] = v
    return out


class ToolRunner:
    def __init__(self, repo: Repository, f: Filters):
        self.repo, self.f, self.used = repo, f, []

    def run(self, name: str, args: dict) -> Any:
        self.used.append(name if name != "get_breakdown" else f"get_breakdown({args.get('by')})")
        if name == "get_kpis":
            prev = self.repo.previous_period(self.f)
            return {
                "recorte": self.repo.describe(self.f),
                "atual": _compact(self.repo.metrics(self.f)),
                "periodo_anterior": _compact(self.repo.metrics(self.f.with_period(*prev))) if prev else None,
            }
        if name == "get_breakdown":
            by = args.get("by")
            if by not in get_args(Dimension):
                return {"erro": f"dimensão inválida: {by}"}
            if by in ("hour", "weekday"):
                # Série completa e em ordem: cortar horas leva o modelo a "achar" que o pico não existe.
                rows = self.repo.breakdown(self.f, by, sort="orders", limit=24)
                return [_compact(r) for r in sorted(rows, key=lambda r: int(r["key"]))]
            sort = args.get("sort", "orders")
            sort = sort if sort in get_args(SortKey) else "orders"
            limit = max(1, min(int(args.get("limit", 8)), 15))
            rows = self.repo.breakdown(self.f, by, sort=sort, desc=not args.get("ascending", False),
                                       limit=limit, min_orders=max(0, int(args.get("min_orders", 0))))
            return [_compact(r) for r in rows]
        if name == "get_alerts":
            return [a.model_dump(exclude={"drilldown", "id"}) for a in detect_alerts(self.repo, self.f)]
        if name == "get_timeseries":
            grain: Grain = "day" if args.get("grain") == "day" else "week"
            return [_compact(p) for p in self.repo.timeseries(self.f, grain)][-60:]
        return {"erro": f"ferramenta desconhecida: {name}"}


def _client(settings: Settings):
    from openai import OpenAI

    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=settings.llm_timeout_s,
        max_retries=1,
        default_headers={"X-Title": "Central de Operacoes Delivery"},
    )


def _messages(question: str, history: list[ChatTurn], scope: str) -> list[dict]:
    msgs: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + f"\n\nRecorte atual: {scope}"}]
    msgs += [{"role": t.role, "content": t.content} for t in history[-8:]]
    msgs.append({"role": "user", "content": question})
    return msgs


def answer_with_tools(
    question: str, history: list[ChatTurn], repo: Repository, f: Filters, settings: Settings
) -> tuple[str, list[str]] | None:
    client = _client(settings)
    runner = ToolRunner(repo, f)
    messages = _messages(question, history, repo.describe(f))
    for _ in range(MAX_ROUNDS):
        response = client.chat.completions.create(
            model=settings.openrouter_model, temperature=0.2, messages=messages, tools=TOOLS,
        )
        msg = response.choices[0].message
        calls = msg.tool_calls or []
        if not calls:
            text = (msg.content or "").strip()
            return (text, runner.used) if text else None
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls
            ],
        })
        for call in calls:
            try:
                args = json.loads(call.function.arguments or "{}")
                result = runner.run(call.function.name, args if isinstance(args, dict) else {})
            except Exception as exc:  # erro de ferramenta volta para o modelo, não derruba a resposta
                log.warning("tool %s falhou: %s", call.function.name, exc)
                result = {"erro": "falha ao consultar"}
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })
    return None


def answer_with_context(
    question: str, history: list[ChatTurn], repo: Repository, f: Filters, settings: Settings
) -> str | None:
    runner = ToolRunner(repo, f)
    context = {
        "kpis": runner.run("get_kpis", {}),
        "alertas": runner.run("get_alerts", {}),
        "hubs": runner.run("get_breakdown", {"by": "hub", "limit": 10}),
        "lojas_cancelamento": runner.run("get_breakdown", {"by": "store", "sort": "cancel_rate", "min_orders": 150}),
        "horas": runner.run("get_breakdown", {"by": "hour", "limit": 24}),
    }
    messages = _messages(question, history, repo.describe(f))
    messages[-1]["content"] = (
        "Contexto do recorte (agregados, não o dataset bruto):\n"
        + json.dumps(context, ensure_ascii=False, default=str)
        + f"\n\nPergunta do operador: {question}"
    )
    response = _client(settings).chat.completions.create(
        model=settings.openrouter_model, temperature=0.2, messages=messages,
    )
    text = (response.choices[0].message.content or "").strip()
    return text or None
