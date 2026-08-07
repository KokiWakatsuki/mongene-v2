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
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.solid_figure import _fmt_pi, _fmt_plain


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _solve(mode: str, values: dict[str, object]) -> Solution:
    solver = REGISTRY.solver("math.solid_figure_measure")
    return cast(Solution, solver(mode, values))


def _make_mr(ctx: CellContext, recipe_name: str, mode: str, values: dict[str, object],
             statement: str, given_key: str, sol: Solution) -> MR:
    assert isinstance(sol.answer, SymbolicAnswer)
    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"mode": mode, **values},
        given={given_key: statement}, sub_questions=[sub_question], visual_plan=None,
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
        if l <= r:
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
        f"底面の半径{r}cm、母線の長さ{l}cmの円錐がある。この円錐の側面(おうぎ形)の"
        "中心角を求め、表面積を求めよ。ただし円周率はπとする"
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
        if (a * a * h2) % 3 == 0:
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


def _draw_sphere_scene(p: Any, rng: Rng) -> tuple[int, str, str]:
    """(半径, 与え方, 単位)。

    【なぜ軸が3つ要るか】dup_key は signature + params なので、params が半径ひとつ
    だけだと 100seed で dup≤0.20 に届かない（約250通り必要・BRIEF「★単一パラメータの
    セルは原理的に通らない」）。そこで
      ・半径で与えるか直径で与えるか（2通り）
      ・長さの単位（3通り）
    を足す。与え方は op 列を変えない（solver の第1手 read_radius_from_statement が
    variant 中立なので、どちらでも同じ手順になる）＝G-FP は安定する。
    """
    r = int(draw(p["radius_domain"], rng))
    given_as = str(draw(list(p["given_as_set"]), rng))
    unit = str(draw(list(p["unit_set"]), rng))
    return r, given_as, unit


def _sphere_size_phrase(r: int, given_as: str, unit: str) -> str:
    return f"直径{2 * r}{unit}" if given_as == "diameter" else f"半径{r}{unit}"


@register_recipe("math.solid_sphere_direct", provides_concepts=_L53_DIRECT_CONCEPTS)
def solid_sphere_direct_recipe(ctx: CellContext, rng: Rng) -> MR:
    """半径から球の表面積・体積をそれぞれ直接求める（g1_l53.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    r, given_as, unit = _draw_sphere_scene(p, rng)
    values = {"radius": r, "given_as": given_as, "unit": unit}
    size = _sphere_size_phrase(r, given_as, unit)
    statement = f"{size}の球がある。この球の表面積と体積をそれぞれ求めよ。ただし円周率はπとする"

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
    r, given_as, unit = _draw_sphere_scene(p, rng)

    if variant == "hemisphere_surface":
        values: dict[str, object] = {
            "variant": variant, "radius": r, "given_as": given_as, "unit": unit,
        }
        size = _sphere_size_phrase(r, given_as, unit)
        statement = (
            f"{size}の球を中心を通る平面で半分に切った半球がある。この半球の表面積を"
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
