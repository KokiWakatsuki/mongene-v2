"""四分位数・箱ひげ図まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C11（データ・統計）クラスタのうち g2_l55〜g2_l57 の非 visual セル群に対応する recipe を
集約する。乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
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
from engine.core.rng import Rng, draw, draw_many


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _draw_data(rng: Rng, p: dict[str, object], n: int) -> list[int]:
    return [int(v) for v in draw_many(p["value_domain"], rng, n)]


# ---------------------------------------------------------------------------
# g2_l55.calculation Lv1: 中央値（第2四分位数）
# ---------------------------------------------------------------------------
_MEDIAN_VALUE_CONCEPTS = ["quartile.compute_median"]


@register_recipe("math.median_value", provides_concepts=_MEDIAN_VALUE_CONCEPTS)
def median_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """データを並べ中央値(第2四分位数)を求める（g2_l55.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw({"int_set": [5, 7, 9, 11]}, rng))
    data = _draw_data(rng, cast("dict[str, object]", p), n)

    solver = REGISTRY.solver("math.median_value")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = f"次のデータを小さい順に並べ、中央値(第2四分位数)を求めよ。データ: {data_text}"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.median_value"),
    )


# ---------------------------------------------------------------------------
# g2_l55.calculation Lv3: 第1/第3四分位数・四分位範囲
# ---------------------------------------------------------------------------
_QUARTILES_IQR_CONCEPTS = ["quartile.compute_q1_q3_iqr"]


@register_recipe("math.quartiles_iqr", provides_concepts=_QUARTILES_IQR_CONCEPTS)
def quartiles_iqr_recipe(ctx: CellContext, rng: Rng) -> MR:
    """第1四分位数・第3四分位数・四分位範囲を求める（g2_l55.calculation Lv3・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw({"int_set": [8, 9, 10, 11, 12, 13]}, rng))
    data = _draw_data(rng, cast("dict[str, object]", p), n)

    solver = REGISTRY.solver("math.quartiles_iqr")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = (
        f"次の{n}個のデータについて、第1四分位数、第3四分位数、および四分位範囲を求めよ。"
        f"データ: {data_text}"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.quartiles_iqr"),
    )


# ---------------------------------------------------------------------------
# g2_l56.calculation Lv1: 最小値・最大値・第1/第3四分位数
# ---------------------------------------------------------------------------
_FIVE_NUMBER_SUMMARY_CONCEPTS = ["quartile.compute_five_number_summary"]


@register_recipe("math.five_number_summary", provides_concepts=_FIVE_NUMBER_SUMMARY_CONCEPTS)
def five_number_summary_recipe(ctx: CellContext, rng: Rng) -> MR:
    """最小値・最大値・第1四分位数・第3四分位数を求める（g2_l56.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw({"int_set": [7, 8, 9, 10, 11]}, rng))
    data = _draw_data(rng, cast("dict[str, object]", p), n)

    solver = REGISTRY.solver("math.five_number_summary")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = f"次のデータについて、最小値・最大値・第1四分位数・第3四分位数を求めよ。データ: {data_text}"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.five_number_summary"),
    )


# ---------------------------------------------------------------------------
# g2_l57.knowledge Lv1: 中央値/範囲/四分位範囲が分布の何を表すかを判別する
# ---------------------------------------------------------------------------
_CLASSIFY_DISTRIBUTION_STATISTIC_CONCEPTS = ["distribution_statistic.classify_role"]
_STATISTIC_LABEL_JP: dict[str, str] = {"median": "中央値", "range": "範囲", "iqr": "四分位範囲"}


@register_recipe(
    "math.classify_distribution_statistic", provides_concepts=_CLASSIFY_DISTRIBUTION_STATISTIC_CONCEPTS
)
def classify_distribution_statistic_recipe(ctx: CellContext, rng: Rng) -> MR:
    """中央値・範囲・四分位範囲が分布の何を表すかを判別する（g2_l57.knowledge Lv1・answer-first）。"""
    p = ctx.spec_level.params
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    n = int(draw(p["number_domain"], rng))
    label = _STATISTIC_LABEL_JP[concept]

    solver = REGISTRY.solver("math.classify_distribution_statistic")
    sol = cast(Solution, solver(concept))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = f"{n}個のデータを表した箱ひげ図における{label}が、データの分布の何を表すかを答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"concept": concept, "n": n},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.classify_distribution_statistic"),
    )
