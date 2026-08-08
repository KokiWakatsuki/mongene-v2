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
from engine.packs.math.solvers import rational_form  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import motion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import quadratic_function  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import probability  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import proportion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import proportion_graph  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import statistics_distribution  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import distribution_chart  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import quartile  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import sample_survey  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import plane_geometry  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import solid_view  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import statistics_inquiry  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import plane_transform  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import angle_tracking  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import triangle_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import congruence_correspondence  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import quadrilateral_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import pythagorean  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import similarity  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import similarity_conditions  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import parallel_line_ratio  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import similarity_scale_ratio  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import inscribed_angle  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import solid_figure  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.solvers import g1_space  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
