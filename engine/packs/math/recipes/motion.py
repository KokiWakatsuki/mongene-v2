"""動点（正方形の辺上を動く点）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は正方形の1辺 s・速さ v・経過時間 t を answer-first で構成し、独立ソルバ
math.solve_moving_point_area（`engine/packs/math/solvers/motion.py`）で三角形 APD の
面積を再計算する（double-solve）。visual は不要（座標幾何の数式のみで完結）。

C3（g3_l31.find_value・2次方程式の利用「動点」）クラスタ。乱数は
`engine.core.rng.draw` 以外で解釈しない。
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
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_distinct_points
from engine.packs.math.visuals.graph import render_segment_solution_svg, tick_labels_from_params

_MOTION_CONCEPTS = [
    "motion.area_single_segment",
    "motion.area_two_segment",
]

_AREA_TIME_GRAPH_CONCEPTS = [
    "motion.area_time_graph_segment",
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


@register_recipe("math.solve_moving_point_area", provides_concepts=_MOTION_CONCEPTS)
def solve_moving_point_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正方形の辺上を動く点 P による三角形 APD の面積を求める MR を組む（C3 g3_l31.find_value）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "single_segment":
        s, v, t, condition = _construct_single_segment(rng)
    elif mode == "two_segment":
        s, v, t, condition = _construct_two_segment(rng)
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.solve_moving_point_area")
    sol = cast(Solution, solver(s, v, t, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 独立に構成した s,v,t から shoelace 公式で再計算した面積と一致する（.equals で
    # 堅牢にゼロ判定）。
    expected = _expected_area(s, v, t, mode)
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: s={s},v={v},t={t},mode={mode} の面積 {expected} != {sol.answer.srepr}"
    )
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={"s": s, "v": v, "t": t, "mode": mode},
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_moving_point_area"),
    )


def _expected_area(s: int, v: int, t: int, mode: str) -> sympy.Rational:
    """独立検証用: shoelace 公式を素直に展開した式で面積を再計算する。"""
    s_v, d = sympy.Integer(s), sympy.Integer(v) * sympy.Integer(t)
    if mode == "single_segment":
        px, py = d, sympy.Integer(0)
    else:
        px, py = s_v, d - s_v
    ax, ay, dx, dy = sympy.Integer(0), sympy.Integer(0), sympy.Integer(0), s_v
    return sympy.Rational(1, 2) * sympy.Abs(ax * (py - dy) + px * (dy - ay) + dx * (ay - py))


def _construct_single_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv2: 点 P が辺 AB 上（1区間）にあるときの構成。

    速さ v・経過時間 t を先に決め AP の長さ p=v·t を求め、1辺 s は p より大きい偶数
    （面積 p·s/2 を整数にするため・鉄則⑤: 構成時に整数解を保証）に絞って引く。
    """
    v = int(draw({"int_range": [1, 5]}, rng))
    t = int(draw({"int_range": [2, 10]}, rng))
    p = v * t
    s_cands = [x for x in range(p + 2, p + 42) if x % 2 == 0]
    s = int(draw({"int_set": s_cands}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDで、点PはAを出発し辺AB上を毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


def _construct_two_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv3: 点 P が A→B→C の2区間目（辺 BC 上）にあるときの構成。

    1辺 s は偶数（面積 s²/2 を整数にするため）に限定し、速さ v から経過距離
    d=v·t が s<d<2s（確実に2区間目）となる t の範囲を計算し、その範囲から引く
    （鉄則⑤: 実行時の場合分け判定ではなく構成時に区間を保証）。
    """
    s = int(draw({"int_set": list(range(6, 41, 2))}, rng))
    v = int(draw({"int_range": [1, 4]}, rng))
    t_lo = s // v + 1
    t_hi = (2 * s - 1) // v
    t = int(draw({"int_range": [t_lo, t_hi]}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDの辺上を、点PがA→B→Cの順に毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


@register_recipe("math.draw_area_time_graph_segment", provides_concepts=_AREA_TIME_GRAPH_CONCEPTS)
def draw_area_time_graph_segment(ctx: CellContext, rng: Rng) -> MR:
    """動点がつくる三角形の面積を、時間 x の関数のグラフ（線分）としてかく（g3_l31.graph_table Lv2）。

    正方形の1辺 s・速さ v で点 P が辺上を動く間、面積 y は時間 x の1次関数
    y=(s·v/2)x（切片 0・底辺 s 固定／高さ=v·x）になる。変域は x∈[0, t_end]（t_end=s/v＝P が
    向かいの頂点に達する時刻）で、両端とも到達の瞬間を含む＝閉区間。
    答えは GraphAnswer（両端点の特徴集合）。独立ソルバ math.solve_moving_point_area
    （shoelace 公式・find_value 側と共有）で両端の面積を再計算し、式 y=(s·v/2)x の値と
    一致することを assert する（幾何の導出と式変形の2経路で検証）。
    端点特徴・描画・checker は g2_l23.graph_table の既存部品
    （math.draw_segment_features / render_segment_solution_svg /
    math.draw_area_time_graph_segment.double_solve）をそのまま再利用する。

    図は時間 x 秒と面積 y cm² という**単位の違う2量**のグラフなので、座標平面ではなく
    量-量グラフとして描く（params の grid_mode="quantity"＝第1象限のみ・軸ごとに独立な
    切りのよい目盛間隔。y は最大 s²/2 まで伸びるため 1 刻みでは方眼が潰れる）。
    """
    p = ctx.spec_level.params
    s, v, t_end, labels_txt, condition = _construct_graph_segment(p, rng)

    area_solver = REGISTRY.solver("math.solve_moving_point_area")
    lo_sol = cast(Solution, area_solver(s, v, 0, "single_segment"))
    hi_sol = cast(Solution, area_solver(s, v, t_end, "single_segment"))
    assert isinstance(lo_sol.answer, SymbolicAnswer)
    assert isinstance(hi_sol.answer, SymbolicAnswer)
    y_lo_geom = sympy.sympify(lo_sol.answer.srepr)
    y_hi_geom = sympy.sympify(hi_sol.answer.srepr)

    a_s = sympy.Rational(s * v, 2)
    b_s = sympy.Integer(0)
    x_lo_s, x_hi_s = sympy.Integer(0), sympy.Integer(t_end)
    y_lo, y_hi = a_s * x_lo_s + b_s, a_s * x_hi_s + b_s
    assert (y_lo - y_lo_geom).equals(0) and (y_hi - y_hi_geom).equals(0), (
        f"面積の式 y=(s·v/2)x と shoelace 再計算が不一致: s={s}, v={v}, t_end={t_end}"
    )

    features_solver = REGISTRY.solver("math.draw_segment_features")
    sol = cast(Solution, features_solver(a_s, b_s, x_lo_s, x_hi_s, True, True))
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "a": str(a_s), "b": str(b_s),
        "seg_x_lo": str(x_lo_s), "seg_x_hi": str(x_hi_s),
        "closed_lo": True, "closed_hi": True,
        "pts": [str((x_lo_s, y_lo)), str((x_hi_s, y_hi))],
        # 時間-面積のグラフ＝量-量グラフとして描く（visuals/graph.py の opt-in モード）
        "grid_mode": "quantity",
        # 場面の構成値と点名（dup_key は params のみを見るため、実際に振っている
        # 自由度はすべて params に残す＝多様性を測定に反映させる）
        "side": s, "speed": v, "t_end": t_end, "labels": labels_txt,
    }
    solution_svg = render_segment_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_segment",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    visual_plan = VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params),
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_area_time_graph_segment"),
    )


def _construct_graph_segment(
    p: dict[str, Any], rng: Rng
) -> tuple[int, int, int, str, str]:
    """速さ v と到達時刻 t_end を先に引き、1辺 s=v·t_end を逆算して場面を構成する。

    s を約数条件で絞る代わりに **s を v·t_end から作る**ことで、t_end=s/v が整数
    （＝変域の右端が目盛にのる）ことを構成時に保証する（鉄則②）。面積 s²/2 を整数に
    保つため s は偶数＝v·t_end が偶数になる組だけを候補にする（鉄則⑤）。
    点名は正方形の4頂点＋動点の5つを相異に引く（surface の自由度＝dup 分散。
    session29 の教訓により params にも残す）。
    """
    side_max = int(p["side_max"])
    pairs = [
        (int(v), int(t))
        for v in p["speed_candidates"]
        for t in p["t_end_candidates"]
        if (int(v) * int(t)) % 2 == 0 and int(v) * int(t) <= side_max
    ]
    idx = int(draw({"int_set": list(range(len(pairs)))}, rng))
    v, t_end = pairs[idx]
    s = v * t_end

    la, lb, lc, ld, lp = _draw_distinct_points(5, rng)
    condition = (
        f"1辺が{s}cmの正方形{la}{lb}{lc}{ld}で、点{lp}は{la}を出発し、"
        f"辺{la}{lb}上を毎秒{v}cmの速さで{lb}まで動く。出発してからの時間をx秒、"
        f"三角形{la}{lp}{ld}の面積をy cm²とするとき、xが0から{t_end}まで変化する"
        f"ときのxとyの関係を表すグラフをかけ"
    )
    return s, v, t_end, la + lb + lc + ld + lp, condition


__all__ = ["solve_moving_point_area_recipe", "draw_area_time_graph_segment"]
