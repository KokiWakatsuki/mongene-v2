"""文字式（一次式の計算）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 expr_str と mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C1（g1 数と式・文字式）クラスタの計算セル群を1つの汎用ソルバに集約する（arithmetic.py の
`evaluate_numeric_expression` と同型の設計）:
  `math.evaluate_letter_expression(expr_str, mode)` が一次式を sympy.expand で厳密に整理し、
  mode ごとに steps の op 列を変える（＝level_sep）。答えは自由変数 x を含む一次式
  （SymbolicAnswer）。式答え（free_symbol 含む）は display 全体一致でのみ漏洩検査されるため
  G-Q5t は相対安全（§引継 13c-2-#1）。narration には数字を書かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.term_definitions import definition_for, rule_reason_for
from engine.packs.math.solvers.arithmetic import fmt_number
from engine.packs.math.solvers._step_text import (
    fmt_expr,
    join_signed,
    top_level_parts,
)
from engine.packs.math.solvers.polynomial import (
    _fmt_monomial_display,
    _fmt_poly_display,
    _terms_in_written_order,
    grouped_by_variable_part,
)

# mode -> op 列（steps の骨格）。level_sep はこの op 列の相異で作る（同一 unit の
# Lv1/Lv2 が異なる mode を持つ）。narration に数字は書かない（G-Q5t 偽陽性の元・§5-#9）。
_MODE_STEPS: dict[str, list[str]] = {
    # g1_l17 一次式の加法・減法
    "combine_linear": ["group_like_terms", "add_coefficients"],
    "expand_paren_linear": ["remove_parentheses", "add_like_terms"],
    # g1_l18 一次式と数の乗法・除法
    "distribute_linear": ["distribute_multiplication"],
    "distribute_divide_linear": [
        "distribute_multiplication",
        "convert_division_to_multiplication",
        "add_like_terms",
    ],
}

# op -> narration（数字を書かない）。
_OP_NARRATION: dict[str, str] = {
    "group_like_terms": "文字の部分が同じ項（同類項）どうしをまとめる。",
    "add_coefficients": "まとめた同類項の係数を計算して、式を簡単にする。",
    "remove_parentheses": "それぞれのかっこを、前の符号に注意して外す（前が - のときは中の各項の符号を変える）。",
    "add_like_terms": "同類項をまとめて計算する。",
    "distribute_multiplication": "かっこの前の数を、かっこの中の各項にかけて計算する。",
    "convert_division_to_multiplication": "÷ の計算を、その数の逆数をかっこの中の各項にかける計算に直す。",
}

# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**式そのもの**（面③）。以前は「同類項どうしをまとめる」の
# ような指示の言い直しが入っていた。`narration` は触らない（ヒントが narration しか
# 見ないので、そちらに数字を書くと答えの先出しになる）。
# ---------------------------------------------------------------------------
def _linear_step_displays(expr_str: str, mode: str, final: str) -> list[str]:
    """一次式の計算の各手の括弧に入れる表示（最後は答え）。"""
    if mode == "combine_linear":
        return [grouped_by_variable_part(_terms_in_written_order(expr_str)), final]
    if mode == "expand_paren_linear":
        return [join_signed(_terms_in_written_order(expr_str)), final]
    if mode == "distribute_divide_linear":
        # `4(x - 5) - (4x + 4) ÷ 2` の3手。
        #   ① かっこの前の数を配る（÷ の部分はまだ触らない）
        #   ② ÷ を逆数のかけ算にして、その部分も式にする
        #   ③ 同類項をまとめる（＝答え）
        parts = top_level_parts(expr_str, "+-")

        def line(divide_done: bool) -> str:
            out = ""
            for op, part in parts:
                joiner = "" if not out else (" - " if op == "-" else " + ")
                if "/" in part:
                    num, den = part.rsplit("/", 1)
                    inner = sympy.expand(sympy.sympify(num))
                    piece = (
                        f"({fmt_expr(sympy.expand(inner / sympy.sympify(den)))})"
                        if divide_done
                        else f"({fmt_expr(inner)}) ÷ {fmt_expr(sympy.sympify(den))}"
                    )
                else:
                    piece = fmt_expr(sympy.expand(sympy.sympify(part)))
                out += joiner + piece
            return out

        return [line(False), line(True), final]
    raise ValueError(f"途中の表示を組めない mode: {mode!r}")


@register_solver("math.evaluate_letter_expression")
def evaluate_letter_expression(expr_str: str, mode: object) -> Solution:
    """一次式の計算（加減・乗除）を整理して1つの一次式にする（g1 文字式 calculation）。

    与式の文字列だけから sympy.expand で厳密に整理する（double-solve）。答えは自由変数 x を
    含む一次式（SymbolicAnswer）。mode ごとに steps の op 列を変える＝level_sep。
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    mode_s = str(mode)
    if mode_s not in _MODE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    simplified = sympy.expand(sympy.sympify(expr_str))
    r_srepr = sympy.srepr(simplified)
    r_disp = _fmt_poly_display(simplified)

    ops = _MODE_STEPS[mode_s]
    displays = [r_disp] if len(ops) == 1 else _linear_step_displays(expr_str, mode_s, r_disp)
    assert len(displays) == len(ops)
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=displays[i],
            narration=_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 代入と式の値（g1_l16.calculation Lv1/Lv2）— 式に数を代入して値（定数）を求める。
# 答えは数値（Integer/Rational）＝arithmetic 系と同じ定数答え。given の数値はすべて
# whitelist されるため G-Q5t は漏洩しない（narration に数字を書かない）。
# ---------------------------------------------------------------------------
_SUBSTITUTE_STEPS: dict[str, list[str]] = {
    # g1_l16 Lv1 正の数を代入
    "substitute_positive": ["substitute_value", "compute_value"],
    # g1_l16 Lv2 負の数・累乗を代入（符号・かっこに注意）
    "substitute_signed": ["substitute_with_parentheses", "evaluate_powers", "compute_value"],
}

_SUBSTITUTE_NARRATION: dict[str, str] = {
    "substitute_value": "式の文字に、代入する数をあてはめる。",
    "compute_value": "あてはめた式を計算して、式の値を求める。",
    "substitute_with_parentheses": "負の数を代入するときは、かっこをつけて文字とおきかえる。",
    "evaluate_powers": "累乗はかっこの中の数をその回数だけかけ合わせ、符号に注意して計算する。",
}

def _term_wise_display(expr_str: str, render_rest: object) -> str:
    """項ごとに「係数 × （文字の部分）」で書く（`2 × (-8)² - 2 × (-8)`）。

    **× を省かない。** 省くと `6x` に `x=9` を入れた式が `69` になる（実際そうなっていた）。
    `render_rest` は文字の部分の書き方（代入したまま／累乗まで計算した値）。
    """
    pieces: list[str] = []
    for term in _terms_in_written_order(expr_str):
        coeff, rest = term.as_coeff_Mul()
        body = fmt_number(abs(coeff))
        if rest != 1:
            body += f" × {render_rest(rest)}"  # type: ignore[operator]
        pieces.append(("-" if coeff < 0 else "+") + body)
    out = pieces[0].removeprefix("+")
    for piece in pieces[1:]:
        out += f" {piece[0]} {piece[1:]}"
    return out


def _paren_if_negative(v: sympy.Expr) -> str:
    return f"({fmt_number(v)})" if v < 0 else fmt_number(v)


def _substituted_display(expr_str: str, var: sympy.Symbol, val: sympy.Rational) -> str:
    """文字を数におきかえた式（`2 × (-8)² - 2 × (-8)`）。

    `subs` で数を入れると sympy が計算してしまうので、**値の文字列を名前にした記号**
    に置きかえて表示だけ作る。負の数はかっこをつける（教科書のきまり）。
    """
    placeholder = sympy.Symbol(_paren_if_negative(val))
    return _term_wise_display(expr_str, lambda rest: fmt_expr(rest.subs(var, placeholder)))


def _powers_evaluated_display(
    expr_str: str, var: sympy.Symbol, val: sympy.Rational
) -> str:
    """累乗だけ計算した形（`2 × 64 - 2 × (-8)`）。"""
    return _term_wise_display(expr_str, lambda rest: _paren_if_negative(rest.subs(var, val)))


@register_solver("math.evaluate_substitution")
def evaluate_substitution(expr_str: str, subs_str: object, mode: object) -> Solution:
    """式に数を代入して式の値（定数）を求める（g1_l16.calculation Lv1/Lv2）。

    expr_str（変数を含む式）と subs_str（"x=-3" 形の代入条件・単一変数）だけから
    sympy で代入・厳密評価する（double-solve）。答えは数値（Integer/Rational）。
    mode ごとに steps の op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _SUBSTITUTE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    var_s, val_s = str(subs_str).split("=")
    var = sympy.Symbol(var_s.strip())
    val = sympy.Rational(sympy.sympify(val_s.strip(), rational=True))
    result = sympy.sympify(expr_str).subs(var, val)
    if not result.is_number:
        raise ValueError(f"数値に評価されない代入結果: {expr_str!r} [{subs_str!r}] -> {result!r}")
    r_srepr = sympy.srepr(result)
    r_disp = fmt_number(result)

    ops = _SUBSTITUTE_STEPS[mode_s]
    displays = {
        "substitute_value": _substituted_display(expr_str, var, val),
        "substitute_with_parentheses": _substituted_display(expr_str, var, val),
        "evaluate_powers": _powers_evaluated_display(expr_str, var, val),
        "compute_value": r_disp,
    }
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=displays[op],
            narration=_SUBSTITUTE_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 乗法・除法の表し方のきまり（g1_l13/l14.calculation）— 単項式の積・商を記法規則に
# 従って簡潔に表す（簡約表示）。答えは式（自由変数を含む SymbolicAnswer）。与式（× ÷ を
# 明示した未簡約の積・商）と答え（記号を省いた簡約形）は別表記なので display 全体一致でのみ
# 漏洩検査され G-Q5t は相対安全（記号 × ÷ を含む与式に、それらを含まない答えが部分文字列で
# 現れることは構造上ない）。narration には数字を書かない。
# ---------------------------------------------------------------------------
_NOTATION_STEPS: dict[str, list[str]] = {
    # g1_l13 Lv1 乗法の表し方（×省略・数を前に）
    "product_basic": ["apply_product_rule"],
    # g1_l13 Lv2 累乗・複数文字（同じ文字の積を累乗にまとめる手が増える）
    "product_powers": ["apply_product_rule", "combine_powers"],
    # g1_l14 Lv1 除法の表し方（÷を分数の形に）
    "quotient_basic": ["rewrite_as_fraction"],
    # g1_l14 Lv2 乗除混合（乗法部を先にまとめてから1つの分数に）
    "quotient_mixed": ["collect_numerator", "rewrite_as_fraction"],
}

_NOTATION_NARRATION: dict[str, str] = {
    "apply_product_rule": "数を文字の前に書き、乗法の記号 × を省いて表す。",
    "combine_powers": "同じ文字の積は、累乗の指数を使ってまとめる。",
    "rewrite_as_fraction": "除法の記号 ÷ を使わず、分数の形で表す。",
    "collect_numerator": "乗法の部分を先にまとめてから、分数の形に表す。",
}

def _notation_step_displays(expr_str: str, mode: str, final: str) -> list[str]:
    """記法のきまりの各手の括弧に入れる表示（最後は答え）。"""
    if mode == "product_powers":
        # × を省いて数を前に出しただけの形（同じ文字はまだ累乗にまとめない）。
        factors = [sympy.sympify(t) for _op, t in top_level_parts(expr_str, "*")]
        numbers = [f for f in factors if f.is_number]
        letters = [f for f in factors if not f.is_number]
        head = "".join(fmt_expr(n) for n in numbers)
        return [head + "".join(fmt_expr(s) for s in letters), final]
    if mode == "quotient_mixed":
        # 乗法の部分（分子）をまとめた形。
        num, _den = expr_str.rsplit("/", 1)
        return [_fmt_monomial_display(sympy.sympify(num)), final]
    raise ValueError(f"途中の表示を組めない mode: {mode!r}")


@register_solver("math.simplify_notation")
def simplify_notation(expr_str: str, mode: object) -> Solution:
    """単項式の積・商を記法規則に従って簡潔に表す（g1_l13/l14.calculation）。

    与式の文字列（× を `*`・÷ を `/` にした未簡約の積・商）だけから sympy が正準化した
    単項式／分数を得る（double-solve）。答えの表示は `_fmt_monomial_display`（数を前・
    アルファベット順・累乗の上付き・÷は分数バー）で教材表記にする。mode ごとに steps の
    op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _NOTATION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    expr = sympy.sympify(expr_str)
    r_srepr = sympy.srepr(expr)
    r_disp = _fmt_monomial_display(expr)

    ops = _NOTATION_STEPS[mode_s]
    displays = [r_disp] if len(ops) == 1 else _notation_step_displays(expr_str, mode_s, r_disp)
    assert len(displays) == len(ops)
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=displays[i],
            narration=_NOTATION_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# knowledge 系（ChoiceAnswer・用語想起／解の判別）— C1 g1 数と式の残 knowledge セル。
# 答えはテキスト（数値トークンなし）＝G-Q5t 素通り（§7.7）。fact_id は根拠規則の識別子。
# 用語想起は「説明された対象の名称を選ぶ」型（concept で correct が変わる）。domain ごとに
# 用語集合を持ち、distractors は同 domain の他の用語（＝もっともらしい紛らわしい選択肢）。
# ---------------------------------------------------------------------------
_TERM_MAPS: dict[str, dict[str, str]] = {
    # g1_l17 文字式の用語（項・係数・次数・同類項）
    "letter": {"term": "項", "coefficient": "係数", "degree": "次数", "like_terms": "同類項"},
    # g1_l19 等式の用語（等式・左辺・右辺・両辺）
    "equality": {"equality": "等式", "lhs": "左辺", "rhs": "右辺", "both_sides": "両辺"},
    # g1_l21 方程式の用語（方程式・解）。distractors に紛らわしい文字式の用語を混ぜる。
    "equation": {"equation": "方程式", "solution": "解", "coefficient": "係数", "term": "項"},
    # g1_l2 正負の数の用語（絶対値・数直線・原点・符号）
    "number": {"absolute_value": "絶対値", "number_line": "数直線", "origin": "原点", "sign": "符号"},
    # g1_l20 不等号（以上/以下/未満/超 → 記号 ≧ ≦ < >）。用語想起の一種として、
    # 大小の関係（説明された phrase）に対応する不等号（＝名前の代わりに記号）を答える。
    "inequality": {"at_least": "≧", "at_most": "≦", "less_than": "<", "greater_than": ">"},
    # g1_l10 数の集合（自然数・整数）
    "number_set": {
        "natural_number": "自然数", "integer": "整数",
        "rational_number": "有理数", "positive_number": "正の数",
    },
    # g1_l7 累乗の用語（指数・底・累乗）
    "power": {"exponent": "指数", "base": "底", "power": "累乗"},
    # g1_l9 計算法則（交換・結合・分配法則）
    "laws": {"commutative": "交換法則", "associative": "結合法則", "distributive": "分配法則"},
    # g1_l11 素数まわりの用語（素数・合成数・素因数）
    "prime_concepts": {"prime": "素数", "composite": "合成数", "prime_factor": "素因数"},
    # g1_l60 近似値まわりの用語（近似値・誤差・有効数字）。g3_l22 でも再利用する。
    "approximation": {
        "approximation": "近似値", "error": "誤差", "significant_figures": "有効数字",
    },
    # g3_l14 平方根の用語（平方根・根号）。答えは漢字＝digit-free（鉄則①）。
    "square_root": {
        "square_root": "平方根", "radical_sign": "根号",
        "absolute_value": "絶対値", "square": "自乗",
    },
    # g3_l16 実数の分類の用語（有理数・無理数・循環小数）。
    "real_numbers": {
        "rational": "有理数", "irrational": "無理数", "repeating_decimal": "循環小数",
    },
    # g3_l24 2次方程式の用語（2次方程式・解）。答えは漢数字「二次方程式」で digit-free。
    "quadratic_terms": {
        "quadratic_equation": "二次方程式", "solution": "解",
        "linear_equation": "一次方程式", "coefficient": "係数",
    },
    # g3_l26 2次方程式 ax²+bx+c=0 の係数の対応（a・b・c）。答えは単一の文字＝digit-free。
    "quadratic_coefficient": {
        "coeff_a": "a", "coeff_b": "b", "coeff_c": "c",
    },
    # g3_l32 y=ax² まわりの用語（比例定数・関連する頂点/軸の用語を distractor として持つ）。
    "quadratic_function_terms": {
        "proportionality_constant": "比例定数", "vertex": "頂点", "axis_of_symmetry": "軸",
    },
    # g1_l28 関数まわりの用語（変数・関数・変域）。C4 g1 比例・反比例クラスタの導入回。
    "function_terms": {
        "variable": "変数", "function": "関数", "domain_range": "変域",
    },
    # g1_l29 比例の用語（比例・比例定数）。答えは漢字＝digit-free。
    "direct_proportion": {
        "proportion": "比例", "proportionality_constant": "比例定数",
        "inverse": "反比例", "function": "関数",
    },
    # g1_l33 反比例の用語（反比例・比例定数）。答えは漢字＝digit-free。
    "inverse_proportion": {
        "inverse_proportion": "反比例", "proportionality_constant": "比例定数",
        "proportion": "比例", "domain_of_x": "変域",
    },
    # g1_l59/g2_l51 確率まわりの用語（試行・確率・同様に確からしい）。答えは漢字＝digit-free。
    "probability_terms": {
        "trial": "試行", "probability": "確率", "equally_likely": "同様に確からしい",
    },
    # g1_l54 度数分布表の用語（階級・階級値・度数・階級の幅）。C11 データ・統計クラスタの導入回。
    "frequency_table_terms": {
        "class": "階級", "class_value": "階級値", "frequency": "度数", "class_width": "階級の幅",
    },
    # g1_l55 相対度数まわりの用語（相対度数・度数折れ線）。
    "relative_frequency_terms": {
        "relative_frequency": "相対度数", "frequency_polygon": "度数折れ線",
        "frequency": "度数", "class_value": "階級値",
    },
    # g1_l56 累積度数まわりの用語（累積度数・累積相対度数）。
    "cumulative_frequency_terms": {
        "cumulative_frequency": "累積度数", "cumulative_relative_frequency": "累積相対度数",
        "relative_frequency": "相対度数", "total_frequency": "総度数",
    },
    # g1_l57 代表値の用語（平均値・中央値・最頻値）。
    "representative_value_terms": {
        "mean": "平均値", "median": "中央値", "mode": "最頻値",
    },
    # g2_l55 四分位数の用語（第一/第二/第三四分位数・四分位範囲）。答えは漢数字＝digit-free。
    "quartile_terms": {
        "q1": "第一四分位数", "q2": "第二四分位数", "q3": "第三四分位数", "iqr": "四分位範囲",
    },
    # g2_l56 箱ひげ図の用語（箱の左端・中央の線・右端・両側のひげの先端）。答えは漢数字＝digit-free。
    "box_plot_terms": {
        "box_left": "第一四分位数", "box_center": "中央値", "box_right": "第三四分位数",
        "whisker_min": "最小値", "whisker_max": "最大値",
    },
    # g3_l57 標本調査の用語（全数調査・標本調査）。
    "survey_method_terms": {
        "census": "全数調査", "sample_survey": "標本調査",
        "random_sampling": "無作為抽出", "population": "母集団",
    },
    # g3_l58 標本の取り出し方の用語（母集団・標本・無作為抽出）。
    "sampling_terms": {
        "population": "母集団", "sample": "標本", "random_sampling": "無作為抽出",
    },
    # g1_l30 座標平面の用語（象限・原点）。答えは漢数字＝digit-free。
    "quadrant_terms": {
        "quadrant1": "第一象限", "quadrant2": "第二象限",
        "quadrant3": "第三象限", "quadrant4": "第四象限", "origin": "原点",
    },
    # g1_l37 直線・線分・半直線・角の用語（C7 平面図形クラスタの導入回）。
    "line_angle_terms": {
        "line": "直線", "segment": "線分", "ray": "半直線", "angle": "角",
    },
    # g1_l37/l43 垂線まわりの用語（垂線の足・点と直線の距離＝垂線の長さ）。
    "perpendicular_terms": {
        "foot": "垂線の足", "distance": "垂線の長さ",
        "perpendicular": "垂線", "midpoint": "中点",
    },
    # g1_l44 条件に対応する基本作図の用語（等距離の条件→使う基本作図）。
    "construction_choice_terms": {
        "equidistant_points": "垂直二等分線", "equidistant_sides": "角の二等分線",
        "perpendicular_line": "垂線", "circle": "円",
    },
    # g1_l45 円まわりの用語（半径・弦・弧・おうぎ形・中心角）。
    "circle_terms": {
        "radius": "半径", "chord": "弦", "arc": "弧",
        "sector": "おうぎ形", "central_angle": "中心角",
    },
    # g2_l31 対頂角・同位角・錯角の用語（C9 平行と合同クラスタの導入回）。
    "angle_pair_terms": {
        "vertical": "対頂角", "corresponding": "同位角", "alternate": "錯角",
    },
    # g2_l37 三角形の合同条件の用語（3辺相等・2辺夾角・1辺両端角）。
    "congruence_condition_terms": {
        "sss": "三辺がそれぞれ等しい",
        "sas": "二辺とその間の角がそれぞれ等しい",
        "asa": "一辺とその両端の角がそれぞれ等しい",
    },
    # **誤答は同じ domain の他の用語から作る**（`distractors = 他の値`）。
    # だから用語が2つしか無い domain は誤答が1つしか出ず、1つの domain
    # （similarity_terms）は**誤答が0個**で、必ず正解する問題になっていた。
    # 生成物を読んで見つけた（2026-08-16）。同じ種類の用語を足して、
    # どの用語想起も誤答が2つ以上になるようにする。
    # ここに足した語は family の concept_set に無いので、**問われることはなく
    # 誤答としてだけ使われる**（surface を書く必要がない）。
    # g2_l38 仮定・結論・反例の用語。
    "proof_logic_terms": {
        "assumption": "仮定", "conclusion": "結論", "counterexample": "反例",
    },
    # g3_l39 相似な図形の用語（対応する辺の長さの比＝相似比）。
    "similarity_terms": {
        "similarity_ratio": "相似比",
        "center_of_similarity": "相似の中心", "similar_position": "相似の位置",
        "corresponding_angle": "対応する角",
    },
    # C8 g1 空間図形クラスタ（g1_l47〜l50 の knowledge Lv1 用語想起）。
    # g1_l47 立体の名称（底面の形を明示しない一般名＋正多面体5種）。1レベル＝1 domain
    # なので、units の example が両方（角柱と正四面体）を問うのに合わせて1つにまとめる。
    "space_solid_terms": {
        "prism": "角柱", "pyramid": "角錐", "cylinder": "円柱", "cone": "円錐",
        "tetrahedron": "正四面体", "hexahedron": "正六面体", "octahedron": "正八面体",
        "dodecahedron": "正十二面体", "icosahedron": "正二十面体",
    },
    # g1_l48 空間内の2直線の位置関係の用語（平行・垂直・ねじれの位置）。
    "spatial_position_terms": {
        "parallel": "平行", "perpendicular": "垂直", "skew": "ねじれの位置",
    },
    # g1_l49 回転体まわりの用語（回転体・回転の軸・母線）。
    "rotation_solid_terms": {
        "rotation_solid": "回転体", "rotation_axis": "回転の軸", "generatrix": "母線",
    },
    # g1_l50 投影図まわりの用語（投影図・立面図・平面図）。
    "projection_terms": {
        "projection": "投影図", "front_view": "立面図", "top_view": "平面図",
    },
}

# domain 別の step テキスト（既定は g1_l17/l19/l21/l2 の現行文＝golden 不変）。
# inequality は答えが「用語の名前」でなく「記号」なので narration を専用化する。
_TERM_RECALL_STEP_TEXT_DEFAULT: dict[str, str] = {
    "s1_display": "",
    "s1_narration": "説明されている式や数の部分がどれかを読み取る。",
    "s2_narration": "その対象を表す用語の名前を思い出す。",
}
_TERM_RECALL_STEP_TEXT_BY_DOMAIN: dict[str, dict[str, str]] = {
    "inequality": {
        "s1_display": "",
        "s1_narration": "説明されている、数量の間の大小の関係を読み取る。",
        "s2_narration": "その関係を表す不等号の記号を思い出す。",
    },
    "quadratic_coefficient": {
        "s1_display": "",
        "s1_narration": "説明されている項が、2次方程式のどの位置（x²・x・定数項）にあるかを読み取る。",
        "s2_narration": "ax²+bx+c=0 の形と見比べて、その位置に対応する文字を思い出す。",
    },
    # C12 g3 標本調査: 説明の対象が「式や数の部分」ではなく**調べ方**なので専用化する。
    # 既定文のままだと「3200人の会員から一部を取り出して調べ、全体を推定する調査を
    # 何といいますか」に対して「説明されている**式や数の部分**がどれかを読み取る」と
    # 出ていた。本文に式も数式表現も無く、1手目が空回りしていた。
    "survey_method_terms": {
        "s1_display": "",
        "s1_narration": "全部を調べるのか、一部を取り出して全体を推定するのかを読み取る。",
        "s2_narration": "その調べ方を表す用語の名前を思い出す。",
    },
    "sampling_terms": {
        "s1_display": "",
        "s1_narration": "母集団・標本・取り出し方のうち、どれが説明されているかを読み取る。",
        "s2_narration": "その対象を表す用語の名前を思い出す。",
    },
    # C8 g1 空間図形: 説明の対象が「式や数の部分」ではなく立体・図なので専用化する。
    "space_solid_terms": {
        "s1_display": "",
        "s1_narration": "底面の形・側面の形・面の数など、説明されている立体の特徴を読み取る。",
        "s2_narration": "その特徴をもつ立体を表す用語の名前を思い出す。",
    },
    "spatial_position_terms": {
        "s1_display": "",
        "s1_narration": "空間の中で、2つの直線がどのように置かれているかを読み取る。",
        "s2_narration": "その位置関係を表す用語の名前を思い出す。",
    },
    "rotation_solid_terms": {
        "s1_display": "",
        "s1_narration": "平面図形を1回転させて立体をつくる場面のどの部分が説明されているかを読み取る。",
        "s2_narration": "その部分を表す用語の名前を思い出す。",
    },
    "projection_terms": {
        "s1_display": "",
        "s1_narration": "立体をどの向きから見てかいた図かを読み取る。",
        "s2_narration": "その図を表す用語の名前を思い出す。",
    },
}


@register_solver("math.term_recall_definition")
def term_recall_definition(concept: object, domain: object) -> Solution:
    """数と式まわりの用語の名称を答える（knowledge 用語想起・g1_l17/l19/l21/l2/l20 Lv1）。

    domain（用語の分野）と concept（説明されている対象）だけから名称／記号を判定する
    （具体例の値は無関係・double-solve）。答えは ChoiceAnswer（concept で correct が
    変わる用語想起型）。distractors は同 domain の他の用語。op 列は判別/verify 型と相異＝level_sep。
    """
    d = str(domain)
    c = str(concept)
    if d not in _TERM_MAPS:
        raise ValueError(f"未知の domain: {d!r}")
    names = _TERM_MAPS[d]
    if c not in names:
        raise ValueError(f"未知の concept: {c!r}（domain={d!r}）")
    correct = names[c]
    distractors = [v for k, v in names.items() if k != c]
    txt = _TERM_RECALL_STEP_TEXT_BY_DOMAIN.get(d, _TERM_RECALL_STEP_TEXT_DEFAULT)
    # **なぜその用語なのかを言う。** 1手目は括弧が空で産物が無く、2手目は
    # 「その対象を表す用語の名前を思い出す。（絶対値）」＝設問の言い直しだった。
    # 定義は解説にしか出ない `detail` に置く（narration はヒントに流れるので
    # 数字・記号を書けない・鉄則⑦）。表は `term_definitions.py`。
    read_target, definition = definition_for(d, c)
    steps = [
        Step(
            op="identify_description",
            args=[],
            result_srepr=c,
            result_display=read_target or txt["s1_display"],
            narration=txt["s1_narration"],
        ),
        Step(
            op="name_concept",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=txt["s2_narration"],
            detail=definition,
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id=f"{d}.term.{c}")
    return Solution(answer=answer, steps=steps)


@register_solver("math.verify_equation_solution")
def verify_equation_solution(equation_str: object, value: object) -> Solution:
    """ある値が方程式の解かどうかを代入して判別する（knowledge verify・g1_l21 Lv2）。

    方程式（"lhs=rhs"）と候補値だけから、代入して両辺が等しいかで判定する（double-solve）。
    答えは値で変わる verify 型の ChoiceAnswer。op 列は用語想起 Lv1 と相異＝level_sep。
    """
    lhs_s, rhs_s = str(equation_str).split("=")
    x = sympy.Symbol("x")
    v = sympy.Rational(sympy.sympify(str(value), rational=True))
    lhs_v = sympy.sympify(lhs_s, rational=True).subs(x, v)
    rhs_v = sympy.sympify(rhs_s, rational=True).subs(x, v)
    is_solution = bool(sympy.simplify(lhs_v - rhs_v) == 0)
    correct = "解である" if is_solution else "解ではない"
    other = "解ではない" if is_solution else "解である"
    steps = [
        Step(
            op="substitute_candidate",
            args=[],
            result_srepr=sympy.srepr(v),
            result_display=f"左辺 {fmt_number(lhs_v)}、右辺 {fmt_number(rhs_v)}",
            narration="候補の値を方程式の x にあてはめる。",
        ),
        Step(
            op="judge_solution",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="左辺と右辺の値が等しければ解、等しくなければ解ではない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="equation.verify_solution")
    return Solution(answer=answer, steps=steps)


@register_solver("math.compare_signed_numbers")
def compare_signed_numbers(a: object, b: object) -> Solution:
    """負の数を含む2数の大小を判別する（knowledge verify・g1_l2 Lv2）。

    2数（整数/分数/小数）だけから大小を比較する（double-solve）。答えは大きいほうの数
    （ChoiceAnswer・値で変わる verify 型）。2数は問題文（given）に現れ whitelist されるため
    G-Q5t は漏洩しない。narration には数字を書かない。
    """
    va = sympy.Rational(sympy.sympify(str(a), rational=True))
    vb = sympy.Rational(sympy.sympify(str(b), rational=True))
    if va == vb:
        raise ValueError(f"大小を判別できない（等しい）: {a!r} == {b!r}")
    larger, smaller = (va, vb) if va > vb else (vb, va)
    correct = fmt_number(larger)
    other = fmt_number(smaller)
    steps = [
        Step(
            op="compare_on_number_line",
            args=[],
            result_srepr=sympy.srepr(larger),
            result_display=f"{fmt_number(smaller)} より {fmt_number(larger)} が右",
            narration="2つの数を数直線上に置き、右にあるほうが大きいと考える。",
        ),
        Step(
            op="judge_larger",
            args=[],
            result_srepr=sympy.srepr(larger),
            result_display=correct,
            narration="負の数どうしでは、絶対値が大きいほど小さいことに注意して大きいほうを選ぶ。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="number.compare")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 規則・約束の想起（knowledge・ChoiceAnswer）— C1 g1 数と式の残 knowledge セル。
# 「説明ではなく規則そのもの（正しい記述）」を選ぶ型。term_recall（名称想起）と違い correct が
# 短い名称でなく規則の文（数字トークンを含まない）＝G-Q5t 素通り。distractors は同 topic の
# もっともらしい誤り記述。topic ごとに (concept -> (正しい記述, 誤り記述リスト)) を持つ。
# 移項(l22)を最初の顧客として、l3/l4/l5/l12/l15 の規則想起へ横展開できる汎用ソルバ。
# ---------------------------------------------------------------------------
_RULE_MAPS: dict[str, dict[str, tuple[str, list[str]]]] = {
    # g1_l3 加法（同符号・異符号の和の符号と絶対値の規則）
    "addition_sign": {
        "same_sign": (
            "共通の符号をそのままつけ、両方の数の絶対値の和を絶対値とする",
            [
                "絶対値の大きいほうの符号をつけ、両方の数の絶対値の差を絶対値とする",
                "いつでも正の符号をつけ、両方の数の絶対値の和を絶対値とする",
                "符号は消えてなくなり、両方の数の絶対値の差だけが残る",
            ],
        ),
        "different_sign": (
            "絶対値の大きいほうの符号をつけ、両方の数の絶対値の差を絶対値とする",
            [
                "共通の符号をそのままつけ、両方の数の絶対値の和を絶対値とする",
                "絶対値の小さいほうの符号をつけ、両方の数の絶対値の和を絶対値とする",
                "いつでも負の符号をつけ、両方の数の絶対値の差を絶対値とする",
            ],
        ),
    },
    # g1_l4 減法（ひき算をたし算に直す規則）
    "subtraction": {
        "to_addition": (
            "ひく数の符号を変えた数を、ひかれる数にたす計算になおす",
            [
                "ひかれる数の符号を変えた数を、ひく数にたす計算になおす",
                "2つの数の符号を両方とも変えて、たす計算になおす",
                "ひく数はそのままにして、記号だけを＋に変える",
            ],
        ),
    },
    # g1_l5 項（加法だけの式とみたときのそれぞれの数）
    "term_in_sum": {
        "definition": (
            "加法だけの式とみたとき、＋で結ばれているそれぞれの数のこと",
            [
                "式の中に出てくる数のうち、いちばん大きいものだけのこと",
                "計算した最後の答えになる数のこと",
                "かっこの中に書かれている数だけのこと",
            ],
        ),
    },
    # g1_l15 速さ・道のり・時間の関係（求める量ごとの式）
    "speed_relation": {
        "speed": (
            "（速さ）＝（道のり）÷（時間）",
            [
                "（速さ）＝（道のり）×（時間）",
                "（速さ）＝（時間）÷（道のり）",
                "（速さ）＝（道のり）＋（時間）",
            ],
        ),
        "distance": (
            "（道のり）＝（速さ）×（時間）",
            [
                "（道のり）＝（速さ）÷（時間）",
                "（道のり）＝（時間）÷（速さ）",
                "（道のり）＝（速さ）＋（時間）",
            ],
        ),
        "time": (
            "（時間）＝（道のり）÷（速さ）",
            [
                "（時間）＝（速さ）÷（道のり）",
                "（時間）＝（道のり）×（速さ）",
                "（時間）＝（速さ）＋（道のり）",
            ],
        ),
    },
    # g1_l12 文字を使った式（文字で数量を表すことの意味・利点）
    "letter_meaning": {
        "benefit": (
            "どんな数にもあてはまる数量の関係を、文字を使って一般的に表せること",
            [
                "計算をしなくても、答えがひとりでに求まること",
                "数を使わずに、図だけで数量を表せること",
                "文字は必ず整数だけを表すと決められること",
            ],
        ),
    },
    # g1_l6 積の符号（負の数の個数で決まる）
    "product_sign": {
        "even_count": (
            "負の数が偶数個のとき、積の符号は正になる",
            [
                "負の数が偶数個のとき、積の符号は負になる",
                "負の数が偶数個のときは、積の符号は数によって正にも負にもなる",
                "負の数が偶数個のとき、積の符号は決められない",
            ],
        ),
        "odd_count": (
            "負の数が奇数個のとき、積の符号は負になる",
            [
                "負の数が奇数個のとき、積の符号は正になる",
                "負の数が奇数個のときは、積の符号は数によって正にも負にもなる",
                "負の数が奇数個のとき、積の符号は決められない",
            ],
        ),
    },
    # g1_l8 逆数（除法を乗法に直す規則）
    "reciprocal": {
        "division_rule": (
            "ある数でわることは、その数の逆数をかけることと同じである",
            [
                "ある数でわることは、その数の符号を変えてかけることと同じである",
                "ある数でわることは、その数をそのままかけることと同じである",
                "ある数でわることは、その数を大きくしてかけることと同じである",
            ],
        ),
    },
    # g1_l13 乗法の記法規則（×省略・累乗）
    "notation_product_rule": {
        "omit_times": (
            "かけ算の記号 × を省き、数を文字の前に書く",
            [
                "かけ算の記号 × を省き、数を文字の後ろに書く",
                "かけ算の記号 × はそのまま残して書く",
                "かけ算の記号 × のかわりに ÷ を書く",
            ],
        ),
        "power": (
            "同じ文字の積は、指数を使って累乗の形で書く",
            [
                "同じ文字の積は、文字の個数を数字にして文字の後ろに書く",
                "同じ文字の積は、そのまま × でつないで書く",
                "同じ文字の積は、文字を大文字にして書く",
            ],
        ),
    },
    # g1_l14 除法の記法規則（÷を分数で表す）
    "notation_quotient_rule": {
        "as_fraction": (
            "わり算の記号 ÷ を使わず、分数の形で書く",
            [
                "わり算の記号 ÷ をそのまま残して書く",
                "わり算の記号 ÷ のかわりに × を書く",
                "わられる数を分母に、わる数を分子にして書く",
            ],
        ),
    },
    # g1_l22 移項（定義・符号が変わる理由）
    "transposition": {
        "definition": (
            "等式の一方の辺の項を、符号を変えて他方の辺に移すこと",
            [
                "等式の左辺と右辺を、そっくりそのまま入れかえること",
                "等式の両辺に同じ数をかけて、係数をそろえること",
                "かっこの前の数を、かっこの中の各項にかけてかっこを外すこと",
            ],
        ),
        "sign_reason": (
            "両辺に同じ数をたす・ひくという等式の性質を使っているから",
            [
                "移項するときは、必ず係数で両辺をわるから",
                "左辺と右辺は、いつでも反対の符号になる決まりだから",
                "移項では符号は変わらず、位置だけが入れかわるから",
            ],
        ),
    },
    # g3_l2 展開の意味（積の形→和の形）
    "expansion_meaning": {
        "definition": (
            "積の形の式を、かっこをはずして和の形に表すこと",
            [
                "和の形の式を、いくつかの因数の積の形に表すこと",
                "式の中の同類項をまとめて、項の数を減らすこと",
                "分母に根号のある式を、分母に根号のない形に直すこと",
            ],
        ),
    },
    # g3_l7 因数分解と展開の関係（逆の操作）
    "factorization_relation": {
        "relation": (
            "多項式を因数の積の形に表すことで、展開のちょうど逆にあたる操作",
            [
                "多項式のかっこをはずして和の形にする、展開と同じ操作",
                "分数の分母と分子に同じ数をかけて、大きさを変えずに表す操作",
                "式に数を代入して、その式の値を求める操作",
            ],
        ),
    },
    # g3_l15 平方根の大小（正の数では中の数の大小と一致）
    "sqrt_magnitude": {
        "rule": (
            "正の数では、根号の中の数が大きいほど、根号のついた数も大きい",
            [
                "正の数では、根号の中の数が大きいほど、根号のついた数は小さい",
                "根号のついた数は、中の数に関わらずすべて等しい",
                "根号の中の数が大きいほど、根号のついた数は0に近づく",
            ],
        ),
    },
    # g3_l3 乗法公式の識別（一般形・平方の公式・和と差の積のどれがそのまま使えるか）
    "multiplication_formula_choice": {
        "general_form": (
            "(x+a)(x+b) の一般の乗法公式がそのまま使える"
            "（かっこの中の数が異なり、たがいに反対の符号でもない）",
            [
                "自乗の公式（かっこの中の数が同じ形）を使う方が適している",
                "和と差の積の公式（かっこの中の数がたがいに反対の符号の形）を使う方が適している",
                "分配法則で項ごとにかけて整理するしかなく、公式は使えない",
            ],
        ),
        "perfect_square_form": (
            "自乗の公式（かっこの中の数が同じ形）を使う方が適している",
            [
                "(x+a)(x+b) の一般の乗法公式がそのまま使える",
                "和と差の積の公式（かっこの中の数がたがいに反対の符号の形）を使う方が適している",
                "分配法則で項ごとにかけて整理するしかなく、公式は使えない",
            ],
        ),
        "diff_of_squares_form": (
            "和と差の積の公式（かっこの中の数がたがいに反対の符号の形）を使う方が適している",
            [
                "(x+a)(x+b) の一般の乗法公式がそのまま使える",
                "自乗の公式（かっこの中の数が同じ形）を使う方が適している",
                "分配法則で項ごとにかけて整理するしかなく、公式は使えない",
            ],
        ),
    },
    # g3_l14 √(a²)=|a| の意味（a が負のときは -a になることに注意）
    "sqrt_square_meaning": {
        "abs_value_rule": (
            "a を自乗した数の平方根は、a の絶対値 |a| に等しい（a が負の数のときは -a になる）",
            [
                "a を自乗した数の平方根は、a にそのまま等しい（a が負の数のときも a のまま）",
                "a を自乗した数の平方根は、a を自乗した数そのものに等しい",
                "a を自乗した数の平方根は、a が負の数のときは求められない",
            ],
        ),
    },
    # g3_l28 2次方程式の解き方の選択（因数分解が適する形か、解の公式が適する形か）
    "quadratic_solving_method_choice": {
        "factoring_suitable": (
            "左辺が整数の範囲でそのまま因数分解できる形だから、因数分解を使う方がよい",
            [
                "左辺が整数の範囲では因数分解できない形だから、解の公式を使う方がよい",
                "つねに解の公式を使うのがよく、因数分解を考える必要はない",
                "係数に文字が含まれているから、まず移項してから考える必要がある",
            ],
        ),
        "formula_suitable": (
            "左辺が整数の範囲では因数分解できない形だから、解の公式を使う方がよい",
            [
                "左辺が整数の範囲でそのまま因数分解できる形だから、因数分解を使う方がよい",
                "つねに因数分解を使うのがよく、解の公式を考える必要はない",
                "係数に文字が含まれているから、まず移項してから考える必要がある",
            ],
        ),
    },
    # g3_l32 y=ax² の形の判別基準（x を自乗した項だけを比例定数倍した形かどうか）
    "quadratic_function_form": {
        "form_criterion": (
            "x を自乗した項だけがあり、それを比例定数倍した形（他の項をふくまない形）であること",
            [
                "x の項だけがあり、それを比例定数倍した形であること",
                "x を自乗した項に加えて、定数項や x の項をふくんでいてもよい形であること",
                "比例定数にあたる数が、つねに正の数である形であること",
            ],
        ),
    },
    # g3_l35 y=ax² の変化の割合の性質（1次関数と異なり区間ごとに変わる）
    "quadratic_roc_property": {
        "variability": (
            "一次関数とちがい、区間によって変化の割合が変わり、一定にならない",
            [
                "一次関数と同じように、区間によらず変化の割合はつねに一定である",
                "変化の割合は、比例定数の符号によらずつねに正になる",
                "変化の割合は、x の変域の位置によらず、つねに比例定数と等しくなる",
            ],
        ),
    },
    # g3_l33 y=ax² のグラフ（放物線）の性質：形と対称性／開く向き
    "parabola_property": {
        "shape_and_symmetry": (
            "放物線とよばれる曲線で、y 軸について対称であり、原点が頂点になる",
            [
                "原点を通る直線で、比例定数がその傾きになる",
                "x 軸について対称な曲線で、比例定数の値そのものが頂点になる",
                "双曲線とよばれる、たがいに離れた2つの部分に分かれた曲線になる",
            ],
        ),
        "opening_direction": (
            "比例定数が正のときは上に開き、負のときは下に開く",
            [
                "比例定数の符号によらず、つねに上に開く",
                "比例定数が正のときは下に開き、負のときは上に開く",
                "比例定数の符号ではなく、その絶対値の大きさで開く向きが決まる",
            ],
        ),
        "opening_width": (
            "比例定数の絶対値が大きいほど開き方はせまく、小さいほど開き方は広い",
            [
                "比例定数の絶対値が大きいほど開き方は広く、小さいほど開き方はせまい",
                "比例定数の絶対値によらず、開き方はどの放物線でも同じである",
                "比例定数が正か負かだけで開き方の広さが決まり、絶対値は関係しない",
            ],
        ),
    },
    # g2_l54 余事象（あることがらが起こらない確率）の意味
    "complementary_event": {
        "definition": (
            "全体を表す確率から、あることがらの起こる確率をひいた値に等しい",
            [
                "あることがらの起こる確率に等しい",
                "あることがらの起こる確率と、全体を表す確率とをたした値に等しい",
                "あることがらの起こりやすさとは関係なく、つねに一定である",
            ],
        ),
    },
    # g2_l32 平行線の性質とその逆（同位角/錯角が等しいこと・その逆）
    "parallel_angle_property": {
        "property": (
            "二直線が平行ならば、同位角や錯角は等しい",
            [
                "二直線が平行ならば、同位角や錯角は足すと一直線の角(平角)になる",
                "二直線が平行であっても、同位角や錯角の大きさに決まった関係はない",
            ],
        ),
        "converse": (
            "同位角や錯角が等しければ、その二直線は平行である",
            [
                "同位角や錯角が等しくても、その二直線が平行であるとは限らない",
                "対頂角が等しければ、その二直線は平行である",
            ],
        ),
    },
    # g2_l33 三角形の内角の和・外角の性質
    "triangle_angle_properties": {
        "interior_sum": (
            "一直線の角(平角)に等しい",
            [
                "直角に等しい",
                "円一周の角に等しい",
            ],
        ),
        "exterior_property": (
            "それととなり合わない二つの内角の和に等しい",
            [
                "それととなり合う二つの内角の和に等しい",
                "三角形の内角の和から直角をひいた大きさに等しい",
            ],
        ),
    },
    # g2_l34 多角形の内角の和が(頂点の数より二少ない数)個の三角形に分かれる理由
    "polygon_interior_sum_reason": {
        "diagonal_from_vertex": (
            "一つの頂点からひける対角線によって、三角形に分けられるから",
            [
                "各辺の中点を結ぶ線分によって、三角形に分けられるから",
                "対角線をすべてひくことによって、三角形に分けられるから",
            ],
        ),
    },
    # g2_l35 多角形の外角の和が辺の数によらず一定であること
    "polygon_exterior_sum_property": {
        "constant": (
            "どんな多角形であっても常に一定である",
            [
                "辺の数が多いほど大きくなる",
                "辺の数が多いほど小さくなる",
            ],
        ),
    },
    # g2_l37 三角形の合同条件（3つすべてを想起する）
    "congruence_conditions": {
        "all_three": (
            "三組の辺がそれぞれ等しい、二組の辺とその間の角がそれぞれ等しい、"
            "一組の辺とその両端の角がそれぞれ等しい、のいずれか",
            [
                "三組の辺がそれぞれ等しい、三組の角がそれぞれ等しい、"
                "一組の辺とその両端の角がそれぞれ等しい、のいずれか",
                "三組の辺がそれぞれ等しい、二組の辺とその間の角がそれぞれ等しい、"
                "二組の辺がそれぞれ等しい、のいずれか",
            ],
        ),
    },
    # g2_l41 二等辺三角形の性質（底角が等しい）
    "isosceles_property": {
        "base_angles_equal": (
            "底角の大きさは等しい",
            [
                "頂角と底角の大きさは等しい",
                "底角の大きさの和が頂角に等しい",
            ],
        ),
    },
    # g2_l42 二等辺三角形になるための条件（2角が等しい）
    "isosceles_condition": {
        "two_angles_equal": (
            "二つの角が等しい",
            [
                "三つの角がすべて異なる",
                "一つの角が直角である",
            ],
        ),
    },
    # g2_l43 正三角形の性質（3辺/3角が等しい）
    "equilateral_property": {
        "all_equal": (
            "三つの辺の長さも三つの内角の大きさも、すべて等しい",
            [
                "三つの辺の長さは等しいが、内角の大きさはそれぞれ異なる",
                "内角の大きさは等しいが、辺の長さはそれぞれ異なる",
            ],
        ),
    },
    # g2_l44 直角三角形の合同条件（2つとも想起する）
    "right_triangle_congruence_conditions": {
        "both": (
            "斜辺と一つの鋭角がそれぞれ等しい、または、斜辺と他の一辺がそれぞれ等しい、のいずれか",
            [
                "斜辺と一つの鋭角がそれぞれ等しい、または、一つの鋭角と他の一辺が"
                "それぞれ等しい、のいずれか",
                "斜辺の長さがそれぞれ等しい、または、斜辺と他の一辺がそれぞれ等しい、"
                "のいずれか",
            ],
        ),
    },
    # g2_l46 平行四辺形の性質（対辺・対角が等しい、対角線が中点で交わる）
    "parallelogram_property": {
        "all": (
            "対辺の長さはそれぞれ等しく、対角の大きさもそれぞれ等しい。また、対角線はそれぞれの中点で交わる",
            [
                "対辺の長さは異なるが、対角の大きさはそれぞれ等しい",
                "対角線はそれぞれの中点で交わるが、直角に交わる",
            ],
        ),
    },
    # g2_l47 平行四辺形になるための条件（5つとも想起する）
    "parallelogram_conditions": {
        "all_five": (
            "二組の対辺がそれぞれ平行である、二組の対辺の長さがそれぞれ等しい、"
            "二組の対角の大きさがそれぞれ等しい、対角線がそれぞれの中点で交わる、"
            "一組の対辺が平行でその長さが等しい、のいずれか",
            [
                "二組の対辺がそれぞれ平行である、二組の対辺の長さがそれぞれ等しい、"
                "二組の対角の大きさがそれぞれ等しい、対角線の長さが等しい、"
                "一組の対辺が平行でその長さが等しい、のいずれか",
                "二組の対辺がそれぞれ平行である、二組の対辺の長さがそれぞれ等しい、"
                "二組の対角の大きさがそれぞれ等しい、対角線がそれぞれの中点で交わる、"
                "一組の対辺が平行である、のいずれか",
            ],
        ),
    },
    # g2_l49 特別な平行四辺形の対角線の性質（形ごとに想起する）
    "special_parallelogram_diagonal_property": {
        "rectangle": (
            "対角線の長さが等しい",
            ["対角線が垂直に交わる", "対角線の長さが異なる"],
        ),
        "rhombus": (
            "対角線が垂直に交わる",
            ["対角線の長さが等しい", "対角線が平行である"],
        ),
        "square": (
            "対角線の長さが等しく、かつ垂直に交わる",
            ["対角線の長さは等しいが垂直には交わらない", "対角線は垂直に交わるが長さは異なる"],
        ),
    },
    # g2_l50 等積変形（共通の底辺・等しい高さの三角形は面積が等しい）
    "equal_area_triangles": {
        "common_base_equal_height": (
            "面積は等しくなる",
            ["面積は頂点の位置によって変わる", "高さが同じでも底辺が異なれば面積は変わる"],
        ),
    },
    # g3_l51 三平方の定理の意味（斜辺の二乗＝他の2辺の二乗の和）
    "pythagorean_theorem": {
        "statement": (
            "斜辺の長さの二乗が、他の二辺の長さの二乗の和に等しい",
            [
                "斜辺の長さが、他の二辺の長さの和に等しい",
                "三辺の長さの二乗の和が、常に一定の値になる",
            ],
        ),
    },
    # g3_l52 三平方の定理の逆（成り立てば最も長い辺を斜辺とする直角三角形）
    "pythagorean_converse": {
        "statement": (
            "cを斜辺とする直角三角形である",
            [
                "aを斜辺とする直角三角形である",
                "cを斜辺とする二等辺三角形である",
            ],
        ),
    },
    # g3_l40 三角形の相似条件（3つすべてを想起する）
    "similarity_conditions": {
        "all_three": (
            "二組の角がそれぞれ等しい、二組の辺の比とその間の角がそれぞれ等しい、"
            "三組の辺の比がすべて等しい、のいずれか",
            [
                "二組の角がそれぞれ等しい、二組の辺の比がそれぞれ等しい、"
                "三組の辺の比がすべて等しい、のいずれか",
                "一組の角が等しい、二組の辺の比とその間の角がそれぞれ等しい、"
                "三組の辺の比がすべて等しい、のいずれか",
            ],
        ),
    },
    # g3_l42 平行線と線分の比の定理（AD:AB=AE:AC=DE:BC がすべて等しい）
    # 選択肢に点名が出るので `{a}`〜`{e}` の穴にしてある（_LABELED_RULE_TOPICS 参照）。
    "parallel_segment_ratio_theorem": {
        "statement": (
            "{a}{d}と{a}{b}の比、{a}{e}と{a}{c}の比、{d}{e}と{b}{c}の比が、すべて等しい",
            [
                "{a}{d}と{d}{b}の比、{a}{e}と{a}{c}の比が等しい",
                "{d}{e}の長さは、{b}{c}の長さから一定の数をひいた値に等しい",
            ],
        ),
    },
    # g3_l43 平行線と線分の比の定理の逆（AD:DB=AE:ECが成り立てばDE//BC）
    "parallel_segment_ratio_converse": {
        "statement": (
            "{d}{e}と{b}{c}が平行である",
            [
                "{d}{e}と{b}{c}が垂直に交わる",
                "三角形{a}{b}{c}と三角形{a}{d}{e}が合同である",
            ],
        ),
    },
    # g3_l44 中点連結定理（中点を結ぶ線分は残りの辺に平行でその半分の長さ）
    "midpoint_connector_theorem": {
        "statement": (
            "残りの辺に平行で、その長さは残りの辺の半分に等しい",
            [
                "残りの辺に垂直で、その長さは残りの辺に等しい",
                "残りの辺に平行で、その長さは残りの辺と等しい",
            ],
        ),
    },
    # g3_l45 相似な平面図形の面積比（相似比の二乗に等しい）
    "area_ratio_theorem": {
        "statement": (
            "相似比を二乗した比に等しい",
            [
                "相似比と同じ比に等しい",
                "相似比を二倍した比に等しい",
            ],
        ),
    },
    # g3_l46 相似な立体の体積比（相似比の三乗に等しい）
    "volume_ratio_theorem": {
        "statement": (
            "相似比を三乗した比に等しい",
            [
                "相似比を二乗した比に等しい",
                "相似比と同じ比に等しい",
            ],
        ),
    },
    # g3_l47 円周角の定理（円周角=中心角の半分・同じ弧の円周角はすべて等しい）
    "circle_inscribed_angle_theorem": {
        "statement": (
            "中心角の半分であり、同じ弧に対する円周角の大きさはすべて等しい",
            [
                "中心角と同じ大きさであり、同じ弧に対する円周角の大きさはそれぞれ異なる",
                "中心角の半分であるが、同じ弧に対する円周角の大きさはそれぞれ異なる",
            ],
        ),
    },
    # g3_l48 円周角の定理の逆（角が等しければ同じ円周上にある）
    "circle_inscribed_angle_converse": {
        "statement": (
            "四つの点は同じ円周上にある",
            [
                "四つの点は同じ直線上にある",
                "四つの点は同じ弧の上にある",
            ],
        ),
    },
    # g3_l50 円周角と弧の長さの比（弧の長さは円周角の大きさに比例する）
    "arc_angle_proportion": {
        "statement": (
            "弧の長さは、その弧に対する円周角の大きさに比例する",
            [
                "弧の長さは、その弧に対する円周角の大きさに反比例する",
                "弧の長さと円周角の大きさは無関係である",
            ],
        ),
    },
    # g1_l53 球の表面積・体積の公式（C8 g1 空間図形クラスタ）。答えは公式を言葉で
    # 述べた記述（漢数字のみ・ASCII 数字なし＝digit-free 鉄則①）。
    "sphere_formula": {
        "surface_area": (
            "半径の二乗に四とπをかけたもの",
            [
                "半径の二乗に二とπをかけたもの",
                "半径の三乗に四とπをかけたもの",
                "半径に四とπをかけたもの",
            ],
        ),
        "volume": (
            "半径の三乗に三分の四とπをかけたもの",
            [
                "半径の三乗に四とπをかけたもの",
                "半径の二乗に三分の四とπをかけたもの",
                "半径の三乗に三分の一とπをかけたもの",
            ],
        ),
    },
}


# ---------------------------------------------------------------------------
# 符号のついた数（g1_l1）— 正負の分類（Lv1・ChoiceAnswer）と、反対の性質をもつ量の符号表現
# （Lv2・数値答え）。分類の答えはテキスト（数字トークンなし）＝G-Q5t 素通り。符号表現の答えは
# 整数で、その絶対値は given（問題文の量の大きさ）に現れ両符号 whitelist されるため G-Q5t 安全。
# ---------------------------------------------------------------------------
@register_solver("math.classify_number_sign")
def classify_number_sign(value: object) -> Solution:
    """符号のついた数を正の数・負の数に分類する（knowledge classify・g1_l1 Lv1）。

    数（0 以外）だけからその符号で分類する（double-solve）。答えは ChoiceAnswer
    （正の数／負の数）。op 列は他の knowledge 型と相異＝level_sep。narration に数字は書かない。
    """
    v = sympy.Rational(sympy.sympify(str(value), rational=True))
    if v == 0:
        raise ValueError("0 は正の数でも負の数でもない（分類対象外）")
    correct = "正の数" if v > 0 else "負の数"
    other = "負の数" if v > 0 else "正の数"
    steps = [
        Step(
            op="read_number_sign",
            args=[],
            result_srepr=("+" if v > 0 else "-"),
            result_display=("+" if v > 0 else "-"),
            narration="数の前についている符号（＋か－か）を読み取る。",
        ),
        Step(
            op="classify_positive_negative",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="符号が＋なら正の数、－なら負の数と分類する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="number.classify_sign")
    return Solution(answer=answer, steps=steps)


# 反対の性質をもつ2量（pos は慣用的に正で表す向き・neg はその反対・unit は表示単位）。
# 一方を正で表すと約束したとき、反対の向きの量は反対の符号で表す（＝規則）。solver が正誤の
# 根拠を持ち、recipe は表示（単位つき場面文）に流用する。
# 反対の性質をもつ量の組。**値の大きさを教材の粒度に絞った分、組の数で広さを戻す。**
_OPPOSITE_PAIRS: list[tuple[str, str, str]] = [
    ("収入", "支出", "円"),
    ("得点", "失点", "点"),
    ("値上がり", "値下がり", "円"),
    ("増加", "減少", "人"),
    ("北へ", "南へ", "km"),
    ("東へ", "西へ", "km"),
    ("上がる", "下がる", "℃"),
    ("進む", "もどる", "m"),
    # 正にする側は、実物が正に取るほう（重い・多い）に合わせる。
    # 一度「軽い 2g」を +2g と表す形にしてしまい、向きが逆になっていた。
    ("重い", "軽い", "g"),
    ("多い", "少ない", "冊"),
    ("上昇", "下降", "m"),
    ("預ける", "引き出す", "円"),
    ("勝ち", "負け", "回"),
]


@register_solver("math.represent_opposite_quantity")
def represent_opposite_quantity(
    positive_label: object, asked_label: object, magnitude: object
) -> Solution:
    """反対の性質をもつ量を符号つきの数で表す（knowledge apply・g1_l1 Lv2）。

    「正で表す向き（positive_label）」「問われている量の向き（asked_label）」「大きさ（magnitude）」
    だけから、反対の向きには反対の符号をつける規則で符号つきの数を求める（double-solve）。
    positive_label と asked_label が同じ向きなら＋、反対の向きなら－。答えは符号つきの数の
    2択（ChoiceAnswer・＋か－か＝符号の判断が学習点）。誤選択肢は符号を逆にした数。
    その絶対値は given の量の大きさに現れ両符号 whitelist されるため G-Q5t 安全。
    """
    pos = str(positive_label)
    asked = str(asked_label)
    mag = int(sympy.Integer(int(str(magnitude))))
    pair = next((pr for pr in _OPPOSITE_PAIRS if pos in (pr[0], pr[1])), None)
    if pair is None:
        raise ValueError(f"未知の向き: {pos!r}")
    partner = pair[1] if pos == pair[0] else pair[0]
    if asked == pos:
        sign = 1
    elif asked == partner:
        sign = -1
    else:
        raise ValueError(f"asked_label が pair に無い: {asked!r}（pair={pair!r}）")
    val = sympy.Integer(sign * mag)
    correct = f"+{val}" if val > 0 else str(val)
    other_val = -val
    other = f"+{other_val}" if other_val > 0 else str(other_val)
    steps = [
        Step(
            op="identify_base_direction",
            args=[],
            result_srepr=pos,
            result_display=str(pos),
            narration="どちらの向き（性質）を正の数で表すことにしたかを読み取る。",
        ),
        Step(
            op="assign_opposite_sign",
            args=[],
            result_srepr=sympy.srepr(val),
            result_display=correct,
            # **同じ向きの量にも「反対の符号をつける」と言っていた。**
            # 「値上がりを正の数で表す」場面で「値上がり2300円」を問われたとき、
            # 答えは +2300（同じ向き）なのに、解説は「反対の向きの量には反対の
            # 符号をつけて表す」と、この問題に当てはまらないことを言っていた。
            narration=(
                "正の数で表すことにした向きと同じ向きの量なので、そのまま + をつけて表す。"
                if sign > 0
                else "正の数で表すことにした向きと反対の向きの量なので、- をつけて表す。"
            ),
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="number.opposite_quantity")
    return Solution(answer=answer, steps=steps)


# 数の集合が四則で閉じているか（g1_l10 Lv2）。set×operation の真偽表（自然数は減法・除法で
# 閉じておらず、整数は除法で閉じていない）。答えはテキスト（数字トークンなし）＝G-Q5t 素通り。
_SET_CLOSURE: dict[tuple[str, str], bool] = {
    ("natural", "add"): True, ("natural", "sub"): False,
    ("natural", "mul"): True, ("natural", "div"): False,
    ("integer", "add"): True, ("integer", "sub"): True,
    ("integer", "mul"): True, ("integer", "div"): False,
}


@register_solver("math.judge_set_closure")
def judge_set_closure(number_set: object, operation: object) -> Solution:
    """数の集合が四則演算について閉じているかを判別する（knowledge verify・g1_l10 Lv2）。

    集合（natural/integer）と演算（add/sub/mul/div）だけから、結果が必ずその集合に入るか
    （閉じているか）を真偽表で判定する（double-solve）。答えは ChoiceAnswer（閉じている／
    閉じていない）。op 列は用語想起 Lv1 と相異＝level_sep。narration に数字は書かない。
    """
    s = str(number_set)
    o = str(operation)
    if (s, o) not in _SET_CLOSURE:
        raise ValueError(f"未知の (集合, 演算): {(s, o)!r}")
    closed = _SET_CLOSURE[(s, o)]
    correct = "閉じている" if closed else "閉じていない"
    other = "閉じていない" if closed else "閉じている"
    steps = [
        Step(
            op="check_operation_result",
            args=[],
            result_srepr=f"{s}.{o}",
            result_display=("いつでも入る" if closed else "入らない場合がある"),
            narration="その集合の数どうしでその演算をした結果が、いつでもその集合に入るかを調べる。",
        ),
        Step(
            op="judge_closure",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="結果がいつでもその集合に入るなら閉じている、そうでなければ閉じていないと判断する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id=f"number_set.closure.{s}.{o}")
    return Solution(answer=answer, steps=steps)


# 有効数字の桁数（g1_l60 knowledge Lv2）— 測定値の有効数字が何けたかを判別する。
# 答えは漢数字の「○けた」（ASCII 数字を含まない）＝G-Q5t 素通り（§7.7・鉄則①）。
_SIGFIG_KANJI: dict[int, str] = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}


def _count_significant_figures(measurement: str) -> int:
    """小数表記の測定値の有効数字の桁数を数える。

    前提: 測定値は小数点を含み、小数部の末尾0も有効（例 "3.50"→3・"0.0280"→3・"4.005"→4）。
    先頭の0（位取りの0）は有効数字に数えない。
    """
    s = measurement.strip().lstrip("+-").replace(".", "")
    stripped = s.lstrip("0")
    if not stripped:
        raise ValueError(f"有効数字が数えられない測定値: {measurement!r}")
    return len(stripped)


@register_solver("math.count_significant_figures")
def count_significant_figures(measurement: object) -> Solution:
    """測定値の有効数字が何けたかを判別する（knowledge 判別・g1_l60 Lv2）。

    測定値の表記（小数）だけから有効数字の桁数を数える（double-solve）。答えは ChoiceAnswer
    （「三けた」など漢数字＝ASCII 数字なし）。誤選択肢は前後の桁数。op 列は用語想起 Lv1 と
    相異＝level_sep。narration に数字は書かない。
    """
    m = str(measurement)
    count = _count_significant_figures(m)
    if count not in _SIGFIG_KANJI:
        raise ValueError(f"対応範囲外の桁数: {count}")
    correct = f"{_SIGFIG_KANJI[count]}けた"
    distractor_counts = [c for c in (count - 1, count + 1) if c in _SIGFIG_KANJI]
    distractors = [f"{_SIGFIG_KANJI[c]}けた" for c in distractor_counts]
    steps = [
        Step(
            op="find_first_significant_digit",
            args=[],
            result_srepr=f"sigfig:{count}",
            result_display=next(ch for ch in m if ch.isdigit() and ch != "0"),
            narration="左から見て、最初の0でない数字が有効数字の始まりである（位取りの0は数えない）。",
        ),
        Step(
            op="count_significant_digits",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="そこから末尾までの数字の個数を数える（小数点以下の末尾の0も有効数字に含める）。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id="approximation.significant_figures")
    return Solution(answer=answer, steps=steps)


@register_solver("math.interpret_expression")
def interpret_expression(item_a: object, item_b: object) -> Solution:
    """与えられた文字式が表す数量の意味を解釈する（knowledge 判別・g1_l12 Lv2）。

    場面は「1個 x 円の item_a を a 個、1個 y 円の item_b を b 個買った」で式は a·x+b·y に固定。
    品名（item_a, item_b）だけから、式が表す意味の正しい記述を選ぶ（double-solve）。
    答えは ChoiceAnswer（品名で記述するため ASCII 数字トークンを含まず G-Q5t 素通り）。
    誤選択肢は「単価の和(x+y)」「個数の和」「代金の差」の混同。
    """
    a = str(item_a)
    b = str(item_b)
    correct = f"買った{a}全部の代金と、買った{b}全部の代金を合わせた金額"
    d_unit = f"{a}と{b}をそれぞれひとつずつ買ったときの代金の合計"
    d_count = f"買った{a}と{b}の個数を合わせた数"
    d_diff = f"買った{a}全部の代金と、買った{b}全部の代金の差"
    steps = [
        Step(
            op="read_each_term_meaning",
            args=[],
            result_srepr="term_meaning",
            result_display=f"{a}の代金と{b}の代金",
            narration=(
                "式の各項は、買った個数にひとつあたりの値段をかけた「代金」を表すことを読み取る。"
            ),
        ),
        Step(
            op="combine_term_meanings",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="項どうしが和で結ばれているので、式全体は代金の合計を表すと判断する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct,
        distractors=[d_unit, d_count, d_diff],
        fact_id="letter_meaning.interpret_expression",
    )
    return Solution(answer=answer, steps=steps)


# 選択肢に点名が出る topic。記述は `{a}`〜`{e}` の穴を持ち、問題文の点名で埋める。
# **問題文の点名は recipe が引く**ので、ここを固定にすると「三角形KFDで…点Q, Cが」と
# 問うて「ADとABの比」と答えることになる（実際そうなっていた）。
_LABELED_RULE_TOPICS = frozenset(
    {"parallel_segment_ratio_theorem", "parallel_segment_ratio_converse"}
)


def _rule_points(labels: object) -> dict[str, str]:
    """`{a}`〜`{e}` に入れる点名（A,B,C,D,E の順）。無ければ既定。"""
    s = str(labels or "ABCDE")
    if len(s) < 5:
        s = "ABCDE"
    return {"a": s[0], "b": s[1], "c": s[2], "d": s[3], "e": s[4]}


@register_solver("math.recall_rule_statement")
def recall_rule_statement(topic: object, concept: object, labels: object = None) -> Solution:
    """規則・約束の正しい記述を選ぶ（knowledge 規則想起・g1_l22 Lv1 ほか）。

    topic（規則の分野）と concept（問われている規則）だけから正しい記述を判定する
    （具体例の値は無関係・double-solve）。答えは ChoiceAnswer（concept で correct が変わる）。
    distractors は同 topic のもっともらしい誤り記述。op 列は用語想起／verify 型と相異＝level_sep。
    `labels` は問題文の点名で、選択肢の記号を問題文に合わせるためだけに使う
    （どれが正しい記述かの判定には効かない）。
    """
    t = str(topic)
    c = str(concept)
    if t not in _RULE_MAPS:
        raise ValueError(f"未知の topic: {t!r}")
    rules = _RULE_MAPS[t]
    if c not in rules:
        raise ValueError(f"未知の concept: {c!r}（topic={t!r}）")
    correct, distractors = rules[c]
    if t in _LABELED_RULE_TOPICS:
        pts = _rule_points(labels)
        correct = correct.format(**pts)
        distractors = [d.format(**pts) for d in distractors]
    # **なぜそう言えるか・どこを間違えやすいかを言う。** 1手目は括弧が空、
    # 2手目は「その規則の正しい内容を思い出して選ぶ。（…）」＝設問の言い直しだった。
    # 表は `term_definitions.RULE_REASONS`（解説にしか出ない detail に置く）。
    rule_target, rule_reason = rule_reason_for(t, c)
    steps = [
        Step(
            op="read_rule_context",
            args=[],
            result_srepr=c,
            result_display=rule_target,
            narration="問題で問われている規則や約束が、何についてのものかを読み取る。",
        ),
        Step(
            op="recall_correct_rule",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その規則の正しい内容を思い出して選ぶ。",
            detail=rule_reason,
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=list(distractors), fact_id=f"{t}.rule.{c}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.classify_rational_irrational（g3_l16.knowledge Lv2）— 具体的な数が有理数か
# 無理数かを分類する（knowledge classify）。答えは ChoiceAnswer（数字トークンなし）。
# ---------------------------------------------------------------------------
@register_solver("math.classify_rational_irrational")
def classify_rational_irrational(value_str: object) -> Solution:
    """具体的な数（分数・小数・平方根・π など）を有理数・無理数に分類する（double-solve）。

    値の文字列だけから sympy の厳密判定（is_rational）で分類する。小数リテラルは
    `rational=True` で厳密な Rational として解析する（Float は is_rational が
    None になり誤判定するため）。答えは ChoiceAnswer（有理数／無理数）。narration に
    数字は書かない。
    """
    expr = sympy.sympify(str(value_str), rational=True)
    is_rational = bool(expr.is_rational)
    correct = "有理数" if is_rational else "無理数"
    other = "無理数" if is_rational else "有理数"
    steps = [
        Step(
            op="evaluate_representability",
            args=[],
            result_srepr=("rational" if is_rational else "irrational"),
            result_display=("分数で表せる" if is_rational else "分数では表せない"),
            narration="その数が、整数を使った分数（p/q）の形で表せるかどうかを調べる。",
        ),
        Step(
            op="classify_rational_irrational",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="分数の形で表せれば有理数、表せなければ無理数と分類する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="real_numbers.classify")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.verify_quadratic_solution（g3_l24.knowledge Lv2）— ある値が2次方程式の解かどうかを
# 代入して判別する（knowledge verify）。答えは ChoiceAnswer（数字トークンなし）。
# ---------------------------------------------------------------------------
@register_solver("math.verify_quadratic_solution")
def verify_quadratic_solution(eq_str: object, value: object) -> Solution:
    """ある値が2次方程式の解かどうかを代入して判別する（double-solve）。

    方程式（"lhs=0"）と候補値だけから、代入して左辺が0になるかで判定する。答えは値で
    変わる verify 型の ChoiceAnswer。narration に数字は書かない。
    """
    lhs_s, rhs_s = str(eq_str).split("=")
    x = sympy.Symbol("x")
    v = sympy.Rational(sympy.sympify(str(value), rational=True))
    lhs_v = sympy.sympify(lhs_s, rational=True).subs(x, v)
    rhs_v = sympy.sympify(rhs_s, rational=True).subs(x, v)
    is_solution = bool(sympy.simplify(lhs_v - rhs_v) == 0)
    correct = "解である" if is_solution else "解ではない"
    other = "解ではない" if is_solution else "解である"
    steps = [
        Step(
            op="substitute_candidate",
            args=[],
            result_srepr=sympy.srepr(v),
            result_display=f"左辺 {fmt_number(lhs_v)}",
            narration="候補の値を2次方程式の x にあてはめる。",
        ),
        Step(
            op="judge_solution",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="左辺の値が0になれば解、0にならなければ解ではない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="quadratic.verify_solution")
    return Solution(answer=answer, steps=steps)


__all__ = [
    "evaluate_letter_expression",
    "evaluate_substitution",
    "simplify_notation",
    "term_recall_definition",
    "verify_equation_solution",
    "compare_signed_numbers",
    "classify_number_sign",
    "represent_opposite_quantity",
    "judge_set_closure",
    "recall_rule_statement",
    "classify_rational_irrational",
    "verify_quadratic_solution",
]
