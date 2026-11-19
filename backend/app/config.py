"""Configuração via variáveis de ambiente (ou backend/.env em dev)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"


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
    # Modelo gratuito, resposta rápida: cada chamada ao LLM tem até 10 s e a conversa inteira 12 s
    # (tools + contexto). Estourou, o operador fica com a leitura local, que já está na tela.
    # 700 tokens cabem a resposta (até 120 palavras), a linha **Ação:** e o bloco ```leitura```.
    llm_timeout_s: float = 10.0
    llm_max_tokens: int = 700
    llm_reasoning_effort: str | None = "low"
    chat_budget_s: float = 12.0
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
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
