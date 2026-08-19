"""空間図形の「計量」（表面積・体積）まわりの recipe（構成的生成・answer-first）。

C8（g1 空間図形の計量）クラスタ9セル（g1_l51.find_value Lv1-3・g1_l52.calculation Lv1・
g1_l52.find_value Lv1-3・g1_l53.find_value Lv1-2）を、共通ソルバ
`math.solid_figure_measure`（solvers/solid_figure.py）への薄い呼び出しとして実装する。
乱数は `engine.core.rng.draw` 以外で解釈しない。

各セルにつき register_recipe は1つ（H5: checker 名は `{mr.provenance.recipe}.double_solve`
で解決されるため、signature ごとに recipe の登録名を分ける必要がある）。solver 内部の
mode 文字列がそのまま level_sep の骨格（steps の op 列）を決める。
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
from engine.packs.math.visuals.solid import render_solid_svg
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.solid_figure import _fmt_pi, _fmt_plain


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _solve(mode: str, values: dict[str, object]) -> Solution:
    solver = REGISTRY.solver("math.solid_figure_measure")
    return cast(Solution, solver(mode, values))


# 本文の shape 名 → 見取図の種類。**表になければ図を出さない**（合成した立体など、
# 見取図を持たない場面がある）。寸法は「図の中に数値を書かない」——数値は本文にあり、
# 図は形を示すためのもの（数値を図に書くと G-Q5v の宣言が形ごとに要る）。
_SKETCH_KIND = {
    "square_prism": "square_prism",
    "rect_prism": "rectangular_prism",
    "cube": "cube",
    "cylinder": "cylinder",
    "cone": "cone",
    "sphere": "sphere",
    "square_pyramid": "square_pyramid",
    "rect_pyramid": "rect_pyramid",
    # 底面が直角三角形の角柱・角錐（g1_l52 Lv2）。
    "right_triangle_pyramid": "triangular_pyramid",
}


# `values` に "shape" が無いセル（形が mode で決まっているもの）の対応表。
# 合成した立体は values["variant"] で形が決まる。
_SKETCH_KIND_BY_VARIANT = {
    "hemisphere_cylinder": "hemisphere_on_cylinder",
    "cube_pyramid_composite": "cube_with_pyramid",
    # **cylinder_cone（円柱の上に円錐）は載せない。** 上が円錐の合成立体の
    # 描き手はまだ無く、半球の骨組みで代用すると図と本文が食い違う。
}

_SKETCH_KIND_BY_MODE = {
    "l53_sphere_direct": "sphere",
    "l53_hemisphere_or_reverse": "hemisphere",
    "l51_cone_central_angle": "cone",
    # **l52_cylinder_volume_substitution は入れない。** これは calculation の
    # セル（「公式 V=πr²h に代入して求めよ」）で、calculation の frame は
    # visual: none。図を付けると G-Q2 が落ちる——実際に落として気づいた。
    # 計算の練習に図は要らない、という M0 の判断はここでは妥当。
}



def _sketch_dim_labels(kind: str, values: dict[str, object]) -> list[str]:
    """見取図に書き入れる寸法（描き手が決めた並び順で返す）。

    ★**本文が与えた寸法が図に1つも書かれていなかった**（2026-08-19 の外部評価で
    指摘・実測 50 問）。「底面が1辺13cmの正方形、高さ6cmの正四角錐」の図に頂点名
    すら無く、どの辺が13cmでどこが6cmか図からは決まらなかった。

    並び順は描き手の約束:
      角柱・立方体   [横, 高さ, 奥行き]
      角錐           [底面の1辺, 高さ]
      円柱・円錐     [半径, 高さ]（`_dimension_labels` が受ける既存の並び）
      正四面体・三角錐 [底面の1辺]
    """
    def cm(key: str) -> str:
        v = values.get(key)
        return f"{v}cm" if v not in (None, "", 0) else ""

    if kind in ("rectangular_prism", "square_prism"):
        return [x for x in (cm("width") or cm("edge"), cm("height"), cm("depth")) if x]
    if kind == "cube":
        return [x for x in (cm("edge"),) if x]
    if kind in ("square_pyramid", "rect_pyramid"):
        return [x for x in (cm("width") or cm("edge"), cm("height")) if x]
    if kind in ("cylinder", "cone"):
        return [x for x in (cm("radius"), cm("height") or cm("slant")) if x]
    if kind in ("tetrahedron", "triangular_pyramid"):
        # 底面が直角三角形の三角錐は「直角をはさむ2辺」と高さを持つ。
        base = cm("edge") or cm("width") or cm("leg1") or cm("base")
        return [x for x in (base, cm("height")) if x]
    if kind in ("sphere", "hemisphere"):
        # 球・半球は半径だけで決まる。描き手は中心から右へ半径を書く。
        return [x for x in (cm("radius"),) if x]
    if kind in ("hemisphere_on_cylinder", "cube_with_pyramid"):
        return [x for x in (cm("radius") or cm("edge"), cm("height")) if x]
    return []


def _sketch_svg(values: dict[str, object], mode: str = "") -> str:
    """★**立体の単元も図が1枚も無かった。** 「底面が1辺13cmの正方形、高さ6cmの
    正四角錐の体積を求めよ」——実物の問題集はここに必ず見取図を添える。形が
    見えていないと、どの面が底面でどこが高さなのかを頭の中で組み立てることになる。

    描き手（visuals/solid.py の見取図）は既にあるので、寸法を画素に直して渡すだけ。
    """
    kind = (
        _SKETCH_KIND.get(str(values.get("shape", "")))
        or _SKETCH_KIND_BY_VARIANT.get(str(values.get("variant", "")))
        or _SKETCH_KIND_BY_MODE.get(mode)
    )
    if kind is None:
        return ""
    r = float(values.get("radius", 0) or 0)
    edge = float(values.get("edge", 0) or 0)
    if kind in ("hemisphere_on_cylinder", "cube_with_pyramid"):
        rr = float(values.get("radius", 0) or 0)
        hh = float(values.get("height", 0) or 0)
        ee = float(values.get("edge", 0) or 0)
        ph = float(values.get("pyramid_height", 0) or 0)
        sc2 = 170.0 / max(rr * 2, ee, hh, ph, 1.0)
        return render_solid_svg(
            {
                "view": "sketch", "solid_kind": kind,
                "radius_px": max(rr * sc2, 60.0),
                "height_px": max((hh if kind == "hemisphere_on_cylinder" else ph) * sc2, 60.0),
                "width_px": max(ee * sc2, 90.0), "depth_px": max(ee * sc2 * 0.45, 40.0),
                "dim_labels": _sketch_dim_labels(kind, values),
            },
            draw=True,
        )
    if kind == "hemisphere":
        return render_solid_svg(
            {"view": "sketch", "solid_kind": "hemisphere", "radius_px": 115.0,
             "dim_labels": _sketch_dim_labels("hemisphere", values)},
            draw=True,
        )
    if kind == "sphere":
        # 球は半径だけで決まる（幅も高さも直径）。
        return render_solid_svg(
            {"view": "sketch", "solid_kind": "sphere", "radius_px": 110.0,
             "dim_labels": _sketch_dim_labels("sphere", values)},
            draw=True,
        )
    w = float(values.get("width", 0) or edge or 2 * r or 1)
    d = float(values.get("depth", 0) or edge or 2 * r or 1)
    h = float(values.get("height", 0) or values.get("slant", 0) or w)
    # 見取図の描き手は左下を基点に描くので、**画面いっぱいになる倍率**で渡す
    # （小さい値で渡すと、広い白紙の隅に小さな立体が乗った図になる）。
    scale = 210.0 / max(w, h, 1.0)
    return render_solid_svg(
        {
            "view": "sketch", "solid_kind": kind,
            "width_px": max(w * scale, 60.0),
            "depth_px": max(d * scale * 0.45, 34.0),
            "height_px": max(h * scale, 60.0),
            "radius_px": max((r or w / 2) * scale, 34.0),
            "dim_labels": _sketch_dim_labels(kind, values),
        },
        draw=True,
    )


def _make_mr(ctx: CellContext, recipe_name: str, mode: str, values: dict[str, object],
             statement: str, given_key: str, sol: Solution) -> MR:
    assert isinstance(sol.answer, SymbolicAnswer)
    figure_svg = _sketch_svg(values, mode)
    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"mode": mode, **values},
        given={given_key: statement},
        context_slots={"figure_svg": figure_svg} if figure_svg else {},
        sub_questions=[sub_question],
        visual_plan=(
            VisualPlan(
                # 図に書き入れた寸法は labels に載せる（G-Q5v は svg の <text> が
                # ここに載っていることを見る）。
                style="figure",
                labels=_sketch_dim_labels(
                    _SKETCH_KIND.get(str(values.get("shape", "")))
                    or _SKETCH_KIND_BY_VARIANT.get(str(values.get("variant", "")))
                    or _SKETCH_KIND_BY_MODE.get(mode)
                    or "",
                    values,
                ),
                elements=[VisualElement(kind="solid_given", attrs={"role": "given"})],
            )
            if figure_svg
            else None
        ),
        provenance=Provenance(recipe=recipe_name),
    )


# ---------------------------------------------------------------------------
# g1_l51.find_value Lv1: 角柱・円柱の表面積を直接合成する
# ---------------------------------------------------------------------------
_L51_DIRECT_SURFACE_CONCEPTS = ["solid_surface.direct"]
_L51_DIRECT_MODE = "l51_direct_surface"


@register_recipe("math.solid_surface_direct", provides_concepts=_L51_DIRECT_SURFACE_CONCEPTS)
def solid_surface_direct_recipe(ctx: CellContext, rng: Rng) -> MR:
    """角柱・円柱の側面と底面を合成して表面積を求める（g1_l51.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    shape = str(draw(p["shape_set"], rng))
    h = int(draw(p["height_domain"], rng))

    if shape == "square_prism":
        edge = int(draw(p["edge_domain"], rng))
        values: dict[str, object] = {"shape": shape, "edge": edge, "height": h}
        statement = f"底面が1辺{edge}cmの正方形、高さ{h}cmの正四角柱がある。この立体の表面積を求めよ"
    elif shape == "rect_prism":
        w = int(draw(p["rect_domain"], rng))
        d = int(draw(p["rect_domain"], rng))
        values = {"shape": shape, "width": w, "depth": d, "height": h}
        statement = f"底面が縦{d}cm、横{w}cmの長方形、高さ{h}cmの四角柱がある。この立体の表面積を求めよ"
    else:  # cylinder
        r = int(draw(p["radius_domain"], rng))
        values = {"shape": shape, "radius": r, "height": h}
        statement = (
            f"底面の半径{r}cm、高さ{h}cmの円柱がある。この立体の表面積を求めよ。"
            "ただし円周率はπとする"
        )

    sol = _solve(_L51_DIRECT_MODE, values)
    return _make_mr(ctx, "math.solid_surface_direct", _L51_DIRECT_MODE, values, statement, "condition", sol)


# ---------------------------------------------------------------------------
# g1_l51.find_value Lv2: 円錐の側面の中心角を経由して表面積を求める
# ---------------------------------------------------------------------------
_L51_CONE_CONCEPTS = ["solid_surface.cone_central_angle"]
_L51_CONE_MODE = "l51_cone_central_angle"


@register_recipe("math.solid_cone_surface_central_angle", provides_concepts=_L51_CONE_CONCEPTS)
def solid_cone_surface_central_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円錐の側面(おうぎ形)の中心角を求めたうえで表面積を求める（g1_l51.find_value Lv2）。

    半径 r と母線 l を直接引き、中心角 a=360r/l が整数になる組合せだけを有界リトライで
    採用する。

    以前は「360 の約数の候補17個から中心角 a を引き、l=360r/a を逆算する」構成だったが、
    dup_key は params の (radius, slant) だけで決まるため、成立する (r,l) は
    半径[2,12]・母線上限60 で **94通りしかなく dup=0.42 で閾超過**していた（100seed 実測）。
    中心角を候補リストに縛る理由は無い（360r/l が整数なら中心角は必ず整数で、225°や252°の
    ような値も おうぎ形として何ら不自然ではない）ため、制約を「整数であること」だけに緩め、
    退化（極端に細い/ほぼ全円のおうぎ形）は angle_min/angle_max で外す。
    """
    p = ctx.spec_level.params
    angle_min = int(p["angle_min"])
    angle_max = int(p["angle_max"])
    for _ in range(500):
        r = int(draw(p["radius_domain"], rng))
        l = int(draw(p["slant_domain"], rng))
        # **母線は半径の 4 倍まで。** 前は l > r とだけ見ていたので
        # 「底面の半径10cm、母線の長さ80cm」（針のように細い円錐）が出ていた。
        # 実物の円錐は母線が半径の 1.5〜3 倍あたり（中心角 90°〜240°）。
        if l <= r or l > 4 * r:
            continue
        if (360 * r) % l != 0:
            continue
        a = 360 * r // l
        if not (angle_min <= a <= angle_max):
            continue
        break
    else:
        raise ValueError("solid_cone_surface_central_angle: 条件を満たす (半径,母線) を構成できず")

    values = {"radius": r, "slant": l}
    statement = (
        # 「中心角を求め、表面積を求めよ」と書くと**2つ答えさせている**ように読めるが、
        # 答えは表面積ひとつ。中心角は途中の手なので、そう読める言い方にする。
        f"底面の半径{r}cm、母線の長さ{l}cmの円錐がある。この円錐の側面(おうぎ形)の"
        "中心角を使って、表面積を求めよ。ただし円周率はπとする"
    )
    sol = _solve(_L51_CONE_MODE, values)
    return _make_mr(
        ctx, "math.solid_cone_surface_central_angle", _L51_CONE_MODE, values, statement, "condition", sol
    )


# ---------------------------------------------------------------------------
# g1_l51.find_value Lv3: 複合立体の表面積、または表面積から半径を逆算する
# ---------------------------------------------------------------------------
_L51_COMPOSITE_CONCEPTS = ["solid_surface.composite_or_reverse"]
_L51_COMPOSITE_MODE = "l51_composite_or_reverse_surface"


@register_recipe("math.solid_composite_or_reverse_surface", provides_concepts=_L51_COMPOSITE_CONCEPTS)
def solid_composite_or_reverse_surface_recipe(ctx: CellContext, rng: Rng) -> MR:
    """複合立体の表面積を重なる面を除いて合成する、または表面積から半径を逆算する

    （g1_l51.find_value Lv3・answer-first）。variant を3通りからランダムに選ぶ:
      hemisphere_cylinder: 半球+円柱の複合立体の表面積
      cylinder_cone      : 円柱+円錐の複合立体の表面積
      reverse_cylinder_radius: 円柱の高さと表面積から底面の半径を逆算
        （k=2r²+2rh を先に r,h から組み立て、方程式 2r²+2rh=k の判別式が
        (h+2r)² の完全平方になる恒真構成で double-solve する）。
    """
    p = ctx.spec_level.params
    variant = str(draw(p["variant_set"], rng))

    if variant == "hemisphere_cylinder":
        r = int(draw(p["radius_domain"], rng))
        h = int(draw(p["height_domain"], rng))
        values: dict[str, object] = {"variant": variant, "radius": r, "height": h}
        statement = (
            f"半径{r}cmの半球と、それと底面の半径が等しく高さ{h}cmの円柱をぴったり"
            "貼り合わせた立体がある。この立体の表面積を求めよ。ただし円周率はπとする"
        )
    elif variant == "cylinder_cone":
        r = int(draw(p["radius_domain"], rng))
        h = int(draw(p["height_domain"], rng))
        for _ in range(200):
            l = int(draw(p["slant_domain"], rng))
            if l > r:
                break
        else:
            raise ValueError("solid_composite_or_reverse_surface: l>r を満たす母線を構成できず")
        values = {"variant": variant, "radius": r, "height": h, "slant": l}
        statement = (
            f"底面の半径{r}cm、高さ{h}cmの円柱の上に、底面の半径が等しく母線の長さ{l}cmの"
            "円錐をのせた立体がある。この立体の表面積を求めよ。ただし円周率はπとする"
        )
    else:  # reverse_cylinder_radius
        r = int(draw(p["radius_domain"], rng))
        h = int(draw(p["height_domain"], rng))
        k = 2 * r * r + 2 * r * h
        values = {"variant": variant, "height": h, "area_coeff": k}
        area_disp = _fmt_pi(sympy.Integer(k) * sympy.pi, "cm²")
        statement = (
            f"ある円柱の高さは{h}cmで、表面積は{area_disp}である。この円柱の底面の"
            "半径を求めよ。ただし円周率はπとする"
        )

    sol = _solve(_L51_COMPOSITE_MODE, values)
    mr = _make_mr(
        ctx, "math.solid_composite_or_reverse_surface", _L51_COMPOSITE_MODE, values,
        statement, "condition", sol,
    )
    if variant == "reverse_cylinder_radius":
        assert sol.answer.srepr == sympy.srepr(sympy.Integer(r)), "double-solve 不一致: 半径"
    return mr


# ---------------------------------------------------------------------------
# g1_l52.calculation Lv1: 円柱の体積を公式に代入して計算する
# ---------------------------------------------------------------------------
_L52_CALC_SUBST_CONCEPTS = ["solid_volume.cylinder_substitution"]
_L52_CALC_SUBST_MODE = "l52_cylinder_volume_substitution"


@register_recipe("math.solid_cylinder_volume_substitution", provides_concepts=_L52_CALC_SUBST_CONCEPTS)
def solid_cylinder_volume_substitution_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円柱の体積の公式 V=πr²h に数値を代入して計算する（g1_l52.calculation Lv1）。"""
    p = ctx.spec_level.params
    r = int(draw(p["radius_domain"], rng))
    h = int(draw(p["height_domain"], rng))
    values = {"radius": r, "height": h}
    statement = f"半径{r}cm、高さ{h}cmの円柱の体積を公式 V=πr²h に代入して求めよ(πはそのまま)"

    sol = _solve(_L52_CALC_SUBST_MODE, values)
    return _make_mr(
        ctx, "math.solid_cylinder_volume_substitution", _L52_CALC_SUBST_MODE, values,
        statement, "expression", sol,
    )


# ---------------------------------------------------------------------------
# g1_l52.find_value Lv1: 底面積×高さ(錐体は1/3)で体積を直接求める
# ---------------------------------------------------------------------------
_L52_DIRECT_CONCEPTS = ["solid_volume.prism_pyramid_direct"]
_L52_DIRECT_MODE = "l52_prism_pyramid_volume_direct"


@register_recipe("math.solid_prism_pyramid_volume_direct", provides_concepts=_L52_DIRECT_CONCEPTS)
def solid_prism_pyramid_volume_direct_recipe(ctx: CellContext, rng: Rng) -> MR:
    """底面積×高さ・角錐は1/3をかけて体積を直接求める（g1_l52.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    shape = str(draw(p["shape_set"], rng))
    is_pyramid = shape.endswith("_pyramid")
    h = int(draw(p["height_domain_pyramid"] if is_pyramid else p["height_domain_prism"], rng))
    solid_word = "角錐" if is_pyramid else "角柱"

    if shape.startswith("square_"):
        edge = int(draw(p["edge_domain"], rng))
        values: dict[str, object] = {"shape": shape, "edge": edge, "height": h}
        kind_word = "正四角錐" if is_pyramid else "正四角柱"
        statement = f"底面が1辺{edge}cmの正方形、高さ{h}cmの{kind_word}の体積を求めよ"
    else:
        w = int(draw(p["rect_domain"], rng))
        d = int(draw(p["rect_domain"], rng))
        values = {"shape": shape, "width": w, "depth": d, "height": h}
        statement = f"底面が縦{d}cm、横{w}cmの長方形、高さ{h}cmの四{solid_word}の体積を求めよ"

    sol = _solve(_L52_DIRECT_MODE, values)
    return _make_mr(
        ctx, "math.solid_prism_pyramid_volume_direct", _L52_DIRECT_MODE, values,
        statement, "condition", sol,
    )


# ---------------------------------------------------------------------------
# g1_l52.find_value Lv2: 直角三角形の底面を経由する多段で体積を求める
# ---------------------------------------------------------------------------
_L52_TRIANGLE_CONCEPTS = ["solid_volume.right_triangle_multistep"]
_L52_TRIANGLE_MODE = "l52_right_triangle_volume_multistep"


@register_recipe("math.solid_right_triangle_volume_multistep", provides_concepts=_L52_TRIANGLE_CONCEPTS)
def solid_right_triangle_volume_multistep_recipe(ctx: CellContext, rng: Rng) -> MR:
    """底面が直角三角形の柱体・錐体の体積を、底面積を先に求める多段で求める

    （g1_l52.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    shape = str(draw(p["shape_set"], rng))
    is_pyramid = shape == "right_triangle_pyramid"
    leg1 = int(draw(p["leg_domain"], rng))
    leg2 = int(draw(p["leg_domain"], rng))
    h = int(draw(p["height_domain_pyramid"] if is_pyramid else p["height_domain_prism"], rng))
    solid_word = "三角錐" if is_pyramid else "三角柱"

    values = {"shape": shape, "leg1": leg1, "leg2": leg2, "height": h}
    statement = (
        f"底面が直角をはさむ2辺{leg1}cm,{leg2}cmの直角三角形、高さ{h}cmの{solid_word}の"
        "体積を求めよ"
    )
    sol = _solve(_L52_TRIANGLE_MODE, values)
    return _make_mr(
        ctx, "math.solid_right_triangle_volume_multistep", _L52_TRIANGLE_MODE, values,
        statement, "condition", sol,
    )


# ---------------------------------------------------------------------------
# g1_l52.find_value Lv3: 複合立体の体積、または体積から高さを逆算する
# ---------------------------------------------------------------------------
_L52_COMPOSITE_CONCEPTS = ["solid_volume.composite_or_reverse"]
_L52_COMPOSITE_MODE = "l52_composite_or_reverse_volume"


@register_recipe("math.solid_composite_or_reverse_volume", provides_concepts=_L52_COMPOSITE_CONCEPTS)
def solid_composite_or_reverse_volume_recipe(ctx: CellContext, rng: Rng) -> MR:
    """立方体+正四角錐の複合立体の体積を求める、または体積から錐の高さを逆算する

    （g1_l52.find_value Lv3・answer-first）。a²·h2 が3の倍数になる組合せだけを
    有界リトライで採用し、体積の合計が整数になるようにする。
    """
    p = ctx.spec_level.params
    variant = str(draw(p["variant_set"], rng))

    for _ in range(300):
        a = int(draw(p["edge_domain"], rng))
        h2 = int(draw(p["pyramid_height_domain"], rng))
        # **錐の高さは立方体の1辺の 0.5〜2.5 倍。** 前は無関係に引いていたので
        # 「1辺3cmの立方体の上に高さ16cmの正四角錐」（針のような立体）が出ていた。
        if (a * a * h2) % 3 == 0 and a <= 2 * h2 <= 5 * a:
            break
    else:
        raise ValueError("solid_composite_or_reverse_volume: 3の倍数になる組合せを構成できず")

    if variant == "cube_pyramid_composite":
        values: dict[str, object] = {"variant": variant, "edge": a, "pyramid_height": h2}
        statement = (
            f"1辺{a}cmの立方体の上に、底面が同じ正方形で高さ{h2}cmの正四角錐をのせた"
            "立体の体積を求めよ"
        )
    else:  # reverse_pyramid_height
        total = a**3 + (a * a * h2) // 3
        values = {"variant": variant, "edge": a, "total_volume_coeff": total}
        statement = (
            f"1辺{a}cmの立方体の上に、底面が同じ正方形で高さの分からない正四角錐を"
            f"のせた立体があり、体積の合計は{total}cm³である。この正四角錐の高さを求めよ"
        )

    sol = _solve(_L52_COMPOSITE_MODE, values)
    mr = _make_mr(
        ctx, "math.solid_composite_or_reverse_volume", _L52_COMPOSITE_MODE, values,
        statement, "condition", sol,
    )
    if variant == "reverse_pyramid_height":
        assert sol.answer.srepr == sympy.srepr(sympy.Integer(h2)), "double-solve 不一致: 錐の高さ"
    return mr


# ---------------------------------------------------------------------------
# g1_l53.find_value Lv1: 半径から球の表面積・体積を直接求める
# ---------------------------------------------------------------------------
_L53_DIRECT_CONCEPTS = ["sphere_measure.direct"]
_L53_DIRECT_MODE = "l53_sphere_direct"


# 球の場面と、その場面に合う単位。**半径を教科書の大きさに戻したぶんを、場面で稼ぐ。**
# 前は半径を 2〜60 まで振っていて「直径94cmの球 → 体積 415292π/3 cm³」が出ていた。
# 場面と、その場面に合う単位と、**その場面としてありうる半径の幅（cm 換算の目安）**。
# 単位と半径を無関係に引いていたので「直径24cmのスーパーボール」「半径14cmのビー玉」が
# 出ていた。物には大きさの相場がある。
# シャボン玉は「中心を通る平面で半分に切る」場面が成り立たないので入れない
# （半球の表面積セルが同じ場面リストを使う）。
# 4つ目は「中心を通る平面で半分に切れるか」。風船・シャボン玉は切れないので、
# 半球のセル（`cuttable_only=True`）では使わない。
_SPHERE_SCENES: list[tuple[str, tuple[str, ...], tuple[int, int], bool]] = [
    ("球", ("cm", "m", "mm"), (2, 15), True),
    ("ボール", ("cm",), (3, 15), True),
    ("ビー玉", ("mm",), (5, 12), True),
    ("地球儀", ("cm",), (10, 15), True),
    ("風船", ("cm",), (8, 15), False),
    ("鉄球", ("cm", "mm"), (2, 8), True),
    ("スーパーボール", ("mm",), (10, 15), True),
    ("ゴムまり", ("cm",), (4, 10), True),
    ("木の球", ("cm",), (3, 12), True),
    ("ねんどの玉", ("cm",), (2, 10), True),
    ("メロン", ("cm",), (7, 12), True),
    ("すいか", ("cm",), (10, 15), True),
]


def _draw_sphere_scene(p: Any, rng: Rng) -> tuple[int, str, str, str]:
    """(半径, 与え方, 単位, 場面)。

    【なぜ軸が要るか】dup_key は signature + params なので、params が半径ひとつ
    だけだと 100seed で dup≤0.20 に届かない（約250通り必要・BRIEF「★単一パラメータの
    セルは原理的に通らない」）。そこで
      ・半径で与えるか直径で与えるか（2通り）
      ・場面と、その場面に合う長さの単位（9通り）
    を足す。**半径そのものは広げない**——広げると答えの数が教材から離れる。
    与え方は op 列を変えない（solver の第1手 read_radius_from_statement が
    variant 中立なので、どちらでも同じ手順になる）＝G-FP は安定する。
    """
    given_as = str(draw(list(p["given_as_set"]), rng))
    cuttable_only = bool(p.get("cuttable_scene_only", False))
    dom_lo, dom_hi = (int(v) for v in p["radius_domain"]["int_range"])
    # **(場面, 単位, 半径) の組を平らにして1回で引く。** 場面を先に引いてから半径を
    # 引くと、相場の狭い場面（ビー玉 5〜12mm）が広い場面と同じ確率で選ばれ、
    # 組の分布が偏って dup_rate が跳ねる（値段の相場で踏んだのと同じ罠）。
    triples = [
        (name, u, r)
        for name, units, (lo, hi), cuttable in _SPHERE_SCENES
        if cuttable or not cuttable_only
        for u in units
        for r in range(max(lo, dom_lo), min(hi, dom_hi) + 1)
    ]
    scene, unit, r = triples[int(draw({"int_set": list(range(len(triples)))}, rng))]
    return r, given_as, unit, scene


def _sphere_size_phrase(r: int, given_as: str, unit: str) -> str:
    return f"直径{2 * r}{unit}" if given_as == "diameter" else f"半径{r}{unit}"


@register_recipe("math.solid_sphere_direct", provides_concepts=_L53_DIRECT_CONCEPTS)
def solid_sphere_direct_recipe(ctx: CellContext, rng: Rng) -> MR:
    """半径から球の表面積・体積をそれぞれ直接求める（g1_l53.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    r, given_as, unit, scene = _draw_sphere_scene(p, rng)
    values = {"radius": r, "given_as": given_as, "unit": unit, "scene": scene}
    size = _sphere_size_phrase(r, given_as, unit)
    statement = (
        f"{size}の{scene}がある。この{scene}の表面積と体積をそれぞれ求めよ。"
        "ただし円周率はπとする"
    )

    sol = _solve(_L53_DIRECT_MODE, values)
    return _make_mr(ctx, "math.solid_sphere_direct", _L53_DIRECT_MODE, values, statement, "condition", sol)


# ---------------------------------------------------------------------------
# g1_l53.find_value Lv2: 半球の表面積、または表面積から半径を逆算する
# ---------------------------------------------------------------------------
_L53_HEMISPHERE_CONCEPTS = ["sphere_measure.hemisphere_or_reverse"]
_L53_HEMISPHERE_MODE = "l53_hemisphere_or_reverse"


@register_recipe("math.solid_hemisphere_or_reverse", provides_concepts=_L53_HEMISPHERE_CONCEPTS)
def solid_hemisphere_or_reverse_recipe(ctx: CellContext, rng: Rng) -> MR:
    """半球の表面積を多段で求める、または球の表面積から半径を逆算する

    （g1_l53.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    # variant は1つに固定する。台帳 desc は「半球や複合立体・逆算」の両方を挙げるが、
    # 逆算（表面積から半径）は op 列が 2手で半球の 4手と相異するため、同じレベルに
    # 混ぜると 1レベル＝1 signature＝1 op 列が崩れ G-FP が不安定になる
    # （BRIEF 失敗パターン1）。半球（台帳 example そのもの）を採る。
    variant = "hemisphere_surface"
    r, given_as, unit, scene = _draw_sphere_scene(p, rng)

    if variant == "hemisphere_surface":
        values: dict[str, object] = {
            "variant": variant, "radius": r, "given_as": given_as, "unit": unit,
            "scene": scene,
        }
        size = _sphere_size_phrase(r, given_as, unit)
        statement = (
            f"{size}の{scene}を中心を通る平面で半分に切った半球がある。この半球の表面積を"
            "求めよ。ただし円周率はπとする"
        )
    else:  # reverse_sphere_radius
        k = 4 * r * r
        values = {"variant": variant, "area_coeff": k}
        area_disp = _fmt_pi(sympy.Integer(k) * sympy.pi, "cm²")
        statement = (
            f"ある球の表面積が{area_disp}である。この球の半径を求めよ。ただし円周率はπとする"
        )

    sol = _solve(_L53_HEMISPHERE_MODE, values)
    mr = _make_mr(
        ctx, "math.solid_hemisphere_or_reverse", _L53_HEMISPHERE_MODE, values,
        statement, "condition", sol,
    )
    if variant == "reverse_sphere_radius":
        assert sol.answer.srepr == sympy.srepr(sympy.Integer(r)), "double-solve 不一致: 半径"
    return mr


__all__ = [
    "solid_surface_direct_recipe",
    "solid_cone_surface_central_angle_recipe",
    "solid_composite_or_reverse_surface_recipe",
    "solid_cylinder_volume_substitution_recipe",
    "solid_prism_pyramid_volume_direct_recipe",
    "solid_right_triangle_volume_multistep_recipe",
    "solid_composite_or_reverse_volume_recipe",
    "solid_sphere_direct_recipe",
    "solid_hemisphere_or_reverse_recipe",
]
