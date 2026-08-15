"""円周角の定理・その逆・弧の比例まわりの recipe（構成的生成・answer-first。

実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l47/l48/l50 の非 visual
find_value/knowledge セル群に対応する recipe を集約する（g3_l49.find_value は
既存 `math.similarity_ratio_transfer` を再利用するため recipes/similarity.py に
`math.circle_similar_chord_length` として集約する）。円周角の定理・その逆・
弧の比例の想起は既存 `math.recall_rule` ハブに topic を追加して対応するため、
ここには含まれない。
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


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l47.find_value Lv1: 中心角から円周角を求める
# ---------------------------------------------------------------------------
_INSCRIBED_ANGLE_FROM_CENTRAL_CONCEPTS = ["circle.inscribed_angle_from_central"]


@register_recipe(
    "math.inscribed_angle_from_central", provides_concepts=_INSCRIBED_ANGLE_FROM_CENTRAL_CONCEPTS
)
def inscribed_angle_from_central_recipe(ctx: CellContext, rng: Rng) -> MR:
    """中心角から、同じ弧に対する円周角の大きさを求める（g3_l47.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    # 円周上の点はアルファベット順に名づける（実物は「円Oの周上に点P」）。
    (v,) = _draw_named_figures([4], rng)
    po, pa, pb, pp = v
    central_angle = int(draw(p["central_angle_domain"], rng))

    solver = REGISTRY.solver("math.inscribed_angle_from_central")
    sol = cast(Solution, solver(central_angle))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"円{po}の周上に点{pp}がある。弧{pa}{pb}に対する中心角∠{pa}{po}{pb}={central_angle}° "
        f"のとき、同じ弧{pa}{pb}に対する円周角∠{pa}{pp}{pb}の大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"central_angle": central_angle, "labels": po + pa + pb + pp},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.inscribed_angle_from_central"),
    )


# ---------------------------------------------------------------------------
# g3_l47.find_value Lv3: 2本の弦の交点にできる角を、2つの円周角の組合せで求める
# ---------------------------------------------------------------------------
_INSCRIBED_ANGLE_TWO_CHORDS_CONCEPTS = ["circle.two_chords_intersection_angle"]


@register_recipe(
    "math.inscribed_angle_two_chords_intersection",
    provides_concepts=_INSCRIBED_ANGLE_TWO_CHORDS_CONCEPTS,
)
def inscribed_angle_two_chords_intersection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円周上の4点A,B,C,Dで、弦AD,BCの交点をPとするとき、∠BAC,∠ACDから

    ∠APBの大きさを求める（g3_l47.find_value Lv3・answer-first）。複数の
    円周角を組み合わせる多段構成。central_angleを1回使うLv1とは異なり、
    2つの円周角から対応する弧を求めたうえで交点の角を求める新規solverを使う。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pp = v
    for _ in range(200):
        bac = int(draw(p["angle_domain"], rng))
        acd = int(draw(p["angle_domain"], rng))
        total = bac + acd
        if total != 90 and total <= 150:
            break
    else:
        raise ValueError("inscribed_angle_two_chords_intersection_recipe: 有効な角の組を構成できず")

    solver = REGISTRY.solver("math.inscribed_angle_two_chords_intersection")
    sol = cast(Solution, solver(bac, acd))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        # 「右の図で」と書いていたが、このセルは visual: none（D-6）。弦の交点を
        # 文で指定しているので配置は決まる——図への言及だけを外す。
        f"4点{pa}, {pb}, {pc}, {pd}がこの順に円周上にある。∠{pb}{pa}{pc}={bac}°、"
        f"∠{pa}{pc}{pd}={acd}° であるとき、2本の弦{pa}{pd}, {pb}{pc}の交点を{pp}として、"
        f"∠{pa}{pp}{pb}の大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"bac": bac, "acd": acd, "labels": pa + pb + pc + pd + pp},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.inscribed_angle_two_chords_intersection"),
    )


# ---------------------------------------------------------------------------
# g3_l48.find_value Lv2: 逆で同一円周上と判断し、同じ弧の円周角を転写する
# ---------------------------------------------------------------------------
_INSCRIBED_ANGLE_TRANSFER_CONCEPTS = ["circle.inscribed_angle_transfer_same_arc"]


@register_recipe(
    "math.inscribed_angle_transfer_same_arc", provides_concepts=_INSCRIBED_ANGLE_TRANSFER_CONCEPTS
)
def inscribed_angle_transfer_same_arc_recipe(ctx: CellContext, rng: Rng) -> MR:
    """逆を用いて同一円周上と判断し、同じ弧に対する円周角を転写する

    （g3_l48.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    v1 = int(draw(p["angle_domain"], rng))
    v2 = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.inscribed_angle_transfer_same_arc")
    sol = cast(Solution, solver(v2))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"∠{pa}{pc}{pb}=∠{pa}{pd}{pb}={v1}°であり、4点{pa}, {pb}, {pc}, {pd}は"
        f"同一円周上にある。∠{pd}{pa}{pc}={v2}°のとき、∠{pd}{pb}{pc}の大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"v1": v1, "v2": v2},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.inscribed_angle_transfer_same_arc"),
    )


# ---------------------------------------------------------------------------
# g3_l48.knowledge Lv2: 角の条件から4点が同一円周上にあるかを判別する
# ---------------------------------------------------------------------------
_JUDGE_CONCYCLIC_CONCEPTS = ["circle.judge_concyclic"]


@register_recipe("math.judge_concyclic_from_angle", provides_concepts=_JUDGE_CONCYCLIC_CONCEPTS)
def judge_concyclic_from_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """直線ABの同じ側にある2点C,Dの角が等しいかどうかから、4点が同一円周上に

    あるかを判別する（g3_l48.knowledge Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    is_concyclic = bool(draw([True, False], rng))
    for _ in range(200):
        angle_c = int(draw(p["angle_domain"], rng))
        if is_concyclic:
            angle_d = angle_c
        else:
            delta = int(draw(p["delta_domain"], rng))
            angle_d = angle_c + delta
        if 1 <= angle_d <= 89:
            break
    else:
        raise ValueError("judge_concyclic_from_angle_recipe: 有効な角の組を構成できず")

    solver = REGISTRY.solver("math.judge_concyclic_from_angle")
    sol = cast(Solution, solver(angle_c, angle_d, pa + pb + pc + pd))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"直線{pa}{pb}について同じ側に点{pc}, {pd}がある。∠{pa}{pc}{pb}={angle_c}°、"
        f"∠{pa}{pd}{pb}={angle_d}° のとき、4点{pa}, {pb}, {pc}, {pd}が同一円周上に"
        "あるといえるかどうかを、理由とともに答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"angle_c": angle_c, "angle_d": angle_d, "labels": pa + pb + pc + pd},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_concyclic_from_angle"),
    )


# ---------------------------------------------------------------------------
# g3_l50.find_value Lv2: 弧の長さの倍率から円周角を求める
# ---------------------------------------------------------------------------
_ARC_PROPORTIONAL_ANGLE_CONCEPTS = ["circle.arc_proportional_angle"]


@register_recipe("math.arc_proportional_angle", provides_concepts=_ARC_PROPORTIONAL_ANGLE_CONCEPTS)
def arc_proportional_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """弧の長さの倍率から、対応する円周角の大きさを求める（g3_l50.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    multiplier = int(draw(p["multiplier_domain"], rng))
    known_angle = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.arc_proportional_angle")
    sol = cast(Solution, solver(multiplier, known_angle))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"1つの円で、弧{pa}{pb}の長さは弧{pc}{pd}の長さの{multiplier}倍である。"
        f"弧{pc}{pd}に対する円周角が{known_angle}°のとき、弧{pa}{pb}に対する円周角の"
        "大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"multiplier": multiplier, "known_angle": known_angle, "labels": pa + pb + pc + pd},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.arc_proportional_angle"),
    )


# ---------------------------------------------------------------------------
# g3_l50.find_value Lv3: 円をn等分してできる多角形で頂点を挟まない弧の円周角
# ---------------------------------------------------------------------------
_EQUAL_ARC_INSCRIBED_ANGLE_CONCEPTS = ["circle.equal_arc_inscribed_angle"]

_POLYGON_NAMES = {
    5: "五角形", 6: "六角形", 7: "七角形", 8: "八角形", 9: "九角形",
}


@register_recipe(
    "math.equal_arc_inscribed_angle", provides_concepts=_EQUAL_ARC_INSCRIBED_ANGLE_CONCEPTS
)
def equal_arc_inscribed_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円周をn等分する点を頂点とするn角形で、ある頂点がつくる角の大きさを求める

    （g3_l50.find_value Lv3・answer-first）。台帳の「円周を5等分する点でできる
    五角形で∠ABDを求める」を一般化した、弧の分割と比の合成の多段構成。
    """
    p = ctx.spec_level.params
    # **円周角（span×180/n）が整数になる組だけを引く。** 定義域 n_domain は狭めない
    # （EVALUATION D-23 と同じ根＝角の答えが `225/2°` になっていた。教科書は角を整数に
    # とる）。n=7 はどの span でも整数にならないので、この条件だけで自然に落ちる。
    for _ in range(200):
        n = int(draw(p["n_domain"], rng))
        span = int(draw({"int_range": [1, n - 2]}, rng))
        remain = n - span
        x = int(draw({"int_range": [1, remain - 1]}, rng))
        y = remain - x
        if span * 180 % n:  # 円周角が分数になる（教科書は整数）
            continue
        if span * 180 != 90 * n:  # 円周角が90°に固定される退化を避ける
            break
    else:
        raise ValueError("equal_arc_inscribed_angle_recipe: 有効な分割を構成できず")
    (run,) = _draw_named_figures([n], rng)
    points = list(run)
    labels = "".join(points)

    vertex = points[0]
    pa = points[(0 - x) % n]
    pc = points[(0 + y) % n]

    solver = REGISTRY.solver("math.equal_arc_inscribed_angle")
    sol = cast(Solution, solver(n, labels, vertex, pa, pc))
    assert isinstance(sol.answer, SymbolicAnswer)

    polygon_name = _POLYGON_NAMES.get(n, f"{n}角形")
    statement = (
        f"円周を{n}等分する点を順に{labels}とする。これらの点を頂点とする{polygon_name}"
        f"について、∠{pa}{vertex}{pc}の大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"n": n, "labels": labels, "vertex": vertex, "a": pa, "c": pc},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.equal_arc_inscribed_angle"),
    )
