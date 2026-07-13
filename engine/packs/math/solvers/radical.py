"""平方根（根号）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 expr_str と mode）から答えと steps を導く。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C3（g3 数と式・平方根）クラスタの簡約セル群（乗除・a√b 変形・有理化・加減・分配/共役）を
1つの汎用ソルバ `math.simplify_radical(expr_str, mode)` に集約する。sympy で根号式を
正準形へ簡約し、mode ごとに steps の op 列を変える（＝level_sep）。答えは根号を含む定数式の
SymbolicAnswer。表示は `sqrt(n)` を `√n` に直す（教材表記）。

有理化（分母に根号）系の mode は sympy.radsimp（分母の有理化を確実に行う）、それ以外は
sympy.simplify（乗除・簡単化・加減・展開の正準化）で分ける。
"""
from __future__ import annotations

import re

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


def fmt_radical(expr: sympy.Expr) -> str:
    """根号式の表示形（`sqrt(n)`→`√n`・`*` 除去）。例: 3*sqrt(2)->"3√2" / sqrt(2)+sqrt(5)->"√2 + √5"。"""
    s = _SQRT_RE.sub(r"√\1", str(sympy.sstr(expr)))
    return s.replace("*", "")


# mode -> op 列（level_sep はこの op 列の相異で作る）。narration に数字を書かない。
_RADICAL_STEPS: dict[str, list[str]] = {
    # g3_l14 根号と平方の相互変換
    "square_of_root": ["square_the_root"],
    # g3_l17 平方根の乗法・除法
    "root_mult": ["multiply_under_one_root", "simplify_root"],
    "root_mult_div": ["rewrite_division_as_multiplication", "combine_roots", "simplify_result"],
    # g3_l18 根号の中を簡単にする（a√b）
    "simplify_root": ["factor_out_square", "take_root_outside"],
    "simplify_root_large": ["factor_into_squares", "take_roots_outside", "simplify_result"],
    # g3_l19 分母の有理化（単項）
    "rationalize_mono": ["multiply_by_same_root", "simplify_fraction"],
    # g3_l20 平方根の加法・減法
    "add_roots": ["combine_like_radicals"],
    "add_roots_simplify": ["simplify_each_root", "combine_like_radicals"],
    # g3_l21 いろいろな計算（分配・共役有理化）
    "expand_roots": ["expand_with_distribution", "combine_like_terms_and_radicals"],
    "rationalize_conjugate": ["multiply_by_conjugate", "simplify_fraction"],
}

_RADICAL_OP_NARRATION: dict[str, str] = {
    "square_the_root": "根号のついた数を2乗し、根号の中の数にもどす。",
    "multiply_under_one_root": "根号の積を、1つの根号の中の積にまとめる。",
    "simplify_root": "根号の中を素因数分解し、平方の因数を根号の外に出す。",
    "rewrite_division_as_multiplication": "わり算を、逆数をかけるかけ算に直す。",
    "combine_roots": "係数どうし・根号の中どうしをそれぞれまとめる。",
    "simplify_result": "根号の中をできるだけ簡単な形に直す。",
    "factor_out_square": "根号の中を素因数分解し、平方の因数を見つける。",
    "take_root_outside": "平方の因数を根号の外に出して a√b の形にする。",
    "factor_into_squares": "根号の中の大きな数を、平方の因数と残りに分ける。",
    "take_roots_outside": "それぞれの平方の因数を根号の外に出す。",
    "multiply_by_same_root": "分母と分子に、分母と同じ根号をかける。",
    "simplify_fraction": "分母を根号のない形にし、約分して簡単にする。",
    "combine_like_radicals": "根号の中が同じ項を、同類項のようにまとめる。",
    "simplify_each_root": "それぞれの根号を a√b の形に直す。",
    "expand_with_distribution": "分配法則や乗法公式で根号を含む式を展開する。",
    "combine_like_terms_and_radicals": "数の項どうし・根号の項どうしをまとめる。",
    "multiply_by_conjugate": "分母と分子に、分母の共役な式をかける。",
}

_RADICAL_OP_PHRASE: dict[str, str] = {
    "multiply_under_one_root": "1つの根号にまとめる",
    "rewrite_division_as_multiplication": "わり算をかけ算に直す",
    "combine_roots": "係数と根号をまとめる",
    "factor_out_square": "平方の因数を見つける",
    "factor_into_squares": "平方の因数に分ける",
    "take_roots_outside": "根号の外に出す",
    "multiply_by_same_root": "同じ根号をかける",
    "simplify_each_root": "各根号を a√b にする",
    "expand_with_distribution": "展開する",
    "multiply_by_conjugate": "共役な式をかける",
}

# 分母の有理化を確実に行う mode（sympy.radsimp を使う）。
_RATIONALIZE_MODES = {"rationalize_mono", "rationalize_conjugate"}


def _canonicalize(expr: sympy.Expr, mode: str) -> sympy.Expr:
    """mode に応じて根号式を正準形へ簡約する。

    非有理化系は sympy.expand で正準化する（sympy は sqrt を自動で a√b に簡約するため、
    expand は乗除・簡単化・加減・展開のすべてで sympy.simplify と同一結果を与え、かつ
    約15倍高速。全 mode の代表式で expand==simplify を実測確認済み）。有理化系は分母の
    有理化を確実に行う sympy.radsimp を使う。
    """
    if mode in _RATIONALIZE_MODES:
        return sympy.radsimp(expr)
    return sympy.expand(expr)


@register_solver("math.simplify_radical")
def simplify_radical(expr_str: str, mode: object) -> Solution:
    """根号を含む式を簡約する（C3 g3_l14/l17〜l21.calculation）。

    与式の文字列だけから sympy で正準形へ簡約する（recipe の構成内訳は見ない・double-solve）。
    答えは根号を含む定数式の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _RADICAL_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    expr = sympy.sympify(expr_str)
    result = _canonicalize(expr, mode_s)
    disp = fmt_radical(result)
    srepr = sympy.srepr(result)

    ops = _RADICAL_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _RADICAL_OP_PHRASE.get(op, ""),
            narration=_RADICAL_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = ["simplify_radical", "fmt_radical"]
