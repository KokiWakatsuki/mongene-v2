"""平行線と線分の比の定理・その逆・中点連結定理まわりの recipe

（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l42/l43/l44 の非 visual
find_value セル群に対応する recipe を集約する。定理・その逆・中点連結定理の
想起は既存 `math.recall_rule` ハブに topic を追加して対応するため、ここには
含まれない。
"""
from __future__ import annotations

from typing import cast

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
from engine.packs.math.recipes.letter_expr import _draw_distinct_points


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l42.find_value Lv2: DE∥BC のとき AD,DB,DE から辺BCの長さを求める
# ---------------------------------------------------------------------------
_PARALLEL_SEGMENT_RATIO_LENGTH_CONCEPTS = ["parallel_segment.ratio_length"]


@register_recipe(
    "math.parallel_segment_ratio_length", provides_concepts=_PARALLEL_SEGMENT_RATIO_LENGTH_CONCEPTS
)
def parallel_segment_ratio_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """DE∥BC のとき、AD,DB,DE から辺BCの長さを求める（g3_l42.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
    ad = int(draw(p["length_domain"], rng))
    db = int(draw(p["length_domain"], rng))
    de = int(draw(p["length_domain"], rng))

    solver = REGISTRY.solver("math.parallel_segment_ratio_length")
    sol = cast(Solution, solver(ad, db, de))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}があり、"
        f"{pd}{pe}∥{pb}{pc}である。{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pd}{pe}={de}cm "
        f"のとき、辺{pb}{pc}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "de": de},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.parallel_segment_ratio_length"),
    )


# ---------------------------------------------------------------------------
# g3_l43.find_value Lv2: AD:DBとAE:ECの比を比べてDE∥BCといえるかを確かめる
# ---------------------------------------------------------------------------
_JUDGE_PARALLEL_FROM_RATIO_CONCEPTS = ["parallel_segment.judge_from_ratio"]


@register_recipe(
    "math.judge_parallel_from_ratio", provides_concepts=_JUDGE_PARALLEL_FROM_RATIO_CONCEPTS
)
def judge_parallel_from_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """AD:DBとAE:ECの比を比べて、DE∥BCといえるかを確かめる

    （g3_l43.find_value Lv2・answer-first）。is_parallel(bool)で、比が一致する
    構成か、片方をずらして一致しない構成かを切り替える。
    """
    p = ctx.spec_level.params
    pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
    is_parallel = bool(draw([True, False], rng))
    expected = "平行である" if is_parallel else "平行ではない"
    for _ in range(200):
        ad = int(draw(p["length_domain"], rng))
        db = int(draw(p["length_domain"], rng))
        scale = int(draw(p["scale_domain"], rng))
        ae, ec = ad * scale, db * scale
        if not is_parallel:
            delta = int(draw(p["delta_domain"], rng))
            ec += delta
        solver = REGISTRY.solver("math.judge_parallel_from_ratio")
        sol = cast(Solution, solver(ad, db, ae, ec))
        assert isinstance(sol.answer, SymbolicAnswer)
        if sol.answer.display == expected:
            break
    else:
        raise ValueError("judge_parallel_from_ratio_recipe: 有効な比の組を構成できず")

    statement = (
        f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}がある。"
        f"{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pa}{pe}={ae}cm, {pe}{pc}={ec}cm であるとき、"
        f"{pd}{pe}と{pb}{pc}が平行であるかどうかを、比を調べて答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "ae": ae, "ec": ec},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_parallel_from_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l44.find_value Lv2: 中点連結定理で中点を結ぶ線分の長さを求める
# ---------------------------------------------------------------------------
_MIDPOINT_CONNECTOR_LENGTH_CONCEPTS = ["midpoint_connector.length"]


@register_recipe(
    "math.midpoint_connector_length", provides_concepts=_MIDPOINT_CONNECTOR_LENGTH_CONCEPTS
)
def midpoint_connector_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形の2辺の中点を結ぶ線分の長さを求める（g3_l44.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    pa, pb, pc, pm, pn = _draw_distinct_points(5, rng)
    bc = int(draw(p["side_domain"], rng))

    solver = REGISTRY.solver("math.midpoint_connector_length")
    sol = cast(Solution, solver(bc))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}の中点をそれぞれ{pm}, {pn}とする。"
        f"{pb}{pc}={bc}cm のとき、線分{pm}{pn}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"bc": bc},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.midpoint_connector_length"),
    )
