"""正の数・負の数の四則（数値式の評価）まわりの recipe（構成的生成・実装設計 §6.1）。

乱数は `draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した与式は独立ソルバ
`math.evaluate_numeric_expression` で再評価し、答えの一致を確認する（double-solve）。

C1（g1 数と式・正負の数）の計算セルを1つの汎用 recipe に集約する:
  `math.compute_signed_arithmetic(ctx, rng)` が mode ごとに演算対象の数（整数・分数・
  小数）を引いて与式を組み立てる。mode は spec_level.params["mode"]（各 unit の各 level に
  一意）。level_sep は solver 側の mode 別 op 列で担保する。答えの数は問題文（＝given のみ）
  の数値がすべて whitelist されるため、定数答えでも G-Q5t 漏洩は起きない（§引継 3）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript(n: int) -> str:
    """指数を上付き数字にする（例 2 -> "²"）。extract_numbers 非抽出＝次数の漏洩なし。"""
    return str(n).translate(_SUPERSCRIPT)


def _fmt_power_base(value: sympy.Rational, magnitude_disp: str) -> str:
    """累乗の底の表示（負・非整数はかっこで囲む＝底ごと累乗を明示）。

    例: Integer(2)->"2" / Integer(-3)->"(-3)" / Rational(-1,2)->"(-1/2)" / Rational(2,3)->"(2/3)"。
    """
    signed = _fmt_signed(value, magnitude_disp)
    if value < 0 or not value.is_Integer:
        return f"({signed})"
    return signed


# 小数として提示する既約分数（終端小数・表示文字列を明示）。負符号は draw で別途決める。
_DECIMALS: list[tuple[int, int, str]] = [
    (1, 2, "0.5"), (3, 2, "1.5"), (5, 2, "2.5"), (7, 2, "3.5"), (9, 2, "4.5"),
    (1, 4, "0.25"), (3, 4, "0.75"), (5, 4, "1.25"), (7, 4, "1.75"),
    (1, 5, "0.2"), (2, 5, "0.4"), (3, 5, "0.6"), (4, 5, "0.8"),
    (6, 5, "1.2"), (7, 5, "1.4"), (8, 5, "1.6"), (11, 5, "2.2"),
    (1, 10, "0.1"), (3, 10, "0.3"), (7, 10, "0.7"), (9, 10, "0.9"),
    (11, 10, "1.1"), (13, 10, "1.3"), (17, 10, "1.7"), (19, 10, "1.9"),
    (1, 8, "0.125"), (3, 8, "0.375"), (5, 8, "0.625"),
]


def _fmt_signed(value: sympy.Rational, magnitude_disp: str) -> str:
    """符号つき数の表示（負なら先頭に - ・分数/小数は magnitude_disp を使う）。

    magnitude_disp は絶対値の表示（"7"・"2/3"・"0.5"）。value<0 なら "-" を前置する。
    """
    return f"-{magnitude_disp}" if value < 0 else magnitude_disp


def _paren_if_neg(value: sympy.Rational, signed_disp: str) -> str:
    """負の数はかっこで囲む（例 -7 -> "(-7)" / 7 -> "7"）。"""
    return f"({signed_disp})" if value < 0 else signed_disp


def _draw_int_operand(rng: Rng, domain: object) -> tuple[sympy.Rational, str]:
    """整数の被演算子を引く（value, 絶対値表示）。"""
    n = int(draw(domain, rng))
    v = sympy.Integer(n)
    return v, str(abs(n))


def _draw_frac_operand(rng: Rng, domain: object) -> tuple[sympy.Rational, str]:
    """分数の被演算子を引く（既約分数・value, 絶対値表示 "p/q"）。"""
    r = draw(domain, rng)
    assert isinstance(r, sympy.Rational)
    return r, f"{abs(r.p)}/{r.q}"


def _draw_decimal_operand(rng: Rng) -> tuple[sympy.Rational, str]:
    """小数として提示する被演算子を引く（value, 絶対値表示 "0.5" 等）。"""
    p, q, disp = cast("tuple[int, int, str]", draw(_DECIMALS, rng))
    sign = int(draw([1, -1], rng))
    r = sympy.Rational(sign * p, q)
    return r, disp


def _draw_operand(rng: Rng, kind: str, p: dict[str, object]) -> tuple[sympy.Rational, str]:
    """kind（"int"/"frac"/"dec"）に応じて1つの被演算子を引く（value, 絶対値表示）。"""
    if kind == "int":
        return _draw_int_operand(rng, p["int_domain"])
    if kind == "frac":
        return _draw_frac_operand(rng, p["frac_domain"])
    if kind == "dec":
        return _draw_decimal_operand(rng)
    raise ValueError(f"未知の operand kind: {kind!r}")


def _build(expr_str: str, given_display: str, mode: str, ctx: CellContext) -> MR:
    """与式文字列と表示から MR を組み立てる（double-solve で答え一致を確認）。"""
    solver = REGISTRY.solver("math.evaluate_numeric_expression")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.sympify(expr_str, rational=True)
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

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
        params={"expr_str": expr_str, "mode": mode, "given_disp": given_display},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_signed_arithmetic"),
    )


# 各 unit の各 level が宣言する concept をすべて列挙（R6: family の concept_tags は
# この集合の部分集合であること）。recipe は _effective_concept_tags で family の宣言を返す。
_SIGNED_ARITHMETIC_CONCEPTS = [
    "signed_number.add_pair",
    "signed_number.add_terms",
    "signed_number.subtract_pair",
    "signed_number.subtract_terms",
    "signed_number.multiply_pair",
    "signed_number.multiply_chain",
    "signed_number.divide_pair",
    "signed_number.divide_chain",
    "signed_number.add_sub_terms_basic",
    "signed_number.add_sub_terms_rational",
    "signed_number.power_single",
    "signed_number.power_sign_contrast",
    "signed_number.four_operations",
    "signed_number.distributive_trick",
]


@register_recipe("math.compute_signed_arithmetic", provides_concepts=_SIGNED_ARITHMETIC_CONCEPTS)
def compute_signed_arithmetic(ctx: CellContext, rng: Rng) -> MR:
    """正負の数の四則（数値式）を構成して評価する（構成的生成・calculation）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])

    if mode == "addition_pair":
        # 2数の加法（整数）。和が 0 に退化しないよう2つ目を絞る。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        cands = [n for n in _int_domain_values(p["int_domain"]) if n != 0 and (v1 + n) != 0]
        n2 = int(draw({"int_set": cands}, rng))
        v2, m2 = sympy.Integer(n2), str(abs(n2))
        expr_str = f"({v1})+({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}+{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "addition_terms":
        # 3項の加法（整数・分数・小数の混在）。和が 0 に退化しないよう最後の項を絞る。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds[:-1]]
        running = sum((v for v, _ in ops), sympy.Integer(0))
        last = _draw_nonzero_last(rng, kinds[-1], p, running)
        ops.append(last)
        expr_str = "+".join(f"({v})" for v, _ in ops)
        disp = "+".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode == "subtraction_pair":
        # 2数の減法（整数）。差が 0 に退化しないよう絞る。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        cands = [n for n in _int_domain_values(p["int_domain"]) if n != 0 and (v1 - n) != 0]
        n2 = int(draw({"int_set": cands}, rng))
        v2, m2 = sympy.Integer(n2), str(abs(n2))
        expr_str = f"({v1})-({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}-{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "subtraction_terms":
        # 3項の減法（整数・分数・小数の混在）。op1 - op2 - op3。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds]
        # 退化（答え 0）を避けるため最後の項を再抽選で調整。
        while (ops[0][0] - ops[1][0] - ops[2][0]) == 0:
            ops[2] = _draw_operand(rng, kinds[2], p)
        expr_str = f"({ops[0][0]})-({ops[1][0]})-({ops[2][0]})"
        disp = "-".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode in ("add_sub_terms", "add_sub_terms_rational"):
        # 加法と減法の混じった計算（項の概念）。各項に + / - の演算子をつけて並べる。
        # Lv1（add_sub_terms・整数）/ Lv2（add_sub_terms_rational・分数小数を含む）。
        kinds = list(cast("list[str]", p["term_kinds"]))
        terms, opsyms, value = _draw_add_sub_terms(rng, kinds, p)
        expr_str = f"({terms[0][0]})" + "".join(
            f"{opsyms[i]}({terms[i + 1][0]})" for i in range(len(opsyms))
        )
        disp = _paren_if_neg(terms[0][0], _fmt_signed(terms[0][0], terms[0][1]))
        for i, opsym in enumerate(opsyms):
            v, m = terms[i + 1]
            disp += opsym + _paren_if_neg(v, _fmt_signed(v, m))
        assert value == sympy.sympify(expr_str, rational=True)
        return _build(expr_str, disp, mode, ctx)

    if mode == "four_operations":
        # 四則の混じった計算（累乗・かっこを含む）。骨格 A - (B)²×C + D÷E（D=k·E で割り切れる）。
        big_a = int(draw(p["lead_domain"], rng))  # 先頭項（正）
        b = int(draw(p["base_domain"], rng))  # 累乗の底（|b|≥2）
        c = int(draw(p["multiplier_domain"], rng))  # ≥2
        e = int(draw(p["divisor_domain"], rng))  # |e|≥2
        k = int(draw(p["quotient_domain"], rng))  # 商（≠0）
        dd = k * e  # 割り切れる被除数
        expr_str = f"({big_a})-({b})**2*({c})+({dd})/({e})"
        disp = (
            f"{big_a}-{_paren_if_neg(sympy.Integer(b), str(b))}{_superscript(2)}×{c}"
            f"+{_paren_if_neg(sympy.Integer(dd), str(dd))}÷{_paren_if_neg(sympy.Integer(e), str(e))}"
        )
        return _build(expr_str, disp, mode, ctx)

    if mode == "distributive_trick":
        # 分配法則で工夫して計算。base=(R+off)、multiplier m。value=base·m=(R·m)+(off·m)。
        r = int(draw(p["round_domain"], rng))  # きりのよい数（10,100,…）
        off = int(draw(p["offset_domain"], rng))  # 小さな数（±1..±4, ≠0）
        mul = int(draw(p["multiplier_domain"], rng))  # かける数（≥2）
        base = r + off
        expr_str = f"({base})*({mul})"
        disp = f"{base}×{mul}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "power_single":
        # 累乗の計算。底は整数・分数・小数（符号つき）、指数 n。底の種類で dup を分散する。
        kind = str(draw(p["base_kinds"], rng))
        bval, bmag = _draw_operand(rng, kind, p)
        n = int(draw(p["exponent_domain"], rng))
        expr_str = f"({bval})**{n}"
        disp = f"{_fmt_power_base(bval, bmag)}{_superscript(n)}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "power_sign_contrast":
        # (-a)^n と -a^n の区別。整数底のみ form=neg_inside（-a^n）を出し、指数のかかる範囲を
        # 見分けさせる。分数・小数底は neg_outside（かっこつき）で dup 分散のみに使う。
        kind = str(draw(p["base_kinds"], rng))
        bval, bmag = _draw_operand(rng, kind, p)
        n = int(draw(p["exponent_domain"], rng))
        form = str(draw(["neg_outside", "neg_inside"], rng)) if kind == "int" else "neg_outside"
        if form == "neg_inside":
            # 指数は数だけにかかり、先頭の - は最後（常に負）。底の絶対値を使う。
            expr_str = f"-{bmag}**{n}"
            disp = f"-{bmag}{_superscript(n)}"
        else:
            # 底ごと累乗（負の底はかっこで囲む）。分数・小数底もここで扱う。
            neg_val = -abs(bval)
            expr_str = f"({neg_val})**{n}"
            disp = f"(-{bmag}){_superscript(n)}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "multiplication_pair":
        # 2数の乗法（整数）。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        v2, m2 = _draw_int_operand(rng, p["int_domain"])
        expr_str = f"({v1})*({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}×{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "multiplication_chain":
        # 3数の乗法（整数・分数・小数の混在）。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds]
        expr_str = "*".join(f"({v})" for v, _ in ops)
        disp = "×".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode == "divide_pair":
        # 2数の除法（整数・割り切れる）。answer-first: 商 q と除数 d を引き、被除数 q·d を作る。
        d = int(draw(p["divisor_domain"], rng))
        q = int(draw(p["quotient_domain"], rng))
        dividend = q * d
        v1, m1 = sympy.Integer(dividend), str(abs(dividend))
        v2, m2 = sympy.Integer(d), str(abs(d))
        expr_str = f"({v1})/({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}÷{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "divide_chain":
        # 分数の乗除混在（逆数）。op1 ÷ op2 × op3。分母が 0 にならないよう frac は既約非零。
        f1 = _draw_frac_operand(rng, p["frac_domain"])
        f2 = _draw_frac_operand(rng, p["frac_domain"])
        f3 = _draw_frac_operand(rng, p["frac_domain"])
        expr_str = f"({f1[0]})/({f2[0]})*({f3[0]})"
        disp = (
            f"{_paren_if_neg(f1[0], _fmt_signed(f1[0], f1[1]))}"
            f"÷{_paren_if_neg(f2[0], _fmt_signed(f2[0], f2[1]))}"
            f"×{_paren_if_neg(f3[0], _fmt_signed(f3[0], f3[1]))}"
        )
        return _build(expr_str, disp, mode, ctx)

    raise ValueError(f"未知の mode: {mode!r}")


def _int_domain_values(domain: object) -> list[int]:
    """int_range/int_set の候補整数を列挙する（exclude 適用）。"""
    d = cast("dict[str, object]", domain)
    if "int_range" in d:
        lo, hi = cast("list[int]", d["int_range"])
        vals = list(range(int(lo), int(hi) + 1))
    elif "int_set" in d:
        vals = [int(v) for v in cast("list[int]", d["int_set"])]
    else:
        raise ValueError(f"未対応 int domain: {domain!r}")
    excl = {int(v) for v in cast("list[int]", d.get("exclude", []))}
    return [v for v in vals if v not in excl]


def _draw_nonzero_last(
    rng: Rng, kind: str, p: dict[str, object], running: sympy.Rational
) -> tuple[sympy.Rational, str]:
    """和が 0 にならない最後の項を引く（有界リトライ）。"""
    for _ in range(200):
        v, m = _draw_operand(rng, kind, p)
        if (running + v) != 0:
            return v, m
    raise ValueError("nonzero last term を確保できず")


def _draw_add_sub_terms(
    rng: Rng, kinds: list[str], p: dict[str, object]
) -> tuple[list[tuple[sympy.Rational, str]], list[str], sympy.Rational]:
    """加減混合の項と演算子（+/-）を引く（結果が 0 に退化しないよう有界リトライ）。

    戻り値: (項の [(value, 絶対値表示)] 列, 各項間の演算子 "+"/"-" 列, 評価値)。
    """
    for _ in range(200):
        terms = [_draw_operand(rng, k, p) for k in kinds]
        opsyms = [str(draw(["+", "-"], rng)) for _ in range(len(kinds) - 1)]
        # 加減が「混じる」よう + と - を両方含める（加減混合の忠実性）。
        if "+" not in opsyms or "-" not in opsyms:
            continue
        value = terms[0][0]
        for opsym, (tv, _) in zip(opsyms, terms[1:]):
            value = value + tv if opsym == "+" else value - tv
        if value != 0:
            return terms, opsyms, value
    raise ValueError("非退化の加減混合を確保できず")


__all__ = ["compute_signed_arithmetic"]
