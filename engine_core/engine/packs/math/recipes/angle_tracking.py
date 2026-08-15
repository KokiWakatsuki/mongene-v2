"""平行線・三角形・多角形の角まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C9（g2 図形・平行と合同）クラスタのうち g2_l31〜l35（角度追跡）の非 visual find_value
セル群に対応する recipe を集約する。乱数は `engine.core.rng.draw` 以外で解釈しない。

g2_l31/g2_l32 は同じ recipe（`math.solve_angle_by_equality_relation` /
`math.solve_zigzag_angle_sum`）を再利用する（family をまたぐ再利用は level_sep に
影響しない・g1_l43 が g1_l37 Lv2 と domain を共有したのと同型）。l31 は対頂角も
ふくむ3種の関係、l32 は平行線特有の同位角/錯角の2種に family yaml の
`relation_set` で絞る。
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


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g2_l31/l32.find_value Lv1: 対頂角・同位角・錯角の関係を1つ使い角を求める
# ---------------------------------------------------------------------------
_ANGLE_EQUALITY_CONCEPTS = ["angle_pair.solve_by_equality"]
_RELATION_CONTEXT_JP = {
    "vertical": "2直線ℓ、mが1点で交わっている",
    "corresponding": "2直線ℓ、mが平行であり、直線nが交わっている",
    "alternate": "2直線ℓ、mが平行であり、直線nが交わっている",
}
_RELATION_LABEL_JP = {"vertical": "対頂角", "corresponding": "同位角", "alternate": "錯角"}


@register_recipe("math.solve_angle_by_equality_relation", provides_concepts=_ANGLE_EQUALITY_CONCEPTS)
def solve_angle_by_equality_relation_recipe(ctx: CellContext, rng: Rng) -> MR:
    """対頂角/同位角/錯角の関係を1つ使い、等しい角を求める（g2_l31/l32.find_value Lv1）。"""
    p = ctx.spec_level.params
    relation = str(draw(cast("list[str]", p["relation_set"]), rng))
    angle = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.solve_angle_by_equality_relation")
    sol = cast(Solution, solver(relation, str(angle)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(angle))

    context = _RELATION_CONTEXT_JP[relation]
    label = _RELATION_LABEL_JP[relation]
    statement = f"{context}。∠aの大きさは{angle}°である。∠aの{label}にあたる∠xの大きさを求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"relation": relation, "angle": angle},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.solve_angle_by_equality_relation"),
    )


# ---------------------------------------------------------------------------
# g2_l31/l32.find_value Lv2: 折れ曲がった線の角を補助線で2つに分けて求める
# ---------------------------------------------------------------------------
_ZIGZAG_CONCEPTS = ["angle_pair.solve_zigzag"]


@register_recipe("math.solve_zigzag_angle_sum", provides_concepts=_ZIGZAG_CONCEPTS)
def solve_zigzag_angle_sum_recipe(ctx: CellContext, rng: Rng) -> MR:
    """平行線間で折れ曲がった角を、頂点を通る補助線で2つに分けて求める

    （g2_l31/l32.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    a1 = int(draw(p["angle_domain"], rng))
    a2 = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.solve_zigzag_angle_sum")
    sol = cast(Solution, solver(str(a1), str(a2)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(a1 + a2))

    statement = (
        f"2直線ℓ、mが平行である。折れ曲がった線の途中の角がそれぞれ{a1}°、{a2}°で"
        "あるとき、補助線をひいて∠xの大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"angle1": a1, "angle2": a2},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.solve_zigzag_angle_sum"),
    )


# ---------------------------------------------------------------------------
# g2_l32.knowledge Lv2: 角の条件から平行かどうかを判別する
# ---------------------------------------------------------------------------
_JUDGE_PARALLEL_CONCEPTS = ["parallel_lines.judge_from_angle"]


@register_recipe(
    "math.judge_parallel_from_angle_condition", provides_concepts=_JUDGE_PARALLEL_CONCEPTS
)
def judge_parallel_from_angle_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """同位角/錯角が等しいという条件から2直線が平行といえるかを判別する

    （g2_l32.knowledge Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    is_equal = bool(draw([True, False], rng))
    angle_a = int(draw(p["angle_domain"], rng))
    angle_b = angle_a if is_equal else angle_a + int(draw(p["diff_domain"], rng))

    solver = REGISTRY.solver("math.judge_parallel_from_angle_condition")
    sol = cast(Solution, solver(str(is_equal)))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"2直線ℓ、mに1本の直線nが交わっている。同位角がそれぞれ{angle_a}°、{angle_b}°で"
        "あるとき、ℓとmは平行であるといえるか、答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"is_equal": str(is_equal), "angle_a": angle_a, "angle_b": angle_b},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_parallel_from_angle_condition"),
    )


# ---------------------------------------------------------------------------
# g2_l33.find_value Lv1: 三角形の内角の和180°で第3の角を求める
# ---------------------------------------------------------------------------
_TRIANGLE_THIRD_ANGLE_CONCEPTS = ["triangle_angle.third_angle"]


_ARROWHEAD_ANGLE_CONCEPTS = ["triangle_angle.arrowhead_multi_step"]


@register_recipe("math.arrowhead_angle", provides_concepts=_ARROWHEAD_ANGLE_CONCEPTS)
def arrowhead_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """内部の点がつくる角を外角の性質2回で求める（g2_l33.find_value Lv2・answer-first）。

    3つの角の和が平角未満になるまで有界リトライする（和が平角以上だと、内部に点を
    とった図として成立しない）。図は与えず、どの点をどう結ぶかを文で述べる
    ——文だけで図が一意に決まる構成なので、visual を使わずに成立する。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        a = int(draw(p["angle_domain"], rng))
        b = int(draw(p["angle_domain"], rng))
        c = int(draw(p["angle_domain"], rng))
        if a + b + c < 180:
            break
    else:
        raise ValueError("arrowhead_angle_recipe: 和が平角未満の組を構成できず")

    solver = REGISTRY.solver("math.arrowhead_angle")
    sol = cast(Solution, solver(str(a), str(b), str(c)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(a + b + c))

    statement = (
        f"三角形ABCの内部に点Dがあり、点Bと点D、点Cと点Dをそれぞれ結ぶ。"
        f"∠BAC={a}°、∠ABD={b}°、∠ACD={c}°のとき、∠BDCの大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"angle_a": a, "angle_b": b, "angle_c": c},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.arrowhead_angle"),
    )


@register_recipe("math.triangle_third_angle", provides_concepts=_TRIANGLE_THIRD_ANGLE_CONCEPTS)
def triangle_third_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形の内角の和180°から第3の角を求める（g2_l33.find_value Lv1・answer-first）。

    2つの内角 a,b(a+b<180) を先に引き、c=180-a-b(>0) を計算する。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        a = int(draw(p["angle_domain"], rng))
        b = int(draw(p["angle_domain"], rng))
        if a + b < 180:
            break
    else:
        raise ValueError("triangle_third_angle_recipe: a+b<180 を満たす組を構成できず")

    solver = REGISTRY.solver("math.triangle_third_angle")
    sol = cast(Solution, solver(str(a), str(b)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(180 - a - b))

    statement = f"三角形ABCで、∠A={a}°、∠B={b}°のとき、∠Cの大きさを求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"angle_a": a, "angle_b": b},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.triangle_third_angle"),
    )


# ---------------------------------------------------------------------------
# g2_l34.find_value Lv1/Lv2: 多角形の内角の和・1つの内角／辺の数の逆算
# ---------------------------------------------------------------------------
_POLYGON_INTERIOR_CONCEPTS = ["polygon_angle.interior_sum_and_angle"]
_POLYGON_SIDES_CONCEPTS = ["polygon_angle.sides_from_interior_sum"]

_POLYGON_NAME_JP = {
    5: "五角形", 6: "六角形", 7: "七角形", 8: "八角形", 9: "九角形", 10: "十角形",
    11: "十一角形", 12: "十二角形", 15: "十五角形", 18: "十八角形", 20: "二十角形",
}


def _polygon_name(n: int) -> str:
    return _POLYGON_NAME_JP.get(n, f"{n}角形")


@register_recipe("math.polygon_interior_sum_and_angle", provides_concepts=_POLYGON_INTERIOR_CONCEPTS)
def polygon_interior_sum_and_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正n角形の内角の和と1つの内角を求める（g2_l34.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(cast("list[int]", p["sides_domain"]), rng))

    solver = REGISTRY.solver("math.polygon_interior_sum_and_angle")
    sol = cast(Solution, solver(str(n)))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(180 * (n - 2), sympy.Rational(180 * (n - 2), n))
    assert sol.answer.srepr == sympy.srepr(expected)

    statement = f"正{_polygon_name(n)}の内角の和を求めよ。また、正{_polygon_name(n)}の1つの内角の大きさを求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"sides": n},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.polygon_interior_sum_and_angle"),
    )


@register_recipe("math.polygon_sides_from_interior_sum", provides_concepts=_POLYGON_SIDES_CONCEPTS)
def polygon_sides_from_interior_sum_recipe(ctx: CellContext, rng: Rng) -> MR:
    """多角形の内角の和から辺の数(何角形か)を逆算する（g2_l34.find_value Lv2・answer-first）。

    辺の数 n を先に引き、内角の和 = 180*(n-2) を逆算対象として提示する。
    """
    p = ctx.spec_level.params
    n = int(draw(cast("list[int]", p["sides_domain"]), rng))
    total = 180 * (n - 2)

    solver = REGISTRY.solver("math.polygon_sides_from_interior_sum")
    sol = cast(Solution, solver(str(total)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(n))

    statement = f"内角の和が{total}°である多角形は何角形か求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"interior_sum": total, "sides": n},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.polygon_sides_from_interior_sum"),
    )


# ---------------------------------------------------------------------------
# g2_l35.find_value Lv1/Lv2: 正n角形の1つの外角／内角から辺の数を逆算
# ---------------------------------------------------------------------------
_POLYGON_EXTERIOR_CONCEPTS = ["polygon_angle.regular_exterior_angle"]
_POLYGON_SIDES_FROM_INTERIOR_ANGLE_CONCEPTS = ["polygon_angle.sides_from_interior_angle"]


@register_recipe("math.regular_polygon_exterior_angle", provides_concepts=_POLYGON_EXTERIOR_CONCEPTS)
def regular_polygon_exterior_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正n角形の1つの外角の大きさを求める（g2_l35.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(cast("list[int]", p["sides_domain"]), rng))

    solver = REGISTRY.solver("math.regular_polygon_exterior_angle")
    sol = cast(Solution, solver(str(n)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(360, n))

    statement = f"正{_polygon_name(n)}の1つの外角の大きさを求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"sides": n},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.regular_polygon_exterior_angle"),
    )


@register_recipe(
    "math.polygon_sides_from_interior_angle",
    provides_concepts=_POLYGON_SIDES_FROM_INTERIOR_ANGLE_CONCEPTS,
)
def polygon_sides_from_interior_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正多角形の1つの内角の大きさから辺の数(正何角形か)を求める

    （g2_l35.find_value Lv2・answer-first）。辺の数 n を先に引き、内角 = 180-360/n を
    逆算対象として提示する。外角(360/n)の分母が極端に大きくない(≤90)組合せだけを
    有界リトライで採用する（分母の上限を小さく絞りすぎると採用される n が360の約数
    付近に偏り dup_rate が悪化するため、実測(engine.eval 100 seed)で分母上限を
    段階的にゆるめて確認した値。g1_l46 の sector 逆算と同じ設計判断）。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        n = int(draw(cast("list[int]", p["sides_domain"]), rng))
        ext = sympy.Rational(360, n)
        if ext.q <= 90:
            break
    else:
        raise ValueError("polygon_sides_from_interior_angle_recipe: 分母が大きすぎない外角を構成できず")
    interior = 180 - ext

    solver = REGISTRY.solver("math.polygon_sides_from_interior_angle")
    sol = cast(Solution, solver(str(interior)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(n))

    statement = f"1つの内角が{sympy.sstr(interior)}°である正多角形は正何角形か、外角の和を使って求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"interior_angle": str(interior), "sides": n},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.polygon_sides_from_interior_angle"),
    )
