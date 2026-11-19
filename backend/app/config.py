"""Configuração via variáveis de ambiente (ou backend/.env em dev)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
# Escolhido no confronto de 19/11/2026 (12 perguntas do placar, mesmas regras): ERNIE respondeu 6 de 7
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
    # Vazio de propósito: nenhum gratuito medido ficou no nível do ERNIE (Super VL acertou 3 de 8),
    # e um fallback pior que as regras locais trocaria uma leitura boa por uma pior. Ligue só com placar.
    openrouter_fallback_models: str = ""
    # Modelos gratuitos com raciocínio contam o raciocínio dentro de `max_tokens` (700 cortava 3/4
    # das respostas do Nemotron; 1400 ainda cortava 2 de 26 rodadas do ERNIE). A leitura local já
    # aparece na tela em ~0,15 s enquanto o LLM roda; 2000 tokens e 20 s de orçamento evitam corte e
    # cobrem 2–3 rodadas. O teto só custa tempo quando o modelo de fato usa os tokens.
    llm_timeout_s: float = 18.0
    llm_max_tokens: int = 2000
    llm_reasoning_effort: str | None = "low"
    chat_budget_s: float = 20.0
    chat_rate_limit_per_minute: int = 8
    # Teto de chamadas ao LLM por minuto, somando todos os IPs. 0 desliga.
    chat_global_rate_limit_per_minute: int = 60
    chat_rate_limit_enabled: bool = True
    # Header de IP confiável (ex.: true-client-ip ou cf-connecting-ip).
    # Vazio: último hop de X-Forwarded-For, que é o IP acrescentado pelo proxy.
    # A documentação do Render não garante True-Client-IP; a Cloudflare, quando está na frente, envia os dois.
    client_ip_header: str = ""

    # Exportação CSV: acima do teto a API pede um recorte menor. 0 desliga a cota por IP.
    csv_export_max_rows: int = 50_000
    csv_export_per_minute: int = 30

    # Se preenchido, /api/briefing e /api/alerts/routing exigem o header X-Automation-Token.
    automation_token: str | None = None

    @field_validator("cors_origin_regex", mode="before")
    @classmethod
    def _empty_regex_is_none(cls, v: str | None) -> str | None:
        if isinstance(v, str) and not v.strip():
            return None
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
