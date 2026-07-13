"""数学パックの recipe 群（構成的生成・answer-first。実装設計 §6.1）。

サブモジュールを import することで `@register_recipe` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.recipes import arithmetic  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import equation  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import linear  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import polynomial  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import letter_expr  # noqa: F401,E402  (polynomial のヘルパに依存＝後に import)
from engine.packs.math.recipes import radical  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import quadratic  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
