"""図の要素を読むセルの double_solve checker（G-Q1・§6.2）。

独立性: params が持つのは**図に描かれているもの**（点名・直線名・角の大きさ・
直角の頂点の位置）だけで、答え（どの線分・どの直線・どの辺か）は入っていない。
checker はそこから solver を呼び直して答えを組み直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.identify_distance_segment.double_solve")
def double_solve_identify_distance_segment(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.identify_distance_segment")(
            p["point_p"], p["point_foot"], p["point_left"], p["point_right"]
        ),
    )


@register_checker("math.identify_parallel_line.double_solve")
def double_solve_identify_parallel_line(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.identify_parallel_line")(p["base_angle"], p["names"], p["angles"]),
    )


@register_checker("math.identify_right_triangle_sides.double_solve")
def double_solve_identify_right_triangle_sides(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.identify_right_triangle_sides")(
            p["vertex_labels"], p["right_angle_index"]
        ),
    )
