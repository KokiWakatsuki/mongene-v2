"""相似比から面積比・表面積比・体積比を求めるまわりの recipe

（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l45/l46 の非 visual
find_value セル群に対応する recipe を集約する。面積比・体積比の想起は既存
`math.recall_rule` ハブに topic を追加して対応するため、ここには含まれない。
"""
from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.packs.math.visuals.solid import render_solid_svg
from engine.packs.math.visuals.similarity_figure import triangle_with_parallel_svg
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _draw_coprime_ratio(rng: Rng, domain: object, max_den: int) -> tuple[int, int]:
    """相似比 m:n（m<n・既約）を有界リトライで構成する。"""
    for _ in range(200):
        a = int(draw(domain, rng))
        b = int(draw([v for v in range(1, max_den + 1) if v != a], rng))
        m, n = min(a, b), max(a, b)
        if math.gcd(m, n) == 1:
            return m, n
    raise ValueError("_draw_coprime_ratio: 既約な相似比を構成できず")


# ---------------------------------------------------------------------------
# g3_l45.find_value Lv2: 相似比から面積比を求め、実際の面積を求める
# ---------------------------------------------------------------------------
_SIMILAR_AREA_RATIO_CONCEPTS = ["similarity.area_ratio"]


@register_recipe("math.similar_area_ratio", provides_concepts=_SIMILAR_AREA_RATIO_CONCEPTS)
def _similar_solids_svg(ratio_num: object, ratio_den: object) -> str:
    """相似な2つの立体を、相似比のとおりの大きさで並べた見取図。

    ★**「相似比 1:2 の2つの三角錐」を、形を見ないまま比だけで解くことになっていた。**
    立体の種類は場面によって変わるが、比を読み取ることがこの問題の中身なので、
    円錐の骨組みで代表させる（どの立体でも相似比と面積比・体積比の関係は同じ）。
    """
    k = float(ratio_den) / float(ratio_num)
    if k > 1:
        k = 1 / k
    return render_solid_svg(
        {"view": "sketch", "solid_kind": "similar_cones",
         "radius_px": 78.0, "height_px": 150.0, "ratio": max(k, 0.3)},
        draw=True,
    )


def similar_area_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比から面積比を求め、既知の面積から対応する面積を求める

    （g3_l45.find_value Lv2・answer-first）。
    """
    p = ctx.spec_level.params
    # 面積比は相似比の二乗なので、比を広げると答えが4桁になる（4:11・208cm² → 1573cm²）。
    # 小さいほうの面積は m² の倍数にとる（でないと大きいほうが分数になる）。
    area_max = int(p["area_max"])
    cands: list[tuple[int, int, int]] = []
    for m in range(1, int(p["ratio_max"]) + 1):
        for n in range(m + 1, int(p["ratio_max"]) + 1):
            if math.gcd(m, n) != 1:
                continue
            for j in range(1, area_max + 1):
                small, large = m * m * j, n * n * j
                if small < 4 or large > area_max:
                    continue
                cands.append((m, n, small))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    ratio_num, ratio_den, known_area = cands[idx]

    solver = REGISTRY.solver("math.similar_area_ratio")
    sol = cast(Solution, solver(ratio_num, ratio_den, known_area))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"相似比が {ratio_num}:{ratio_den} である2つの相似な三角形について、面積比を"
        f"求めよ。また、小さいほうの面積が {known_area}cm² のとき、大きいほうの面積を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ratio_num": ratio_num, "ratio_den": ratio_den, "known_area": known_area},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_area_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l46.find_value Lv2: 相似比から表面積比・体積比を直接求める
# ---------------------------------------------------------------------------
_SIMILAR_SOLID_RATIO_CONCEPTS = ["similarity.solid_surface_volume_ratio"]


@register_recipe(
    "math.similar_solid_surface_volume_ratio", provides_concepts=_SIMILAR_SOLID_RATIO_CONCEPTS
)
def similar_solid_surface_volume_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比から表面積比・体積比を直接求める（g3_l46.find_value Lv2・answer-first）。

    相似比は**小さい整数**に限る。前は `ratio_domain` が 1〜60 で「相似比 24:41 →
    体積比 13824:68921」が出ていた（体積比は相似比の三乗なので、比を広げると
    答えが一気に5桁になる）。狭めたぶんは**立体の種類と名前**という軸で稼ぐ
    （FIXES.md の原則1・2）——どちらも教科書にある言い方で、数は小さいまま。
    """
    p = ctx.spec_level.params
    ratio_num, ratio_den = _draw_coprime_ratio(rng, p["ratio_domain"], int(p["ratio_max"]))
    solid = str(draw(cast("list[str]", p["solid_set"]), rng))
    # 図形の頂点はアルファベット順に名づける（実物は「正方形ABCD」「△ABC∽△DEF」）。
    # 無作為に引くと「正方形ERDJ」「三角形JQBと三角形CMH」になる。
    f1, f2 = _draw_named_figures([1, 1], rng)
    ls, lt = f1, f2

    solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    sol = cast(Solution, solver(ratio_num, ratio_den))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図のように、相似な2つの{solid}{ls}, {lt}があり、相似比は {ratio_num}:{ratio_den} である。"
        f"{ls}と{lt}の表面積の比と体積の比をそれぞれ求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # 立体の種類と名前も dup_key に効かせる（params に無いと話の違いを見落とす）。
        params={
            "ratio_num": ratio_num, "ratio_den": ratio_den,
            "solid": solid, "labels": ls + lt,
        },
        given={"condition": statement},
        context_slots={"figure_svg": _similar_solids_svg(ratio_num, ratio_den)},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[],
            elements=[VisualElement(kind="solid_given", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.similar_solid_surface_volume_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l45.find_value Lv3: DE∥BC、AD:DBから三角形ADEと台形DBCEの面積比を求める
# ---------------------------------------------------------------------------
_SIMILAR_TRIANGLE_TRAPEZOID_AREA_RATIO_CONCEPTS = ["similarity.trapezoid_area_ratio"]


@register_recipe(
    "math.similar_triangle_trapezoid_area_ratio",
    provides_concepts=_SIMILAR_TRIANGLE_TRAPEZOID_AREA_RATIO_CONCEPTS,
)
def similar_triangle_trapezoid_area_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """DE∥BC、AD:DB=ad:dbのとき、三角形ADEと台形DBCEの面積比を求める

    （g3_l45.find_value Lv3・answer-first）。面積比が相似比の二乗という
    既存の性質（Lv2 math.similar_area_ratio と同じ関係）に、三角形ABC全体
    からADEを除いた残りが台形になるという合成を加えた多段構成。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    for _ in range(200):
        ad = int(draw(p["ratio_domain"], rng))
        db = int(draw(p["ratio_domain"], rng))
        if math.gcd(ad, db) == 1:
            break
    else:
        raise ValueError("similar_triangle_trapezoid_area_ratio_recipe: 有効な比を構成できず")

    solver = REGISTRY.solver("math.similar_triangle_trapezoid_area_ratio")
    sol = cast(Solution, solver(ad, db, pa + pb + pc + pd + pe))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}があり"
        f"{pd}{pe}∥{pb}{pc}、{pa}{pd}:{pd}{pb}={ad}:{db}である。三角形{pa}{pd}{pe}の"
        f"面積と、台形{pd}{pb}{pc}{pe}の面積の比を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "labels": pa + pb + pc + pd + pe},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_triangle_trapezoid_area_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l46.find_value Lv3: 体積比から相似比を逆算し表面積比を求める
# ---------------------------------------------------------------------------
_SIMILAR_SOLID_RATIO_FROM_VOLUME_CONCEPTS = ["similarity.solid_ratio_from_volume"]


@register_recipe(
    "math.similar_solid_ratio_from_volume",
    provides_concepts=_SIMILAR_SOLID_RATIO_FROM_VOLUME_CONCEPTS,
)
def similar_solid_ratio_from_volume_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似な2つの立体P, Qの体積から、相似比を逆算して表面積の比を求める

    （g3_l46.find_value Lv3・answer-first）。相似比 m:n（既約）をまず決め、
    体積比 m^3:n^3 にスケール k をかけた具体的な体積を提示する
    （見た目からすぐ相似比がわからないようにする）。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        m = int(draw(p["ratio_domain"], rng))
        n = int(draw(p["ratio_domain"], rng))
        if m != n and math.gcd(m, n) == 1:
            break
    else:
        raise ValueError("similar_solid_ratio_from_volume_recipe: 有効な相似比を構成できず")
    k = int(draw(p["scale_domain"], rng))
    vol_p, vol_q = m**3 * k, n**3 * k

    solver = REGISTRY.solver("math.similar_solid_ratio_from_volume")
    sol = cast(Solution, solver(vol_p, vol_q))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"相似な2つの円錐P, Qがあり、Pの体積は{vol_p}cm³、Qの体積は{vol_q}cm³である。"
        "PとQの表面積の比を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"vol_p": vol_p, "vol_q": vol_q},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.similar_solid_ratio_from_volume"),
    )


# ===========================================================================
# exam_l6（入試融合・相似と面積比／体積比）— C13
#
# 新しい数学は Lv4 の1本（`math.trapezoid_diagonal_area_ratios`）だけで、残りは
# 既存 solver の合成。recipe と checker が**同じ関数**（`EXAM_L6_SOLVERS`）を呼び、
# 独立性は「checker は params の場面数値だけから解き直す」ところに置く
# （word_problem_probability.py の SOLVE_BUILDERS と同じ設計）。
#
# proof Lv3（相似の記述証明）は proof form の frame がまだ無いため、ここには無い。
# ===========================================================================
def _draw_from(candidates: list[Any], rng: Rng) -> str:
    return str(candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))])


def _exam_l6_step(op: str, narration: str, display: str, srepr: str = "") -> Step:
    return Step(op=op, args=[], result_srepr=srepr, result_display=display, narration=narration)


def solve_exam_similar_solid_volume(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l6.find_value Lv3: 相似比と小さいほうの体積から、大きいほうの体積を求める。

    体積比そのものは既存 `math.similar_solid_surface_volume_ratio` が出す
    （相似比の三乗）。ここはその比と既知の体積から、もう一方の体積を求める合成。
    """
    m, n = int(numbers["ratio_num"]), int(numbers["ratio_den"])
    known = sympy.Integer(int(numbers["known_volume"]))
    ratio_solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    sol_ratio = cast(Solution, ratio_solver(m, n))
    assert isinstance(sol_ratio.answer, SymbolicAnswer)
    _, _, vol_num, vol_den = sympy.sympify(sol_ratio.answer.srepr)
    other = known * vol_den / vol_num
    if not sympy.Integer(other).equals(other):
        raise ValueError(f"大きいほうの体積が整数にならない: {other}")
    other = sympy.Integer(other)
    disp = f"{other}cm³"
    steps = [
        _exam_l6_step(
            "cube_ratio_for_volume",
            "相似な立体の体積の比は相似比の三乗に等しいことから、体積の比を求める。",
            f"{m}³:{n}³",
        ),
        _exam_l6_step(
            "apply_volume_ratio",
            "求めた体積の比と、わかっているほうの体積から、もう一方の体積を求める。",
            disp,
            sympy.srepr(other),
        ),
    ]
    return [Solution(answer=SymbolicAnswer(srepr=sympy.srepr(other), display=disp), steps=steps)]


def solve_exam_cone_split_volume_ratio(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l6.find_value Lv4: 円錐を底面に平行な平面で切ったときの、小円錐と円錐台の体積比。

    切り口から上の小円錐はもとの円錐と相似で、相似比は高さの比（上:全体）。体積比は
    その三乗（既存 `math.similar_solid_surface_volume_ratio`）で、円錐台はもとの円錐
    から小円錐を除いた残り——という**引き算の合成**が Lv4 の眼目。
    """
    upper, lower = int(numbers["upper_part"]), int(numbers["lower_part"])
    ratio_solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    sol_ratio = cast(Solution, ratio_solver(upper, upper + lower))
    assert isinstance(sol_ratio.answer, SymbolicAnswer)
    _, _, small, whole = sympy.sympify(sol_ratio.answer.srepr)
    frustum = whole - small
    g = sympy.gcd(small, frustum)
    ratio_num, ratio_den = small // g, frustum // g
    result = sympy.Tuple(ratio_num, ratio_den)
    disp = f"小さい円錐:円錐台 = {ratio_num}:{ratio_den}"
    steps = [
        _exam_l6_step(
            "identify_similar_cone",
            "底面に平行な平面で切ると、切り口から上の小さい円錐はもとの円錐と相似になる。"
            "その相似比は、高さの比（上の部分ともとの円錐全体の比）に等しい。",
            f"{upper}:{upper + lower}",
        ),
        _exam_l6_step(
            "cube_ratio_for_volume",
            "相似な立体の体積の比は相似比の三乗に等しいことから、"
            "小さい円錐ともとの円錐全体の体積の比を求める。",
            f"{small}:{whole}",
        ),
        _exam_l6_step(
            "subtract_for_frustum",
            "円錐台は、もとの円錐から小さい円錐を除いた残りなので、"
            "全体から小さい円錐の分をひいて、求める比とする。",
            disp,
            sympy.srepr(result),
        ),
    ]
    return [
        Solution(answer=SymbolicAnswer(srepr=sympy.srepr(result), display=disp), steps=steps)
    ]


def solve_exam_parallel_line_area_guided(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l6.word_problem Lv3: DE∥BC の三角形で (1)相似比 →(2)面積比 →(3)四角形の面積。

    (2)(3) は既存 `math.similar_area_ratio`（面積比＝相似比の二乗と、既知の面積から
    もう一方の面積）に委ね、(3) の値は既存
    `math.similar_triangle_trapezoid_area_ratio` が出す 三角形ADE:四角形DBCE の比
    でも検算する（二つの独立した経路が一致することを構成時に確かめる）。
    """
    ad, db = int(numbers["ad"]), int(numbers["db"])
    area_ade = sympy.Integer(int(numbers["area_ade"]))
    whole = ad + db

    ratio = sympy.Rational(ad, whole)
    ratio_num, ratio_den = ratio.p, ratio.q
    similar_ratio = sympy.Tuple(sympy.Integer(ratio_num), sympy.Integer(ratio_den))
    disp1 = f"三角形ADE:三角形ABC = {ratio_num}:{ratio_den}"
    sol1 = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(similar_ratio), display=disp1),
        steps=[
            _exam_l6_step(
                "convert_partial_to_whole_ratio",
                "DE と BC が平行なので、三角形ADEと三角形ABCは相似である。"
                "AD と DB の比から、AD と AB 全体の比になおして相似比とする。",
                disp1,
                sympy.srepr(similar_ratio),
            )
        ],
    )

    area_solver = REGISTRY.solver("math.similar_area_ratio")
    sol_area = cast(Solution, area_solver(ad, whole, area_ade))
    assert isinstance(sol_area.answer, SymbolicAnswer)
    area_num, area_den, area_abc = sympy.sympify(sol_area.answer.srepr)
    area_ratio = sympy.Tuple(area_num, area_den)
    disp2 = f"三角形ADE:三角形ABC = {area_num}:{area_den}"
    sol2 = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(area_ratio), display=disp2),
        steps=[
            _exam_l6_step(
                "square_similarity_ratio",
                "相似な図形の面積比は相似比の二乗に等しいことから、面積の比を求める。",
                disp2,
                sympy.srepr(area_ratio),
            )
        ],
    )

    quad = sympy.Integer(area_abc - area_ade)
    # 独立した経路（三角形ADE:四角形DBCE の比）でも同じ値になることを確かめる。
    trapezoid_solver = REGISTRY.solver("math.similar_triangle_trapezoid_area_ratio")
    sol_trapezoid = cast(Solution, trapezoid_solver(ad, db))
    assert isinstance(sol_trapezoid.answer, SymbolicAnswer)
    t_num, t_den = sympy.sympify(sol_trapezoid.answer.srepr)
    if quad != area_ade * t_den / t_num:
        raise ValueError("四角形の面積が2つの経路で一致しない")
    disp3 = f"{quad}cm²"
    sol3 = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(quad), display=disp3),
        steps=[
            _exam_l6_step(
                "compute_whole_area",
                "求めた面積の比と、わかっている三角形ADEの面積から、"
                "三角形ABC全体の面積を求める。",
                f"{quad + area_ade}cm²",
            ),
            _exam_l6_step(
                "subtract_inner_triangle",
                "四角形DBCEは、三角形ABC全体から三角形ADEを除いた残りなので、"
                "全体の面積から三角形ADEの面積をひいて求める。",
                disp3,
                sympy.srepr(quad),
            ),
        ],
    )
    return [sol1, sol2, sol3]


def solve_exam_trapezoid_diagonal_ratios(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l6.word_problem Lv4: 台形の対角線の交点まわりの面積比（誘導なし）。"""
    solver = REGISTRY.solver("math.trapezoid_diagonal_area_ratios")
    return [cast(Solution, solver(int(numbers["ad"]), int(numbers["bc"])))]


EXAM_L6_SOLVERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "similar_solid_volume": solve_exam_similar_solid_volume,
    "cone_split_volume_ratio": solve_exam_cone_split_volume_ratio,
    "parallel_line_area_guided": solve_exam_parallel_line_area_guided,
    "trapezoid_diagonal_ratios": solve_exam_trapezoid_diagonal_ratios,
}


def _exam_l6_mr(
    ctx: CellContext,
    *,
    kind: str,
    numbers: dict[str, Any],
    given: dict[str, str],
    ask_texts: tuple[str, ...],
    slots: dict[str, str] | None = None,
    figure_svg: str = "",
    figure_labels: list[str] | None = None,
) -> MR:
    """exam_l6 の4セル共通の MR 組み立て（小問数が level_sep の骨）。"""
    solutions = EXAM_L6_SOLVERS[kind](numbers)
    assert len(solutions) == len(ask_texts)
    context_slots = dict(slots or {})
    if len(ask_texts) == 1:
        # find_value（問い文は given.condition が持つ）は空文字を渡す＝スロットを作らない。
        if ask_texts[0]:
            context_slots["ask_value"] = ask_texts[0]
    else:
        for i, ask_text in enumerate(ask_texts):
            context_slots[f"ask_{i + 1}"] = ask_text
    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})", asked="value", answer=sol.answer, steps=sol.steps,
            concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
        )
        for i, sol in enumerate(solutions)
    ]
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # 答えは params に入れない（checker が場面の数値だけから解き直せるようにする）。
        params={"kind": kind, "numbers": {k: str(v) for k, v in numbers.items()},
                "slots": dict(slots or {})},
        given=given,
        context_slots=(
            {**context_slots, "figure_svg": figure_svg} if figure_svg else context_slots
        ),
        sub_questions=sub_questions,
        visual_plan=(
            VisualPlan(
                style="figure", labels=list(figure_labels or []),
                elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
            )
            if figure_svg
            else None
        ),
        provenance=Provenance(recipe=ctx.spec_level.recipe),
    )


_EXAM_L6_SOLID_VOLUME_CONCEPTS = ["exam.similar_solid_volume_from_ratio"]


@register_recipe(
    "math.exam_similar_solid_volume", provides_concepts=_EXAM_L6_SOLID_VOLUME_CONCEPTS
)
def exam_similar_solid_volume_recipe(ctx: CellContext, rng: Rng) -> MR:
    """相似比と小さいほうの体積から大きいほうの体積（exam_l6.find_value Lv3・answer-first）。"""
    p = ctx.spec_level.params
    m, n = _draw_coprime_ratio(rng, p["ratio_domain"], 6)
    # 大きいほうの体積が整数になるよう、小さいほうを m³ の倍数として構成する。
    known = int(draw(p["scale_domain"], rng)) * m**3
    solid = _draw_from(list(p["solid_candidates"]), rng)
    statement = (
        f"相似比が{m}:{n}である2つの相似な{solid}がある。"
        f"小さいほうの{solid}の体積が{known}cm³であるとき、"
        f"大きいほうの{solid}の体積を求めよ"
    )
    return _exam_l6_mr(
        ctx, kind="similar_solid_volume",
        numbers={"ratio_num": m, "ratio_den": n, "known_volume": known},
        given={"condition": statement}, ask_texts=("",), slots={"solid": solid},
    )


_EXAM_L6_CONE_SPLIT_CONCEPTS = ["exam.cone_split_volume_ratio"]


@register_recipe(
    "math.exam_cone_split_volume_ratio", provides_concepts=_EXAM_L6_CONE_SPLIT_CONCEPTS
)
def exam_cone_split_volume_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """円錐を平行な平面で切った小円錐と円錐台の体積比（exam_l6.find_value Lv4・answer-first）。"""
    p = ctx.spec_level.params
    upper = int(draw(p["upper_domain"], rng))
    lower = int(draw(p["lower_domain"], rng))
    # 高さ・底面の半径は答え（体積の比）に効かない surface（場面を具体にし、
    # 同じ比でも問題文が変わるようにする）。高さは分けた比で割り切れる値にする。
    height = (upper + lower) * int(draw(p["height_unit_domain"], rng))
    radius = int(draw(p["radius_domain"], rng))
    statement = (
        f"下の図のように、底面の半径が{radius}cm、高さが{height}cmの円錐がある。"
        f"この円錐を底面に平行な平面で切り、高さを上から{upper}:{lower}に分けた。"
        "切り口から上の小さい円錐と、下の円錐台の体積の比を求めよ"
    )
    # 切り口の位置は与えられた比のとおりに描く（図と本文が食い違わない）。
    figure_svg = render_solid_svg(
        {
            "view": "sketch", "solid_kind": "cut_cone",
            "radius_px": 95.0, "height_px": 180.0,
            "cut_ratio": upper / (upper + lower),
        },
        draw=True,
    )
    return _exam_l6_mr(
        ctx, kind="cone_split_volume_ratio",
        numbers={"upper_part": upper, "lower_part": lower, "height": height, "radius": radius},
        given={"condition": statement}, ask_texts=("",),
        figure_svg=figure_svg, figure_labels=[],
    )


_EXAM_L6_PARALLEL_AREA_CONCEPTS = ["exam.parallel_line_similar_area_guided"]


@register_recipe(
    "math.exam_parallel_line_area_guided", provides_concepts=_EXAM_L6_PARALLEL_AREA_CONCEPTS
)
def exam_parallel_line_area_guided_recipe(ctx: CellContext, rng: Rng) -> MR:
    """DE∥BC の相似 →面積比 →四角形の面積（exam_l6.word_problem Lv3・answer-first）。"""
    p = ctx.spec_level.params
    ad, db = _draw_coprime_ratio(rng, p["ratio_domain"], 6)
    # 四角形DBCEの面積が整数になるよう、三角形ADEの面積を AD² の倍数として構成する。
    area_ade = int(draw(p["scale_domain"], rng)) * ad**2
    statement = (
        f"下の図の三角形ABCで、辺AB上に点D、辺AC上に点Eをとり、DEとBCが平行になるように"
        f"する。AD:DB={ad}:{db}であり、三角形ADEの面積は{area_ade}cm²である。"
    )
    # 内分の比は与えられた比のとおりに取るので、図と本文が食い違わない。
    figure_svg = triangle_with_parallel_svg(
        "A", "B", "C", "D", "E", ad / (ad + db),
        side_labels=[("A", "D", str(ad)), ("D", "B", str(db))],
    )
    ask_texts = (
        "三角形ADEと三角形ABCの相似比を、最も簡単な整数の比で求めよ。",
        "三角形ADEと三角形ABCの面積比を求めよ。",
        "四角形DBCEの面積を求めよ。",
    )
    return _exam_l6_mr(
        ctx, kind="parallel_line_area_guided",
        numbers={"ad": ad, "db": db, "area_ade": area_ade},
        given={"scenario": statement}, ask_texts=ask_texts,
        figure_svg=figure_svg,
        figure_labels=[str(ad), str(db), "A", "B", "C", "D", "E"],
    )


_EXAM_L6_TRAPEZOID_CONCEPTS = ["exam.trapezoid_diagonal_area_ratios"]


@register_recipe(
    "math.exam_trapezoid_diagonal_ratios", provides_concepts=_EXAM_L6_TRAPEZOID_CONCEPTS
)
def exam_trapezoid_diagonal_ratios_recipe(ctx: CellContext, rng: Rng) -> MR:
    """台形の対角線の交点まわりの面積比（exam_l6.word_problem Lv4・answer-first）。"""
    p = ctx.spec_level.params
    ad, bc = _draw_coprime_ratio(rng, p["length_domain"], 15)
    # **高さは下底の 0.4〜1.2 倍**（「AD=1cm、BC=3cm、高さ9cm」は紙に描けない）。
    lo, hi = max(2, (2 * bc) // 5), max(3, (6 * bc) // 5)
    height = int(draw({"int_range": [lo, hi]}, rng))
    statement = (
        f"ADとBCが平行な台形ABCDがあり、AD={ad}cm、BC={bc}cm、高さは{height}cmである。"
        "対角線ACとBDの交点をPとする。"
    )
    ask_texts = (
        "三角形APDと三角形BPCの面積比を求め、さらに三角形APDの面積が"
        "三角形APBの面積の何倍になるかを求めよ。",
    )
    return _exam_l6_mr(
        ctx, kind="trapezoid_diagonal_ratios",
        numbers={"ad": ad, "bc": bc, "height": height},
        given={"scenario": statement}, ask_texts=ask_texts,
    )
