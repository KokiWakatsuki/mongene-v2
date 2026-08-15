"""比例・反比例の **グラフ**（graph_table）recipe（構成的生成・answer-first。§6.1）。

C4（g1 関数・比例と反比例）クラスタの visual セル（g1_l30 / l31 / l32 / l34 / l35 / l36）。
乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8）。構成した値は独立ソルバ
（`engine.packs.math.solvers.proportion_graph`）で再計算し、答えの一致を確認する
（double-solve）。

図の規約（実装設計 §6.4・§8.2 G-Q5v）:
- SVG 内の `<text>` は軸目盛だけ。`visual_plan.labels` は `tick_labels_from_params(params)`
  から機械的に作る（手で書かない）。
- 「読む」セルは読む対象そのもの（＝直線／曲線）を図に描き、答えの点・注記は描かない。
- 「かく」セルの問題図は**空の方眼**（elements に line/curve を宣言しない）。模範解答図は
  visual 純ヘルパ（`render_line_solution_svg` / `render_curve_solution_svg`）で描いて
  `GraphAnswer.solution_svg_ref` に格納する。
- 比例 y=ax は**直線**なので既存の `math.linear_graph` 経路（a=比例定数・b=0）を使う。
  反比例 y=a/x は `curve_kind="hyperbola"` の `math.curve_graph` 経路を使う。

G-Q5t（漏洩）の設計原則: **テンプレートに数字を一切書かない**。問題文に出る数値は
すべて `mr.given` 由来になるため、whitelist が本文の数値を必ず覆い、漏洩誤検出が
構造的に起こらない。narration にも数字を書かない（hints に narration が流れるため）。
"""
from __future__ import annotations

import math
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.recipes.polynomial import _domain_candidates
from engine.packs.math.solvers.arithmetic import fmt_number
from engine.packs.math.visuals.graph import (
    render_curve_solution_svg,
    render_line_solution_svg,
    tick_labels_from_params,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _cands(p: dict[str, Any], key: str) -> list[int]:
    return _domain_candidates(cast("dict[str, object]", p[key]))


def _pt_str(x: Any, y: Any) -> str:
    """描画ヘルパ（`_parse_point`）が読む代表点の書式 `"(2, 6)"`。"""
    return str((sympy.Integer(int(x)), sympy.Integer(int(y))))


def _fmt_pt(x: Any, y: Any) -> str:
    return f"({fmt_number(sympy.nsimplify(x))}, {fmt_number(sympy.nsimplify(y))})"


def _fmt_direct(a: sympy.Expr) -> str:
    if a == 1:
        return "y = x"
    if a == -1:
        return "y = -x"
    return f"y = {fmt_number(a)}x"


def _fmt_inverse(a: sympy.Expr) -> str:
    return f"y = {fmt_number(a)}/x"


def _grid_plan(labels: list[str], *, extra_kind: str | None = None) -> VisualPlan:
    """方眼＋軸（＋読む対象の線/曲線）の visual_plan。

    extra_kind=None は「かく」セルの問題図＝空の方眼（生徒が描き込む）。
    """
    elements = [VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})]
    if extra_kind is not None:
        elements.append(VisualElement(kind=extra_kind, attrs={}))
    return VisualPlan(style="grid", labels=labels, elements=elements)


def _mr(
    ctx: CellContext,
    *,
    params: dict[str, Any],
    given: dict[str, str],
    sub_question: SubQuestionMR,
    visual_plan: VisualPlan,
    recipe: str,
) -> MR:
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given=given,
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe=recipe),
    )


def _sub_question(ctx: CellContext, *, asked: str, answer: Any, steps: list[Any]) -> SubQuestionMR:
    return SubQuestionMR(
        label="(1)",
        asked=asked,
        answer=answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )


# ---------------------------------------------------------------------------
# math.read_coordinate_on_plane（g1_l30.graph_table Lv1）
# x座標・y座標の値から点の座標を書く（座標平面は空の方眼＝生徒が点をとる）。
# ---------------------------------------------------------------------------
_READ_COORDINATE_CONCEPTS = ["coordinate_plane.read_point_coordinate"]


@register_recipe("math.read_coordinate_on_plane", provides_concepts=_READ_COORDINATE_CONCEPTS)
def read_coordinate_on_plane(ctx: CellContext, rng: Rng) -> MR:
    """x座標・y座標から点の座標を答える（answer-first・graph_table Lv1）。

    組合せは (x0, y0) の2軸。座標平面は空の方眼で、生徒はそこに点をとりながら座標を
    確かめる（答えの点は図に先出ししない＝`labeled_answer_point` を宣言しない）。
    """
    p = ctx.spec_level.params
    x0 = int(draw(p["x_domain"], rng))
    y0 = int(draw(p["y_domain"], rng))

    solver = REGISTRY.solver("math.read_coordinate_components")
    sol = cast(Solution, solver(x0, y0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(x0), sympy.Integer(y0))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {"x0": x0, "y0": y0, "pts": [_pt_str(x0, y0), _pt_str(-x0, -y0)]}
    given = {
        "situation_params": (
            f"座標平面上に点Aがある。点Aのx座標は{fmt_number(sympy.Integer(x0))}、"
            f"y座標は{fmt_number(sympy.Integer(y0))}である"
        )
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.read_coordinate_on_plane",
    )


# ---------------------------------------------------------------------------
# math.reflect_point_on_plane（g1_l30.graph_table Lv2）
# 点Aから、原点対称の点Bとx軸対称の点Cの座標を求め、3点を座標平面に示す。
# ---------------------------------------------------------------------------
_REFLECT_POINT_CONCEPTS = ["coordinate_plane.reflect_point"]


@register_recipe("math.reflect_point_on_plane", provides_concepts=_REFLECT_POINT_CONCEPTS)
def reflect_point_on_plane(ctx: CellContext, rng: Rng) -> MR:
    """原点対称・x軸対称の点の座標を求める（answer-first・graph_table Lv2）。

    Lv1（座標を読む2手順）に対し、対称移動の2手順＋書き出しで op 列が変わる（level_sep）。
    問題図は空の方眼（3点は生徒がとる）。
    """
    p = ctx.spec_level.params
    x0 = int(draw(p["x_domain"], rng))
    y0 = int(draw(p["y_domain"], rng))

    solver = REGISTRY.solver("math.reflect_point_pair")
    sol = cast(Solution, solver(x0, y0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(
        sympy.Tuple(sympy.Integer(-x0), sympy.Integer(-y0)),
        sympy.Tuple(sympy.Integer(x0), sympy.Integer(-y0)),
    )
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {"x0": x0, "y0": y0, "pts": [_pt_str(x0, y0), _pt_str(-x0, -y0)]}
    given = {
        "situation_params": (
            f"座標平面上に点A{_fmt_pt(x0, y0)}、原点について点Aと対称な点B、"
            "x軸について点Aと対称な点Cをとりたい"
        )
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.reflect_point_on_plane",
    )


# ---------------------------------------------------------------------------
# math.read_proportion_graph_value（g1_l31.graph_table Lv1）
# 比例のグラフ（原点を通る直線）から、指定した x に対応する y をグラフで読む。
# ---------------------------------------------------------------------------
_READ_PROPORTION_GRAPH_CONCEPTS = ["direct_proportion.read_value_from_graph"]


@register_recipe(
    "math.read_proportion_graph_value", provides_concepts=_READ_PROPORTION_GRAPH_CONCEPTS
)
def read_proportion_graph_value(ctx: CellContext, rng: Rng) -> MR:
    """比例のグラフから対応する y の値を読む（answer-first・graph_table「読む」Lv1）。

    比例定数 a(≠0)・グラフが通ることを本文で示す点の x 座標 p・読み取る x 座標 x0 を
    構成する。値域は `value_abs_max`（|a*x| の上限）で有界化し、方眼が細かくなりすぎ
    ないようにする（図の可読性）。図には直線を描く（読む対象そのもの）。
    """
    p = ctx.spec_level.params
    v_max = int(p["value_abs_max"])
    x_abs = int(p["x_abs_max"])
    p_abs = int(p["point_abs_max"])

    a = int(draw(p["a_domain"], rng))
    x_cands = [v for v in range(-x_abs, x_abs + 1) if v != 0 and abs(a * v) <= v_max]
    x0 = int(draw({"int_set": x_cands}, rng))
    p_cands = [v for v in range(-p_abs, p_abs + 1) if v != 0 and abs(a * v) <= v_max and v != x0]
    p_x = int(draw({"int_set": p_cands}, rng))

    solver = REGISTRY.solver("math.read_value_on_proportion_graph")
    sol = cast(Solution, solver(a, x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Integer(a * x0)
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "a": a,
        "b": 0,
        "x0": x0,
        "p": p_x,
        "pts": [_pt_str(p_x, a * p_x), _pt_str(x0, a * x0)],
    }
    given = {
        "situation_params": (
            f"原点を通る直線のグラフがあり、このグラフは点{_fmt_pt(p_x, a * p_x)}を通っている。"
            f"このグラフ上で x = {fmt_number(sympy.Integer(x0))} のときの y の値"
        )
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params), extra_kind="line"),
        recipe="math.read_proportion_graph_value",
    )


# ---------------------------------------------------------------------------
# math.draw_proportion_graph（g1_l31.graph_table Lv2）
# 式 y=ax から、原点と指定された2つの格子点をとって直線をかく。
# ---------------------------------------------------------------------------
_DRAW_PROPORTION_GRAPH_CONCEPTS = ["direct_proportion.draw_graph"]


@register_recipe("math.draw_proportion_graph", provides_concepts=_DRAW_PROPORTION_GRAPH_CONCEPTS)
def draw_proportion_graph(ctx: CellContext, rng: Rng) -> MR:
    """比例 y=ax のグラフをかく（answer-first・graph_table「かく」Lv2）。

    比例定数 a(≠0) と、明示させる2つの格子点の x 座標 p<q を構成する。答えは GraphAnswer
    （比例定数・通る2点）。問題図は空の方眼、模範解答図は直線つき（solution_svg_ref）。
    Lv1（読む2手順）と op 列（plot_origin→plot_point→plot_second_point→draw_line）が
    相異＝level_sep。
    """
    p = ctx.spec_level.params
    v_max = int(p["value_abs_max"])
    pt_abs = int(p["point_abs_max"])

    # (a, p, q) を全列挙して index を1回引く。a を先に引いてから点を引くと、点の候補数が
    # a によって違うぶん確率が偏り（|a| が大きいほど1組あたりの確率が上がる）、組合せ数の
    # 割に実測 dup_rate が悪化する。列挙して一様に引けば実効的な多様性が組合せ数と一致する。
    combos = [
        (a_v, p_v, q_v)
        for a_v in range(-int(p["a_abs_max"]), int(p["a_abs_max"]) + 1)
        if a_v != 0
        for p_v in range(-pt_abs, pt_abs + 1)
        if p_v != 0 and abs(a_v * p_v) <= v_max
        for q_v in range(p_v + 1, pt_abs + 1)
        if q_v != 0 and abs(a_v * q_v) <= v_max
    ]
    a, p_x, q_x = combos[int(draw({"int_set": list(range(len(combos)))}, rng))]

    solver = REGISTRY.solver("math.draw_proportion_graph_features")
    sol = cast(Solution, solver(a, p_x, q_x))
    assert isinstance(sol.answer, GraphAnswer)
    expected_sreprs = {
        sympy.srepr(sympy.Integer(a)),
        sympy.srepr(sympy.Tuple(sympy.Integer(p_x), sympy.Integer(a * p_x))),
        sympy.srepr(sympy.Tuple(sympy.Integer(q_x), sympy.Integer(a * q_x))),
    }
    assert {f.srepr for f in sol.answer.features} == expected_sreprs, (
        f"double-solve 不一致: 構成した特徴 {expected_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    mr_params = {
        "a": a,
        "b": 0,
        "p": p_x,
        "q": q_x,
        "pts": [_pt_str(p_x, a * p_x), _pt_str(q_x, a * q_x)],
    }
    answer = GraphAnswer(
        features=sol.answer.features, solution_svg_ref=render_line_solution_svg(mr_params)
    )
    given = {
        "expression": _fmt_direct(sympy.Integer(a)),
        "situation_params": (
            f"原点と、x座標が{fmt_number(sympy.Integer(p_x))}である点、"
            f"x座標が{fmt_number(sympy.Integer(q_x))}である点"
        ),
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="draw_graph", answer=answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.draw_proportion_graph",
    )


# ---------------------------------------------------------------------------
# 3本のグラフを比べるセル（g1_l31 Lv3 / g1_l34 Lv3）の共通構成
# ---------------------------------------------------------------------------
_ORDERINGS = [
    (0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0),
]


def _compare_triple_combos(magnitudes: list[int]) -> list[tuple[int, int, int]]:
    """(負にする大きさ n, 正の大きい方 big, 正の小さい方 small) の妥当な組を全列挙する。

    条件: big > n（＝絶対値最大は正のグラフ）・small < big・n/big/small は互いに相異。
    これで「右下がりのグラフが最も急」「最大が同率で一つに決まらない」という退化が
    起こり得なくなる（実行時の再抽選ではなく列挙で閉じる＝鉄則⑤）。
    """
    combos: list[tuple[int, int, int]] = []
    for n in magnitudes:
        for big in magnitudes:
            if big <= n:
                continue
            for small in magnitudes:
                if small >= big or small == n:
                    continue
                combos.append((n, big, small))
    return combos


def _draw_compare_triple(p: dict[str, Any], rng: Rng) -> list[int]:
    """負を1本だけ・絶対値最大は正の1本だけ、になる3つの比例定数を構成して並べる。

    妥当な組を全列挙してから index を1回引く（draw 以外で乱数を解釈しない）。
    並び順も抽選して、同じ3値でも提示順が変わるようにする。
    """
    magnitudes = sorted({abs(v) for v in _cands(p, "a_domain") if v != 0})
    combos = _compare_triple_combos(magnitudes)
    n, big, small = combos[int(draw({"int_set": list(range(len(combos)))}, rng))]
    values = [-n, big, small]
    order = _ORDERINGS[int(draw({"int_set": list(range(len(_ORDERINGS)))}, rng))]
    return [values[i] for i in order]


# ---------------------------------------------------------------------------
# math.compare_proportion_graphs（g1_l31.graph_table Lv3）
# ---------------------------------------------------------------------------
_COMPARE_PROPORTION_CONCEPTS = ["direct_proportion.compare_graphs"]


@register_recipe(
    "math.compare_proportion_graphs", provides_concepts=_COMPARE_PROPORTION_CONCEPTS
)
def compare_proportion_graphs(ctx: CellContext, rng: Rng) -> MR:
    """3本の比例のグラフを比べる（answer-first・graph_table Lv3）。

    最も傾きが急なグラフと右下がりのグラフの比例定数を組で答える。問題図は空の方眼
    （生徒が3本をかいて比べる）。Lv1/Lv2 と op 列が相異＝level_sep。
    """
    p = ctx.spec_level.params
    a1, a2, a3 = _draw_compare_triple(p, rng)

    solver = REGISTRY.solver("math.compare_proportion_graphs")
    sol = cast(Solution, solver(a1, a2, a3))
    assert isinstance(sol.answer, SymbolicAnswer)
    steepest = max([a1, a2, a3], key=abs)
    negative = next(v for v in (a1, a2, a3) if v < 0)
    expected = sympy.Tuple(sympy.Integer(steepest), sympy.Integer(negative))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    span = max(abs(v) for v in (a1, a2, a3))
    mr_params = {"a1": a1, "a2": a2, "a3": a3, "pts": [_pt_str(1, span), _pt_str(-1, -span)]}
    given = {
        "expression": "、".join(_fmt_direct(sympy.Integer(v)) for v in (a1, a2, a3)),
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(
            ctx, asked="read_slope_intercept", answer=sol.answer, steps=sol.steps
        ),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.compare_proportion_graphs",
    )


# ---------------------------------------------------------------------------
# math.read_lattice_point_on_proportion_graph（g1_l32.graph_table Lv1）
# 比例のグラフ上の（原点でない）格子点を読む。式決定の材料。
# ---------------------------------------------------------------------------
_READ_LATTICE_PROPORTION_CONCEPTS = ["direct_proportion.read_lattice_point"]


@register_recipe(
    "math.read_lattice_point_on_proportion_graph",
    provides_concepts=_READ_LATTICE_PROPORTION_CONCEPTS,
)
def read_lattice_point_on_proportion_graph(ctx: CellContext, rng: Rng) -> MR:
    """比例のグラフ上の格子点を読む（answer-first・graph_table「読む」Lv1）。

    比例定数は既約分数 n/r（r は `denominator_domain`・r=1 で整数）を許す——分数の
    比例定数こそ「格子点を読む」技能が要る題材だから。given は空（式を与えると計算で
    解けてしまい題材が破綻する）。図には直線を描く（読む対象そのもの）。
    """
    p = ctx.spec_level.params
    v_max = int(p["value_abs_max"])
    x_abs = int(p["x_abs_max"])

    # (分母 r, 分子 n, 倍数 m) を全列挙して index を1回引く。r→n→m と順に引くと分母ごとの
    # 候補数の違いがそのまま確率の偏りになり、組合せ数の割に実測 dup_rate が悪化する。
    # 格子点になる x は r の倍数。値域は |y| = |n*m| ≤ v_max、|x| = |r*m| ≤ x_abs。
    combos = [
        (r, n, m)
        for r in _cands(p, "denominator_domain")
        for n in _cands(p, "numerator_domain")
        if n != 0 and math.gcd(abs(n), r) == 1
        for m in range(-x_abs, x_abs + 1)
        if m != 0 and abs(r * m) <= x_abs and abs(n * m) <= v_max
    ]
    r, n, m = combos[int(draw({"int_set": list(range(len(combos)))}, rng))]
    x0, y0 = r * m, n * m
    a = sympy.Rational(n, r)

    solver = REGISTRY.solver("math.read_lattice_point_on_proportion")
    sol = cast(Solution, solver(str(a), x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(x0), sympy.Integer(y0))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "a": str(a),
        "b": 0,
        "x0": x0,
        "pts": [_pt_str(x0, y0), _pt_str(-x0, -y0)],
    }
    return _mr(
        ctx,
        params=mr_params,
        # x座標だけを与えて答えを一意にする（式は与えない＝y は図から読むしかない）。
        given={"x_target": fmt_number(sympy.Integer(x0))},
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params), extra_kind="line"),
        recipe="math.read_lattice_point_on_proportion_graph",
    )


# ---------------------------------------------------------------------------
# 双曲線の格子点（x0, y0）の構成（g1_l34 Lv1 / g1_l35 Lv1 共通）
# ---------------------------------------------------------------------------
def _draw_hyperbola_lattice(p: dict[str, Any], rng: Rng) -> tuple[int, int, int]:
    """双曲線 y=a/x が通る格子点 (x0, y0) と比例定数 a=x0*y0 を構成する。

    (x0, y0) を全列挙して index を1回引く。x0 を先に引いてから y0 を引くと、|x0| が
    大きいほど y0 の候補が少なくなるぶん確率が偏り、組合せ数の割に実測 dup_rate が
    悪化する（列挙して一様に引けば実効的な多様性が組合せ数と一致する）。
    """
    x_abs = int(p["x_abs_max"])
    y_abs = int(p["y_abs_max"])
    c_abs = int(p["coeff_abs_max"])
    combos = [
        (x, y)
        for x in range(-x_abs, x_abs + 1)
        if x != 0
        for y in range(-y_abs, y_abs + 1)
        if y != 0 and abs(x * y) <= c_abs
    ]
    x0, y0 = combos[int(draw({"int_set": list(range(len(combos)))}, rng))]
    return x0, y0, x0 * y0


# ---------------------------------------------------------------------------
# math.read_hyperbola_graph_value（g1_l34.graph_table Lv1）
# ---------------------------------------------------------------------------
_READ_HYPERBOLA_GRAPH_CONCEPTS = ["inverse_proportion.read_value_from_graph"]


@register_recipe(
    "math.read_hyperbola_graph_value", provides_concepts=_READ_HYPERBOLA_GRAPH_CONCEPTS
)
def read_hyperbola_graph_value(ctx: CellContext, rng: Rng) -> MR:
    """双曲線から対応する y の値を読む（answer-first・graph_table「読む」Lv1）。

    格子点 (x0, y0) を先に選び a=x0*y0 とする（読み取れる点であることを構成で保証）。
    図には双曲線を描く（読む対象そのもの・`curve_kind="hyperbola"`）。
    """
    p = ctx.spec_level.params
    x0, y0, a = _draw_hyperbola_lattice(p, rng)

    solver = REGISTRY.solver("math.read_value_on_hyperbola_graph")
    sol = cast(Solution, solver(a, x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Integer(y0)
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "a": a,
        "x0": x0,
        "curve_kind": "hyperbola",
        "coeff": a,
        "pts": [_pt_str(x0, y0), _pt_str(-x0, -y0)],
    }
    given = {
        "expression": _fmt_inverse(sympy.Integer(a)),
        "situation_params": f"このグラフ上で x = {fmt_number(sympy.Integer(x0))} のときの y の値",
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params), extra_kind="curve"),
        recipe="math.read_hyperbola_graph_value",
    )


# ---------------------------------------------------------------------------
# math.draw_hyperbola_from_table（g1_l34.graph_table Lv2）
# 表で対応値を求め、点をとって双曲線を2つの枝でかく。
# ---------------------------------------------------------------------------
_DRAW_HYPERBOLA_CONCEPTS = ["inverse_proportion.draw_hyperbola"]


@register_recipe("math.draw_hyperbola_from_table", provides_concepts=_DRAW_HYPERBOLA_CONCEPTS)
def draw_hyperbola_from_table(ctx: CellContext, rng: Rng) -> MR:
    """反比例 y=a/x のグラフ（双曲線）を表からかく（answer-first・graph_table「かく」Lv2）。

    比例定数 a と、表に並べる正の x 座標（a の約数）の組を構成する。x も y=a/x も
    `table_abs_max` 以下に収め、方眼に収まる点だけを表に載せる（図の可読性）。
    問題図は空の方眼、模範解答図は双曲線つき（`render_curve_solution_svg`）。
    """
    p = ctx.spec_level.params
    t_max = int(p["table_abs_max"])

    a = int(draw(p["coeff_domain"], rng))
    divisors = [d for d in range(1, t_max + 1) if abs(a) % d == 0 and abs(a) // d <= t_max]
    size = int(draw(p["table_size_domain"], rng))
    xs = sorted(int(v) for v in draw_many({"int_set": divisors, "distinct": ["value"]}, rng, k=size))

    solver = REGISTRY.solver("math.draw_hyperbola_features")
    sol = cast(Solution, solver(a, xs))
    assert isinstance(sol.answer, GraphAnswer)
    x1 = xs[0]
    y1 = a // x1
    expected_sreprs = {
        sympy.srepr(sympy.Integer(a)),
        sympy.srepr(sympy.Tuple(sympy.Integer(x1), sympy.Integer(y1))),
        sympy.srepr(sympy.Tuple(sympy.Integer(-x1), sympy.Integer(-y1))),
    }
    assert {f.srepr for f in sol.answer.features} == expected_sreprs, (
        f"double-solve 不一致: 構成した特徴 {expected_sreprs} "
        f"!= solver 再計算 {{f.srepr for f in sol.answer.features}}"
    )

    mr_params = {
        "a": a,
        "xs": xs,
        "curve_kind": "hyperbola",
        "coeff": a,
        "pts": [_pt_str(x1, y1), _pt_str(-x1, -y1), _pt_str(xs[-1], a // xs[-1])],
    }
    answer = GraphAnswer(
        features=sol.answer.features, solution_svg_ref=render_curve_solution_svg(mr_params)
    )
    xs_disp = "、".join(fmt_number(sympy.Integer(v)) for v in xs)
    neg_disp = "、".join(fmt_number(sympy.Integer(-v)) for v in xs)
    given = {
        "expression": _fmt_inverse(sympy.Integer(a)),
        "data_table": f"x = {xs_disp} および x = {neg_disp}",
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="draw_graph", answer=answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.draw_hyperbola_from_table",
    )


# ---------------------------------------------------------------------------
# math.compare_hyperbolas（g1_l34.graph_table Lv3）
# ---------------------------------------------------------------------------
_COMPARE_HYPERBOLAS_CONCEPTS = ["inverse_proportion.compare_hyperbolas"]


@register_recipe("math.compare_hyperbolas", provides_concepts=_COMPARE_HYPERBOLAS_CONCEPTS)
def compare_hyperbolas(ctx: CellContext, rng: Rng) -> MR:
    """3本の双曲線を比べる（answer-first・graph_table Lv3）。

    第2・第4象限にある双曲線と、原点から最も離れた双曲線の比例定数を組で答える。
    問題図は空の方眼（生徒が3本をかいて比べる）。Lv1/Lv2 と op 列が相異＝level_sep。
    """
    p = ctx.spec_level.params
    a1, a2, a3 = _draw_compare_triple(p, rng)

    solver = REGISTRY.solver("math.compare_hyperbolas")
    sol = cast(Solution, solver(a1, a2, a3))
    assert isinstance(sol.answer, SymbolicAnswer)
    farthest = max([a1, a2, a3], key=abs)
    negative = next(v for v in (a1, a2, a3) if v < 0)
    expected = sympy.Tuple(sympy.Integer(negative), sympy.Integer(farthest))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    span = max(abs(v) for v in (a1, a2, a3))
    mr_params = {"a1": a1, "a2": a2, "a3": a3, "pts": [_pt_str(1, span), _pt_str(-1, -span)]}
    given = {"expression": "、".join(_fmt_inverse(sympy.Integer(v)) for v in (a1, a2, a3))}
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(
            ctx, asked="read_slope_intercept", answer=sol.answer, steps=sol.steps
        ),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.compare_hyperbolas",
    )


# ---------------------------------------------------------------------------
# math.read_lattice_point_on_hyperbola_graph（g1_l35.graph_table Lv1）
# ---------------------------------------------------------------------------
_READ_LATTICE_HYPERBOLA_CONCEPTS = ["inverse_proportion.read_lattice_point"]


@register_recipe(
    "math.read_lattice_point_on_hyperbola_graph",
    provides_concepts=_READ_LATTICE_HYPERBOLA_CONCEPTS,
)
def read_lattice_point_on_hyperbola_graph(ctx: CellContext, rng: Rng) -> MR:
    """双曲線上の格子点を読む（answer-first・graph_table「読む」Lv1）。

    given は空（式を与えると積で計算できてしまい「グラフから読む」題材が破綻する）。
    図には双曲線を描く（読む対象そのもの）。
    """
    p = ctx.spec_level.params
    x0, y0, a = _draw_hyperbola_lattice(p, rng)

    solver = REGISTRY.solver("math.read_lattice_point_on_hyperbola")
    sol = cast(Solution, solver(a, x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(x0), sympy.Integer(y0))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "a": a,
        "x0": x0,
        "curve_kind": "hyperbola",
        "coeff": a,
        "pts": [_pt_str(x0, y0), _pt_str(-x0, -y0)],
    }
    return _mr(
        ctx,
        params=mr_params,
        given={"x_target": fmt_number(sympy.Integer(x0))},
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params), extra_kind="curve"),
        recipe="math.read_lattice_point_on_hyperbola_graph",
    )


# ---------------------------------------------------------------------------
# math.graph_situation_proportion（g1_l36.graph_table Lv2）
# 場面の対応を表とグラフに表し、別の x に対応する値をグラフから読む。
# ---------------------------------------------------------------------------
_GRAPH_SITUATION_CONCEPTS = ["direct_proportion.graph_from_situation"]


@register_recipe("math.graph_situation_proportion", provides_concepts=_GRAPH_SITUATION_CONCEPTS)
def graph_situation_proportion(ctx: CellContext, rng: Rng) -> MR:
    """場面の対応をグラフに表して読む（answer-first・graph_table Lv2）。

    一定の割合 a（≥2）と測定した x の値の組、たずねる x_q を構成する。x_q は測定値と
    相異にし、答え a*x_q が測定値の y と一致する退化を構成で排除する（鉄則⑤）。
    量-量グラフなので `grid_mode="quantity"`（第1象限・軸ごとの目盛）で描く。
    """
    p = ctx.spec_level.params
    a = int(draw(p["rate_domain"], rng))
    xs = sorted(int(v) for v in draw_many(p["x_domain"], rng, k=int(p["sample_size"])))
    q_cands = [v for v in _cands(p, "query_domain") if v not in xs]
    x_q = int(draw({"int_set": q_cands}, rng))

    solver = REGISTRY.solver("math.read_situation_value_from_graph")
    sol = cast(Solution, solver(a, x_q))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Integer(a * x_q)
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "a": a,
        "b": 0,
        "xs": xs,
        "x_q": x_q,
        "grid_mode": "quantity",
        "pts": [_pt_str(v, a * v) for v in xs] + [_pt_str(x_q, a * x_q)],
    }
    pairs = "、".join(
        f"x = {fmt_number(sympy.Integer(v))} のとき y = {fmt_number(sympy.Integer(a * v))}"
        for v in xs
    )
    given = {
        "condition": (
            "水そうに一定の割合で水を入れる。入れ始めてからの時間 x 分と水の深さ y cm を測ると、"
            f"{pairs} であった。x = {fmt_number(sympy.Integer(x_q))} のときの水の深さ"
        )
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(ctx, asked="read_point", answer=sol.answer, steps=sol.steps),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.graph_situation_proportion",
    )


# ---------------------------------------------------------------------------
# math.graph_two_plans_crossover（g1_l36.graph_table Lv3）
# 2つの料金プランを同じ座標平面にグラフでかき、交点（得の分かれ目）を読む。
# ---------------------------------------------------------------------------
_GRAPH_TWO_PLANS_CONCEPTS = ["direct_proportion.compare_two_plans_graph"]


@register_recipe("math.graph_two_plans_crossover", provides_concepts=_GRAPH_TWO_PLANS_CONCEPTS)
def graph_two_plans_crossover(ctx: CellContext, rng: Rng) -> MR:
    """2つの料金プランのグラフの交点を読む（answer-first・graph_table Lv3）。

    交点の枚数 x0・1枚あたりの差 d(≥2)・B社の単価 pb を先に選び、固定費 fixed=d*x0 を
    逆算する（交点が必ず格子点になる＝グラフから読める）。x0 は単価より大きい域から
    引くので、答えの座標が本文の数値と偶然一致する退化も構成で避けている。
    問題図は空の方眼（read_intersection は両直線入りの図を禁止＝§6.4）。
    """
    p = ctx.spec_level.params
    pb = int(draw(p["unit_price_domain"], rng))
    d = int(draw(p["price_diff_domain"], rng))
    x0 = int(draw(p["crossover_domain"], rng))
    pa = pb + d
    fixed = d * x0
    y0 = pa * x0

    solver = REGISTRY.solver("math.read_plan_crossover_from_graph")
    sol = cast(Solution, solver(pa, pb, fixed))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(x0), sympy.Integer(y0))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    mr_params = {
        "pa": pa,
        "pb": pb,
        "fixed": fixed,
        "grid_mode": "quantity",
        "pts": [_pt_str(x0, y0), _pt_str(0, fixed)],
    }
    given = {
        "condition": (
            f"A社はコピー1枚を{fmt_number(sympy.Integer(pa))}円で引き受ける。"
            f"B社は1枚を{fmt_number(sympy.Integer(pb))}円で引き受けるが、"
            f"枚数によらず{fmt_number(sympy.Integer(fixed))}円の基本料金がかかる。"
            "コピーの枚数 x と料金 y の関係"
        )
    }
    return _mr(
        ctx,
        params=mr_params,
        given=given,
        sub_question=_sub_question(
            ctx, asked="read_intersection", answer=sol.answer, steps=sol.steps
        ),
        visual_plan=_grid_plan(tick_labels_from_params(mr_params)),
        recipe="math.graph_two_plans_crossover",
    )


__all__ = [
    "read_coordinate_on_plane",
    "reflect_point_on_plane",
    "read_proportion_graph_value",
    "draw_proportion_graph",
    "compare_proportion_graphs",
    "read_lattice_point_on_proportion_graph",
    "read_hyperbola_graph_value",
    "draw_hyperbola_from_table",
    "compare_hyperbolas",
    "read_lattice_point_on_hyperbola_graph",
    "graph_situation_proportion",
    "graph_two_plans_crossover",
]
