"""Guarda de contrato OpenAPI: `frontend/openapi.json` precisa bater com `create_app().openapi()`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.main import create_app
from app.repository import ORDER_SORTS

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "frontend" / "openapi.json"


@pytest.mark.skipif(not OPENAPI.exists(), reason="frontend/openapi.json fora do checkout")
def test_openapi_schema_matches_committed_json():
    committed_text = OPENAPI.read_text(encoding="utf-8")
    committed = json.loads(committed_text)
    live = create_app().openapi()
    live_text = json.dumps(live, ensure_ascii=False, indent=2) + "\n"
    msg = (
        "OpenAPI divergiu de frontend/openapi.json. "
        "Rode: cd backend && python scripts/export_openapi.py && (cd ../frontend && npm run gen:api)"
    )
    assert live == committed, msg
    assert live_text == committed_text, msg


def test_openapi_documents_naive_brasilia_datetimes_and_contract_fields():
    spec = create_app().openapi()
    schemas = spec["components"]["schemas"]

    time_desc = schemas["TimePoint"]["properties"]["t"]["description"]
    order_desc = schemas["OrderRow"]["properties"]["created_at"]["description"]
    assert "Brasília" in time_desc and "sem offset" in time_desc
    assert "Brasília" in order_desc and "sem offset" in order_desc

    orders_params = {p["name"]: p for p in spec["paths"]["/api/orders"]["get"]["parameters"]}
    assert set(orders_params["sort"]["schema"]["enum"]) == ORDER_SORTS

    assert {"measured", "low_sample", "volume_low_sample"} <= set(schemas["TimePoint"]["required"])
    assert {"measured", "low_sample", "volume_low_sample"} <= set(schemas["HeatCell"]["required"])
    assert {"hub_id", "store_id", "amount_outlier"} <= set(schemas["OrderRow"]["required"])
    assert "heatmap_min_sample" in schemas["Meta"]["required"]
    assert "empty_reason" in schemas["AlertsResponse"]["properties"]
