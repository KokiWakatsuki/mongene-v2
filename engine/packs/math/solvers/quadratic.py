"""2次方程式まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 eq_str と mode）から答えと steps を導く。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C3（g3 数と式・2次方程式）クラスタの求解セル群（平方根の考え・平方完成・解の公式・
因数分解・解法選択）を1つの汎用ソルバ `math.solve_quadratic(eq_str, mode)` に集約する。
eq_str は "左辺=右辺" 形式で "=" で分割して解く。答えは解を昇順に並べた Tuple の
SymbolicAnswer（解が2つ）。根号は √ 表示、分数＋根号は together で単一分数にまとめる
（例 (-5+√17)/4）。mode ごとに steps の op 列を変える＝level_sep。

代入して左辺の値を求める mode（evaluate_quadratic）だけは答えが単一の値（SymbolicAnswer）。
"""
from __future__ import annotations

import re

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_X = sympy.Symbol("x")
_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


def _fmt_scalar(v: sympy.Expr) -> str:
    """1つの解／値の表示（sqrt(n)→√n・分数＋根号は together で単一分数・`*` 除去）。"""
    s = _SQRT_RE.sub(r"√\1", str(sympy.sstr(sympy.together(v))))
    return s.replace("*", "")


def _parse_eq(eq_str: str) -> sympy.Expr:
    """"左辺=右辺" を (左辺)-(右辺) の式に直す（=0 の左辺）。"""
    lhs_s, rhs_s = eq_str.split("=", 1)
    return sympy.sympify(lhs_s) - sympy.sympify(rhs_s)


def _sorted_roots(eq_str: str) -> list[sympy.Expr]:
    """2次方程式の解を実部→虚部の昇順で並べて返す（決定論）。"""
    expr = _parse_eq(eq_str)
    roots = sympy.solve(sympy.Eq(expr, 0), _X)
    return sorted(
        roots,
        key=lambda r: (float(sympy.re(r.evalf())), float(sympy.im(r.evalf()))),
    )


# mode -> op 列（level_sep はこの op 列の相異で作る）。narration に数字を書かない。
_QUAD_STEPS: dict[str, list[str]] = {
    # g3_l24 代入して左辺の値を求める（＝解かどうかの確認）
    "evaluate_quadratic": ["substitute_value", "evaluate_left_side"],
    # g3_l25 平方根の考え方
    "solve_square_form": ["take_square_root", "solve_two_cases"],
    "solve_complete_square": ["complete_the_square", "take_square_root", "solve_two_cases"],
    # g3_l26 解の公式
    "solve_formula": ["identify_coefficients", "apply_quadratic_formula"],
    "solve_formula_hard": ["identify_coefficients", "compute_discriminant", "apply_quadratic_formula"],
    # g3_l27 因数分解
    "solve_factoring": ["factor_left_side", "apply_zero_product"],
    "solve_factoring_common": ["factor_out_common", "apply_zero_product"],
    # g3_l28 解法の選択
    "solve_rearrange": ["expand_and_rearrange", "factor_left_side", "apply_zero_product"],
    "solve_choose": ["factor_out_common_binomial", "apply_zero_product"],
    # g3_l29/l30 立式した2次方程式の求解（x(x+c)=k 型）
    "solve_product_form": ["expand_and_rearrange", "factor_left_side", "apply_zero_product"],
    # g3_l30.find_value 図形条件から立式し、正の解のみを採用する
    "solve_product_form_positive_root": [
        "expand_and_rearrange", "factor_left_side", "apply_zero_product", "select_positive_root",
    ],
}

_QUAD_OP_NARRATION: dict[str, str] = {
    # narration の数字は原則書かない（G-Q5t 偽陽性の元＝§5-#9。特に "b²-4ac" の 4 が
    # 答えの根号係数トークンと衝突した実バグあり→語で述べる）。ただし "0" は given の
    # "=0" で常に whitelist されるため自然に用いてよい。
    "substitute_value": "指定された値を左辺の文字に代入する。",
    "evaluate_left_side": "左辺を計算して、その値を求める（値が 0 なら等式が成り立つ）。",
    "take_square_root": "平方根の考え方で、両辺の平方根をとる。",
    "solve_two_cases": "正の場合と負の場合に分けて x を求める。",
    "complete_the_square": "定数項を移項し、両辺に同じ数を加えて左辺を平方の形にする。",
    "identify_coefficients": "与式を整理して、それぞれの項の係数 a・b・c を読み取る。",
    "apply_quadratic_formula": "a・b・c を解の公式に代入して x を求める。",
    "compute_discriminant": "根号の中の値（判別式）を計算する。",
    "factor_left_side": "左辺を因数分解する。",
    "apply_zero_product": "積が 0 になるのは各因数が 0 のときだから、それぞれを 0 とおいて x を求める。",
    "factor_out_common": "左辺の共通因数をくくり出す。",
    "expand_and_rearrange": "かっこを展開し、右辺を左辺に移項して、=0 の形に整理する。",
    "factor_out_common_binomial": "両辺を移項し、共通なかっこをくくり出す。",
    "select_positive_root": "求めるものは正の数だから、2つの解のうち条件に合う正の解を選ぶ。",
}

_QUAD_OP_PHRASE: dict[str, str] = {
    "substitute_value": "値を代入する",
    "take_square_root": "平方根をとる",
    "complete_the_square": "平方完成する",
    "identify_coefficients": "a・b・c を読み取る",
    "compute_discriminant": "根号の中を計算する",
    "factor_left_side": "左辺を因数分解する",
    "factor_out_common": "共通因数をくくり出す",
    "expand_and_rearrange": "展開して整理する",
    "factor_out_common_binomial": "共通なかっこをくくり出す",
}

_EVALUATE_MODES = {"evaluate_quadratic"}
_POSITIVE_ROOT_MODES = {"solve_product_form_positive_root"}


@register_solver("math.solve_quadratic")
def solve_quadratic(eq_str: str, mode: object, value: object = None) -> Solution:
    """2次方程式を解く／左辺に値を代入して評価する（C3 g3_l24〜l28.calculation）。

    与式の文字列 eq_str と mode だけから答えを導く（recipe の構成内訳は見ない・double-solve）。
    solve 系: 答えは解を昇順に並べた Tuple の SymbolicAnswer。evaluate 系: value を代入した
    左辺の値の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    """
    mode_s = str(mode)
    if mode_s not in _QUAD_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    ops = _QUAD_STEPS[mode_s]

    if mode_s in _EVALUATE_MODES:
        expr = _parse_eq(eq_str)  # 左辺（右辺は0）
        val = sympy.nsimplify(sympy.sympify(str(value)))
        result = sympy.simplify(expr.subs(_X, val))
        disp = _fmt_scalar(result)
        srepr = sympy.srepr(result)
    elif mode_s in _POSITIVE_ROOT_MODES:
        roots = _sorted_roots(eq_str)
        positive = [r for r in roots if r.is_real and r > 0]
        assert len(positive) == 1, f"正の解がちょうど1つでない: {eq_str} -> {roots}"
        disp = _fmt_scalar(positive[0])
        srepr = sympy.srepr(positive[0])
    else:
        roots = _sorted_roots(eq_str)
        answer_tuple = sympy.Tuple(*roots)
        srepr = sympy.srepr(answer_tuple)
        disp = ", ".join(f"x = {_fmt_scalar(r)}" for r in roots)

    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _QUAD_OP_PHRASE.get(op, ""),
            narration=_QUAD_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = ["solve_quadratic"]
