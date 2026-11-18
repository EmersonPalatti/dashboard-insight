"""Testes de concorrência, singleflight de cache e smoke test sobre o parquet real."""

from __future__ import annotations

import concurrent.futures
import threading
from pathlib import Path

import pytest

from app.alerts import detect_alerts
from app.config import Settings
from app.filters import Filters
from app.repository import Repository

REAL_PARQUET = Path(__file__).resolve().parents[1] / "data" / "orders.parquet"


def test_cached_singleflight_runs_compute_once(repo):
    calls = 0
    counter_lock = threading.Lock()
    barrier = threading.Barrier(16)

    def compute():
        nonlocal calls
        with counter_lock:
            calls += 1
        return {"ok": True}

    def worker():
        barrier.wait()
        return repo.cached("test:singleflight:ok", compute)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        results = [ft.result() for ft in [ex.submit(worker) for _ in range(16)]]

    assert calls == 1
    assert all(r == {"ok": True} for r in results)


def test_detect_alerts_concurrent_no_deadlock(repo):
    slices = [
        Filters(),
        Filters(city=["São Paulo"]),
        Filters(city=["Curitiba"]),
        Filters(segment=["food"]),
    ]

    def worker(i: int):
        f = slices[i % len(slices)]
        return len(detect_alerts(repo, f))

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        counts = [ft.result() for ft in [ex.submit(worker, i) for i in range(32)]]

    assert all(isinstance(c, int) for c in counts)


@pytest.mark.skipif(not REAL_PARQUET.exists(), reason="parquet real fora do checkout")
def test_real_parquet_concurrent_page_loads_and_invariants():
    s = Settings()
    real_repo = Repository(REAL_PARQUET, s.sla_food_min, s.sla_good_min)
    try:
        page_calls = [
            lambda r, f: r.meta(),
            lambda r, f: detect_alerts(r, f),
            lambda r, f: r.metrics(f),
            lambda r, f: r.timeseries(f, "day"),
            lambda r, f: r.breakdown(f, "hub", limit=50),
            lambda r, f: r.heatmap(f),
            lambda r, f: r.breakdown(f, "store", sort="orders", limit=1000, min_orders=30),
            lambda r, f: r.orders_page(f, 0, 200, "created_at", True),
        ]
        tasks = []
        for u in range(3):
            city = [[], ["São Paulo"], ["Curitiba"]][u]
            f = Filters(city=city)
            for fn in page_calls:
                tasks.append((fn, real_repo, f))

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
            results = [ft.result() for ft in [ex.submit(fn, r, f) for fn, r, f in tasks]]
        assert len(results) == 24

        # Lojas homônimas no mesmo shopping ficam desambiguadas pelo id.
        rap_stores = [
            st["label"] for st in real_repo.meta()["stores"]
            if st["parent"] == 28 and st["label"].startswith("Salito")
        ]
        assert len(rap_stores) == 2
        assert all("#" in name for name in rap_stores)
        assert len(set(rap_stores)) == 2

        # Identidade exata cost_avg - fee_avg == subsidy em todos os hubs.
        for hub in real_repo.breakdown(Filters(), "hub", limit=100):
            if hub["cost_avg"] is not None and hub["fee_avg"] is not None:
                assert hub["cost_avg"] - hub["fee_avg"] == pytest.approx(hub["subsidy"], abs=1e-9)
    finally:
        real_repo._con.close()
