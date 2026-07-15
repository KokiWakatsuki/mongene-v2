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
from engine.packs.math.solvers.arithmetic import fmt_number
from engine.packs.math.solvers.polynomial import _fmt_monomial_display, _fmt_poly_display

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

# op -> 非終端 step の result_display フレーズ（数字を書かない）。
_OP_PHRASE: dict[str, str] = {
    "group_like_terms": "同類項どうしをまとめる",
    "remove_parentheses": "符号に注意してかっこを外す",
    "distribute_multiplication": "かっこの前の数を各項にかける",
    "convert_division_to_multiplication": "÷ を逆数のかけ算に直す",
}


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

_SUBSTITUTE_PHRASE: dict[str, str] = {
    "substitute_value": "文字に数をあてはめる",
    "substitute_with_parentheses": "かっこをつけて文字を数におきかえる",
    "evaluate_powers": "累乗を符号に注意して計算する",
}


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
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=r_disp if i == len(ops) - 1 else _SUBSTITUTE_PHRASE.get(op, ""),
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

_NOTATION_PHRASE: dict[str, str] = {
    "apply_product_rule": "数を前にして × を省く",
    "collect_numerator": "乗法の部分をまとめる",
}


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
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=r_disp if i == len(ops) - 1 else _NOTATION_PHRASE.get(op, ""),
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
    "number_set": {"natural_number": "自然数", "integer": "整数"},
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
    "square_root": {"square_root": "平方根", "radical_sign": "根号"},
    # g3_l16 実数の分類の用語（有理数・無理数・循環小数）。
    "real_numbers": {
        "rational": "有理数", "irrational": "無理数", "repeating_decimal": "循環小数",
    },
    # g3_l24 2次方程式の用語（2次方程式・解）。答えは漢数字「二次方程式」で digit-free。
    "quadratic_terms": {"quadratic_equation": "二次方程式", "solution": "解"},
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
    "direct_proportion": {"proportion": "比例", "proportionality_constant": "比例定数"},
    # g1_l33 反比例の用語（反比例・比例定数）。答えは漢字＝digit-free。
    "inverse_proportion": {
        "inverse_proportion": "反比例", "proportionality_constant": "比例定数",
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
    },
    # g1_l56 累積度数まわりの用語（累積度数・累積相対度数）。
    "cumulative_frequency_terms": {
        "cumulative_frequency": "累積度数", "cumulative_relative_frequency": "累積相対度数",
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
    "survey_method_terms": {"census": "全数調査", "sample_survey": "標本調査"},
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
    },
    # g1_l44 条件に対応する基本作図の用語（等距離の条件→使う基本作図）。
    "construction_choice_terms": {
        "equidistant_points": "垂直二等分線", "equidistant_sides": "角の二等分線",
    },
    # g1_l45 円まわりの用語（半径・弦・弧・おうぎ形・中心角）。
    "circle_terms": {
        "radius": "半径", "chord": "弦", "arc": "弧",
        "sector": "おうぎ形", "central_angle": "中心角",
    },
}

# domain 別の step テキスト（既定は g1_l17/l19/l21/l2 の現行文＝golden 不変）。
# inequality は答えが「用語の名前」でなく「記号」なので narration を専用化する。
_TERM_RECALL_STEP_TEXT_DEFAULT: dict[str, str] = {
    "s1_display": "説明されている対象を読み取る",
    "s1_narration": "説明されている式や数の部分がどれかを読み取る。",
    "s2_narration": "その対象を表す用語の名前を思い出す。",
}
_TERM_RECALL_STEP_TEXT_BY_DOMAIN: dict[str, dict[str, str]] = {
    "inequality": {
        "s1_display": "説明されている数量の大小の関係を読み取る",
        "s1_narration": "説明されている、数量の間の大小の関係を読み取る。",
        "s2_narration": "その関係を表す不等号の記号を思い出す。",
    },
    "quadratic_coefficient": {
        "s1_display": "説明されている項が式のどの位置にあるかを読み取る",
        "s1_narration": "説明されている項が、2次方程式のどの位置（x²・x・定数項）にあるかを読み取る。",
        "s2_narration": "ax²+bx+c=0 の形と見比べて、その位置に対応する文字を思い出す。",
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
    steps = [
        Step(
            op="identify_description",
            args=[],
            result_srepr=c,
            result_display=txt["s1_display"],
            narration=txt["s1_narration"],
        ),
        Step(
            op="name_concept",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=txt["s2_narration"],
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
            result_display="候補の値を方程式の x に代入する",
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
            result_display="2数を数直線上の位置で比べる",
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
            result_display="数の前についている符号を読み取る",
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
_OPPOSITE_PAIRS: list[tuple[str, str, str]] = [
    ("収入", "支出", "円"),
    ("得点", "失点", "点"),
    ("値上がり", "値下がり", "円"),
    ("増加", "減少", "人"),
    ("北へ", "南へ", "km"),
    ("東へ", "西へ", "km"),
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
            result_display="どちらの向きを正の数で表すことにしたかを読み取る",
            narration="どちらの向き（性質）を正の数で表すことにしたかを読み取る。",
        ),
        Step(
            op="assign_opposite_sign",
            args=[],
            result_srepr=sympy.srepr(val),
            result_display=correct,
            narration="正の数で表す向きと反対の向きの量には、反対の符号をつけて表す。",
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
            result_display="その演算の結果が必ずその集合に入るかを調べる",
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
            result_display="左から最初の0でない数字を見つける",
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
            result_display="式の各項が表す数量を読み取る",
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


@register_solver("math.recall_rule_statement")
def recall_rule_statement(topic: object, concept: object) -> Solution:
    """規則・約束の正しい記述を選ぶ（knowledge 規則想起・g1_l22 Lv1 ほか）。

    topic（規則の分野）と concept（問われている規則）だけから正しい記述を判定する
    （具体例の値は無関係・double-solve）。答えは ChoiceAnswer（concept で correct が変わる）。
    distractors は同 topic のもっともらしい誤り記述。op 列は用語想起／verify 型と相異＝level_sep。
    """
    t = str(topic)
    c = str(concept)
    if t not in _RULE_MAPS:
        raise ValueError(f"未知の topic: {t!r}")
    rules = _RULE_MAPS[t]
    if c not in rules:
        raise ValueError(f"未知の concept: {c!r}（topic={t!r}）")
    correct, distractors = rules[c]
    steps = [
        Step(
            op="read_rule_context",
            args=[],
            result_srepr=c,
            result_display="問われている規則が何についてかを読み取る",
            narration="問題で問われている規則や約束が、何についてのものかを読み取る。",
        ),
        Step(
            op="recall_correct_rule",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その規則の正しい内容を思い出して選ぶ。",
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
            result_display="整数を使った分数の形で表せるかを調べる",
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
            result_display="候補の値を方程式の x に代入する",
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
