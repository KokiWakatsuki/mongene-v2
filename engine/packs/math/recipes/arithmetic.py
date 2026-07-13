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


# 小数として提示する既約分数（終端小数・表示文字列を明示）。負符号は draw で別途決める。
_DECIMALS: list[tuple[int, int, str]] = [
    (1, 2, "0.5"), (3, 2, "1.5"), (5, 2, "2.5"), (1, 4, "0.25"), (3, 4, "0.75"),
    (1, 5, "0.2"), (2, 5, "0.4"), (3, 5, "0.6"), (4, 5, "0.8"),
    (1, 10, "0.1"), (3, 10, "0.3"), (7, 10, "0.7"), (9, 10, "0.9"),
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


__all__ = ["compute_signed_arithmetic"]
