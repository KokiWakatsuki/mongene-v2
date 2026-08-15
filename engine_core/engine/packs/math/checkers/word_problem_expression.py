"""数量を文字式で表す文章題の double_solve checker（G-Q1 が呼ぶ・§6.2）。

5セル（g1_l12 Lv1/Lv2・g1_l15 Lv1/Lv2/Lv3）を1つの checker が賄う。recipe が
`math.word_problem_expression` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値/文字**（単価・割引き・速さ・g1_l15
Lv3 の3文字の選び方…）だけで、答えは入っていない。checker はその数値/文字から
`FORMULATION_BUILDERS` で式を組み直し、既存 solver（`math.simplify_notation` /
`math.evaluate_letter_expression` / `math.compute_monomial_expression`）で独立に
再計算する。1小問セル（誘導なし）なので `Solution` 単体を返す（G-Q1 の対応規約）。
"""
from __future__ import annotations

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_expression import (
    RECIPE_NAME,
    build_answer,
    solve_expression,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_expression(mr: MR) -> Solution:
    kind = str(mr.params["scenario_kind"])
    numbers = {k: str(v) for k, v in mr.params["numbers"].items()}
    formulation, sol = solve_expression(kind, numbers)
    return Solution(answer=build_answer(formulation, sol), steps=[])


__all__ = ["double_solve_word_problem_expression"]
