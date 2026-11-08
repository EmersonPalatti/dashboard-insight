"""Exporta o schema OpenAPI para o frontend gerar os tipos TypeScript.

    python scripts/export_openapi.py && (cd ../frontend && npm run gen:api)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"

if __name__ == "__main__":
    OUT.write_text(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI salvo em {OUT}")
