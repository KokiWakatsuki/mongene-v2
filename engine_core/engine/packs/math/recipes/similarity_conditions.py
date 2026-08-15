"""三角形の相似条件まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l40 の非 visual
find_value/knowledge セル群に対応する recipe を集約する。3つの相似条件の想起は
既存 `math.recall_rule` ハブに topic を追加して対応するため、ここには含まれ
ない。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.recipes.similarity import _proportional_lengths


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l40.find_value Lv2: AB//CD の交わる線分がつくる相似な三角形から長さを求める
# ---------------------------------------------------------------------------
_SIMILAR_TRIANGLE_X_SHAPE_CONCEPTS = ["similarity.x_shape_length"]


@register_recipe("math.similar_triangle_x_shape", provides_concepts=_SIMILAR_TRIANGLE_X_SHAPE_CONCEPTS)
def similar_triangle_x_shape_recipe(ctx: CellContext, rng: Rng) -> MR:
    """AB//CD の2線分が点Oで交わってできる相似な三角形から、対応する辺の長さを求める

    （g3_l40.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    # OD = OB·OC/OA なので、OC を OA の倍数にとらないと答えが分数になる
    # （OA=168, OB=195, OC=97 で OD=6630/133 が出ていた）。
    # 図形の頂点はアルファベット順に名づける（実物は「正方形ABCD」「△ABC∽△DEF」）。
    # 無作為に引くと「正方形ERDJ」「三角形JQBと三角形CMH」になる。
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, po = v
    oa, ob, oc, _ = _proportional_lengths(
        rng,
        ratio_max=int(p["ratio_max"]),
        scale_max=int(p["scale_max"]),
        side_max=int(p["side_max"]),
    )

    solver = REGISTRY.solver("math.similar_triangle_x_shape")
    sol = cast(Solution, solver(oa, ob, oc, pa + pb + pc + pd + po))
    assert isinstance(sol.answer, SymbolicAnswer)

    # 交わるのは AC と BD（AB と CD は平行なので交わらない。前は
    # 「線分ABと線分CDが点Oで交わり、AB∥CD」＝図として成り立たない文だった）。
    statement = (
        f"線分{pa}{pc}と線分{pb}{pd}が点{po}で交わり、{pa}{pb}∥{pc}{pd}である。"
        f"{po}{pa}={oa}cm, {po}{pb}={ob}cm, {po}{pc}={oc}cm "
        f"のとき、相似な三角形を見つけて線分{po}{pd}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"oa": oa, "ob": ob, "oc": oc, "labels": pa + pb + pc + pd + po},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_triangle_x_shape"),
    )


# ---------------------------------------------------------------------------
# g3_l40.knowledge Lv2: 条件からどの相似条件によるかを判別する
# ---------------------------------------------------------------------------
_IDENTIFY_SIMILARITY_CONDITION_CONCEPTS = ["similarity.identify_condition"]

_SIMILARITY_CONDITION_TEXT: dict[str, str] = {
    "aa": "∠{b}=∠{e} かつ ∠{c}=∠{f}が成り立っている",
    "sas_ratio": "{a}{b}:{d}{e}={a}{c}:{d}{f}={m}:{n}、∠{a}=∠{d}が成り立っている",
    "sss_ratio": "{a}{b}:{d}{e}={b}{c}:{e}{f}={c}{a}:{f}{d}={m}:{n}が成り立っている",
}


@register_recipe(
    "math.identify_similarity_condition", provides_concepts=_IDENTIFY_SIMILARITY_CONDITION_CONCEPTS
)
def identify_similarity_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """示されている条件が、三角形の相似条件のうちどれによるかを判別する

    （g3_l40.knowledge Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    condition_key = str(draw(list(_SIMILARITY_CONDITION_TEXT.keys()), rng))
    f1, f2 = _draw_named_figures([3, 3], rng)
    pa, pb, pc = f1
    pd, pe, pf = f2
    m = int(draw(p["ratio_domain"], rng))
    n = int(draw([v for v in range(1, 8) if v != m], rng))
    condition_text = _SIMILARITY_CONDITION_TEXT[condition_key].format(
        a=pa, b=pb, c=pc, d=pd, e=pe, f=pf, m=m, n=n
    )
    statement = (
        f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}について、{condition_text}とき、"
        "この2つの三角形が相似であることがいえる。用いた相似条件を答えよ"
    )

    solver = REGISTRY.solver("math.identify_similarity_condition")
    sol = cast(Solution, solver(condition_key))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"condition_key": condition_key, "a": pa, "b": pb, "c": pc, "d": pd, "e": pe, "f": pf, "m": m, "n": n},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.identify_similarity_condition"),
    )
