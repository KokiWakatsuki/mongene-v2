"""数学パック（engine.packs.math）。

frame / solver / recipe / template 等の登録は import 時の副作用で行われる
（registry パターン）。このモジュールを import すると、数学パックの
frame・solver・recipe・template・checker が登録される。
"""
from __future__ import annotations

from engine.packs.math import frames  # noqa: F401  (register_frame の副作用のため import)
from engine.packs.math import solvers  # noqa: F401  (register_solver の副作用のため import)
from engine.packs.math import recipes  # noqa: F401  (register_recipe の副作用のため import)
from engine.packs.math import templates  # noqa: F401  (register_template の副作用のため import)
from engine.packs.math import checkers  # noqa: F401  (register_checker の副作用のため import)

__all__: list[str] = []
