"""平面図形の移動（平行移動・回転移動・対称移動）まわりの recipe

（構成的生成・answer-first。実装設計 §6.1・§6.4）。

C7（g1 平面図形）クラスタの graph_table セル（g1_l38 平行移動・g1_l39 回転移動・
g1_l40 対称移動）に対応する。各 unit は2レベル持つ:
  - Lv1（grid_only・方眼のみ）: 座標軸・目盛の数値を一切見せず、方眼のマス目だけで
    移動を示す（教科書の「方眼上に図形がかかれている」形）。答えの座標は生徒に見えない
    内部の座標系上で計算するだけで、問題文・問題図には一切数値を出さない。
  - Lv2（coordinate・座標平面）: 頂点の座標を明示し、座標平面上で移動する（教科書の
    「座標平面上に図形があり、A(1,1)...」形）。

同一 family 内で Lv1/Lv2 とも同じ独立ソルバ（math.translate_polygon_features 等）を
再利用するため、given のキー名を Lv1="polygon_points"／Lv2="polygon_coordinates" と
分けることで fp（signature 抜きの構造指紋）を相異させる（level_sep・G-FP 対策。
g1_l37 Lv2 で遭遇した「同一 solver 再利用で fp 衝突」の教訓を反映）。

答えは GraphAnswer（移動後の各頂点座標を Feature の集合で表す・順序に依らない集合
一致で double-solve 検証）。三角形（3頂点 A,B,C）のみを対象にする（l40 Lv1 の元
curriculum 例は四角形だが、対称移動という技能自体は頂点数に依らないため三角形に
統一し実装を簡潔にする）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.visuals.plane_transform import render_polygon_transform_solution_svg

_VERTEX_LABELS = ["A", "B", "C"]
_VERTEX_LABELS_PRIME = ["A'", "B'", "C'"]

# style（内部の描画スタイル値）→ 登録済み recipe 名の末尾（"math.<topic>_polygon_<suffix>"）。
# style="grid_only" は recipe 名としては短く "grid" とする（例: math.translate_polygon_grid）。
_RECIPE_KEY_SUFFIX = {"grid_only": "grid", "coordinate": "coordinate"}


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _draw_triangle(coord_domain: object, rng: Rng) -> list[tuple[int, int]]:
    """図として読める三角形の3頂点を引く（有界リトライ）。

    **面積が0でないだけでは足りない。** 面積≠0 の条件しか課していなかったので、
    3点がほとんど一直線に並んだ「細い破片」のような三角形が図に出ていた
    （移動の前後を見比べる問題で、形が読めないと何も比べられない）。
    面積が最短辺の長さに対して十分あることを確かめる——具体的には、
    2·面積 ÷ 最長辺 = 最長辺への高さ が 2 目盛以上あること。
    """
    for _ in range(400):
        pts = [(int(draw(coord_domain, rng)), int(draw(coord_domain, rng))) for _ in range(3)]
        (x1, y1), (x2, y2), (x3, y3) = pts
        area2 = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))
        if area2 == 0:
            continue
        sides = [
            ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5,
            ((x3 - x2) ** 2 + (y3 - y2) ** 2) ** 0.5,
            ((x1 - x3) ** 2 + (y1 - y3) ** 2) ** 0.5,
        ]
        if area2 / max(sides) >= 2.0 and min(sides) >= 2.0:
            return pts
    raise ValueError("_draw_triangle: 図として読める三角形を構成できず")


def _pts_strs(pts: list[tuple[int, int]]) -> list[str]:
    return [str((x, y)) for x, y in pts]


def _new_pts_from_features(answer: GraphAnswer) -> list[str]:
    """GraphAnswer.features(Feature.srepr=Tuple(x,y)) から "(x, y)" 文字列の列を作る

    （solution_svg 描画用・vertex_labels_prime と対応する順序を feature の並び順に
    合わせる。features は solver が pts と同じ頂点順で返す＝実装内で保証）。
    """
    out = []
    for f in answer.features:
        t = sympy.sympify(f.srepr)
        out.append(str((int(t[0]), int(t[1]))))
    return out


# ---------------------------------------------------------------------------
# g1_l38.graph_table: 平行移動
# ---------------------------------------------------------------------------
_TRANSLATE_CONCEPTS = ["polygon_transform.translate"]


def _translate_move_spec(dx: int, dy: int, *, style: str) -> str:
    if style == "grid_only":
        horiz = f"右へ{dx}目盛り" if dx > 0 else f"左へ{-dx}目盛り"
        vert = f"上へ{dy}目盛り" if dy > 0 else f"下へ{-dy}目盛り"
        return f"{horiz}、{vert}だけ平行移動した"
    return f"x軸方向に{dx}、y軸方向に{dy}だけ平行移動した"


def _translate_polygon_recipe(ctx: CellContext, rng: Rng, *, style: str) -> MR:
    p = ctx.spec_level.params
    pts = _draw_triangle(p["coord_domain"], rng)
    dx = int(draw(p["move_domain"], rng))
    dy = int(draw(p["move_domain"], rng))

    solver = REGISTRY.solver("math.translate_polygon_features")
    sol = cast(Solution, solver(_pts_strs(pts), str(dx), str(dy)))
    assert isinstance(sol.answer, GraphAnswer)

    move_spec = _translate_move_spec(dx, dy, style=style)
    if style == "grid_only":
        polygon_given = "方眼上に三角形ABCがかかれている。"
        given = {"polygon_points": polygon_given, "move_spec": move_spec}
    else:
        coord_text = "、".join(f"{lb}{pt}" for lb, pt in zip(_VERTEX_LABELS, _pts_strs(pts)))
        polygon_given = f"座標平面上に三角形ABCがあり、{coord_text}である。"
        given = {"polygon_coordinates": polygon_given, "move_spec": move_spec}

    render_params = {
        "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
        "new_pts": _new_pts_from_features(sol.answer), "vertex_labels_prime": _VERTEX_LABELS_PRIME,
        "reflect_axis": None,
    }
    solution_svg = render_polygon_transform_solution_svg(render_params, style=style)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)", asked="draw_transformed_polygon", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    visual_plan = VisualPlan(
        style="grid" if style == "grid_only" else "coordinate",
        labels=(_VERTEX_LABELS if style == "grid_only" else _VERTEX_LABELS + _tick_labels(pts, _new_pts_from_features(sol.answer))),
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="polygon", attrs={"role": "original"}),
        ] + ([VisualElement(kind="axis", attrs={})] if style != "grid_only" else []),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
            "dx": dx, "dy": dy,
            # **移動後の図形も方眼に収める。** 描かないが枠には入れる
            # （`bbox_pts`）。ここを渡していなかったので、方眼の範囲が元の図形
            # だけから決まり、移動後の三角形が枠の外に出ていた（生徒が描けない）。
            "bbox_pts": _new_pts_from_features(sol.answer),
        },
        given=given, sub_questions=[sub_question], visual_plan=visual_plan,
        provenance=Provenance(recipe=f"math.translate_polygon_{_RECIPE_KEY_SUFFIX[style]}"),
    )


def _int_pts(pts_strs: list[str]) -> list[tuple[int, int]]:
    """"(x, y)" の文字列の列を整数の組に戻す（目盛ラベルの範囲を出すのに使う）。"""
    out: list[tuple[int, int]] = []
    for s in pts_strs:
        x, y = s.strip("() ").split(",")
        out.append((int(x), int(y)))
    return out


def _tick_labels(pts: list[tuple[int, int]], bbox: list[str] | None = None) -> list[str]:
    """coordinate スタイルの目盛ラベル一覧（graph.py の tick_labels_from_params と同型）。

    `bbox` は**描かないが枠には入れる点**（移動後の図形）。渡さないと、
    目盛ラベルと実際に描かれる方眼の範囲が食い違う（G-Q5v が落ちる）。
    """
    from engine.packs.math.visuals.graph import tick_labels_from_params

    return tick_labels_from_params({"pts": _pts_strs(pts), "bbox_pts": bbox or []})


@register_recipe("math.translate_polygon_grid", provides_concepts=_TRANSLATE_CONCEPTS)
def translate_polygon_grid_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を方眼上で平行移動する（g1_l38.graph_table Lv1・answer-first）。"""
    return _translate_polygon_recipe(ctx, rng, style="grid_only")


@register_recipe("math.translate_polygon_coordinate", provides_concepts=_TRANSLATE_CONCEPTS)
def translate_polygon_coordinate_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を座標平面上で平行移動する（g1_l38.graph_table Lv2・answer-first）。"""
    return _translate_polygon_recipe(ctx, rng, style="coordinate")


# ---------------------------------------------------------------------------
# g1_l39.graph_table: 回転移動
# ---------------------------------------------------------------------------
_ROTATE_CONCEPTS = ["polygon_transform.rotate"]


def _rotate_polygon_recipe(ctx: CellContext, rng: Rng, *, style: str) -> MR:
    p = ctx.spec_level.params
    pts = _draw_triangle(p["coord_domain"], rng)
    angle = int(draw(cast("list[int]", p["angle_domain"]), rng))

    for _ in range(50):
        center_pt = (int(draw(p["center_domain"], rng)), int(draw(p["center_domain"], rng)))
        if center_pt not in pts:
            break
    else:
        raise ValueError("_rotate_polygon_recipe: 三角形の頂点と重ならない回転の中心を構成できず")
    center_label = _draw_named_figures([1], rng)[0] if style == "grid_only" else None

    solver = REGISTRY.solver("math.rotate_polygon_features")
    sol = cast(Solution, solver(_pts_strs(pts), str(center_pt), str(angle)))
    assert isinstance(sol.answer, GraphAnswer)

    if style == "grid_only":
        move_spec = f"点{center_label}を中心として反時計回りに{angle}°回転移動した"
        polygon_given = f"方眼上に三角形ABCと点{center_label}がある。"
        given = {"polygon_points": polygon_given, "move_spec": move_spec}
        visual_labels = _VERTEX_LABELS + [cast(str, center_label)]
    else:
        center_label_disp = "原点" if center_pt == (0, 0) else f"点{center_pt}"
        move_spec = f"{center_label_disp}を中心として反時計回りに{angle}°回転移動した"
        coord_text = "、".join(f"{lb}{pt}" for lb, pt in zip(_VERTEX_LABELS, _pts_strs(pts)))
        polygon_given = f"座標平面上に三角形ABCがあり、{coord_text}である。"
        given = {"polygon_coordinates": polygon_given, "move_spec": move_spec}
        visual_labels = _VERTEX_LABELS + _tick_labels(pts, _new_pts_from_features(sol.answer))

    render_params = {
        "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
        "new_pts": _new_pts_from_features(sol.answer), "vertex_labels_prime": _VERTEX_LABELS_PRIME,
        "reflect_axis": None,
        "center_label": center_label, "center_pt": str(center_pt) if style == "grid_only" else None,
    }
    solution_svg = render_polygon_transform_solution_svg(render_params, style=style)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)", asked="draw_transformed_polygon", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    visual_plan = VisualPlan(
        style="grid" if style == "grid_only" else "coordinate",
        labels=visual_labels,
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="polygon", attrs={"role": "original"}),
        ] + ([VisualElement(kind="axis", attrs={})] if style != "grid_only" else []),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
            # 移動後の図形も方眼に収める（描かないが枠には入れる）。
            "bbox_pts": _new_pts_from_features(sol.answer),
            "center": str(center_pt), "angle": angle,
            "center_label": center_label,
            "center_pt": str(center_pt) if style == "grid_only" else None,
        },
        given=given, sub_questions=[sub_question], visual_plan=visual_plan,
        provenance=Provenance(recipe=f"math.rotate_polygon_{_RECIPE_KEY_SUFFIX[style]}"),
    )


@register_recipe("math.rotate_polygon_grid", provides_concepts=_ROTATE_CONCEPTS)
def rotate_polygon_grid_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を方眼上で回転移動する（g1_l39.graph_table Lv1・answer-first）。"""
    return _rotate_polygon_recipe(ctx, rng, style="grid_only")


@register_recipe("math.rotate_polygon_coordinate", provides_concepts=_ROTATE_CONCEPTS)
def rotate_polygon_coordinate_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を座標平面上で回転移動する（g1_l39.graph_table Lv2・answer-first）。"""
    return _rotate_polygon_recipe(ctx, rng, style="coordinate")


# ---------------------------------------------------------------------------
# g1_l40.graph_table: 対称移動
# ---------------------------------------------------------------------------
_REFLECT_CONCEPTS = ["polygon_transform.reflect"]
_AXIS_LABEL_JP = {"x_axis": "x軸", "y_axis": "y軸"}


def _clear_of_axis(pts: list[tuple[int, int]], axis: str) -> bool:
    """三角形が対称の軸をまたいでいないか（3頂点とも同じ側にあるか）。

    またぐ配置だと**折り返した図形が元の図形と重なる**ので、生徒はどの線が
    どちらのものか分からないまま描くことになる。市販の教材は片側に置く。

    軸に接していると、折り返した頂点が元の頂点の隣に来て**ラベルが重なる**
    （B' と B が並んで読めない図が出ていた）ので、2目盛り離す。

    定義域は狭めない——座標の値はどれも元のまま引き、**組み合わせだけ**を弾く。
    読める三角形 2,685,768 通りのうち 277,920 通り（10.3%）が、どちらかの軸の
    片側に2目盛り以上離れて収まる（全数で実測）ので、有界リトライで足りる。
    """
    vals = [x for x, _ in pts] if axis == "y_axis" else [y for _, y in pts]
    return all(v >= 2 for v in vals) or all(v <= -2 for v in vals)


def _reflect_polygon_recipe(ctx: CellContext, rng: Rng, *, style: str) -> MR:
    p = ctx.spec_level.params
    for _ in range(400):
        pts = _draw_triangle(p["coord_domain"], rng)
        axis = str(draw(cast("list[str]", p["axis_domain"]), rng))
        if _clear_of_axis(pts, axis):
            break
    else:
        raise ValueError("対称の軸をまたがない三角形と軸の組を構成できず")

    solver = REGISTRY.solver("math.reflect_polygon_features")
    sol = cast(Solution, solver(_pts_strs(pts), axis))
    assert isinstance(sol.answer, GraphAnswer)

    if style == "grid_only":
        move_spec = "直線ℓを対称の軸として対称移動(折り返し)した"
        polygon_given = "方眼上に三角形ABCと直線ℓがある。"
        given = {"polygon_points": polygon_given, "move_spec": move_spec}
    else:
        move_spec = f"{_AXIS_LABEL_JP[axis]}について対称移動した"
        coord_text = "、".join(f"{lb}{pt}" for lb, pt in zip(_VERTEX_LABELS, _pts_strs(pts)))
        polygon_given = f"座標平面上に三角形ABCがあり、{coord_text}である。"
        given = {"polygon_coordinates": polygon_given, "move_spec": move_spec}

    render_params = {
        "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
        "new_pts": _new_pts_from_features(sol.answer), "vertex_labels_prime": _VERTEX_LABELS_PRIME,
        "reflect_axis": axis if style == "grid_only" else None,
    }
    solution_svg = render_polygon_transform_solution_svg(render_params, style=style)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)", asked="draw_transformed_polygon", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    visual_plan = VisualPlan(
        style="grid" if style == "grid_only" else "coordinate",
        # grid_only では対称の軸を ℓ と名づけて図に書く（本文が「直線ℓ」と呼ぶのに、
        # 図には名前の無い線が1本引いてあるだけだった）。
        labels=([*_VERTEX_LABELS, "ℓ"] if style == "grid_only" else _VERTEX_LABELS + _tick_labels(pts, _new_pts_from_features(sol.answer))),
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="polygon", attrs={"role": "original"}),
        ] + ([VisualElement(kind="axis", attrs={})] if style != "grid_only" else []),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
            # 移動後の図形も方眼に収める（描かないが枠には入れる）。
            "bbox_pts": _new_pts_from_features(sol.answer),
            "axis": axis, "reflect_axis": axis if style == "grid_only" else None,
        },
        given=given, sub_questions=[sub_question], visual_plan=visual_plan,
        provenance=Provenance(recipe=f"math.reflect_polygon_{_RECIPE_KEY_SUFFIX[style]}"),
    )


@register_recipe("math.reflect_polygon_grid", provides_concepts=_REFLECT_CONCEPTS)
def reflect_polygon_grid_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を方眼上で対称移動する（g1_l40.graph_table Lv1・answer-first）。"""
    return _reflect_polygon_recipe(ctx, rng, style="grid_only")


@register_recipe("math.reflect_polygon_coordinate", provides_concepts=_REFLECT_CONCEPTS)
def reflect_polygon_coordinate_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形を座標平面上で対称移動する（g1_l40.graph_table Lv2・answer-first）。"""
    return _reflect_polygon_recipe(ctx, rng, style="coordinate")


# ---------------------------------------------------------------------------
# g1_l39.graph_table Lv3: 回転の中心を対応点から特定する
#
# Lv1/Lv2 が「中心と角を与えて動かす」のに対し、Lv3 は**動いた結果から中心を逆に
# 特定する**。作図（垂直二等分線を2本引いて交点をとる）そのものは engine が採点
# できないので、**その交点である中心の座標**を答えにする（作図の手順は
# solution_steps が担う——記述を値に落とす既存の手と同じ）。
# ---------------------------------------------------------------------------
_ROTATION_CENTER_CONCEPTS = ["polygon_transform.find_rotation_center"]


@register_recipe("math.find_rotation_center", provides_concepts=_ROTATION_CENTER_CONCEPTS)
def find_rotation_center_recipe(ctx: CellContext, rng: Rng) -> MR:
    """合同な2つの三角形から回転の中心を求める（g1_l39.graph_table Lv3・answer-first）。

    先に中心と回転角を決めて移動後の三角形を作り（answer-first）、問題文と図には
    **2つの三角形だけ**を出す。中心が三角形の頂点と重ならないこと、中心と2頂点が
    一直線に並ばないこと（垂直二等分線が平行になって交点が定まらない）を構成で保証する。
    """
    p = ctx.spec_level.params
    rotate_solver = REGISTRY.solver("math.rotate_polygon_features")
    for _ in range(200):
        pts = _draw_triangle(p["coord_domain"], rng)
        angle = int(draw(cast("list[int]", p["angle_domain"]), rng))
        center_pt = (int(draw(p["center_domain"], rng)), int(draw(p["center_domain"], rng)))
        if center_pt in pts:
            continue
        # 中心と最初の2頂点が一直線だと、2本の垂直二等分線が平行になって中心が定まらない。
        (x1, y1), (x2, y2) = pts[0], pts[1]
        cx, cy = center_pt
        if (x1 - cx) * (y2 - cy) - (y1 - cy) * (x2 - cx) == 0:
            continue
        sol_rot = cast(Solution, rotate_solver(_pts_strs(pts), str(center_pt), str(angle)))
        assert isinstance(sol_rot.answer, GraphAnswer)
        new_pts = _new_pts_from_features(sol_rot.answer)
        break
    else:  # pragma: no cover - 有界リトライを使い切る確率は無視できる
        raise ValueError("find_rotation_center_recipe: 中心が定まる構成を引けず")

    sol = cast(
        Solution,
        REGISTRY.solver("math.rotation_center_from_corresponding_points")(
            _pts_strs(pts), new_pts
        ),
    )
    assert isinstance(sol.answer, GraphAnswer)

    center_label = _draw_named_figures([1], rng)[0]
    render_params = {
        "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
        "new_pts": new_pts, "vertex_labels_prime": _VERTEX_LABELS_PRIME,
        "reflect_axis": None,
        "center_label": center_label, "center_pt": str(center_pt),
    }
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_polygon_transform_solution_svg(render_params, style="coordinate"),
    )
    src_text = "、".join(f"{lb}{pt}" for lb, pt in zip(_VERTEX_LABELS, _pts_strs(pts)))
    dst_text = "、".join(f"{lb}{pt}" for lb, pt in zip(_VERTEX_LABELS_PRIME, new_pts))
    given = {
        # 座標を答えさせるので、図は座標平面（軸と目盛つき）にし、頂点の座標も文で与える。
        "polygon_coordinates": (
            f"座標平面上に合同な三角形ABCと三角形A'B'C'があり、{src_text}、{dst_text}である。"
            "三角形A'B'C'は三角形ABCをある点を中心として回転移動したものである。"
        ),
        "move_spec": (
            f"回転の中心を点{center_label}とするとき、対応する点を結んでできる線分の"
            f"垂直二等分線を使って点{center_label}の位置を求め、その座標を答えよ"
        ),
    }
    visual_plan = VisualPlan(
        style="coordinate",
        labels=_VERTEX_LABELS + _VERTEX_LABELS_PRIME + _tick_labels([*pts, *_int_pts(new_pts)]),
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            VisualElement(kind="polygon", attrs={"role": "original"}),
            VisualElement(kind="polygon", attrs={"role": "image"}),
        ],
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "pts": _pts_strs(pts), "vertex_labels": _VERTEX_LABELS,
            # 移動後の図形も方眼に収める（描かないが枠には入れる）。
            "bbox_pts": _new_pts_from_features(sol.answer),
            "new_pts": new_pts, "vertex_labels_prime": _VERTEX_LABELS_PRIME,
            "center_label": center_label,
        },
        given=given,
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="read_point", answer=answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
            )
        ],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.find_rotation_center"),
    )
