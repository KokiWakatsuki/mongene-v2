"""相似比から面積比・表面積比・体積比を求めるまわりの recipe

（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l45/l46 の非 visual
find_value セル群に対応する recipe を集約する。面積比・体積比の想起は既存
`math.recall_rule` ハブに topic を追加して対応するため、ここには含まれない。
"""
from __future__ import annotations

import math
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


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _draw_coprime_ratio(rng: Rng, domain: object, max_den: int) -> tuple[int, int]:
    """相似比 m:n（m<n・既約）を有界リトライで構成する。"""
    for _ in range(200):
        a = int(draw(domain, rng))
        b = int(draw([v for v in range(1, max_den + 1) if v != a], rng))
        m, n = min(a, b), max(a, b)
        if math.gcd(m, n) == 1:
            return m, n
    raise ValueError("_draw_coprime_ratio: 既約な相似比を構成できず")


# ---------------------------------------------------------------------------
# g3_l45.find_value Lv2: 相似比から面積比を求め、実際の面積を求める
# ---------------------------------------------------------------------------
_SIMILAR_AREA_RATIO_CONCEPTS = ["similarity.area_ratio"]


@register_recipe("math.similar_area_ratio", provides_concepts=_SIMILAR_AREA_RATIO_CONCEPTS)
def similar_area_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比から面積比を求め、既知の面積から対応する面積を求める

    （g3_l45.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    ratio_num, ratio_den = _draw_coprime_ratio(rng, p["ratio_domain"], 12)
    known_area = int(draw(p["area_domain"], rng))

    solver = REGISTRY.solver("math.similar_area_ratio")
    sol = cast(Solution, solver(ratio_num, ratio_den, known_area))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"相似比が {ratio_num}:{ratio_den} である2つの相似な三角形について、面積比を"
        f"求めよ。また、小さいほうの面積が {known_area}cm² のとき、大きいほうの面積を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": ratio_num, "ratio_den": ratio_den, "known_area": known_area},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_area_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l46.find_value Lv2: 相似比から表面積比・体積比を直接求める
# ---------------------------------------------------------------------------
_SIMILAR_SOLID_RATIO_CONCEPTS = ["similarity.solid_surface_volume_ratio"]


@register_recipe(
    "math.similar_solid_surface_volume_ratio", provides_concepts=_SIMILAR_SOLID_RATIO_CONCEPTS
)
def similar_solid_surface_volume_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比から表面積比・体積比を直接求める（g3_l46.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    ratio_num, ratio_den = _draw_coprime_ratio(rng, p["ratio_domain"], 60)

    solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    sol = cast(Solution, solver(ratio_num, ratio_den))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"相似比が {ratio_num}:{ratio_den} である2つの相似な立体について、表面積の比と"
        "体積の比をそれぞれ求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": ratio_num, "ratio_den": ratio_den},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_solid_surface_volume_ratio"),
    )
