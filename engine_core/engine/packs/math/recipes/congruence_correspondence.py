"""合同な図形の対応関係まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C9（g2 図形・平行と合同・三角形と四角形）クラスタのうち g2_l36 の非 visual
find_value/knowledge セル群に対応する recipe を集約する。
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

_SIDE_PAIRS: list[tuple[int, int]] = [(0, 1), (1, 2), (2, 0)]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g2_l36.find_value Lv1: 合同な図形で対応する辺の長さ・角の大きさを求める
# ---------------------------------------------------------------------------
_CONGRUENCE_TRANSFER_CONCEPTS = ["congruence.transfer_values"]


@register_recipe("math.congruence_transfer_values", provides_concepts=_CONGRUENCE_TRANSFER_CONCEPTS)
def congruence_transfer_values_recipe(ctx: CellContext, rng: Rng) -> MR:
    """合同な図形で、わかっている辺の長さ・角の大きさから対応する辺・角を求める

    （g2_l36.find_value Lv1・answer-first）。
    """
    p = ctx.spec_level.params
    # 点名を無作為に引くと「三角形EAQ≡三角形PBR」になる。実物は
    # 「△ABC≡△DEF」のように頂点をアルファベット順に並べて名づける。
    p_labels, q_labels = _draw_named_figures([3, 3], rng)
    pa, pb, pc = p_labels
    qa, qb, qc = q_labels
    side_value = int(draw(p["side_domain"], rng))
    angle_value = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.congruence_transfer_values")
    sol = cast(Solution, solver(side_value, angle_value))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}≡三角形{qa}{qb}{qc}で、辺{pa}{pb}={side_value}cm、"
        f"∠{pb}={angle_value}°である。このとき、辺{qa}{qb}の長さと∠{qb}の大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"side_value": side_value, "angle_value": angle_value},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.congruence_transfer_values"),
    )


# ---------------------------------------------------------------------------
# g2_l36.knowledge Lv1: 合同記号＋対応する辺の判別
# ---------------------------------------------------------------------------
_CONGRUENCE_SYMBOL_SIDE_CONCEPTS = ["congruence.symbol_and_correspondence"]


@register_recipe(
    "math.congruence_symbol_and_side", provides_concepts=_CONGRUENCE_SYMBOL_SIDE_CONCEPTS
)
def congruence_symbol_and_side_recipe(ctx: CellContext, rng: Rng) -> MR:
    """合同を表す記号と、指定した辺に対応する辺を判別する（g2_l36.knowledge Lv1）。"""
    p_labels, q_labels = _draw_named_figures([3, 3], rng)
    i, j = _SIDE_PAIRS[int(draw({"int_set": [0, 1, 2]}, rng))]

    solver = REGISTRY.solver("math.congruence_symbol_and_side")
    sol = cast(Solution, solver(p_labels, q_labels, i, j))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"2つの図形が合同であることを表す記号を答えよ。また、三角形{p_labels}≡三角形{q_labels}"
        f"と書くとき、辺{p_labels[i]}{p_labels[j]}に対応する辺はどれか答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"p_labels": p_labels, "q_labels": q_labels, "i": i, "j": j},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.congruence_symbol_and_side"),
    )


# ---------------------------------------------------------------------------
# g2_l36.knowledge Lv2: 対応する角・辺をそれぞれ判別する
# ---------------------------------------------------------------------------
_CONGRUENCE_PAIR_CONCEPTS = ["congruence.identify_corresponding_pair"]


@register_recipe("math.congruence_corresponding_pair", provides_concepts=_CONGRUENCE_PAIR_CONCEPTS)
def congruence_corresponding_pair_recipe(ctx: CellContext, rng: Rng) -> MR:
    """合同な図形で、指定した角・辺に対応する角・辺をそれぞれ判別する（g2_l36.knowledge Lv2）。"""
    p_labels, q_labels = _draw_named_figures([3, 3], rng)
    angle_i = int(draw({"int_set": [0, 1, 2]}, rng))
    side_i, side_j = _SIDE_PAIRS[int(draw({"int_set": [0, 1, 2]}, rng))]

    solver = REGISTRY.solver("math.congruence_corresponding_pair")
    sol = cast(Solution, solver(p_labels, q_labels, angle_i, side_i, side_j))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"三角形{p_labels}≡三角形{q_labels}であるとき、"
        f"∠{p_labels[angle_i]}に対応する角と、辺{p_labels[side_i]}{p_labels[side_j]}"
        "に対応する辺をそれぞれ答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "p_labels": p_labels, "q_labels": q_labels,
            "angle_i": angle_i, "side_i": side_i, "side_j": side_j,
        },
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.congruence_corresponding_pair"),
    )
