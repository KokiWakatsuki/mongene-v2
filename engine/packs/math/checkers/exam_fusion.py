"""exam（入試対策・T1融合）まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.exam_probability_from_counts.double_solve")
def double_solve_exam_probability_from_counts(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.exam_relative_frequency.double_solve")
def double_solve_exam_relative_frequency(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.relative_frequency")
    return cast(Solution, solver(p["occurred"], p["total"]))


@register_checker("math.exam_quartiles_full_summary.double_solve")
def double_solve_exam_quartiles_full_summary(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.quartiles_full_summary")
    return cast(Solution, solver(p["data"]))


# ---------------------------------------------------------------------------
# exam_l1（入試融合・一次関数と図形の融合）— C13
#
# 渡すのは本文に出ている数値（直線の傾き・切片、面積の条件、倍率）だけ。
# 答え（交点の座標・面積・逆算した係数・求める点）は params に無いので、
# 解き直しが答えの読み直しにならない。
# ---------------------------------------------------------------------------
@register_checker("math.exam_linear_intersection_area.double_solve")
def double_solve_exam_linear_intersection_area(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.lines_intersection_and_triangle_area")(
            p["m1"], p["b1"], p["m2"], p["b2"]
        ),
    )


@register_checker("math.exam_linear_coefficient_from_area.double_solve")
def double_solve_exam_linear_coefficient_from_area(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution, REGISTRY.solver("math.slope_from_triangle_area")(p["intercept"], p["area"])
    )


@register_checker("math.exam_linear_line_through_triangle.double_solve")
def double_solve_exam_linear_line_through_triangle(mr: MR) -> Solution:
    """判定を、図ではなく直線の式と頂点の座標から解き直す。"""
    p = mr.params
    verts = [_parse_pair(s) for s in p["polygon_pts"]]
    return cast(
        Solution, REGISTRY.solver("math.judge_line_through_triangle")(p["a"], p["b"], verts)
    )


def _parse_pair(s: str) -> tuple[int, int]:
    """"(3, -2)" のような文字列を整数の組に戻す（params は文字列で持つ）。"""
    x, y = s.strip("() ").split(",")
    return int(x), int(y)


@register_checker("math.exam_linear_guided_triangle.double_solve")
def double_solve_exam_linear_guided_triangle(mr: MR) -> list[Solution]:
    """(1)=交点・(2)=2つの x 切片・(3)=三角形の面積。"""
    p = mr.params["numbers"]
    args = (p["m1"], p["b1"], p["m2"], p["b2"])
    return [
        cast(Solution, REGISTRY.solver("math.intersection_point_of_two_lines")(*args)),
        cast(Solution, REGISTRY.solver("math.x_intercepts_of_two_lines")(*args)),
        cast(Solution, REGISTRY.solver("math.triangle_area_from_two_lines")(*args)),
    ]


@register_checker("math.exam_linear_area_multiple_point.double_solve")
def double_solve_exam_linear_area_multiple_point(mr: MR) -> Solution:
    p = mr.params["numbers"]
    return cast(
        Solution,
        REGISTRY.solver("math.point_on_x_axis_for_area_multiple")(
            p["slope"], p["intercept"], p["multiple"]
        ),
    )
