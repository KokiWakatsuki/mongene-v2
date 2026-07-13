"""正の数・負の数の四則（数値式の評価）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 expr_str と mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C1（g1 数と式・正負の数）クラスタの計算セル群を1つの汎用ソルバに集約する:
  `math.evaluate_numeric_expression(expr_str, mode)` が数値式を sympy で厳密評価し、
  mode ごとに steps の op 列を変える（＝level_sep）。答えは定数（Integer/Rational）の
  SymbolicAnswer。定数答えの G-Q5t は given whitelist と narration の数字不記載で守る
  （問題文の数値はすべて given 由来＝whitelist なので、答えは原理上漏洩しない・§引継 3）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def fmt_number(v: sympy.Expr) -> str:
    """数（Integer / Rational）を教材表記にする（分数は p/q・符号は分子に載る）。

    例: Integer(-8) -> "-8" / Rational(-1, 3) -> "-1/3" / Rational(2, 3) -> "2/3"。
    """
    if v.is_Integer:
        return str(int(v))
    if isinstance(v, sympy.Rational):
        return f"{v.p}/{v.q}"
    raise ValueError(f"数として表示できない値: {v!r}")


# mode -> op 列（steps の骨格）。level_sep はこの op 列の相異で作る（同一 unit の
# Lv1/Lv2 が異なる mode を持つ）。narration に数字は書かない（G-Q5t 偽陽性の元・§5-#9）。
_MODE_STEPS: dict[str, list[str]] = {
    # g1_l3 加法
    "addition_pair": ["determine_sum_sign", "add_magnitudes"],
    "addition_terms": ["rewrite_as_term_sum", "group_by_sign", "total_terms"],
    # g1_l4 減法
    "subtraction_pair": ["rewrite_subtraction_as_addition", "add_signed"],
    "subtraction_terms": ["rewrite_all_as_addition", "group_by_sign", "total_terms"],
    # g1_l5 加減混合（項の概念）
    "add_sub_terms": ["drop_parentheses_to_terms", "group_by_sign", "total_terms"],
    "add_sub_terms_rational": ["drop_parentheses_to_terms", "align_fractions", "total_terms"],
    # g1_l6 乗法
    "multiplication_pair": ["determine_product_sign", "multiply_magnitudes"],
    "multiplication_chain": ["count_negative_factors", "multiply_all_magnitudes"],
    # g1_l7 累乗
    "power_single": ["rewrite_power_as_product", "evaluate_power_with_sign"],
    "power_sign_contrast": ["identify_base_scope", "evaluate_power_with_sign"],
    # g1_l8 除法
    "divide_pair": ["rewrite_division_as_reciprocal", "multiply_signed"],
    "divide_chain": ["rewrite_all_as_reciprocal", "determine_product_sign", "multiply_all_magnitudes"],
    # g1_l9 四則混合・分配法則
    "four_operations": ["evaluate_powers_and_parentheses", "multiply_and_divide", "add_and_subtract"],
}

# op -> (narration, 非終端 step の result_display フレーズ)。数字は書かない。
_OP_NARRATION: dict[str, str] = {
    "determine_sum_sign": "たがいの数の符号を見て、和の符号を先に決める（同符号なら絶対値の和、異符号なら絶対値の差）。",
    "add_magnitudes": "決めた符号のもとで絶対値を計算し、和を求める。",
    "rewrite_as_term_sum": "かっこを外し、それぞれの数を符号のついた項として並べる。",
    "group_by_sign": "正の項どうし、負の項どうしをそれぞれまとめる。",
    "total_terms": "正の合計と負の合計を合わせて、答えを求める。",
    "rewrite_subtraction_as_addition": "ひく数の符号を変えて、たし算に直す。",
    "add_signed": "符号に注意して和を計算する。",
    "rewrite_all_as_addition": "すべてのひき算を、符号を変えてたし算に直す。",
    "drop_parentheses_to_terms": "かっこを外して、符号のついた項の和とみなす。",
    "align_fractions": "分数・小数を通分してそろえる。",
    "determine_product_sign": "かけ合わせる数の符号から、積の符号を先に決める。",
    "multiply_magnitudes": "絶対値どうしをかけて、積を求める。",
    "count_negative_factors": "負の数の個数を数え、積の符号を決める（偶数個なら正、奇数個なら負）。",
    "multiply_all_magnitudes": "すべての絶対値をかけ合わせて、積を求める。",
    "rewrite_power_as_product": "累乗を、同じ数を指数の回数だけかけ合わせる積に書き直す。",
    "evaluate_power_with_sign": "符号に注意して計算し、累乗の値を求める。",
    "identify_base_scope": "指数がどの数にかかっているか（かっこの有無）を見分ける。",
    "rewrite_division_as_reciprocal": "わる数の逆数をかけるかけ算に直す。",
    "multiply_signed": "符号に注意してかけ算を計算する。",
    "rewrite_all_as_reciprocal": "すべてのわり算を、逆数をかけるかけ算に直す。",
    "evaluate_powers_and_parentheses": "累乗とかっこの中を先に計算する。",
    "multiply_and_divide": "次に、乗法と除法を計算する。",
    "add_and_subtract": "最後に、加法と減法を計算して答えを求める。",
}

_OP_PHRASE: dict[str, str] = {
    "determine_sum_sign": "和の符号を先に決める",
    "rewrite_as_term_sum": "符号のついた項の和に直す",
    "group_by_sign": "正の項・負の項をまとめる",
    "rewrite_subtraction_as_addition": "ひき算をたし算に直す",
    "rewrite_all_as_addition": "すべてたし算に直す",
    "drop_parentheses_to_terms": "かっこを外し項の和とみなす",
    "align_fractions": "分数・小数を通分してそろえる",
    "determine_product_sign": "積の符号を先に決める",
    "count_negative_factors": "負の数の個数から符号を決める",
    "rewrite_power_as_product": "累乗を積に書き直す",
    "identify_base_scope": "指数のかかる数を見分ける",
    "rewrite_division_as_reciprocal": "逆数をかけるかけ算に直す",
    "rewrite_all_as_reciprocal": "すべて逆数のかけ算に直す",
    "evaluate_powers_and_parentheses": "累乗とかっこの中を先に計算する",
    "multiply_and_divide": "乗法と除法を計算する",
}


@register_solver("math.evaluate_numeric_expression")
def evaluate_numeric_expression(expr_str: str, mode: object) -> Solution:
    """正負の数の四則（数値式）を評価して1つの数にする（g1 正負の数 calculation）。

    与式の文字列だけから sympy で厳密評価する（double-solve）。答えは定数
    （Integer/Rational）の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    mode_s = str(mode)
    if mode_s not in _MODE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    # rational=True で小数リテラル（0.5 等）も既約分数として厳密評価する。
    value = sympy.sympify(expr_str, rational=True)
    if not value.is_number:
        raise ValueError(f"数値に評価されない与式: {expr_str!r} -> {value!r}")
    r_srepr = sympy.srepr(value)
    r_disp = fmt_number(value)

    ops = _MODE_STEPS[mode_s]
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


__all__ = ["evaluate_numeric_expression", "fmt_number"]
