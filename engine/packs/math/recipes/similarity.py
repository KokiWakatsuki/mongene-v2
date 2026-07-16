"""相似な図形まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l39 の非 visual
find_value/knowledge セル群に対応する recipe を集約する。相似・相似比の用語想起
は既存 `math.term_recall` ハブに domain を追加して対応するため、ここには含まれ
ない。
"""
from __future__ import annotations

import math
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
from engine.packs.math.recipes.letter_expr import _draw_distinct_points


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l39.find_value Lv2: 相似比を用い対応辺の長さを比例式で求める
# ---------------------------------------------------------------------------
_SIMILARITY_RATIO_TRANSFER_CONCEPTS = ["similarity.ratio_transfer"]


@register_recipe(
    "math.similarity_ratio_transfer", provides_concepts=_SIMILARITY_RATIO_TRANSFER_CONCEPTS
)
def similarity_ratio_transfer_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比を用い、対応する辺の長さを比例式で求める（g3_l39.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
    for _ in range(200):
        ratio_num = int(draw(p["ratio_domain"], rng))
        ratio_den = int(draw([v for v in range(1, 13) if v != ratio_num], rng))
        if math.gcd(ratio_num, ratio_den) == 1:
            break
    else:
        raise ValueError("similarity_ratio_transfer_recipe: 既約な相似比を構成できず")
    known_side = int(draw(p["side_domain"], rng))

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(ratio_num, ratio_den, known_side))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}は相似で、相似比は {ratio_num}:{ratio_den} "
        f"である。{pa}{pb}={known_side}cm のとき、対応する辺{pd}{pe}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": ratio_num, "ratio_den": ratio_den, "known_side": known_side},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similarity_ratio_transfer"),
    )


# ---------------------------------------------------------------------------
# g3_l39.knowledge Lv2: 相似な四角形で対応する頂点を判別する
# （スコープ縮小: 相似比の算出部分は本セルでは扱わず対応頂点の判別に絞る）
# ---------------------------------------------------------------------------
_IDENTIFY_SIMILAR_VERTEX_CONCEPTS = ["similarity.identify_corresponding_vertex"]


@register_recipe(
    "math.identify_similar_corresponding_vertex",
    provides_concepts=_IDENTIFY_SIMILAR_VERTEX_CONCEPTS,
)
def identify_similar_corresponding_vertex_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似な四角形で、指定した頂点に対応する頂点を判別する（g3_l39.knowledge Lv2・answer-first）。"""
    pa, pb, pc, pd, pe, pf, pg, ph = _draw_distinct_points(8, rng)
    labels1, labels2 = pa + pb + pc + pd, pe + pf + pg + ph
    index = int(draw({"int_set": [0, 1, 2, 3]}, rng))

    solver = REGISTRY.solver("math.identify_similar_corresponding_vertex")
    sol = cast(Solution, solver(labels1, labels2, index))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"四角形{labels1}と四角形{labels2}が相似で、その順に対応しているとき、"
        f"頂点{labels1[index]}に対応する頂点はどれか答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"labels1": labels1, "labels2": labels2, "index": index},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.identify_similar_corresponding_vertex"),
    )


# ---------------------------------------------------------------------------
# g3_l41.find_value Lv2: 証明された相似(頂点Aを共有)から相似比で辺の長さを求める
# 既存 solver math.similarity_ratio_transfer を、AE:AB を相似比としてそのまま
# 再利用する（family をまたぐ recipe/solver 共有は level_sep に無関係・確認済み）。
# ---------------------------------------------------------------------------
_SIMILARITY_PROVEN_RATIO_CONCEPTS = ["similarity.proven_ratio_length"]


@register_recipe(
    "math.similarity_proven_ratio_length", provides_concepts=_SIMILARITY_PROVEN_RATIO_CONCEPTS
)
def similarity_proven_ratio_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """証明済みの相似(頂点を共有する△ABC∽△AED型)から、相似比で辺の長さを求める

    （g3_l41.find_value Lv2・answer-first）。AE:AB を相似比として
    `math.similarity_ratio_transfer` にそのまま渡し、DE から対応する BC を求める。
    """
    p = ctx.spec_level.params
    pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
    for _ in range(200):
        ae = int(draw(p["side_domain"], rng))
        ab = int(draw(p["side_domain"], rng))
        if math.gcd(ae, ab) == 1:
            break
    else:
        raise ValueError("similarity_proven_ratio_length_recipe: 既約な比を構成できず")
    de = int(draw(p["side_domain"], rng))

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(ae, ab, de))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}∽三角形{pa}{pd}{pe}であることが証明されている。"
        f"{pa}{pd}={ae}cm, {pa}{pb}={ab}cm, {pd}{pe}={de}cm のとき、"
        f"辺{pb}{pc}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": ae, "ratio_den": ab, "known_side": de},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similarity_proven_ratio_length"),
    )


# ---------------------------------------------------------------------------
# g3_l49.find_value Lv2: 円周上の4点でつくられる証明済みの相似(頂点Pを共有)
# から辺の長さを求める。既存 solver math.similarity_ratio_transfer を、
# PA:PD を相似比としてそのまま再利用する（family をまたぐ再利用・l41 と同型）。
# ---------------------------------------------------------------------------
_CIRCLE_SIMILAR_CHORD_LENGTH_CONCEPTS = ["circle.similar_chord_length"]


@register_recipe(
    "math.circle_similar_chord_length", provides_concepts=_CIRCLE_SIMILAR_CHORD_LENGTH_CONCEPTS
)
def circle_similar_chord_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円周上の4点でつくられる証明済みの相似(頂点Pを共有する△PAB∽△PDC型)から、

    弦の長さを求める（g3_l49.find_value Lv2・answer-first）。PA:PD を相似比として
    `math.similarity_ratio_transfer` にそのまま渡し、PB から対応する PC を求める。
    """
    p = ctx.spec_level.params
    pp, pa, pb, pc, pd = _draw_distinct_points(5, rng)
    for _ in range(200):
        pa_len = int(draw(p["side_domain"], rng))
        pd_len = int(draw(p["side_domain"], rng))
        if math.gcd(pa_len, pd_len) == 1:
            break
    else:
        raise ValueError("circle_similar_chord_length_recipe: 既約な比を構成できず")
    pb_len = int(draw(p["side_domain"], rng))

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(pa_len, pd_len, pb_len))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"円周上の4点{pa}, {pb}, {pc}, {pd}について三角形{pp}{pa}{pb}∽三角形{pp}{pd}{pc}"
        f"が示されている。弦{pa}{pc}と弦{pb}{pd}の交点を{pp}とし、{pp}{pa}={pa_len}cm, "
        f"{pp}{pb}={pb_len}cm, {pp}{pd}={pd_len}cm のとき、線分{pp}{pc}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": pa_len, "ratio_den": pd_len, "known_side": pb_len},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.circle_similar_chord_length"),
    )
