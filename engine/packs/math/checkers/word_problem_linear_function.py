"""1次関数の利用(word_problem)の double_solve checker（G-Q1 が呼ぶ・§6.2）。

3セル（g2_l28 Lv2/Lv3・g2_l30 Lv3）を1つの checker で賄う。recipe と同じ
`solve_<kind>` 関数を再利用して params の場面文の数値から立式し直し・解き直す
（独立性は「同じ関数を、recipe とは別の呼び出しどきに再実行する」ことで担保する。
G-Q1 が比較するのは各 Solution.answer.srepr のみ——`engine/core/verify/quality_gates.py`
の `_answers_match` 参照——なので checker 側の steps は空でよい。既存
word_problem_linear/system と同型）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_linear_function import (
    RECIPE_NAME,
    solve_meeting,
    solve_second_meeting,
    solve_spring,
    solve_tank,
    solve_tank_race,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_linear_function(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}

    if kind == "spring_two_point":
        return solve_spring(**numbers)
    if kind == "tank_piecewise":
        return solve_tank(**numbers)
    if kind == "meeting_intersection":
        return solve_meeting(**numbers)
    if kind == "tank_race":
        return solve_tank_race(**numbers)
    if kind == "second_meeting":
        return solve_second_meeting(**numbers)
    raise ValueError(f"未知の scenario_kind: {kind!r}")


__all__ = ["double_solve_word_problem_linear_function"]
