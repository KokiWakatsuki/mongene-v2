"""多項式（式の計算）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C2（数と式）クラスタの初セル（g2_l2.calculation 同類項）。`linear.py` は並行編集中の
ため触らず、本ファイルに polynomial 系の独立ヘルパを新設する（linear.py からの
import は可・編集は不可）。
"""
from __future__ import annotations

import re

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

# 任意桁の指数を上付き数字へ（単項式の乗除は 4 次以上も生じうる）。
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _fmt_poly_display(expr: sympy.Expr) -> str:
    """展開済み多項式の表示形（sympy sstr の乗算記号 * を除去・冪を上付きに）。

    例: 6*x -> "6x" / x - 5*y -> "x - 5y" / -x**2 -> "-x²"。
    `engine.packs.math.recipes.linear._fmt_expr` と同方針の独立実装
    （linear.py は編集禁止のため、本モジュール専用にヘルパを複製する）。
    """
    s = str(sympy.sstr(expr))
    s = s.replace("**2", "²").replace("**3", "³")
    return s.replace("*", "")


def _fmt_monomial_display(expr: sympy.Expr) -> str:
    """単項式の表示形（`**n` を任意桁の上付きに変換し `*` を除去）。

    `_fmt_poly_display` は 2/3 次のみ対応だが、単項式どうしの乗除では 4 次以上も
    生じうるため、`**<桁>` を正規表現で上付き数字へ一般化する。整数係数の答え
    （recipe が構成で保証）なので分数バーは出ないが、Rational が sstr で "3/2" と
    出ても `*` を含まないため副作用はない。
    例: -8*x*y -> "-8xy" / 2*a**4 -> "2a⁴"。
    """
    s = str(sympy.sstr(expr))
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_SUPERSCRIPT), s)
    return s.replace("*", "")


@register_solver("math.simplify_polynomial")
def simplify_polynomial(expr_str: str) -> Solution:
    """同類項をまとめて式を簡単にする（g2_l2.calculation）。

    与式の文字列だけから独立に sympy.expand で同類項を集約する（recipe が構成した
    個々の項の内訳は見ない・double-solve）。steps は「同類項を集める」→「係数を
    計算する」の2手（Lv1/Lv2共通の構造。レベル差は recipe 側の項数・文字種で作る）。
    """
    expr = sympy.sympify(expr_str)
    simplified = sympy.expand(expr)

    steps = [
        Step(
            op="group_like_terms",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="文字の部分が同じ項どうしをまとめる",
            # narration に数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
            narration="文字の部分が同じ項（同類項）どうしをまとめる。",
        ),
        Step(
            op="add_coefficients",
            args=[],
            result_srepr=sympy.srepr(simplified),
            result_display=_fmt_poly_display(simplified),
            narration="まとめた同類項の係数を計算し、式を簡単にする。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(simplified), display=_fmt_poly_display(simplified))
    return Solution(answer=answer, steps=steps)


@register_solver("math.add_or_subtract_polynomials")
def add_or_subtract_polynomials(expr_str: str, is_subtraction: object) -> Solution:
    """多項式の加減 (A)±(B) をかっこを外して整理する（g2_l3.calculation Lv1/Lv2）。

    与式の文字列だけから sympy.expand で答えを再計算する（double-solve）。steps は
    加法（かっこをそのまま外す）/減法（うしろのかっこの符号を変えて外す）で op 列を変える
    ＝level_sep。narration には数字を書かない。
    """
    expr = sympy.sympify(expr_str)
    simplified = sympy.expand(expr)
    is_sub = bool(is_subtraction)
    if is_sub:
        first = Step(
            op="distribute_negative_sign",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="うしろのかっこの符号を変えて外す",
            narration="うしろのかっこの前が - なので、かっこの中の各項の符号を変えてかっこを外す。",
        )
    else:
        first = Step(
            op="remove_parentheses",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="かっこをそのまま外す",
            narration="かっこの前が + なので、そのままかっこを外す。",
        )
    second = Step(
        op="add_like_terms",
        args=[],
        result_srepr=sympy.srepr(simplified),
        result_display=_fmt_poly_display(simplified),
        narration="同類項をまとめて計算する。",
    )
    answer = SymbolicAnswer(srepr=sympy.srepr(simplified), display=_fmt_poly_display(simplified))
    return Solution(answer=answer, steps=[first, second])


@register_solver("math.distribute_or_divide")
def distribute_or_divide(expr_str: str, is_division: object) -> Solution:
    """分配法則 k(A) / (A)÷d をかっこを外して計算する（g2_l5.calculation Lv1/Lv2）。

    与式の文字列だけから sympy.expand で答えを再計算する（double-solve）。乗法（分配）と除法
    （逆数をかける→分配）で op 列を変える＝level_sep。narration には数字を書かない。
    """
    expr = sympy.sympify(expr_str)
    simplified = sympy.expand(expr)
    is_div = bool(is_division)
    if is_div:
        steps = [
            Step(
                op="convert_division_to_multiplication",
                args=[],
                result_srepr=sympy.srepr(expr),
                result_display="÷ を逆数をかける計算に直す",
                narration="÷ の計算を、その数の逆数をかっこにかける計算に直す。",
            ),
            Step(
                op="distribute",
                args=[],
                result_srepr=sympy.srepr(simplified),
                result_display=_fmt_poly_display(simplified),
                narration="逆数をかっこの中の各項にかけて計算する。",
            ),
        ]
    else:
        steps = [
            Step(
                op="distribute_multiplication",
                args=[],
                result_srepr=sympy.srepr(simplified),
                result_display=_fmt_poly_display(simplified),
                narration="かっこの前の数を、かっこの中の各項にかけて計算する。",
            ),
        ]
    answer = SymbolicAnswer(srepr=sympy.srepr(simplified), display=_fmt_poly_display(simplified))
    return Solution(answer=answer, steps=steps)


_MONOMIAL_STEPS: dict[str, list[str]] = {
    "simple_mul": ["multiply_coefficients", "combine_powers"],
    "power_mul": ["determine_sign", "multiply_coefficients", "combine_powers"],
    "mul_div_chain": ["convert_divisions_to_reciprocal", "multiply_coefficients", "combine_powers"],
}


@register_solver("math.compute_monomial_expression")
def compute_monomial_expression(expr_str: str, mode: object) -> Solution:
    """単項式どうしの乗除を計算して1つの単項式にする（g2_l4.calculation Lv1/2/3）。

    与式の文字列だけから sympy で積・商を評価する（double-solve）。答えは整数係数の
    単項式（recipe が構成で保証）。mode ごとに steps の op 列を変える＝level_sep:
      Lv1 "simple_mul"    : 係数と1文字の単純な乗法   [multiply_coefficients, combine_powers]
      Lv2 "power_mul"     : 符号・累乗・複数文字の乗法 [determine_sign, +…]
      Lv3 "mul_div_chain" : 乗除混在（逆数変換の連鎖） [convert_divisions_to_reciprocal, +…]
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    expr = sympy.sympify(expr_str)
    result = sympy.simplify(expr)
    mode_s = str(mode)
    if mode_s not in _MONOMIAL_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")

    r_srepr = sympy.srepr(result)
    r_disp = _fmt_monomial_display(result)

    narrations = {
        "multiply_coefficients": "係数どうしをかけ算する。",
        "combine_powers": "同じ文字は指数の和にまとめ、1つの単項式にする。",
        "determine_sign": "かけ合わせる式の符号から、答えの符号を先に決める。",
        "convert_divisions_to_reciprocal": "÷ を、その式の逆数をかけるかけ算に直す。",
    }
    displays = {
        "multiply_coefficients": "係数どうしをかける",
        "combine_powers": r_disp,
        "determine_sign": "答えの符号を先に決める",
        "convert_divisions_to_reciprocal": "÷ を逆数のかけ算に直す",
    }
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=displays[op],
            narration=narrations[op],
        )
        for op in _MONOMIAL_STEPS[mode_s]
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


def _fmt_fraction_display(num: sympy.Expr, den: sympy.Expr) -> str:
    """分数式 (多項式分子)/(整数分母) の表示形（分母1なら分子のみ）。

    例: (11x-2y, 12) -> "(11x - 2y)/12" / (5x, 1) -> "5x"。
    """
    if den == 1:
        return _fmt_poly_display(num)
    return f"({_fmt_poly_display(num)})/{den}"


_FRACTION_STEPS: dict[str, list[str]] = {
    "two_fractions_add": ["find_common_denominator", "combine_numerators"],
    "fractions_with_integer": ["find_common_denominator", "distribute_signs", "add_integer_term"],
}


@register_solver("math.combine_fractional_expressions")
def combine_fractional_expressions(expr_str: str, mode: object) -> Solution:
    """分数式の加減を通分して1つの分数にまとめる（g2_l6.calculation Lv2/Lv3）。

    与式の文字列だけから sympy.together で1つの分数に通分する（double-solve）。分子は
    expand して整理し、分母は最小公倍数のまま残す（＝通分の答え）。mode ごとに steps の
    op 列を変える＝level_sep:
      Lv2 "two_fractions_add"     : 2分数の和   [find_common_denominator, combine_numerators]
      Lv3 "fractions_with_integer": 減法＋整数項 [find_common_denominator, distribute_signs, add_integer_term]
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    expr = sympy.sympify(expr_str)
    combined = sympy.together(expr)
    num, den = sympy.fraction(combined)
    if den.is_negative:
        num, den = -num, -den
    num_e = sympy.expand(num)
    disp = _fmt_fraction_display(num_e, den)

    mode_s = str(mode)
    if mode_s not in _FRACTION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    steps_ops = _FRACTION_STEPS[mode_s]

    narrations = {
        "find_common_denominator": "分母の最小公倍数を求めて通分する。",
        "combine_numerators": "分子どうしを計算し、1つの分数にまとめる。",
        "distribute_signs": "うしろの分数の前が - なので、その分子の各項の符号を変える。",
        "add_integer_term": "整数をふくむ項も同じ分母にそろえて、分子に加える。",
    }
    phrases = {
        "find_common_denominator": "分母を最小公倍数にそろえる",
        "combine_numerators": "分子を計算して1つの分数にまとめる",
        "distribute_signs": "うしろの分子の各項の符号を変える",
        "add_integer_term": "整数の項も通分して分子に加える",
    }
    r_srepr = sympy.srepr(combined)
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=disp if i == len(steps_ops) - 1 else phrases[op],
            narration=narrations[op],
        )
        for i, op in enumerate(steps_ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=disp)
    return Solution(answer=answer, steps=steps)


@register_solver("math.degree_of_expression")
def degree_of_expression(expr_str: str) -> Solution:
    """1変数の単項式・多項式の次数を答える（g2_l1.calculation Lv1）。

    与式の文字列だけから sympy.degree で x についての次数を求める（double-solve）。
    答えは次数（小さな整数・定数）。steps は「次数がもっとも高い項を見つける」→
    「その項の指数の和が次数」の2手。narration には数字を書かない。
    """
    expr = sympy.sympify(expr_str)
    deg = int(sympy.degree(expr, gen=sympy.Symbol("x")))
    deg_expr = sympy.Integer(deg)
    steps = [
        Step(
            op="find_highest_degree_term",
            args=[],
            result_srepr=sympy.srepr(deg_expr),
            result_display="次数がもっとも高い項を見つける",
            narration="式の中で、文字の指数がもっとも高い項を見つける。",
        ),
        Step(
            op="read_degree",
            args=[],
            result_srepr=sympy.srepr(deg_expr),
            result_display=str(deg),
            narration="その項の文字の指数（の和）が、この式の次数になる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(deg_expr), display=str(deg))
    return Solution(answer=answer, steps=steps)


__all__ = [
    "simplify_polynomial",
    "add_or_subtract_polynomials",
    "distribute_or_divide",
    "compute_monomial_expression",
    "combine_fractional_expressions",
    "degree_of_expression",
]
