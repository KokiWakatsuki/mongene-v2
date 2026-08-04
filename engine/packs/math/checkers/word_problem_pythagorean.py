"""三平方の定理の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

3セル（g3_l53 Lv3・g3_l55 Lv3・g3_l56 Lv3）を1つの checker が賄う。recipe が
`math.word_problem_pythagorean` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている長さ**（ひし形の1辺と対角線・正四角錐の
底面の1辺と側辺・直方体の3辺）だけで、答え（対角線・高さ・面積・体積・最短距離）は
入っていない。checker は `SOLVE_BUILDERS`（recipe と共有）でその数値から既存 solver
（`math.pythagorean_hypotenuse` / `math.solve_quadratic`）を呼び直し、答えを独立に
再計算する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_pythagorean import RECIPE_NAME, SOLVE_BUILDERS


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_pythagorean(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    return SOLVE_BUILDERS[kind](numbers)


__all__ = ["double_solve_word_problem_pythagorean"]
