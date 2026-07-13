"""多項式（式の計算）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は「答え（または綺麗な中核値）を先に決め、問題を逆算する」登録済み関数。
乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した
答えは独立ソルバ（`engine.packs.math.solvers.polynomial`）で再計算し一致を確認する。

C2（数と式）クラスタの初セル: g2_l2.calculation（同類項をまとめる）Lv1/Lv2。
`linear.py` は並行編集中のため触らず、本ファイルに独立ヘルパ（_fmt_term 等）を
新設する（linear.py からの import は可・編集は不可）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

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
                result_display="文字の部分が同じ項どうしを見分ける",
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


__all__ = [
    "combine_like_terms",
    "add_or_subtract_polynomials",
    "distribute_or_divide",
    "compute_monomial_expression",
    "combine_fractional_expressions",
]
