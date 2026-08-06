"""文字式（一次式の計算）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した与式は
独立ソルバ `math.evaluate_letter_expression` で再整理し、答えの一致を確認する（double-solve）。

C1（g1 数と式・文字式）の計算セルを1つの汎用 recipe に集約する（arithmetic.py の
`compute_signed_arithmetic` と同型）:
  `math.compute_letter_expression(ctx, rng)` が mode ごとに一次式の項・係数を引いて与式を
  組み立てる。mode は spec_level.params["mode"]（各 unit の各 level に一意）。level_sep は
  solver 側の mode 別 op 列で担保する。答えは自由変数 x を含む一次式。

G-Q5t 対策（式答えは display 全体一致で検査・§引継 13c-2-#1）: 答えが定数に退化しないよう
x 係数は構成で非零にし、さらに「答えの表示が与式中に部分文字列として現れる」漏洩
（例: 答え bare `12x` が被除数 `(12x - 9)` の一部と一致／答え `3x` が与式 `-3x` の一部と一致）を
有界リトライで排除する。narration には数字を書かない。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

# 表示・sympy 文字列の整形ヘルパは polynomial recipe（式の計算）と共通。
from engine.packs.math.recipes.polynomial import (
    _domain_candidates,
    _fmt_expr_from_terms,
    _fmt_poly_x_terms,
    _sympy_poly_x,
    _sympy_str_from_terms,
)
from engine.packs.math.solvers.arithmetic import fmt_number
from engine.packs.math.solvers.letter_expr import _OPPOSITE_PAIRS


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# 各 unit の各 level が宣言する concept をすべて列挙（R6: family の concept_tags は
# この集合の部分集合であること）。
_LETTER_EXPR_CONCEPTS = [
    "letter_expr.combine_linear",
    "letter_expr.add_sub_linear_paren",
    "letter_expr.distribute_linear",
    "letter_expr.distribute_divide_mixed",
]


def _draw_expr(mode: str, p: dict[str, object], rng: Rng) -> tuple[str, str]:
    """mode ごとに一次式を1つ引いて (sympy 文字列, 表示) を返す（answer-first の逆算）。

    リトライで再抽選されうるので RNG を都度消費してよい（golden は最終列で承認する）。
    """
    coeff_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    const_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["const_domain"])) if v != 0]

    if mode == "combine_linear":
        # 同類項をまとめて一次式を整理する（a1·x + b1 + a2·x + b2）。x 係数の和≠0 を保証。
        a1 = int(draw({"int_set": coeff_cands}, rng))
        a2 = int(draw({"int_set": [v for v in coeff_cands if v + a1 != 0]}, rng))
        b1 = int(draw({"int_set": const_cands}, rng))
        b2 = int(draw({"int_set": const_cands}, rng))
        terms = [(a1, "x"), (b1, ""), (a2, "x"), (b2, "")]
        return _sympy_str_from_terms(terms), _fmt_expr_from_terms(terms)

    if mode == "expand_paren_linear":
        # かっこを含む一次式の加減 (a1·x + b1) op (a2·x + b2)。答えの x 係数≠0 を保証。
        op = str(draw(["+", "-"], rng))
        a1 = int(draw({"int_set": coeff_cands}, rng))
        if op == "+":
            a2_cands = [v for v in coeff_cands if v + a1 != 0]
        else:
            a2_cands = [v for v in coeff_cands if a1 - v != 0]
        a2 = int(draw({"int_set": a2_cands}, rng))
        b1 = int(draw({"int_set": const_cands}, rng))
        b2 = int(draw({"int_set": const_cands}, rng))
        g1 = [(a1, "x"), (b1, "")]
        g2 = [(a2, "x"), (b2, "")]
        expr_str = f"({_sympy_str_from_terms(g1)}){op}({_sympy_str_from_terms(g2)})"
        given_display = f"({_fmt_expr_from_terms(g1)}) {op} ({_fmt_expr_from_terms(g2)})"
        return expr_str, given_display

    if mode == "distribute_linear":
        # 一次式に数を掛ける k(a·x + b)。k は ±1・0 を除く（分配が自明にならない）。負の k も含む。
        k = int(draw(p["multiplier_domain"], rng))
        a = int(draw({"int_set": coeff_cands}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        inner = [(a, "x"), (b, "")]
        expr_str = f"({k})*({_sympy_str_from_terms(inner)})"
        given_display = f"{k}({_fmt_expr_from_terms(inner)})"
        return expr_str, given_display

    if mode == "distribute_divide_linear":
        # 分配と分数係数の乗除混合 k(a·x + b) op (rx·m·x + ry·m) ÷ m。
        # answer-first: ÷m 後の係数 rx,ry と除数 m を先に決め、割り切れる被除数を逆算する。
        # 答え = k(a·x+b) op (rx·x + ry)。x 係数（k·a ± rx）≠0 を保証。
        op = str(draw(["+", "-"], rng))
        k = int(draw(p["multiplier_domain"], rng))
        a = int(draw({"int_set": coeff_cands}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        m = int(draw(p["divisor_domain"], rng))
        rx_target = k * a
        if op == "+":
            rx_cands = [v for v in coeff_cands if rx_target + v != 0]
        else:
            rx_cands = [v for v in coeff_cands if rx_target - v != 0]
        rx = int(draw({"int_set": rx_cands}, rng))
        ry = int(draw({"int_set": const_cands}, rng))
        outer = [(a, "x"), (b, "")]
        divided = [(rx * m, "x"), (ry * m, "")]  # 割り切れる被除数
        expr_str = (
            f"({k})*({_sympy_str_from_terms(outer)})"
            f"{op}(({_sympy_str_from_terms(divided)}))/({m})"
        )
        given_display = (
            f"{k}({_fmt_expr_from_terms(outer)}) {op} "
            f"({_fmt_expr_from_terms(divided)}) ÷ {m}"
        )
        return expr_str, given_display

    raise ValueError(f"未知の mode: {mode!r}")


def _leaks(answer_display: str, given_display: str) -> bool:
    """答えの表示が与式中に部分文字列として現れるか（G-Q5t の disp∈norm_full を先取り）。

    正規化は空白除去で保守的に照合する（normalize_math_text は空白を単一化するのみだが、
    本チェックは空白差に依らず漏洩を検出したいので全空白を除去して比較する）。
    """
    return answer_display.replace(" ", "") in given_display.replace(" ", "")


@register_recipe("math.compute_letter_expression", provides_concepts=_LETTER_EXPR_CONCEPTS)
def compute_letter_expression(ctx: CellContext, rng: Rng) -> MR:
    """一次式の計算（加減・乗除）を構成して整理する（answer-first・calculation）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])

    solver = REGISTRY.solver("math.evaluate_letter_expression")
    for _ in range(200):
        expr_str, given_display = _draw_expr(mode, cast("dict[str, object]", p), rng)
        sol = cast(Solution, solver(expr_str, mode))
        assert isinstance(sol.answer, SymbolicAnswer)
        simplified = sympy.sympify(sol.answer.srepr)
        # 答えは一次式（x を残す＝定数に退化していない）で、かつ与式に部分文字列として漏れない。
        if simplified.free_symbols and not _leaks(sol.answer.display, given_display):
            expected = sympy.expand(sympy.sympify(expr_str))
            assert sol.answer.srepr == sympy.srepr(expected), (
                f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
            )
            sub_question = SubQuestionMR(
                label="(1)",
                asked="simplified_expr",
                answer=sol.answer,
                steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
            return MR(
                signature=ctx.spec_level.signature,
                family=ctx.family,
                level=ctx.level,
                purpose=ctx.purpose,
                seed=0,
                params={"expr_str": expr_str, "mode": mode, "given_disp": given_display},
                given={"expression": given_display},
                sub_questions=[sub_question],
                visual_plan=None,
                provenance=Provenance(recipe="math.compute_letter_expression"),
            )
    raise ValueError(f"非退化・非漏洩の一次式を構成できず（mode={mode!r}）")


# ---------------------------------------------------------------------------
# math.compute_substitution（g1_l16.calculation Lv1/Lv2 用）— 代入と式の値
# 式に数を代入して値（定数）を求める。答えは数値なので arithmetic 系と同じく given の数値が
# すべて whitelist され G-Q5t は漏洩しない（narration に数字を書かない）。
#   Lv1 "substitute_positive": a·x + b に正の整数を代入        op[substitute_value, compute_value]
#   Lv2 "substitute_signed"  : c2·x² + c1·x に負の整数を代入   op[substitute_with_parentheses,
#                              evaluate_powers, compute_value]（負数・累乗の符号処理が構造差）
# 忠実性: 例は整数代入（Lv1 x=4 で 3x-5／Lv2 x=-3 で -x²+2x）。desc の「分数・複数文字」は
# 負数×累乗の代表題材に畳んで実装し、本注記を source_desc に明示（§10 の sanction 手順）。
# ---------------------------------------------------------------------------
_SUBSTITUTION_CONCEPTS = [
    "letter_expr.substitute_positive",
    "letter_expr.substitute_signed",
]


@register_recipe("math.compute_substitution", provides_concepts=_SUBSTITUTION_CONCEPTS)
def compute_substitution(ctx: CellContext, rng: Rng) -> MR:
    """式に数を代入して式の値を求める（構成的生成・calculation Lv1/Lv2）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])
    coeff_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    const_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["const_domain"])) if v != 0]

    if mode == "substitute_positive":
        # a·x + b に正の整数を代入する（1次式・正の値）。
        a = int(draw({"int_set": coeff_cands}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        v = int(draw(p["value_domain"], rng))
        terms = [(a, 1), (b, 0)]
        steps_ops = ["substitute_value", "compute_value"]
    elif mode == "substitute_signed":
        # c2·x² + c1·x に負の整数を代入する（累乗・符号処理）。
        c2 = int(draw({"int_set": coeff_cands}, rng))
        c1 = int(draw({"int_set": const_cands}, rng))
        v = int(draw(p["value_domain"], rng))
        terms = [(c2, 2), (c1, 1)]
        steps_ops = ["substitute_with_parentheses", "evaluate_powers", "compute_value"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    expr_str = _sympy_poly_x(terms)
    expr_display = _fmt_poly_x_terms(terms)
    subs_str = f"x={v}"

    solver = REGISTRY.solver("math.evaluate_substitution")
    sol = cast(Solution, solver(expr_str, subs_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.sympify(expr_str).subs(sympy.Symbol("x"), sympy.Integer(v))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )
    assert [s.op for s in sol.steps] == steps_ops
    # 答えは定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols, "代入結果が定数にならなかった"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"expr_str": expr_str, "subs_str": subs_str, "mode": mode},
        given={"expression": expr_display, "input_value": str(v)},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_substitution"),
    )


# ---------------------------------------------------------------------------
# math.compute_notation（g1_l13/l14.calculation）— 乗法・除法の表し方のきまり
# 単項式の積・商を「× ÷ を明示した未簡約の形」で与え、記法規則に従った簡約形（式答え）を問う。
# 答えは自由変数を含む式なので display 全体一致で漏洩検査（letter_expr 系の定石）。与式は必ず
# × か ÷ を含み、答えはそれらを含まない簡約形なので部分文字列漏洩は構造上ない（_leaks で保険）。
# ---------------------------------------------------------------------------
_NOTATION_CONCEPTS = [
    "notation.product_rule_basic",
    "notation.product_rule_powers",
    "notation.quotient_as_fraction",
    "notation.quotient_mixed",
]

# sympy が特別扱いしない安全な単一小文字（全小文字が Symbol になることは確認済み）。
_NOTATION_LETTERS = ["a", "b", "c", "d", "k", "m", "n", "p", "x", "y"]


def _draw_distinct_letters(k: int, rng: Rng) -> list[str]:
    """相異なる k 個の文字を引く（draw の int_set で残りから逐次選択＝H8 準拠）。"""
    pool = list(_NOTATION_LETTERS)
    out: list[str] = []
    for _ in range(k):
        idx = int(draw({"int_set": list(range(len(pool)))}, rng))
        out.append(pool.pop(idx))
    return out


# 図形の点を表す大文字（C7 平面図形クラスタの用語想起・surface の variety 用）。
_POINT_LETTERS = [
    "A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R",
]

# 図形の直線を表す小文字（C9 平行と合同クラスタの用語想起・surface の variety 用）。
_LINE_LABELS = ["ℓ", "m", "n", "p", "q", "r", "s", "t", "u", "v", "w", "z"]


def _draw_distinct_from_pool(pool_source: list[str], k: int, rng: Rng) -> list[str]:
    """pool_source から相異なる k 個を引く（_draw_distinct_points の汎用版）。"""
    pool = list(pool_source)
    out: list[str] = []
    for _ in range(k):
        idx = int(draw({"int_set": list(range(len(pool)))}, rng))
        out.append(pool.pop(idx))
    return out


def _draw_distinct_points(k: int, rng: Rng) -> list[str]:
    """相異なる k 個の点名（大文字）を引く（_draw_distinct_from_pool の点名版）。"""
    return _draw_distinct_from_pool(_POINT_LETTERS, k, rng)


def _draw_distinct_lines(k: int, rng: Rng) -> list[str]:
    """相異なる k 個の直線名（小文字）を引く（_draw_distinct_from_pool の直線名版）。"""
    return _draw_distinct_from_pool(_LINE_LABELS, k, rng)


def _shuffle_pairs(pairs: list[tuple[str, str]], rng: Rng) -> list[tuple[str, str]]:
    """(sym, disp) の並びを draw で撹拌する（未簡約の見た目＝文字が正準順でない）。"""
    rest = list(pairs)
    out: list[tuple[str, str]] = []
    while rest:
        idx = int(draw({"int_set": list(range(len(rest)))}, rng))
        out.append(rest.pop(idx))
    return out


def _num_factor_disp(k: int) -> str:
    """積の因数として数を表示する（負数はかっこ付き＝教材の生の書き方）。"""
    return f"({k})" if k < 0 else str(k)


def _draw_notation(mode: str, p: dict[str, object], rng: Rng) -> tuple[str, str]:
    """mode ごとに未簡約の積・商を1つ引き (sympy 文字列, 与式表示) を返す。"""
    if mode == "product_basic":
        # 数×文字×文字（×省略・数を前に）。係数は |k|≥2（±1・0 除外）で必ず見える。
        k = int(draw(p["coeff_domain"], rng))
        ls = _draw_distinct_letters(2, rng)
        pairs = [(f"({k})", _num_factor_disp(k))] + [(le, le) for le in ls]
        order = _shuffle_pairs(pairs, rng)
        return "*".join(s for s, _ in order), " × ".join(d for _, d in order)

    if mode == "product_powers":
        # 数×（累乗になる複数文字）。相異なる文字ごとに指数を引き、その回数だけ因数に展開する。
        k = int(draw(p["coeff_domain"], rng))
        n_letters = int(draw(p["letter_count_domain"], rng))  # 2 または 3
        ls = _draw_distinct_letters(n_letters, rng)
        exps = [int(draw(p["exponent_domain"], rng)) for _ in ls]
        if max(exps) < 2:  # 少なくとも1文字は累乗（Lv1 との構造差を保証）
            exps[0] = 2
        pow_pairs = [(f"({k})", _num_factor_disp(k))]
        for le, e in zip(ls, exps):
            pow_pairs.extend([(le, le)] * e)
        order = _shuffle_pairs(pow_pairs, rng)
        return "*".join(s for s, _ in order), " × ".join(d for _, d in order)

    if mode == "quotient_basic":
        # ÷ を分数の形に。文字÷数・数÷文字・文字÷文字の3形で variety を確保。
        form = str(draw(["letter_over_num", "num_over_letter", "letter_over_letter"], rng))
        if form == "letter_over_num":
            le = _draw_distinct_letters(1, rng)[0]
            n = int(draw(p["divisor_domain"], rng))
            return f"{le}/({n})", f"{le} ÷ {n}"
        if form == "num_over_letter":
            le = _draw_distinct_letters(1, rng)[0]
            n = int(draw(p["divisor_domain"], rng))
            return f"({n})/{le}", f"{n} ÷ {le}"
        l1, l2 = _draw_distinct_letters(2, rng)
        return f"{l1}/{l2}", f"{l1} ÷ {l2}"

    if mode == "quotient_mixed":
        # 乗除混合を1つの分数に。分子＝数×（1〜2文字）、分母＝別の1文字（分数退化を防ぐ）。
        k = int(draw(p["coeff_domain"], rng))  # ≥2（× が自明でない）
        n_num_letters = int(draw(p["num_letter_count_domain"], rng))  # 1 または 2
        picks = _draw_distinct_letters(n_num_letters + 1, rng)
        num_letters, denom = picks[:n_num_letters], picks[n_num_letters]
        num_pairs = [(str(k), str(k))] + [(le, le) for le in num_letters]
        order = _shuffle_pairs(num_pairs, rng)
        num_sym = "*".join(s for s, _ in order)
        num_disp = " × ".join(d for _, d in order)
        return f"({num_sym})/({denom})", f"{num_disp} ÷ {denom}"

    raise ValueError(f"未知の mode: {mode!r}")


@register_recipe("math.compute_notation", provides_concepts=_NOTATION_CONCEPTS)
def compute_notation(ctx: CellContext, rng: Rng) -> MR:
    """単項式の積・商を記法規則に従って簡潔に表す（構成的生成・calculation）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])
    solver = REGISTRY.solver("math.simplify_notation")

    for _ in range(200):
        expr_str, given_display = _draw_notation(mode, cast("dict[str, object]", p), rng)
        sol = cast(Solution, solver(expr_str, mode))
        assert isinstance(sol.answer, SymbolicAnswer)
        simplified = sympy.sympify(sol.answer.srepr)
        # 答えは自由変数を残す式（定数退化なし）で、かつ与式に部分文字列として漏れない。
        if simplified.free_symbols and not _leaks(sol.answer.display, given_display):
            assert sol.answer.srepr == sympy.srepr(sympy.sympify(expr_str)), (
                f"double-solve 不一致: {expr_str!r} != {sol.answer.srepr}"
            )
            sub_question = SubQuestionMR(
                label="(1)",
                asked="simplified_expr",
                answer=sol.answer,
                steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
            return MR(
                signature=ctx.spec_level.signature,
                family=ctx.family,
                level=ctx.level,
                purpose=ctx.purpose,
                seed=0,
                params={"expr_str": expr_str, "mode": mode, "given_disp": given_display},
                given={"expression": given_display},
                sub_questions=[sub_question],
                visual_plan=None,
                provenance=Provenance(recipe="math.compute_notation"),
            )
    raise ValueError(f"非退化・非漏洩の記法問題を構成できず（mode={mode!r}）")


# ---------------------------------------------------------------------------
# knowledge 系（ChoiceAnswer・用語想起／解の判別）— C1 g1 数と式の残 knowledge セル。
# 答えはテキスト＝G-Q5t 素通り（§7.7）。dup は具体例（surface）と concept のパラメータ化で分散。
# ---------------------------------------------------------------------------
_TERM_RECALL_CONCEPTS = [
    "letter_expr.term_recall",
    "equality.term_recall",
    "equation.term_recall",
    "number.term_recall",
    "inequality.term_recall",
    "number_set.term_recall",
    "power.term_recall",
    "laws.term_recall",
    "prime_concepts.term_recall",
    "approximation.term_recall",
    # C3 g3 knowledge（用語想起）
    "square_root.term_recall",
    "real_numbers.term_recall",
    "quadratic_terms.term_recall",
    "approximation.term_recall_g3",
    "quadratic_coefficient.term_recall",
    # C6 g3 knowledge（用語想起）
    "quadratic_function_terms.term_recall",
    # C4 g1 比例・反比例（用語想起）
    "function_terms.term_recall",
    "direct_proportion.term_recall",
    "inverse_proportion.term_recall",
    # C12 確率（用語想起）
    "probability_terms.term_recall",
    # C11 データ・統計（用語想起）
    "frequency_table_terms.term_recall",
    "relative_frequency_terms.term_recall",
    "cumulative_frequency_terms.term_recall",
    "representative_value_terms.term_recall",
    "quartile_terms.term_recall",
    "box_plot_terms.term_recall",
    "survey_method_terms.term_recall",
    "sampling_terms.term_recall",
    "quadrant_terms.term_recall",
    # C7 g1 平面図形（用語想起）
    "line_angle_terms.term_recall",
    "perpendicular_terms.term_recall",
    "construction_choice_terms.term_recall",
    "circle_terms.term_recall",
    # C9 g2 平行と合同（用語想起）
    "angle_pair_terms.term_recall",
    "congruence_condition_terms.term_recall",
    "proof_logic_terms.term_recall",
    # C10 g3 相似・円・三平方（用語想起）
    "similarity_terms.term_recall",
]


# g1_l11 knowledge の具体例プール（素数／合成数）。例示は「意味」を表す surface であり
# 答え（用語名）とは無関係だが、教材として正しい例を出すために sympy で分類する。
_PRIMES = [n for n in range(2, 98) if sympy.isprime(n)]
_COMPOSITES = [n for n in range(4, 51) if not sympy.isprime(n)]


def _draw_eq_example_disp(rng: Rng, p: dict[str, object]) -> str:
    """具体例の一次方程式 a·x + b = c の表示を引く（surface・答えに無関係）。"""
    cc = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    a = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
    b = int(draw({"int_set": cc}, rng))
    x0 = int(draw({"int_set": [v for v in cc if v != 0]}, rng))
    c = a * x0 + b
    return f"{_fmt_poly_x_terms([(a, 1), (b, 0)])} = {c}"


def _draw_term_statement(domain: str, concept: str, rng: Rng, p: dict[str, object]) -> str:
    """(domain, concept) から説明文（具体例つき）を組み立てる。"""
    if domain == "number":
        # g1_l2 正負の数の用語。具体例の正の数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "absolute_value":
            return f"数 {n} について、数直線上でそれに対応する点と原点とのきょり"
        if concept == "number_line":
            return f"{n} や -{n} などの数を、点で対応させて表した直線"
        if concept == "origin":
            return f"数直線上で、+{n} と -{n} のちょうど真ん中にある、0 を表す点"
        return f"+{n} や -{n} の前についている、正と負を表す + や - のしるし"  # sign

    if domain == "inequality":
        # g1_l20 不等号（以上/以下/未満/超）。具体例の正の数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "at_least":
            return f"x は {n} 以上である（x は {n} と等しいか、それより大きい）"
        if concept == "at_most":
            return f"x は {n} 以下である（x は {n} と等しいか、それより小さい）"
        if concept == "less_than":
            return f"x は {n} 未満である（x は {n} より小さく、{n} は含まない）"
        return f"x は {n} より大きい（{n} を超える。{n} は含まない）"  # greater_than

    if domain == "power":
        # g1_l7 累乗の用語。具体例の累乗（底 b・指数 e）を埋め込み surface を分散する。
        b = int(draw(p["base_domain"], rng))
        e = int(draw(p["exponent_domain"], rng))
        if concept == "exponent":
            return f"{b} を {e} 回かけ合わせた累乗で、かけ合わせる回数 {e} を表す、右上に小さく書く数"
        if concept == "base":
            return f"{b} を {e} 回かけ合わせた累乗で、くり返しかけ合わせるもとの数 {b}"
        return f"同じ数 {b} を {e} 回かけ合わせて、1 つの数の形で表したもの"  # power

    if domain == "laws":
        # g1_l9 計算法則。具体例（数の等式）を埋め込み surface を分散する。
        a = int(draw(p["number_domain"], rng))
        b = int(draw(p["number_domain"], rng))
        c = int(draw(p["number_domain"], rng))
        if concept == "commutative":
            return f"{a} + {b} = {b} + {a} のように、たす順序を変えても和が変わらないという計算のきまり"
        if concept == "associative":
            return (
                f"({a} + {b}) + {c} = {a} + ({b} + {c}) のように、"
                f"たす組み合わせを変えても和が変わらないという計算のきまり"
            )
        return (
            f"{a} × ({b} + {c}) = {a} × {b} + {a} × {c} のように、"
            f"かっこの中の和にかけ算を分けて計算できるという計算のきまり"
        )  # distributive

    if domain == "approximation":
        # g1_l60 近似値まわりの用語。具体例の測定値 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "approximation":
            return f"長さや重さなどを測定して得られる、真の値に近いおよその値（たとえば {n} cm など）"
        if concept == "error":
            return f"測定で {n} cm を得たときのように、近似値から真の値をひいた差（真の値とのちがい）"
        return f"近似値 {n} cm のうち、測定して意味があると考えられる位の数字"  # significant_figures

    if domain == "square_root":
        # g3_l14 平方根の用語。具体例の正の数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "square_root":
            return f"2乗すると {n * n} になる数のように、2乗するとその数になるもとの数（正と負の2つがある）"
        return f"√{n} の √ のように、平方根を表すために使う記号"  # radical_sign

    if domain == "real_numbers":
        # g3_l16 実数の分類。具体例（分数・平方数でない数）を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "rational":
            b = int(draw(p["number_domain"], rng))
            return f"{n}/{b + 1} のように、整数を使った分数の形で表すことができる数"
        if concept == "irrational":
            nsq = n * n + 1  # 平方数でない数を確実に作る
            return f"√{nsq} や π のように、分数の形で表すことができない数"
        return f"0.{n}{n}{n}… のように、小数点以下で同じ数字の並びがくり返し続く小数"  # repeating_decimal

    if domain == "quadratic_terms":
        # g3_l24 2次方程式の用語。具体例の x²+bx+c=0 を埋め込み surface を分散する。
        b = int(draw(p["number_domain"], rng))
        c = int(draw(p["number_domain"], rng))
        sign_b = f"+ {b}" if b >= 0 else f"- {-b}"
        sign_c = f"+ {c}" if c >= 0 else f"- {-c}"
        eqx = f"x² {sign_b}x {sign_c} = 0"
        if concept == "quadratic_equation":
            return f"移項して整理すると {eqx} のように、x の2乗をふくむ形になる方程式"
        return f"方程式 {eqx} を成り立たせる x の値"  # solution

    if domain == "quadratic_coefficient":
        # g3_l26 2次方程式 ax²+bx+c=0 の係数の対応。具体例を埋め込み surface を分散する。
        # b・c は 0 だと項が式から消えて表示できないため非0 に限定する。
        a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]
        bc_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": a_cands}, rng))
        b = int(draw({"int_set": bc_cands}, rng))
        c = int(draw({"int_set": bc_cands}, rng))
        eqx = f"{_fmt_poly_x_terms([(a, 2), (b, 1), (c, 0)])} = 0"
        if concept == "coeff_a":
            return f"2次方程式 {eqx} において、x² の項の係数"
        if concept == "coeff_b":
            return f"2次方程式 {eqx} において、x の項の係数"
        return f"2次方程式 {eqx} において、定数項"  # coeff_c

    if domain == "probability_terms":
        # g1_l59/g2_l51 確率まわりの用語。具体例（さいころをn回投げる等）を埋め込み
        # surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "trial":
            return f"さいころを{n}回投げる実験のように、同じ条件のもとで何回もくり返すことができる実験や観察のこと"
        if concept == "probability":
            return f"{n}回中の一部で起こることがらのように、あることがらの起こりやすさの程度を表す数のこと"
        return f"1から{n}までの番号のカードのように、起こりうるどの結果も同じ程度に起こると考えられるようす"  # equally_likely

    if domain == "quadratic_function_terms":
        # g3_l32 y=ax² まわりの用語。具体例の比例定数 a(≠0) を埋め込み surface を分散する。
        a = int(draw({"int_set": [
            v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0
        ]}, rng))
        if concept == "proportionality_constant":
            return f"y = {a}x² の式で、x² にかけられている数（a にあたる部分）を何というか"
        if concept == "vertex":
            return "関数 y=ax² のグラフ（放物線）が、対称の中心として通る点を何というか"
        return "関数 y=ax² のグラフ（放物線）が、左右対称になるもとになる直線を何というか"  # axis_of_symmetry

    if domain == "function_terms":
        # g1_l28 関数まわりの用語（変数・関数・変域）。具体例（正方形の1辺と周の長さ）を
        # 埋め込み surface を分散する（C4 g1 比例・反比例クラスタの導入回）。各 concept で
        # 必ず number_domain から1つ以上引き、無駄引き（未使用の draw）を作らない。
        if concept == "variable":
            m = int(draw(p["number_domain"], rng))
            return (
                f"1辺の長さが{m}cmより大きい正方形の1辺の長さを x cm とするときの x のように、"
                "いろいろな値をとることができる文字"
            )
        if concept == "function":
            # 2通りの言い回し（定義そのもの／具体例つき）を surface として分散する。
            # どちらの言い回しにも number_domain の値を埋め込み variety を確保する。
            variant = int(draw({"int_set": [0, 1]}, rng))
            n = int(draw(p["number_domain"], rng))
            if variant == 0:
                return (
                    f"ある値を1つ決める（例えば{n}のように）と、それに対応してもう一方の値が"
                    "ただ1つに決まるときの、2つの数量の関係"
                )
            return (
                f"1辺の長さが{n}cmより長い正方形の1辺の長さを x cm、"
                "周の長さを y cm とするときの、この y と x のような関係"
            )
        n = int(draw(p["number_domain"], rng))
        return f"x の値が {n} 以上のように限られているときの、その x のとる値の範囲"  # domain_range

    if domain == "direct_proportion":
        # g1_l29 比例の用語（比例・比例定数）。具体例 y=ax を埋め込み surface を分散する。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        eqx = f"y = {a}x" if a != 1 else "y = x"
        if concept == "proportion":
            return f"{eqx} のように、x の値が2倍、3倍になると、それにともなって y の値も2倍、3倍になる関係"
        return f"{eqx} で、x にかけられている決まった数 {a} のような、比例の関係を決める定数"  # proportionality_constant

    if domain == "inverse_proportion":
        # g1_l33 反比例の用語（反比例・比例定数）。具体例 y=a/x を埋め込み surface を分散する。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        eqx = f"y = {a}/x"
        if concept == "inverse_proportion":
            return f"{eqx} のように、x の値が2倍、3倍になると、それにともなって y の値が1/2倍、1/3倍になる関係"
        return f"{eqx} で、積 xy がつねに等しくなる決まった数 {a} のような、反比例の関係を決める定数"  # proportionality_constant

    if domain == "frequency_table_terms":
        # g1_l54 度数分布表の用語。具体例の階級の下端・幅を埋め込み surface を分散する。
        lo = int(draw(p["number_domain"], rng))
        width = int(draw(p["width_domain"], rng))
        hi = lo + width
        if concept == "class":
            return f"度数分布表で、{lo}以上{hi}未満のように区切った、データを整理するための区間"
        if concept == "class_value":
            return f"度数分布表で、{lo}以上{hi}未満の階級の区間の中央の値"
        if concept == "frequency":
            return f"度数分布表で、{lo}以上{hi}未満の階級に入るデータの個数"
        return f"度数分布表で、{lo}以上{hi}未満のように区切ったときの区間の大きさ（{width}）"  # class_width

    if domain == "relative_frequency_terms":
        # g1_l55 相対度数まわりの用語。具体例の総度数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "relative_frequency":
            return f"総度数が{n}の度数分布表で、各階級の度数の、総度数に対する割合"
        return f"総度数{n}の度数分布表の、各階級の相対度数を折れ線でつないで表したグラフ"  # frequency_polygon

    if domain == "cumulative_frequency_terms":
        # g1_l56 累積度数まわりの用語。具体例の階級数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "cumulative_frequency":
            return f"{n}個の階級に分けた度数分布表で、いちばん小さい階級から対象の階級までの度数を合計した値"
        return f"{n}個の階級に分けた度数分布表で、いちばん小さい階級から対象の階級までの相対度数を合計した値"  # cumulative_relative_frequency

    if domain == "representative_value_terms":
        # g1_l57 代表値の用語。具体例のデータ個数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "mean":
            return f"{n}個のデータの値をすべて合計し、データの個数でわった値"
        if concept == "median":
            return f"{n}個のデータを大きさの順に並べたときの、中央の位置にある値"
        return f"{n}個のデータの中で、もっとも個数が多く現れる値"  # mode

    if domain == "quartile_terms":
        # g2_l55 四分位数の用語。具体例のデータ個数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "q1":
            return f"{n}個のデータを大きさの順に並べて中央値を境に下組・上組に分けたときの、下組の中央値"
        if concept == "q2":
            return f"{n}個のデータを大きさの順に並べたときの中央値のよび名"
        if concept == "q3":
            return f"{n}個のデータを大きさの順に並べて中央値を境に下組・上組に分けたときの、上組の中央値"
        return f"{n}個のデータについて、上組の中央値から下組の中央値をひいた差"  # iqr

    if domain == "box_plot_terms":
        # g2_l56 箱ひげ図の用語。具体例のデータ個数 n を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "box_left":
            return f"{n}個のデータを表した箱ひげ図で、箱の左端が表す値"
        if concept == "box_center":
            return f"{n}個のデータを表した箱ひげ図で、箱の中にひかれた線が表す値"
        if concept == "box_right":
            return f"{n}個のデータを表した箱ひげ図で、箱の右端が表す値"
        if concept == "whisker_min":
            return f"{n}個のデータを表した箱ひげ図で、左側にのびるひげの先端が表す値"
        return f"{n}個のデータを表した箱ひげ図で、右側にのびるひげの先端が表す値"  # whisker_max

    if domain == "survey_method_terms":
        # g3_l57 標本調査の用語。具体例（対象の個数 n）を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "census":
            return f"{n}個（人）の対象すべてを、もれなく調べる調査"
        return f"{n}個（人）の対象の集団から一部を取り出して調べ、集団全体のようすを推定する調査"  # sample_survey

    if domain == "sampling_terms":
        # g3_l58 標本の取り出し方の用語。具体例（対象の個数 n）を埋め込み surface を分散する。
        n = int(draw(p["number_domain"], rng))
        if concept == "population":
            return f"{n}個（人）からなる、調査したい対象全体の集まり"
        if concept == "sample":
            return f"{n}個（人）からなる対象全体から、調査のために取り出した一部分"
        return f"{n}個（人）からなる対象全体から、かたよりが出ないように偶然にまかせて標本を選び出す方法"  # random_sampling

    if domain == "quadrant_terms":
        # g1_l30 座標平面の用語（象限・原点）。具体例の座標平面上の点を埋め込み surface を分散する。
        m = int(draw(p["number_domain"], rng))
        n = int(draw(p["number_domain"], rng))
        if concept == "quadrant1":
            return f"座標平面上で、x座標が{m}のように正、y座標も{n}のように正である点が含まれる部分"
        if concept == "quadrant2":
            return f"座標平面上で、x座標が-{m}のように負、y座標は{n}のように正である点が含まれる部分"
        if concept == "quadrant3":
            return f"座標平面上で、x座標が-{m}のように負、y座標も-{n}のように負である点が含まれる部分"
        if concept == "quadrant4":
            return f"座標平面上で、x座標が{m}のように正、y座標は-{n}のように負である点が含まれる部分"
        return "座標平面上で、x軸とy軸が交わる点（座標が(0, 0)である点）"  # origin

    if domain == "line_angle_terms":
        # g1_l37 直線・線分・半直線・角の用語。具体例の点名を埋め込み surface を分散する。
        pa, pb, po = _draw_distinct_points(3, rng)
        if concept == "line":
            return f"2点{pa}、{pb}を両方向に限りなくのばした、まっすぐな図形"
        if concept == "segment":
            return f"2点{pa}、{pb}を両端とする、まっすぐな線の一部分"
        if concept == "ray":
            return f"点{pa}を端として、{pb}の方向へ一方だけ限りなくのばした図形"
        return f"点{po}から出る2つの半直線{po}{pa}、{po}{pb}がつくる図形"  # angle

    if domain == "perpendicular_terms":
        # g1_l37/l43 垂線まわりの用語。具体例の点名・直線名を埋め込み surface を分散する
        # （foot/distance のどちらの concept でも p_name/h_name/line_name をすべて本文に
        # 使う＝draw が dup_key の variety に反映されない「無駄引き」を避ける）。
        p_name, h_name = _draw_distinct_points(2, rng)
        line_name = str(draw(["ℓ", "m", "n"], rng))
        if concept == "foot":
            return f"点{p_name}から直線{line_name}に垂線を引いたときの、直線{line_name}との交点{h_name}"
        return (
            f"点{p_name}から直線{line_name}に引いた垂線と、その足{h_name}によってできる"
            f"線分の長さのことで、点{p_name}と直線{line_name}との距離とよばれる長さ"
        )  # distance

    if domain == "construction_choice_terms":
        # g1_l44 条件に対応する基本作図の用語。具体例の点名を埋め込み surface を分散する
        # （concept ごとに使う点の数が違うため、無駄引きを避け concept 別に draw する）。
        if concept == "equidistant_points":
            pa, pb = _draw_distinct_points(2, rng)
            return f"2点{pa}、{pb}から等しい距離にある点の集まりを作図するときに使う、基本作図の名前"
        po, pa, pb = _draw_distinct_points(3, rng)
        return (
            f"∠{pa}{po}{pb}の2辺{po}{pa}、{po}{pb}から等しい距離にある点の集まりを"
            "作図するときに使う、基本作図の名前"
        )  # equidistant_sides

    if domain == "circle_terms":
        # g1_l45 円まわりの用語。具体例の点名を埋め込み surface を分散する。
        po, pa, pb = _draw_distinct_points(3, rng)
        if concept == "radius":
            return f"円の中心{po}と、円周上の点{pa}を結んだ線分"
        if concept == "chord":
            return f"円周上の2点{pa}、{pb}を結んだ線分"
        if concept == "arc":
            return f"円周上の2点{pa}、{pb}によって分けられる、円周の一部分"
        if concept == "sector":
            return f"円の中心{po}と円周上の2点{pa}、{pb}を通る2つの半径、およびその間の弧で囲まれた図形"
        return f"円の中心{po}と円周上の2点{pa}、{pb}を結ぶ2つの半径がつくる、中心にできる角"  # central_angle

    if domain == "angle_pair_terms":
        # g2_l31 対頂角・同位角・錯角の用語。具体例の直線名を埋め込み surface を分散する。
        la, lb, lc = _draw_distinct_lines(3, rng)
        if concept == "vertical":
            return f"2直線{la}、{lb}が1点で交わってできる4つの角のうち、向かい合う位置にある2つの角の関係"
        if concept == "corresponding":
            return (
                f"平行な2直線{la}、{lb}に1本の直線{lc}が交わってできる角のうち、"
                f"直線{lc}に対して同じ側の同じ位置にある2つの角の関係"
            )
        return (
            f"平行な2直線{la}、{lb}に1本の直線{lc}が交わってできる角のうち、"
            f"直線{lc}をはさんで反対側にある2つの角の関係"
        )  # alternate

    if domain == "congruence_condition_terms":
        # g2_l37 三角形の合同条件の用語。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
        if concept == "sss":
            return f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}で、3組の辺の長さがそれぞれ等しいとわかっているとき、合同を示すのに使える条件"
        if concept == "sas":
            return f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}で、2組の辺とその間の角がそれぞれ等しいとわかっているとき、合同を示すのに使える条件"
        return f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}で、1組の辺とその両端の角がそれぞれ等しいとわかっているとき、合同を示すのに使える条件"  # asa

    if domain == "proof_logic_terms":
        # g2_l38 仮定・結論・反例の用語。具体例の命題(数量の大小関係)を埋め込み surface を分散する。
        m = int(draw(p["number_domain"], rng))
        if concept == "assumption":
            return f"「a、bが{m}より大きい数ならば、a+bも{m}より大きい」という文で、「ならば」の前に書かれている部分"
        if concept == "conclusion":
            return f"「a、bが{m}より大きい数ならば、a+bも{m}より大きい」という文で、「ならば」の後に書かれている部分"
        return f"あることがらが成り立たないことを示すために挙げる、条件に合うが結論には当てはまらない具体例のこと（{m}を使った例が挙げられることがある）"  # counterexample

    if domain == "similarity_terms":
        # g3_l39 相似な図形の用語。具体例の図形名を埋め込み surface を分散する。
        pa, pb = _draw_distinct_points(2, rng)
        return f"図形{pa}と図形{pb}が相似であるとき、対応する辺の長さの比のこと"

    if domain == "prime_concepts":
        # g1_l11 素数まわりの用語。相異なる2つの具体例を埋め込み surface を分散する
        # （小さいプールを2値で使い variety を確保し dup≤0.20 にする）。
        if concept == "prime":
            q1 = int(draw({"int_set": _PRIMES}, rng))
            q2 = int(draw({"int_set": [v for v in _PRIMES if v != q1]}, rng))
            return f"{q1} や {q2} のように、1 とその数自身のほかに約数をもたない、1 より大きい整数"
        if concept == "composite":
            n1 = int(draw({"int_set": _COMPOSITES}, rng))
            n2 = int(draw({"int_set": [v for v in _COMPOSITES if v != n1]}, rng))
            return f"{n1} や {n2} のように、1 とその数自身のほかにも約数をもつ整数"
        # prime_factor
        p1 = int(draw({"int_set": _PRIMES}, rng))
        p2 = int(draw({"int_set": _PRIMES}, rng))
        return f"整数 {p1 * p2} を {p1} × {p2} のように素数だけの積で表したときの、その1つ1つの素数"

    if domain == "number_set":
        # g1_l10 数の集合。相異なる2つの正の整数を例に埋め込み surface を分散する
        # （2 concept と少数のため、独立2値で variety を確保し dup≤0.20 にする）。
        cands = _domain_candidates(cast("dict[str, object]", p["number_domain"]))
        n1 = int(draw({"int_set": cands}, rng))
        n2 = int(draw({"int_set": [v for v in cands if v != n1]}, rng))
        if concept == "natural_number":
            lo, hi = sorted((n1, n2))
            return f"{lo}, {hi} のように、ものの個数や順番を表すのに使う、1 以上の整数を集めたもの"
        # integer
        return f"-{n1} や 0 や +{n2} のように、正の整数・0・負の整数をすべて集めたもの"

    cc = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    if domain == "letter":
        if concept == "term":
            a = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
            b = int(draw({"int_set": cc}, rng))
            ex = _fmt_poly_x_terms([(a, 1), (b, 0)])
            return f"式 {ex} を数や文字のまとまりの和とみたときの、その1つ1つの部分"
        if concept == "coefficient":
            a = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
            ex = _fmt_poly_x_terms([(a, 1)])
            return f"単項式 {ex} で、文字にかけられている数の部分"
        if concept == "degree":
            a = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
            pw = int(draw(p["power_domain"], rng))
            ex = _fmt_poly_x_terms([(a, pw)])
            return f"単項式 {ex} で、かけ合わされている文字の個数"
        # like_terms
        a1 = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
        a2 = int(draw({"int_set": [v for v in cc if v not in (1, -1) and v != a1]}, rng))
        pw = int(draw(p["power_domain"], rng))
        e1 = _fmt_poly_x_terms([(a1, pw)])
        e2 = _fmt_poly_x_terms([(a2, pw)])
        return f"{e1} と {e2} のように、文字の部分がまったく同じである項どうし"

    ex = _draw_eq_example_disp(rng, p)
    if domain == "equality":
        if concept == "equality":
            return f"{ex} のように、等号 = を使って2つの数量が等しいことを表した式"
        if concept == "lhs":
            return f"等式 {ex} で、等号の左側の部分"
        if concept == "rhs":
            return f"等式 {ex} で、等号の右側の部分"
        return f"等式 {ex} で、左辺と右辺を合わせたよび名"  # both_sides
    # equation
    if concept == "equation":
        return f"{ex} のように、文字にあてはめる値によって成り立ったり成り立たなかったりする等式"
    return f"方程式 {ex} を成り立たせる文字の値"  # solution


@register_recipe("math.term_recall", provides_concepts=_TERM_RECALL_CONCEPTS)
def term_recall(ctx: CellContext, rng: Rng) -> MR:
    """数と式まわりの用語の名称を答える（knowledge 用語想起・g1_l17/l19/l21 Lv1）。"""
    p = ctx.spec_level.params
    domain = cast(str, p["domain"])
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    statement = _draw_term_statement(domain, concept, rng, cast("dict[str, object]", p))

    solver = REGISTRY.solver("math.term_recall_definition")
    sol = cast(Solution, solver(concept, domain))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["identify_description", "name_concept"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # statement（具体例＝surface）を params に含め dup_key を分散させる（§7.7）。
        params={"concept": concept, "domain": domain, "statement": statement},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.term_recall"),
    )


@register_recipe("math.verify_equation_solution", provides_concepts=["equation.verify_solution"])
def verify_equation_solution(ctx: CellContext, rng: Rng) -> MR:
    """ある値が方程式の解かどうかを代入して判別する（knowledge verify・g1_l21 Lv2）。"""
    p = ctx.spec_level.params
    cc = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    a = int(draw({"int_set": [v for v in cc if v not in (1, -1)]}, rng))
    b = int(draw({"int_set": cc}, rng))
    x0 = int(draw({"int_set": [v for v in cc if v != 0]}, rng))
    c = a * x0 + b  # 方程式 a·x + b = c の真の解は x0
    is_solution = int(draw({"int_set": [0, 1]}, rng)) == 1
    if is_solution:
        cand = x0
    else:
        delta = int(draw({"int_set": [v for v in cc if v != 0]}, rng))
        cand = x0 + delta  # x0 とは異なる（delta≠0）＝解ではない
    eq_str = f"({a})*x+({b})=({c})"
    eq_disp = f"{_fmt_poly_x_terms([(a, 1), (b, 0)])} = {c}"
    statement = f"方程式 {eq_disp} について、x = {cand}"

    solver = REGISTRY.solver("math.verify_equation_solution")
    sol = cast(Solution, solver(eq_str, cand))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "解である" if is_solution else "解ではない"
    assert sol.answer.correct == expected, f"double-solve 不一致: {is_solution} != {sol.answer.correct}"
    assert [s.op for s in sol.steps] == ["substitute_candidate", "judge_solution"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"equation_str": eq_str, "value": str(cand), "is_solution": str(is_solution)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.verify_equation_solution"),
    )


@register_recipe("math.compare_signed_numbers", provides_concepts=["number.compare_magnitude"])
def compare_signed_numbers(ctx: CellContext, rng: Rng) -> MR:
    """負の数を含む2数の大小を判別する（knowledge verify・g1_l2 Lv2）。"""
    p = ctx.spec_level.params
    cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
    for _ in range(200):
        a = int(draw({"int_set": cands}, rng))
        b = int(draw({"int_set": [v for v in cands if v != a]}, rng))
        if min(a, b) >= 0:  # 少なくとも一方は負（「負の数を含む大小」＝§desc）
            continue
        a_disp, b_disp = fmt_number(sympy.Integer(a)), fmt_number(sympy.Integer(b))
        statement = f"{a_disp} と {b_disp}"

        solver = REGISTRY.solver("math.compare_signed_numbers")
        sol = cast(Solution, solver(str(a), str(b)))
        assert isinstance(sol.answer, ChoiceAnswer)
        expected = fmt_number(sympy.Integer(max(a, b)))
        assert sol.answer.correct == expected, f"double-solve 不一致: {expected} != {sol.answer.correct}"
        assert [s.op for s in sol.steps] == ["compare_on_number_line", "judge_larger"]

        sub_question = SubQuestionMR(
            label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
            concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
        )
        return MR(
            signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
            purpose=ctx.purpose, seed=0,
            params={"a": str(a), "b": str(b)},
            given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
            provenance=Provenance(recipe="math.compare_signed_numbers"),
        )
    raise ValueError("compare_signed_numbers: 負の数を含む2数を構成できず")


# ---------------------------------------------------------------------------
# math.classify_number_sign / math.represent_opposite_quantity（g1_l1 knowledge）
# Lv1: 符号のついた数を正負に分類（ChoiceAnswer）。Lv2: 反対の性質をもつ量を符号つきの数で
# 表す（数値答え）。Lv2 の答えの絶対値は given の量の大きさに現れ両符号 whitelist されるため
# G-Q5t 安全（かつ「反対向き＝負」なので答えは given 正数と一致しない）。
# ---------------------------------------------------------------------------
@register_recipe("math.classify_number_sign", provides_concepts=["number.classify_sign"])
def classify_number_sign(ctx: CellContext, rng: Rng) -> MR:
    """符号のついた数を正の数・負の数に分類する（構成的生成・knowledge Lv1）。"""
    p = ctx.spec_level.params
    cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
    v = int(draw({"int_set": cands}, rng))
    statement = f"+{v}" if v > 0 else str(v)  # 符号を明示（正の数も +）

    solver = REGISTRY.solver("math.classify_number_sign")
    sol = cast(Solution, solver(str(v)))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "正の数" if v > 0 else "負の数"
    assert sol.answer.correct == expected
    assert [s.op for s in sol.steps] == ["read_number_sign", "classify_positive_negative"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"value": str(v)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.classify_number_sign"),
    )


@register_recipe("math.represent_opposite_quantity", provides_concepts=["number.opposite_quantity"])
def represent_opposite_quantity(ctx: CellContext, rng: Rng) -> MR:
    """反対の性質をもつ量を符号つきの数で表す（構成的生成・knowledge Lv2）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_set": list(range(len(_OPPOSITE_PAIRS)))}, rng))
    pos_label, neg_label, unit = _OPPOSITE_PAIRS[idx]
    m0 = int(draw(p["number_domain"], rng))  # 基準の場面（例示）の大きさ
    m = int(draw(p["number_domain"], rng))   # 問われる量の大きさ
    # 問われる量は必ず反対の向き（neg_label）＝答えは -m（given の正数 m と一致しない）。
    statement = (
        f"「{pos_label} {m0}{unit}」を +{m0}{unit} と表すことにするとき、"
        f"「{neg_label} {m}{unit}」"
    )

    solver = REGISTRY.solver("math.represent_opposite_quantity")
    sol = cast(Solution, solver(pos_label, neg_label, m))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert sol.answer.correct == str(-m)  # 反対の向き＝負
    assert [s.op for s in sol.steps] == ["identify_base_direction", "assign_opposite_sign"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"positive_label": pos_label, "asked_label": neg_label, "magnitude": str(m)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.represent_opposite_quantity"),
    )


# ---------------------------------------------------------------------------
# math.judge_set_closure（g1_l10 Lv2）— 数の集合が四則で閉じているかの判別（verify）。
# 答えはテキスト（閉じている／閉じていない）＝G-Q5t 素通り。集合の要素例（数）を surface に
# 埋め込み dup 分散（例は集合の要素であって、誤解を招く特定の演算例は出さない）。
# ---------------------------------------------------------------------------
_SET_LABELS = {"natural": "自然数", "integer": "整数"}
_OP_LABELS = {"add": "加法", "sub": "減法", "mul": "乗法", "div": "除法"}


@register_recipe("math.judge_set_closure", provides_concepts=["number_set.closure"])
def judge_set_closure(ctx: CellContext, rng: Rng) -> MR:
    """数の集合が四則について閉じているかを判別する（構成的生成・knowledge Lv2）。"""
    p = ctx.spec_level.params
    number_set = str(draw(cast("list[str]", p["set_domain"]), rng))
    operation = str(draw(cast("list[str]", p["op_domain"]), rng))
    cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v > 0]
    a = int(draw({"int_set": cands}, rng))
    b = int(draw({"int_set": [v for v in cands if v != a]}, rng))
    set_label, op_label = _SET_LABELS[number_set], _OP_LABELS[operation]
    # 例は集合の要素の列挙（誤解を招く特定の演算例は避ける）。整数は負・0 も含めて例示。
    if number_set == "integer":
        elems = f"-{a}, 0, {b}"
    else:
        lo, hi = sorted((a, b))
        elems = f"{lo}, {hi}"
    statement = f"{set_label}（たとえば {elems} など）の集合は、{op_label}について閉じているといえますか"

    solver = REGISTRY.solver("math.judge_set_closure")
    sol = cast(Solution, solver(number_set, operation))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["check_operation_result", "judge_closure"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"number_set": number_set, "operation": operation, "statement": statement},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_set_closure"),
    )


# ---------------------------------------------------------------------------
# math.recall_rule（規則想起・ChoiceAnswer）— C1 g1 数と式の残 knowledge セル。
# 「規則そのもの（正しい記述）」を選ぶ型。答えは規則の文（数字トークンなし）＝G-Q5t 素通り。
# 具体例（surface）を statement に埋め込み dup を分散する（term_recall と同じ定石・§7.7）。
# 移項(l22)を最初の顧客に、l3/l4/l5/l12/l15 の規則想起へ横展開できる汎用 recipe。
# ---------------------------------------------------------------------------
_RULE_RECALL_CONCEPTS = [
    "addition_sign.rule_recall",
    "subtraction.rule_recall",
    "term_in_sum.rule_recall",
    "speed_relation.rule_recall",
    "letter_meaning.rule_recall",
    "product_sign.rule_recall",
    "reciprocal.rule_recall",
    "notation_product_rule.rule_recall",
    "notation_quotient_rule.rule_recall",
    "transposition.rule_recall",
    # C3 g3 knowledge（規則・意味の想起）
    "expansion_meaning.rule_recall",
    "factorization_relation.rule_recall",
    "sqrt_magnitude.rule_recall",
    "multiplication_formula_choice.rule_recall",
    "sqrt_square_meaning.rule_recall",
    "quadratic_solving_method_choice.rule_recall",
    # C6 g3 knowledge（規則・意味の想起）
    "quadratic_function_form.rule_recall",
    "quadratic_roc_property.rule_recall",
    # solver 側（_RULE_MAPS）に topic を足しただけでは lint R6 が通らず、セルが
    # capabilities() に載らない（＝台帳上「未実装」のまま）。ここへの追加が対）。
    "parabola_property.rule_recall",
    # C12 確率（規則・意味の想起）
    "complementary_event.rule_recall",
    # C9 g2 平行と合同（規則・意味の想起）
    "parallel_angle_property.rule_recall",
    "triangle_angle_properties.rule_recall",
    "polygon_interior_sum_reason.rule_recall",
    "polygon_exterior_sum_property.rule_recall",
    "congruence_conditions.rule_recall",
    "isosceles_property.rule_recall",
    "isosceles_condition.rule_recall",
    "equilateral_property.rule_recall",
    "right_triangle_congruence_conditions.rule_recall",
    "parallelogram_property.rule_recall",
    "parallelogram_conditions.rule_recall",
    "special_parallelogram_diagonal_property.rule_recall",
    "equal_area_triangles.rule_recall",
    "pythagorean_theorem.rule_recall",
    "pythagorean_converse.rule_recall",
    "similarity_conditions.rule_recall",
    "parallel_segment_ratio_theorem.rule_recall",
    "parallel_segment_ratio_converse.rule_recall",
    "midpoint_connector_theorem.rule_recall",
    "area_ratio_theorem.rule_recall",
    "volume_ratio_theorem.rule_recall",
    "circle_inscribed_angle_theorem.rule_recall",
    "circle_inscribed_angle_converse.rule_recall",
    "arc_angle_proportion.rule_recall",
]


# 記法規則（l13/l14）の具体例に使う文字（surface の variety 用・答えには無関係）。
_RULE_EXAMPLE_LETTERS = ["a", "b", "c", "m", "n", "p", "x", "y"]


def _signed_paren(sign: str, mag: int) -> str:
    """符号つき整数を教材の生の書き方（かっこ付き）で表示する（例: (-7) / (+5)）。"""
    return f"({sign}{mag})"


def _draw_rule_statement(topic: str, concept: str, rng: Rng, p: dict[str, object]) -> str:
    """(topic, concept) から surface（具体例つきの文脈文）を組み立てる。"""
    if topic == "addition_sign":
        # g1_l3 加法の符号規則。同符号／異符号の2数の和を具体例として埋め込み dup 分散。
        m1 = int(draw(p["number_domain"], rng))
        m2 = int(draw(p["number_domain"], rng))
        if concept == "same_sign":
            s = str(draw(["+", "-"], rng))
            ex = f"{_signed_paren(s, m1)} + {_signed_paren(s, m2)}"
            return f"{ex} のように、同符号の2数をたすときの和の符号と絶対値の決まりについて"
        ex = f"{_signed_paren('+', m1)} + {_signed_paren('-', m2)}"  # different_sign
        return f"{ex} のように、異符号の2数をたすときの和の符号と絶対値の決まりについて"

    if topic == "subtraction":
        # g1_l4 減法→加法。具体例の減法を埋め込み dup 分散。
        m1 = int(draw(p["number_domain"], rng))
        m2 = int(draw(p["number_domain"], rng))
        s1 = str(draw(["+", "-"], rng))
        s2 = str(draw(["+", "-"], rng))
        ex = f"{_signed_paren(s1, m1)} - {_signed_paren(s2, m2)}"
        return f"{ex} のような減法（ひき算）を計算するときのやり方について"

    if topic == "term_in_sum":
        # g1_l5 項。符号つき3項の和を具体例として埋め込み dup 分散。
        pieces: list[tuple[str, int]] = []
        for _ in range(3):
            s = str(draw(["+", "-"], rng))
            n = int(draw(p["number_domain"], rng))
            pieces.append((s, n))
        head = f"{'-' if pieces[0][0] == '-' else ''}{pieces[0][1]}"
        tail = "".join(f" {s} {n}" for s, n in pieces[1:])
        ex = head + tail
        return f"式 {ex} を、加法だけの式とみて「項」に分けて考えるとき、項とは何を指すか"

    if topic == "speed_relation":
        # g1_l15 速さ・道のり・時間。求める量に応じ、残り2量の具体的な場面を surface に
        # 埋め込む（数値は装飾で dup 分散。求める量そのものの数値は与えない）。
        d = int(draw(p["number_domain"], rng))
        t = int(draw(p["number_domain"], rng))
        v = int(draw(p["number_domain"], rng))
        if concept == "speed":
            return f"道のり {d} km を {t} 時間で進む場面のように、道のり・速さ・時間の関係で「速さ」を求める式"
        if concept == "distance":
            return f"速さ {v} km/時 で {t} 時間進む場面のように、道のり・速さ・時間の関係で「道のり」を求める式"
        return f"道のり {d} km を速さ {v} km/時 で進む場面のように、道のり・速さ・時間の関係で「時間」を求める式"  # time

    if topic == "letter_meaning":
        # g1_l12 文字を使った式。1本 price 円の品物を x 本買う場面を surface に埋め込み dup 分散。
        price = int(draw(p["number_domain"], rng))
        return f"1本 {price} 円の品物を x 本買ったときの代金を {price}x 円と表す場面のように、文字を使って数量を表すことの利点"

    if topic == "product_sign":
        # g1_l6 積の符号。負の数を偶数個／奇数個ふくむ積の具体例を埋め込み dup 分散。
        m1 = int(draw(p["number_domain"], rng))
        m2 = int(draw(p["number_domain"], rng))
        if concept == "even_count":
            return f"(-{m1}) × (-{m2}) のように、負の数を偶数個かけ合わせた積の符号について"
        return f"(-{m1}) × {m2} のように、負の数を奇数個かけ合わせた積の符号について"  # odd_count

    if topic == "reciprocal":
        # g1_l8 逆数。具体例の除法を埋め込み dup 分散。
        a = int(draw(p["number_domain"], rng))
        b = int(draw(p["number_domain"], rng))
        return f"{a} ÷ {b} のように、ある数でわる計算をかけ算になおすやり方について"

    if topic == "notation_product_rule":
        # g1_l13 乗法の記法規則。数と文字を両方振って dup 分散（数のみだと variety 不足）。
        k = int(draw(p["number_domain"], rng))
        le = str(draw(_RULE_EXAMPLE_LETTERS, rng))
        if concept == "omit_times":
            return f"{k} × {le} のように、数と文字の積を書き表すきまりについて"
        return f"{k} × {le} × {le} のように、同じ文字をふくむ積を書き表すきまりについて"  # power

    if topic == "notation_quotient_rule":
        # g1_l14 除法の記法規則。数と文字を両方振って dup 分散。
        k = int(draw(p["number_domain"], rng))
        le = str(draw(_RULE_EXAMPLE_LETTERS, rng))
        return f"{le} ÷ {k} のように、文字をふくむ式のわり算を書き表すきまりについて"

    if topic == "transposition":
        # g1_l22 移項。具体例の一次方程式 a·x + b = c を surface として埋め込み dup 分散。
        ex = _draw_eq_example_disp(rng, p)
        if concept == "definition":
            return f"方程式 {ex} を解くときに使う「移項」とは、どのような操作か"
        return f"方程式 {ex} で、ある項を反対の辺に移すと符号が変わるのはなぜか"  # sign_reason

    if topic == "expansion_meaning":
        # g3_l2 展開の意味。具体例の積 (x+a)(x+b) を surface として埋め込み dup 分散。
        a = int(draw(p["number_domain"], rng))
        b = int(draw(p["number_domain"], rng))
        sa = f"+ {a}" if a >= 0 else f"- {-a}"
        sb = f"+ {b}" if b >= 0 else f"- {-b}"
        return f"(x {sa})(x {sb}) のような積の形の式を計算するときの「展開」とは、どのような操作か"

    if topic == "factorization_relation":
        # g3_l7 因数分解と展開の関係。具体例の多項式 x²+ax+b を surface として埋め込み dup 分散
        # （2数を直接係数・定数に使い、distinct な組を多く確保する）。
        a = int(draw(p["number_domain"], rng))
        b = int(draw(p["number_domain"], rng))
        return f"多項式 x² + {a}x + {b} を扱うときの「因数分解」は、どのような操作か"

    if topic == "sqrt_magnitude":
        # g3_l15 平方根の大小。相異なる2つの正の数を surface として埋め込み dup 分散。
        a = int(draw(p["number_domain"], rng))
        b = int(draw(p["number_domain"], rng))
        while b == a:
            b = int(draw(p["number_domain"], rng))
        return f"√{a} と √{b} のような、正の数の平方根の大小について成り立つこと"

    if topic == "sqrt_square_meaning":
        # g3_l14 √(a²)=|a| の意味。負の数を含む具体例を surface として埋め込み dup 分散。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        n = int(draw({"int_set": cands}, rng))
        return f"√(({n})²) の値について"

    if topic == "multiplication_formula_choice":
        # g3_l3 乗法公式の識別。concept に応じて (x+a)(x+b) の a,b の関係を構成する
        # （一般形: a≠b かつ a≠-b／平方の形: a=b／和と差の積の形: b=-a）。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        if concept == "perfect_square_form":
            b = a
        elif concept == "diff_of_squares_form":
            b = -a
        else:  # general_form: a と異なり、かつ a の反対の符号(-a)でもない
            b_cands = [v for v in cands if v != a and v != -a]
            b = int(draw({"int_set": b_cands}, rng))
        sa = f"+ {a}" if a >= 0 else f"- {-a}"
        sb = f"+ {b}" if b >= 0 else f"- {-b}"
        return f"(x {sa})(x {sb}) を乗法公式を使って展開するときについて"

    if topic == "quadratic_solving_method_choice":
        # g3_l28 2次方程式の解き方の選択。concept に応じて因数分解しやすい形／
        # しにくい形（判別式が平方数でない）を構成する。
        if concept == "factoring_suitable":
            small = {"int_set": [n for n in range(-9, 10) if n != 0]}
            r1 = int(draw(small, rng))
            r2 = int(draw(small, rng))
            while r2 == r1:
                r2 = int(draw(small, rng))
            b, c = -(r1 + r2), r1 * r2
        else:  # formula_suitable: 判別式が平方数でない a=1 の2次式を構成する
            small = {"int_set": [n for n in range(-9, 10) if n != 0]}
            b = int(draw(small, rng))
            c = int(draw(small, rng))
            while _is_perfect_square(b * b - 4 * c):
                b = int(draw(small, rng))
                c = int(draw(small, rng))
        eqx = f"{_fmt_poly_x_terms([(1, 2), (b, 1), (c, 0)])} = 0"
        return f"2次方程式 {eqx} を解くときについて"

    if topic == "quadratic_function_form":
        # g3_l32 y=ax² の形の判別基準。具体例の比例定数 a(≠0) を surface に埋め込み dup 分散。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        return f"y = {a}x² のような式が「y は x の2乗に比例する」といえるための条件"

    if topic == "parabola_property":
        # g3_l33 放物線の性質。具体例の比例定数 a(≠0) を surface に埋め込み dup 分散。
        # concept ごとに、問う性質（形と対称性／開く向き／開き方の広さ）を言い分ける。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        if concept == "shape_and_symmetry":
            return f"関数 y = {a}x² のグラフがどのような曲線になるか、その形と対称性について"
        if concept == "opening_direction":
            return f"関数 y = {a}x² のグラフが、上と下のどちらに開くかの決まりについて"
        return f"関数 y = {a}x² のグラフと、比例定数だけがちがう別の放物線とを比べたときの開き方の広さについて"

    if topic == "quadratic_roc_property":
        # g3_l35 変化の割合の性質。具体例の比例定数 a(≠0) を surface に埋め込み dup 分散。
        cands = [v for v in _domain_candidates(cast("dict[str, object]", p["number_domain"])) if v != 0]
        a = int(draw({"int_set": cands}, rng))
        return f"関数 y = {a}x² について、x の変域を変えたときの変化の割合の性質"

    if topic == "complementary_event":
        # g2_l54 余事象の意味。具体例の確率 p=分数 を surface に埋め込み dup 分散。
        den = int(draw(p["number_domain"], rng))
        num = int(draw({"int_range": [1, den - 1]}, rng))
        return f"あることがらの起こる確率が {num}/{den} であるとき、その「余事象」（そのことがらが起こらないという事象）の確率"

    if topic == "parallel_angle_property":
        # g2_l32 平行線の性質とその逆。具体例の直線名を埋め込み surface を分散する。
        la, lb, lc = _draw_distinct_lines(3, rng)
        if concept == "property":
            return f"2直線{la}、{lb}が平行であるとき、直線{lc}がつくる同位角や錯角について成り立つこと"
        return f"2直線{la}、{lb}に直線{lc}が交わってできる同位角や錯角が等しいとき、2直線{la}、{lb}についていえること"

    if topic == "triangle_angle_properties":
        # g2_l33 三角形の内角の和・外角の性質。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        if concept == "interior_sum":
            return f"三角形{pa}{pb}{pc}の3つの内角をすべてたした大きさ"
        return f"三角形{pa}{pb}{pc}の頂点{pc}での外角の大きさ"  # exterior_property

    if topic == "polygon_interior_sum_reason":
        # g2_l34 多角形の内角の和の公式のしくみ。具体例の辺の数 n を surface に埋め込み dup 分散。
        n = int(draw(p["sides_domain"], rng))
        return f"{n}角形の内角の和を求めるとき、1つの頂点から対角線をひいて三角形に分けられる、その個数の求め方"

    if topic == "polygon_exterior_sum_property":
        # g2_l35 多角形の外角の和が辺の数によらず一定であること。具体例の辺の数 n を埋め込み dup 分散。
        n = int(draw(p["sides_domain"], rng))
        return f"{n}角形の外角の和は、辺の数を変えた他の多角形の外角の和と比べてどうなるか"

    if topic == "congruence_conditions":
        # g2_l37 三角形の合同条件(3つすべて)。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
        return f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}が合同であることを示すために使える条件"

    if topic == "isosceles_property":
        # g2_l41 二等辺三角形の性質(底角が等しい)。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        return f"{pa}{pb}={pa}{pc}の二等辺三角形{pa}{pb}{pc}で、底角どうしの大きさの関係"

    if topic == "isosceles_condition":
        # g2_l42 二等辺三角形になるための条件。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        return f"三角形{pa}{pb}{pc}が二等辺三角形になるといえる、角に着目した条件"

    if topic == "equilateral_property":
        # g2_l43 正三角形の性質(3辺/3角が等しい)。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        return f"三角形{pa}{pb}{pc}が正三角形であるときに成り立つ、辺の長さと内角の大きさの関係"

    if topic == "right_triangle_congruence_conditions":
        # g2_l44 直角三角形の合同条件(2つとも)。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
        return (
            f"直角三角形{pa}{pb}{pc}と直角三角形{pd}{pe}{pf}が合同であることを示すために"
            "使える条件"
        )

    if topic == "parallelogram_property":
        # g2_l46 平行四辺形の性質。具体例の四角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return f"平行四辺形{pa}{pb}{pc}{pd}で、対辺・対角・対角線について成り立つこと"

    if topic == "parallelogram_conditions":
        # g2_l47 平行四辺形になるための条件(5つとも)。具体例の四角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return f"四角形{pa}{pb}{pc}{pd}が平行四辺形になるといえる条件"

    if topic == "special_parallelogram_diagonal_property":
        # g2_l49 特別な平行四辺形の対角線の性質。具体例の四角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        shape = {"rectangle": "長方形", "rhombus": "ひし形", "square": "正方形"}[concept]
        return f"{shape}{pa}{pb}{pc}{pd}の対角線がもつ性質"

    if topic == "equal_area_triangles":
        # g2_l50 等積変形(共通の底辺・等しい高さの三角形は面積が等しい)。具体例の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return (
            f"三角形{pa}{pb}{pc}と三角形{pd}{pb}{pc}が、共通の底辺{pb}{pc}を持ち、"
            f"頂点{pa}、{pd}が底辺に平行な同じ直線上にあるとき、2つの三角形の面積の関係"
        )

    if topic == "pythagorean_theorem":
        # g3_l51 三平方の定理の意味。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        return (
            f"直角三角形{pa}{pb}{pc}で、∠{pc}=90°のとき、斜辺{pa}{pb}と他の2辺"
            f"{pb}{pc}、{pc}{pa}の長さについて成り立つ関係"
        )

    if topic == "pythagorean_converse":
        # g3_l52 三平方の定理の逆。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc = _draw_distinct_points(3, rng)
        return (
            f"三角形{pa}{pb}{pc}の3辺の長さを a, b, c とするとき、a²+b²=c² が"
            "成り立つならば、この三角形はどんな三角形であるといえるか"
        )

    if topic == "similarity_conditions":
        # g3_l40 三角形の相似条件(3つすべて)。具体例の三角形の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
        return f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}が相似であることを示すために使える条件"

    if topic == "parallel_segment_ratio_theorem":
        # g3_l42 平行線と線分の比の定理。具体例の三角形と分点の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
        return (
            f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}があり"
            f"{pd}{pe}∥{pb}{pc}であるとき、線分の比について成り立つ関係"
        )

    if topic == "parallel_segment_ratio_converse":
        # g3_l43 平行線と線分の比の定理の逆。具体例の三角形と分点の点名を埋め込み surface を分散する。
        pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
        return (
            f"三角形{pa}{pb}{pc}の辺{pa}{pb}, {pa}{pc}上の点{pd}, {pe}について、"
            f"{pa}{pd}:{pd}{pb}={pa}{pe}:{pe}{pc}が成り立つとき、いえること"
        )

    if topic == "midpoint_connector_theorem":
        # g3_l44 中点連結定理。具体例の三角形と中点の点名を埋め込み surface を分散する。
        pa, pb, pc, pm, pn = _draw_distinct_points(5, rng)
        return (
            f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}の中点をそれぞれ{pm}, {pn}と"
            f"するとき、線分{pm}{pn}について成り立つこと"
        )

    if topic == "area_ratio_theorem":
        # g3_l45 相似な平面図形の面積比。図形名を2文字の複合ラベルにして surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return f"相似な図形{pa}{pb}と図形{pc}{pd}の相似比がm:nであるとき、面積比はどのように表されるか"

    if topic == "volume_ratio_theorem":
        # g3_l46 相似な立体の体積比。立体名を2文字の複合ラベルにして surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return f"相似な立体{pa}{pb}と立体{pc}{pd}の相似比がm:nであるとき、体積比はどのように表されるか"

    if topic == "circle_inscribed_angle_theorem":
        # g3_l47 円周角の定理。具体例の円周上の点名を埋め込み surface を分散する。
        po, pa, pb, pp = _draw_distinct_points(4, rng)
        return (
            f"円{po}で、弧{pa}{pb}に対する中心角と、同じ弧{pa}{pb}に対する円周角"
            f"∠{pa}{pp}{pb}の大きさの関係"
        )

    if topic == "circle_inscribed_angle_converse":
        # g3_l48 円周角の定理の逆。具体例の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return (
            f"直線{pa}{pb}について同じ側にある2点{pc}, {pd}について、"
            f"∠{pa}{pc}{pb}=∠{pa}{pd}{pb}が成り立つとき、いえること"
        )

    if topic == "arc_angle_proportion":
        # g3_l50 円周角と弧の長さの比。具体例の点名を埋め込み surface を分散する。
        pa, pb, pc, pd = _draw_distinct_points(4, rng)
        return f"1つの円で、弧{pa}{pb}と弧{pc}{pd}の長さと、それぞれに対する円周角の大きさの関係"

    raise ValueError(f"未知の topic: {topic!r}")


def _is_perfect_square(n: int) -> bool:
    """判別式などの整数が平方数か（負・0 は非平方扱い）。"""
    if n < 0:
        return False
    r = int(n**0.5)
    return r * r == n or (r + 1) * (r + 1) == n


@register_recipe("math.recall_rule", provides_concepts=_RULE_RECALL_CONCEPTS)
def recall_rule(ctx: CellContext, rng: Rng) -> MR:
    """規則・約束の正しい記述を選ぶ（knowledge 規則想起・g1_l22 Lv1 ほか）。"""
    p = ctx.spec_level.params
    topic = cast(str, p["topic"])
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    statement = _draw_rule_statement(topic, concept, rng, cast("dict[str, object]", p))

    solver = REGISTRY.solver("math.recall_rule_statement")
    sol = cast(Solution, solver(topic, concept))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["read_rule_context", "recall_correct_rule"]
    assert sol.answer.correct not in sol.answer.distractors

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # statement（具体例＝surface）を params に含め dup_key を分散させる（§7.7）。
        params={"topic": topic, "concept": concept, "statement": statement},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.recall_rule"),
    )


# 有効数字の桁判別（g1_l60 knowledge Lv2）。測定値（小数）を構成し、有効数字の桁数を問う。
# 答えは漢数字「○けた」（ASCII 数字なし）＝G-Q5t 素通り。measurement を surface として params に
# 含め dup を分散する（§7.7・鉄則④）。
_SIGFIG_UNITS = ["m", "kg", "cm", "L", "g", "km"]


@register_recipe(
    "math.count_significant_figures",
    provides_concepts=["approximation.judge_significant_figures"],
)
def count_significant_figures(ctx: CellContext, rng: Rng) -> MR:
    """測定値の有効数字が何けたかを判別する（構成的生成・knowledge Lv2）。

    有効数字の桁数 c（2〜4）と数字列・小数点位置を引いて測定値の表記を作り、独立ソルバで
    桁数を数え直す（double-solve）。答えは ChoiceAnswer（漢数字「○けた」）。
    """
    c = int(draw({"int_set": [2, 3, 4]}, rng))
    first = int(draw({"int_range": [1, 9]}, rng))
    rest = "".join(str(int(draw({"int_range": [0, 9]}, rng))) for _ in range(c - 1))
    sig_digits = f"{first}{rest}"  # c 桁の数字列（先頭は 0 でない）

    form = str(draw(["intfrac", "lessone"], rng))
    if form == "intfrac":
        # 1 以上: 小数点を pos 桁目の後に置く（pos は 1〜c-1 で必ず小数部が残る）。
        pos = int(draw({"int_range": [1, c - 1]}, rng))
        measurement = f"{sig_digits[:pos]}.{sig_digits[pos:]}"
    else:
        # 1 未満: "0." のあとに位取りの 0 を lz 個おいてから有効数字を並べる。
        lz = int(draw({"int_set": [0, 1, 2]}, rng))
        measurement = "0." + "0" * lz + sig_digits

    unit = str(draw(_SIGFIG_UNITS, rng))
    statement = f"{measurement} {unit}"

    solver = REGISTRY.solver("math.count_significant_figures")
    sol = cast(Solution, solver(measurement))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["find_first_significant_digit", "count_significant_digits"]
    assert sol.answer.correct not in sol.answer.distractors

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"measurement": measurement, "unit": unit},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.count_significant_figures"),
    )


# 式の意味の解釈（g1_l12 knowledge Lv2）。場面（品名・個数・単価変数）を構成し、式 a·x+b·y が
# 表す数量の意味を問う。答えは品名で記述する ChoiceAnswer（ASCII 数字なし）＝G-Q5t 素通り。
# 品名・個数を surface として params に含め dup 分散（§7.7・鉄則④）。
_INTERPRET_ITEMS = ["りんご", "みかん", "ノート", "えんぴつ", "ペン", "消しゴム", "クッキー", "あめ"]


@register_recipe(
    "math.interpret_expression",
    provides_concepts=["letter_meaning.interpret_expression"],
)
def interpret_expression(ctx: CellContext, rng: Rng) -> MR:
    """与えられた文字式が表す数量の意味を解釈する（構成的生成・knowledge Lv2）。

    2種類の品物（単価 x 円・y 円）を個数ずつ買う場面と式 a·x+b·y を作り、式の意味を問う。
    品名だけから独立ソルバで正しい意味を判定し直す（double-solve）。
    """
    ia = str(draw(_INTERPRET_ITEMS, rng))
    ib = str(draw([it for it in _INTERPRET_ITEMS if it != ia], rng))
    a = int(draw({"int_range": [2, 9]}, rng))
    b = int(draw({"int_range": [2, 9]}, rng))
    expr = f"{a}x＋{b}y"
    statement = (
        f"1個 x 円の{ia}を {a} 個と、1個 y 円の{ib}を {b} 個買った。"
        f"このとき、式 {expr}"
    )

    solver = REGISTRY.solver("math.interpret_expression")
    sol = cast(Solution, solver(ia, ib))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["read_each_term_meaning", "combine_term_meanings"]
    assert sol.answer.correct not in sol.answer.distractors

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"item_a": ia, "item_b": ib, "count_a": str(a), "count_b": str(b)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.interpret_expression"),
    )


# 無理数の根号の中身（平方数でない・小さめの値でdup分散）。
_NONSQUARE_RADICANDS = [n for n in range(2, 300) if int(n**0.5) ** 2 != n]


@register_recipe(
    "math.classify_rational_irrational", provides_concepts=["real_numbers.classify_instance"]
)
def classify_rational_irrational_recipe(ctx: CellContext, rng: Rng) -> MR:
    """具体的な数を有理数・無理数に分類する MR を組む（C3 g3_l16.knowledge Lv2）。

    answer-first: 先に kind（有理数／無理数）を決め、その kind に属する具体的な数の
    形（分数／小数／平方数の根号 or 非平方数の根号）を1つ構成する。独立ソルバ
    math.classify_rational_irrational が値の文字列だけから再判定する（double-solve）。
    π は固定値で dup が必ず衝突する（自由度0）ため構成対象から除く（鉄則②）。
    """
    p = ctx.spec_level.params
    kind = str(draw(cast("list[str]", p["kind_set"]), rng))
    cands = _domain_candidates(cast("dict[str, object]", p["number_domain"]))

    if kind == "rational":
        shape = str(draw(["fraction", "decimal", "perfect_square_root"], rng))
        if shape == "fraction":
            num = int(draw({"int_set": cands}, rng))
            den_cands = [v for v in cands if v not in (0, num, -num)]
            den = int(draw({"int_set": den_cands}, rng))
            value_str, disp = f"{num}/{den}", f"{num}/{den}"
        elif shape == "decimal":
            d1 = int(draw({"int_range": [0, 9]}, rng))
            d2 = int(draw({"int_range": [1, 9]}, rng))
            value_str = disp = f"0.{d1}{d2}"
        else:  # perfect_square_root
            k = int(draw({"int_range": [2, 40]}, rng))
            value_str, disp = f"sqrt({k * k})", f"√{k * k}"
    else:  # irrational
        n = int(draw({"int_set": _NONSQUARE_RADICANDS}, rng))
        value_str, disp = f"sqrt({n})", f"√{n}"

    solver = REGISTRY.solver("math.classify_rational_irrational")
    sol = cast(Solution, solver(value_str))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "有理数" if kind == "rational" else "無理数"
    assert sol.answer.correct == expected, f"double-solve 不一致: {kind} != {sol.answer.correct}"
    assert [s.op for s in sol.steps] == [
        "evaluate_representability", "classify_rational_irrational",
    ]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"value_str": value_str, "kind": kind},
        given={"statement": disp}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.classify_rational_irrational"),
    )


@register_recipe(
    "math.verify_quadratic_solution", provides_concepts=["quadratic.verify_solution"]
)
def verify_quadratic_solution_recipe(ctx: CellContext, rng: Rng) -> MR:
    """ある値が2次方程式の解かどうかを代入して判別する MR を組む（C3 g3_l24.knowledge Lv2）。

    answer-first: 整数解 r1,r2 から x²+bx+c=0 を構成し、候補値が解かどうか（is_solution）
    を先に決める。独立ソルバ math.verify_quadratic_solution が方程式と候補値だけから
    再判定する（double-solve）。r2=-r1 だと b=0 になり "x² + 0x + c" のような不自然な
    表示になるため、r1 と反対の符号（-r1）も避けて引く（鉄則⑤: 構成時に排除）。
    """
    small = {"int_set": [n for n in range(-9, 10) if n != 0]}
    r1 = int(draw(small, rng))
    r2 = int(draw({"int_set": [n for n in range(-9, 10) if n != 0 and n != r1 and n != -r1]}, rng))
    b, c = -(r1 + r2), r1 * r2
    eq_str = f"x**2+({b})*x+({c})=0"
    eq_disp = f"{_fmt_poly_x_terms([(1, 2), (b, 1), (c, 0)])} = 0"

    is_solution = bool(int(draw({"int_set": [0, 1]}, rng)))
    if is_solution:
        cand = int(draw({"int_set": [r1, r2]}, rng))
    else:
        non_root_cands = [n for n in range(-9, 10) if n != 0 and n != r1 and n != r2]
        cand = int(draw({"int_set": non_root_cands}, rng))
    statement = f"2次方程式 {eq_disp} について、x = {cand}"

    solver = REGISTRY.solver("math.verify_quadratic_solution")
    sol = cast(Solution, solver(eq_str, cand))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "解である" if is_solution else "解ではない"
    assert sol.answer.correct == expected, f"double-solve 不一致: {is_solution} != {sol.answer.correct}"
    assert [s.op for s in sol.steps] == ["substitute_candidate", "judge_solution"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"eq_str": eq_str, "value": str(cand)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.verify_quadratic_solution"),
    )


__all__ = [
    "compute_letter_expression",
    "compute_substitution",
    "compute_notation",
    "term_recall",
    "verify_equation_solution",
    "compare_signed_numbers",
    "classify_number_sign",
    "represent_opposite_quantity",
    "judge_set_closure",
    "recall_rule",
    "count_significant_figures",
    "interpret_expression",
    "classify_rational_irrational_recipe",
    "verify_quadratic_solution_recipe",
]
