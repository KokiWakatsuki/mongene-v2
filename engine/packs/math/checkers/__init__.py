"""数学パックの double_solve checker 群（G-Q1 が呼ぶ・§4.1 統合配線）。

サブモジュールを import することで `@register_checker` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.checkers import arithmetic  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import equation  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import letter_expr  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import linear  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import polynomial  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import radical  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import quadratic  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import rational_form  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import motion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import quadratic_function  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import probability  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import proportion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import statistics_distribution  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import quartile  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import sample_survey  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import exam_fusion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import plane_geometry  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import plane_transform  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import angle_tracking  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import triangle_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import congruence_correspondence  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import quadrilateral_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import pythagorean  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import similarity  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import similarity_conditions  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import parallel_line_ratio  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.checkers import similarity_scale_ratio  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
