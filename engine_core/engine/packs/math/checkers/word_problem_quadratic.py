"""2次方程式の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g3_l29/g3_l30 の Lv2・Lv3）を1つの checker が賄う。recipe が
`math.word_problem_quadratic` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**（積・倍率・差・面積・1辺の長さ）
だけで、答えは入っていない。checker はその数値から `FORMULATION_BUILDERS` で
立式し直し、solver `math.solve_quadratic`（mode=solve_product_form_positive_root）
で正の解のみを解き直し、`answer_coeffs` で問われている量まで再計算する。したがって
「場面文の数値 → 立式 → 正の解 → 求める量」の連鎖が recipe とは別経路で再現される。

返す Solution の数は params の `guided` から決める（MR の小問数を見ない）。
形をなぞってしまうと「小問が1つ減っていても気づかない」ので、G-Q1 の
個数照合が意味を持つようにここは独立に決める。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_quadratic import (
    RECIPE_NAME,
    format_answer,
    solve_scene,
)


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_quadratic(mr: MR) -> list[Solution]:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}
    coeffs = tuple(
        (int(sympy.sympify(m)), int(sympy.sympify(n))) for m, n in p["answer_coeffs"]
    )
    labels = tuple(str(v) for v in p["answer_labels"])
    units = tuple(str(v) for v in p["answer_units"])

    formulation, sol, answer_values = solve_scene(kind, numbers, coeffs)
    value = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            display=format_answer(answer_values, labels, units),
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


__all__ = ["double_solve_word_problem_quadratic"]
