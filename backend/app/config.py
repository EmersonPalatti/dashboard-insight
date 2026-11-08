"""Configuração via variáveis de ambiente (ou backend/.env em dev)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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
    llm_timeout_s: float = 45.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
