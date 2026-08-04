"""平方根の利用＋取りこぼしの double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g3_l23 Lv2/Lv3・g1_l1 Lv1・g1_l11 Lv2）を1つの checker が賄う。recipe が
`math.word_problem_sqrt_misc` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（面積・比・量の大きさ・対象の数）
だけで、答え（1辺の長さ・符号つきの数・かける数）は入っていない。checker は
`SOLVE_BUILDERS`（recipe と共有）でその数値から既存 solver を呼び直し、答えを
独立に再計算する（近似値・素因数の指数といった導出値も params からは読まず、
場面文の数値から導き直す）。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_sqrt_misc import RECIPE_NAME, SOLVE_BUILDERS


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_sqrt_misc(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    labels: dict[str, str] = {k: str(v) for k, v in dict(mr.params["labels"]).items()}
    return SOLVE_BUILDERS[kind](numbers, labels)


__all__ = ["double_solve_word_problem_sqrt_misc"]
