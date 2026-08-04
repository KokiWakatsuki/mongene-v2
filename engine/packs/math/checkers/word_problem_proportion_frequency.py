"""比例・反比例の利用＋相対度数としての確率の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g1_l36 Lv2/Lv3・g1_l59 Lv2/Lv3）を1つの checker が賄う。recipe が
`math.word_problem_proportion_frequency` 1つに集約されているので、G-Q1 が引く
checker 名（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**本文に出ている数値**（毎分の水量・満水までの分数・分速・
投げた回数・不良品の個数…）だけで、答え（式・値・相対度数）は入っていない。checker は
`SOLVE_BUILDERS`（recipe と共有）でその数値から既存 solver を呼び直し、答えを独立に
再計算する。`variant`（比例か反比例か）は数値ではない構成フラグなので params 直下に
あり、numbers に合流させて渡す。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import MR, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_proportion_frequency import (
    RECIPE_NAME,
    SOLVE_BUILDERS,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_proportion_frequency(mr: MR) -> list[Solution]:
    kind = str(mr.params["scenario_kind"])
    numbers: dict[str, Any] = dict(mr.params["numbers"])
    variant = mr.params.get("variant")
    if variant is not None:
        numbers["variant"] = str(variant)
    return SOLVE_BUILDERS[kind](numbers)


__all__ = ["double_solve_word_problem_proportion_frequency"]
