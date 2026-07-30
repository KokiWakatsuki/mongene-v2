"""確率の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

6セル（g2_l51 Lv2/Lv3・g2_l52 Lv3・g2_l53 Lv3・g2_l54 Lv2/Lv3）を1つの checker が
賄う。recipe が `math.word_problem_probability` 1つに集約されているので、G-Q1 が
引く checker 名（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（玉の個数・カード枚数・さいころの
面数・くじの本数…）だけで、答え（確率）は入っていない。checker は
`SOLVE_BUILDERS`（recipe と共有）でその数値から既存 solver を呼び直し、答えを
独立に再計算する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_probability import RECIPE_NAME, SOLVE_BUILDERS


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_probability(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    return SOLVE_BUILDERS[kind](numbers)


__all__ = ["double_solve_word_problem_probability"]
