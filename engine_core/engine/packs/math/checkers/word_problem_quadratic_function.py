"""関数 y=ax² の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g3_l32 Lv2・g3_l36 Lv2/Lv3・g3_l38 Lv3）を1つの checker が賄う。recipe が
`math.word_problem_quadratic_function` 1つに集約されているので、G-Q1 が引く
checker 名（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文・小問文に出ている数値**（比例定数が本文で与えられる
セルの a・秒数・距離・速さ・正方形の1辺）だけで、比例定数 a（g3_l36 の導出値）も答えも
入っていない。checker は `SOLVE_BUILDERS`（recipe と共有）でその数値から既存 solver を
呼び直し、答えを独立に再計算する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_quadratic_function import (
    RECIPE_NAME,
    SOLVE_BUILDERS,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_quadratic_function(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    return SOLVE_BUILDERS[kind](numbers)


__all__ = ["double_solve_word_problem_quadratic_function"]
