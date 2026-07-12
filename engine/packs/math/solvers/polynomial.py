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


__all__ = [
    "simplify_polynomial",
]
