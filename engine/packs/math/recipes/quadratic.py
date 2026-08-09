"""2次方程式まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は与式（2次方程式）を構成し、独立ソルバ math.solve_quadratic で解いて答えを刻印する
（double-solve）。given には方程式（display）を出し、答えは解の Tuple（solve 系）または代入値
（evaluate 系）。答えは定数（根号を含みうる）で、問題文の数値はすべて given 由来（whitelist）
＝テンプレは数字を含まないため漏洩は起きない。narration にも数字を書かない。

C3（g3 数と式・2次方程式）クラスタ。乱数は `engine.core.rng.draw` 以外で解釈しない。
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

_X = sympy.Symbol("x")

_QUADRATIC_CONCEPTS = [
    "quadratic.evaluate_solution",
    "quadratic.solve_by_square_root",
    "quadratic.solve_by_formula",
    "quadratic.solve_by_factoring",
    "quadratic.solve_by_choice",
    "quadratic.solve_from_word_setup",
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _is_square(n: int) -> bool:
    return n >= 0 and int(n**0.5) ** 2 == n


def _mono_x(coef: int, power: int) -> str:
    """係数つきの x の項の表示（先頭項用・符号込み）。例: (1,2)->"x²" / (-1,1)->"-x" / (3,2)->"3x²"。"""
    var = "x²" if power == 2 else ("x" if power == 1 else "")
    if power == 0:
        return str(coef)
    if coef == 1:
        return var
    if coef == -1:
        return f"-{var}"
    return f"{coef}{var}"


def _term_tail(coef: int, power: int) -> str:
    """先頭以外の項を符号つきで後置。例: (6,1)->" + 6x" / (-1,1)->" - x" / (2,0)->" + 2"。coef≠0。"""
    var = "x²" if power == 2 else ("x" if power == 1 else "")
    mag = abs(coef)
    body = var if (mag == 1 and power >= 1) else f"{mag}{var}"
    return f" + {body}" if coef > 0 else f" - {body}"


def _quad_lhs(a: int, b: int, c: int) -> str:
    """ax²+bx+c の表示（0 の項は省く・a≠0）。例: (1,6,2)->"x² + 6x + 2" / (2,-8,0)->"2x² - 8x"。"""
    s = _mono_x(a, 2)
    if b != 0:
        s += _term_tail(b, 1)
    if c != 0:
        s += _term_tail(c, 0)
    return s


def _lin_binomial(coef: int, const: int) -> str:
    """(coef·x + const) の表示（かっこ付き・coef≥1）。例: (1,-2)->"(x - 2)" / (2,-1)->"(2x - 1)"。"""
    lead = _mono_x(coef, 1)
    tail = f" + {const}" if const > 0 else f" - {-const}"
    return f"({lead}{tail})"


def _quadratic_construct(mode: str, rng: Rng) -> tuple[str, str, str | None]:
    """mode ごとに (eq_str[solver用・"lhs=rhs"], given_display, value[evaluate用のみ]) を構成する。"""
    small = {"int_set": [n for n in range(-9, 10) if n != 0]}

    if mode == "evaluate_quadratic":
        b = int(draw(small, rng))
        c = int(draw(small, rng))
        k = int(draw({"int_set": list(range(-5, 6))}, rng))
        eq = f"x**2+({b})*x+({c})=0"
        disp = f"{_quad_lhs(1, b, c)} = 0"
        return eq, disp, str(k)

    if mode == "solve_square_form":
        a = int(draw({"int_set": list(range(-9, 10))}, rng))  # 0 も許す（x²=k 形）
        k = int(draw({"int_set": list(range(2, 51))}, rng))
        eq = f"(x-({a}))**2={k}"
        if a == 0:
            disp = f"x² = {k}"
        else:
            inner = f"x - {a}" if a > 0 else f"x + {-a}"
            disp = f"({inner})² = {k}"
        return eq, disp, None

    if mode == "solve_complete_square":
        m = int(draw({"int_set": [n for n in range(-8, 9) if n != 0]}, rng))
        p = 2 * m
        # m²-q>0 かつ非平方（無理数解＝平方完成が必要）になる q を引く。q は広めにとり dup 分散。
        q_dom = {"int_set": [n for n in range(-15, 16) if n != 0]}
        q = int(draw(q_dom, rng))
        while not (m * m - q > 0 and not _is_square(m * m - q)):
            q = int(draw(q_dom, rng))
        eq = f"x**2+({p})*x+({q})=0"
        disp = f"{_quad_lhs(1, p, q)} = 0"
        return eq, disp, None

    if mode in ("solve_formula", "solve_formula_hard"):
        a_dom = list(range(2, 6)) if mode == "solve_formula" else [n for n in range(-5, 6) if abs(n) >= 2]
        a = int(draw({"int_set": a_dom}, rng))
        b = int(draw(small, rng))
        c = int(draw(small, rng))
        # 判別式>0 かつ非平方（無理数解＝解の公式が要る・因数分解で割り切れない）に絞る。
        while not (b * b - 4 * a * c > 0 and not _is_square(b * b - 4 * a * c)):
            b = int(draw(small, rng))
            c = int(draw(small, rng))
        eq = f"({a})*x**2+({b})*x+({c})=0"
        disp = f"{_quad_lhs(a, b, c)} = 0"
        return eq, disp, None

    if mode == "solve_factoring":
        # 整数解 r1,r2 の組で dup 分散するため広め [-15,15] にとる。
        root_dom = {"int_set": [n for n in range(-15, 16) if n != 0]}
        r1 = int(draw(root_dom, rng))
        r2 = int(draw(root_dom, rng))
        while r2 == r1:
            r2 = int(draw(root_dom, rng))
        b = -(r1 + r2)
        c = r1 * r2
        eq = f"x**2+({b})*x+({c})=0"
        disp = f"{_quad_lhs(1, b, c)} = 0"
        return eq, disp, None

    if mode == "solve_factoring_common":
        # 自由度が (a,b) のみで少ないため広くとる（a∈2..6・b∈[-40,40]で 400 通り）。
        a = int(draw({"int_set": list(range(2, 7))}, rng))
        b = int(draw({"int_set": [n for n in range(-40, 41) if n != 0]}, rng))
        eq = f"({a})*x**2+({b})*x=0"
        disp = f"{_quad_lhs(a, b, 0)} = 0"
        return eq, disp, None

    if mode == "solve_rearrange":
        # 最終の整数解 r1,r2 を先に決め、(x+A)(x+B)=C の見かけに再構成する。
        r1 = int(draw(small, rng))
        r2 = int(draw(small, rng))
        while r2 == r1:
            r2 = int(draw(small, rng))
        # 最終方程式は x² -(r1+r2)x + r1 r2 = 0。A を自由に選び B=-(r1+r2)-A、C=A·B - r1·r2。
        a_shift = int(draw(small, rng))
        b_shift = -(r1 + r2) - a_shift
        if b_shift == 0:
            b_shift = 1  # 0 だと (x+A)(x)= の見かけになり退化するので避ける
        c_rhs = a_shift * b_shift - r1 * r2
        eq = f"(x+({a_shift}))*(x+({b_shift}))={c_rhs}"
        left = f"(x + {a_shift})" if a_shift > 0 else f"(x - {-a_shift})"
        right = f"(x + {b_shift})" if b_shift > 0 else f"(x - {-b_shift})"
        disp = f"{left}{right} = {c_rhs}"
        return eq, disp, None

    if mode == "solve_choose":
        m = int(draw({"int_set": list(range(1, 4))}, rng))
        n = int(draw(small, rng))
        k = int(draw({"int_set": [v for v in range(-9, 10) if v != 0]}, rng))
        binom = f"({m})*x+({n})"
        eq = f"({binom})**2={k}*({binom})"
        disp = f"{_lin_binomial(m, n)}² = {k}{_lin_binomial(m, n)}"
        return eq, disp, None

    if mode == "solve_product_form":
        _, c, k = _construct_positive_root_product_form(rng)
        eq = f"(x)*(x+({c}))={k}"
        disp = f"x(x{_term_tail(c, 0)}) = {k}"
        return eq, disp, None

    raise ValueError(f"未知の mode: {mode!r}")


def _construct_positive_root_product_form(rng: Rng) -> tuple[int, int, int]:
    """x(x+c)=k 型（g3_l29/l30）: 正の整数解 x0 と c から k=x0(x0+c) を構成する
    （answer-first）。c,k>0 なら2根の積は -k<0 で異符号になるため、常にちょうど1つの
    正根（=x0）を持つ（鉄則⑤: 場合分け不要な形に構成時から絞る）。
    """
    # 解も定数項も教科書の大きさに収める。x0 を 60 まで振っていたので
    # 「x(x + 9) = 3402」（解 x=54）のように、因数分解で解けない式が出ていた。
    x0 = int(draw({"int_range": [1, 24]}, rng))
    c = int(draw({"int_range": [1, 20]}, rng))
    k = x0 * (x0 + c)
    return x0, c, k


@register_recipe("math.solve_quadratic", provides_concepts=_QUADRATIC_CONCEPTS)
def solve_quadratic(ctx: CellContext, rng: Rng) -> MR:
    """2次方程式を解く／左辺に代入して評価する MR を組む（C3 g3_l24〜l28.calculation）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    eq_str, given_disp, value = _quadratic_construct(mode, rng)

    solver = REGISTRY.solver("math.solve_quadratic")
    sol = cast(Solution, solver(eq_str, mode, value))
    assert isinstance(sol.answer, SymbolicAnswer)

    lhs_s, rhs_s = eq_str.split("=", 1)
    eq_expr = sympy.sympify(lhs_s) - sympy.sympify(rhs_s)
    if value is None:
        # solve 系: 答えの各解が方程式を満たす（恒真・.equals はハングしない堅牢なゼロ判定）。
        roots = sympy.sympify(sol.answer.srepr)
        assert len(roots) >= 1, f"解が求まらない: {eq_str}"
        for r in roots:
            assert eq_expr.subs(_X, r).equals(0), (
                f"double-solve 不一致: {eq_str} に解 {r} を代入して 0 にならない"
            )
    else:
        # evaluate 系: 答えは左辺に value を代入した値に等しい。
        expected = sympy.simplify(eq_expr.subs(_X, sympy.nsimplify(sympy.sympify(value))))
        assert sympy.sympify(sol.answer.srepr) == expected, (
            f"double-solve 不一致: {eq_str} の x={value} 代入値が {sol.answer.display} と不一致"
        )

    given = {"equation": given_disp}
    if value is not None:
        given["input_value"] = f"x = {value}"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value" if value is not None else "solution",
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
        params={"eq_str": eq_str, "mode": mode, "value": value},
        given=given,
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_quadratic"),
    )


_RECTANGLE_AREA_CONCEPTS = ["quadratic.solve_from_rectangle_area"]


@register_recipe("math.quadratic_rectangle_area_value", provides_concepts=_RECTANGLE_AREA_CONCEPTS)
def quadratic_rectangle_area_value(ctx: CellContext, rng: Rng) -> MR:
    """縦 x cm・横 (x+c) cm の長方形の面積条件から x の値（正の解のみ）を求める MR を組む
    （C3 g3_l30.find_value）。answer-first: 正の整数解 x0 と c から面積 k=x0(x0+c) を
    決め、独立ソルバ math.solve_quadratic（mode=solve_product_form_positive_root）で
    正の解のみを再計算する（double-solve）。負の解は長さとして不適のため構造的に除外する。
    """
    mode = "solve_product_form_positive_root"
    _, c, k = _construct_positive_root_product_form(rng)
    eq_str = f"(x)*(x+({c}))={k}"

    solver = REGISTRY.solver("math.solve_quadratic")
    sol = cast(Solution, solver(eq_str, mode, None))
    assert isinstance(sol.answer, SymbolicAnswer)

    lhs_s, rhs_s = eq_str.split("=", 1)
    eq_expr = sympy.sympify(lhs_s) - sympy.sympify(rhs_s)
    root = sympy.sympify(sol.answer.srepr)
    assert eq_expr.subs(_X, root).equals(0), (
        f"double-solve 不一致: {eq_str} に解 {root} を代入して 0 にならない"
    )
    assert root > 0, f"find_value の答えが正でない: {root}"

    condition = f"縦が x cm、横が (x{_term_tail(c, 0)}) cm の長方形の面積が {k}cm² であるとき"

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
        params={"eq_str": eq_str, "mode": mode},
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.quadratic_rectangle_area_value"),
    )


__all__ = ["solve_quadratic", "quadratic_rectangle_area_value"]
