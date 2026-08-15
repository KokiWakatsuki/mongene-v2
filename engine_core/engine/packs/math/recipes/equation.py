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
    "equation.solve_by_clear_denominators",
    "equation.solve_proportion",
    "equation.solve_proportion_linear",
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

    if mode == "clear_denominators_two":
        # (x + p)/d1 ± (m·x + s)/d2 = c（かっこ＋分数）。answer-first: 各項が x0 で整数値
        # （term1(x0)=kp・term2(x0)=ks）になるよう小さな p・s を p≡-x0(mod d1)・s≡-m·x0(mod d2)
        # を満たす候補から引き、c=kp+sgn·ks。分母を払った後の x 係数（d2+sgn·m·d1）≠0 で非退化。
        denoms = [int(v) for v in cast("list[int]", p["denominator_set"])]
        const_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["num_const_domain"])) if v != 0]
        for _ in range(200):
            x0 = int(draw(p["solution_domain"], rng))
            d1 = int(draw({"int_set": denoms}, rng))
            d2 = int(draw({"int_set": [d for d in denoms if d != d1]}, rng))
            m = int(draw(p["num_coeff_domain"], rng))
            sgn = int(draw({"int_set": [1, -1]}, rng))
            if d2 + sgn * m * d1 == 0:  # 分母を払うと x が消える退化を回避
                continue
            # 分子の定数は小さく保ちつつ、各項が x0 で整数値になる（＝割り切れる）ものだけ許す。
            p_cands = [v for v in const_cands if (x0 + v) % d1 == 0]
            s_cands = [v for v in const_cands if (m * x0 + v) % d2 == 0]
            if not p_cands or not s_cands:
                continue
            p_const = int(draw({"int_set": p_cands}, rng))
            s_const = int(draw({"int_set": s_cands}, rng))
            kp = (x0 + p_const) // d1
            ks = (m * x0 + s_const) // d2
            c = kp + sgn * ks
            # 答え x0 が表示中の整数と一致すると（whitelist で gate は素通りだが）教材上の漏洩。
            shown = {abs(p_const), d1, m, abs(s_const), d2, abs(c)}
            if abs(x0) in shown:
                continue
            num1 = _fmt_poly_x_terms([(1, 1), (p_const, 0)])
            num2 = _fmt_poly_x_terms([(m, 1), (s_const, 0)])
            op = "+" if sgn > 0 else "-"
            eq_str = f"(x+({p_const}))/({d1}) {op} ({m}*x+({s_const}))/({d2}) = ({c})"
            eq_disp = f"({num1})/{d1} {op} ({num2})/{d2} = {c}"
            return _build_eq(eq_str, eq_disp, mode, ctx)
        raise ValueError("clear_denominators_two: 非退化・非漏洩の方程式を構成できず")

    if mode == "cross_multiply":
        # a : b = c : x（比例式・たすきがけ）。answer-first: a,b,t から c=a·t・x0=b·t。
        # a≠b で x0≠c、t≥2 で x0≠b。solver へは外項の積＝内項の積の線形式 a·x=b·c を渡す。
        ratios = [v for v in _domain_candidates(cast("dict[str, object]", p["ratio_domain"])) if v != 0]
        for _ in range(200):
            a = int(draw({"int_set": ratios}, rng))
            b = int(draw({"int_set": [v for v in ratios if v != a]}, rng))
            t = int(draw(p["scale_domain"], rng))
            c = a * t
            x0 = b * t
            if x0 in {a, b, c}:  # 答えが表示中の数と一致する漏洩を回避
                continue
            eq_str = f"({a})*x = ({b})*({c})"
            eq_disp = f"{a} : {b} = {c} : x"
            return _build_eq(eq_str, eq_disp, mode, ctx)
        raise ValueError("cross_multiply: 非漏洩の比例式を構成できず")

    if mode == "cross_multiply_expand":
        # (x + p) : b = c : d（文字を含む項の比例式）。answer-first: x0 と小さな p を先に決め、
        # 左辺の分子値 N=x0+p（>0）と左辺分母 b から右比を c:d = 既約(N:b) で得る。
        # solver へはクロス乗算した線形式 d·(x+p)=b·c を渡す（表示は比例式・式は線形で別物）。
        const_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["num_const_domain"])) if v != 0]
        denom_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["denom_domain"])) if v > 0]
        for _ in range(200):
            x0 = int(draw(p["solution_domain"], rng))
            p_const = int(draw({"int_set": const_cands}, rng))
            n = x0 + p_const
            if n <= 0:  # 比の左項 N は正（負の比を避ける）
                continue
            b = int(draw({"int_set": denom_cands}, rng))
            g = sympy.igcd(n, b)
            c = n // g
            d = b // g
            if abs(x0) in {abs(p_const), b, c, d}:
                continue
            num = _fmt_poly_x_terms([(1, 1), (p_const, 0)])
            eq_str = f"({d})*(x+({p_const})) = ({b})*({c})"
            eq_disp = f"({num}) : {b} = {c} : {d}"
            return _build_eq(eq_str, eq_disp, mode, ctx)
        raise ValueError("cross_multiply_expand: 非退化・非漏洩の比例式を構成できず")

    raise ValueError(f"未知の mode: {mode!r}")


__all__ = ["compute_linear_equation"]
