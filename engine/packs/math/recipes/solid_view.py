"""立体の見え方（回転体）の recipe（構成的生成・answer-first。実装設計 §6.1）。

C8（g1_l49 面が動いてできる立体・回転体）。数学は独立ソルバ
`engine/packs/math/solvers/solid_view.py` に、図は `engine/packs/math/visuals/solid.py`
に委ねる。この module は「どの平面図形をどの辺のまわりに回すか」を構成し、
問題図（回転体の元図）と模範解答図（見取図・断面）の描画パラメータを組むだけ。

## 問題図と模範解答図が別のビューであること

問題図は `view="rotation_source"`（回転させる平面図形＋回転の軸）で、これは
**答えではない**ので常に描く。模範解答図は `view="sketch"`（見取図）または
`view="section"`（断面）で、`render_solid_solution_svg` を recipe から直接呼ぶ
（`graph.py` の `render_segment_solution_svg` と同型）。
visual_plan の element は `"rotation_source"` にする——`"solid"` は frame の
`_FORBIDDEN_BY_ASKED` で禁じられており、答えの図を問題図に出さないための仕掛け。
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
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_distinct_points
from engine.packs.math.visuals.solid import render_solid_solution_svg, solid_labels

_REVOLUTION_CONCEPTS = [
    "solid_revolution.name",
    "solid_revolution.sketch",
    "solid_revolution.section",
]

# 元の平面図形 -> (頂点の数, 回転してできる立体)
_SHAPE_VERTEX_COUNT = {"rectangle": 4, "right_triangle": 3, "semicircle": 3}
_SHAPE_SOLID = {"rectangle": "cylinder", "right_triangle": "cone", "semicircle": "sphere"}

# 図の大きさ（px）。辺の長さ（cm）をそのまま px にすると小さすぎたり枠を超えたりする
# ので、縦横それぞれ枠に収まる範囲に線形に写す（比は保つ必要がない＝図は「形」を
# 示すためのもので、長さは本文と寸法ラベルが与える）。
_PX_MIN, _PX_MAX = 90.0, 170.0


def _to_px(value: int, lo: int, hi: int) -> float:
    if hi == lo:
        return (_PX_MIN + _PX_MAX) / 2
    t = (value - lo) / (hi - lo)
    return _PX_MIN + t * (_PX_MAX - _PX_MIN)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _scene(p: dict[str, Any], rng: Rng) -> tuple[str, int, int, list[str]]:
    """(元の平面図形, 軸にする辺の長さ, もう一方の辺の長さ, 頂点名)。

    【組合せ数】図形の種類 × 軸の辺 × もう一方の辺 × 頂点名。既定で
    Lv1 は 3×14×14=588 通り、Lv2/Lv3 は 2×14×14=392 通り（いずれも閾の250超）。
    頂点名の自由度がさらに乗る（params に残すので dup に効く）。

    【退化の封じ方】2辺を相異にする。等しいと「底面の半径と高さが同じ」になり、
    どちらがどちらか区別できているかを問えない（Lv2 の要点が消える）。
    """
    shape = str(draw(list(p["shape_set"]), rng))
    lo, hi = (int(v) for v in p["length_range"])
    axis_len = int(draw({"int_range": [lo, hi]}, rng))
    other_cands = [v for v in range(lo, hi + 1) if v != axis_len]
    other_len = int(draw({"int_set": other_cands}, rng))
    names = _draw_distinct_points(_SHAPE_VERTEX_COUNT[shape], rng)
    return shape, axis_len, other_len, names


def _source_params(
    shape: str, axis_len: int, other_len: int, names: list[str], p: dict[str, Any]
) -> dict[str, Any]:
    lo, hi = (int(v) for v in p["length_range"])
    return {
        "view": "rotation_source",
        "shape": shape,
        "width_px": _to_px(other_len, lo, hi),
        "height_px": _to_px(axis_len, lo, hi),
        "vertices": list(names),
        # 構成した長さは params に残す（dup_key は params のみを見る）。
        "axis_len": axis_len,
        "other_len": other_len,
    }


def _statement(shape: str, axis_len: int, other_len: int, names: list[str], unit: str) -> str:
    if shape == "rectangle":
        a, b, c, d = names
        return (
            f"1辺が{axis_len}{unit}、となりの辺が{other_len}{unit}の長方形{a}{b}{c}{d}を、"
            f"辺{d}{a}を回転の軸として1回転させる"
        )
    if shape == "right_triangle":
        b, c, a = names
        return (
            f"∠{b}が直角で、{a}{b}が{axis_len}{unit}、{b}{c}が{other_len}{unit}の"
            f"直角三角形{a}{b}{c}を、辺{a}{b}を回転の軸として1回転させる"
        )
    p_, q_, r_ = names
    return (
        f"直径{p_}{r_}が{axis_len}{unit}の半円{p_}{q_}{r_}を、"
        f"直径{p_}{r_}を回転の軸として1回転させる"
    )


def _mr(
    ctx: CellContext, *, params: dict[str, Any], statement: str, asked: str, sol: Solution,
    recipe: str, element_kind: str = "rotation_source",
) -> MR:
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given={"condition": statement},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked=asked, answer=sol.answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
        ],
        visual_plan=VisualPlan(
            style="solid",
            labels=solid_labels(params),
            # "solid"（答えの立体）ではなく、問題図として出してよいビューを宣言する
            # （回転体の元図／投影図）。"solid" は frame の禁止要素。
            elements=[VisualElement(kind=element_kind, attrs={})],
        ),
        provenance=Provenance(recipe=recipe),
    )


@register_recipe("math.solid_of_revolution", provides_concepts=_REVOLUTION_CONCEPTS)
def solid_of_revolution_recipe(ctx: CellContext, rng: Rng) -> MR:
    """回転体を読む／見取図をかく／断面をかく（g1_l49.graph_table Lv1/Lv2/Lv3）。

    mode で問うものを変える＝op 列が相異する（level_sep）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    mode = str(p["mode"])
    unit = str(p.get("unit", "cm"))
    shape, axis_len, other_len, names = _scene(p, rng)
    params = _source_params(shape, axis_len, other_len, names, p)
    statement = _statement(shape, axis_len, other_len, names, unit)

    if mode == "name":
        sol = cast(Solution, REGISTRY.solver("math.solid_of_revolution_name")(shape))
        return _mr(
            ctx, params=params, statement=f"{statement}。できる立体はどれか、選べ",
            asked="read_solid", sol=sol, recipe="math.solid_of_revolution",
        )

    if mode == "sketch":
        sol = cast(
            Solution,
            REGISTRY.solver("math.solid_of_revolution_sketch")(shape, axis_len, other_len),
        )
        assert isinstance(sol.answer, GraphAnswer)
        answer_params = {
            "view": "sketch",
            "solid_kind": _SHAPE_SOLID[shape],
            "radius_px": params["width_px"],
            "height_px": params["height_px"],
            # 設問が「図中に書き入れよ」なので、模範解答図に寸法を書く。
            "dim_labels": [f"{other_len}{unit}", f"{axis_len}{unit}"],
        }
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(answer_params),
        )
        return _mr(
            ctx, params=params,
            statement=(
                f"{statement}。できる立体の見取図をかき、底面の半径と高さを図中に書き入れよ"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_of_revolution",
        )

    if mode == "section":
        sol = cast(
            Solution,
            REGISTRY.solver("math.solid_of_revolution_section")(shape, axis_len, other_len),
        )
        assert isinstance(sol.answer, GraphAnswer)
        answer_params = {
            "view": "section",
            # 円柱→長方形／円錐→二等辺三角形。図と答えの形を食い違わせない。
            "section_shape": (
                "rectangle" if shape == "rectangle" else "isosceles_triangle"
            ),
            "width_px": 2 * params["width_px"],
            "height_px": params["height_px"],
            "vertices": [],
        }
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(answer_params),
        )
        return _mr(
            ctx, params=params,
            statement=(
                f"{statement}。できる立体を回転の軸をふくむ平面で切ったときの"
                "切り口はどんな図形になるか、その図をかいて示せ"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_of_revolution",
        )

    raise ValueError(f"未知の mode: {mode!r}")


# ---------------------------------------------------------------------------
# g1_l50.graph_table Lv1/Lv2/Lv3: 投影図
#
# 立体 -> (立面図, 平面図) の対応表は solver 側が持つ（`projection_shapes`）。
# recipe は「どの立体をどの寸法で出すか」と、問題図にどちらのビューを見せるかを決める。
# ---------------------------------------------------------------------------
_PROJECTION_CONCEPTS = [
    "solid_projection.read",
    "solid_projection.draw",
    "solid_projection.complete",
]

# 立体の言い方（本文用）。底面の1辺と高さの与え方が立体ごとに違う。
_PROJECTION_PHRASE = {
    "square_prism": "底面が1辺{b}{u}の正方形、高さ{h}{u}の正四角柱",
    "cube": "1辺が{b}{u}の立方体",
    "cylinder": "底面の半径が{b}{u}、高さ{h}{u}の円柱",
    "cone": "底面の半径が{b}{u}、高さ{h}{u}の円錐",
    "sphere": "半径が{b}{u}の球",
    "square_pyramid": "底面が1辺{b}{u}の正方形、高さ{h}{u}の正四角錐",
    "triangular_prism": "底面が1辺{b}{u}の正三角形、高さ{h}{u}の正三角柱",
}


def _projection_scene(p: dict[str, Any], rng: Rng) -> tuple[str, int, int]:
    """(立体, 底面の長さ, 高さ)。

    【組合せ数】立体7種 × 底面 × 高さ（相異）。既定（2〜15）で 7×14×13=1274 通り。

    【退化の封じ方】底面と高さを相異にする（等しいと正四角柱と立方体の区別が
    figure の上でつかなくなる）。
    """
    kind = str(draw(list(p["solid_set"]), rng))
    lo, hi = (int(v) for v in p["length_range"])
    base = int(draw({"int_range": [lo, hi]}, rng))
    height = int(draw({"int_set": [v for v in range(lo, hi + 1) if v != base]}, rng))
    return kind, base, height


def _projection_params(
    kind: str, base: int, height: int, p: dict[str, Any], shown: str
) -> dict[str, Any]:
    lo, hi = (int(v) for v in p["length_range"])
    return {
        "view": "projection",
        "solid_kind": kind,
        "width_px": _to_px(base, lo, hi),
        "height_px": _to_px(height, lo, hi),
        "shown_view": shown,
        "base_len": base,
        "solid_height": height,
    }


@register_recipe("math.solid_projection", provides_concepts=_PROJECTION_CONCEPTS)
def solid_projection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """投影図を読む／かく／片方から他方を構成する（g1_l50.graph_table Lv1/Lv2/Lv3）。"""
    from engine.packs.math.solvers.solid_view import projection_shapes, solid_name_jp

    p = cast("dict[str, Any]", ctx.spec_level.params)
    mode = str(p["mode"])
    unit = str(p.get("unit", "cm"))
    kind, base, height = _projection_scene(p, rng)
    elev, plan = projection_shapes(kind)
    shape_jp = {
        "rect": "長方形", "square": "正方形", "circle": "円",
        "triangle": "三角形", "square_with_diagonals": "対角線のひかれた正方形",
    }

    if mode == "read":
        # 問題図に投影図の両方を出し、立体を選ばせる。
        params = _projection_params(kind, base, height, p, "both")
        sol = cast(Solution, REGISTRY.solver("math.solid_from_projection")(elev, plan))
        return _mr(
            ctx, params=params,
            statement="ある立体の投影図が右のようになっている。この立体はどれか、選べ",
            asked="read_solid", sol=sol, recipe="math.solid_projection",
            element_kind="projection",
        )

    if mode == "draw":
        # 立体は本文で与える。問題図は投影図を出さない（＝答えの先出しになる）。
        params = _projection_params(kind, base, height, p, "none")
        sol = cast(
            Solution, REGISTRY.solver("math.projection_views_of_solid")(kind, base, height)
        )
        assert isinstance(sol.answer, GraphAnswer)
        answer_params = dict(params)
        answer_params["shown_view"] = "both"
        # 設問が「長さがわかるようにかけ」なので、模範解答図に寸法を書く。
        answer_params["dim_labels"] = [f"{base}{unit}", f"{height}{unit}"]
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(answer_params),
        )
        phrase = _PROJECTION_PHRASE[kind].format(b=base, h=height, u=unit)
        return _mr(
            ctx, params=params,
            statement=(
                f"{phrase}がある。この立体の投影図（立面図と平面図）を、"
                "長さがわかるようにかけ"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_projection", element_kind="projection",
        )

    if mode == "complete":
        # 平面図だけを見せ、立面図の形を条件として本文で与えて立体を特定させる。
        params = _projection_params(kind, base, height, p, "plan")
        sol = cast(Solution, REGISTRY.solver("math.complete_projection")(plan, elev))
        assert isinstance(sol.answer, GraphAnswer)
        answer_params = dict(params)
        answer_params["shown_view"] = "both"
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(answer_params),
        )
        return _mr(
            ctx, params=params,
            statement=(
                f"ある立体の投影図のうち、平面図が{shape_jp[plan]}であることだけが"
                f"右の図でわかっている。立面図が{shape_jp[elev]}になる立体は何か特定し、"
                "その立面図をかいて示せ"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_projection", element_kind="projection",
        )

    raise ValueError(f"未知の mode: {mode!r}")


# ---------------------------------------------------------------------------
# g1_l51.graph_table Lv2/Lv3: 展開図
# ---------------------------------------------------------------------------
_NET_CONCEPTS = ["solid_net.prism", "solid_net.composite"]

_POLYGON_JP = {3: "正三角形", 4: "正方形", 5: "正五角形", 6: "正六角形"}
_PRISM_JP = {3: "正三角柱", 4: "正四角柱", 5: "正五角柱", 6: "正六角柱"}


@register_recipe("math.solid_net", provides_concepts=_NET_CONCEPTS)
def solid_net_recipe(ctx: CellContext, rng: Rng) -> MR:
    """角柱の展開図をかく／複合立体の側面の展開図をかく（g1_l51.graph_table Lv2/Lv3）。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    mode = str(p["mode"])
    unit = str(p.get("unit", "cm"))
    lo, hi = (int(v) for v in p["length_range"])

    if mode == "prism":
        n = int(draw({"int_set": [int(v) for v in p["face_count_set"]]}, rng))
        base = int(draw({"int_range": [lo, hi]}, rng))
        # 1辺と高さを相異にし、さらに「側面の長方形の縦と横」が一致する組も外す
        # （縦＝横だと、横が底面の周の長さであることを正しく出せたか判別できない）。
        height = int(draw({
            "int_set": [
                v for v in range(lo, hi + 1) if v != base and v != n * base
            ]
        }, rng))
        sol = cast(
            Solution, REGISTRY.solver("math.prism_net_side_rectangle")(n, base, height)
        )
        assert isinstance(sol.answer, GraphAnswer)
        params: dict[str, Any] = {
            "view": "net",
            "solid_kind": "triangular_prism" if n == 3 else "square_prism",
            "face_count": n,
            "width_px": _to_px(base, lo, hi) * 0.5,
            "height_px": _to_px(height, lo, hi),
            "base_px": _to_px(base, lo, hi) * 0.5,
            "base_edges": n,
            "base_len": base,
            "solid_height": height,
        }
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(params),
        )
        return _mr(
            ctx, params=params,
            statement=(
                f"底面が1辺{base}{unit}の{_POLYGON_JP[n]}、高さ{height}{unit}の"
                f"{_PRISM_JP[n]}がある。この立体の展開図をかき、"
                "側面の長方形の縦と横の長さを書き入れよ"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_net", element_kind="net",
        )

    if mode == "composite":
        # 母線 √(r²+h²) が整数になる (半径, 円錐の高さ) の組だけを列挙して引く。
        # 【定義域の数え上げ】この条件を満たす組は範囲によって
        #   ≦15 で 10 組 ／ ≦20 で 14 組 ／ ≦24 で 22 組 ／ ≦30 で 26 組。
        # 円柱の高さと合わせて 250 通りを超える必要があるので、円錐側は ≦24 まで、
        # 円柱の高さは別レンジ（広め）で引く（≦15 の 10 組では dup 0.27 で落ちた）。
        c_lo, c_hi = (int(v) for v in p["cone_length_range"])
        pairs = [
            (r, h)
            for r in range(c_lo, c_hi + 1)
            for h in range(c_lo, c_hi + 1)
            if sympy.sqrt(r * r + h * h).is_Integer
        ]
        idx = int(draw({"int_set": list(range(len(pairs)))}, rng))
        radius, cone_h = pairs[idx]
        cyl_lo, cyl_hi = (int(v) for v in p["cylinder_height_range"])
        cyl_h = int(draw({"int_range": [cyl_lo, cyl_hi]}, rng))
        sol = cast(
            Solution, REGISTRY.solver("math.composite_side_net")(radius, cyl_h, cone_h)
        )
        assert isinstance(sol.answer, GraphAnswer)
        slant = int(sympy.sqrt(radius * radius + cone_h * cone_h))
        params = {
            "view": "net",
            "solid_kind": "cylinder_cone_side",
            "width_px": 0,
            "height_px": _to_px(cyl_h, cyl_lo, cyl_hi),
            "band_width_px": 150.0,
            "slant_px": _to_px(slant, c_lo, 2 * c_hi),
            # おうぎ形の中心角は 360°×(底面の半径/母線)。図の形を答えと合わせる。
            "sector_angle_deg": 360.0 * radius / slant,
            "radius_len": radius,
            "cone_height": cone_h,
            "cylinder_height": cyl_h,
            "dim_labels": [
                f"{cyl_h}{unit}", f"{2 * radius}π{unit}",
                f"{slant}{unit}", f"{2 * radius}π{unit}",
            ],
        }
        answer = GraphAnswer(
            features=sol.answer.features,
            solution_svg_ref=render_solid_solution_svg(params),
        )
        return _mr(
            ctx, params=params,
            statement=(
                f"底面の半径{radius}{unit}、高さ{cyl_h}{unit}の円柱の上に、"
                f"底面の半径が等しく高さ{cone_h}{unit}の円錐をのせた立体がある。"
                "この立体の側面部分の展開図をかき、面積計算に必要な長さ"
                "（円柱側面の縦横・円錐側面のおうぎ形の半径と弧の長さ）を書き入れよ。"
                "ただし円周率はπとする"
            ),
            asked="draw_solid", sol=Solution(answer=answer, steps=sol.steps),
            recipe="math.solid_net", element_kind="net",
        )

    raise ValueError(f"未知の mode: {mode!r}")


__all__ = [
    "solid_of_revolution_recipe",
    "solid_projection_recipe",
    "solid_net_recipe",
]
