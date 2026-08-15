"""多項式（式の計算）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は「答え（または綺麗な中核値）を先に決め、問題を逆算する」登録済み関数。
乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した
答えは独立ソルバ（`engine.packs.math.solvers.polynomial`）で再計算し一致を確認する。

C2（数と式）クラスタの初セル: g2_l2.calculation（同類項をまとめる）Lv1/Lv2。
`linear.py` は並行編集中のため触らず、本ファイルに独立ヘルパ（_fmt_term 等）を
新設する（linear.py からの import は可・編集は不可）。
"""
from __future__ import annotations

import math
import re
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.polynomial import variable_parts

_COMBINE_LIKE_TERMS_CONCEPTS_LV1 = ["polynomial.combine_like_terms_basic"]
_COMBINE_LIKE_TERMS_CONCEPTS_LV2 = ["polynomial.combine_like_terms_mixed"]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    """spec_level.concept_tags が非空ならそれを、無ければ spec_family.concepts_default を使う。"""
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _fmt_term(coef: int, var: str, *, is_first: bool) -> str:
    """1つの項 (係数, 文字) を教材表記にする（例: (4,"a")->"4a"／(-1,"x")->"-x"／先頭以外は "+ "/"- " を前置）。"""
    mag = abs(coef)
    mag_s = "" if mag == 1 else str(mag)
    body = f"{mag_s}{var}" if var else str(mag)
    if is_first:
        return f"-{body}" if coef < 0 else body
    return f"- {body}" if coef < 0 else f"+ {body}"


def _fmt_expr_from_terms(terms: list[tuple[int, str]]) -> str:
    """項の並び [(係数,文字), ...] を与式の表示形にする（例: "5x + 3x - 2x"）。"""
    return " ".join(_fmt_term(c, v, is_first=(i == 0)) for i, (c, v) in enumerate(terms))


def _sympy_str_from_terms(terms: list[tuple[int, str]]) -> str:
    """項の並びを sympy.sympify に渡せる文字列にする（solver への独立入力）。"""
    parts = [f"({c})*{v}" if v else f"({c})" for c, v in terms]
    return "+".join(parts)


def _domain_candidates(domain: dict[str, object]) -> list[int]:
    """`int_range`/`int_set` ドメインの候補値を明示列挙する（exclude 適用済み）。

    候補を陽に持つのは `_draw_term_group` が「まだ引いていない最後の1項について、
    集約結果の絶対値が既存の項の絶対値と衝突しないか」を候補ごとに検査してから
    `draw({"int_set": 有効候補}, rng)` する必要があるため（値ベースの exclude だけでは
    「候補 v 自身の絶対値と結果の絶対値が一致する」自己言及的な条件を表現できない）。
    """
    vals: list[int]
    if "int_range" in domain:
        bounds = cast("list[int]", domain["int_range"])
        lo, hi = int(bounds[0]), int(bounds[1])
        vals = list(range(lo, hi + 1))
    elif "int_set" in domain:
        vals = [int(v) for v in cast("list[int]", domain["int_set"])]
    else:
        raise ValueError(f"未対応の coeff_domain: {domain!r}")
    excl = {int(v) for v in cast("list[int]", domain.get("exclude", []))}
    return [v for v in vals if v not in excl]


def _draw_term_group(rng: Rng, domain: dict[str, object], n: int) -> list[int]:
    """文字1種ぶんの項の係数を n 個、1つずつ `draw` する（answer-first の逆算）。

    退化を構造的に排除する（draw 以外で乱数を解釈しない・候補を絞ってから draw する
    だけで、乱数の解釈経路そのものは draw に一本化されている）:
      1. 途中の部分和が 0 になる＝まとめる前に一部の項だけで同類項が消える。
      2. 最終的な集約結果（答え）の絶対値が 0/1 になる、または既存のどの項・最後の
         項自身の絶対値とも一致する＝答えの式がそのまま与式中に部分文字列として
         現れる G-Q5t 漏洩（例: "6x - 3x" の答え "3x" が与式中の "3x" と衝突。
         実装時に seed 3/9/41 等で実際に発覚した）。
    """
    cands = _domain_candidates(domain)
    terms: list[int] = []
    running = 0
    for i in range(n):
        is_last = i == n - 1
        if is_last:
            valid = []
            for v in cands:
                new_total = v + running
                if abs(new_total) in (0, 1):
                    continue
                if any(abs(t) == abs(new_total) for t in terms):
                    continue
                if abs(v) == abs(new_total):  # 最後の項自身との自己衝突
                    continue
                valid.append(v)
        else:
            valid = [v for v in cands if (v + running) != 0]
        val = int(draw({"int_set": valid}, rng))
        terms.append(val)
        running += val
    return terms


# ---------------------------------------------------------------------------
# math.combine_like_terms（g2_l2.calculation Lv1/Lv2 用）— C2 クラスタ初セル
# 同類項をまとめる。answer-first: 文字ごとに項の係数群を先に決め（合計≠0を構成で保証）、
# 見かけの与式を組み立てる。独立ソルバ `math.simplify_polynomial` で式全体を再計算し一致を確認。
#   Lv1 "single_var" : 1種の文字・2〜3項          op列 [group_like_terms, add_coefficients]
#   Lv2 "mixed_vars" : 2種の文字混在・a,b交互に配置 op列 [identify_like_terms, group_like_terms,
#                       add_coefficients]（先頭に選別の1手を足す＝level_sep）
# ---------------------------------------------------------------------------
@register_recipe("math.combine_like_terms", provides_concepts=(
    _COMBINE_LIKE_TERMS_CONCEPTS_LV1 + _COMBINE_LIKE_TERMS_CONCEPTS_LV2
))
def combine_like_terms(ctx: CellContext, rng: Rng) -> MR:
    """同類項をまとめて式を簡単にする（answer-first・calculation）。

    Lv1（mode="single_var"）: 1種の文字 x の項を n 個（2〜3）選ぶ。
    Lv2（mode="mixed_vars"）: 文字 a の項 n_a 個・文字 b の項 n_b 個を a,b交互に配置する
    （選別＝同類項の識別が必須になる構造）。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    coeff_domain = p["coeff_domain"]

    if mode == "single_var":
        n = int(draw(p["term_count_domain"], rng))
        coeffs = _draw_term_group(rng, coeff_domain, n)
        terms = [(c, "x") for c in coeffs]
        signature_extra = {"n": n}
        steps_ops = ["group_like_terms", "add_coefficients"]
    elif mode == "mixed_vars":
        n_a = int(draw(p["term_count_domain"], rng))
        n_b = int(draw(p["term_count_domain"], rng))
        coeffs_a = _draw_term_group(rng, coeff_domain, n_a)
        coeffs_b = _draw_term_group(rng, coeff_domain, n_b)
        # a, b を交互に配置（片方が尽きたら残りを続けて並べる）＝units.generated.yaml の
        # 例「4a − 7b − 6a + 2b + 3a」と同型の見かけ。
        terms = []
        ia = ib = 0
        while ia < len(coeffs_a) or ib < len(coeffs_b):
            if ia < len(coeffs_a):
                terms.append((coeffs_a[ia], "a"))
                ia += 1
            if ib < len(coeffs_b):
                terms.append((coeffs_b[ib], "b"))
                ib += 1
        signature_extra = {"n_a": n_a, "n_b": n_b}
        steps_ops = ["identify_like_terms", "group_like_terms", "add_coefficients"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    expr_str = _sympy_str_from_terms(terms)
    given_display = _fmt_expr_from_terms(terms)

    solver = REGISTRY.solver("math.simplify_polynomial")
    sol = cast(Solution, solver(expr_str))
    assert isinstance(sol.answer, SymbolicAnswer)

    expected = sympy.expand(sympy.sympify(expr_str))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: recipe が構成した式 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    # steps は level_sep のためレベルごとに op 列を作り直す（solver の2手は共通コアとして
    # そのまま流用し、Lv2 のみ「同類項を見分ける」1手を先頭に足す）。narration に数字は書かない。
    steps: list[Step] = []
    if mode == "mixed_vars":
        steps.append(
            Step(
                op="identify_like_terms",
                args=[],
                result_srepr="",
                # 見分けた結果＝**どの文字の項があるか**（「a の項と b の項」）。
                # 指示の言い直しを括弧に置かない（面③）。
                # 「項 と b」のように**かなの前に半角スペース**を置かない
                # （`scan_explanations` の「かなと語の間の半角スペース」に当たる）。
                result_display="、".join(
                    f"{v} の項" for v in variable_parts(sympy.sympify(expr_str))
                ),
                narration="式の中から、文字の部分が同じ項（同類項）の組を見分ける。",
            )
        )
    steps.extend(sol.steps)
    assert [s.op for s in steps] == steps_ops

    sub_question = SubQuestionMR(
        label="(1)",
        asked="simplified_expr",
        answer=sol.answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    mr_params: dict[str, object] = {
        "mode": mode,
        "terms": [[str(c), v] for c, v in terms],
        **{k: str(v) for k, v in signature_extra.items()},
    }

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,  # pipeline が上書きする
        params=mr_params,
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.combine_like_terms"),
    )


# ---------------------------------------------------------------------------
# math.add_or_subtract_polynomials（g2_l3.calculation Lv1/Lv2 用）— C2
# 多項式の加減 (A)±(B) をかっこを外して整理する。answer-first: 2群の各項の係数を先に決め、
# 見かけの与式を組み立てる。独立ソルバで expand し一致を確認。
#   Lv1 "add"      : (x,y の1項ずつ)+(x,y の1項ずつ)  op列 [remove_parentheses, add_like_terms]
#   Lv2 "subtract" : (a,b,定数)-(a,b,定数)            op列 [distribute_negative_sign, add_like_terms]
# ---------------------------------------------------------------------------
_ADD_SUB_POLY_CONCEPTS = [
    "polynomial.add_polynomials",
    "polynomial.subtract_polynomials",
]


@register_recipe("math.add_or_subtract_polynomials", provides_concepts=_ADD_SUB_POLY_CONCEPTS)
def add_or_subtract_polynomials(ctx: CellContext, rng: Rng) -> MR:
    """多項式の加減をかっこを外して整理する（answer-first・calculation）。

    Lv1（mode="add"）: (x,y の1項ずつ) + (x,y の1項ずつ)。かっこをそのまま外す。
    Lv2（mode="subtract"）: (a,b,定数) - (a,b,定数)。うしろのかっこの符号を変えて外す。
    各項の係数は nonzero で引き、答えが完全に消える（全項相殺）場合のみ bounded_retry で再構成。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    variables = ["x", "y"] if mode == "add" else ["a", "b", ""]
    cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]

    # 各「変数」の項は答えに必ず残す（相殺しない）ように群Bの係数を候補から絞って引く。
    # これで答えが bare な単項（例 "y"）になって与式中に部分文字列として漏洩する事故を構造的に防ぐ
    # （G-Q5t は答えの表示文字列も検査する・retry を使わず候補制限で回避）。定数項（var=""）は相殺可。
    coeffs_a: list[int] = []
    coeffs_b: list[int] = []
    for var in variables:
        ca = int(draw({"int_set": cands}, rng))
        if var == "":
            cb_cands = cands
        elif mode == "add":
            cb_cands = [v for v in cands if v != -ca]  # 和 ca+cb ≠ 0
        else:
            cb_cands = [v for v in cands if v != ca]   # 差 ca-cb ≠ 0
        cb = int(draw({"int_set": cb_cands}, rng))
        coeffs_a.append(ca)
        coeffs_b.append(cb)
    group_a = list(zip(coeffs_a, variables))
    group_b = list(zip(coeffs_b, variables))

    op_sym = "+" if mode == "add" else "-"
    expr_str = f"({_sympy_str_from_terms(group_a)}){op_sym}({_sympy_str_from_terms(group_b)})"
    simplified = sympy.expand(sympy.sympify(expr_str))

    given_display = (
        f"({_fmt_expr_from_terms(group_a)}) {op_sym} ({_fmt_expr_from_terms(group_b)})"
    )

    solver = REGISTRY.solver("math.add_or_subtract_polynomials")
    sol = cast(Solution, solver(expr_str, mode == "subtract"))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(simplified), (
        f"double-solve 不一致: 構成 {simplified} != solver 再計算 {sol.answer.srepr}"
    )
    steps_ops = (
        ["distribute_negative_sign", "add_like_terms"]
        if mode == "subtract"
        else ["remove_parentheses", "add_like_terms"]
    )
    assert [s.op for s in sol.steps] == steps_ops

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
        params={"expr_str": expr_str, "is_subtraction": mode == "subtract", "mode": mode},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.add_or_subtract_polynomials"),
    )


# ---------------------------------------------------------------------------
# math.distribute_or_divide（g2_l5.calculation Lv1/Lv2 用）— C2
# 分配法則 k(A)（乗法）/ (A)÷d（除法）をかっこを外して計算する。
#   Lv1 "multiply": k(px + qy)            op列 [distribute_multiplication]
#   Lv2 "divide"  : (rx·d x + ry·d y)÷d   op列 [convert_division_to_multiplication, distribute]
#     （answer-first で結果係数 rx,ry と除数 d を選び、割り切れる被除数を逆算）
# ---------------------------------------------------------------------------
_DISTRIBUTE_CONCEPTS = [
    "polynomial.distribute_multiply",
    "polynomial.divide_polynomial",
]


@register_recipe("math.distribute_or_divide", provides_concepts=_DISTRIBUTE_CONCEPTS)
def distribute_or_divide(ctx: CellContext, rng: Rng) -> MR:
    """分配法則 k(A) / (A)÷d をかっこを外して計算する（answer-first・calculation）。

    Lv1（mode="multiply"）: 係数 k(≠0,±1) と2項の多項式 (px+qy) を選び、k(px+qy) を分配する。
    Lv2（mode="divide"）: 割り切れるよう結果係数 rx,ry(≠0) と除数 d(|d|≥2) を先に選び、
    被除数 (rx·d x + ry·d y) を逆算して (…)÷d を構成する（除法→逆数の乗法に直して分配）。
    独立ソルバ `math.distribute_or_divide` で expand し一致を確認する。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    inner_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]

    if mode == "multiply":
        k = int(draw(p["multiplier_domain"], rng))  # ≠0,±1
        px = int(draw({"int_set": inner_cands}, rng))
        qy = int(draw({"int_set": inner_cands}, rng))
        group = [(px, "x"), (qy, "y")]
        expr_str = f"({k})*({_sympy_str_from_terms(group)})"
        given_display = f"{k}({_fmt_expr_from_terms(group)})"
        is_division = False
    else:  # divide
        d = int(draw(p["divisor_domain"], rng))  # |d|≥2
        rx = int(draw({"int_set": inner_cands}, rng))  # 結果（答え）の係数
        ry = int(draw({"int_set": inner_cands}, rng))
        group = [(rx * d, "x"), (ry * d, "y")]  # 割り切れる被除数
        expr_str = f"({_sympy_str_from_terms(group)})/({d})"
        given_display = f"({_fmt_expr_from_terms(group)}) ÷ ({d})"
        is_division = True

    simplified = sympy.expand(sympy.sympify(expr_str))
    solver = REGISTRY.solver("math.distribute_or_divide")
    sol = cast(Solution, solver(expr_str, is_division))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(simplified), (
        f"double-solve 不一致: 構成 {simplified} != solver 再計算 {sol.answer.srepr}"
    )
    steps_ops = (
        ["convert_division_to_multiplication", "distribute"]
        if is_division
        else ["distribute_multiplication"]
    )
    assert [s.op for s in sol.steps] == steps_ops

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
        params={"expr_str": expr_str, "is_division": is_division, "mode": mode},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.distribute_or_divide"),
    )


# ---------------------------------------------------------------------------
# math.compute_monomial_expression（g2_l4.calculation Lv1/Lv2/Lv3 用）— C2
# 単項式どうしの乗除を計算して1つの単項式にする。answer は自由変数を含む symbolic
# （係数だけでなく display 全体一致でのみ漏洩検査＝G-Q5t 相対安全・§2-#1）。
#   Lv1 "simple_mul"    : (c1 x^e1) × (c2 x^e2)              op[multiply_coefficients, combine_powers]
#   Lv2 "power_mul"     : (c1 a^p b^q) × (c2 a^r b^s)        op[determine_sign, +…]（符号・累乗・複数文字）
#   Lv3 "mul_div_chain" : (A) ÷ (B[分数係数]) × (C)          op[convert_divisions_to_reciprocal, +…]
#     Lv3 は結果が整数係数の単項式になるよう factor-first で構成（A を B の分子の倍数に／
#     各文字は x を全因子に必ず含めて result 指数を非負・非定数に保つ）。
# ---------------------------------------------------------------------------
_SUP_DIGITS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

_MONOMIAL_CONCEPTS = [
    "polynomial.multiply_monomials",
    "polynomial.multiply_monomials_powers",
    "polynomial.monomial_mul_div_chain",
]


def _coef_sympy(coef: object) -> str:
    """係数を sympy.sympify に渡せる文字列にする（整数/既約有理数）。"""
    if isinstance(coef, sympy.Rational) and coef.q != 1:
        return f"(Rational({coef.p}, {coef.q}))"
    return f"({int(cast(int, coef))})"


def _mono_sympy_str(coef: object, exps: dict[str, int]) -> str:
    """(係数, {文字:指数}) を sympy.sympify に渡せる単項式文字列にする（指数0の文字は略）。"""
    parts = [_coef_sympy(coef)]
    for v, e in exps.items():
        if e == 1:
            parts.append(v)
        elif e >= 2:
            parts.append(f"{v}**{e}")
    return "*".join(parts)


def _fmt_monomial_factor(coef: object, exps: dict[str, int]) -> str:
    """単項式1因子を教材表記に（係数±1省略・指数上付き・分数係数は p/q 表記）。

    例: (-2,{a:2,b:1})->"-2a²b" / (1,{x:1})->"x" / (Rational(-3,2),{x:1,y:1})->"-3/2xy"。
    """
    var_part = ""
    for v, e in exps.items():
        if e == 1:
            var_part += v
        elif e >= 2:
            var_part += f"{v}{str(e).translate(_SUP_DIGITS)}"

    if isinstance(coef, sympy.Rational) and coef.q != 1:
        # 分数係数は文字部との間にスペースを置いて曖昧さを避ける（例「-3/2 xy」・source example に一致）。
        coef_s = f"{coef.p}/{coef.q}"
        return f"{coef_s} {var_part}" if var_part else coef_s

    c = int(cast(int, coef))
    if not var_part:
        return str(c)
    if c == 1:
        return var_part
    if c == -1:
        return f"-{var_part}"
    return f"{c}{var_part}"


def _fmt_monomial_chain(
    factors: list[tuple[object, dict[str, int]]], ops: list[str]
) -> str:
    """因子列と演算子列（"×"/"÷"）を連結して与式表記にする。

    ÷ の被演算子・負係数・分数係数の因子はかっこで囲む（優先順位と符号の明示）。
    """
    def _needs_paren(factor: tuple[object, dict[str, int]], op: str) -> bool:
        coef = factor[0]
        if op == "÷":
            return True
        if isinstance(coef, sympy.Rational):
            return bool(coef < 0 or coef.q != 1)
        return int(cast(int, coef)) < 0

    out = _fmt_monomial_factor(*factors[0])
    for i, op in enumerate(ops):
        f = factors[i + 1]
        fs = _fmt_monomial_factor(*f)
        if _needs_paren(f, op):
            fs = f"({fs})"
        out += f" {op} {fs}"
    return out


@register_recipe("math.compute_monomial_expression", provides_concepts=_MONOMIAL_CONCEPTS)
def compute_monomial_expression(ctx: CellContext, rng: Rng) -> MR:
    """単項式どうしの乗除を計算する（answer/factor-first・calculation Lv1/2/3）。"""
    p = ctx.spec_level.params
    mode: str = p["mode"]

    factors: list[tuple[object, dict[str, int]]]
    if mode == "simple_mul":
        coef_dom = p["coeff_domain"]
        exp_dom = p["exp_domain"]
        c1 = int(draw(coef_dom, rng))
        e1 = int(draw(exp_dom, rng))
        c2 = int(draw(coef_dom, rng))
        e2 = int(draw(exp_dom, rng))
        factors = [(c1, {"x": e1}), (c2, {"x": e2})]
        ops = ["×"]
        steps_ops = ["multiply_coefficients", "combine_powers"]
    elif mode == "power_mul":
        coef_dom = p["coeff_domain"]
        a_dom = p["a_exp_domain"]
        b_dom = p["b_exp_domain"]
        c1 = int(draw(coef_dom, rng))
        ea1 = int(draw(a_dom, rng))
        eb1 = int(draw(b_dom, rng))
        c2 = int(draw(coef_dom, rng))
        ea2 = int(draw(a_dom, rng))
        eb2 = int(draw(b_dom, rng))
        factors = [(c1, {"a": ea1, "b": eb1}), (c2, {"a": ea2, "b": eb2})]
        ops = ["×"]
        steps_ops = ["determine_sign", "multiply_coefficients", "combine_powers"]
    elif mode == "mul_div_chain":
        # A ÷ B × C。B のみ分数係数。結果は整数係数の単項式になるよう factor-first。
        b_coef = draw(p["divisor_frac_domain"], rng)
        assert isinstance(b_coef, sympy.Rational)
        c_coef = int(draw(p["coeff_domain"], rng))
        m = int(draw(p["multiplier_domain"], rng))
        a_coef = int(b_coef.p) * m  # A を B の分子の倍数に → 結果係数 m·C·q は整数
        ex_a: dict[str, int] = {}
        ex_b: dict[str, int] = {}
        ex_c: dict[str, int] = {}
        for v in ("x", "y"):
            if v == "x":
                # x は全因子・答えに必ず残す（因子が定数化せず答えも非定数）。
                eb = int(draw({"int_set": [1, 2]}, rng))
                extra = int(draw({"int_set": [0, 1]}, rng))
                ec = int(draw({"int_set": [1, 2]}, rng))
            else:
                eb = int(draw({"int_set": [0, 1]}, rng))
                extra = int(draw({"int_set": [0, 1]}, rng))
                ec = int(draw({"int_set": [0, 1]}, rng))
            ex_b[v] = eb
            ex_a[v] = eb + extra  # result 指数 = extra + ec ≥ 0 を保証
            ex_c[v] = ec
        factors = [(a_coef, ex_a), (b_coef, ex_b), (c_coef, ex_c)]
        ops = ["÷", "×"]
        steps_ops = ["convert_divisions_to_reciprocal", "multiply_coefficients", "combine_powers"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    factor_strs = [_mono_sympy_str(c, e) for c, e in factors]
    expr_str = factor_strs[0]
    sym_ops = {"×": "*", "÷": "/"}
    for i, op in enumerate(ops):
        expr_str = f"({expr_str}){sym_ops[op]}({factor_strs[i + 1]})"
    given_display = _fmt_monomial_chain(factors, ops)

    result = sympy.simplify(sympy.sympify(expr_str))

    solver = REGISTRY.solver("math.compute_monomial_expression")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(result), (
        f"double-solve 不一致: 構成 {result} != solver 再計算 {sol.answer.srepr}"
    )
    assert [s.op for s in sol.steps] == steps_ops

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
        params={"expr_str": expr_str, "mode": mode},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_monomial_expression"),
    )


# ---------------------------------------------------------------------------
# math.combine_fractional_expressions（g2_l6.calculation Lv2/Lv3 用）— C2
# 分数式の加減を通分して1つの分数にまとめる。answer は自由変数を含む symbolic
# （display 全体一致でのみ漏洩検査＝G-Q5t 相対安全・§2-#1）。
#   Lv2 "two_fractions_add"      : (A)/d1 + (B)/d2            op[find_common_denominator, combine_numerators]
#   Lv3 "fractions_with_integer" : (A)/d1 − (B)/d2 + k·a      op[find_common_denominator, distribute_signs, add_integer_term]
#     結果が必ず自由変数を残すよう、後ろの分数のある文字の係数を「相殺する値」から外して引く。
# ---------------------------------------------------------------------------
_COMBINE_FRACTION_CONCEPTS = [
    "polynomial.combine_fractions_basic",
    "polynomial.combine_fractions_signed",
]


@register_recipe("math.combine_fractional_expressions", provides_concepts=_COMBINE_FRACTION_CONCEPTS)
def combine_fractional_expressions(ctx: CellContext, rng: Rng) -> MR:
    """分数式の加減を通分して1つの分数にまとめる（構成的生成・calculation Lv2/Lv3）。"""
    p = ctx.spec_level.params
    mode: str = p["mode"]
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]
    den_cands = [int(v) for v in cast("list[int]", p["denominator_set"])]

    d_a = int(draw({"int_set": den_cands}, rng))
    d_b = int(draw({"int_set": [d for d in den_cands if d != d_a]}, rng))
    big_d = int(sympy.ilcm(d_a, d_b))
    ma = big_d // d_a
    mb = big_d // d_b

    if mode == "two_fractions_add":
        # (c1 x + c2 y)/d_a + (c3 x + c4 y)/d_b。結果に必ず x を残す（c3 を相殺値から外す）。
        c1 = int(draw({"int_set": coef_cands}, rng))
        bad = sympy.Rational(-c1 * ma, mb)  # c1·ma + c3·mb = 0 になる c3
        c3_cands = [c for c in coef_cands if sympy.Rational(c) != bad]
        c3 = int(draw({"int_set": c3_cands}, rng))
        c2 = int(draw({"int_set": coef_cands}, rng))
        c4 = int(draw({"int_set": coef_cands}, rng))
        terms_a = [(c1, "x"), (c2, "y")]
        terms_b = [(c3, "x"), (c4, "y")]
        expr_str = (
            f"({_sympy_str_from_terms(terms_a)})/({d_a})"
            f" + ({_sympy_str_from_terms(terms_b)})/({d_b})"
        )
        given_display = (
            f"({_fmt_expr_from_terms(terms_a)})/{d_a}"
            f" + ({_fmt_expr_from_terms(terms_b)})/{d_b}"
        )
        steps_ops = ["find_common_denominator", "combine_numerators"]
    elif mode == "fractions_with_integer":
        # (c1 a + c2 b)/d_a − (c3 a + c4 b)/d_b + k·a。結果に必ず b を残す（c4 を相殺値から外す）。
        c1 = int(draw({"int_set": coef_cands}, rng))
        c2 = int(draw({"int_set": coef_cands}, rng))
        c3 = int(draw({"int_set": coef_cands}, rng))
        bad = sympy.Rational(c2 * ma, mb)  # c2·ma − c4·mb = 0 になる c4
        c4_cands = [c for c in coef_cands if sympy.Rational(c) != bad]
        c4 = int(draw({"int_set": c4_cands}, rng))
        k = int(draw({"int_set": coef_cands}, rng))
        terms_a = [(c1, "a"), (c2, "b")]
        terms_b = [(c3, "a"), (c4, "b")]
        expr_str = (
            f"({_sympy_str_from_terms(terms_a)})/({d_a})"
            f" - ({_sympy_str_from_terms(terms_b)})/({d_b})"
            f" + ({k})*a"
        )
        given_display = (
            f"({_fmt_expr_from_terms(terms_a)})/{d_a}"
            f" - ({_fmt_expr_from_terms(terms_b)})/{d_b}"
            f" {_fmt_term(k, 'a', is_first=False)}"
        )
        steps_ops = ["find_common_denominator", "distribute_signs", "add_integer_term"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.combine_fractional_expressions")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.together(sympy.sympify(expr_str))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )
    assert [s.op for s in sol.steps] == steps_ops
    # 結果が自由変数を残す（定数・0 に退化していない）ことを確認。
    assert sympy.sympify(sol.answer.srepr).free_symbols, "分数式が定数に退化した"

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
        params={"expr_str": expr_str, "mode": mode},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.combine_fractional_expressions"),
    )


# ---------------------------------------------------------------------------
# math.degree_of_expression（g2_l1.calculation Lv1 用）— C2
# 1変数の単項式・多項式の次数を答える。単一小問に集約し（G-Q1 は sub_questions[0] のみ
# double-solve・§2-#7）、form（monomial/polynomial）は surface として振る（レベルは1つ）。
# 答えは次数（小さな整数・定数）。G-Q5t は given の係数が whitelist される＝次数が given の
# 係数と一致しても許可、given に無ければ本文に現れず、いずれも漏洩しない（§2-#2）。
# ---------------------------------------------------------------------------
_DEGREE_CONCEPTS = ["polynomial.degree_of_expression"]


def _sympy_poly_x(terms: list[tuple[int, int]]) -> str:
    """x の項 [(係数, 指数), ...] を sympy.sympify に渡せる文字列にする。"""
    parts = []
    for c, e in terms:
        if e == 0:
            parts.append(f"({c})")
        elif e == 1:
            parts.append(f"({c})*x")
        else:
            parts.append(f"({c})*x**{e}")
    return "+".join(parts)


def _fmt_poly_x_terms(terms: list[tuple[int, int]]) -> str:
    """x の項 [(係数, 指数), ...] を教材表記に（例 [(2,2),(-5,1),(1,0)] -> "2x² - 5x + 1")。

    **係数が 0 の項は書かない。** `x² + 0x - 25 = 0` `y = 0x + 16` のような式が
    出ていた（実物にこの書き方は無い）。項がすべて消えたときだけ "0" を返す。
    """
    terms = [(c, e) for c, e in terms if c != 0]
    if not terms:
        return "0"
    out = ""
    for i, (c, e) in enumerate(terms):
        mag = _fmt_monomial_factor(abs(c), {"x": e})
        if i == 0:
            out = ("-" + mag) if c < 0 else mag
        else:
            out += (" - " if c < 0 else " + ") + mag
    return out


@register_recipe("math.degree_of_expression", provides_concepts=_DEGREE_CONCEPTS)
def degree_of_expression(ctx: CellContext, rng: Rng) -> MR:
    """1変数の単項式・多項式の次数を答える（構成的生成・calculation Lv1）。"""
    p = ctx.spec_level.params
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]
    form = str(draw(p["form_set"], rng))

    if form == "monomial":
        d = int(draw(p["monomial_degree_domain"], rng))
        c = int(draw({"int_set": coef_cands}, rng))
        terms = [(c, d)]
    elif form == "polynomial":
        d = int(draw(p["polynomial_degree_domain"], rng))
        lead = int(draw({"int_set": coef_cands}, rng))
        terms = [(lead, d)]
        # 中間の次数（d-1 .. 1）は 0 を許して取捨、定数項は必ず nonzero＝常に多項式（2項以上）。
        for e in range(d - 1, 0, -1):
            mid = int(draw({"int_set": [*coef_cands, 0]}, rng))
            if mid != 0:
                terms.append((mid, e))
        c0 = int(draw({"int_set": coef_cands}, rng))
        terms.append((c0, 0))
    else:
        raise ValueError(f"未知の form: {form!r}")

    expr_str = _sympy_poly_x(terms)
    given_display = _fmt_poly_x_terms(terms)

    solver = REGISTRY.solver("math.degree_of_expression")
    sol = cast(Solution, solver(expr_str))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(d)), (
        f"double-solve 不一致: 構成次数 {d} != solver {sol.answer.srepr}"
    )
    assert [s.op for s in sol.steps] == ["find_highest_degree_term", "read_degree"]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="degree",
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
        params={"expr_str": expr_str, "form": form},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.degree_of_expression"),
    )


# ---------------------------------------------------------------------------
# math.solve_for_variable（g2_l9.calculation Lv1/Lv2/Lv3 用）— C2
# 等式を指定された文字について解く。answer は自由変数を含む symbolic（display 全体一致で
# のみ漏洩検査＝G-Q5t 相対安全・§2-#1）。
#   Lv1 "move_only"       : a·x + t = c（t 係数1）      op[isolate_target]
#   Lv2 "divide_coeff"    : a·t + b·u = c（|a|≥2）       op[isolate_target, divide_by_coefficient]
#   Lv3 "clear_and_divide": vl = vs·t/k（分母・積）      op[multiply_both_sides, divide_by_coefficient]
# ---------------------------------------------------------------------------
_SOLVE_FOR_VARIABLE_CONCEPTS = [
    "polynomial.rearrange_move",
    "polynomial.rearrange_divide",
    "polynomial.rearrange_product",
]


@register_recipe("math.solve_for_variable", provides_concepts=_SOLVE_FOR_VARIABLE_CONCEPTS)
def solve_for_variable(ctx: CellContext, rng: Rng) -> MR:
    """等式を指定された文字について解く（構成的生成・calculation Lv1/2/3）。"""
    p = ctx.spec_level.params
    mode: str = p["mode"]

    if mode == "move_only":
        # a·x + y = c を y について解く（y の係数は 1＝移項のみ）。
        a = int(draw({"int_set": [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]}, rng))
        c = int(draw(p["const_domain"], rng))
        target = "y"
        equation_str = f"({a})*x + y=({c})"
        given_equation = f"{_fmt_term(a, 'x', is_first=True)} + y = {c}"
        steps_ops = ["isolate_target"]
    elif mode == "divide_coeff":
        # a·x + b·y = c を x について解く（|a|≥2＝係数でわる）。
        a = int(draw(p["target_coeff_domain"], rng))  # |a|≥2
        b = int(draw({"int_set": [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]}, rng))
        c = int(draw(p["const_domain"], rng))
        target = "x"
        equation_str = f"({a})*x + ({b})*y=({c})"
        given_equation = (
            f"{_fmt_term(a, 'x', is_first=True)} {_fmt_term(b, 'y', is_first=False)} = {c}"
        )
        steps_ops = ["isolate_target", "divide_by_coefficient"]
    elif mode == "clear_and_divide":
        # vl = vs·vt/k を vt について解く（分母 k を払い、文字 vs でわる）。
        k = int(draw(p["denominator_domain"], rng))  # ≥2
        pool = list(cast("list[str]", p["letter_pool"]))
        vl = str(draw(pool, rng))
        vs = str(draw([c for c in pool if c != vl], rng))
        vt = str(draw([c for c in pool if c not in (vl, vs)], rng))
        target = vt
        equation_str = f"{vl}=({vs})*({vt})/({k})"
        given_equation = f"{vl} = {vs}{vt}/{k}"
        steps_ops = ["multiply_both_sides", "divide_by_coefficient"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.solve_for_variable")
    sol = cast(Solution, solver(equation_str, target, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert [s.op for s in sol.steps] == steps_ops
    # 解の式は自由変数を残す（定数に退化しない）。
    assert sympy.sympify(sol.answer.srepr).free_symbols, "解が定数に退化した"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="expression",
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
        params={"equation_str": equation_str, "target": target, "mode": mode},
        given={"equation": given_equation, "target_variable": target},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_for_variable"),
    )


# ---------------------------------------------------------------------------
# math.express_number_property（g2_l7.calculation Lv1 用）— C2
# 文字式で数の性質を表す（連続する偶数・奇数・整数などの和を1つの式にまとめる）。
# 答えは自由変数を含む symbolic（display 全体一致でのみ漏洩検査＝G-Q5t 相対安全・§2-#1）。
# dup_rate は property_type が少数のため構造的に高リスク → 変数文字・性質の種類・個数を
# surface param として広くとる（§7.7 F-3 の定石。答えに無関係な surface を分散させる）。
# ---------------------------------------------------------------------------
_NUMBER_PROPERTY_CONCEPTS = ["polynomial.consecutive_number_sum"]

# 性質 -> (係数, 先頭のオフセット, ラベル)。連続の刻みは係数に等しい（偶数=2, 3の倍数=3 …）。
_PROP_TYPES: dict[str, tuple[int, int, str]] = {
    "even": (2, 0, "偶数"),
    "odd": (2, 1, "奇数"),
    "int": (1, 0, "整数"),
    "mult3": (3, 0, "3の倍数"),
    "mult5": (5, 0, "5の倍数"),
}
_COUNT_WORD = {2: "2", 3: "3", 4: "4", 5: "5"}


def _fmt_consecutive_term(coef: int, var: str, const: int) -> str:
    """連続数の1項を教材表記に（例 coef=2,var="n",const=2 -> "2n+2" / const=0 -> "2n")。"""
    head = _fmt_term(coef, var, is_first=True)
    if const == 0:
        return head
    return f"{head}+{const}" if const > 0 else f"{head}-{abs(const)}"


@register_recipe("math.express_number_property", provides_concepts=_NUMBER_PROPERTY_CONCEPTS)
def express_number_property(ctx: CellContext, rng: Rng) -> MR:
    """連続する偶数・奇数・整数などの和を1つの式で表す（構成的生成・calculation Lv1）。"""
    p = ctx.spec_level.params
    var = str(draw(cast("list[str]", p["letter_pool"]), rng))
    ptype = str(draw(cast("list[str]", p["type_set"]), rng))
    count = int(draw(p["count_domain"], rng))
    base_coef, first_off, label = _PROP_TYPES[ptype]
    step = base_coef

    term_disps: list[str] = []
    term_syms: list[str] = []
    for i in range(count):
        const = first_off + step * i
        term_disps.append(_fmt_consecutive_term(base_coef, var, const))
        term_syms.append(f"({base_coef}*{var}+{const})")
    expr_str = "+".join(term_syms)
    exprs_joined = ", ".join(term_disps)
    expressions = (
        f"整数 {var} を使って表した、連続する{_COUNT_WORD[count]}つの{label} {exprs_joined}"
    )

    solver = REGISTRY.solver("math.express_number_property")
    sol = cast(Solution, solver(expr_str))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(expr_str))), (
        "double-solve 不一致"
    )
    assert [s.op for s in sol.steps] == ["expand_expression", "combine_like_terms"]
    assert sympy.sympify(sol.answer.srepr).free_symbols, "和が定数に退化した"

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
        params={"expr_str": expr_str, "var": var, "ptype": ptype, "count": count},
        given={"expressions": expressions},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.express_number_property"),
    )


# ---------------------------------------------------------------------------
# math.combine_digit_number（g2_l8.calculation Lv1 用）— C2
# 2けたの自然数 10a+b と位を入れかえた数 10b+a の和・差を整理する。数値パラメータが無く
# 構造が毎回同型のため dup_rate が構造的に困難（§3.1・design_C2）。対策＝2つの位の文字ペア
# （順序つき）と演算（和/差）を surface として広くとって見かけを分散させる。
# 答えは自由変数を含む symbolic（display 全体一致でのみ漏洩検査＝G-Q5t 相対安全・§2-#1）。
# ---------------------------------------------------------------------------
_DIGIT_NUMBER_CONCEPTS = ["polynomial.two_digit_number_property"]


@register_recipe("math.combine_digit_number", provides_concepts=_DIGIT_NUMBER_CONCEPTS)
def combine_digit_number(ctx: CellContext, rng: Rng) -> MR:
    """2けたの自然数と位を入れかえた数の和・差を整理する（構成的生成・calculation Lv1）。"""
    p = ctx.spec_level.params
    pool = list(cast("list[str]", p["letter_pool"]))
    tens = str(draw(pool, rng))
    units = str(draw([c for c in pool if c != tens], rng))
    operation = str(draw(cast("list[str]", p["operation_set"]), rng))

    op_sym = "+" if operation == "sum" else "-"
    op_word = "和" if operation == "sum" else "差"
    expr_str = f"(10*{tens}+{units}){op_sym}(10*{units}+{tens})"
    original = f"10{tens}+{units}"
    swapped = f"10{units}+{tens}"
    expressions = (
        f"十の位が {tens}、一の位が {units} の2けたの自然数 {original} と、"
        f"位を入れかえた数 {swapped} の{op_word}"
    )

    solver = REGISTRY.solver("math.combine_digit_number")
    sol = cast(Solution, solver(expr_str, operation))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(expr_str))), (
        "double-solve 不一致"
    )
    assert [s.op for s in sol.steps] == ["express_swapped_number", "combine_like_terms"]
    assert sympy.sympify(sol.answer.srepr).free_symbols, "結果が定数に退化した"

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
        params={"expr_str": expr_str, "operation": operation},
        given={"expressions": expressions},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.combine_digit_number"),
    )


# ---------------------------------------------------------------------------
# knowledge 系（ChoiceAnswer・用語想起／判別）— C2 の残 knowledge セル。
# 答えはテキスト＝G-Q5t 素通り（§7.7）。dup は具体例（surface）と concept/式のパラメータ化で分散。
# ---------------------------------------------------------------------------
_POLY_TERM_DESC = {
    "monomial": "数や文字の乗法だけでできている式 {ex}",
    "polynomial": "いくつかの単項式の和で表された式 {ex}",
    "coefficient": "単項式 {ex} で、文字にかけられている数の部分",
    "degree": "単項式 {ex} で、かけ合わされている文字の個数",
}


def _draw_example_monomial_disp(rng: Rng, p: dict[str, Any]) -> str:
    """具体例の単項式（係数 |c|≥2・指数≥1）の表示を引く（surface・答えに無関係）。"""
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v not in (0, 1, -1)]
    coef = int(draw({"int_set": coef_cands}, rng))
    var = str(draw(cast("list[str]", p["var_pool"]), rng))
    power = int(draw(p["power_domain"], rng))
    return _fmt_monomial_factor(coef, {var: power})


def _draw_example_polynomial_disp(rng: Rng, p: dict[str, Any]) -> str:
    """具体例の多項式（2項）の表示を引く（surface）。"""
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]
    var = str(draw(cast("list[str]", p["var_pool"]), rng))
    c1 = int(draw({"int_set": [v for v in coef_cands if v not in (1, -1)]}, rng))
    power = int(draw(p["power_domain"], rng))
    c0 = int(draw({"int_set": coef_cands}, rng))
    head = _fmt_monomial_factor(c1, {var: power})
    tail = f"+ {c0}" if c0 > 0 else f"- {abs(c0)}"
    return f"{head} {tail}"


@register_recipe("math.poly_term_recall", provides_concepts=["polynomial.term_recall"])
def poly_term_recall(ctx: CellContext, rng: Rng) -> MR:
    """多項式まわりの用語（単項式・多項式・係数・次数）の名称を答える（knowledge・g2_l1 Lv1）。"""
    p = ctx.spec_level.params
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    if concept == "polynomial":
        ex = _draw_example_polynomial_disp(rng, p)
    else:
        ex = _draw_example_monomial_disp(rng, p)
    statement = _POLY_TERM_DESC[concept].format(ex=ex)

    solver = REGISTRY.solver("math.poly_term_definition")
    sol = cast(Solution, solver(concept))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["identify_description", "name_concept"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"concept": concept, "example": ex},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.poly_term_recall"),
    )


@register_recipe("math.classify_monomial_or_polynomial", provides_concepts=["polynomial.classify_type"])
def classify_monomial_or_polynomial(ctx: CellContext, rng: Rng) -> MR:
    """式が単項式か多項式かを判別する（knowledge verify 型・g2_l1 Lv2）。"""
    p = ctx.spec_level.params
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]
    var = str(draw(cast("list[str]", p["var_pool"]), rng))
    form = str(draw(["monomial", "polynomial"], rng))
    c1 = int(draw({"int_set": [v for v in coef_cands if v not in (1, -1)]}, rng))
    power = int(draw(p["power_domain"], rng))
    if form == "monomial":
        disp = _fmt_monomial_factor(c1, {var: power})
        expr_str = f"({c1})*{var}**{power}"
    else:
        c0 = int(draw({"int_set": coef_cands}, rng))
        tail = f"+ {c0}" if c0 > 0 else f"- {abs(c0)}"
        disp = f"{_fmt_monomial_factor(c1, {var: power})} {tail}"
        expr_str = f"({c1})*{var}**{power}+({c0})"

    solver = REGISTRY.solver("math.classify_monomial_or_polynomial")
    sol = cast(Solution, solver(expr_str))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "多項式" if form == "polynomial" else "単項式"
    assert sol.answer.correct == expected, f"double-solve 不一致: form={form} != {sol.answer.correct}"
    assert [s.op for s in sol.steps] == ["count_terms", "classify_type"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"expr_str": expr_str, "form": form},
        given={"statement": disp}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.classify_monomial_or_polynomial"),
    )


@register_recipe("math.judge_like_terms", provides_concepts=["polynomial.like_terms_judge"])
def judge_like_terms(ctx: CellContext, rng: Rng) -> MR:
    """2つの項が同類項かを判別する（knowledge verify 型・g2_l2 Lv1）。"""
    p = ctx.spec_level.params
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]
    powers = [int(v) for v in cast("list[int]", p["power_domain"]["int_set"])]
    var_pool = cast("list[str]", p["var_pool"])
    same = int(draw({"int_set": [0, 1]}, rng)) == 1
    var = str(draw(var_pool, rng))
    power = int(draw({"int_set": powers}, rng))
    c1 = int(draw({"int_set": coef_cands}, rng))
    c2 = int(draw({"int_set": [v for v in coef_cands if v != c1]}, rng))

    t1_disp = _fmt_monomial_factor(c1, {var: power})
    t1_sym = f"({c1})*{var}**{power}"
    if same:
        var2, power2 = var, power
    else:
        var2 = str(draw(var_pool, rng))
        if var2 == var:
            power2 = int(draw({"int_set": [q for q in powers if q != power]}, rng))
        else:
            power2 = int(draw({"int_set": powers}, rng))
    t2_disp = _fmt_monomial_factor(c2, {var2: power2})
    t2_sym = f"({c2})*{var2}**{power2}"
    statement = f"{t1_disp} と {t2_disp}"

    solver = REGISTRY.solver("math.judge_like_terms")
    sol = cast(Solution, solver(t1_sym, t2_sym))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "同類項である" if same else "同類項ではない"
    assert sol.answer.correct == expected, f"double-solve 不一致: same={same} != {sol.answer.correct}"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"term1": t1_sym, "term2": t2_sym, "same": same},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_like_terms"),
    )


_SYSTEM_TERM_DESC = {
    "two_var_eq": "x, y の2つの文字をふくむ1次方程式 {ex}",
    "simultaneous": "2つの2元1次方程式を1つの組にした {ex}",
    "solution": "連立方程式 {ex} を、どちらも成り立たせる x, y の値の組",
}


def _fmt_two_var_eq(a: int, b: int, c: int) -> str:
    return f"{_fmt_term(a, 'x', is_first=True)} {_fmt_term(b, 'y', is_first=False)} = {c}"


@register_recipe("math.system_term_recall", provides_concepts=["polynomial.system_term_recall"])
def system_term_recall(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式まわりの用語の名称を答える（knowledge・g2_l10 Lv1）。"""
    p = ctx.spec_level.params
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    coef_cands = [v for v in _domain_candidates(p["coeff_domain"]) if v != 0]

    def _draw_eq() -> str:
        a = int(draw({"int_set": coef_cands}, rng))
        b = int(draw({"int_set": coef_cands}, rng))
        c = int(draw(p["const_domain"], rng))
        return _fmt_two_var_eq(a, b, c)

    if concept == "two_var_eq":
        ex = _draw_eq()
    else:
        ex = f"{_draw_eq()}, {_draw_eq()}"
    statement = _SYSTEM_TERM_DESC[concept].format(ex=ex)

    solver = REGISTRY.solver("math.system_term_definition")
    sol = cast(Solution, solver(concept))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert [s.op for s in sol.steps] == ["identify_description", "name_concept"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"concept": concept, "example": ex},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.system_term_recall"),
    )


# ---------------------------------------------------------------------------
# 多項式の展開（C3 g3_l1〜l6.calculation）— 積・平方・分配の形を答え先に構成し expand で展開
#
# 1つの recipe が mode で構成を切り替える（compute_signed_arithmetic 同型）。given には
# 展開前の「積の形」を display で出し、答えは展開後の多項式（自由変数を含む式＝G-Q5t は
# display 全体一致のみ検査＝積の形と展開形は構造が違うので漏洩しない）。level_sep は
# solver の mode 別 op 列で担保。dup は構成整数と文字種で分散する。
# ---------------------------------------------------------------------------
_EXPAND_CONCEPTS = [
    "polynomial.expand_mono_poly",
    "polynomial.expand_product",
    "polynomial.expand_formula_sum_product",
    "polynomial.expand_formula_square",
    "polynomial.expand_formula_diff_squares",
    "polynomial.expand_various",
    "polynomial.proof_diff_squares_linear",
]

# 展開の練習で使う文字（(x+a)² のように、数を教材の大きさに絞ったぶん
# 文字の種類で組合せを確保する）。
_EXPAND_VARS = ["x", "a", "y", "m", "t", "n", "b", "p", "k", "s"]
_EXPAND_VAR_PAIRS = [("a", "b"), ("x", "y"), ("m", "n"), ("p", "q"), ("s", "t")]


def _mono(c: int, var: str) -> str:
    """単項式 c·var の表示（c≠0）。例: (1,"x")->"x" / (-1,"x")->"-x" / (3,"a")->"3a"。"""
    if c == 1:
        return var
    if c == -1:
        return f"-{var}"
    return f"{c}{var}"


def _const_tail(q: int) -> str:
    """定数項を符号つきで後置（先頭以外）。例: 2->" + 2" / -5->" - 5"。q≠0。"""
    return f" + {q}" if q > 0 else f" - {-q}"


def _term_tail(coef: int, var: str) -> str:
    """変数つきの項を符号つきで後置（先頭以外）。例: (4,"t")->" + 4t" / (-1,"t")->" - t"。coef≠0。"""
    mag = abs(coef)
    body = var if mag == 1 else f"{mag}{var}"
    return f" + {body}" if coef > 0 else f" - {body}"


def _lin_factor(p: int, q: int, var: str) -> str:
    """1次式の因数 (p·var + q) の表示（p≥1, q≠0）。例: (2,-3,"x")->"(2x - 3)"。"""
    return f"({_mono(p, var)}{_const_tail(q)})"


def _expand_construct(mode: str, rng: Rng, p: dict[str, Any]) -> tuple[str, str]:
    """mode ごとに (expr_str[sympy用], given_display[表示用]) を構成する。"""
    if mode == "distribute_mono":
        var = str(draw(_EXPAND_VARS, rng))
        c = int(draw({"int_set": [n for n in range(-6, 7) if abs(n) >= 2]}, rng))
        a = int(draw({"int_set": list(range(1, 6))}, rng))
        b = int(draw({"int_set": [n for n in range(-9, 10) if n != 0]}, rng))
        expr = f"({c})*{var}*(({a})*{var}+({b}))"
        disp = f"{_mono(c, var)}({_mono(a, var)}{_const_tail(b)})"
        return expr, disp

    if mode == "distribute_mono_combine":
        var = str(draw(_EXPAND_VARS, rng))
        c1 = int(draw({"int_set": [n for n in range(-4, 5) if abs(n) >= 2]}, rng))
        a1 = int(draw({"int_set": list(range(2, 6))}, rng))
        b1 = int(draw({"int_set": [n for n in range(-6, 7) if n != 0]}, rng))
        d1 = int(draw({"int_set": [n for n in range(-6, 7) if n != 0]}, rng))
        c2 = int(draw({"int_set": [n for n in range(-4, 5) if n != 0]}, rng))
        a2 = int(draw({"int_set": list(range(2, 6))}, rng))
        b2 = int(draw({"int_set": [n for n in range(-6, 7) if n != 0]}, rng))
        expr = (
            f"({c1})*{var}*(({a1})*{var}**2+({b1})*{var}+({d1}))"
            f"+({c2})*{var}*(({a2})*{var}**2+({b2})*{var})"
        )
        term1 = f"{_mono(c1, var)}({_mono(a1, var)}²{_term_tail(b1, var)}{_const_tail(d1)})"
        # 第2項は c2 の符号を演算子として前置する。
        op2 = " + " if c2 > 0 else " - "
        term2 = f"{_mono(abs(c2), var)}({_mono(a2, var)}²{_term_tail(b2, var)})"
        disp = f"{term1}{op2}{term2}"
        return expr, disp

    if mode in ("binomial_product", "formula_sum_product", "formula_sum_product_signed"):
        var = str(draw(_EXPAND_VARS, rng))
        if mode == "formula_sum_product":
            dom = {"int_set": list(range(1, 13))}  # 基礎: 正の定数
        else:
            dom = {"int_set": [n for n in range(-12, 13) if n != 0]}
        a = int(draw(dom, rng))
        b = int(draw(dom, rng))
        expr = f"({var}+({a}))*({var}+({b}))"
        disp = f"({var}{_const_tail(a)})({var}{_const_tail(b)})"
        return expr, disp

    if mode == "binomial_product_coeff":
        var = str(draw(_EXPAND_VARS, rng))
        p1 = int(draw({"int_set": list(range(2, 6))}, rng))
        q1 = int(draw({"int_set": [n for n in range(-9, 10) if n != 0]}, rng))
        p2 = int(draw({"int_set": list(range(2, 6))}, rng))
        q2 = int(draw({"int_set": [n for n in range(-9, 10) if n != 0]}, rng))
        expr = f"(({p1})*{var}+({q1}))*(({p2})*{var}+({q2}))"
        disp = f"{_lin_factor(p1, q1, var)}{_lin_factor(p2, q2, var)}"
        return expr, disp

    if mode == "square_binomial":
        var = str(draw(_EXPAND_VARS, rng))
        # (x+a)² は自由度が a と文字種のみで少ない → a を広くとって dup を分散する。
        # **ただし ±18 まで。** ±30 まで引いていて「(t - 28)² = t² - 56t + 784」
        # という、乗法公式の練習としては数が大きすぎる式が出ていた。
        a = int(draw({"int_set": [n for n in range(-18, 19) if n != 0]}, rng))
        expr = f"({var}+({a}))**2"
        disp = f"({var}{_const_tail(a)})²"
        return expr, disp

    if mode == "square_binomial_coeff":
        var = str(draw(_EXPAND_VARS, rng))
        p1 = int(draw({"int_set": list(range(2, 6))}, rng))
        q1 = int(draw({"int_set": [n for n in range(-9, 10) if n != 0]}, rng))
        expr = f"(({p1})*{var}+({q1}))**2"
        disp = f"({_mono(p1, var)}{_const_tail(q1)})²"
        return expr, disp

    if mode == "diff_of_squares":
        var = str(draw(_EXPAND_VARS, rng))
        p1 = int(draw({"int_set": list(range(1, 6))}, rng))
        q1 = int(draw({"int_set": list(range(1, 16))}, rng))
        expr = f"(({p1})*{var}+({q1}))*(({p1})*{var}-({q1}))"
        lead = _mono(p1, var)
        disp = f"({lead} + {q1})({lead} - {q1})"
        return expr, disp

    if mode == "expand_multi":
        var = str(draw(_EXPAND_VARS, rng))
        dom = {"int_set": [n for n in range(-9, 10) if n != 0]}
        a = int(draw(dom, rng))
        b = int(draw(dom, rng))
        c = int(draw(dom, rng))
        # (x+a)²-(x+b)(x+c) は x² が必ず相殺し1次式になる（例題の型）。ただし
        # 1次の係数 2a-b-c が 0 だと答えが定数に退化する（自由変数が消え問題が
        # 成立しない）ため、退化しないよう有界リトライで引き直す。
        while 2 * a - b - c == 0:
            a = int(draw(dom, rng))
            b = int(draw(dom, rng))
            c = int(draw(dom, rng))
        expr = f"({var}+({a}))**2-(({var}+({b}))*({var}+({c})))"
        disp = f"({var}{_const_tail(a)})² - ({var}{_const_tail(b)})({var}{_const_tail(c)})"
        return expr, disp

    if mode == "expand_substitution":
        v1, v2 = tuple(draw(_EXPAND_VAR_PAIRS, rng))
        dom = {"int_set": [n for n in range(-9, 10) if n != 0]}
        a = int(draw(dom, rng))
        b = int(draw(dom, rng))
        common = f"({v1}+{v2})"
        expr = f"({common}+({a}))*({common}+({b}))"
        disp = f"({v1} + {v2}{_const_tail(a)})({v1} + {v2}{_const_tail(b)})"
        return expr, disp

    if mode == "proof_diff_squares_linear":
        # (a·n+b)² - (a·n+d)² は n² の項が常に相殺し、1次式 2a(b-d)n + (b-d)(b+d)
        # になる（証明の式変形で定番の型・g3_l13 例題 (2n+1)²-(2n-1)²=8n と同型）。
        # b と d が段階的に相異する（b=d だと恒等的に 0 に退化する）よう前の値を
        # 除外して引く（鉄則⑤: 一括判定の while だと衝突時に無限ループしうる）。
        a = int(draw({"int_set": list(range(1, 6))}, rng))
        bd_candidates = [n for n in range(-9, 10) if n != 0]
        b = int(draw({"int_set": bd_candidates}, rng))
        d = int(draw({"int_set": [n for n in bd_candidates if n != b]}, rng))
        expr = f"(({a})*n+({b}))**2-(({a})*n+({d}))**2"
        disp = f"({_mono(a, 'n')}{_const_tail(b)})² - ({_mono(a, 'n')}{_const_tail(d)})²"
        return expr, disp

    raise ValueError(f"未知の mode: {mode!r}")


_FACTOR_CONCEPTS = [
    "polynomial.factor_common",
    "polynomial.factor_sum_product",
    "polynomial.factor_perfect_square",
    "polynomial.factor_diff_squares",
    "polynomial.factor_various",
]


_EXPAND_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _fmt_poly_display_any(expr: sympy.Expr) -> str:
    """多項式（任意次数）の表示（`**n`→上付き・`*` 除去）。recipe 内の共通整形。"""
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_EXPAND_SUP), str(sympy.sstr(expr)))
    return s.replace("*", "")


def _expanded_pair(factored_src: str) -> tuple[str, str]:
    """因数分解形の文字列を展開し、(expr_str[solver用], given_display[展開形の表示]) を返す。"""
    expanded = sympy.expand(sympy.sympify(factored_src))
    return str(expanded), _fmt_poly_display_any(expanded)


def _factor_construct(mode: str, rng: Rng, p: dict[str, Any]) -> tuple[str, str]:
    """mode ごとに (expr_str[sympy用], given_display[表示用]) を構成する（因数分解の given は展開形）。"""
    small_nonzero = {"int_set": [n for n in range(-9, 10) if n != 0]}

    if mode == "factor_common":
        var = str(draw(_EXPAND_VARS, rng))
        g = int(draw({"int_set": list(range(2, 10))}, rng))
        pp = int(draw({"int_set": list(range(2, 7))}, rng))
        qq = int(draw(small_nonzero, rng))
        while math.gcd(pp, abs(qq)) != 1:
            qq = int(draw(small_nonzero, rng))
        return _expanded_pair(f"{g}*{var}*(({pp})*{var}+({qq}))")

    if mode == "factor_common_multi":
        v1, v2 = tuple(draw(_EXPAND_VAR_PAIRS, rng))
        g = int(draw({"int_set": list(range(2, 7))}, rng))
        c1 = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        c2 = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        c3 = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        while math.gcd(math.gcd(abs(c1), abs(c2)), abs(c3)) != 1:
            c3 = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        return _expanded_pair(
            f"{g}*{v1}*{v2}*(({c1})*{v1}+({c2})*{v2}+({c3}))"
        )

    if mode in ("factor_sum_product", "factor_sum_product_signed"):
        var = str(draw(_EXPAND_VARS, rng))
        if mode == "factor_sum_product":
            dom = {"int_set": list(range(1, 13))}
        else:
            dom = {"int_set": [n for n in range(-12, 13) if n != 0]}
        a = int(draw(dom, rng))
        b = int(draw(dom, rng))
        # 完全平方（a=b）・平方の差（a=-b）は l9/l10 の題材なので l8 では除外する。
        while a == b or a == -b:
            b = int(draw(dom, rng))
        return _expanded_pair(f"({var}+({a}))*({var}+({b}))")

    if mode == "factor_perfect_square":
        var = str(draw(_EXPAND_VARS, rng))
        a = int(draw({"int_set": [n for n in range(-30, 31) if n != 0]}, rng))
        return _expanded_pair(f"({var}+({a}))**2")

    if mode == "factor_diff_squares":
        var = str(draw(_EXPAND_VARS, rng))
        pp = int(draw({"int_set": list(range(1, 6))}, rng))
        qq = int(draw({"int_set": list(range(1, 16))}, rng))
        return _expanded_pair(f"(({pp})*{var}+({qq}))*(({pp})*{var}-({qq}))")

    if mode == "factor_common_then_formula":
        var = str(draw(_EXPAND_VARS, rng))
        g = int(draw({"int_set": list(range(2, 10))}, rng))
        a = int(draw({"int_set": list(range(1, 13))}, rng))
        return _expanded_pair(f"{g}*({var}+({a}))*({var}-({a}))")

    if mode == "factor_substitution":
        var = str(draw(_EXPAND_VARS, rng))
        pp = int(draw(small_nonzero, rng))
        c = int(draw({"int_set": list(range(1, 13))}, rng))
        csq = c * c
        expr = f"({var}+({pp}))**2-{csq}"
        disp = f"({var}{_const_tail(pp)})² - {csq}"
        return expr, disp

    raise ValueError(f"未知の mode: {mode!r}")


@register_recipe("math.factor_polynomial", provides_concepts=_FACTOR_CONCEPTS)
def factor_polynomial(ctx: CellContext, rng: Rng) -> MR:
    """展開された多項式を因数分解する MR を組む（C3 g3_l7〜l11.calculation）。

    answer-first: 因数分解形を先に構成し展開して given（＝問題の多項式）にする。独立ソルバ
    math.factor_expression が sympy.factor で因数分解し直し、答えを刻印する（double-solve）。
    """
    mode = cast(str, ctx.spec_level.params["mode"])
    expr_str, given_disp = _factor_construct(mode, rng, ctx.spec_level.params)

    solver = REGISTRY.solver("math.factor_expression")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    factored = sympy.sympify(sol.answer.srepr)
    # 恒真: 因数分解形を展開すると与式に一致し、かつ非自明に因数分解されている
    # （＝積または累乗で、与式そのものではない）。
    assert sympy.expand(factored) == sympy.expand(sympy.sympify(expr_str)), (
        f"double-solve 不一致: factor({expr_str}) の展開が与式に戻らない"
    )
    assert factored.is_Mul or factored.is_Pow, (
        f"因数分解が非自明でない（既約）: {expr_str} -> {sol.answer.display}"
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
        params={"expr_str": expr_str, "mode": mode},
        given={"expression": given_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.factor_polynomial"),
    )


@register_recipe("math.expand_product", provides_concepts=_EXPAND_CONCEPTS)
def expand_product(ctx: CellContext, rng: Rng) -> MR:
    """積・平方・分配の形の式を展開する MR を組む（C3 g3_l1〜l6.calculation）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    expr_str, given_disp = _expand_construct(mode, rng, ctx.spec_level.params)

    solver = REGISTRY.solver("math.expand_expression")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 与式を展開すると答えに一致する。
    assert sympy.expand(sympy.sympify(expr_str)) == sympy.sympify(sol.answer.srepr), (
        f"double-solve 不一致: expand({expr_str}) != {sol.answer.srepr}"
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
        params={"expr_str": expr_str, "mode": mode},
        given={"expression": given_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.expand_product"),
    )


# ---------------------------------------------------------------------------
# math.evaluate_arithmetic_via_identity（g3_l12.calculation Lv2/Lv3 用）— C3
# 恒等式を利用して数値計算・式の値を直接求める。answer-first: 恒等式の右辺に使う
# 値（Lv2: a,b／Lv3: s,p）を先に決め、独立ソルバで恒等式の右辺（＝答え）を再計算する。
#   Lv2 "diff_of_squares_arithmetic": a²-b² を (a+b)(a-b) の工夫で計算する。
#     a,b は非負整数・a≠b（a=b だと答えが0になり工夫の意味が薄れるため除外）。
#   Lv3 "symmetric_sum_of_squares"  : x+y=s, xy=p のとき x²+y²=(x+y)²-2xy=s²-2p。
#     x,y の実数解の有無を問わない純粋な恒等式（対称式の変形）。s,p は広い整数範囲。
# ---------------------------------------------------------------------------
_ARITHMETIC_IDENTITY_CONCEPTS = [
    "polynomial.arithmetic_via_diff_of_squares",
    "polynomial.symmetric_expression_from_sum_product",
]


@register_recipe(
    "math.evaluate_arithmetic_via_identity", provides_concepts=_ARITHMETIC_IDENTITY_CONCEPTS
)
def evaluate_arithmetic_via_identity(ctx: CellContext, rng: Rng) -> MR:
    """恒等式を利用して数値計算・式の値を直接求める（answer-first・calculation Lv2/Lv3）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "diff_of_squares_arithmetic":
        return _evaluate_diff_of_squares_arithmetic(ctx, rng, mode)
    if mode == "symmetric_sum_of_squares":
        return _evaluate_symmetric_sum_of_squares(ctx, rng, mode)
    raise ValueError(f"未知の mode: {mode!r}")


def _evaluate_diff_of_squares_arithmetic(ctx: CellContext, rng: Rng, mode: str) -> MR:
    p = ctx.spec_level.params
    # **「工夫して」と言う以上、工夫が効く組だけにする。** a,b を無関係に引いて
    # いたので「80² - 9²」（a+b=89・a-b=71 でどちらもきりが悪い）が出ていた。
    # 実物は 98²-2²（a+b=100）や 51²-49²（a-b=2）のように、和か差の一方が
    # 10の倍数になっていて暗算できる組を選ぶ。
    for _ in range(200):
        a = int(draw(p["a_domain"], rng))
        b_cands = [
            v for v in _domain_candidates(p["b_domain"])
            # b < a（a² - b² が負になる「19² - 31²」は実物の工夫の問題に無い）。
            if 0 < v < a and ((a + v) % 10 == 0 or (a - v) % 10 == 0 or a - v <= 2)
        ]
        if b_cands:
            break
    else:
        raise ValueError("diff_of_squares_arithmetic: 工夫が効く (a,b) を構成できず")
    b = int(draw({"int_set": b_cands}, rng))

    expression = f"{a}² - {b}²"

    solver = REGISTRY.solver("math.evaluate_arithmetic_via_identity")
    sol = cast(Solution, solver(mode, a, b))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.expand((sympy.Integer(a) + sympy.Integer(b)) * (sympy.Integer(a) - sympy.Integer(b)))
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: 構成 a={a},b={b} の a²-b²={expected} != solver 再計算 {sol.answer.srepr}"
    )
    assert [s.op for s in sol.steps] == [
        "factor_difference_of_squares", "multiply_factors",
    ]
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={"mode": mode, "value1": a, "value2": b},
        given={"expression": expression},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_arithmetic_via_identity"),
    )


def _evaluate_symmetric_sum_of_squares(ctx: CellContext, rng: Rng, mode: str) -> MR:
    p = ctx.spec_level.params
    s = int(draw(p["sum_domain"], rng))
    # **実数の x, y が存在する組だけを引く。** 和と積を独立に引いていたので
    # 「x + y = -1, xy = 8 のとき x² + y²」→ 答え -15 が出ていた。
    # 実数の平方の和が負になることはなく、この条件を満たす x, y は存在しない
    # （判別式 s² - 4p < 0）。数学として成り立たない問題だった。
    prod_cands = [v for v in _domain_candidates(p["product_domain"])
                  if s * s - 4 * int(v) >= 0]
    prod = int(draw({"int_set": prod_cands}, rng))

    equation_a = f"x + y = {s}"
    equation_b = f"xy = {prod}"
    expression = "x² + y²"

    solver = REGISTRY.solver("math.evaluate_arithmetic_via_identity")
    sol = cast(Solution, solver(mode, s, prod))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.expand(sympy.Integer(s) ** 2 - 2 * sympy.Integer(prod))
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: 構成 s={s},p={prod} の s²-2p={expected} != solver 再計算 {sol.answer.srepr}"
    )
    assert [s_.op for s_ in sol.steps] == [
        "express_via_elementary_symmetric", "substitute_and_compute",
    ]
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={"mode": mode, "value1": s, "value2": prod},
        given={"equation_a": equation_a, "equation_b": equation_b, "expression": expression},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_arithmetic_via_identity"),
    )


__all__ = [
    "combine_like_terms",
    "add_or_subtract_polynomials",
    "distribute_or_divide",
    "compute_monomial_expression",
    "combine_fractional_expressions",
    "degree_of_expression",
    "solve_for_variable",
    "express_number_property",
    "combine_digit_number",
    "poly_term_recall",
    "classify_monomial_or_polynomial",
    "judge_like_terms",
    "system_term_recall",
    "expand_product",
    "factor_polynomial",
    "evaluate_arithmetic_via_identity",
]
