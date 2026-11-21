"""Testes do contrato de recorte (`Filters`), incluindo city sem diferenciar caixa."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.filters import Filters


def test_city_where_uses_parameterized_lower():
    sql, params = Filters(city=["SÃO PAULO", "curitiba"]).where()
    assert "list_contains(?, lower(city))" in sql
    assert params == [["são paulo", "curitiba"]]


def test_city_cache_key_is_case_insensitive_and_deduplicated():
    assert Filters(city=["curitiba"]).cache_key() == Filters(city=["Curitiba"]).cache_key()
    assert Filters(city=["SÃO PAULO"]).cache_key() == Filters(city=["São Paulo"]).cache_key()
    assert (
        Filters(city=["curitiba", "CURITIBA", "são paulo"]).cache_key()
        == Filters(city=["São Paulo", "Curitiba"]).cache_key()
    )


def test_city_filter_matches_repo_case_insensitively(repo):
    curitiba = repo.metrics(Filters(city=["Curitiba"]))["orders"]
    sao_paulo = repo.metrics(Filters(city=["São Paulo"]))["orders"]
    assert curitiba > 0
    assert sao_paulo > 0

    for variant in ("curitiba", "CURITIBA", "Curitiba"):
        assert repo.metrics(Filters(city=[variant]))["orders"] == curitiba

    for variant in ("são paulo", "SÃO PAULO", "São Paulo"):
        assert repo.metrics(Filters(city=[variant]))["orders"] == sao_paulo

    assert repo.metrics(Filters(city=["curitiba", "SÃO PAULO"]))["orders"] == curitiba + sao_paulo


def test_city_filter_http_api_case_insensitive(client):
    canonical_cwb = client.get("/api/kpis", params={"city": "Curitiba"})
    lower_cwb = client.get("/api/kpis", params={"city": "curitiba"})
    assert canonical_cwb.status_code == 200
    assert lower_cwb.status_code == 200
    assert lower_cwb.json()["current"]["orders"] == canonical_cwb.json()["current"]["orders"] > 0

    canonical_sp = client.get("/api/kpis", params={"city": "São Paulo"})
    upper_sp = client.get("/api/kpis", params={"city": "SÃO PAULO"})
    assert canonical_sp.status_code == 200
    assert upper_sp.status_code == 200
    assert upper_sp.json()["current"]["orders"] == canonical_sp.json()["current"]["orders"] > 0


def test_date_range_and_helpers():
    with pytest.raises(ValidationError):
        Filters(start=date(2021, 3, 10), end=date(2021, 3, 9))

    base = Filters(city=["Curitiba"])
    assert not base.is_full_network()
    assert Filters(start=date(2021, 1, 1), end=date(2021, 1, 31)).is_full_network()

    moved = base.with_period(date(2021, 2, 1), date(2021, 2, 28))
    assert moved.start == date(2021, 2, 1)
    assert moved.end == date(2021, 2, 28)
    assert moved.city == ["Curitiba"]
