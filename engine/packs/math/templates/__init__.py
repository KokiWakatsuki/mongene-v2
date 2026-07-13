"""数学パックの T1 テンプレート群（実装設計 §7）。

サブモジュールを import することで `register_template` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.templates import arithmetic  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import equation  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import letter_expr  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import linear  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import polynomial  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import radical  # noqa: F401  (register_template の副作用のため import)
from engine.packs.math.templates import quadratic  # noqa: F401  (register_template の副作用のため import)

__all__: list[str] = []
