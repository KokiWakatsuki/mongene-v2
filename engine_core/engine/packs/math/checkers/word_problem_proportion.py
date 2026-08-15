"""比例・反比例の利用の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g1_l29/g1_l33 の Lv2・Lv3）を1つの checker が賄う。recipe が
`math.word_problem_proportion` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**読者に見えている数値**（1mあたりの重さ・分速・面積・
最初の人数と日数…）だけで、答え（比例定数 a や求める値）は入っていない。checker は
その数値から `solve_scene` で a を求め直し・値を求め直す。したがって「場面の数値 →
a → 式 → 値」の連鎖が recipe とは別経路で再現される。

返す Solution の数は params の `guided` から決める（MR の小問数を見ない）。
形をなぞってしまうと「小問が1つ減っていても気づかない」ので、G-Q1 の個数照合が
意味を持つようにここは独立に決める。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_proportion import RECIPE_NAME, solve_scene


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_proportion(mr: MR) -> list[Solution]:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}

    formulation, value_answer, value_steps = solve_scene(kind, numbers)
    value_solution = Solution(answer=value_answer, steps=value_steps)
    if not bool(p["guided"]):
        return [value_solution]
    formulation_solution = Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(formulation.expr), display=formulation.display
        ),
        steps=[],
    )
    return [formulation_solution, value_solution]


__all__ = ["double_solve_word_problem_proportion"]
