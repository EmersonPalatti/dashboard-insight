"""Settings() nos testes não lê o .env do desenvolvedor nem variáveis do shell (conftest._isolate_settings_env)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.config import Settings, get_settings

BACKEND = Path(__file__).resolve().parents[1]
LEAK = "leak-check-token"


def test_settings_start_from_the_defaults():
    # Roda também dentro do subprocesso abaixo, com AUTOMATION_TOKEN e OPENROUTER_* no ambiente.
    assert Settings.model_config.get("env_file") is None
    settings = Settings()
    assert settings.automation_token is None
    assert settings.openrouter_api_key is None
    assert settings.fallback_models == []
    assert get_settings().automation_token is None


def test_shell_automation_token_does_not_leak_into_the_suite():
    env = {
        **os.environ,
        "AUTOMATION_TOKEN": LEAK,
        "OPENROUTER_API_KEY": "sk-leak",
        "OPENROUTER_FALLBACK_MODELS": "x/leak",
    }
    node = f"{Path(__file__).name}::test_settings_start_from_the_defaults"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"tests/{node}"],
        check=False,
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
