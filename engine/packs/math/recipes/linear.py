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
    GraphAnswer,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.visuals.graph import render_line_solution_svg, tick_labels_from_params

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

    設計判断（Task8・図担当確定分）:
    - 式（y=ax+b）は生徒に提示する given ではなく、図を規定する内部パラメータ
      （params の a/b/pts に残す）。given は空 {} にする——式を given に出すと
      「グラフから読む」題材が計算で解けてしまい破綻するため。G-GND は given 空
      なら自明に通過する。
    - visual_plan.labels は実描画（`packs.math.visuals.graph.tick_labels`）が
      実際に描く軸目盛の数値文字列と機械的に一致させる（式や答え座標は含めない）。
    - visual_plan.elements は grid/axis/line のみ。答えの点マーカー・座標ラベル
      （`labeled_answer_point`）は描かない・宣言しない
      （frame.forbidden_visual_elements(["read_point"]) が禁止する種別）。
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

    # narration の日本語表現を数詞なしに差し替える（steps の op/result_srepr/result_display
    # は solver 由来のまま維持し、narration のみ）。
    #
    # 理由（既知の G-Q5t 挙動・報告済み・quality_gates.py は本 Task の対象外のため未修正）:
    # solver 側 narration「グラフ上の格子点の座標を1つ読み取る。」の助数詞「1つ」の
    # "1" が、extract_numbers（core/verify/quality_gates.py）の数値トークン抽出で
    # 答え座標の数値（例: x=1, y=1 等）と偶然一致し、G-Q5t が「解答由来の値が
    # hints に漏洩」と誤検出することがある（答え座標が -9..9 の小さい整数になりやすい
    # ため高頻度で発生する）。ここでは hint の元になる narration の文言自体を
    # 数詞を含まない表現に変えることで回避する（steps の計算内容は不変）。
    steps = [
        Step(
            op=s.op,
            args=s.args,
            result_srepr=s.result_srepr,
            result_display=s.result_display,
            narration=narration,
        )
        for s, narration in zip(
            sol.steps,
            [
                "グラフ上の格子点の座標を読み取る。",
                "グラフ上の別の格子点の座標を読み取る。",
            ],
        )
    ]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_point",
        answer=sol.answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    mr_params = {"a": str(a_s), "b": str(b_s), "pts": [str(pts[0]), str(pts[1])]}
    labels = tick_labels_from_params(mr_params)

    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            VisualElement(kind="line", attrs={}),
        ],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=mr_params,
        given={},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.graph_read_two_points"),
    )


# ---------------------------------------------------------------------------
# math.read_slope_intercept（g2_l21.graph_table Lv1 用）— 横展開#4（グラフから傾き・切片を読む）
# ---------------------------------------------------------------------------
_READ_SLOPE_INTERCEPT_CONCEPTS = [
    "graph.read_slope_intercept",
]


@register_recipe("math.read_slope_intercept", provides_concepts=_READ_SLOPE_INTERCEPT_CONCEPTS)
def read_slope_intercept(ctx: CellContext, rng: Rng) -> MR:
    """グラフ上の直線から傾きと切片を読み取る（answer-first・graph_table「読む」Lv1）。

    整数傾き a(≠0)・整数切片 b を先に選び、直線 y=ax+b 上の格子点2つを逆算する。独立
    ソルバ `math.read_slope_intercept_from_graph` で2点から傾き・切片を再計算し、答え
    (a, b) の一致を assert する。

    設計判断（graph_read_two_points と同じ・Task8 図担当確定分）:
    - 式（y=ax+b）は生徒に提示する given ではなく図を規定する内部パラメータ（params の
      a/b/pts に残す）。given は空 {}——式を given に出すと「グラフから読む」題材が計算で
      解けてしまい破綻する。G-GND は given 空なら自明に通過する。
    - 整数傾き・整数切片により (0,b) と (1,b+a) が格子点になり、傾きを「右1・上a」で、
      切片を「y 軸との交点」で読める（可読性）。
    - visual_plan.labels は実描画の軸目盛の数値文字列と機械的に一致させる（式や答えの
      傾き・切片は含めない）。elements は grid/axis/line のみ（labeled_answer_point は
      描かない・宣言しない＝frame.forbidden_visual_elements(["read_slope_intercept"])）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-4, 4]}), rng)
    (x1, _y1), (x2, _y2) = draw_many(p["point_domain"], rng, k=2)

    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    x1_s, x2_s = sympy.nsimplify(x1), sympy.nsimplify(x2)
    pts = [(x1_s, a_s * x1_s + b_s), (x2_s, a_s * x2_s + b_s)]

    solver = REGISTRY.solver("math.read_slope_intercept_from_graph")
    sol = cast(Solution, solver(pts[0], pts[1]))
    assert isinstance(sol.answer, SymbolicAnswer)

    expected_pair = sympy.Tuple(a_s, b_s)
    assert sol.answer.srepr == sympy.srepr(expected_pair), (
        f"double-solve 不一致: recipe が構成した (傾き, 切片) {expected_pair} "
        f"!= solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_slope_intercept",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    mr_params = {"a": str(a_s), "b": str(b_s), "pts": [str(pts[0]), str(pts[1])]}
    labels = tick_labels_from_params(mr_params)

    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            VisualElement(kind="line", attrs={}),
        ],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=mr_params,
        given={},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.read_slope_intercept"),
    )


# ---------------------------------------------------------------------------
# math.solve_equation_for_y（g2_l26.calculation Lv1 用）— 横展開#5
# 2元1次方程式 ax+by=c を y=… に変形する（最初の calculation セル）
# ---------------------------------------------------------------------------
_SOLVE_FOR_Y_CONCEPTS = [
    "linear_function.solve_equation_for_y",
]


def _format_two_var_equation_display(a: sympy.Expr, b: sympy.Expr, c: sympy.Expr) -> str:
    """2元1次方程式 a x + b y = c の given 表示（b>0 前提・solver の step 表示と一致）。"""

    def coeff_term(coeff: sympy.Expr, var: str) -> str:
        mag = abs(coeff)
        mag_part = "" if mag == 1 else _fmt_number(mag)
        return f"{mag_part}{var}"

    ax = ("-" if a < 0 else "") + coeff_term(a, "x")
    by = coeff_term(b, "y")
    return f"{ax} + {by} = {_fmt_number(c)}"


@register_recipe("math.solve_equation_for_y", provides_concepts=_SOLVE_FOR_Y_CONCEPTS)
def solve_equation_for_y(ctx: CellContext, rng: Rng) -> MR:
    """2元1次方程式 ax+by=c を y について解く（answer-first・calculation Lv1）。

    結果の式 y = m x + k（整数 m≠0・整数 k）を先に決め、y の係数 b (>0, ≥2) を選び、
    a = -m*b・c = k*b として方程式 a x + b y = c を逆算する（b で割ると必ず整数係数に
    戻る＝基礎レベルの clean な変形）。独立ソルバ `math.solve_equation_for_y` で ax+by=c
    を y について解き直し、y = m x + k との一致を assert する。図は無し（calculation）。
    """
    p = ctx.spec_level.params
    m = draw(p["result_slope_domain"], rng)
    k = draw(p["result_intercept_domain"], rng)
    b = draw(p["b_domain"], rng)  # y の係数（正・2 以上で非自明な除算を保証）

    m_s, k_s, b_s = sympy.nsimplify(m), sympy.nsimplify(k), sympy.nsimplify(b)
    a_s = -m_s * b_s
    c_s = k_s * b_s

    solver = REGISTRY.solver("math.solve_equation_for_y")
    sol = cast(Solution, solver(a_s, b_s, c_s))
    assert isinstance(sol.answer, SymbolicAnswer)

    expected_expr = m_s * sympy.Symbol("x") + k_s
    assert sol.answer.srepr == sympy.srepr(expected_expr), (
        f"double-solve 不一致: recipe が構成した式 {expected_expr} != solver 再計算 {sol.answer.srepr}"
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
        params={"a": str(a_s), "b": str(b_s), "c": str(c_s)},
        given={"equation": _format_two_var_equation_display(a_s, b_s, c_s)},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_equation_for_y"),
    )


# ---------------------------------------------------------------------------
# math.evaluate_linear（g2_l19.calculation Lv1 用）— 横展開#6
# 1次関数 y=ax+b に x の値を代入して y を求める（最初の asked=value セル）
# ---------------------------------------------------------------------------
_EVALUATE_LINEAR_CONCEPTS = [
    "linear_function.evaluate_at_x",
]


@register_recipe("math.evaluate_linear", provides_concepts=_EVALUATE_LINEAR_CONCEPTS)
def evaluate_linear(ctx: CellContext, rng: Rng) -> MR:
    """1次関数 y=ax+b に x=x0 を代入して y を求める（answer-first・calculation Lv1）。

    傾き a(≠0)・切片 b・代入する x0(≠0) を選び、独立ソルバ `math.evaluate_linear_at_x`
    で y = a*x0 + b を再計算する（代入するだけなので構成＝解が自明に一致）。答えは1つの
    数値 y（asked=value）。図は無し（calculation frame visual=none）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-9, 9]}), rng)
    x0 = draw(p["x_domain"], rng)

    a_s, b_s, x_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(x0)
    y_expected = a_s * x_s + b_s

    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    sol = cast(Solution, solver(a_s, b_s, x_s))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(y_expected), (
        f"double-solve 不一致: recipe が構成した y {y_expected} != solver 再計算 {sol.answer.srepr}"
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
        params={"a": str(a_s), "b": str(b_s), "x0": str(x_s)},
        given={
            "expression": _format_parallel_line_display(a_s, b_s),
            "input_value": f"x = {_fmt_number(x_s)}",
        },
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_linear"),
    )


# ---------------------------------------------------------------------------
# math.point_on_line（g2_l22.calculation Lv1 用）— 横展開#7
# グラフが通る点を代入で求める。solver は evaluate_linear_at_x を再利用（償却前進）。
# ---------------------------------------------------------------------------
_POINT_ON_LINE_CONCEPTS = [
    "linear_function.point_on_line",
]


@register_recipe("math.point_on_line", provides_concepts=_POINT_ON_LINE_CONCEPTS)
def point_on_line(ctx: CellContext, rng: Rng) -> MR:
    """y=ax+b のグラフが通る点(x0, y0)を代入で求める（answer-first・calculation Lv1）。

    傾き a(≠0)・切片 b・x 座標 x0(≠0) を選び、独立ソルバ `math.point_on_line_at_x`
    （内部で g2_l19 と同じ `evaluate_linear_at_x` を再利用）で通過点 (x0, a*x0+b) を得る。
    答えは座標。図は無し（calculation）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-9, 9]}), rng)
    x0 = draw(p["x_domain"], rng)

    a_s, b_s, x_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(x0)
    point_expected = sympy.Tuple(x_s, a_s * x_s + b_s)

    solver = REGISTRY.solver("math.point_on_line_at_x")
    sol = cast(Solution, solver(a_s, b_s, x_s))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(point_expected), (
        f"double-solve 不一致: recipe が構成した通過点 {point_expected} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="coordinate",
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
        params={"a": str(a_s), "b": str(b_s), "x0": str(x_s)},
        given={
            "expression": _format_parallel_line_display(a_s, b_s),
            "input_value": _fmt_number(x_s),
        },
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.point_on_line"),
    )


# ---------------------------------------------------------------------------
# math.draw_linear（g2_l22.graph_table Lv1 用）— 横展開#8・「かく」capability の初セル
# y=ax+b のグラフをかく。答えは GraphAnswer(特徴点集合で採点)、問題図＝空の方眼、
# 模範解答図＝直線つき（solution_svg_ref）。
# ---------------------------------------------------------------------------
_DRAW_GRAPH_CONCEPTS = [
    "linear_function.draw_graph",
]


@register_recipe("math.draw_linear", provides_concepts=_DRAW_GRAPH_CONCEPTS)
def draw_linear(ctx: CellContext, rng: Rng) -> MR:
    """1次関数 y=ax+b のグラフをかく（answer-first・graph_table「かく」Lv1）。

    傾き a(≠0)・切片 b を選ぶ。独立ソルバ `math.draw_linear_features` で採点用の特徴
    （傾き・y切片の点）を得る（answer.kind="graph"）。問題図は**空の方眼**（生徒が描き込む・
    visual_plan.elements に line を宣言しない）、模範解答図は visual 純ヘルパ
    `render_line_solution_svg` で描いて GraphAnswer.solution_svg_ref に格納する。

    グリッド範囲を決める pts は (a, b) から決定論的に定める（切片と傾き1つ分の点）ので、
    dup_key は実質 (a, b) に一致する＝同じ直線は grid の窓が違っても重複として数えられる。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-9, 9]}), rng)

    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    # グリッド範囲用の代表点（決定論・(a,b)のみに依存）: 切片と、傾き1つ分進んだ点。
    pts = [(sympy.Integer(0), b_s), (sympy.Integer(1), a_s + b_s)]

    solver = REGISTRY.solver("math.draw_linear_features")
    sol = cast(Solution, solver(a_s, b_s))
    assert isinstance(sol.answer, GraphAnswer)

    expected_feature_sreprs = {
        sympy.srepr(a_s),
        sympy.srepr(sympy.Tuple(sympy.Integer(0), b_s)),
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: recipe が想定した特徴 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    mr_params = {"a": str(a_s), "b": str(b_s), "pts": [str(pts[0]), str(pts[1])]}
    solution_svg = render_line_solution_svg(mr_params)  # 直線つきの模範解答図
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_graph",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    labels = tick_labels_from_params(mr_params)
    # 問題図＝空の方眼（line を宣言しない＝render_visual が直線を描かない）。
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
        ],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=mr_params,
        given={"expression": _format_parallel_line_display(a_s, b_s)},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_linear"),
    )


# ---------------------------------------------------------------------------
# math.draw_linear_from_equation（g2_l26.graph_table Lv1 用）— 横展開#9
# ax+by=c を y=… に変形してグラフをかく。solver は #5(変形)＋#8(かく)のコア合成のみ＝
# 新 solver の数学ロジックはゼロ。capability 投資の償却（部品追加なしでセルが増える）の実証。
# ---------------------------------------------------------------------------
_DRAW_FROM_EQUATION_CONCEPTS = [
    "linear_function.draw_graph_from_equation",
]


@register_recipe("math.draw_linear_from_equation", provides_concepts=_DRAW_FROM_EQUATION_CONCEPTS)
def draw_linear_from_equation(ctx: CellContext, rng: Rng) -> MR:
    """2元1次方程式 ax+by=c を y=… に変形してグラフをかく（answer-first・graph_table「かく」Lv1）。

    answer-first: 変形後の直線 y=mx+k（整数 m≠0・整数 k）と y の係数 B(≥1) を先に選び、
    A=-m*B・C=k*B として方程式を逆算する（B で割ると整数に戻る clean な変形）。合成ソルバ
    `math.draw_from_equation` が #5 の変形手順と #8 の作図特徴を再利用して GraphAnswer を返す。
    問題図＝空の方眼、模範解答図＝変形後の直線つき（#8 と同じ経路）。
    """
    p = ctx.spec_level.params
    m = draw(p["result_slope_domain"], rng)
    k = draw(p["result_intercept_domain"], rng)
    bcoef = draw(p["b_domain"], rng)  # y の係数 B（正）

    m_s, k_s, b_s = sympy.nsimplify(m), sympy.nsimplify(k), sympy.nsimplify(bcoef)
    a_coeff = -m_s * b_s
    c_coeff = k_s * b_s

    solver = REGISTRY.solver("math.draw_from_equation")
    sol = cast(Solution, solver(a_coeff, b_s, c_coeff))
    assert isinstance(sol.answer, GraphAnswer)
    expected_feature_sreprs = {
        sympy.srepr(m_s),
        sympy.srepr(sympy.Tuple(sympy.Integer(0), k_s)),
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: 変形後の直線の特徴 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    # 描画（問題図の方眼＋模範解答図）は変形後の直線 y=mx+k で行う。
    render_params = {
        "a": str(m_s),
        "b": str(k_s),
        "pts": [str((sympy.Integer(0), k_s)), str((sympy.Integer(1), m_s + k_s))],
    }
    solution_svg = render_line_solution_svg(render_params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_graph",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    labels = tick_labels_from_params(render_params)
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    # params: checker 用の方程式係数（eq_*）と、描画（問題図の方眼）用の直線係数 a/b/pts の両方。
    mr_params = {
        "eq_a": str(a_coeff),
        "eq_b": str(b_s),
        "eq_c": str(c_coeff),
        "a": str(m_s),
        "b": str(k_s),
        "pts": render_params["pts"],
    }
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=mr_params,
        given={"equation": _format_two_var_equation_display(a_coeff, b_s, c_coeff)},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_linear_from_equation"),
    )


# ---------------------------------------------------------------------------
# math.rate_of_change（g2_l20.find_value Lv1 用）— 横展開の第1セル
# ---------------------------------------------------------------------------
_RATE_OF_CHANGE_CONCEPTS = [
    "linear_function.rate_of_change",
]


@register_recipe("math.rate_of_change", provides_concepts=_RATE_OF_CHANGE_CONCEPTS)
def rate_of_change(ctx: CellContext, rng: Rng) -> MR:
    """2点から一次関数の変化の割合（＝傾き）を求める（answer-first）。

    整数傾き a・切片 b を先に選び、直線 y=ax+b 上の格子点2つを逆算する。答えは
    a（変化の割合）そのもの。独立ソルバ `math.rate_of_change_from_two_points` で
    (y2-y1)/(x2-x1) を再計算し a と一致することを assert する。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-8, 8]}), rng)
    (x1, _y1), (x2, _y2) = draw_many(p["point_domain"], rng, k=2)

    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    x1_s, x2_s = sympy.nsimplify(x1), sympy.nsimplify(x2)
    pts = [(x1_s, a_s * x1_s + b_s), (x2_s, a_s * x2_s + b_s)]

    solver = REGISTRY.solver("math.rate_of_change_from_two_points")
    sol = cast(Solution, solver(pts[0], pts[1]))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(a_s), (
        f"double-solve 不一致: recipe が構成した変化の割合 {a_s} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="rate_of_change",
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
        params={"a": str(a_s), "pts": [str(pts[0]), str(pts[1])]},
        given={"point_a": _fmt_point(pts[0]), "point_b": _fmt_point(pts[1])},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.rate_of_change"),
    )


# ---------------------------------------------------------------------------
# math.intersection（g2_l27.find_value Lv2/Lv3 用）— 横展開の第2セル（2直線の交点）
# ---------------------------------------------------------------------------
_INTERSECTION_CONCEPTS = [
    "linear_function.intersection_of_two_lines",
]


def _format_general_form(a_coeff: sympy.Expr, b_coeff: sympy.Expr, c_coeff: sympy.Expr) -> str:
    """A x + B y = C 形の表示（例: "2x - y = 5"）。先頭係数は正に正規化済みを前提。"""

    def term(coeff: sympy.Expr, var: str, *, lead: bool) -> str:
        if coeff == 0:
            return ""
        sign = "-" if coeff < 0 else ("+" if not lead else "")
        mag = abs(coeff)
        mag_part = "" if mag == 1 else sympy.sstr(mag)
        joiner = "" if lead else " "
        return f"{joiner}{sign}{joiner if not lead else ''}{mag_part}{var}"

    lhs = term(a_coeff, "x", lead=True) + term(b_coeff, "y", lead=False)
    return f"{lhs} = {sympy.sstr(c_coeff)}"


@register_recipe("math.intersection", provides_concepts=_INTERSECTION_CONCEPTS)
def intersection(ctx: CellContext, rng: Rng) -> MR:
    """2直線の交点の座標を求める（answer-first）。

    交点 (x0, y0) と相異な2傾き a1, a2 を先に選び、各直線が (x0, y0) を通るよう
    切片を逆算する（構成で非平行・交点一意を恒真に保証）。Lv2 は傾き切片形を等値
    （method=substitute）、Lv3 は一般形 ax+by=c を連立消去（method=elimination）。
    独立ソルバ `math.intersection_of_two_lines` で交点を再計算し一致を assert する。
    """
    p = ctx.spec_level.params
    method: str = p["method"]

    x0 = draw(p["x_domain"], rng)
    y0 = draw(p["y_domain"], rng)
    a1, a2 = draw_many(p["slope_pair_domain"], rng, k=2)  # distinct:[value] で相異保証

    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a1_s, a2_s = sympy.nsimplify(a1), sympy.nsimplify(a2)
    b1_s = y0_s - a1_s * x0_s
    b2_s = y0_s - a2_s * x0_s

    def to_coeffs_and_display(a_slope: sympy.Expr, b_int: sympy.Expr) -> tuple[list[sympy.Expr], str]:
        # 傾き切片 y = a x + b ⇔ -a x + y = b。一般形は先頭係数を正に正規化する。
        A, B, C = -a_slope, sympy.Integer(1), b_int
        if A < 0:
            A, B, C = -A, -B, -C
        if method == "substitute":
            return [A, B, C], _format_parallel_line_display(a_slope, b_int)  # "y = a x + b"
        return [A, B, C], _format_general_form(A, B, C)  # "A x + B y = C"

    coeffs1, disp1 = to_coeffs_and_display(a1_s, b1_s)
    coeffs2, disp2 = to_coeffs_and_display(a2_s, b2_s)

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs1), tuple(coeffs2), method))
    assert isinstance(sol.answer, SymbolicAnswer)

    expected_pt = sympy.Tuple(x0_s, y0_s)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: recipe が構成した交点 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="intersection",
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
        params={
            "line_a": [str(c) for c in coeffs1],
            "line_b": [str(c) for c in coeffs2],
            "method": method,
        },
        given={"line_a": disp1, "line_b": disp2},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.intersection"),
    )


# ---------------------------------------------------------------------------
# math.y_range_from_domain / math.expr_from_range（g2_l23.find_value）— 横展開#3
# 変域とグラフの端点。Lv2=順方向(関数+x変域→y変域)、Lv3=逆算(x変域+y変域+符号→式)。
# ---------------------------------------------------------------------------
_Y_RANGE_CONCEPTS = ["linear_function.variable_range"]


def _format_x_domain(x_lo: sympy.Expr, x_hi: sympy.Expr) -> str:
    return f"{_fmt_number(x_lo)} ≦ x ≦ {_fmt_number(x_hi)}"


def _format_y_range_display(y_lo: sympy.Expr, y_hi: sympy.Expr) -> str:
    return f"{_fmt_number(y_lo)} ≦ y ≦ {_fmt_number(y_hi)}"


def _draw_ordered_x_pair(p: dict[str, Any], rng: Rng) -> tuple[sympy.Expr, sympy.Expr]:
    """x の変域端点 x_lo < x_hi を2つ引く（distinct 保証つき domain を昇順に）。"""
    x_a, x_b = draw_many(p["x_domain"], rng, k=2)
    xs = sorted([sympy.nsimplify(x_a), sympy.nsimplify(x_b)])
    return xs[0], xs[1]


@register_recipe("math.y_range_from_domain", provides_concepts=_Y_RANGE_CONCEPTS)
def y_range_from_domain(ctx: CellContext, rng: Rng) -> MR:
    """順方向（g2_l23 Lv2）: 1次関数 y=ax+b と x の変域から y の変域を求める。"""
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p.get("intercept_domain", {"int_range": [-6, 6]}), rng)
    x_lo, x_hi = _draw_ordered_x_pair(p, rng)

    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    solver = REGISTRY.solver("math.y_range_over_domain")
    sol = cast(Solution, solver(a_s, b_s, x_lo, x_hi))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="domain_range",
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
        params={"a": str(a_s), "b": str(b_s), "x_lo": str(x_lo), "x_hi": str(x_hi)},
        given={
            "expression": _format_parallel_line_display(a_s, b_s),
            "x_domain": _format_x_domain(x_lo, x_hi),
        },
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.y_range_from_domain"),
    )


@register_recipe("math.expr_from_range", provides_concepts=_Y_RANGE_CONCEPTS)
def expr_from_range(ctx: CellContext, rng: Rng) -> MR:
    """逆算（g2_l23 Lv3）: x の変域・y の変域・傾きの符号（正）から式を求める。

    傾き正のとき x_lo↔y_lo・x_hi↔y_hi と対応するので、端点2点から式を復元する
    （既存ソルバ `math.linear_expr_from_two_points` を再利用）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)  # 正の傾き（spec で exclude<=0 を保証）
    b = draw(p.get("intercept_domain", {"int_range": [-6, 6]}), rng)
    x_lo, x_hi = _draw_ordered_x_pair(p, rng)

    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    y_lo = a_s * x_lo + b_s
    y_hi = a_s * x_hi + b_s  # a>0 なので y_lo < y_hi
    pts = [(x_lo, y_lo), (x_hi, y_hi)]

    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = cast(Solution, solver(pts[0], pts[1], "slope_then_intercept"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = a_s * sympy.Symbol("x") + b_s
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver {sol.answer.srepr}"
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
        params={"pts": [str(pts[0]), str(pts[1])], "method": "slope_then_intercept"},
        given={
            "x_domain": _format_x_domain(x_lo, x_hi),
            "y_range": _format_y_range_display(y_lo, y_hi),
            "condition": "傾き a が正のとき",
        },
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.expr_from_range"),
    )


__all__ = [
    "linear_from_two_points",
    "linear_from_slope_point",
    "linear_from_parallel_condition",
    "graph_read_two_points",
    "read_slope_intercept",
    "solve_equation_for_y",
    "evaluate_linear",
    "point_on_line",
    "draw_linear",
    "draw_linear_from_equation",
    "rate_of_change",
    "intersection",
    "y_range_from_domain",
    "expr_from_range",
]
