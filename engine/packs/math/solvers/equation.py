"""一次方程式（1変数）を解く独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（方程式の文字列 equation_str と mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C1（g1 数と式・一次方程式）クラスタの解法セル群を1つの汎用ソルバに集約する（arithmetic.py の
`evaluate_numeric_expression` と同型）:
  `math.solve_linear_equation(equation_str, mode)` が "lhs=rhs" を sympy.solve で x について解く。
  答えは解 x=定数（Integer/Rational）。mode ごとに steps の op 列を変える（＝level_sep）。
  定数答えの G-Q5t は問題文の数値がすべて given 由来（whitelist・両符号）なので漏洩しない。
  narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_number

# mode -> op 列（steps の骨格）。level_sep はこの op 列の相異で作る。
_EQUATION_STEPS: dict[str, list[str]] = {
    # g1_l21 等式の性質
    "equality_add": ["subtract_constant_both_sides", "state_solution"],
    "equality_multi": ["subtract_constant_both_sides", "divide_both_sides"],
    # g1_l22 移項
    "transpose_constant": ["transpose_constant", "state_solution"],
    "transpose_both": ["transpose_terms", "combine_and_divide"],
}

_OP_NARRATION: dict[str, str] = {
    "subtract_constant_both_sides": "等式の性質を使い、両辺から同じ数をひく（または加える）。",
    "state_solution": "両辺を計算して、解を求める。",
    "divide_both_sides": "等式の性質を使い、両辺を x の係数でわる。",
    "transpose_constant": "数の項を、符号を変えて反対の辺に移項する。",
    "transpose_terms": "文字の項を左辺に、数の項を右辺に、符号を変えて移項する。",
    "combine_and_divide": "両辺をそれぞれ整理し、x の係数で両辺をわって解を求める。",
}

_OP_PHRASE: dict[str, str] = {
    "subtract_constant_both_sides": "両辺から同じ数をひく",
    "transpose_constant": "数の項を移項する",
    "transpose_terms": "文字は左辺・数は右辺に移項する",
}


@register_solver("math.solve_linear_equation")
def solve_linear_equation(equation_str: str, mode: object) -> Solution:
    """1変数の一次方程式を解いて解 x=定数を求める（g1 一次方程式 calculation）。

    equation_str（"lhs=rhs"）と mode だけから sympy.solve で x について解く（double-solve）。
    答えは解 x=定数（Integer/Rational）の SymbolicAnswer（display="x = ..."）。mode ごとに
    steps の op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _EQUATION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    lhs_s, rhs_s = equation_str.split("=")
    x = sympy.Symbol("x")
    eq = sympy.Eq(sympy.sympify(lhs_s, rational=True), sympy.sympify(rhs_s, rational=True))
    sols = sympy.solve(eq, x)
    if len(sols) != 1:
        raise ValueError(f"一意に解けない方程式: {equation_str!r} -> {sols!r}")
    value = sympy.Rational(sols[0])
    r_srepr = sympy.srepr(value)
    r_disp = f"x = {fmt_number(value)}"

    ops = _EQUATION_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=r_disp if i == len(ops) - 1 else _OP_PHRASE.get(op, ""),
            narration=_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


__all__ = ["solve_linear_equation"]
