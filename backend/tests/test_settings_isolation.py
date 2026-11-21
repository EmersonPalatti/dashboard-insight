"""Settings() nos testes não lê o .env do desenvolvedor nem variáveis do shell (conftest.pytest_configure).

O isolamento precisa valer antes da coleta: `app.main` e `app.agent.llm` chamam `get_settings()` na
importação. Por isso os subprocessos rodam, junto, testes que importam `app.main` no topo do módulo.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.config import Settings, get_settings

BACKEND = Path(__file__).resolve().parents[1]
LEAK = "leak-check-token"
LEAKED_ORIGIN = "https://leaked.example"
# Valores ruins de propósito: SLA diferente do código e limites fora da faixa (ValidationError).
BAD_SETTINGS = {
    "AUTOMATION_TOKEN": LEAK,
    "OPENROUTER_API_KEY": "sk-leak",
    "OPENROUTER_FALLBACK_MODELS": "x/leak",
    "SLA_FOOD_MIN": "45",
    "SLA_GOOD_MIN": "90",
    "INVESTIGATION_MAX_PROBES": "10",
    "CHAT_BUDGET_S": "0",
    "CORS_ORIGINS": LEAKED_ORIGIN,
}
NODES = [
    "tests/test_settings_isolation.py::test_settings_start_from_the_defaults",
    "tests/test_api.py::test_health",
    "tests/test_semantic.py::test_business_numbers_follow_the_code",
    "tests/test_agent_llm.py::test_system_prompt_carries_the_semantic_layer_and_the_contract",
]


def test_settings_start_from_the_defaults():
    # Roda também dentro dos subprocessos abaixo, com BAD_SETTINGS no shell ou num .env.
    assert Settings.model_config.get("env_file") is None
    settings = Settings()
    assert settings.automation_token is None
    assert settings.openrouter_api_key is None
    assert settings.fallback_models == []
    assert (settings.sla_food_min, settings.sla_good_min) == (60, 120)
    assert settings.investigation_max_probes == 0
    assert get_settings().automation_token is None

    from app.agent import llm
    from app.main import app

    assert "60 min" in llm.SYSTEM_PROMPT and "45 min" not in llm.SYSTEM_PROMPT
    assert LEAKED_ORIGIN not in repr([m.kwargs for m in app.user_middleware])


def _run(cmd: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k.upper() not in {n.upper() for n in Settings.model_fields}}


def test_shell_variables_do_not_leak_into_the_suite():
    env = {**_clean_env(), **BAD_SETTINGS}
    result = _run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *NODES], BACKEND, env)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "4 passed" in result.stdout


def test_dotenv_file_does_not_leak_into_the_suite(tmp_path: Path):
    # O .env fica ao lado do cwd do subprocesso; o bootstrap aponta Settings para ele (caminho relativo)
    # e confere que, sem o isolamento, ele seria lido. Depois a suíte roda com o conftest normal.
    (tmp_path / ".env").write_text("".join(f"{k}={v}\n" for k, v in BAD_SETTINGS.items()), encoding="utf-8")
    bootstrap = f"""
import sys
sys.path.insert(0, {str(BACKEND)!r})
from pydantic import ValidationError
from app.config import Settings
Settings.model_config["env_file"] = ".env"
try:
    Settings()
except ValidationError:
    pass
else:
    sys.exit("o .env do teste não foi lido: a prova não vale")
import pytest
nodes = [{str(BACKEND)!r} + "/" + n for n in {NODES!r}]
sys.exit(pytest.main(["-q", "-p", "no:cacheprovider", "--rootdir", {str(BACKEND)!r}, *nodes]))
"""
    result = _run([sys.executable, "-c", bootstrap], tmp_path, _clean_env())
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "4 passed" in result.stdout
