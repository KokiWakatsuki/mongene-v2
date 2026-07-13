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


__all__ = [
    "evaluate_letter_expression",
    "evaluate_substitution",
    "simplify_notation",
    "term_recall_definition",
    "verify_equation_solution",
    "compare_signed_numbers",
]
