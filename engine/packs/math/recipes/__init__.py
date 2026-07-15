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
from engine.packs.math.recipes import rational_form  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import motion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import quadratic_function  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import probability  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import proportion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import statistics_distribution  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import quartile  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import sample_survey  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.recipes import exam_fusion  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
