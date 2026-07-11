"""数学パックの double_solve checker 群（G-Q1 が呼ぶ・§4.1 統合配線）。

サブモジュールを import することで `@register_checker` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.checkers import linear  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
