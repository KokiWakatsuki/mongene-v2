# **文末は常体で統一する。** 実物を27出典・6系統測った結果、私たちが手本にする
# 「練習させる」系統（教科書会社・無料プリント・塾）は常体が 81〜100%だった
# （records/docs/typography_spec_2026-08-14.md）。敬体は試験・調査の体裁。
# 1つの教材の中で混ぜない——実物はどの系統も冊子内で統一している。

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
from engine.packs.math.templates import rational_form  # noqa: F401  (register_template の副作用のため import)
from engine.packs.math.templates import motion  # noqa: F401  (register_template の副作用のため import)
from engine.packs.math.templates import quadratic_function  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import probability  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import proportion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import statistics_distribution  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import distribution_chart  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import quartile  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import box_plot  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import sample_survey  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import exam_fusion  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import plane_geometry  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import plane_transform  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import angle_tracking  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import triangle_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import congruence_correspondence  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import quadrilateral_properties  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import pythagorean  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import similarity  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import similarity_conditions  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import parallel_line_ratio  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import similarity_scale_ratio  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import inscribed_angle  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import word_problem  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import solid_figure  # noqa: F401  (登録の副作用のため import)

from engine.packs.math.templates import proportion_graph  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import g1_space  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import number_proof  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import construction  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import conditional_proof  # noqa: F401  (登録の副作用のため import)
from engine.packs.math.templates import pythagoras_proof  # noqa: F401  (登録の副作用のため import)

__all__: list[str] = []
