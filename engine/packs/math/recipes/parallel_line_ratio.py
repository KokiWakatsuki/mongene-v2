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
from engine.packs.math.recipes.letter_expr import _draw_distinct_lines, _draw_distinct_points


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
# g3_l42.find_value Lv3: 3本の平行線l,m,nが2直線を切る比から辺の長さを求める（多段）
# ---------------------------------------------------------------------------
_PARALLEL_LINES_TRANSVERSAL_RATIO_CONCEPTS = ["parallel_segment.transversal_ratio"]


@register_recipe(
    "math.parallel_lines_transversal_ratio",
    provides_concepts=_PARALLEL_LINES_TRANSVERSAL_RATIO_CONCEPTS,
)
def parallel_lines_transversal_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """3本の平行線が2直線と交わってできる線分の比から、辺の長さを求める

    （g3_l42.find_value Lv3・answer-first）。台帳の「3本の直線l,m,nが平行、
    AB=3,BC=x,DE=4,EF=6でxを求める」を一般化した比例配分。三角形内の
    DE∥BCとは別の定理（3本の平行線が2直線を切る比は等しい）を使うため、
    Lv2の math.parallel_segment_ratio_length とは異なる新規solver。
    """
    p = ctx.spec_level.params
    pl1, pl2, pl3, pt1, pt2 = _draw_distinct_lines(5, rng)
    pa, pb, pc, pd, pe, pf = _draw_distinct_points(6, rng)
    for _ in range(200):
        ab = int(draw(p["length_domain"], rng))
        de = int(draw(p["length_domain"], rng))
        ef = int(draw(p["length_domain"], rng))
        if de != ef:  # 比が1:1に潰れる退化を避ける
            break
    else:
        raise ValueError("parallel_lines_transversal_ratio_recipe: 有効な比を構成できず")

    solver = REGISTRY.solver("math.parallel_lines_transversal_ratio")
    sol = cast(Solution, solver(ab, de, ef))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"右の図で、3本の直線{pl1}, {pl2}, {pl3}は平行である。直線{pt1}は"
        f"{pl1}, {pl2}, {pl3}とそれぞれ点{pa}, {pb}, {pc}で交わり、直線{pt2}は"
        f"{pl1}, {pl2}, {pl3}とそれぞれ点{pd}, {pe}, {pf}で交わる。"
        f"{pa}{pb}={ab}cm, {pd}{pe}={de}cm, {pe}{pf}={ef}cm のとき、"
        f"線分{pb}{pc}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "ab": ab, "de": de, "ef": ef,
            "labels": pl1 + pl2 + pl3 + pt1 + pt2 + pa + pb + pc + pd + pe + pf,
        },
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.parallel_lines_transversal_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l43.find_value Lv3: 逆で平行を確かめたうえで辺の長さを多段で求める
# ---------------------------------------------------------------------------
_PARALLEL_RATIO_JUDGE_THEN_LENGTH_CONCEPTS = ["parallel_segment.judge_then_length"]


@register_recipe(
    "math.parallel_ratio_judge_then_length",
    provides_concepts=_PARALLEL_RATIO_JUDGE_THEN_LENGTH_CONCEPTS,
)
def parallel_ratio_judge_then_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """AD:DBとAE:ECの比が等しいことからDE∥BCを確かめたうえで、DEの長さから

    辺BCの長さを求める（g3_l43.find_value Lv3・answer-first）。逆（判定）と
    定理（長さ）を組み合わせた多段構成。既存の math.judge_parallel_from_ratio と
    math.parallel_segment_ratio_length を合成した solver を使う（新しい数学的
    計算は増やさない）。
    """
    p = ctx.spec_level.params
    pa, pb, pc, pd, pe = _draw_distinct_points(5, rng)
    for _ in range(200):
        ad = int(draw(p["length_domain"], rng))
        db = int(draw(p["length_domain"], rng))
        scale = int(draw(p["scale_domain"], rng))
        if scale == 1:  # AE:ECがAD:DBと同じ数字の繰り返しになる退化を避ける
            continue
        de = int(draw(p["de_domain"], rng))
        ae, ec = ad * scale, db * scale
        break
    else:
        raise ValueError("parallel_ratio_judge_then_length_recipe: 有効な比を構成できず")

    solver = REGISTRY.solver("math.parallel_ratio_judge_then_length")
    sol = cast(Solution, solver(ad, db, ae, ec, de))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}がある。"
        f"{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pa}{pe}={ae}cm, {pe}{pc}={ec}cm である。"
        f"{pd}{pe}={de}cm のとき、{pd}{pe}と{pb}{pc}が平行であることを確かめたうえで、"
        f"辺{pb}{pc}の長さを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "ae": ae, "ec": ec, "de": de},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.parallel_ratio_judge_then_length"),
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
