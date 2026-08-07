"""1元1次方程式の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

6セル（g1_l25/l26/l27 の Lv2・Lv3）を1つの checker が賄う。recipe が
`math.word_problem_linear_equation` 1つに集約されているので、G-Q1 が引く
checker 名（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（単価・総数・合計代金・過不足の
枚数…）だけで、答えは入っていない。checker はその数値から
`FORMULATION_BUILDERS` で立式し直し、solver `math.solve_linear_equation` で
解き直し、`answer_coeff` で問われている量まで再計算する。したがって
「場面文の数値 → 立式 → x → 求める量」の連鎖が recipe とは別経路で再現される。

返す Solution の数は params の `guided` から決める（MR の小問数を見ない）。
形をなぞってしまうと「小問が1つ減っていても気づかない」ので、G-Q1 の
個数照合が意味を持つようにここは独立に決める。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import REGISTRY, register_checker
from engine.packs.math.recipes.word_problem_linear import RECIPE_NAME, solve_scene


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_linear(mr: MR) -> list[Solution]:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}
    coeff_a, coeff_b = (int(sympy.sympify(c)) for c in p["answer_coeff"])
    unit = str(p["answer_unit"])

    formulation, sol, answer_value = solve_scene(kind, numbers, (coeff_a, coeff_b))
    value = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(answer_value), display=f"{answer_value}{unit}"
        ),
        steps=sol.steps,
    )
    if not bool(p["guided"]):
        return [value]
    formulation_solution = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(formulation.eq), display=formulation.display
        ),
        steps=[],
    )
    return [formulation_solution, value]


@register_checker("math.word_problem_round_trip_average_speed.double_solve")
def double_solve_word_problem_round_trip_average_speed(mr: MR) -> Solution:
    """g1_l27.word_problem Lv4。渡すのは本文に出ている速さ2つと往復の時間だけ。

    片道の道のりも平均の速さも params に無いので、解き直しが答えの読み直しにならない。
    """
    n = mr.params["numbers"]
    solver = REGISTRY.solver("math.solve_round_trip_average_speed")
    return cast(
        Solution, solver(n["speed_go"], n["speed_back"], n["total_time"])
    )


__all__ = [
    "double_solve_word_problem_linear",
    "double_solve_word_problem_round_trip_average_speed",
]
