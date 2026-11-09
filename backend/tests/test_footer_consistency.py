"""O rodapé do painel é HTML estático (casca Astro) e repete as regras de limpeza.

Se o SLA padrão mudar em `Settings`, o texto do rodapé precisa mudar junto
(AGENTS.md, regra 7). Este teste falha antes de o painel publicar números velhos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings

INDEX = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "index.astro"


@pytest.mark.skipif(not INDEX.exists(), reason="frontend fora do checkout")
def test_footer_sla_matches_settings_defaults():
    footer = INDEX.read_text(encoding="utf-8")
    food = Settings.model_fields["sla_food_min"].default
    good = Settings.model_fields["sla_good_min"].default
    assert f"food ≤ {food} min" in footer
    assert f"goods ≤ {good} min" in footer
