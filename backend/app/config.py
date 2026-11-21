"""Configuração via variáveis de ambiente (ou backend/.env em dev)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Escolhido no confronto de 19/11/2026: recorte de 12 perguntas da suíte de 45 casos de evals/,
# mesmas regras, rodado localmente (as saídas do placar não ficam versionadas). Denominador menor que
# 12 conta só as perguntas que chegaram ao modelo; as outras caíram nas regras locais pela cota do
# plano gratuito ou por 429 do provedor. ERNIE respondeu 6 de 7
# pelo LLM com p50 de 9 s; Nemotron 3 Ultra estourou o prazo em 8 de 12, Nemotron 3.5 Super VL acertou
# 3 de 8, Nemotron 3.5 Lightning estourou 6 de 12 e Gemma 4 31B ficou 12 de 12 com o provedor
# congestionado (429). "preview" pode sair do ar: troque por OPENROUTER_MODEL sem mexer em código.
DEFAULT_MODEL = "baidu/ernie-5.5-flash-preview:free"


class Settings(BaseSettings):
    # .env da raiz do repo e depois o de backend/ (o último vence). Em produção: variáveis do Render.
    model_config = SettingsConfigDict(env_file=(BACKEND_ROOT.parent / ".env", BACKEND_ROOT / ".env"), extra="ignore")

    data_path: Path = BACKEND_ROOT / "data" / "orders.parquet"

    # Separados por vírgula. O regex cobre previews da Vercel, por exemplo.
    cors_origins: str = "http://localhost:4321,http://127.0.0.1:4321"
    cors_origin_regex: str | None = None

    # SLA de ciclo (criação → finalização) por segmento, em minutos.
    sla_food_min: int = 60
    sla_good_min: int = 120

    openrouter_api_key: str | None = None
    openrouter_model: str = DEFAULT_MODEL
    # Modelos de reserva, separados por vírgula, que o OpenRouter tenta se o principal falhar.
    # Vazio de propósito: nenhum gratuito medido ficou no nível do ERNIE (Super VL acertou 3 de 8
    # perguntas que chegaram a pontuar no confronto acima),
    # e um fallback pior que as regras locais trocaria uma leitura boa por uma pior. Ligue só com placar.
    openrouter_fallback_models: str = ""
    # Modelos gratuitos com raciocínio contam o raciocínio dentro de `max_tokens` (700 cortava 3/4
    # das respostas do Nemotron; 1400 ainda cortava 2 de 26 rodadas do ERNIE). A leitura local já
    # aparece na tela em ~0,15 s enquanto o LLM roda; 2000 tokens e 20 s de orçamento evitam corte e
    # cobrem 2–3 rodadas. O teto só custa tempo quando o modelo de fato usa os tokens.
    llm_timeout_s: float = Field(default=18.0, gt=0, le=120)
    llm_max_tokens: int = Field(default=2000, ge=100, le=16000)
    llm_reasoning_effort: str | None = "low"
    chat_budget_s: float = Field(default=20.0, gt=0, le=120)
    # Pergunta "por que mudou" com período anterior passa pelo grafo de investigação (investigate.py):
    # decomposição e drill determinísticos e uma chamada de síntese. No placar de 19/11/2026 (outro
    # recorte, de 8 perguntas da mesma suíte de evals/, rodado em cada configuração; saídas locais)
    # respondeu pelo LLM tanto quanto o loop de tools (5 de 8), com 1,4 chamada por pergunta contra 3,4
    # e p50 de 8,6 s contra 11,5 s.
    investigation_enabled: bool = True
    # Consultas extras que uma revisão curta do LLM (JSON) pode pedir antes da síntese. 0 pula a revisão.
    # Zero de propósito: o ERNIE não desliga nem limita o raciocínio, e a revisão estourou o teto de
    # tokens sem JSON em 9 de 9 tentativas (400 e 1200 tokens), gastando 3–7 s. Ligue com um modelo que
    # devolva o JSON, medindo no placar. Teto 5: cada consulta custa 2 passos do grafo e o LangGraph
    # para em 25 passos.
    investigation_max_probes: int = Field(default=0, ge=0, le=5)
    # Teto da síntese do grafo, separado do loop de tools: é a única chamada da investigação e o
    # raciocínio do ERNIE vai junto. Abril e fevereiro fecham com ~2.100–2.400 tokens (10–13 s), mas
    # março pede ~6.000 (~27 s, a ~220 tokens/s): com 3000 a síntese voltava vazia (finish=length)
    # e a pergunta caía nas regras em produção.
    investigation_synth_max_tokens: int = Field(default=7000, ge=100, le=32000)
    # Prazo próprio da pergunta que vai ao grafo (o resto do agente fica em chat_budget_s). A espera
    # maior não trava o operador: a leitura por regras já está na tela e é substituída quando a
    # síntese chega. A síntese usa este prazo, não o teto por chamada (llm_timeout_s).
    investigation_budget_s: float = Field(default=35.0, gt=0, le=120)
    # Teto de perguntas com LLM em voo ao mesmo tempo (cada uma segura uma thread do servidor).
    llm_max_concurrent: int = Field(default=8, ge=1, le=64)
    chat_rate_limit_per_minute: int = 8
    # Teto de chamadas ao LLM por minuto, somando todos os IPs. 0 desliga.
    chat_global_rate_limit_per_minute: int = 60
    chat_rate_limit_enabled: bool = True
    # Header de IP confiável, só quando o proxy na frente sobrescreve o header. Vazio mantém o último
    # hop de X-Forwarded-For (seguro para dev/outros hosts). O render.yaml define cf-connecting-ip
    # porque a borda do Render roda atrás da Cloudflare. "x-forwarded-for" aqui é ignorado.
    client_ip_header: str = ""

    # Exportação CSV: acima do teto a API pede um recorte menor. 0 desliga a cota por IP.
    csv_export_max_rows: int = 50_000
    csv_export_per_minute: int = 30

    # Se preenchido, /api/briefing e /api/alerts/routing exigem o header X-Automation-Token.
    # Só espaços conta como vazio; espaços nas pontas são removidos.
    automation_token: str | None = None

    @field_validator("cors_origin_regex", "automation_token", mode="before")
    @classmethod
    def _empty_str_is_none(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def fallback_models(self) -> list[str]:
        primary = self.openrouter_model.strip()
        names = (m.strip() for m in self.openrouter_fallback_models.split(","))
        return list(dict.fromkeys(m for m in names if m and m != primary))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
