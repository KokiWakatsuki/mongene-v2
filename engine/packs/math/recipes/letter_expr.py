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
]


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
    "transposition.rule_recall",
]


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

    if topic == "transposition":
        # g1_l22 移項。具体例の一次方程式 a·x + b = c を surface として埋め込み dup 分散。
        ex = _draw_eq_example_disp(rng, p)
        if concept == "definition":
            return f"方程式 {ex} を解くときに使う「移項」とは、どのような操作か"
        return f"方程式 {ex} で、ある項を反対の辺に移すと符号が変わるのはなぜか"  # sign_reason
    raise ValueError(f"未知の topic: {topic!r}")


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


__all__ = [
    "compute_letter_expression",
    "compute_substitution",
    "compute_notation",
    "term_recall",
    "verify_equation_solution",
    "compare_signed_numbers",
    "classify_number_sign",
    "represent_opposite_quantity",
    "recall_rule",
]
