"""連立方程式の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

6セル（g2_l17/g2_l18 の Lv2・Lv3・Lv4）を1つの checker が賄う。recipe が
`math.word_problem_system_equations` 1つに集約されているので、G-Q1 が引く
checker 名（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（速さ・道のり・時間・％・重さ）
だけで、答えは入っていない。checker はその数値から `FORMULATION_BUILDERS` で
連立を立て直し、solver `math.intersection_of_two_lines` で解き直し、`answer_map`
で問われている量まで再計算する。したがって「場面文の数値 → 立式 → (x, y) →
求める量」の連鎖が recipe とは別経路で再現される。

返す Solution の数は params の `guided` から決める（MR の小問数を見ない）。
形をなぞってしまうと「小問が1つ減っていても気づかない」ので、G-Q1 の
個数照合が意味を持つようにここは独立に決める。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_system import (
    RECIPE_NAME,
    format_pair_answer,
    solve_scene,
    solving_steps,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_system(mr: MR) -> list[Solution]:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}
    rows = [tuple(int(sympy.sympify(v)) for v in row) for row in p["answer_map"]]
    answer_map = cast(
        "tuple[tuple[int, int, int], tuple[int, int, int]]", (rows[0], rows[1])
    )
    labels = cast("tuple[str, str]", tuple(str(v) for v in p["answer_labels"]))
    units = cast("tuple[str, str]", tuple(str(v) for v in p["answer_units"]))

    formulation, sol, answer_values = solve_scene(kind, numbers, answer_map)
    value = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            display=format_pair_answer(answer_values, labels, units),
        ),
        steps=solving_steps(sol),
    )
    if not bool(p["guided"]):
        return [value]
    formulation_solution = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(formulation.eqs), display=formulation.display
        ),
        steps=[],
    )
    return [formulation_solution, value]


__all__ = ["double_solve_word_problem_system"]
