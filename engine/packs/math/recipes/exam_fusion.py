"""exam（入試対策・T1融合）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C13（exam 融合の T1 部）クラスタのうち、新しい数学ロジックを要さず既存 solver の
合成だけで構成できるセルを集約する（g3_l59/probability.py の資産を再利用）。
乱数は `engine.core.rng.draw` 以外で解釈しない。
"""
from __future__ import annotations

from typing import cast

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
from engine.core.rng import Rng, draw, draw_many


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# exam_l5.calculation Lv2: 場合の数から確率を計算処理する（既存 math.relative_frequency 再利用）
# ---------------------------------------------------------------------------
_EXAM_PROBABILITY_FROM_COUNTS_CONCEPTS = ["exam.probability_from_counts"]


@register_recipe(
    "math.exam_probability_from_counts", provides_concepts=_EXAM_PROBABILITY_FROM_COUNTS_CONCEPTS
)
def exam_probability_from_counts_recipe(ctx: CellContext, rng: Rng) -> MR:
    """場合の数(全体・該当)から確率を求める（exam_l5.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    total = int(draw(p["total_domain"], rng))
    favorable = int(draw({"int_range": [1, total - 1]}, rng))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(favorable, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(favorable, total))

    statement = (
        f"ある試行で起こりうる場合が全部で{total}通りあり、そのうち条件に当てはまる場合が"
        f"{favorable}通りである。この条件が起こる確率を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": favorable, "total": total},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_probability_from_counts"),
    )


# ---------------------------------------------------------------------------
# exam_l7.calculation Lv2: 相対度数・比率の計算処理（既存 math.relative_frequency 再利用）
# ---------------------------------------------------------------------------
_EXAM_RELATIVE_FREQUENCY_CONCEPTS = ["exam.relative_frequency_ratio"]


@register_recipe("math.exam_relative_frequency", provides_concepts=_EXAM_RELATIVE_FREQUENCY_CONCEPTS)
def exam_relative_frequency_recipe(ctx: CellContext, rng: Rng) -> MR:
    """標本調査の賛成者数などから相対度数(割合)を求める（exam_l7.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    total = int(draw(p["total_domain"], rng))
    favorable = int(draw({"int_range": [1, total - 1]}, rng))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(favorable, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(favorable, total))

    statement = (
        f"ある調査で、標本{total}人のうち賛成した人が{favorable}人であった。"
        "賛成した人の相対度数(割合)を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": favorable, "total": total},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_relative_frequency"),
    )


# ---------------------------------------------------------------------------
# exam_l7.find_value Lv3: 四分位数・範囲を求める（既存 math.quartiles_full_summary 再利用）
# ---------------------------------------------------------------------------
_EXAM_QUARTILES_FULL_SUMMARY_CONCEPTS = ["exam.quartiles_full_summary"]


@register_recipe(
    "math.exam_quartiles_full_summary", provides_concepts=_EXAM_QUARTILES_FULL_SUMMARY_CONCEPTS
)
def exam_quartiles_full_summary_recipe(ctx: CellContext, rng: Rng) -> MR:
    """データの第1〜第3四分位数・四分位範囲を求める（exam_l7.find_value Lv3・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(p["n_domain"], rng))
    data = [int(v) for v in draw_many(p["value_domain"], rng, n)]

    solver = REGISTRY.solver("math.quartiles_full_summary")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = (
        f"次の{n}個のデータについて、第1四分位数・第2四分位数(中央値)・第3四分位数、"
        f"および四分位範囲を求めよ。データ:{data_text}"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_quartiles_full_summary"),
    )
