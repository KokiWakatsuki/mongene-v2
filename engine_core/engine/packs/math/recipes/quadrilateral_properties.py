"""平行四辺形・特別な平行四辺形・等積変形まわりの recipe（構成的生成・answer-first。

実装設計 §6.1）。

C9（g2 図形・平行と合同・三角形と四角形）クラスタのうち g2_l46/l47/l49/l50 の非
visual find_value/knowledge セル群に対応する recipe を集約する。
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
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.packs.math.visuals.quadrilateral_figure import (
    equal_area_transform_svg,
    parallelogram_svg,
    quadrilateral_with_diagonals_svg,
)
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g2_l46.find_value Lv1: 平行四辺形の対辺の長さ・対角の大きさを求める
# ---------------------------------------------------------------------------
_PARALLELOGRAM_OPPOSITE_CONCEPTS = ["parallelogram.opposite_properties"]


@register_recipe(
    "math.parallelogram_opposite_properties", provides_concepts=_PARALLELOGRAM_OPPOSITE_CONCEPTS
)
def parallelogram_opposite_properties_recipe(ctx: CellContext, rng: Rng) -> MR:
    """平行四辺形の対辺の長さ・対角の大きさを求める（g2_l46.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    # 実物は「平行四辺形ABCD」のように頂点をアルファベット順に名づける
    # （無作為に引くと「平行四辺形NKRF」になる）。
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    side_value = int(draw(p["side_domain"], rng))
    angle_value = int(draw(p["angle_domain"], rng))

    solver = REGISTRY.solver("math.parallelogram_opposite_properties")
    sol = cast(Solution, solver(side_value, angle_value))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図の平行四辺形{pa}{pb}{pc}{pd}で、{pa}{pb}={side_value}cm、"
        f"∠{pb}={angle_value}°であるとき、辺{pc}{pd}の長さと∠{pd}の大きさを求めよ"
    )
    # ★どの辺が対辺でどの角が対角かは、図があれば一目で分かる。
    # **求めるほうには名前を付けない**（本文に無い記号を図に足さない）。
    figure_svg = parallelogram_svg(
        pa + pb + pc + pd, f"{side_value}cm", f"{angle_value}°", "", ""
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"side_value": side_value, "angle_value": angle_value},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{side_value}cm", f"{angle_value}°", pa, pb, pc, pd],
            elements=[VisualElement(kind="quadrilateral", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.parallelogram_opposite_properties"),
    )


# ---------------------------------------------------------------------------
# g2_l47.knowledge Lv2: 条件からどの平行四辺形の条件によるかを判別する
# ---------------------------------------------------------------------------
_IDENTIFY_PARALLELOGRAM_CONDITION_CONCEPTS = ["parallelogram.identify_condition"]

_PARALLELOGRAM_CONDITION_TEXT: dict[str, str] = {
    "opposite_sides_parallel": "{a}{b}∥{d}{c} かつ {b}{c}∥{a}{d}が成り立っている",
    "opposite_sides_equal": "{a}{b}={d}{c} かつ {b}{c}={a}{d}が成り立っている",
    "opposite_angles_equal": "∠{a}=∠{c} かつ ∠{b}=∠{d}が成り立っている",
    "diagonals_bisect": "対角線{a}{c}と{b}{d}の交点が、それぞれの中点になっている",
    "one_pair_parallel_and_equal": "{a}{b}={d}{c} かつ {a}{b}∥{d}{c}が成り立っている",
}


@register_recipe(
    "math.identify_parallelogram_condition",
    provides_concepts=_IDENTIFY_PARALLELOGRAM_CONDITION_CONCEPTS,
)
def identify_parallelogram_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """示されている条件が平行四辺形になるための5条件のうちどれによるかを判別する

    （g2_l47.knowledge Lv2・answer-first）。
    """
    condition_key = str(draw(list(_PARALLELOGRAM_CONDITION_TEXT.keys()), rng))
    # 実物は「平行四辺形ABCD」のように頂点をアルファベット順に名づける
    # （無作為に引くと「平行四辺形NKRF」になる）。
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    condition_text = _PARALLELOGRAM_CONDITION_TEXT[condition_key].format(a=pa, b=pb, c=pc, d=pd)
    statement = (
        f"四角形{pa}{pb}{pc}{pd}で、{condition_text}とき、"
        "この四角形が平行四辺形といえるのはどの条件によるか答えよ"
    )

    solver = REGISTRY.solver("math.identify_parallelogram_condition")
    sol = cast(Solution, solver(condition_key))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"condition_key": condition_key, "a": pa, "b": pb, "c": pc, "d": pd},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.identify_parallelogram_condition"),
    )


# ---------------------------------------------------------------------------
# g2_l49.find_value Lv1: 特別な平行四辺形の対角線の性質から辺・角を求める
# ---------------------------------------------------------------------------
_SPECIAL_PARALLELOGRAM_DIAGONAL_CONCEPTS = ["special_parallelogram.diagonal_value"]


@register_recipe(
    "math.special_parallelogram_diagonal_value",
    provides_concepts=_SPECIAL_PARALLELOGRAM_DIAGONAL_CONCEPTS,
)
def special_parallelogram_diagonal_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """特別な平行四辺形の対角線の性質から、辺の長さ・角の大きさを求める

    （g2_l49.find_value Lv1・answer-first）。
    """
    p = ctx.spec_level.params
    shape = str(draw(["rectangle", "square", "rhombus"], rng))
    # 実物は「平行四辺形ABCD」のように頂点をアルファベット順に名づける
    # （無作為に引くと「平行四辺形NKRF」になる）。
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v
    value = int(draw(p["value_domain"], rng))

    solver = REGISTRY.solver("math.special_parallelogram_diagonal_value")
    sol = cast(Solution, solver(shape, value))
    assert isinstance(sol.answer, SymbolicAnswer)

    shape_disp = {"rectangle": "長方形", "square": "正方形", "rhombus": "ひし形"}[shape]
    if shape == "rhombus":
        statement = (
            f"下の図の{shape_disp}{pa}{pb}{pc}{pd}で対角線{pa}{pc}と{pb}{pd}の交点をOとする。"
            f"{pa}{pc}={value}cm のとき、線分O{pa}の長さと∠{pa}O{pb}の大きさを求めよ"
        )
    else:
        statement = (
            f"下の図の{shape_disp}{pa}{pb}{pc}{pd}で対角線{pa}{pc}と{pb}{pd}の交点をOとする。"
            f"{pa}{pc}={value}cm のとき、線分O{pb}の長さを求めよ"
        )
    # 対角線の交点がどこかを図で示す（ひし形は垂直に交わることが図で見える）。
    figure_svg = quadrilateral_with_diagonals_svg(
        pa + pb + pc + pd, "O", kind=shape, diagonal_label=f"{value}cm"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"shape": shape, "value": value, "labels": pa + pb + pc + pd},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{value}cm", pa, pb, pc, pd, "O"],
            elements=[VisualElement(kind="quadrilateral", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.special_parallelogram_diagonal_value"),
    )


# ---------------------------------------------------------------------------
# g2_l49.knowledge Lv2: 対角線の条件からどの四角形になるかを判別する
# ---------------------------------------------------------------------------
_CLASSIFY_QUADRILATERAL_CONCEPTS = ["quadrilateral.classify_from_diagonal"]


@register_recipe(
    "math.classify_quadrilateral_from_diagonal_condition",
    provides_concepts=_CLASSIFY_QUADRILATERAL_CONCEPTS,
)
def classify_quadrilateral_from_diagonal_condition_recipe(ctx: CellContext, rng: Rng) -> MR:
    """対角線の条件（等しい／垂直に交わる）から、平行四辺形がどんな四角形になるかを判別する

    （g2_l49.knowledge Lv2・answer-first）。
    """
    equal = bool(draw([True, False], rng))
    perpendicular = bool(draw([True, False], rng))
    # 実物は「平行四辺形ABCD」のように頂点をアルファベット順に名づける
    # （無作為に引くと「平行四辺形NKRF」になる）。
    (v,) = _draw_named_figures([4], rng)
    pa, pb, pc, pd = v

    clauses = []
    if equal:
        clauses.append("対角線の長さが等しく")
    else:
        clauses.append("対角線の長さは異なるが")
    if perpendicular:
        clauses.append("垂直に交わる")
    else:
        clauses.append("垂直には交わらない")
    condition_text = "、".join(clauses)
    statement = (
        f"平行四辺形{pa}{pb}{pc}{pd}で、{condition_text}とき、"
        "この四角形はどんな四角形になるか答えよ"
    )

    solver = REGISTRY.solver("math.classify_quadrilateral_from_diagonal_condition")
    sol = cast(Solution, solver(str(equal), str(perpendicular)))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "equal": str(equal), "perpendicular": str(perpendicular),
            "a": pa, "b": pb, "c": pc, "d": pd,
        },
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.classify_quadrilateral_from_diagonal_condition"),
    )


# ---------------------------------------------------------------------------
# g2_l50.find_value Lv2: 等積変形でつくった三角形の面積を求める
# ---------------------------------------------------------------------------
_EQUAL_AREA_TRANSFORM_CONCEPTS = ["equal_area.transform_value"]


@register_recipe(
    "math.equal_area_transform_value", provides_concepts=_EQUAL_AREA_TRANSFORM_CONCEPTS
)
def equal_area_transform_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """四角形と等積変形でつくった三角形の面積を求める（g2_l50.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    area_value = int(draw(p["area_domain"], rng))

    solver = REGISTRY.solver("math.equal_area_transform_value")
    sol = cast(Solution, solver(area_value))
    assert isinstance(sol.answer, SymbolicAnswer)

    # **「面積の等しい三角形をつくったとき」と書いてはいけない。**
    # 等積であることこそ生徒が導く結論なのに、問題文がそれを先に言ってしまい、
    # 「四角形の面積が424cm² ならば三角形の面積を求めよ」＝答えを本文が告げていた。
    # 実物は作図の手順だけを述べ、等積になる理由（底辺共通・高さ等しい）を問う。
    statement = (
        f"下の図の四角形{pa}{pb}{pc}{pd}で、頂点{pd}を通り対角線{pa}{pc}に平行な直線をひき、"
        f"辺{pb}{pc}の延長との交点を{pe}とする。"
        f"四角形{pa}{pb}{pc}{pd}の面積が{area_value}cm²であるとき、"
        f"三角形{pa}{pb}{pe}の面積を求めよ"
    )
    # 「辺MNの延長」がどちらへ伸びるのかは、ことばだけだと読み取りにくい。
    figure_svg = equal_area_transform_svg(pa + pb + pc + pd, pe, "")

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"area_value": area_value, "labels": pa + pb + pc + pd + pe},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[pa, pb, pc, pd, pe],
            elements=[VisualElement(kind="quadrilateral", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.equal_area_transform_value"),
    )
