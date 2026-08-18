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
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.packs.math.visuals.circle_figure import two_chords_svg
from engine.packs.math.visuals.similarity_figure import similar_pair_svg
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _proportional_lengths(
    rng: Rng,
    *,
    ratio_max: int,
    scale_max: int,
    side_max: int,
    increasing: bool = False,
) -> tuple[int, int, int, int]:
    """相似比 m:n（既約）と、m の倍数である既知の辺 s=m·k、対応する辺 t=n·k を引く。

    **答えが整数になる組だけを列挙してから引く。** 辺の長さを独立に引いていたため
    「RB=198cm, RF=17cm, BA=171cm のとき FN=34762/37」のような、教材にならない
    答えが出ていた。教科書は「相似比 2:3、AB=8cm のとき DE=12cm」のように、
    与える辺を相似比の倍数にとる。

    **狭めたぶんの組み合わせは、定義域ではなく軸で取り戻す**（点名を params に
    記録して dup_key に効かせる。FIXES.md の原則1・2）。定義域を広げて dup_rate を
    通すのは、この欠陥そのものだった。

    `increasing=True` は m<n を要求する（辺ADが辺ABの一部であるように、
    小さいほうを先に置く場面用）。
    """
    cands: list[tuple[int, int, int, int]] = []
    for m in range(2, ratio_max + 1):
        for n in range(2, ratio_max + 1):
            if m == n or math.gcd(m, n) != 1:
                continue
            if increasing and m > n:
                continue
            for k in range(2, scale_max + 1):
                s, t = m * k, n * k
                if s > side_max or t > side_max:
                    continue
                if t in {m, n, s}:  # 答えが本文に出る数と一致する組は外す（G-Q5t）
                    continue
                cands.append((m, n, s, t))
    if not cands:
        raise ValueError("_proportional_lengths: 有効な組が無い")
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    return cands[idx]


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
    # 図形の頂点はアルファベット順に名づける（実物は「正方形ABCD」「△ABC∽△DEF」）。
    # 無作為に引くと「正方形ERDJ」「三角形JQBと三角形CMH」になる。
    f1, f2 = _draw_named_figures([3, 3], rng)
    pa, pb, pc = f1
    pd, pe, pf = f2
    ratio_num, ratio_den, known_side, _ = _proportional_lengths(
        rng,
        ratio_max=int(p["ratio_max"]),
        scale_max=int(p["scale_max"]),
        side_max=int(p["side_max"]),
    )

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(ratio_num, ratio_den, known_side))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図で、三角形{pa}{pb}{pc}と三角形{pd}{pe}{pf}は相似で、"
        f"相似比は {ratio_num}:{ratio_den} である。{pa}{pb}={known_side}cm のとき、"
        f"対応する辺{pd}{pe}の長さを求めよ"
    )
    # 2つ目は相似比のとおりに縮めて描く（1:2 と書いてあるのに同じ大きさで並んで
    # いる、という食い違いを作らない）。
    figure_svg = similar_pair_svg(
        pa + pb + pc, pd + pe + pf, float(ratio_num), float(ratio_den),
        f"{known_side}cm",
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "ratio_num": ratio_num, "ratio_den": ratio_den, "known_side": known_side,
            # 数を教材の大きさに戻したぶんの組み合わせは、点名の軸で稼ぐ（原則1・2）。
            "labels": pa + pb + pc + pd + pe + pf,
        },
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{known_side}cm", pa, pb, pc, pd, pe, pf],
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
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
    f1, f2 = _draw_named_figures([4, 4], rng)
    pa, pb, pc, pd = f1
    pe, pf, pg, ph = f2
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
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    # 点Dは辺AB上にあるので AD < AB（独立に引くと AD > AB という図にならない組が出る）。
    ae, ab, de, _ = _proportional_lengths(
        rng,
        ratio_max=int(p["ratio_max"]),
        scale_max=int(p["scale_max"]),
        side_max=int(p["side_max"]),
        increasing=True,
    )

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(ae, ab, de))
    assert isinstance(sol.answer, SymbolicAnswer)

    # **相似の書き方の順を、solver に渡す相似比の順にそろえる。**
    # 「三角形ABC∽三角形ADE」と書くと相似比は AB:AD＝ab:ae なのに、
    # solver には (ae, ab) を渡していて、解説が「相似比 2:9」と逆順に出ていた。
    # 小さいほうを先に書けば、相似比 ae:ab とそろう（どちらの順に書いても
    # 正しい式だが、**本文と解説で順が違う**のは生徒が対応を取れない）。
    statement = (
        f"三角形{pa}{pd}{pe}∽三角形{pa}{pb}{pc}であることが証明されている。"
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
        params={
            "ratio_num": ae, "ratio_den": ab, "known_side": de,
            "labels": pa + pb + pc + pd + pe,
        },
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
    one, rest = _draw_named_figures([1, 4], rng)
    pp = one
    pa, pb, pc, pd = rest
    pa_len, pd_len, pb_len, _ = _proportional_lengths(
        rng,
        ratio_max=int(p["ratio_max"]),
        scale_max=int(p["scale_max"]),
        side_max=int(p["side_max"]),
    )

    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = cast(Solution, solver(pa_len, pd_len, pb_len))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図で、円周上の4点{pa}, {pb}, {pc}, {pd}について三角形{pp}{pa}{pb}∽"
        f"三角形{pp}{pd}{pc}が示されている。弦{pa}{pc}と弦{pb}{pd}の交点を{pp}とし、"
        f"{pp}{pa}={pa_len}cm, {pp}{pb}={pb_len}cm, {pp}{pd}={pd_len}cm のとき、"
        f"線分{pp}{pc}の長さを求めよ"
    )
    # 4点の並びと2本の弦の交わり方を図で示す（対応する三角形がどれかが見える）。
    figure_svg = two_chords_svg(
        pa, pb, pc, pd, pp, 40.0, 50.0,
        f"{pa_len}cm", f"{pb_len}cm", f"{pd_len}cm",
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "ratio_num": pa_len, "ratio_den": pd_len, "known_side": pb_len,
            "labels": pp + pa + pb + pc + pd,
        },
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure",
            labels=[f"{pa_len}cm", f"{pb_len}cm", f"{pd_len}cm", pa, pb, pc, pd, pp],
            elements=[VisualElement(kind="circle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.circle_similar_chord_length"),
    )
