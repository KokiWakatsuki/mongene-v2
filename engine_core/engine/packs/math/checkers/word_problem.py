"""文章題（form=word_problem）の double_solve checker（G-Q1 が呼ぶ・§6.2）。

**多段小問の checker の型**: G-Q1 は「小問と同数の Solution」を要求するので、
誘導つき文章題の checker は `list[Solution]` を返す（1小問セルの checker は
従来どおり `Solution` 単体でよい）。これにより (1) だけ検証され (2) が素通り、
という無検証の小問が構造的に作れない。

独立性: params が持つのは**係数の行**（個数の式・代金の式）だけで、答え (a, b) は
入っていない。checker はその係数から立式し直し（(1)）・連立を解き直す（(2)）ので、
「場面文の数値 → 立式 → 解」の連鎖が recipe とは別経路で再現される。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import REGISTRY, register_checker
from engine.packs.math.recipes.word_problem import build_price_count_equations


@register_checker("math.word_problem_price_count.double_solve")
def double_solve_word_problem_price_count(mr: MR) -> list[Solution]:
    p = mr.params
    _, _, total = (int(sympy.sympify(c)) for c in p["line_count"])
    price_a, price_b, cost = (int(sympy.sympify(c)) for c in p["line_cost"])

    equations, eq_display = build_price_count_equations(total, price_a, price_b, cost)
    formulation = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(equations), display=eq_display), steps=[]
    )

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    value = cast(
        Solution, solver((1, 1, total), (price_a, price_b, cost), str(p["method"]))
    )
    return [formulation, value]


__all__ = ["double_solve_word_problem_price_count"]
