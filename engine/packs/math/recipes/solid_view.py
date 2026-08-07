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
    recipe: str,
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
            # "solid"（答えの立体）ではなく "rotation_source"（元図）を宣言する。
            elements=[VisualElement(kind="rotation_source", attrs={})],
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


__all__ = ["solid_of_revolution_recipe"]
