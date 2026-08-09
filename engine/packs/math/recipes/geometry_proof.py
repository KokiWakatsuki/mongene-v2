"""図形の証明セルの recipe（docs/proof_engine_design_2026-08-08.md）。

**問題を手で書かない。** 作図手順で図を組み（`geometry/construct.py`）、前向き推論で
導ける事実を飽和させ（`geometry/deduce.py`）、そこから Lv に合う結論を選んで
（`geometry/naturalness.py`）証明文を組む（`geometry/render_text.py`）。
だから「解き方が違う問題」は、**構成カタログと規則カタログを増やすこと**で増える。

構成カタログは params の `construction` で選ぶ。図そのものは
`geometry/constructions_*.py` にあり、`geometry/catalog.py` に名前で登録されている
——**この recipe に構成を書き足さない**（単元クラスタごとに別ファイルで進められる
ようにしてある）。パラメータ（角度・長さ）は rng で引き、**同じ手順を別のパラメータで
もう一度組んで**、図がたまたま見せている性質が無いかを確かめる
（`accidental_coincidences`）。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import (
    MR,
    CellContext,
    ProofAnswer,
    ProofStep,
    Provenance,
    Step,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.geometry import (  # noqa: F401  登録の副作用で構成が入る
    constructions_area,
    constructions_circle,
    constructions_congruence,
    constructions_parallelogram,
    constructions_right_triangle,
    constructions_similarity,
)
from engine.packs.math.geometry.catalog import CONSTRUCTIONS, topics_of
from engine.packs.math.geometry.construct import figure_quality_problems
from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import fact_text
from engine.packs.math.geometry.naturalness import accidental_coincidences, select_goal
from engine.packs.math.geometry.rules import RULES
from engine.packs.math.geometry.render_text import (
    build_proof_lines,
    compared_triangles,
    render_proof,
)
from engine.packs.math.visuals.geometry_figure import render_construction_svg

# family が topic_set を書かないときの既定（合同の単元群）。
DEFAULT_TOPIC_SET = "congruence"
TOPICS_CONGRUENCE = topics_of(DEFAULT_TOPIC_SET)


# 図をゆらすときのパラメータの動かし方（偶然の一致を見つけるため）。
_PERTURBATIONS = ({"base": 0.8, "angle": 1.15, "offset": 1.25}, {"base": 1.2, "angle": 0.85, "offset": 0.8})

_MAX_TRIES = 24


def build_problem(
    kind: str,
    params: dict[str, Any],
    *,
    level: int,
    topic_set: str = DEFAULT_TOPIC_SET,
    exclude_rules: tuple[str, ...] = (),
    depth: int | None = None,
    prefer: str | None = "tri_cong",
):
    """構成 → 推論 → 結論 → 証明 を一息に行う（recipe と checker が共有する単一の真実）。

    `exclude_rules` は**証明したい定理そのものを規則から外す**ために要る。
    「二等辺三角形の底角は等しいことを証明せよ」というセルで、その定理を規則として
    使えてしまうと1手で終わってしまい、証明にならない（循環）。単元ごとに、
    その単元で「これから示すこと」を外す。

    `topic_set` は**その単元で習っている定理の範囲**（`catalog.TOPIC_SETS`）。
    範囲外の定理を使う証明はここで落ちる。

    戻り値は (構成, 導出, 選ばれた結論, 証明の行) の組。質のフィルタに落ちたら None。
    """
    builder = CONSTRUCTIONS[kind]
    con = builder(params)
    rules = tuple(r for r in RULES if r.name not in exclude_rules)
    ded = saturate(
        con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes()
    )
    goal = select_goal(
        ded, level=level, allowed_topics=topics_of(topic_set), prefer=prefer, depth=depth
    )
    if goal is None:
        return None
    if figure_quality_problems(con):
        return None
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERTURBATIONS]
    if accidental_coincidences([con, *others], ded):
        return None
    return con, ded, goal, build_proof_lines(ded, goal.fact)


# **family が使う概念IDはすべてここに載せる。** 載せ忘れると lint R6 が落ち、
# check_cell は通るのに capabilities に出ない（台帳に載らない）——既知の罠。
_PROOF_CONCEPTS = [
    "congruence_proof.triangle_congruence",
    "congruence_proof.choose_condition",
    "congruence_proof.corresponding_parts",
    "isosceles_proof.property_by_congruence",
    # 横展開（構成カタログ＋規則カタログを増やして開く単元群）
    "isosceles_proof.condition_two_angles",
    "isosceles_proof.condition_construct",
    "equilateral_proof.property_and_condition",
    "equilateral_proof.construct",
    "right_triangle_proof.hypotenuse_angle",
    "right_triangle_proof.hypotenuse_side",
    "right_triangle_proof.construct",
    "parallelogram_proof.property_opposite_sides",
    "parallelogram_proof.property_diagonals",
    "parallelogram_proof.property_construct",
    "parallelogram_proof.condition_given",
    "parallelogram_proof.condition_choose",
    "parallelogram_proof.apply_condition",
    "parallelogram_proof.apply_via_congruence",
    "parallelogram_proof.apply_construct",
    "special_quad_proof.condition_given",
    "special_quad_proof.condition_choose",
    "similarity_proof.direct_condition",
    "similarity_proof.two_step",
    "similarity_proof.construct",
    "parallel_ratio_proof.ratio_from_similarity",
    "parallel_ratio_proof.converse",
    "midline_proof.direct",
    "midline_proof.auxiliary",
    "circle_proof.inscribed_direct",
    "circle_proof.two_step",
    "circle_proof.construct",
    "parallel_lines.judge_from_angle",
    "parallel_angle_property.rule_recall",
    "equal_area_proof.parallel_direct",
    "equal_area_proof.chain",
]


@register_recipe("math.geometry_proof", provides_concepts=_PROOF_CONCEPTS)
def geometry_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """図形の証明（推論器が問題そのものを作る・answer-first ではなく search-first）。

    質のフィルタに落ちる構成があるので、パラメータを引き直す有界リトライを回す。
    落ちた構成は「人が作らない図」なので、捨てるのが正しい。
    """
    p = ctx.spec_level.params
    kind = str(p["construction"])
    topic_set = str(p.get("topic_set") or DEFAULT_TOPIC_SET)
    level = int(ctx.level)
    for _ in range(_MAX_TRIES):
        params = {
            "base": int(draw(p["base_domain"], rng)) / 10.0,
            "angle": int(draw(p["angle_domain"], rng)),
            "offset": int(draw(p["offset_domain"], rng)) / 10.0,
        }
        built = build_problem(
            kind, params, level=level, topic_set=topic_set,
            exclude_rules=tuple(str(x) for x in p.get("exclude_rules", ())),
            depth=int(p["proof_depth"]) if p.get("proof_depth") is not None else None,
            prefer=str(p["prefer"]) if p.get("prefer") else None,
        )
        if built is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは定義域が悪いとき
        raise ValueError(f"{kind}: 質のフィルタを通る構成を引けなかった")

    con, ded, goal, lines = built
    targets = compared_triangles(ded, goal.fact)
    text = render_proof(lines, targets=targets)
    svg = render_construction_svg(
        {
            "coords": con.coords,
            "segments": con.segments,
            "circles": con.circles,
            "equal_groups": _equal_groups(con),
        }
    )
    # 「右の図で、AB ＝ AD、BC ＝ CD である」の形にする（条件を並べるだけだと
    # 文にならない）。構成が自前の言い方を持つならそれを使う（「平行四辺形ABCDで」）。
    premise_text = con.description or (
        "右の図で、" + "、".join(fact_text(f) for f in con.givens) + " である"
    )
    answer = ProofAnswer(
        text=text,
        lines=[
            ProofStep(
                claim=line.claim, reason=line.reason, number=line.number,
                refs=list(line.refs), op=line.op,
            )
            for line in lines
        ],
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=level,
        purpose=ctx.purpose, seed=0,
        params={
            "construction": kind,
            "numbers": {k: str(v) for k, v in params.items()},
            # checker が同じ条件で探索し直せるように、探索の条件も params に置く。
            "topic_set": topic_set,
            "exclude_rules": [str(x) for x in p.get("exclude_rules", ())],
            "proof_depth": int(p["proof_depth"]) if p.get("proof_depth") is not None else None,
            "prefer": str(p["prefer"]) if p.get("prefer") else None,
        },
        given={"premises": premise_text, "conclusion": fact_text(goal.fact)},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="proof_text", answer=answer,
                # **証明の各行がそのまま steps になる。** ここを空にすると op 列が消え、
                # Lv 間で fingerprint が同じになって level_sep が壊れる（eval が検出した）。
                # 採点の粒度としても、証明は「行ごとに何を根拠にしたか」が単位である。
                steps=_steps_from_lines(lines),
                concept_tags=list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=VisualPlan(
            style="plane",
            labels=sorted(con.coords),
            elements=[VisualElement(kind="figure_given", attrs={})],
        ),
        context_slots={"figure_svg": svg},
        provenance=Provenance(recipe="math.geometry_proof"),
    )


# 証明の行の種類ごとの言い方（解説・ヒントに出る）。
_STEP_NARRATION: dict[str, str] = {
    "cite_hypothesis": "仮定から、等しい辺（角）を書き出す。",
    "cite_common": "2つの三角形が共有している辺を確かめる。",
}


def _steps_from_lines(lines) -> list[Step]:
    """証明の行を採点粒度の Step にする（op 列＝level_sep の材料になる）。"""
    out: list[Step] = []
    for line in lines:
        narration = _STEP_NARRATION.get(line.op)
        if narration is None:
            if not line.reason:
                narration = "図から読み取る。"
            elif line.reason.endswith("だから"):
                # 定義を開く行（「O は AD の中点だから」）はそのまま続ける。
                narration = f"{line.reason}、等しい辺が分かる。"
            else:
                narration = f"{line.reason}ことから、次がいえる。"
        out.append(
            Step(op=line.op, args=[], result_srepr="", result_display=line.claim,
                 narration=narration)
        )
    return out


def _equal_groups(con: Construction) -> list[list[tuple[str, str]]]:
    """図に付ける等長の印。与えられた条件のうち、辺の等式だけを組にする。"""
    groups: list[list[tuple[str, str]]] = []
    for f in con.givens:
        if f.kind == "seg_eq" and f.args[0] != f.args[1]:
            groups.append([f.args[0], f.args[1]])
    return groups
