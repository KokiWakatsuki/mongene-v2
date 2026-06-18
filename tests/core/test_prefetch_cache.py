"""§42 PrefetchCache の単体テスト"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from apps.api.src.core.cache.prefetch import PrefetchCache


def _make_request(lesson_id: str = "g1_l5", form: str = "calculation", diff: int = 13) -> MagicMock:
    req = MagicMock()
    req.curriculum.lesson_ids = [lesson_id]
    req.problem_form = form
    req.target_difficulty = diff
    req.unlearned_lesson_ids = []
    return req


def test_pop_returns_none_when_empty() -> None:
    cache = PrefetchCache(max_size=5)
    req = _make_request()
    assert cache.pop_for(req, "g1_l5") is None


def test_pop_returns_item_after_refill() -> None:
    cache = PrefetchCache(max_size=5)
    req = _make_request()
    fake_problem = object()

    async def _refill() -> None:
        await cache.refill(req, "g1_l5", runner_run=lambda: fake_problem, count=1)

    asyncio.run(_refill())
    result = cache.pop_for(req, "g1_l5")
    assert result is fake_problem


def test_pop_depletes_cache() -> None:
    cache = PrefetchCache(max_size=5)
    req = _make_request()

    async def _refill() -> None:
        await cache.refill(req, "g1_l5", runner_run=lambda: "p", count=3)

    asyncio.run(_refill())
    assert cache.size(req, "g1_l5") == 3
    cache.pop_for(req, "g1_l5")
    assert cache.size(req, "g1_l5") == 2


def test_max_size_is_respected() -> None:
    cache = PrefetchCache(max_size=2)
    req = _make_request()

    async def _refill() -> None:
        await cache.refill(req, "g1_l5", runner_run=lambda: "p", count=10)

    asyncio.run(_refill())
    assert cache.size(req, "g1_l5") == 2  # max_size で止まる


def test_different_requests_have_separate_caches() -> None:
    cache = PrefetchCache(max_size=5)
    req_a = _make_request("g1_l5", diff=13)
    req_b = _make_request("g1_l5", diff=15)  # diff が違う → 別キー

    async def _refill() -> None:
        await cache.refill(req_a, "g1_l5", runner_run=lambda: "a", count=1)

    asyncio.run(_refill())
    assert cache.pop_for(req_a, "g1_l5") == "a"
    assert cache.pop_for(req_b, "g1_l5") is None


def test_refill_ignores_runner_exception() -> None:
    cache = PrefetchCache(max_size=5)
    req = _make_request()

    def _failing_runner():
        raise RuntimeError("runner failed")

    async def _refill() -> None:
        await cache.refill(req, "g1_l5", runner_run=_failing_runner, count=3)

    asyncio.run(_refill())
    # 例外発生時はキャッシュに何も溜まらないが、例外は伝播しない
    assert cache.size(req, "g1_l5") == 0


def test_clear_empties_all_caches() -> None:
    cache = PrefetchCache(max_size=5)
    req = _make_request()

    async def _refill() -> None:
        await cache.refill(req, "g1_l5", runner_run=lambda: "p", count=2)

    asyncio.run(_refill())
    assert cache.size(req, "g1_l5") == 2
    cache.clear()
    assert cache.size(req, "g1_l5") == 0
