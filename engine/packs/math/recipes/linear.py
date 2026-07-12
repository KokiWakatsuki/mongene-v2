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
    ChoiceAnswer,
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
from engine.packs.math.visuals.graph import (
    render_line_solution_svg,
    render_segment_solution_svg,
    render_special_lines_solution_svg,
    tick_labels_from_params,
)

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


def _fmt_expr(expr: Any) -> str:
    """1次式を教材表記に整形（sympy sstr の乗算記号 * を除去）。

    例: 2*x - 1 -> "2x - 1" / 7 - 2*y -> "7 - 2y" / 1*x -> "x"（sstr が係数1を省く）。
    連立クラスタの方程式・途中式の表示に使う（符号処理を sympy に委ねて手作業のバグを避ける）。
    冪は上付き表記に直す（x**2 -> x²）。knowledge の1次関数判別セル（2次式の提示）で使う。
    既存の1次式には冪が現れないため後方互換（golden 不変）。
    """
    s = str(sympy.sstr(sympy.nsimplify(expr)))
    s = s.replace("**2", "²").replace("**3", "³")
    return s.replace("*", "")


def _fmt_eq(lhs: Any, rhs: Any) -> str:
    """等式 lhs = rhs を教材表記で返す（両辺を `_fmt_expr` で整形）。"""
    return f"{_fmt_expr(lhs)} = {_fmt_expr(rhs)}"


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
# math.read_intersection_from_graph（g2_l27.graph_table Lv1 用）— 横展開#10
# 2直線をかき交点をグラフから読む。answer は交点座標（SymbolicAnswer）、検証は既存
# intersection_of_two_lines を再利用（新 solver ゼロ）。問題図＝空の方眼（生徒が描く）。
# ---------------------------------------------------------------------------
_READ_INTERSECTION_CONCEPTS = [
    "linear_function.read_intersection_from_graph",
]


@register_recipe("math.read_intersection_from_graph", provides_concepts=_READ_INTERSECTION_CONCEPTS)
def read_intersection_from_graph(ctx: CellContext, rng: Rng) -> MR:
    """2直線をかき交点の座標をグラフから読み取る（answer-first・graph_table「読む」）。

    交点 (x0,y0) と相異な2傾き a1,a2 を先に選び、各直線が (x0,y0) を通るよう切片を逆算する
    （交点は格子点＝グラフから読める）。答え（交点）は既存 solver
    `math.intersection_of_two_lines`（g2_l27.find_value と共有）で再計算して一致を確認する。
    問題図は空の方眼（生徒が2直線をかいて読む）、steps はグラフ読解の手順。
    """
    p = ctx.spec_level.params
    x0 = draw(p["x_domain"], rng)
    y0 = draw(p["y_domain"], rng)
    a1, a2 = draw_many(p["slope_pair_domain"], rng, k=2)  # distinct:[value] で相異保証

    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a1_s, a2_s = sympy.nsimplify(a1), sympy.nsimplify(a2)
    b1_s = y0_s - a1_s * x0_s
    b2_s = y0_s - a2_s * x0_s

    # 一般形係数（y = a x + b ⇔ -a x + y = b）で solver に渡す。
    coeffs1 = [-a1_s, sympy.Integer(1), b1_s]
    coeffs2 = [-a2_s, sympy.Integer(1), b2_s]
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs1), tuple(coeffs2), "substitute"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0_s, y0_s)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成交点 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    disp1 = _format_parallel_line_display(a1_s, b1_s)
    disp2 = _format_parallel_line_display(a2_s, b2_s)
    # グラフ読解の手順（narration は助数詞「本」で数を表し答え座標と衝突させない）。
    steps = [
        Step(
            op="draw_line_1",
            args=[disp1],
            result_srepr=sympy.srepr(a1_s * sympy.Symbol("x") + b1_s),
            result_display=disp1,
            narration="1本目の直線を座標平面にかく。",
        ),
        Step(
            op="draw_line_2",
            args=[disp2],
            result_srepr=sympy.srepr(a2_s * sympy.Symbol("x") + b2_s),
            result_display=disp2,
            narration="2本目の直線を同じ平面にかく。",
        ),
        Step(
            op="read_intersection",
            args=[],
            result_srepr=sol.answer.srepr,
            result_display=sol.answer.display,
            narration="2本の直線が交わる点の座標を読み取る。",
        ),
    ]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_intersection",
        answer=sol.answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    # 空の方眼の描画範囲: 交点と両直線の y切片を含める（生徒が両直線をかける窓）。
    pts = [str((x0_s, y0_s)), str((sympy.Integer(0), b1_s)), str((sympy.Integer(0), b2_s))]
    labels = tick_labels_from_params({"pts": pts})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
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
            "method": "substitute",
            "pts": pts,
        },
        given={"line_a": disp1, "line_b": disp2},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.read_intersection_from_graph"),
    )


# ---------------------------------------------------------------------------
# math.read_diagram_intersection（g2_l30.graph_table Lv2 用）— 横展開・P1/C5
# ダイヤグラム（時間-道のり）の2直線をかき、交点（出会い/追いつき）をグラフから読む。
# #10 read_intersection_from_graph の流用: solver は `intersection_of_two_lines`（g2_l27 と共有）
# を再利用＝新 solver ゼロ。追加分は「交点を第1象限の格子点（時間・道のり>0）に限定」と
# 「シナリオ（meet=傾き異符号で向かい合う／catchup=傾き同符号で相異＝追いつき）」のみ。
# ★式は既知として与え、グラフ読解のみを問う（場面→立式は word_problem g2_l30 の領域）。
#   問題図は空の方眼（l27 前例。生徒が2直線をかいて交点を読む＝幾何リーク規則は不発）。
# ---------------------------------------------------------------------------
_DIAGRAM_INTERSECTION_CONCEPTS = [
    "linear_function.diagram_intersection",
]


@register_recipe("math.read_diagram_intersection", provides_concepts=_DIAGRAM_INTERSECTION_CONCEPTS)
def read_diagram_intersection(ctx: CellContext, rng: Rng) -> MR:
    """ダイヤグラムの2直線の交点（出会い/追いつき）をグラフから読み取る（answer-first・「読む」Lv2）。

    交点 (x0,y0) を第1象限の格子点（時間 x>0・道のり y>0）に先に決め、シナリオ
    （meet=向かい合う＝傾き異符号／catchup=同方向で追いつき＝傾き同符号かつ相異）に応じて
    2傾き a1,a2 を選び、各直線が (x0,y0) を通るよう切片を逆算する。答え（交点）は既存 solver
    `math.intersection_of_two_lines`（g2_l27 と共有）で再計算して一致を確認する（新 solver ゼロ）。
    問題図は空の方眼（生徒が2直線をかいて交点を読む）。steps はグラフ読解の手順（数字を含めない）。
    """
    p = ctx.spec_level.params
    x0 = draw(p["x_domain"], rng)
    y0 = draw(p["y_domain"], rng)
    scenario = draw(p["scenario_domain"], rng)  # 素の配列 [meet, catchup] からの一様選択
    if scenario == "meet":
        a1 = draw(p["pos_slope_domain"], rng)  # 向かい合う: 一方は正の傾き
        a2 = draw(p["neg_slope_domain"], rng)  # もう一方は負の傾き（異符号）
    else:  # catchup: 同方向（同符号）で傾きが相異＝速い方が追いつく
        a1, a2 = draw_many(p["pos_slope_domain"], rng, k=2)  # distinct:[value] で相異保証

    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a1_s, a2_s = sympy.nsimplify(a1), sympy.nsimplify(a2)
    b1_s = y0_s - a1_s * x0_s
    b2_s = y0_s - a2_s * x0_s

    # 一般形係数（y = a x + b ⇔ -a x + y = b）で solver に渡す（g2_l27 と同じ規約）。
    coeffs1 = [-a1_s, sympy.Integer(1), b1_s]
    coeffs2 = [-a2_s, sympy.Integer(1), b2_s]
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs1), tuple(coeffs2), "substitute"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0_s, y0_s)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成交点 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    disp1 = _format_parallel_line_display(a1_s, b1_s)
    disp2 = _format_parallel_line_display(a2_s, b2_s)
    # グラフ読解の手順（narration に数字を書かない＝G-Q5t 偽陽性回避。§5-#9）。
    steps = [
        Step(
            op="draw_line_a",
            args=[disp1],
            result_srepr=sympy.srepr(a1_s * sympy.Symbol("x") + b1_s),
            result_display=disp1,
            narration="Aさんの進むようすを表す直線を座標平面にかく。",
        ),
        Step(
            op="draw_line_b",
            args=[disp2],
            result_srepr=sympy.srepr(a2_s * sympy.Symbol("x") + b2_s),
            result_display=disp2,
            narration="Bさんの進むようすを表す直線を同じ平面にかく。",
        ),
        Step(
            op="read_intersection",
            args=[],
            result_srepr=sol.answer.srepr,
            result_display=sol.answer.display,
            narration="2つの直線が交わる点の座標（同じ地点にいる時間と道のり）を読み取る。",
        ),
    ]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_intersection",
        answer=sol.answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    # 空の方眼の描画範囲: 交点と両直線の y切片を含める（生徒が両直線をかける窓）。
    pts = [str((x0_s, y0_s)), str((sympy.Integer(0), b1_s)), str((sympy.Integer(0), b2_s))]
    labels = tick_labels_from_params({"pts": pts})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
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
            "method": "substitute",
            "scenario": scenario,  # dup_key 分散のため（＋faithful な題材差の記録）
            "pts": pts,
        },
        given={"line_a": disp1, "line_b": disp2},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.read_diagram_intersection"),
    )


# ---------------------------------------------------------------------------
# math.draw_special_lines（g2_l26.graph_table Lv2 用）— 横展開・P1/C5
# 2元1次方程式を切片法（x軸/y軸との交点）でかき、さらに x=k / y=k の特殊直線もかく。
# Lv1（y= 変形して1本）と op 列を変える（find_x_intercept→find_y_intercept→draw_line→
# draw_special_line）＝level_sep。答えは GraphAnswer（2交点＋特殊直線の特徴集合・単一小問で
# 両方を採点。G-Q1 は sub_questions[0] のみ検査するため単一小問に集約）。問題図＝空の方眼。
# ---------------------------------------------------------------------------
_DRAW_SPECIAL_LINES_CONCEPTS = [
    "linear_function.draw_special_lines",
]


@register_recipe("math.draw_special_lines", provides_concepts=_DRAW_SPECIAL_LINES_CONCEPTS)
def draw_special_lines(ctx: CellContext, rng: Rng) -> MR:
    """切片法で 2元1次方程式の直線をかき、特殊直線 x=k / y=k もかく（answer-first・「かく」Lv2）。

    answer-first: x 軸との交点 (xi,0)・y 軸との交点 (0,yi)（ともに整数・xi>0）を先に決め、
    直線が両交点を通るよう方程式 (yi)x + (xi)y = xi·yi を逆算する（切片が clean な整数に戻る）。
    特殊直線は axis（vertical→x=k / horizontal→y=k）と k を選ぶ。答え（2交点＋特殊直線の特徴）は
    独立ソルバ `math.draw_special_lines` で再計算し一致を assert（新 solver）。問題図は空の方眼、
    模範解答図は主直線＋特殊直線つき（render_special_lines_solution_svg）。
    """
    p = ctx.spec_level.params
    xi = draw(p["x_intercept_domain"], rng)  # x 軸との交点（正＝方程式の y 係数 b>0 を保証）
    yi = draw(p["y_intercept_domain"], rng)  # y 軸との交点（0 以外・任意符号）
    axis = draw(p["axis_domain"], rng)       # 素の配列 [vertical, horizontal]
    k = draw(p["special_k_domain"], rng)     # 特殊直線の定数（0 以外）

    xi_s, yi_s, k_s = sympy.nsimplify(xi), sympy.nsimplify(yi), sympy.nsimplify(k)
    a_coeff = yi_s          # x の係数
    b_coeff = xi_s          # y の係数（>0）
    c_coeff = xi_s * yi_s   # 右辺

    solver = REGISTRY.solver("math.draw_special_lines")
    sol = cast(Solution, solver(xi_s, yi_s, axis, k_s))
    assert isinstance(sol.answer, GraphAnswer)
    if axis == "vertical":
        special_srepr = sympy.srepr(sympy.Eq(sympy.Symbol("x"), k_s))
        equation2_disp = f"x = {_fmt_number(k_s)}"
    else:
        special_srepr = sympy.srepr(sympy.Eq(sympy.Symbol("y"), k_s))
        equation2_disp = f"y = {_fmt_number(k_s)}"
    expected_feature_sreprs = {
        sympy.srepr(sympy.Tuple(xi_s, sympy.Integer(0))),
        sympy.srepr(sympy.Tuple(sympy.Integer(0), yi_s)),
        special_srepr,
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: 想定特徴 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    # 描画: 主直線 y = m x + yi（m=-yi/xi）＋特殊直線。pts は2交点と特殊直線の位置を含める。
    m_s = -yi_s / xi_s
    render_params: dict[str, Any] = {
        "a": str(m_s),
        "b": str(yi_s),
        "pts": [
            str((xi_s, sympy.Integer(0))),
            str((sympy.Integer(0), yi_s)),
        ],
    }
    if axis == "vertical":
        render_params["vline_x"] = str(k_s)
        render_params["pts"].append(str((k_s, sympy.Integer(0))))
    else:
        render_params["hline_y"] = str(k_s)
        render_params["pts"].append(str((sympy.Integer(0), k_s)))

    solution_svg = render_special_lines_solution_svg(render_params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_graph",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    labels = tick_labels_from_params({"pts": render_params["pts"]})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    mr_params: dict[str, Any] = {
        "xi": str(xi_s),
        "yi": str(yi_s),
        "axis": axis,
        "k": str(k_s),
        "a": str(m_s),
        "b": str(yi_s),
        "pts": render_params["pts"],
    }
    if axis == "vertical":
        mr_params["vline_x"] = str(k_s)
    else:
        mr_params["hline_y"] = str(k_s)

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=mr_params,
        given={
            "equation": _format_two_var_equation_display(a_coeff, b_coeff, c_coeff),
            "equation2": equation2_disp,
        },
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_special_lines"),
    )


# ---------------------------------------------------------------------------
# math.draw_from_table（g2_l28.graph_table Lv2 用）— 横展開・P1/C5
# 対応表（x-y の4組）からグラフ（直線）をかく。solver は既存 draw_linear_features を再利用
# ＝新 solver ゼロ（答えの線は y=ax+b の傾き・切片で採点）。given=data_table（表）、
# 答え=GraphAnswer。問題図＝空の方眼。x=0 を含めるので切片 b は表に現れ whitelist される。
# ---------------------------------------------------------------------------
_DRAW_FROM_TABLE_CONCEPTS = [
    "linear_function.draw_from_table",
]


def _format_data_table(xs: list[sympy.Expr], ys: list[sympy.Expr]) -> str:
    """x-y 対応表を教材表記（1行目 x・2行目 y）で返す。"""
    x_row = " | ".join(_fmt_number(x) for x in xs)
    y_row = " | ".join(_fmt_number(y) for y in ys)
    return f"| x | {x_row} |\n| y | {y_row} |"


@register_recipe("math.draw_from_table", provides_concepts=_DRAW_FROM_TABLE_CONCEPTS)
def draw_from_table(ctx: CellContext, rng: Rng) -> MR:
    """対応表からグラフ（直線）をかく（answer-first・graph_table「かく」Lv2）。

    傾き a(≠0)・切片 b・x の刻み幅 d を選び、x=0,d,2d,3d の4点で y=ax+b を計算して対応表を作る
    （y は必ず整数）。答え（線の傾き・切片）は既存ソルバ `math.draw_linear_features` を再利用して
    再計算し一致を assert（新 solver ゼロ）。問題図は空の方眼、模範解答図は直線つき。
    刻み幅 d は線そのものを変えない surface param（表の見かけを変え dup_rate を分散）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p["intercept_domain"], rng)
    d = draw(p["step_domain"], rng)  # x の刻み幅（線に無関係な surface param）

    a_s, b_s, d_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(d)
    xs = [d_s * i for i in range(4)]  # x = 0, d, 2d, 3d（0 を含む＝切片が表に出る）
    ys = [a_s * x + b_s for x in xs]

    solver = REGISTRY.solver("math.draw_linear_features")
    sol = cast(Solution, solver(a_s, b_s))
    assert isinstance(sol.answer, GraphAnswer)
    expected_feature_sreprs = {
        sympy.srepr(a_s),
        sympy.srepr(sympy.Tuple(sympy.Integer(0), b_s)),
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: 想定特徴 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    # 対応表からグラフをかく手順（narration に数字を書かない＝漏洩回避）。
    steps = [
        Step(
            op="read_table_points",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*[sympy.Tuple(x, y) for x, y in zip(xs, ys)])),
            result_display="表の x と y の組",
            narration="表から x と y の値の組を読み取り、座標平面上の点とみる。",
        ),
        Step(
            op="plot_points",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*xs)),
            result_display="表の各点",
            narration="読み取った点を座標平面にとる。",
        ),
        Step(
            op="draw_line",
            args=[],
            result_srepr=sympy.srepr(a_s * sympy.Symbol("x") + b_s),
            result_display=_format_parallel_line_display(a_s, b_s),
            narration="とった点を通る直線をひく。",
        ),
    ]

    pts = [str((x, y)) for x, y in zip(xs, ys)]
    render_params = {"a": str(a_s), "b": str(b_s), "pts": pts}
    solution_svg = render_line_solution_svg(render_params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_graph",
        answer=answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    labels = tick_labels_from_params({"pts": pts})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"a": str(a_s), "b": str(b_s), "pts": pts},
        given={"data_table": _format_data_table(xs, ys)},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_from_table"),
    )


# ---------------------------------------------------------------------------
# math.draw_linear_fraction（g2_l22.graph_table Lv3 用）— 横展開・P1/C5
# 分数の傾き y=(p/q)x+b のグラフを、格子点 (0,b)・(q,p+b) を通るように正確にかく。
# Lv1（整数傾き・draw_linear）と op 列を変える（分母/分子ぶんの移動→格子点印づけ）＝level_sep。
# 答えは GraphAnswer（傾き・切片・通る格子点の3特徴）。問題図＝空の方眼。傾き・切片は given の
# 式係数由来で whitelist（両符号化）。
# ---------------------------------------------------------------------------
_DRAW_FRACTION_CONCEPTS = [
    "linear_function.draw_graph_fraction",
]


def _format_line_display_frac(slope: sympy.Rational, b: sympy.Expr) -> str:
    """分数の傾き y=(p/q)x+b の given 表示（例: "y = -(2/3)x - 1", "y = (3/4)x + 2"）。"""
    p_num, q_den = slope.p, slope.q
    sign = "-" if p_num < 0 else ""
    a_part = f"{sign}({abs(p_num)}/{q_den})x"
    if b == 0:
        rhs = a_part
    elif b > 0:
        rhs = f"{a_part} + {sympy.sstr(b)}"
    else:
        rhs = f"{a_part} - {sympy.sstr(-b)}"
    return f"y = {rhs}"


@register_recipe("math.draw_linear_fraction", provides_concepts=_DRAW_FRACTION_CONCEPTS)
def draw_linear_fraction(ctx: CellContext, rng: Rng) -> MR:
    """分数の傾きの直線を格子点を通るようにかく（answer-first・graph_table「かく」Lv3）。

    傾き p/q（frac_range で q≥2・既約・非整数）と切片 b を選ぶ。独立ソルバ
    `math.draw_linear_features_fraction` で採点用の特徴（傾き・切片・通る格子点 (q,p+b)）を得る。
    問題図は空の方眼、模範解答図は直線つき。dup_key は実質 (p,q,b)。
    """
    prm = ctx.spec_level.params
    slope = draw(prm["slope_domain"], rng)  # frac_range → 非整数・非ゼロの既約 Rational
    b = draw(prm["intercept_domain"], rng)

    slope_s = sympy.Rational(slope)
    b_s = sympy.nsimplify(b)
    p_num = sympy.Integer(slope_s.p)
    q_den = sympy.Integer(slope_s.q)

    solver = REGISTRY.solver("math.draw_linear_features_fraction")
    sol = cast(Solution, solver(p_num, q_den, b_s))
    assert isinstance(sol.answer, GraphAnswer)
    expected_feature_sreprs = {
        sympy.srepr(slope_s),
        sympy.srepr(sympy.Tuple(sympy.Integer(0), b_s)),
        sympy.srepr(sympy.Tuple(q_den, p_num + b_s)),
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: 想定特徴 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    pts = [
        str((sympy.Integer(0), b_s)),
        str((q_den, p_num + b_s)),
    ]
    render_params = {"a": str(slope_s), "b": str(b_s), "pts": pts}
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

    labels = tick_labels_from_params({"pts": pts})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"p": str(p_num), "q": str(q_den), "b": str(b_s), "a": str(slope_s), "pts": pts},
        given={"expression": _format_line_display_frac(slope_s, b_s)},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_linear_fraction"),
    )


# ---------------------------------------------------------------------------
# math.draw_segment（g2_l23.graph_table Lv2 用）— 横展開・P1/C5
# 変域つき1次関数 y=ax+b（x_lo≦/<x≦/<x_hi）を、端点の開閉（●/○）を区別して線分としてかく。
# 新 solver draw_segment_features（端点2つ・開閉を srepr flag で区別）＋新 visual render_segment。
# 答えは GraphAnswer。問題図＝空の方眼。given=expression（式）+x_domain（不等号つき変域）。
# ---------------------------------------------------------------------------
_DRAW_SEGMENT_CONCEPTS = [
    "linear_function.draw_segment",
]


def _format_segment_x_domain(
    x_lo: sympy.Expr, x_hi: sympy.Expr, closed_lo: bool, closed_hi: bool
) -> str:
    """変域の表示（例: "-1 ≦ x ≦ 2", "-1 < x ≦ 2"）。等号の有無が端点の開閉を表す。"""
    lo_sign = "≦" if closed_lo else "<"
    hi_sign = "≦" if closed_hi else "<"
    return f"{_fmt_number(x_lo)} {lo_sign} x {hi_sign} {_fmt_number(x_hi)}"


@register_recipe("math.draw_segment", provides_concepts=_DRAW_SEGMENT_CONCEPTS)
def draw_segment(ctx: CellContext, rng: Rng) -> MR:
    """変域つき1次関数を端点の開閉を区別して線分としてかく（answer-first・「かく」Lv2）。

    傾き a(≠0)・切片 b・変域 [x_lo, x_hi]（x_lo<x_hi）・両端の開閉 closed_lo/closed_hi を選ぶ。
    端点 (x_lo, a·x_lo+b)・(x_hi, a·x_hi+b) は整数（a,b,x 整数）。答え（両端点＋開閉）は独立ソルバ
    `math.draw_segment_features` で再計算し一致を assert。問題図は空の方眼、模範解答図は端点マーカー
    つきの線分（render_segment_solution_svg）。
    """
    p = ctx.spec_level.params
    a = draw(p["slope_domain"], rng)
    b = draw(p["intercept_domain"], rng)
    x_lo, x_hi = sorted(draw_many(p["x_domain_endpoints"], rng, k=2))  # 相異な2整数を昇順に
    closed_lo = draw(p["closed_domain"], rng)  # 素の配列 [True, False]
    closed_hi = draw(p["closed_domain"], rng)

    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    x_lo_s, x_hi_s = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    cl, ch = bool(closed_lo), bool(closed_hi)
    y_lo = a_s * x_lo_s + b_s
    y_hi = a_s * x_hi_s + b_s

    solver = REGISTRY.solver("math.draw_segment_features")
    sol = cast(Solution, solver(a_s, b_s, x_lo_s, x_hi_s, cl, ch))
    assert isinstance(sol.answer, GraphAnswer)
    expected_feature_sreprs = {
        sympy.srepr(sympy.Tuple(x_lo_s, y_lo, sympy.Integer(1 if cl else 0))),
        sympy.srepr(sympy.Tuple(x_hi_s, y_hi, sympy.Integer(1 if ch else 0))),
    }
    assert {f.srepr for f in sol.answer.features} == expected_feature_sreprs, (
        f"double-solve 不一致: 想定端点 {expected_feature_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    pts = [str((x_lo_s, y_lo)), str((x_hi_s, y_hi))]
    render_params: dict[str, Any] = {
        "a": str(a_s), "b": str(b_s),
        "seg_x_lo": str(x_lo_s), "seg_x_hi": str(x_hi_s),
        "closed_lo": cl, "closed_hi": ch, "pts": pts,
    }
    solution_svg = render_segment_solution_svg(render_params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_segment",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    labels = tick_labels_from_params({"pts": pts})
    visual_plan = VisualPlan(
        style="grid",
        labels=labels,
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "a": str(a_s), "b": str(b_s),
            "seg_x_lo": str(x_lo_s), "seg_x_hi": str(x_hi_s),
            "closed_lo": cl, "closed_hi": ch, "pts": pts,
        },
        given={
            "expression": _format_parallel_line_display(a_s, b_s),
            "x_domain": _format_segment_x_domain(x_lo_s, x_hi_s, cl, ch),
        },
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_segment"),
    )


# ---------------------------------------------------------------------------
# math.evaluate_linear_fraction（g2_l28.calculation Lv1 用）— 横展開・P1/C5
# 分数係数の1次関数 y=(p/q)x+b に x を代入して y を求める。solver は既存 evaluate_linear_at_x
# （g2_l19 と共有）を再利用＝新 solver ゼロ。x0 を分母 q の倍数に選び y を整数に保つ。
# g2_l19（整数係数）と別セル＝分数係数の代入という別の練習。asked=value。図なし。
# ---------------------------------------------------------------------------
_EVALUATE_FRACTION_CONCEPTS = [
    "linear_function.evaluate_at_x_fraction",
]


@register_recipe("math.evaluate_linear_fraction", provides_concepts=_EVALUATE_FRACTION_CONCEPTS)
def evaluate_linear_fraction(ctx: CellContext, rng: Rng) -> MR:
    """分数係数の1次関数 y=(p/q)x+b に x を代入して y を求める（answer-first・calculation Lv1）。

    傾き p/q（frac_range で非整数）・切片 b・倍率 m を選び、x0 = q·m（分母の倍数）とすることで
    y = (p/q)·(q·m)+b = p·m+b が必ず整数になる（分数係数でも答えは clean な整数）。答えと steps は
    既存ソルバ `math.evaluate_linear_at_x`（g2_l19 と共有）を再利用して再計算し一致を assert。
    """
    p = ctx.spec_level.params
    slope = draw(p["slope_domain"], rng)  # frac_range → 非整数の既約 Rational
    b = draw(p["intercept_domain"], rng)
    m = draw(p["x_mult_domain"], rng)

    slope_s = sympy.Rational(slope)
    b_s = sympy.nsimplify(b)
    q = sympy.Integer(slope_s.q)
    x0 = q * sympy.nsimplify(m)  # 分母の倍数 → 代入後の y は整数

    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    sol = cast(Solution, solver(slope_s, b_s, x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    y = slope_s * x0 + b_s
    assert sol.answer.srepr == sympy.srepr(y), (
        f"double-solve 不一致: 構成 y={y} != solver 再計算 {sol.answer.srepr}"
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
        params={"a": str(slope_s), "b": str(b_s), "x0": str(x0)},
        given={
            "expression": _format_line_display_frac(slope_s, b_s),
            "input_value": f"x = {_fmt_number(x0)}",
        },
        sub_questions=[sub_question],
        provenance=Provenance(recipe="math.evaluate_linear_fraction"),
    )


# ---------------------------------------------------------------------------
# math.solve_system_elimination（g2_l11.calculation Lv1 用）— 横展開#11・連立クラスタへ横展開
# 加減法（係数の絶対値が等しい）。答え(x,y)は既存 intersection_of_two_lines を再利用（新solverゼロ）。
# ---------------------------------------------------------------------------
_SOLVE_SYSTEM_ELIM_CONCEPTS = [
    "simultaneous_equations.solve_by_elimination",
]


@register_recipe("math.solve_system_elimination", provides_concepts=_SOLVE_SYSTEM_ELIM_CONCEPTS)
def solve_system_elimination(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式を加減法で解く（answer-first・calculation Lv1・係数の絶対値が等しい）。

    解 (x0,y0) を先に選び、y の係数を両式で同じ b にとる（A1≠A2）。C1,C2 を逆算すると、
    2式を辺々引くだけで y が消える＝「係数の絶対値が等しい」加減法。答え (x0,y0) は既存
    solver `math.intersection_of_two_lines`（g2_l27 と共有・交点＝連立解）で再計算し一致を確認。
    steps は加減法の手順（幾何 narration の交点 solver とは別に、代数の手順を書く）。図なし。
    """
    p = ctx.spec_level.params
    x0 = draw(p["x_domain"], rng)
    y0 = draw(p["y_domain"], rng)
    a1, a2 = draw_many(p["x_coeff_pair_domain"], rng, k=2)  # x の係数（相異＝非平行）
    bcoef = draw(p["y_coeff_domain"], rng)  # y の係数（両式で共通・正）

    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a1_s, a2_s = sympy.nsimplify(a1), sympy.nsimplify(a2)
    b_s = sympy.nsimplify(bcoef)
    c1_s = a1_s * x0_s + b_s * y0_s
    c2_s = a2_s * x0_s + b_s * y0_s

    coeffs1 = [a1_s, b_s, c1_s]
    coeffs2 = [a2_s, b_s, c2_s]
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs1), tuple(coeffs2), "elimination"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0_s, y0_s)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成解 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    disp1 = _format_two_var_equation_display(a1_s, b_s, c1_s)
    disp2 = _format_two_var_equation_display(a2_s, b_s, c2_s)
    steps = [
        Step(
            op="identify_equal_coeff",
            args=[disp1, disp2],
            result_srepr=sympy.srepr(b_s),
            result_display=f"y の係数はどちらも {_fmt_number(b_s)}",
            narration="y の係数が等しいので、辺々を引いて y を消去する。",
        ),
        Step(
            op="eliminate_and_solve_x",
            args=[],
            result_srepr=sympy.srepr(x0_s),
            result_display=f"x = {_fmt_number(x0_s)}",
            narration="残った式から x の値を求める。",
        ),
        Step(
            op="back_substitute",
            args=[_fmt_number(x0_s)],
            result_srepr=sympy.srepr(y0_s),
            result_display=f"y = {_fmt_number(y0_s)}",
            narration="求めた x を一方の式に代入して y を求める。",
        ),
    ]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
        answer=sol.answer,
        steps=steps,
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
            "method": "elimination",
        },
        given={"equation_a": disp1, "equation_b": disp2},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_system_elimination"),
    )


# ---------------------------------------------------------------------------
# math.solve_system_substitution（g2_l13.calculation Lv1/Lv2 用）— 横展開#12・連立クラスタ
# 代入法。答え(x,y)は既存 intersection_of_two_lines を再利用（新solverゼロ）。
# レベル間は steps の op 列で構造を変える（level_sep=fp 相異の必須）:
#   Lv1 "prepared" = そのまま代入 [substitute_expr, solve_for_x, back_substitute]（3手）
#   Lv2 "isolate"  = 1文字について解いてから代入 [isolate_variable, substitute_expr,
#                    solve_for_y, back_substitute]（4手・前処理1手を足す）
# ---------------------------------------------------------------------------
_SOLVE_SYSTEM_SUBST_CONCEPTS = [
    "simultaneous_equations.solve_by_substitution",
]


@register_recipe("math.solve_system_substitution", provides_concepts=_SOLVE_SYSTEM_SUBST_CONCEPTS)
def solve_system_substitution(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式を代入法で解く（answer-first・calculation）。

    解 (x0,y0) を先に選び、2式を逆算する。非退化（2直線が非平行）は構成で保証する:
      - Lv1: 両式の y 係数を 1 にそろえ、x 係数を相異な整数対 (p,q) にとる（det=p-q≠0）。
        一方を y=… の解けた形で与える＝「そのまま代入」。
      - Lv2: eq_a を x 係数 1（x+b1·y=c1・|b1|≥2）に、eq_b を全係数 |·|≥2 にとる。
        |a2·b1|≥4 > |b2|≤3 なので det=b2−a2·b1≠0 が恒真。eq_a を x について解いてから代入。
    答え (x0,y0) は既存 solver `math.intersection_of_two_lines`（g2_l27 と共有）で再計算し一致を確認。
    steps は代入法の代数手順（交点 solver の幾何 narration とは別立て）。図なし（calculation）。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    x_sym, y_sym = sympy.symbols("x y")
    x0 = sympy.nsimplify(draw(p["x_domain"], rng))
    y0 = sympy.nsimplify(draw(p["y_domain"], rng))

    if mode == "prepared":
        # 両式 y 係数 1・x 係数対 (p_coef,q_coef) は相異（=非平行）。
        p_coef, q_coef = (sympy.nsimplify(v) for v in draw_many(p["x_coeff_pair_domain"], rng, k=2))
        m_s = -p_coef  # eq_a の解けた形 y = m x + k の傾き
        k_s = y0 - m_s * x0
        c2_s = q_coef * x0 + y0
        coeffs_a = [p_coef, sympy.Integer(1), k_s]  # p_coef x + y = k  (= y = m x + k)
        coeffs_b = [q_coef, sympy.Integer(1), c2_s]  # q_coef x + y = c2
        disp_a = _fmt_eq(y_sym, m_s * x_sym + k_s)
        disp_b = _fmt_eq(q_coef * x_sym + y_sym, c2_s)
        # 代入後の x だけの方程式: (q_coef + m) x = c2 - k
        coef_x = q_coef + m_s
        sub_eq_disp = _fmt_eq(coef_x * x_sym, c2_s - k_s)
        steps = [
            Step(
                op="substitute_expr",
                args=[disp_a, disp_b],
                result_srepr=sympy.srepr(sympy.Eq(coef_x * x_sym, c2_s - k_s)),
                result_display=sub_eq_disp,
                narration="一方の式の y を、もう一方の式に代入して x だけの方程式にする。",
            ),
            Step(
                op="solve_for_x",
                args=[sub_eq_disp],
                result_srepr=sympy.srepr(x0),
                result_display=f"x = {_fmt_number(x0)}",
                narration="x の値を求める。",
            ),
            Step(
                op="back_substitute",
                args=[_fmt_number(x0)],
                result_srepr=sympy.srepr(y0),
                result_display=f"y = {_fmt_number(y0)}",
                narration="求めた x を y = … の式に代入して y を求める。",
            ),
        ]
    elif mode == "isolate":
        # eq_a: x + b1 y = c1（x 係数 1・|b1|≥2）、eq_b: a2 x + b2 y = c2（全係数 |·|≥2）。
        b1_s = sympy.nsimplify(draw(p["eqa_y_coeff_domain"], rng))
        a2_s = sympy.nsimplify(draw(p["eqb_x_coeff_domain"], rng))
        b2_s = sympy.nsimplify(draw(p["eqb_y_coeff_domain"], rng))
        c1_s = x0 + b1_s * y0
        c2_s = a2_s * x0 + b2_s * y0
        coeffs_a = [sympy.Integer(1), b1_s, c1_s]  # x + b1 y = c1
        coeffs_b = [a2_s, b2_s, c2_s]  # a2 x + b2 y = c2
        disp_a = _fmt_eq(x_sym + b1_s * y_sym, c1_s)
        disp_b = _fmt_eq(a2_s * x_sym + b2_s * y_sym, c2_s)
        iso_disp = _fmt_eq(x_sym, c1_s - b1_s * y_sym)  # x = c1 - b1 y
        # 代入後の y だけの方程式: (b2 - a2 b1) y = c2 - a2 c1
        coef_y = b2_s - a2_s * b1_s
        sub_eq_disp = _fmt_eq(coef_y * y_sym, c2_s - a2_s * c1_s)
        steps = [
            Step(
                op="isolate_variable",
                args=[disp_a],
                result_srepr=sympy.srepr(sympy.Eq(x_sym, c1_s - b1_s * y_sym)),
                result_display=iso_disp,
                # narration に数字を書かない（例「係数が 1」の "1" が答えの値と衝突して
                # G-Q5t 偽陽性になる・§5-#9）。eq_a は常に x 係数 1 の「はじめの式」。
                narration="はじめの式を x について解く。",
            ),
            Step(
                op="substitute_expr",
                args=[iso_disp, disp_b],
                result_srepr=sympy.srepr(sympy.Eq(coef_y * y_sym, c2_s - a2_s * c1_s)),
                result_display=sub_eq_disp,
                narration="これをもう一方の式に代入して y だけの方程式にする。",
            ),
            Step(
                op="solve_for_y",
                args=[sub_eq_disp],
                result_srepr=sympy.srepr(y0),
                result_display=f"y = {_fmt_number(y0)}",
                narration="y の値を求める。",
            ),
            Step(
                op="back_substitute",
                args=[_fmt_number(y0)],
                result_srepr=sympy.srepr(x0),
                result_display=f"x = {_fmt_number(x0)}",
                narration="求めた y を x = … の式に代入して x を求める。",
            ),
        ]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs_a), tuple(coeffs_b), "substitute"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0, y0)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成解 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
        answer=sol.answer,
        steps=steps,
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
            "line_a": [str(c) for c in coeffs_a],
            "line_b": [str(c) for c in coeffs_b],
            "method": "substitute",
        },
        given={"equation_a": disp_a, "equation_b": disp_b},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_system_substitution"),
    )


# ---------------------------------------------------------------------------
# math.solve_system_elim_scaled（g2_l12.calculation Lv2/Lv3 用）— 横展開#13・連立クラスタ
# 加減法（係数をそろえる）。答え(x,y)は既存 intersection_of_two_lines を再利用（新solverゼロ）。
# レベル間は steps の先頭 op で構造を変える（level_sep=fp 相異の必須）:
#   Lv2 "scale_one"  = 片方を整数倍して係数をそろえる [scale_one_equation, ...]
#   Lv3 "scale_both" = 両式を別々に倍して最小公倍数にそろえる [scale_both_equations, ...]
# ---------------------------------------------------------------------------
_SOLVE_SYSTEM_ELIM_SCALED_CONCEPTS = [
    "simultaneous_equations.solve_by_elimination_scaled",
]


@register_recipe(
    "math.solve_system_elim_scaled", provides_concepts=_SOLVE_SYSTEM_ELIM_SCALED_CONCEPTS
)
def solve_system_elim_scaled(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式を加減法（係数をそろえる）で解く（answer-first・calculation）。

    解 (x0,y0) を先に選び、2式を逆算する。非退化（非平行）は構成で保証する:
      - Lv2 "scale_one": eq_a=a1·x+y=c1（|a1|≥2・y 係数 1）、eq_b=a2·x+b2·y=c2（|b2|≥2）。
        |a1·b2|≥4 > |a2|≤3 なので det=a1·b2−a2≠0。y 係数を eq_a の整数倍でそろえる。
      - Lv3 "scale_both": eq_a=a1·x+b1·y=c1（a1 奇数・|b1|=2）、eq_b=a2·x+b2·y=c2（|b2|=3）。
        a1·b2 は奇数・a2·b1 は偶数で det=a1·b2−a2·b1≠0（恒真）。|b1|,|b2| は互いに割り切れない
        ので両式を別々に倍して最小公倍数 6 にそろえる（真の Lv3）。
    答え (x0,y0) は既存 solver `math.intersection_of_two_lines`（method=elimination・g2_l11/l27 と
    共有）で再計算し一致を確認。steps は加減法の代数手順。図なし（calculation）。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    x_sym, y_sym = sympy.symbols("x y")
    x0 = sympy.nsimplify(draw(p["x_domain"], rng))
    y0 = sympy.nsimplify(draw(p["y_domain"], rng))

    def sign() -> sympy.Integer:
        return sympy.Integer(draw(p["sign_domain"], rng))

    if mode == "scale_one":
        # y は係数 (1, b2) で「片方を倍す」だけで消去できる易しい変数＝生徒はこの手を選ぶ。
        # x は係数を互いに素な大きさ (2,3) にして「両方倍す」が要る＝x では消しにくくする
        # （＝この題材は真に「片方を倍してそろえる」Lv2。係数が偶然そろって倍が要らない＝
        # g2_l11 相当への退化を構成で禁止する）。
        m1 = sympy.Integer(draw(p["x_coeff_mag_domain"], rng))  # |a1| ∈ {2,3}
        a1 = m1 * sign()
        a2 = (5 - m1) * sign()  # |a2| = 5-|a1| ∈ {3,2}（x 係数は互いに素・|·|≥2）
        b1 = sympy.Integer(1)  # eq_a の y 係数 1（これを整数倍してそろえる）
        b2 = sympy.Integer(draw(p["eqb_y_coeff_mag_domain"], rng)) * sign()  # |b2| ∈ {2,3}
        first_op = "scale_one_equation"
        scale_narr = "y の係数をそろえるため、一方の式を何倍かする。"
        # eq_a を b2 倍して y 係数を b2 にそろえた式（表示用）。
        scaled_disp = _fmt_eq(a1 * b2 * x_sym + b2 * y_sym, (x0 * a1 + b1 * y0) * b2)
    elif mode == "scale_both":
        # x 係数 (3,2)・y 係数 (2,3) いずれも互いに素で大きさ≥2＝どちらの変数も「両方倍す」が
        # 要る（真の Lv3）。|a1·b2|=9 > |a2·b1|=4 で det≠0 が恒真（非平行）。
        a1 = sympy.Integer(3) * sign()
        a2 = sympy.Integer(2) * sign()
        b1 = sympy.Integer(2) * sign()
        b2 = sympy.Integer(3) * sign()
        first_op = "scale_both_equations"
        scale_narr = "y の係数を最小公倍数にそろえるため、両方の式をそれぞれ何倍かする。"
        c1_tmp = x0 * a1 + b1 * y0
        c2_tmp = x0 * a2 + b2 * y0
        # eq_a を b2 倍・eq_b を b1 倍し、y 係数を b1·b2 にそろえた2式（表示用）。
        sa = _fmt_eq(a1 * b2 * x_sym + b1 * b2 * y_sym, c1_tmp * b2)
        sb = _fmt_eq(a2 * b1 * x_sym + b1 * b2 * y_sym, c2_tmp * b1)
        scaled_disp = f"{sa} , {sb}"
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    c1 = a1 * x0 + b1 * y0
    c2 = a2 * x0 + b2 * y0
    coeffs_a = [a1, b1, c1]
    coeffs_b = [a2, b2, c2]
    disp_a = _fmt_eq(a1 * x_sym + b1 * y_sym, c1)
    disp_b = _fmt_eq(a2 * x_sym + b2 * y_sym, c2)

    steps = [
        Step(
            op=first_op,
            args=[disp_a, disp_b],
            result_srepr=sympy.srepr(b1 * b2),
            result_display=scaled_disp,
            narration=scale_narr,
        ),
        Step(
            op="eliminate_and_solve_x",
            args=[scaled_disp],
            result_srepr=sympy.srepr(x0),
            result_display=f"x = {_fmt_number(x0)}",
            narration="2式を加減して y を消去し、x を求める。",
        ),
        Step(
            op="back_substitute",
            args=[_fmt_number(x0)],
            result_srepr=sympy.srepr(y0),
            result_display=f"y = {_fmt_number(y0)}",
            narration="求めた x をもとの式に代入して y を求める。",
        ),
    ]

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs_a), tuple(coeffs_b), "elimination"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0, y0)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成解 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
        answer=sol.answer,
        steps=steps,
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
            "line_a": [str(c) for c in coeffs_a],
            "line_b": [str(c) for c in coeffs_b],
            "method": "elimination",
        },
        given={"equation_a": disp_a, "equation_b": disp_b},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_system_elim_scaled"),
    )


# ---------------------------------------------------------------------------
# math.solve_system_preprocessed（g2_l14.calculation Lv2/Lv3 用）— 横展開#14・連立クラスタ
# いろいろな連立方程式（前処理を伴う）。答え(x,y)は前処理後の整数系に対し既存
# intersection_of_two_lines を再利用（新solverゼロ）。レベル間は前処理 op で構造を変える:
#   Lv2 "expand_parens"   = かっこを展開して整数係数に直す [expand_parentheses, ...]
#   Lv3 "clear_fractions" = 分数を払って整数化する         [clear_denominators, ...]
# ---------------------------------------------------------------------------
_SOLVE_SYSTEM_PREPROCESSED_CONCEPTS = [
    "simultaneous_equations.solve_with_preprocessing",
]


@register_recipe(
    "math.solve_system_preprocessed", provides_concepts=_SOLVE_SYSTEM_PREPROCESSED_CONCEPTS
)
def solve_system_preprocessed(ctx: CellContext, rng: Rng) -> MR:
    """前処理を伴う連立方程式を解く（answer-first・calculation）。

    解 (x0,y0) を先に選び、前処理後の整数係数の連立系（非退化は係数の大きさで恒真化）を
    逆算し、それを未整理の見かけ（かっこ／分数）で提示する。答え (x0,y0) は前処理後の整数系に
    対して既存 solver `math.intersection_of_two_lines`（g2_l11/l12/l27 と共有）で再計算し一致を確認。
      - Lv2 "expand_parens": eq_a=k(x+s)+m·y=r、eq_b=a·x−(y+t)=u。展開すると整数係数の系
        (k, m, ·), (a, −1, ·) になる。|a·m|≥4 > k≤3 で det=−k−a·m≠0 が恒真。
      - Lv3 "clear_fractions": 非退化な整数系（|A1|=3,|A2|=2,|B1|=2,|B2|=3・det≠0 恒真）を作り、
        各式を da,db で割った分数係数の見かけで提示する。分数を払うと元の整数系に戻る。
    steps は前処理→加減法。図なし（calculation）。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    x_sym, y_sym = sympy.symbols("x y")
    x0 = sympy.nsimplify(draw(p["x_domain"], rng))
    y0 = sympy.nsimplify(draw(p["y_domain"], rng))

    def sign() -> sympy.Integer:
        return sympy.Integer(draw(p["sign_domain"], rng))

    if mode == "expand_parens":
        k = sympy.Integer(draw(p["outer_coeff_domain"], rng))  # かっこ前の係数（正・2〜3）
        s = sympy.Integer(draw(p["offset_domain"], rng))  # かっこ内オフセット x+s（≠0）
        m = sympy.Integer(draw(p["mag_domain"], rng)) * sign()  # eq_a の y 係数 |m|∈{2,3}
        a = sympy.Integer(draw(p["mag_domain"], rng)) * sign()  # eq_b の x 係数 |a|∈{2,3}
        t = sympy.Integer(draw(p["offset_domain"], rng))  # eq_b のかっこ内 y+t（≠0）
        # 展開後の整数系: eq_a= k x + m y = k x0 + m y0 / eq_b= a x − y = a x0 − y0
        A1, B1 = k, m
        A2, B2 = a, sympy.Integer(-1)
        C1 = A1 * x0 + B1 * y0
        C2 = A2 * x0 + B2 * y0
        r = k * (x0 + s) + m * y0  # eq_a 右辺（かっこ形のまま）
        u = a * x0 - (y0 + t)  # eq_b 右辺（かっこ形のまま）
        paren_a = f"{_fmt_number(k)}(x {'+' if s > 0 else '-'} {_fmt_number(abs(s))})"
        y_sign = "+" if m > 0 else "-"
        y_term = _fmt_expr(abs(m) * y_sym)
        disp_a = f"{paren_a} {y_sign} {y_term} = {_fmt_number(r)}"
        paren_b = f"(y {'+' if t > 0 else '-'} {_fmt_number(abs(t))})"
        disp_b = f"{_fmt_expr(a * x_sym)} - {paren_b} = {_fmt_number(u)}"
        cleared_a = _fmt_eq(A1 * x_sym + B1 * y_sym, C1)
        cleared_b = _fmt_eq(A2 * x_sym + B2 * y_sym, C2)
        first_op = "expand_parentheses"
        pre_narr = "かっこを展開して整数の連立方程式に直す。"
        cleared_disp = f"{cleared_a} , {cleared_b}"
    elif mode == "clear_fractions":
        # 非退化な整数系（互いに素な大きさ・det≠0 恒真）を作り、各式を割って分数で提示。
        A1 = sympy.Integer(3) * sign()
        B1 = sympy.Integer(2) * sign()
        A2 = sympy.Integer(2) * sign()
        B2 = sympy.Integer(3) * sign()
        C1 = A1 * x0 + B1 * y0
        C2 = A2 * x0 + B2 * y0
        da = sympy.Integer(draw(p["denom_domain"], rng))
        db = sympy.Integer(draw(p["denom_domain"], rng))
        disp_a = _fmt_eq(
            sympy.Rational(A1, da) * x_sym + sympy.Rational(B1, da) * y_sym,
            sympy.Rational(C1, da),
        )
        disp_b = _fmt_eq(
            sympy.Rational(A2, db) * x_sym + sympy.Rational(B2, db) * y_sym,
            sympy.Rational(C2, db),
        )
        cleared_a = _fmt_eq(A1 * x_sym + B1 * y_sym, C1)
        cleared_b = _fmt_eq(A2 * x_sym + B2 * y_sym, C2)
        first_op = "clear_denominators"
        pre_narr = "分母を払って整数の連立方程式に直す。"
        cleared_disp = f"{cleared_a} , {cleared_b}"
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    coeffs_a = [A1, B1, C1]
    coeffs_b = [A2, B2, C2]
    steps = [
        Step(
            op=first_op,
            args=[disp_a, disp_b],
            result_srepr=sympy.srepr([sympy.Eq(A1 * x_sym + B1 * y_sym, C1),
                                      sympy.Eq(A2 * x_sym + B2 * y_sym, C2)]),
            result_display=cleared_disp,
            narration=pre_narr,
        ),
        Step(
            op="eliminate_and_solve_x",
            args=[cleared_disp],
            result_srepr=sympy.srepr(x0),
            result_display=f"x = {_fmt_number(x0)}",
            narration="整理した連立方程式を加減法で解いて x を求める。",
        ),
        Step(
            op="back_substitute",
            args=[_fmt_number(x0)],
            result_srepr=sympy.srepr(y0),
            result_display=f"y = {_fmt_number(y0)}",
            narration="求めた x をもとの式に代入して y を求める。",
        ),
    ]

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs_a), tuple(coeffs_b), "elimination"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0, y0)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成解 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
        answer=sol.answer,
        steps=steps,
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
            "line_a": [str(c) for c in coeffs_a],
            "line_b": [str(c) for c in coeffs_b],
            "method": "elimination",
        },
        given={"equation_a": disp_a, "equation_b": disp_b},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_system_preprocessed"),
    )


# ---------------------------------------------------------------------------
# math.solve_system_abc（g2_l15.calculation Lv2 用）— 横展開#15・連立クラスタ（A=B=C 形）
# A=B=C を A=C, B=C の2式に組み替えて解く。答え(x,y)は既存 intersection_of_two_lines を再利用。
# 単一レベル（level_sep のペア無し）。
# ---------------------------------------------------------------------------
_SOLVE_SYSTEM_ABC_CONCEPTS = [
    "simultaneous_equations.solve_abc_form",
]


@register_recipe("math.solve_system_abc", provides_concepts=_SOLVE_SYSTEM_ABC_CONCEPTS)
def solve_system_abc(ctx: CellContext, rng: Rng) -> MR:
    """A=B=C 形の等式を連立にして解く（answer-first・calculation Lv2）。

    A=a1·x+b1·y, B=a2·x+b2·y+k, C=V（定数）を A=B=C=V が解 (x0,y0) で成り立つよう逆算し、
    「A = B = C」の見かけで提示する。組み替えた2式 A=C（a1·x+b1·y=V）, B=C（a2·x+b2·y=V−k）は
    既存 solver `math.intersection_of_two_lines`（連立クラスタ共有）で解を検算。非退化は係数の
    大きさで恒真化（|a1|=3,|a2|=2,|b1|=2,|b2|=3・|a1·b2|=9>|a2·b1|=4 → det≠0）。図なし。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    x0 = sympy.nsimplify(draw(p["x_domain"], rng))
    y0 = sympy.nsimplify(draw(p["y_domain"], rng))

    def sign() -> sympy.Integer:
        return sympy.Integer(draw(p["sign_domain"], rng))

    a1 = sympy.Integer(3) * sign()
    b1 = sympy.Integer(2) * sign()
    a2 = sympy.Integer(2) * sign()
    b2 = sympy.Integer(3) * sign()
    v = a1 * x0 + b1 * y0  # 共通の値 C = V（A=C が解で成立）
    k = v - (a2 * x0 + b2 * y0)  # B の定数項（B=C が解で成立）

    # 組み替えた整数系: A=C → a1 x + b1 y = V / B=C → a2 x + b2 y = V − k
    A1, B1, C1 = a1, b1, v
    A2, B2, C2 = a2, b2, v - k
    coeffs_a = [A1, B1, C1]
    coeffs_b = [A2, B2, C2]

    a_disp = _fmt_expr(a1 * x_sym + b1 * y_sym)
    b_disp = _fmt_expr(a2 * x_sym + b2 * y_sym + k)
    abc_disp = f"{a_disp} = {b_disp} = {_fmt_number(v)}"
    split_disp = f"{_fmt_eq(a1 * x_sym + b1 * y_sym, C1)} , {_fmt_eq(a2 * x_sym + b2 * y_sym, C2)}"

    steps = [
        Step(
            op="split_abc_equation",
            args=[abc_disp],
            result_srepr=sympy.srepr([sympy.Eq(a1 * x_sym + b1 * y_sym, C1),
                                      sympy.Eq(a2 * x_sym + b2 * y_sym, C2)]),
            result_display=split_disp,
            narration="A=B=C を A=C と B=C の2つの式に分けて連立方程式にする。",
        ),
        Step(
            op="eliminate_and_solve_x",
            args=[split_disp],
            result_srepr=sympy.srepr(x0),
            result_display=f"x = {_fmt_number(x0)}",
            narration="連立方程式を解いて x を求める。",
        ),
        Step(
            op="back_substitute",
            args=[_fmt_number(x0)],
            result_srepr=sympy.srepr(y0),
            result_display=f"y = {_fmt_number(y0)}",
            narration="求めた x をもとの式に代入して y を求める。",
        ),
    ]

    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(tuple(coeffs_a), tuple(coeffs_b), "elimination"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected_pt = sympy.Tuple(x0, y0)
    assert sol.answer.srepr == sympy.srepr(expected_pt), (
        f"double-solve 不一致: 構成解 {expected_pt} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="solution",
        answer=sol.answer,
        steps=steps,
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
            "line_a": [str(c) for c in coeffs_a],
            "line_b": [str(c) for c in coeffs_b],
            "method": "elimination",
        },
        given={"equation": abc_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_system_abc"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_slope_direction（g2_l21.knowledge Lv1 用）— 横展開#16・knowledge capability 初
# 1次関数のグラフの向き（傾きの符号→右上がり/右下がり）を単一選択で問う。答えは ChoiceAnswer。
# knowledge form の初セル（ChoiceAnswer 生成経路・初）。無限性は係数 a,b のパラメータ化で満たす。
# ---------------------------------------------------------------------------
_KNOWLEDGE_SLOPE_DIRECTION_CONCEPTS = [
    "linear_function.slope_sign_to_direction",
]


@register_recipe(
    "math.knowledge_slope_direction", provides_concepts=_KNOWLEDGE_SLOPE_DIRECTION_CONCEPTS
)
def knowledge_slope_direction(ctx: CellContext, rng: Rng) -> MR:
    """1次関数のグラフの向きを傾きの符号から判別する（knowledge・answer-first）。

    傾き a（≠0）と切片 b を選び、式 y=ax+b を statement として提示。向き（右上がり/右下がり）は
    独立 solver `math.linear_direction_from_slope` が a の符号だけから判定（b は無関係＝double-solve）。
    答えは ChoiceAnswer（correct=向き・distractors=もう一方・fact_id=規則ID）。図なし（knowledge）。
    無限性は a,b のパラメータ化で満たす（答えは2値だが dup_key は params(a,b) で測る）。
    """
    p = ctx.spec_level.params
    x_sym = sympy.symbols("x")
    a = sympy.nsimplify(draw(p["slope_domain"], rng))  # 傾き（≠0）
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))  # 切片（向きに無関係）
    y_sym = sympy.symbols("y")
    statement = _fmt_eq(y_sym, a * x_sym + b)  # "y = -3x + 4"

    solver = REGISTRY.solver("math.linear_direction_from_slope")
    sol = cast(Solution, solver(a))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "右上がり" if a > 0 else "右下がり"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: 構成向き {expected} != solver 判定 {sol.answer.correct}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"a": str(a), "b": str(b)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_slope_direction"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_classify_line_signs（g2_l21.knowledge Lv2 用）— 横展開・P1/C5
# 傾き・切片の符号を合わせてグラフのようすを4分類で判別・適用する。Lv1（向き単独）と
# op 列（identify_slope_sign→identify_intercept_sign→combine_signs）が異なる＝level_sep。
# ---------------------------------------------------------------------------
_KNOWLEDGE_CLASSIFY_SIGNS_CONCEPTS = [
    "linear_function.classify_line_by_signs",
]


@register_recipe(
    "math.knowledge_classify_line_signs", provides_concepts=_KNOWLEDGE_CLASSIFY_SIGNS_CONCEPTS
)
def knowledge_classify_line_signs(ctx: CellContext, rng: Rng) -> MR:
    """傾き・切片の符号からグラフのようすを判別・適用する（knowledge・answer-first・Lv2）。

    傾き a（≠0）・切片 b（≠0＝判別対象）を選び、式 y=ax+b を statement として提示。グラフのようす
    （向き×y 軸のどちら側で交わるか＝4分類）は独立 solver `math.classify_line_by_signs` が a,b の
    符号だけから判定する（double-solve）。答えは ChoiceAnswer（テキスト4択・数字なしで G-Q5t 素通り）。
    無限性は a,b のパラメータ化で満たす（答えは4値だが dup_key は params(a,b) で測る）。
    """
    p = ctx.spec_level.params
    x_sym = sympy.symbols("x")
    y_sym = sympy.symbols("y")
    a = sympy.nsimplify(draw(p["slope_domain"], rng))  # 傾き（≠0）
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))  # 切片（≠0・判別対象）
    statement = _fmt_eq(y_sym, a * x_sym + b)  # "y = -3x + 4"

    solver = REGISTRY.solver("math.classify_line_by_signs")
    sol = cast(Solution, solver(a, b))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"a": str(a), "b": str(b)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_classify_line_signs"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_range_endpoint（g2_l23.knowledge Lv1 用）— 横展開#17・knowledge 償却の実証
# 変域の端点が含まれるか（≦/≧なら含む・</>なら含まない）を単一選択で問う。#16 で開通した
# knowledge capability（ChoiceAnswer 経路）を spec＋小規則 solver だけで再利用＝償却の実証。
# ---------------------------------------------------------------------------
_KNOWLEDGE_RANGE_ENDPOINT_CONCEPTS = [
    "linear_function.range_endpoint_inclusion",
]


@register_recipe(
    "math.knowledge_range_endpoint", provides_concepts=_KNOWLEDGE_RANGE_ENDPOINT_CONCEPTS
)
def knowledge_range_endpoint(ctx: CellContext, rng: Rng) -> MR:
    """変域の端点がグラフにふくまれるかを不等号の種類から判別する（knowledge・answer-first）。

    包含は不等号の等号の有無だけで決まる（端点値・関数は無関係）。独立 solver
    `math.range_endpoint_inclusion` が inclusive の真偽から判定（double-solve）。答えは ChoiceAnswer。
    無限性(F-3)は「1次関数 y=ax+b のグラフで変域…」の a,b,端点 n のパラメータ化で満たす
    （包含に無関係な a,b が式の見かけを変え、dup_key は params で広く分散する）。図なし（knowledge）。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    a = sympy.nsimplify(draw(p["slope_domain"], rng))  # 見かけの1次関数の傾き（≠0・包含に無関係）
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))  # 切片（包含に無関係）
    n = sympy.nsimplify(draw(p["endpoint_domain"], rng))  # 変域の端点の値
    inclusive = int(draw(p["inclusive_domain"], rng))  # 1=等号あり(≦) / 0=等号なし(<)
    sym = "≦" if inclusive else "<"
    eq = _fmt_eq(y_sym, a * x_sym + b)
    statement = f"1次関数 {eq} のグラフで、x の変域が {_fmt_number(n)} {sym} x のとき"

    solver = REGISTRY.solver("math.range_endpoint_inclusion")
    sol = cast(Solution, solver(bool(inclusive)))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "ふくまれる" if inclusive else "ふくまれない"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: 構成 {expected} != solver 判定 {sol.answer.correct}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"a": str(a), "b": str(b), "n": str(n), "inclusive": inclusive},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_range_endpoint"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_verify_solution（g2_l10.knowledge Lv2 用）— 横展開#18・knowledge 横展開
# 連立方程式の与えられた組(x,y)が解かを判定（○×）。knowledge capability（ChoiceAnswer）を
# 新しい小規則 solver verify_system_solution で再利用＝l10 の verify セルを開ける。
# ---------------------------------------------------------------------------
_KNOWLEDGE_VERIFY_SOLUTION_CONCEPTS = [
    "simultaneous_equations.verify_solution",
]


@register_recipe(
    "math.knowledge_verify_solution", provides_concepts=_KNOWLEDGE_VERIFY_SOLUTION_CONCEPTS
)
def knowledge_verify_solution(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式の組(x,y)が解かを判定する knowledge セル（answer-first）。

    真偽ビット truth を先に引き、非退化な連立系（解 (x0,y0)）を構成する。truth=1 なら候補
    (x0,y0) をそのまま、truth=0 なら x を delta（≠0）ずらして「解でない」候補にする（一意解の
    系では他の点は必ず少なくとも一方の式を満たさない）。独立 solver `math.verify_system_solution`
    が候補と係数だけから代入判定（double-solve・切片/真偽ビットは見ない）。答えは ChoiceAnswer。
    無限性(F-3)は 係数・解・候補・真偽 のパラメータ化で満たす。図なし（knowledge）。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")

    def sign() -> sympy.Integer:
        return sympy.Integer(draw(p["sign_domain"], rng))

    x0 = sympy.nsimplify(draw(p["x_domain"], rng))
    y0 = sympy.nsimplify(draw(p["y_domain"], rng))
    # 非退化（非平行）を係数の大きさで恒真化: |A1|=3,|A2|=2,|B1|=2,|B2|=3（|A1·B2|=9>|A2·B1|=4）。
    a1 = sympy.Integer(3) * sign()
    b1 = sympy.Integer(2) * sign()
    a2 = sympy.Integer(2) * sign()
    b2 = sympy.Integer(3) * sign()
    c1 = a1 * x0 + b1 * y0
    c2 = a2 * x0 + b2 * y0
    coeffs_a = [a1, b1, c1]
    coeffs_b = [a2, b2, c2]

    truth = int(draw(p["truth_domain"], rng))  # 1=解である / 0=解でない
    if truth:
        xc, yc = x0, y0
    else:
        delta = sympy.Integer(draw(p["perturb_domain"], rng))  # ≠0
        xc, yc = x0 + delta, y0  # 一意解の系なので少なくとも eq_a を満たさない＝解でない

    solver = REGISTRY.solver("math.verify_system_solution")
    sol = cast(Solution, solver(tuple(coeffs_a), tuple(coeffs_b), (xc, yc)))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "解である" if truth else "解でない"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: 構成 {expected} != solver 判定 {sol.answer.correct}"
    )

    system_disp = f"{_fmt_eq(a1 * x_sym + b1 * y_sym, c1)}, {_fmt_eq(a2 * x_sym + b2 * y_sym, c2)}"
    candidate_disp = f"x = {_fmt_number(xc)}, y = {_fmt_number(yc)}"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
            "line_a": [str(c) for c in coeffs_a],
            "line_b": [str(c) for c in coeffs_b],
            "candidate": f"({xc}, {yc})",
        },
        given={"statement": system_disp, "term_context": candidate_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_verify_solution"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_classify_linear（g2_l19.knowledge Lv2 用）— 横展開#19・knowledge verify型
# 与えられた式 y=… が x の1次関数かを単一選択で判別（式の種類で答えが変わる真の verify 型）。
# #16 で開通した knowledge capability（ChoiceAnswer 経路）を spec＋小規則 solver で再利用。
# ---------------------------------------------------------------------------
_KNOWLEDGE_CLASSIFY_LINEAR_CONCEPTS = [
    "linear_function.classify_as_linear",
]


@register_recipe(
    "math.knowledge_classify_linear", provides_concepts=_KNOWLEDGE_CLASSIFY_LINEAR_CONCEPTS
)
def knowledge_classify_linear(ctx: CellContext, rng: Rng) -> MR:
    """与式が1次関数かを判別する knowledge セル（answer-first・verify 型）。

    category（0=1次/1=定数/2=2次/3=反比例）を先に引き、対応する式 y=<rhs> を構成する。
    1次関数か否かは独立 solver `math.classify_linear_function` が式そのものを微分して判定
    （category ビットは見ない・double-solve）。答えは ChoiceAnswer（式の種類で correct が
    「1次関数である/ではない」に変わる真の verify 型）。無限性(F-3)は category と係数 a,b の
    パラメータ化で満たす。図なし（knowledge）。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    category = int(draw(p["category_domain"], rng))  # 0..3

    if category == 0:  # 1次関数: y = ax + b（a≠0）
        a = sympy.nsimplify(draw(p["coeff_domain"], rng))
        b = sympy.nsimplify(draw(p["intercept_domain"], rng))
        rhs = a * x_sym + b
    elif category == 1:  # 定数関数: y = c（c≠0・傾き0で1次関数でない）
        # 定数値は線形性判定に無関係な surface param。広い域で無限性(F-3)を稼ぐ（§7.7）。
        c = sympy.nsimplify(draw(p["const_domain"], rng))
        rhs = c
    elif category == 2:  # 2次関数: y = ax² + b（a≠0）
        a = sympy.nsimplify(draw(p["coeff_domain"], rng))
        b = sympy.nsimplify(draw(p["intercept_domain"], rng))
        rhs = a * x_sym**2 + b
    else:  # 反比例: y = k/x（k≠0）
        # 反比例定数も線形性判定に無関係な surface param。広い域で無限性を稼ぐ。
        k = sympy.nsimplify(draw(p["inverse_domain"], rng))
        rhs = k / x_sym

    solver = REGISTRY.solver("math.classify_linear_function")
    sol = cast(Solution, solver(rhs))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "1次関数である" if category == 0 else "1次関数ではない"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: 構成 category={category}（{expected}）"
        f" != solver 判定 {sol.answer.correct}"
    )

    statement = _fmt_eq(y_sym, rhs)  # 例 "y = 2x - 1" / "y = 2x² + 3" / "y = 3/x"

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"category": category, "rhs": str(rhs)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_classify_linear"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_rate_constant（g2_l20.knowledge Lv1 用）— 横展開#22（P1・C5）
# 1次関数の変化の割合はつねに一定で傾きに等しい、という性質の正しい説明を選ぶ。答え固定型。
# ---------------------------------------------------------------------------
_KNOWLEDGE_RATE_CONSTANT_CONCEPTS = [
    "linear_function.rate_of_change_is_constant",
]


@register_recipe(
    "math.knowledge_rate_constant", provides_concepts=_KNOWLEDGE_RATE_CONSTANT_CONCEPTS
)
def knowledge_rate_constant(ctx: CellContext, rng: Rng) -> MR:
    """1次関数の変化の割合の性質（つねに一定・傾きに等しい）の正しい説明を選ぶ（knowledge）。

    独立 solver `math.rate_of_change_is_constant` が正しい説明を返す（式によらず不変・答え固定型）。
    答えは ChoiceAnswer（correct 固定・distractors=誤った説明）。無限性(F-3)は具体式 y=ax+b の
    見かけ a,b（答えに無関係な surface param）で満たす（source_desc の設計モデル参照）。図なし。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    a = sympy.nsimplify(draw(p["slope_domain"], rng))
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))
    statement = _fmt_eq(y_sym, a * x_sym + b)

    solver = REGISTRY.solver("math.rate_of_change_is_constant")
    sol = cast(Solution, solver())
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"a": str(a), "b": str(b)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_rate_constant"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_equation_solution_set（g2_l26.knowledge Lv1 用）— 横展開#23（P1・C5）
# 2元1次方程式の解の集合は直線、という性質の想起。答え固定型。
# ---------------------------------------------------------------------------
_KNOWLEDGE_EQUATION_SOLUTION_SET_CONCEPTS = [
    "linear_function.equation_solution_set_is_line",
]


@register_recipe(
    "math.knowledge_equation_solution_set",
    provides_concepts=_KNOWLEDGE_EQUATION_SOLUTION_SET_CONCEPTS,
)
def knowledge_equation_solution_set(ctx: CellContext, rng: Rng) -> MR:
    """2元1次方程式 ax+by=c の解の集合が直線になる性質を問う（knowledge・答え固定型）。

    独立 solver `math.equation_solution_set_shape` が「直線」を返す（係数によらず不変）。答えは
    ChoiceAnswer（correct 固定）。無限性(F-3)は方程式の係数 a,b,c（答えに無関係な surface）で満たす。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    a = sympy.nsimplify(draw(p["coeff_domain"], rng))  # ≠0
    b = sympy.nsimplify(draw(p["coeff_domain"], rng))  # ≠0
    c = sympy.nsimplify(draw(p["const_domain"], rng))
    statement = _fmt_eq(a * x_sym + b * y_sym, c)  # 例 "3x + 2y = 6"

    solver = REGISTRY.solver("math.equation_solution_set_shape")
    sol = cast(Solution, solver())
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"a": str(a), "b": str(b), "c": str(c)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_equation_solution_set"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_system_intersection（g2_l27.knowledge Lv1 用）— 横展開#24（P1・C5）
# 連立方程式の解は2直線の交点、という性質の想起。答え固定型。
# ---------------------------------------------------------------------------
_KNOWLEDGE_SYSTEM_INTERSECTION_CONCEPTS = [
    "linear_function.system_solution_is_intersection",
]


@register_recipe(
    "math.knowledge_system_intersection",
    provides_concepts=_KNOWLEDGE_SYSTEM_INTERSECTION_CONCEPTS,
)
def knowledge_system_intersection(ctx: CellContext, rng: Rng) -> MR:
    """連立方程式の解が2直線の交点である性質を問う（knowledge・答え固定型）。

    独立 solver `math.system_solution_is_intersection` が「2直線の交点」を返す（係数によらず不変）。
    答えは ChoiceAnswer（correct 固定）。無限性(F-3)は連立の係数（答えに無関係な surface）で満たす。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    a1 = sympy.nsimplify(draw(p["coeff_domain"], rng))
    b1 = sympy.nsimplify(draw(p["coeff_domain"], rng))
    c1 = sympy.nsimplify(draw(p["const_domain"], rng))
    a2 = sympy.nsimplify(draw(p["coeff_domain"], rng))
    b2 = sympy.nsimplify(draw(p["coeff_domain"], rng))
    c2 = sympy.nsimplify(draw(p["const_domain"], rng))
    statement = (
        f"{_fmt_eq(a1 * x_sym + b1 * y_sym, c1)}, {_fmt_eq(a2 * x_sym + b2 * y_sym, c2)}"
    )

    solver = REGISTRY.solver("math.system_solution_is_intersection")
    sol = cast(Solution, solver())
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
            "line_a": [str(a1), str(b1), str(c1)],
            "line_b": [str(a2), str(b2), str(c2)],
        },
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_system_intersection"),
    )


# ---------------------------------------------------------------------------
# math.knowledge_coefficient_role（g2_l19.knowledge Lv1 用）— 横展開#21（P1・C5）
# 1次関数 y=ax+b の x の係数・定数項がグラフの何を表すか（傾き/切片）を単一選択で問う。
# which（係数/定数項）で答えが変わる（用語想起・#19 判別 Lv2 と op 列が異なり level_sep）。
# ---------------------------------------------------------------------------
_KNOWLEDGE_COEFFICIENT_ROLE_CONCEPTS = [
    "linear_function.coefficient_role",
]


@register_recipe(
    "math.knowledge_coefficient_role", provides_concepts=_KNOWLEDGE_COEFFICIENT_ROLE_CONCEPTS
)
def knowledge_coefficient_role(ctx: CellContext, rng: Rng) -> MR:
    """1次関数の式の x の係数・定数項が傾き・切片のどちらを表すかを問う（knowledge・answer-first）。

    which（slope=x の係数／intercept=定数項）を引き、具体式 y=ax+b を statement に提示。答えは
    独立 solver `math.linear_coefficient_role` が which だけから判定（式の値は無関係・double-solve）。
    答えは ChoiceAnswer（which で correct が「傾き/切片」に変わる用語想起型）。無限性(F-3)は which と
    式の見かけ a,b のパラメータ化で満たす（具体式で realize＝dup 分散のため。source_desc 参照）。図なし。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    which = "slope" if int(draw(p["which_domain"], rng)) == 0 else "intercept"
    a = sympy.nsimplify(draw(p["slope_domain"], rng))  # x の係数（見かけ・答えに無関係）
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))  # 定数項（見かけ・答えに無関係）
    statement = _fmt_eq(y_sym, a * x_sym + b)  # 例 "y = 3x + 5"
    term_context = "x の係数" if which == "slope" else "定数項"

    solver = REGISTRY.solver("math.linear_coefficient_role")
    sol = cast(Solution, solver(which))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "傾き" if which == "slope" else "切片"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: which={which}（{expected}）!= solver 判定 {sol.answer.correct}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
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
        params={"which": which, "a": str(a), "b": str(b)},
        given={"statement": statement, "term_context": term_context},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.knowledge_coefficient_role"),
    )


# ---------------------------------------------------------------------------
# math.linear_slope_as_rate（g2_l21.calculation Lv1 用）— 横展開#20（P1・C5）
# 1次関数 y=ax+b で x が1増加したときの y の増加量（＝変化の割合＝傾き a）を数値で求める。
# ---------------------------------------------------------------------------
_LINEAR_SLOPE_AS_RATE_CONCEPTS = [
    "linear_function.slope_as_rate_of_change",
]


@register_recipe(
    "math.linear_slope_as_rate", provides_concepts=_LINEAR_SLOPE_AS_RATE_CONCEPTS
)
def linear_slope_as_rate(ctx: CellContext, rng: Rng) -> MR:
    """1次関数の式から変化の割合（x が1増えたときの y の増加量＝傾き a）を求める（answer-first）。

    傾き a（≠0・±1除外）と切片 b を選び、式 y=ax+b を given.expression に提示。答えは傾き a を
    独立 solver `math.linear_slope_as_rate` が a だけから再計算（double-solve）。答えは数値。
    ★±1 を除外する理由: テンプレの「x が1増加」の "1" と答え a=±1 が G-Q5t で衝突するため
    （傾き ±1 は特別扱い＝この増加量セルの対象外とする。他の傾きで概念は十分伝わる）。
    無限性(F-3)は a,b のパラメータ化で満たす。図なし（calculation）。
    """
    p = ctx.spec_level.params
    x_sym, y_sym = sympy.symbols("x y")
    a = sympy.nsimplify(draw(p["slope_domain"], rng))  # 傾き（≠0・±1除外）
    b = sympy.nsimplify(draw(p["intercept_domain"], rng))  # 切片（増加量に無関係）
    expr = _fmt_eq(y_sym, a * x_sym + b)  # 例 "y = -4x + 1"

    solver = REGISTRY.solver("math.linear_slope_as_rate")
    sol = cast(Solution, solver(a))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(a), (
        f"double-solve 不一致: 構成傾き {a} != solver 再計算 {sol.answer.srepr}"
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
        params={"a": str(a), "b": str(b)},
        given={"expression": expr},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.linear_slope_as_rate"),
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
    # P1/C5: ダイヤグラム（時間-道のり）の2直線を連立し交点=出会いの時刻・道のりを求める
    # （g2_l30.find_value）。計算は intersection と同一なので同 recipe を再利用（新 recipe ゼロ）。
    "linear_function.diagram_intersection",
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
    "read_intersection_from_graph",
    "solve_system_elimination",
    "solve_system_substitution",
    "solve_system_elim_scaled",
    "solve_system_preprocessed",
    "solve_system_abc",
    "knowledge_slope_direction",
    "knowledge_range_endpoint",
    "knowledge_verify_solution",
    "knowledge_classify_linear",
    "knowledge_coefficient_role",
    "knowledge_rate_constant",
    "knowledge_equation_solution_set",
    "knowledge_system_intersection",
    "linear_slope_as_rate",
    "rate_of_change",
    "intersection",
    "y_range_from_domain",
    "expr_from_range",
]
