"""標本調査の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g3_l59 Lv2/Lv3・g3_l60 Lv3/Lv4）を1つの checker が賄う。recipe が
`math.word_problem_sample_survey` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（標本の大きさ・標本内の該当個数・
既知個数または母集団の大きさ）だけで、答えは入っていない。checker はその数値から
既存 solver（`math.sample_ratio_estimate` / `math.sample_ratio_solve_population`）を
呼び直し、`answer_offset` で問われている量まで再計算する。したがって「場面文の数値
→ 標本比率 → solver → 求める量」の連鎖が recipe とは別経路で再現される。

返す Solution の数は params の `guided` から決める（MR の小問数を見ない）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_sampling import (
    RECIPE_NAME,
    ratio_steps_and_answer,
    solve_scene,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_sample_survey(mr: MR) -> list[Solution]:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}
    offset = int(sympy.sympify(p["answer_offset"]))
    unit = str(p["answer_unit"])

    sol, answer_value = solve_scene(kind, numbers, offset)
    value = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(answer_value), display=f"{answer_value}{unit}"
        ),
        steps=sol.steps,
    )
    if not bool(p["guided"]):
        return [value]

    ratio_steps, ratio_answer = ratio_steps_and_answer(numbers)
    formulation_solution = Solution(answer=ratio_answer, steps=ratio_steps)
    return [formulation_solution, value]


__all__ = ["double_solve_word_problem_sample_survey"]
