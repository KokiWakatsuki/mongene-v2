"""三角形の合同条件・二等辺三角形・正三角形まわりの recipe

（構成的生成・answer-first。実装設計 §6.1）。

C9（g2 図形・平行と合同・三角形と四角形）クラスタのうち g2_l41/l42/l43 の非 visual
find_value/knowledge セル群に対応する recipe を集約する。用語・規則の想起
（g2_l37/l38/l41/l42/l43 の一部）は既存 `math.term_recall`/`math.recall_rule` ハブ
（letter_expr.py）に domain/topic を追加して対応するため、ここには含まれない。
"""
from __future__ import annotations

from typing import cast

import sympy

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
# g2_l41.find_value Lv1: 二等辺三角形の頂角/底角の一方からもう一方を求める
# ---------------------------------------------------------------------------
_ISOSCELES_BASE_ANGLE_CONCEPTS = ["isosceles.base_angle_from_apex"]


@register_recipe("math.isosceles_base_angle", provides_concepts=_ISOSCELES_BASE_ANGLE_CONCEPTS)
def isosceles_base_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """二等辺三角形の頂角/底角の一方からもう一方を求める（g2_l41.find_value Lv1・answer-first）。

    「頂角→底角」「底角→頂角」のどちらを問うかを direction で分ける（頂角のみ・
    1〜178°では dup_rate を満たす組合せ数が足りないため、頂角を求める向きも加えて
    実質2倍の variety を確保する。§4.4 の教訓: 単一スカラーで決まるセルは値域拡張
    だけでなく問う向きの追加も検討する）。
    """
    p = ctx.spec_level.params
    direction = str(draw(["apex_to_base", "base_to_apex"], rng))
    if direction == "apex_to_base":
        apex = int(draw(p["apex_domain"], rng))
        solver = REGISTRY.solver("math.isosceles_base_angle")
        sol = cast(Solution, solver("apex", str(apex)))
        assert isinstance(sol.answer, SymbolicAnswer)
        assert sol.answer.srepr == sympy.srepr(sympy.Rational(180 - apex, 2))
        statement = f"AB=ACの二等辺三角形ABCで、頂角∠Aの大きさが{apex}°のとき、底角∠Bの大きさを求めよ"
        params = {"known_type": "apex", "known_value": apex}
    else:
        base = int(draw(p["base_domain"], rng))
        solver = REGISTRY.solver("math.isosceles_base_angle")
        sol = cast(Solution, solver("base", str(base)))
        assert isinstance(sol.answer, SymbolicAnswer)
        assert sol.answer.srepr == sympy.srepr(sympy.Integer(180 - 2 * base))
        statement = f"AB=ACの二等辺三角形ABCで、底角∠Bの大きさが{base}°のとき、頂角∠Aの大きさを求めよ"
        params = {"known_type": "base", "known_value": base}

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.isosceles_base_angle"),
    )


# ---------------------------------------------------------------------------
# g2_l43.find_value Lv1: 正三角形の1辺の長さからもう1辺と1つの内角を求める
# ---------------------------------------------------------------------------
_EQUILATERAL_PROPERTIES_CONCEPTS = ["equilateral.properties_from_side"]


@register_recipe(
    "math.equilateral_triangle_properties", provides_concepts=_EQUILATERAL_PROPERTIES_CONCEPTS
)
def equilateral_triangle_properties_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正三角形の1辺の長さからもう1辺の長さと1つの内角の大きさを求める

    （g2_l43.find_value Lv1・answer-first）。
    """
    p = ctx.spec_level.params
    side = int(draw(p["side_domain"], rng))

    solver = REGISTRY.solver("math.equilateral_triangle_properties")
    sol = cast(Solution, solver(str(side)))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(side), sympy.Rational(180, 3))
    assert sol.answer.srepr == sympy.srepr(expected)

    statement = f"1辺の長さが{side}cmの正三角形ABCで、辺BCの長さと∠Aの大きさを求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"side": side},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.equilateral_triangle_properties"),
    )


# ---------------------------------------------------------------------------
# g2_l42.knowledge Lv2: 2角が等しいという条件から二等辺三角形といえるかを判別する
# ---------------------------------------------------------------------------
_JUDGE_ISOSCELES_CONCEPTS = ["isosceles.judge_from_angle"]


@register_recipe(
    "math.judge_isosceles_from_angle_condition", provides_concepts=_JUDGE_ISOSCELES_CONCEPTS
)
def judge_isosceles_from_angle_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2つの角が等しいという条件から二等辺三角形といえるかを判別する

    （g2_l42.knowledge Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    is_equal = bool(draw([True, False], rng))
    for _ in range(200):
        angle_b = int(draw(p["angle_domain"], rng))
        angle_c = angle_b if is_equal else angle_b + int(draw(p["diff_domain"], rng))
        if angle_b + angle_c < 180:
            break
    else:
        raise ValueError("judge_isosceles_from_angle_condition_recipe: 有効な角の組を構成できず")

    solver = REGISTRY.solver("math.judge_isosceles_from_angle_condition")
    sol = cast(Solution, solver(str(is_equal)))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = f"三角形ABCで、∠B={angle_b}°、∠C={angle_c}°であるとき、この三角形は二等辺三角形であるといえるか、答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"is_equal": str(is_equal), "angle_b": angle_b, "angle_c": angle_c},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_isosceles_from_angle_condition"),
    )


# ---------------------------------------------------------------------------
# g2_l43.knowledge Lv2: 辺と角の条件から正三角形といえるかを判別する
# ---------------------------------------------------------------------------
_JUDGE_EQUILATERAL_CONCEPTS = ["equilateral.judge_from_condition"]


@register_recipe("math.judge_equilateral_from_condition", provides_concepts=_JUDGE_EQUILATERAL_CONCEPTS)
def judge_equilateral_from_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """辺と角の条件から正三角形といえるかを判別する（g2_l43.knowledge Lv2・answer-first）。

    正三角形といえる条件(AB=ACかつ∠A=60°)か、二等辺であるだけの不十分な条件
    (AB=ACのみ)かを、is_equilateral(bool)で切り替える。
    """
    is_equilateral = bool(draw([True, False], rng))
    pa, pb, pc = _draw_distinct_points(3, rng)
    if is_equilateral:
        statement = (
            f"三角形{pa}{pb}{pc}で{pa}{pb}={pa}{pc}かつ∠{pa}=60°であるとき、"
            "この三角形は正三角形であるといえるか、答えよ"
        )
    else:
        statement = (
            f"三角形{pa}{pb}{pc}で{pa}{pb}={pa}{pc}であるとき、"
            "この三角形は正三角形であるといえるか、答えよ"
        )

    solver = REGISTRY.solver("math.judge_equilateral_from_condition")
    sol = cast(Solution, solver(str(is_equilateral)))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"is_equilateral": str(is_equilateral), "a": pa, "b": pb, "c": pc},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_equilateral_from_condition"),
    )
