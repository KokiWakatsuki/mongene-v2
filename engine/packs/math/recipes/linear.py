"""一次関数まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は「答え（または綺麗な中核値）を先に決め、問題を逆算する」登録済み関数。
乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。
構成した答えは独立ソルバ（`engine.packs.math.solvers.linear`、Task5a 完成済み）で
再計算し一致を確認する（不一致は recipe のバグ = 即例外。§6.2 double-solve の
recipe 側担保）。

M0 縦串: g2_l25.find_value（Lv2/Lv3）・g2_l24.find_value（Lv1/Lv3）・
g2_l25.graph_table（Lv2）。
"""
from __future__ import annotations

from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many

# 提供概念（recipe が「提供できる概念タグ集合」を宣言。spec_lint R6 の題材ズレ検出用）。
_LINEAR_FROM_TWO_POINTS_CONCEPTS = [
    "linear_function.slope_from_two_points",
    "linear_function.intercept_from_point",
    "linear_function.expression_from_two_points",
]
_LINEAR_FROM_SLOPE_POINT_CONCEPTS = [
    "linear_function.expression_from_slope_point",
    "linear_function.intercept_from_point",
]
_LINEAR_FROM_PARALLEL_CONCEPTS = [
    "linear_function.parallel_condition",
    "linear_function.expression_from_slope_point",
]
_GRAPH_READ_TWO_POINTS_CONCEPTS = [
    "graph.read_lattice_points",
]


def _fmt_point(p: tuple[Any, Any]) -> str:
    x, y = p
    return f"({sympy.sstr(sympy.nsimplify(x))}, {sympy.sstr(sympy.nsimplify(y))})"


def _fmt_number(v: Any) -> str:
    return str(sympy.sstr(sympy.nsimplify(v)))


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    """spec_level.concept_tags が非空ならそれを、無ければ spec_family.concepts_default を使う。"""
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# math.linear_from_two_points（g2_l25.find_value 用）
# ---------------------------------------------------------------------------
@register_recipe("math.linear_from_two_points", provides_concepts=_LINEAR_FROM_TWO_POINTS_CONCEPTS)
def linear_from_two_points(ctx: CellContext, rng: Rng) -> MR:
    """2点から1次関数の式を求める（answer-first）。

    整数傾き a・整数切片 b を先に選び、格子点2つを直線上に逆算する。独立ソルバ
    `math.linear_expr_from_two_points` で解いて steps を得て、答えの一致を assert する。
    """
    p = ctx.spec_level.params
    method: str = p["method"]

    a = draw(p["slope_domain"], rng)
    b = draw({"int_range": [-8, 8]}, rng)
    (x1, _y1), (x2, _y2) = draw_many(p["point_domain"], rng, k=2)

    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    x1_s, x2_s = sympy.nsimplify(x1), sympy.nsimplify(x2)
    pts = [(x1_s, a_s * x1_s + b_s), (x2_s, a_s * x2_s + b_s)]

    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = cast(Solution, solver(pts[0], pts[1], method))
    assert isinstance(sol.answer, SymbolicAnswer)  # 縦串 find_value は必ず symbolic

    expected_expr = a_s * sympy.Symbol("x") + b_s
    assert sol.answer.srepr == sympy.srepr(expected_expr), (
        f"double-solve 不一致: recipe が構成した式 {expected_expr} != solver 再計算 {sol.answer.srepr}"
    )

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
        seed=0,  # pipeline が上書きする（Task4 の仕様）
        params={"a": str(a_s), "b": str(b_s), "pts": [str(pts[0]), str(pts[1])], "method": method},
        given={"point_a": _fmt_point(pts[0]), "point_b": _fmt_point(pts[1])},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.linear_from_two_points"),
    )


# ---------------------------------------------------------------------------
# math.linear_from_slope_point（g2_l24.find_value Lv1 用）
# ---------------------------------------------------------------------------
@register_recipe("math.linear_from_slope_point", provides_concepts=_LINEAR_FROM_SLOPE_POINT_CONCEPTS)
def linear_from_slope_point(ctx: CellContext, rng: Rng) -> MR:
    """傾きと1点から1次関数の式を求める（answer-first）。

    傾き a・通る点 (px, py) を先に選び、独立ソルバ `math.linear_expr_from_slope_point`
    で切片 b と steps を得る。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    point = draw(p["point_domain"], rng)

    a_s = sympy.nsimplify(a)
    px, py = sympy.nsimplify(point[0]), sympy.nsimplify(point[1])
    b_expected = py - a_s * px

    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol = cast(Solution, solver(a_s, (px, py)))
    assert isinstance(sol.answer, SymbolicAnswer)  # 縦串 find_value は必ず symbolic

    expected_expr = a_s * sympy.Symbol("x") + b_expected
    assert sol.answer.srepr == sympy.srepr(expected_expr), (
        f"double-solve 不一致: recipe が構成した式 {expected_expr} != solver 再計算 {sol.answer.srepr}"
    )

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
        params={"a": str(a_s), "point": str((px, py))},
        given={"slope": _fmt_number(a_s), "point_a": _fmt_point((px, py))},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.linear_from_slope_point"),
    )


# ---------------------------------------------------------------------------
# math.linear_from_parallel_condition（g2_l24.find_value Lv3 用）
# ---------------------------------------------------------------------------
@register_recipe("math.linear_from_parallel_condition", provides_concepts=_LINEAR_FROM_PARALLEL_CONCEPTS)
def linear_from_parallel_condition(ctx: CellContext, rng: Rng) -> MR:
    """平行元の直線の傾きと通る1点から1次関数の式を求める（answer-first）。

    平行元の直線の傾き a・切片 b0（given に表示する平行元の式用）と、求める直線が
    通る点 (px, py) を先に選ぶ。独立ソルバ `math.linear_expr_parallel_through_point`
    で答えを得る。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b0 = draw(p.get("parallel_intercept_domain", {"int_range": [-8, 8]}), rng)
    point = draw(p["point_domain"], rng)

    a_s = sympy.nsimplify(a)
    b0_s = sympy.nsimplify(b0)
    px, py = sympy.nsimplify(point[0]), sympy.nsimplify(point[1])
    b_expected = py - a_s * px

    solver = REGISTRY.solver("math.linear_expr_parallel_through_point")
    sol = cast(Solution, solver(a_s, (px, py)))
    assert isinstance(sol.answer, SymbolicAnswer)  # 縦串 find_value は必ず symbolic

    expected_expr = a_s * sympy.Symbol("x") + b_expected
    assert sol.answer.srepr == sympy.srepr(expected_expr), (
        f"double-solve 不一致: recipe が構成した式 {expected_expr} != solver 再計算 {sol.answer.srepr}"
    )

    parallel_line_display = _format_parallel_line_display(a_s, b0_s)

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
        params={"a": str(a_s), "b0": str(b0_s), "point": str((px, py))},
        given={"condition": parallel_line_display, "point_a": _fmt_point((px, py))},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.linear_from_parallel_condition"),
    )


def _format_parallel_line_display(a: sympy.Expr, b: sympy.Expr) -> str:
    """平行元の直線 y = ax + b の表示形（given に載せる文字列）。"""
    if a == 1:
        a_part = "x"
    elif a == -1:
        a_part = "-x"
    else:
        a_part = f"{sympy.sstr(a)}x"
    if b == 0:
        rhs = a_part
    elif b > 0:
        rhs = f"{a_part} + {sympy.sstr(b)}"
    else:
        rhs = f"{a_part} - {sympy.sstr(-b)}"
    return f"y = {rhs}"


# ---------------------------------------------------------------------------
# math.graph_read_two_points（g2_l25.graph_table Lv2 用）
# ---------------------------------------------------------------------------
@register_recipe("math.graph_read_two_points", provides_concepts=_GRAPH_READ_TWO_POINTS_CONCEPTS)
def graph_read_two_points(ctx: CellContext, rng: Rng) -> MR:
    """グラフ上の直線が通る2つの格子点の座標を読み取る（graph_table「読む」Lv2）。

    直線を1本 answer-first で選び格子点2つを取る。独立ソルバ
    `math.read_two_lattice_points` で座標そのものを答えとする。

    visual_plan: frame.visual="required" を満たす最小構成。図に描いてよい文字列
    （labels）は MR.given から機械構築できる範囲のみとし、答え（読み取るべき2点の
    座標そのもの）は載せない。実際の描画要素・whitelist の最終仕様は Task8（図担当）
    が詰める — 以下は骨格を満たすための最小実装であり、TODO として明示する。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-8, 8]}), rng)
    (x1, _y1), (x2, _y2) = draw_many(p["point_domain"], rng, k=2)

    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    x1_s, x2_s = sympy.nsimplify(x1), sympy.nsimplify(x2)
    pts = [(x1_s, a_s * x1_s + b_s), (x2_s, a_s * x2_s + b_s)]

    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = cast(Solution, solver(pts[0], pts[1]))
    assert isinstance(sol.answer, SymbolicAnswer)  # 読み取り座標も symbolic(sympy Tuple の srepr)

    expected_pts = sympy.Tuple(sympy.Tuple(pts[0][0], pts[0][1]), sympy.Tuple(pts[1][0], pts[1][1]))
    assert sol.answer.srepr == sympy.srepr(expected_pts), (
        f"double-solve 不一致: recipe が構成した点 {expected_pts} != solver 再計算 {sol.answer.srepr}"
    )

    line_display = _format_parallel_line_display(a_s, b_s)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_point",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    # TODO(Task8・図担当): 実際の描画要素（グリッド範囲・直線の描画方法・
    # ラベル whitelist の最終仕様）はここで詰める。ここでは frame.visual="required"
    # を満たす最小構成（式のみを labels として許可し、答えである座標は載せない）。
    visual_plan = VisualPlan(
        style="grid",
        labels=[line_display],
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="line", attrs={"expr": line_display}),
        ],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"a": str(a_s), "b": str(b_s), "pts": [str(pts[0]), str(pts[1])]},
        given={"expression": line_display},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.graph_read_two_points"),
    )


__all__ = [
    "linear_from_two_points",
    "linear_from_slope_point",
    "linear_from_parallel_condition",
    "graph_read_two_points",
]
