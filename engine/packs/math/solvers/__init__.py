"""数学パックの独立再計算ソルバ群（実装設計 §6.2）。

サブモジュールを import することで `@register_solver` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.solvers import arithmetic  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import equation  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import letter_expr  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import linear  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import polynomial  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import radical  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import quadratic  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
