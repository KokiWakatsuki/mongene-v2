"""三平方の定理の利用（find_value / knowledge）の double_solve checker（G-Q1・§6.2）。

11 セル（g3_l53.find_value Lv2/Lv3/Lv4・g3_l53.knowledge Lv1・g3_l54.find_value Lv2/Lv3・
g3_l55.find_value Lv2/Lv3/Lv4・g3_l56.find_value Lv2/Lv4）を2つの checker が賄う
（G-Q1 が引く checker 名は `{recipe}.double_solve` なので recipe ごとに1つ）。

独立性: params の `numbers` が持つのは**本文に出ている値**（辺・角・座標・半径・母線と、
どの辺を求めるかの役割語）だけで、答え（斜辺・高さ・面積・体積・最短距離・座標・比）は
入っていない。checker は `SOLVE_BUILDERS` / `solve_special_right_triangle_ratio`
（recipe と共有）でその値から既存 solver を呼び直し、答えを独立に再計算する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.pythagorean_find_value import (
    KNOWLEDGE_RECIPE_NAME,
    RECIPE_NAME,
    SOLVE_BUILDERS,
    solve_special_right_triangle_ratio,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_pythagorean_find_value(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    return SOLVE_BUILDERS[kind](numbers)


@register_checker(f"{KNOWLEDGE_RECIPE_NAME}.double_solve")
def double_solve_special_right_triangle_ratio(mr: MR) -> list[Solution]:
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    return solve_special_right_triangle_ratio(numbers)


__all__ = [
    "double_solve_pythagorean_find_value",
    "double_solve_special_right_triangle_ratio",
]
