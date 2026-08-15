"""C8 g1 空間図形クラスタ（g1_l47/l48 の knowledge Lv2）の recipe（構成的生成・§6.1）。

用語想起（g1_l47/l48/l49/l50 Lv1）と規則想起（g1_l53 Lv1）は既存ハブ
`math.term_recall` / `math.recall_rule` に domain/topic を足して賄うため、ここには
含まれない（新設 recipe は判別型の2つだけ）。

いずれも answer-first：先に「主張が正しいか」「どの辺・面を問うか」を引いてから、
独立ソルバに同じ入力を渡して判定させ（double-solve）、答えの ChoiceAnswer を得る。
1レベル＝1 signature＝1 op 列なので、同一レベル内の mode は op 列を揃えてある
（G-FP 安定・BRIEF の失敗パターン1）。
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
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.recipes.polynomial import _domain_candidates
from engine.packs.math.solvers.g1_space import (
    CUBOID_EDGE_INDICES,
    CUBOID_FACE_INDICES,
    ELEMENT_LABEL_JA,
    ELEMENT_QUANTITIES,
    SOLID_LABEL_JA,
    true_element_count,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# **多角形の名前は漢数字**（実物の教材は「八角形」と書き、「8角形」とは書かない）。
_POLYGON_NAME_JP = {
    3: "三角形", 4: "四角形", 5: "五角形", 6: "六角形", 7: "七角形", 8: "八角形",
    9: "九角形", 10: "十角形", 11: "十一角形", 12: "十二角形",
}


def _polygon_name_jp(n: int) -> str:
    if n not in _POLYGON_NAME_JP:
        raise ValueError(f"多角形の漢数字名が未登録: {n}")
    return _POLYGON_NAME_JP[n]


# ---------------------------------------------------------------------------
# g1_l47.knowledge Lv2: 面・辺・頂点の数／正多面体の条件についての主張を判別する
# ---------------------------------------------------------------------------
_POLYHEDRON_CLAIM_CONCEPTS = ["polyhedron.judge_claim"]


@register_recipe("math.judge_polyhedron_claim", provides_concepts=_POLYHEDRON_CLAIM_CONCEPTS)
def judge_polyhedron_claim(ctx: CellContext, rng: Rng) -> MR:
    """多面体についての主張（面辺頂点の数／正多面体の条件）の正誤を判別する。

    （g1_l47.knowledge Lv2・answer-first）。mode で題材が変わるが op 列は共通
    [read_claim, judge_claim]（G-FP 安定）。答えは digit-free の ChoiceAnswer。
    """
    p = ctx.spec_level.params
    mode = str(draw(cast("list[str]", p["mode_set"]), rng))

    if mode == "element_count":
        n = int(draw(p["base_sides_domain"], rng))
        solid_type = str(draw(["prism", "pyramid"], rng))
        quantity = str(draw(list(ELEMENT_QUANTITIES), rng))
        truth = int(draw({"int_set": [0, 1]}, rng)) == 1
        true_value = true_element_count(n, solid_type, quantity)
        if truth:
            candidate = true_value
        else:
            # 真の値からずらす（0 は除外済み＝必ず真の値と異なる・退化防止）。
            offsets = [
                int(d)
                for d in cast("list[int]", p["offset_set"])
                if d != 0 and true_value + int(d) >= 1
            ]
            candidate = true_value + int(draw(offsets, rng))
        # **多角形の名前は漢数字**（「底面が8角形の角柱」は実物に無い書き方）。
        statement = (
            f"底面が{_polygon_name_jp(n)}の{SOLID_LABEL_JA[solid_type]}について、"
            f"{ELEMENT_LABEL_JA[quantity]}の数は{candidate}である"
        )
        solver = REGISTRY.solver("math.judge_polyhedron_element_count")
        sol = cast(Solution, solver(n, solid_type, quantity, candidate))
        expected = "正しい" if truth else "誤り"
        params: dict[str, object] = {
            "mode": mode,
            "n": str(n),
            "solid_type": solid_type,
            "quantity": quantity,
            "candidate": str(candidate),
            "statement": statement,
        }
    elif mode == "regular_condition":
        # answer-first: 先に正誤を引き、その正誤になる (m, k) の組だけから引く。
        # 素直に m,k を引くと「角の和が360°未満」になる組が 36 通り中 5 通りしかなく、
        # 答えが「誤り」に潰れる（ゲートは退化を素通りするので構成側で防ぐ）。
        truth = int(draw({"int_set": [0, 1]}, rng)) == 1
        pairs = [
            (mm, kk)
            for mm in _domain_candidates(cast("dict[str, object]", p["shape_sides_domain"]))
            for kk in _domain_candidates(cast("dict[str, object]", p["vertex_count_domain"]))
            if ((mm - 2) * 180 * kk < 360 * mm) == truth
        ]
        idx = int(draw({"int_set": list(range(len(pairs)))}, rng))
        m, k = pairs[idx]
        (vertex,) = _draw_named_figures([1], rng)
        statement = (
            f"1つの頂点{vertex}のまわりに正{_polygon_name_jp(m)}の面が{k}つ"
            "集まるようにすれば、すきまなく折り曲げて正多面体を組み立てることができる"
        )
        solver = REGISTRY.solver("math.judge_regular_polyhedron_condition")
        sol = cast(Solution, solver(m, k))
        expected = "正しい" if (m - 2) * 180 * k < 360 * m else "誤り"
        params = {
            "mode": mode,
            "shape_sides": str(m),
            "count_at_vertex": str(k),
            "vertex": vertex,
            "statement": statement,
        }
    else:  # pragma: no cover - spec で mode_set を縛るため到達しない
        raise ValueError(f"未知の mode: {mode!r}")

    assert isinstance(sol.answer, ChoiceAnswer)
    assert sol.answer.correct == expected, f"double-solve 不一致: {expected} != {sol.answer.correct}"
    assert [s.op for s in sol.steps] == ["read_claim", "judge_claim"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_polyhedron_claim"),
    )


# ---------------------------------------------------------------------------
# g1_l48.knowledge Lv2: 直方体の 辺と辺／辺と面 の位置関係を判別する
# ---------------------------------------------------------------------------
_SOLID_POSITION_CONCEPTS = ["spatial_position.judge_relation"]


@register_recipe("math.judge_solid_position", provides_concepts=_SOLID_POSITION_CONCEPTS)
def judge_solid_position(ctx: CellContext, rng: Rng) -> MR:
    """直方体の 辺と辺／辺と面 の位置関係を判別する（g1_l48.knowledge Lv2・answer-first）。

    頂点ラベル8文字を引き（底面4つ→上面4つの順にそろえるため昇順に並べる）、その
    ラベルで辺・面の名前を組み立てる。ラベルは本文に出るので params に必ず含める。
    mode で対象（辺と辺／辺と面）が変わるが op 列は共通（G-FP 安定）。
    """
    p = ctx.spec_level.params
    mode = str(draw(cast("list[str]", p["mode_set"]), rng))
    # 立体の頂点はアルファベット順（実物は「立方体ABCD-EFGH」）。
    (labels,) = _draw_named_figures([8], rng)
    solid_name = f"{labels[:4]}-{labels[4:]}"
    edges = [labels[i] + labels[j] for i, j in CUBOID_EDGE_INDICES]

    if mode == "edge_edge":
        first = str(draw(edges, rng))
        second = str(draw([e for e in edges if e != first], rng))
        statement = f"直方体{solid_name}で、辺{first}と辺{second}の位置関係"
    elif mode == "edge_face":
        first = str(draw(edges, rng))
        faces = ["".join(labels[i] for i in f) for f in CUBOID_FACE_INDICES]
        second = str(draw(faces, rng))
        statement = f"直方体{solid_name}で、辺{first}と面{second}の位置関係"
    else:  # pragma: no cover - spec で mode_set を縛るため到達しない
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.judge_solid_position_relation")
    sol = cast(Solution, solver(labels, mode, first, second))
    assert isinstance(sol.answer, ChoiceAnswer)
    assert sol.answer.correct not in sol.answer.distractors
    assert [s.op for s in sol.steps] == ["read_position_query", "classify_relation"]

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "mode": mode, "labels": labels, "first": first, "second": second,
            "statement": statement,
        },
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_solid_position"),
    )


__all__ = ["judge_polyhedron_claim", "judge_solid_position"]
