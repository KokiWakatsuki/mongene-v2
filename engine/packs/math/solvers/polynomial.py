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

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
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


_SOLVE_FOR_VARIABLE_STEPS: dict[str, list[str]] = {
    "move_only": ["isolate_target"],
    "divide_coeff": ["isolate_target", "divide_by_coefficient"],
    "clear_and_divide": ["multiply_both_sides", "divide_by_coefficient"],
}


@register_solver("math.solve_for_variable")
def solve_for_variable(equation_str: str, target: object, mode: object) -> Solution:
    """等式を指定された文字について解く（g2_l9.calculation Lv1/2/3）。

    与式（equation_str="lhs=rhs"）と target だけから sympy.solve で解く（double-solve）。
    答えは「target = 解の式」（自由変数を含む symbolic）。mode ごとに steps の op 列を変える
    ＝level_sep:
      Lv1 "move_only"       : 移項のみ           [isolate_target]
      Lv2 "divide_coeff"    : 移項して係数でわる  [isolate_target, divide_by_coefficient]
      Lv3 "clear_and_divide": 分母を払って文字でわる [multiply_both_sides, divide_by_coefficient]
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    tvar = sympy.Symbol(str(target))
    lhs_s, rhs_s = equation_str.split("=")
    eq = sympy.Eq(sympy.sympify(lhs_s), sympy.sympify(rhs_s))
    sol_expr = sympy.solve(eq, tvar)[0]
    disp = f"{target} = {_fmt_poly_display(sol_expr)}"

    mode_s = str(mode)
    if mode_s not in _SOLVE_FOR_VARIABLE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    steps_ops = _SOLVE_FOR_VARIABLE_STEPS[mode_s]

    narrations = {
        "isolate_target": "解く文字の項だけを片方の辺に残すよう、ほかの項を移項する。",
        "divide_by_coefficient": "両辺を、解く文字にかかっている係数でわる。",
        "multiply_both_sides": "分母をなくすため、両辺に分母をかける。",
    }
    phrases = {
        "isolate_target": "ほかの項を移項する",
        "divide_by_coefficient": "解く文字の係数で両辺をわる",
        "multiply_both_sides": "両辺に分母をかける",
    }
    r_srepr = sympy.srepr(sol_expr)
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


@register_solver("math.express_number_property")
def express_number_property(expr_str: str) -> Solution:
    """数の性質を表す式の和を1つの式にまとめる（g2_l7.calculation Lv1）。

    与式の文字列（各数を表す式の和）だけから sympy.expand で整理する（double-solve）。
    steps は「かっこを外して和を書き出す」→「同類項をまとめる」の2手。答えは1つの式
    （自由変数を含む symbolic）。narration には数字を書かない。
    """
    expr = sympy.sympify(expr_str)
    simplified = sympy.expand(expr)
    disp = _fmt_poly_display(simplified)
    steps = [
        Step(
            op="expand_expression",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="かっこを外して和を書き出す",
            narration="それぞれの数を表す式の和を、かっこを外して書き出す。",
        ),
        Step(
            op="combine_like_terms",
            args=[],
            result_srepr=sympy.srepr(simplified),
            result_display=disp,
            narration="同類項をまとめて、1つの式にする。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(simplified), display=disp)
    return Solution(answer=answer, steps=steps)


@register_solver("math.combine_digit_number")
def combine_digit_number(expr_str: str, operation: object) -> Solution:
    """2けたの自然数とその位を入れかえた数の和・差を整理する（g2_l8.calculation Lv1）。

    与式（(10a+b)±(10b+a) の形）だけから sympy.expand で整理する（double-solve）。
    operation は steps の narration（和／差の語）に使うだけで、答えは expr_str のみから
    再計算する。答えは1つの式（自由変数を含む symbolic）。narration には数字を書かない。
    """
    expr = sympy.sympify(expr_str)
    simplified = sympy.expand(expr)
    disp = _fmt_poly_display(simplified)
    op_word = "差" if str(operation) == "difference" else "和"
    steps = [
        Step(
            op="express_swapped_number",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="もとの数と入れかえた数を文字式で書き出す",
            narration="もとの数と、位を入れかえた数を、それぞれ文字式で書き出す。",
        ),
        Step(
            op="combine_like_terms",
            args=[],
            result_srepr=sympy.srepr(simplified),
            result_display=disp,
            narration=f"2つの数の{op_word}を計算し、同類項をまとめて1つの式にする。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(simplified), display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# knowledge 系（ChoiceAnswer・用語想起／判別）— C2 の残 knowledge セル。
# 答えはテキスト（数値トークンなし）＝G-Q5t 素通り（§7.7）。fact_id は根拠規則の識別子。
# ---------------------------------------------------------------------------
_POLY_TERM_NAMES = {
    "monomial": "単項式",
    "polynomial": "多項式",
    "coefficient": "係数",
    "degree": "次数",
}


@register_solver("math.poly_term_definition")
def poly_term_definition(concept: object) -> Solution:
    """多項式まわりの用語（単項式・多項式・係数・次数）の名称を答える（knowledge・g2_l1 Lv1）。

    concept（説明されている対象）だけから名称を判定する（具体例の値は無関係・double-solve）。
    答えは ChoiceAnswer（concept で correct が変わる用語想起型）。op 列は判別 Lv2 と相異＝level_sep。
    """
    c = str(concept)
    if c not in _POLY_TERM_NAMES:
        raise ValueError(f"未知の concept: {c!r}")
    correct = _POLY_TERM_NAMES[c]
    distractors = [v for k, v in _POLY_TERM_NAMES.items() if k != c]
    steps = [
        Step(
            op="identify_description",
            args=[],
            result_srepr=c,
            result_display="説明されている対象を読み取る",
            narration="説明されている式や数の部分がどれかを読み取る。",
        ),
        Step(
            op="name_concept",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その対象を表す用語の名前を思い出す。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id=f"poly.term.{c}")
    return Solution(answer=answer, steps=steps)


@register_solver("math.classify_monomial_or_polynomial")
def classify_monomial_or_polynomial(expr_str: str) -> Solution:
    """式が単項式か多項式かを判別する（knowledge・g2_l1 Lv2）。

    与式の文字列だけから項の個数で判定する（single term＝単項式／和＝多項式・double-solve）。
    答えは式で変わる verify 型の ChoiceAnswer。op 列は用語想起 Lv1 と相異＝level_sep。
    """
    expr = sympy.expand(sympy.sympify(expr_str))
    is_poly = bool(expr.is_Add)
    correct = "多項式" if is_poly else "単項式"
    other = "単項式" if is_poly else "多項式"
    steps = [
        Step(
            op="count_terms",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display="式がいくつの項からできているかを見る",
            narration="式が、単独の項か、いくつかの項の和かを見分ける。",
        ),
        Step(
            op="classify_type",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="単独の項なら単項式、いくつかの項の和なら多項式である。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="poly.classify_type")
    return Solution(answer=answer, steps=steps)


@register_solver("math.judge_like_terms")
def judge_like_terms(term1: str, term2: str) -> Solution:
    """2つの項が同類項か（文字の部分が一致するか）を判別する（knowledge・g2_l2 Lv1）。

    2つの項の文字部分（係数を除いた部分）だけを比べて判定する（係数の値は無関係・double-solve）。
    答えは項の組で変わる verify 型の ChoiceAnswer。
    """
    v1 = sympy.sympify(term1).as_coeff_Mul()[1]
    v2 = sympy.sympify(term2).as_coeff_Mul()[1]
    same = bool(v1 == v2)
    correct = "同類項である" if same else "同類項ではない"
    other = "同類項ではない" if same else "同類項である"
    steps = [
        Step(
            op="compare_variable_parts",
            args=[],
            result_srepr=sympy.srepr(v1),
            result_display="2つの項の文字の部分を比べる",
            narration="2つの項の、文字の部分（文字と指数）が同じかどうかを比べる。",
        ),
        Step(
            op="judge_like_terms",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="文字の部分が同じなら同類項、ちがえば同類項ではない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="poly.like_terms")
    return Solution(answer=answer, steps=steps)


_SYSTEM_TERM_NAMES = {
    "two_var_eq": "2元1次方程式",
    "simultaneous": "連立方程式",
    "solution": "連立方程式の解",
}


@register_solver("math.system_term_definition")
def system_term_definition(concept: object) -> Solution:
    """連立方程式まわりの用語の名称を答える（knowledge・g2_l10 Lv1）。

    concept だけから名称を判定する（具体例の値は無関係・double-solve）。答えは ChoiceAnswer
    （concept で correct が変わる用語想起型）。op 列は既存 Lv2（解の判定 verify）と相異＝level_sep。
    """
    c = str(concept)
    if c not in _SYSTEM_TERM_NAMES:
        raise ValueError(f"未知の concept: {c!r}")
    correct = _SYSTEM_TERM_NAMES[c]
    distractors = [v for k, v in _SYSTEM_TERM_NAMES.items() if k != c]
    steps = [
        Step(
            op="identify_description",
            args=[],
            result_srepr=c,
            result_display="説明されている対象を読み取る",
            narration="説明されている方程式や値の組がどれかを読み取る。",
        ),
        Step(
            op="name_concept",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その対象を表す用語の名前を思い出す。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id=f"system.term.{c}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 多項式の展開（C3 g3_l1〜l6.calculation）— sympy.expand の1コア能力
#
# 与式（積・平方・分配の形の文字列）だけから sympy.expand で展開後の多項式を導く
# （double-solve）。答えは自由変数を含む式の SymbolicAnswer（G-Q5t は display 全体一致
# のみ検査＝積の形と展開形は構造が違うので漏洩しない）。mode ごとに steps の op 列を
# 変える＝level_sep（同一 family の Lv 間で op 列＝fp を相異させる）。narration に数字を
# 書かない。
# ---------------------------------------------------------------------------
_EXPAND_STEPS: dict[str, list[str]] = {
    # g3_l1 単項式×多項式・多項式÷単項式
    "distribute_mono": ["distribute_monomial"],
    "distribute_mono_combine": ["distribute_each_monomial", "combine_like_terms"],
    # g3_l2 多項式どうしの乗法
    "binomial_product": ["expand_all_products", "combine_like_terms"],
    "binomial_product_coeff": ["expand_all_products", "collect_x_terms", "combine_like_terms"],
    # g3_l3 乗法公式①（x+a)(x+b)
    "formula_sum_product": ["compute_sum_and_product", "write_expansion"],
    "formula_sum_product_signed": [
        "determine_constant_signs", "compute_sum_and_product", "write_expansion",
    ],
    # g3_l4 乗法公式②（x±a)²
    "square_binomial": ["compute_square_terms", "write_expansion"],
    "square_binomial_coeff": ["square_leading_term", "compute_cross_term", "write_expansion"],
    # g3_l5 乗法公式③（x+a)(x-a)
    "diff_of_squares": ["apply_diff_of_squares"],
    # g3_l6 いろいろな展開
    "expand_multi": ["expand_each_part", "combine_like_terms"],
    "expand_substitution": ["substitute_common_part", "apply_formula", "restore_expansion"],
    # g3_l13 証明で用いる式変形（(an+b)²-(cn+d)² 形・n² が相殺し1次式になる）
    "proof_diff_squares_linear": ["apply_diff_of_squares_formula", "simplify_result"],
}

_EXPAND_OP_NARRATION: dict[str, str] = {
    "distribute_monomial": "単項式を、かっこの中の各項にそれぞれかける。",
    "distribute_each_monomial": "それぞれの単項式を、対応するかっこの中の各項にかける。",
    "expand_all_products": "分配法則で、前のかっこの各項を後ろのかっこの各項にすべてかける。",
    "collect_x_terms": "文字の1次の項どうしを集める。",
    "combine_like_terms": "同類項をまとめて計算する。",
    "compute_sum_and_product": "2つの定数の和と積を求める。",
    "determine_constant_signs": "それぞれの定数の符号を確かめる。",
    "write_expansion": "乗法公式にあてはめて展開した式を書く。",
    "compute_square_terms": "はじめの項の平方・積の2倍・終わりの項の平方を求める。",
    "square_leading_term": "係数のついたはじめの項を平方する。",
    "compute_cross_term": "2つの項の積の2倍（中間の項）を求める。",
    "apply_diff_of_squares": "和と差の積の公式で、はじめの項の平方から終わりの項の平方をひく。",
    "expand_each_part": "それぞれのかっこを乗法公式で展開する。",
    "substitute_common_part": "共通する部分を1つの文字に置きかえる。",
    "apply_formula": "置きかえた式に乗法公式をあてはめる。",
    "restore_expansion": "置きかえをもとにもどして展開した式を整理する。",
    "apply_diff_of_squares_formula": "2つの平方の差を、和と差の積の形になおす。",
    "simplify_result": "積の形を計算し、式を簡単にする。",
}

_EXPAND_OP_PHRASE: dict[str, str] = {
    "distribute_each_monomial": "各単項式を分配する",
    "expand_all_products": "各項の積をすべて書き出す",
    "collect_x_terms": "1次の項を集める",
    "compute_sum_and_product": "和と積を求める",
    "determine_constant_signs": "定数の符号を確かめる",
    "compute_square_terms": "平方と積の2倍を求める",
    "square_leading_term": "はじめの項を平方する",
    "compute_cross_term": "中間の項を求める",
    "expand_each_part": "各かっこを展開する",
    "substitute_common_part": "共通部分を置きかえる",
    "apply_formula": "公式にあてはめる",
    "apply_diff_of_squares_formula": "和と差の積の形になおす",
}


@register_solver("math.expand_expression")
def expand_expression(expr_str: str, mode: object) -> Solution:
    """積・平方・分配の形の式を展開する（C3 g3_l1〜l6.calculation）。

    与式の文字列だけから sympy.expand で展開後の多項式を導く（recipe の構成内訳は見ない
    ・double-solve）。答えは展開後の多項式の SymbolicAnswer。mode ごとに steps の op 列を
    変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _EXPAND_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    expr = sympy.sympify(expr_str)
    expanded = sympy.expand(expr)
    disp = _fmt_monomial_display(expanded)
    srepr = sympy.srepr(expanded)

    ops = _EXPAND_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _EXPAND_OP_PHRASE.get(op, ""),
            narration=_EXPAND_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 多項式の因数分解（C3 g3_l7〜l11.calculation）— sympy.factor の1コア能力
#
# 与式（展開された多項式または (x+p)²-c² の形の文字列）だけから sympy.factor で
# 因数分解した形を導く（double-solve）。答えは自由変数を含む式の SymbolicAnswer
# （G-Q5t は display 全体一致のみ検査＝展開形と因数分解形は構造が違うので漏洩しない）。
# mode ごとに steps の op 列を変える＝level_sep。narration に数字を書かない。
# ---------------------------------------------------------------------------
_FACTOR_STEPS: dict[str, list[str]] = {
    # g3_l7 共通因数のくくり出し
    "factor_common": ["factor_out_common"],
    "factor_common_multi": ["identify_common_factor", "factor_out_common"],
    # g3_l8 乗法公式の逆①（x²+(a+b)x+ab）
    "factor_sum_product": ["find_two_numbers", "write_factors"],
    "factor_sum_product_signed": ["determine_signs", "find_two_numbers", "write_factors"],
    # g3_l9 平方の公式の逆
    "factor_perfect_square": ["recognize_perfect_square", "write_square"],
    # g3_l10 和と差の積の逆
    "factor_diff_squares": ["apply_diff_of_squares_factor"],
    # g3_l11 いろいろな因数分解
    "factor_common_then_formula": ["factor_out_common", "apply_formula"],
    "factor_substitution": ["substitute_common_part", "apply_formula_factor", "restore_factors"],
}

_FACTOR_OP_NARRATION: dict[str, str] = {
    "factor_out_common": "各項に共通する因数をかっこの外にくくり出す。",
    "identify_common_factor": "各項の係数と文字に共通する因数を見つける。",
    "find_two_numbers": "たすと1次の係数、かけると定数になる2つの数を見つける。",
    "determine_signs": "定数の符号から、2つの数の符号を決める。",
    "write_factors": "見つけた2つの数を使い、2つの1次式の積で表す。",
    "recognize_perfect_square": "はじめと終わりが平方で、中央が積の2倍になっていることを確かめる。",
    "write_square": "1次式の平方の形で表す。",
    "apply_diff_of_squares_factor": "平方の差を、和と差の積の形になおす。",
    "apply_formula": "くくり出した後のかっこの中を乗法公式の逆で因数分解する。",
    "substitute_common_part": "共通する部分を1つの文字に置きかえる。",
    "apply_formula_factor": "置きかえた式を公式の逆で因数分解する。",
    "restore_factors": "置きかえをもとにもどして整理する。",
}

_FACTOR_OP_PHRASE: dict[str, str] = {
    "identify_common_factor": "共通因数を見つける",
    "find_two_numbers": "2つの数を見つける",
    "determine_signs": "符号を決める",
    "recognize_perfect_square": "平方の形を確かめる",
    "factor_out_common": "共通因数をくくり出す",
    "substitute_common_part": "共通部分を置きかえる",
    "apply_formula_factor": "公式の逆で因数分解する",
}


@register_solver("math.factor_expression")
def factor_expression(expr_str: str, mode: object) -> Solution:
    """展開された多項式を因数分解する（C3 g3_l7〜l11.calculation）。

    与式の文字列だけから sympy.factor で因数分解した形を導く（recipe の構成内訳は見ない
    ・double-solve）。答えは因数分解後の式の SymbolicAnswer。mode ごとに steps の op 列を
    変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _FACTOR_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    expr = sympy.sympify(expr_str)
    factored = sympy.factor(expr)
    disp = _fmt_monomial_display(factored)
    srepr = sympy.srepr(factored)

    ops = _FACTOR_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _FACTOR_OP_PHRASE.get(op, ""),
            narration=_FACTOR_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 数値計算・式の値への工夫（C3 g3_l12.calculation）— 恒等式を使って直接値を求める
#
# 与えられた数値（Lv2: a,b／Lv3: s,p）だけから、恒等式を経由して答えの整数を導く
# （double-solve は独立に a²-b²／s²-2p を直接計算し .equals(0) で一致確認）。
# mode ごとに steps の op 列を変える＝level_sep。narration に数字を書かない。
#   Lv2 "diff_of_squares_arithmetic": a²-b² = (a+b)(a-b) を利用して工夫計算する。
#   Lv3 "symmetric_sum_of_squares"  : x+y=s, xy=p のとき x²+y²=(x+y)²-2xy=s²-2p。
#     x,y の実数解の有無は問わない（s,p という基本対称式の値のみから恒等式で導く）。
# ---------------------------------------------------------------------------
_ARITHMETIC_IDENTITY_STEPS: dict[str, list[str]] = {
    "diff_of_squares_arithmetic": ["factor_difference_of_squares", "multiply_factors"],
    "symmetric_sum_of_squares": [
        "express_via_elementary_symmetric", "substitute_and_compute",
    ],
}

_ARITHMETIC_IDENTITY_NARRATION: dict[str, str] = {
    "factor_difference_of_squares": "2つの数の平方の差を、和と差の積の形になおす。",
    "multiply_factors": "和と差の積を計算し、値を求める。",
    "express_via_elementary_symmetric": "求める式を、和と積だけで表せる形に変形する。",
    "substitute_and_compute": "和と積の値をあてはめて計算する。",
}

_ARITHMETIC_IDENTITY_PHRASE: dict[str, str] = {
    "factor_difference_of_squares": "和と差の積の形になおす",
    "express_via_elementary_symmetric": "和と積だけの形に変形する",
}


@register_solver("math.evaluate_arithmetic_via_identity")
def evaluate_arithmetic_via_identity(mode: object, value1: object, value2: object) -> Solution:
    """恒等式を利用して数値計算・式の値を直接求める（C3 g3_l12.calculation Lv2/Lv3）。

    recipe の構成内訳（a,b または s,p）だけから、独立に恒等式の右辺を計算する
    （double-solve）。mode ごとに steps の op 列を変える＝level_sep:
      Lv2 "diff_of_squares_arithmetic": value1=a, value2=b -> a²-b²=(a+b)(a-b)。
      Lv3 "symmetric_sum_of_squares"  : value1=s, value2=p -> x²+y²=s²-2p。
    答えは整数の SymbolicAnswer（鉄則①: 数値の calc 答えは digit 可）。narration に
    数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _ARITHMETIC_IDENTITY_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    v1 = sympy.sympify(value1)
    v2 = sympy.sympify(value2)
    if mode_s == "diff_of_squares_arithmetic":
        result = sympy.expand((v1 + v2) * (v1 - v2))
    else:  # symmetric_sum_of_squares
        result = sympy.expand(v1**2 - 2 * v2)

    disp = str(sympy.sstr(result))
    srepr = sympy.srepr(result)

    ops = _ARITHMETIC_IDENTITY_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _ARITHMETIC_IDENTITY_PHRASE.get(op, ""),
            narration=_ARITHMETIC_IDENTITY_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "simplify_polynomial",
    "add_or_subtract_polynomials",
    "distribute_or_divide",
    "compute_monomial_expression",
    "combine_fractional_expressions",
    "degree_of_expression",
    "solve_for_variable",
    "express_number_property",
    "combine_digit_number",
    "poly_term_definition",
    "classify_monomial_or_polynomial",
    "judge_like_terms",
    "system_term_definition",
    "expand_expression",
    "factor_expression",
    "evaluate_arithmetic_via_identity",
]
