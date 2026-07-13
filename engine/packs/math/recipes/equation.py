"""一次方程式（1変数）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した方程式は
独立ソルバ `math.solve_linear_equation` で解き直し、解の一致を確認する（double-solve）。

C1（g1 数と式・一次方程式）の解法セルを1つの汎用 recipe に集約する（arithmetic.py の
`compute_signed_arithmetic` と同型）:
  `math.compute_linear_equation(ctx, rng)` が answer-first で解 x0 と係数を引いて方程式を組む。
  mode は spec_level.params["mode"]（各 unit の各 level に一意）。level_sep は solver 側の
  mode 別 op 列で担保する。答えは解 x=定数。given の数値はすべて whitelist（両符号）される
  ため G-Q5t は漏洩しない。narration には数字を書かない。
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
from engine.packs.math.recipes.polynomial import (
    _domain_candidates,
    _fmt_poly_x_terms,
    _sympy_poly_x,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


_EQUATION_CONCEPTS = [
    "equation.solve_by_equality_property",
    "equation.solve_by_equality_property_multi",
    "equation.solve_by_transpose",
    "equation.solve_by_transpose_both_sides",
    "equation.solve_by_expand_parens",
    "equation.solve_word_price",
    "equation.solve_shortage",
    "equation.solve_speed_fraction",
]


def _fmt_paren_add(inner: str, k: int) -> str:
    """かっこ内の定数項を "x + k" / "x - |k|" 形にする（k≠0 前提）。"""
    return f"x + {k}" if k > 0 else f"x - {abs(k)}"


def _build(
    lhs_terms: list[tuple[int, int]],
    rhs_terms: list[tuple[int, int]],
    mode: str,
    ctx: CellContext,
) -> MR:
    """左辺・右辺の項（(係数,指数)列）から方程式 MR を組み立てる（多項式表示）。"""
    equation_str = f"{_sympy_poly_x(lhs_terms)}={_sympy_poly_x(rhs_terms)}"
    equation_display = f"{_fmt_poly_x_terms(lhs_terms)} = {_fmt_poly_x_terms(rhs_terms)}"
    return _build_eq(equation_str, equation_display, mode, ctx)


def _build_eq(equation_str: str, equation_display: str, mode: str, ctx: CellContext) -> MR:
    """方程式の文字列と表示から MR を組み立てる（double-solve で解の一致を確認）。"""
    solver = REGISTRY.solver("math.solve_linear_equation")
    sol = cast(Solution, solver(equation_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 答えは定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols, "解が定数にならなかった"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
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
        params={"equation_str": equation_str, "mode": mode, "given_disp": equation_display},
        given={"equation": equation_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_linear_equation"),
    )


@register_recipe("math.compute_linear_equation", provides_concepts=_EQUATION_CONCEPTS)
def compute_linear_equation(ctx: CellContext, rng: Rng) -> MR:
    """一次方程式を構成して解く（answer-first・calculation）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])
    # const_domain を使うのは移項・等式・かっこ展開系のみ（利用系 l25/l27 は持たない）。
    const_cands = (
        [v for v in _domain_candidates(cast("dict[str, object]", p["const_domain"])) if v != 0]
        if "const_domain" in p
        else []
    )

    if mode in ("equality_add", "transpose_constant"):
        # x + b = c（1手で解ける・等式の性質 or 移項）。answer-first: 解 x0 と b から c=x0+b。
        # RHS が 0 になると解きかけに見えるため c≠0 を保証（b ≠ -x0）。
        x0 = int(draw(p["solution_domain"], rng))
        b = int(draw({"int_set": [v for v in const_cands if x0 + v != 0]}, rng))
        c = x0 + b
        return _build([(1, 1), (b, 0)], [(c, 0)], mode, ctx)

    if mode == "equality_multi":
        # a·x + b = c（|a|≥2・等式の性質を2回）。answer-first: c = a·x0 + b。c≠0 を保証。
        x0 = int(draw(p["solution_domain"], rng))
        a = int(draw(p["coeff_domain"], rng))
        b = int(draw({"int_set": [v for v in const_cands if a * x0 + v != 0]}, rng))
        c = a * x0 + b
        return _build([(a, 1), (b, 0)], [(c, 0)], mode, ctx)

    if mode == "transpose_both":
        # a·x + b = c·x + d（両辺に文字・複数回移項）。answer-first: d = (a-c)·x0 + b（a≠c）。
        x0 = int(draw(p["solution_domain"], rng))
        a = int(draw(p["coeff_domain"], rng))
        c = int(draw({"int_set": [v for v in _domain_candidates(cast("dict[str, object]", p["rhs_coeff_domain"])) if v != 0 and v != a]}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        d = (a - c) * x0 + b
        return _build([(a, 1), (b, 0)], [(c, 1), (d, 0)], mode, ctx)

    if mode == "expand_parens":
        # a(x + p) = c·x + q（かっこ展開）。answer-first: q=(a-c)·x0 + a·p（a≠c で非退化）。
        x0 = int(draw(p["solution_domain"], rng))
        a = int(draw(p["coeff_domain"], rng))  # |a|≥2
        pp = int(draw({"int_set": const_cands}, rng))
        c = int(draw({"int_set": [v for v in _domain_candidates(cast("dict[str, object]", p["rhs_coeff_domain"])) if v != 0 and v != a]}, rng))
        q = (a - c) * x0 + a * pp
        lhs_disp = f"{a}({_fmt_paren_add('x', pp)})"
        rhs_disp = _fmt_poly_x_terms([(c, 1), (q, 0)])
        eq_str = f"({a})*(x+({pp})) = ({c})*x+({q})"
        return _build_eq(eq_str, f"{lhs_disp} = {rhs_disp}", mode, ctx)

    if mode == "word_linear":
        # a·x + b(k - x) = c（代金の利用）。answer-first: c=(a-b)·x0 + b·k（a≠b・x0 は 1..k-1）。
        a = int(draw(p["price_domain"], rng))
        b = int(draw({"int_set": [v for v in _domain_candidates(cast("dict[str, object]", p["price_domain"])) if v != a]}, rng))
        k = int(draw(p["count_domain"], rng))
        x0 = int(draw({"int_set": list(range(1, k))}, rng))
        c = (a - b) * x0 + b * k
        eq_str = f"({a})*x+({b})*(({k})-x) = ({c})"
        eq_disp = f"{a}x + {b}({k} - x) = {c}"
        return _build_eq(eq_str, eq_disp, mode, ctx)

    if mode == "clear_denominators_simple":
        # x/p + x/q = r（分数係数・速さの利用）。answer-first: x0=lcm(p,q)·t で r を整数に。
        denoms = [int(v) for v in cast("list[int]", p["denominator_set"])]
        dp = int(draw({"int_set": denoms}, rng))
        dq = int(draw({"int_set": [d for d in denoms if d != dp]}, rng))
        big = int(sympy.ilcm(dp, dq))
        t = int(draw(p["scale_domain"], rng))
        x0 = big * t
        r = x0 // dp + x0 // dq
        eq_str = f"x/({dp}) + x/({dq}) = ({r})"
        eq_disp = f"x/{dp} + x/{dq} = {r}"
        return _build_eq(eq_str, eq_disp, mode, ctx)

    raise ValueError(f"未知の mode: {mode!r}")


__all__ = ["compute_linear_equation"]
