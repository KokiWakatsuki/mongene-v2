"""バックグラウンド非同期生成キャッシュ（§42）

ユーザーが画面で問題を解いている間、次の問題を裏で先読み生成しキューに溜める。
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

logger = logging.getLogger(__name__)


class PrefetchCache:
    def __init__(self, max_size: int = 10) -> None:
        self.max_size = max_size
        self._caches: Dict[str, Deque[Any]] = {}

    def _key(self, request: Any, lesson_mapping_key: str) -> str:
        # 同一 lesson + form + difficulty + unlearned で同じキー
        unlearned = tuple(getattr(request, "unlearned_lesson_ids", []) or [])
        return (
            f"{lesson_mapping_key}|"
            f"{getattr(request, 'problem_form', '')}|"
            f"{getattr(request, 'target_difficulty', 0)}|"
            f"{unlearned}"
        )

    def pop_for(self, request: Any, lesson_mapping_key: str) -> Optional[Any]:
        key = self._key(request, lesson_mapping_key)
        cache = self._caches.get(key)
        if cache:
            return cache.popleft()
        return None

    async def refill(
        self,
        request: Any,
        lesson_mapping_key: str,
        runner_run: Callable[[], Any],
        count: int = 1,
    ) -> None:
        key = self._key(request, lesson_mapping_key)
        cache = self._caches.setdefault(key, deque(maxlen=self.max_size))
        for _ in range(count):
            if len(cache) >= self.max_size:
                break
            try:
                problem = await asyncio.to_thread(runner_run)
                cache.append(problem)
            except Exception as e:
                logger.warning(f"Prefetch failed for {key}: {e}")
                break

    def size(self, request: Any, lesson_mapping_key: str) -> int:
        key = self._key(request, lesson_mapping_key)
        return len(self._caches.get(key, []))

    def clear(self) -> None:
        self._caches.clear()
