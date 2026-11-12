"""O rodapé do painel e o README repetem as decisões de limpeza (AGENTS.md, regra 7).

Os limiares saem do mesmo lugar que o ETL usa. Se o número mudar só num dos lados,
este teste falha antes de o painel publicar a regra velha.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from scripts.build_parquet import AMOUNT_OUTLIER, SQL, STUCK_CYCLE_MIN, TZ_OFFSET_HOURS

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "frontend" / "src" / "pages" / "index.astro"
README = ROOT / "README.md"


@pytest.mark.skipif(not INDEX.exists() or not README.exists(), reason="frontend ou README fora do checkout")
def test_footer_and_readme_match_cleaning_rules():
    footer = INDEX.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    food = Settings.model_fields["sla_food_min"].default
    good = Settings.model_fields["sla_good_min"].default
    hours = STUCK_CYCLE_MIN // 60
    mil = AMOUNT_OUTLIER // 1000

    assert STUCK_CYCLE_MIN % 60 == 0
    assert AMOUNT_OUTLIER % 1000 == 0
    assert f"interval {TZ_OFFSET_HOURS} hour" in SQL
    assert f"cycle_min > {STUCK_CYCLE_MIN}" in SQL
    assert f"amount > {AMOUNT_OUTLIER}" in SQL

    for text in (footer, readme):
        assert "UTC" in text and "Brasília" in text
        assert f"food ≤ {food} min" in text
        assert f"goods ≤ {good} min" in text
        assert f"R$ {mil} mil" in text

    # O HTML do rodapé escapa o ">".
    assert f"ciclo &gt; {hours}h" in footer
    assert f"ciclo > {hours}h" in readme
