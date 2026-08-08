"""図形の証明セルの recipe（docs/proof_engine_design_2026-08-08.md）。

**問題を手で書かない。** 作図手順で図を組み（`geometry/construct.py`）、前向き推論で
導ける事実を飽和させ（`geometry/deduce.py`）、そこから Lv に合う結論を選んで
（`geometry/naturalness.py`）証明文を組む（`geometry/render_text.py`）。
だから「解き方が違う問題」は、**構成カタログと規則カタログを増やすこと**で増える。

構成カタログは params の `construction` で選ぶ。パラメータ（角度・長さ）は rng で
引き、**同じ手順を別のパラメータでもう一度組んで**、図がたまたま見せている性質が
無いかを確かめる（`accidental_coincidences`）。
"""
from __future__ import annotations

from collections.abc import Callable
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
from engine.packs.math.geometry.construct import Construction, figure_quality_problems
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

# 単元ごとに「使ってよい定理」を宣言する（質のフィルタが単元違いの証明を弾く）。
TOPICS_CONGRUENCE = frozenset(
    {"congruence", "congruence_property", "isosceles", "midpoint", "angle", "parallel"}
)


def _kite(p: dict[str, Any]) -> Construction:
    """たこ形（AB=AD・CB=CD）に対角線 AC を引いた図。SSS の定番。"""
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", float(p["base"]), 0.0)
    c.point_on_circle("D", "A", "B", angle_deg=float(p["angle"]))
    c.point_on_perpendicular_bisector("C", "B", "D", offset=-float(p["offset"]))
    for x, y in (("A", "B"), ("A", "D"), ("B", "C"), ("D", "C")):
        c.connect(x, y)
    c.connect("A", "C", shared=True)
    return c


def _x_shape(p: dict[str, Any]) -> Construction:
    """2本の線分が中点で交わる X 字型。中点 → 対頂角 → SAS。"""
    c = Construction()
    c.free_point("O", 0.0, 0.0)
    c.free_point("A", -float(p["base"]), float(p["angle"]) / 40.0)
    c.free_point("B", -float(p["offset"]) / 2.0, -2.0)
    c.reflected_point("D", "A", "O")
    c.reflected_point("C", "B", "O")
    for x, y in (("A", "D"), ("B", "C"), ("A", "B"), ("C", "D")):
        c.connect(x, y)
    return c


def _parallelogram(p: dict[str, Any]) -> Construction:
    """平行四辺形に対角線を引いた図。"""
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", float(p["base"]), 0.0)
    c.free_point("C", float(p["base"]) + float(p["offset"]) / 3.0, float(p["angle"]) / 25.0)
    c.translated_point("D", "A", "B", "C")
    for x, y in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        c.connect(x, y)
    c.connect("A", "C", shared=True)
    c.description = "平行四辺形ABCDで、対角線ACを引いた"
    return c


def _isosceles_with_median(p: dict[str, Any]) -> Construction:
    """二等辺三角形 ABC（AB=AC）に、底辺 BC の中点 M を結んだ図。

    「底角が等しい」を**証明する**ための図。だからこのセルでは、その定理を規則から
    外して探索する（外さないと1手で終わってしまう）。
    """
    c = Construction()
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]), 0.0)
    c.point_on_perpendicular_bisector("A", "B", "C", offset=-float(p["offset"]) - 1.0)
    c.midpoint_of("M", "B", "C")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("A", "M")):
        c.connect(x, y)
    c.connect("A", "M", shared=True)
    return c


CONSTRUCTIONS: dict[str, Callable[[dict[str, Any]], Construction]] = {
    "isosceles_median": _isosceles_with_median,
    "kite": _kite,
    "x_shape": _x_shape,
    "parallelogram": _parallelogram,
}

# 図をゆらすときのパラメータの動かし方（偶然の一致を見つけるため）。
_PERTURBATIONS = ({"base": 0.8, "angle": 1.15, "offset": 1.25}, {"base": 1.2, "angle": 0.85, "offset": 0.8})

_MAX_TRIES = 24


def build_problem(
    kind: str,
    params: dict[str, Any],
    *,
    level: int,
    topics: frozenset[str],
    exclude_rules: tuple[str, ...] = (),
    depth: int | None = None,
    prefer: str | None = "tri_cong",
):
    """構成 → 推論 → 結論 → 証明 を一息に行う（recipe と checker が共有する単一の真実）。

    `exclude_rules` は**証明したい定理そのものを規則から外す**ために要る。
    「二等辺三角形の底角は等しいことを証明せよ」というセルで、その定理を規則として
    使えてしまうと1手で終わってしまい、証明にならない（循環）。単元ごとに、
    その単元で「これから示すこと」を外す。

    戻り値は (構成, 導出, 選ばれた結論, 証明の行) の組。質のフィルタに落ちたら None。
    """
    builder = CONSTRUCTIONS[kind]
    con = builder(params)
    rules = tuple(r for r in RULES if r.name not in exclude_rules)
    ded = saturate(con.points, frozenset(con.facts), rules=rules)
    goal = select_goal(ded, level=level, allowed_topics=topics, prefer=prefer, depth=depth)
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
]


@register_recipe("math.geometry_proof", provides_concepts=_PROOF_CONCEPTS)
def geometry_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """図形の証明（推論器が問題そのものを作る・answer-first ではなく search-first）。

    質のフィルタに落ちる構成があるので、パラメータを引き直す有界リトライを回す。
    落ちた構成は「人が作らない図」なので、捨てるのが正しい。
    """
    p = ctx.spec_level.params
    kind = str(p["construction"])
    level = int(ctx.level)
    for _ in range(_MAX_TRIES):
        params = {
            "base": int(draw(p["base_domain"], rng)) / 10.0,
            "angle": int(draw(p["angle_domain"], rng)),
            "offset": int(draw(p["offset_domain"], rng)) / 10.0,
        }
        built = build_problem(
            kind, params, level=level, topics=TOPICS_CONGRUENCE,
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
