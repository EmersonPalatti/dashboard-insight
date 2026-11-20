"""Contratos de configuração de deploy e dependências de desenvolvimento."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.config import DEFAULT_MODEL

ROOT = Path(__file__).resolve().parents[2]


def test_render_yaml_model_matches_default_model():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    env_vars = blueprint["services"][0]["envVars"]
    by_key = {item["key"]: item for item in env_vars}
    assert by_key["OPENROUTER_MODEL"]["value"] == DEFAULT_MODEL


def test_env_example_model_matches_default_model():
    lines = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8").splitlines()
    model_line = next(line for line in lines if line.startswith("OPENROUTER_MODEL="))
    assert model_line.split("=", 1)[1].strip() == DEFAULT_MODEL


def test_requirements_dev_pins_exact_versions():
    lines = (ROOT / "backend" / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    reqs = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith(("#", "-r "))]
    assert reqs
    for req in reqs:
        assert "==" in req, f"Dependência sem versão exata em requirements-dev.txt: {req}"
