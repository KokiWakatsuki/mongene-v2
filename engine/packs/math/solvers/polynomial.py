"""多項式（式の計算）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C2（数と式）クラスタの初セル（g2_l2.calculation 同類項）。`linear.py` は並行編集中の
ため触らず、本ファイルに polynomial 系の独立ヘルパを新設する（linear.py からの
import は可・編集は不可）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _fmt_poly_display(expr: sympy.Expr) -> str:
    """展開済み多項式の表示形（sympy sstr の乗算記号 * を除去・冪を上付きに）。

    例: 6*x -> "6x" / x - 5*y -> "x - 5y" / -x**2 -> "-x²"。
    `engine.packs.math.recipes.linear._fmt_expr` と同方針の独立実装
    （linear.py は編集禁止のため、本モジュール専用にヘルパを複製する）。
    """
    s = str(sympy.sstr(expr))
    s = s.replace("**2", "²").replace("**3", "³")
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


__all__ = [
    "simplify_polynomial",
    "add_or_subtract_polynomials",
    "distribute_or_divide",
]
