"""三平方の定理・その逆まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l51/l52 の非 visual
find_value/knowledge セル群に対応する recipe を集約する。定理・その逆の想起は
既存 `math.recall_rule` ハブ（letter_expr.py）に topic を追加して対応するため、
ここには含まれない。
"""
from __future__ import annotations

from functools import lru_cache
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

def _is_triangle(a: int, b: int, c: int) -> bool:
    """3辺が三角形をつくるか（正で、いちばん長い辺が他の2辺の和より短い）。"""
    x, y, z = sorted((a, b, c))
    return x > 0 and x + y > z


# 有名な原始ピタゴラス数（g3_l52.find_value/knowledge の非退化構成に使う）。
_PRIMITIVE_TRIPLES: list[tuple[int, int, int]] = [
    (3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25),
    (20, 21, 29), (9, 40, 41), (12, 35, 37), (11, 60, 61),
]


def _squarefree_part(n: int) -> int:
    """n から平方因数を取り除いた残り（√n = k√m の m）。"""
    m, d = n, 2
    while d * d <= m:
        while m % (d * d) == 0:
            m //= d * d
        d += 1
    return m


@lru_cache(maxsize=16)
def usable_leg_pairs(leg_max: int, radicand_max: int) -> tuple[tuple[int, int], ...]:
    """斜辺が教材で扱える形になる（直角をはさむ2辺）の組。

    斜辺 √(a²+b²) は、整数になるか、a√b に直したとき**根号の中が小さい**もの
    （教科書に出るのは √2, √5, √13 くらいまで）に限る。前は 1〜60 を独立に
    引いていたので「55cm, 9cm → √3106」という、素因数分解もできない答えが
    出ていた。狭めたぶんは順序と言い回し・点名の軸で稼ぐ（FIXES.md の原則1）。
    """
    out: list[tuple[int, int]] = []
    for a in range(1, leg_max + 1):
        for b in range(1, leg_max + 1):
            if a == b:
                continue  # 直角二等辺は Lv3 の題材なのでここでは避ける
            if _squarefree_part(a * a + b * b) <= radicand_max:
                out.append((a, b))
    return tuple(out)


@lru_cache(maxsize=16)
def usable_hypotenuse_leg_pairs(
    side_max: int, radicand_max: int
) -> tuple[tuple[int, int], ...]:
    """残りの辺が教材で扱える形になる（斜辺, 直角をはさむ1辺）の組。"""
    out: list[tuple[int, int]] = []
    for c in range(2, side_max + 1):
        for b in range(1, c):
            if _squarefree_part(c * c - b * b) <= radicand_max:
                out.append((c, b))
    return tuple(out)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l51.find_value Lv1: 直角をはさむ2辺から斜辺の長さを求める
# ---------------------------------------------------------------------------
_PYTHAGOREAN_HYPOTENUSE_CONCEPTS = ["pythagorean.hypotenuse_from_legs"]


@register_recipe("math.pythagorean_hypotenuse", provides_concepts=_PYTHAGOREAN_HYPOTENUSE_CONCEPTS)
def pythagorean_hypotenuse_recipe(ctx: CellContext, rng: Rng) -> MR:
    """直角をはさむ2辺の長さから斜辺の長さを求める（g3_l51.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    pairs = usable_leg_pairs(int(p["leg_max"]), int(p["radicand_max"]))
    leg_a, leg_b = pairs[int(draw({"int_set": list(range(len(pairs)))}, rng))]
    # 言い回しを2つ持つ（辺の名前で問う形は教科書の定番で、点名の軸も乗る）。
    wording = str(draw(["plain", "named"], rng))
    # 図形の頂点はアルファベット順に名づける（実物は「正方形ABCD」「△ABC∽△DEF」）。
    # 無作為に引くと「正方形ERDJ」「三角形JQBと三角形CMH」になる。
    (v,) = _draw_named_figures([3], rng)
    pa, pb, pc = v

    solver = REGISTRY.solver("math.pythagorean_hypotenuse")
    sol = cast(Solution, solver(leg_a, leg_b))
    assert isinstance(sol.answer, SymbolicAnswer)

    if wording == "plain":
        statement = f"直角をはさむ2辺が {leg_a}cm, {leg_b}cm の直角三角形の斜辺の長さを求めよ"
    else:
        statement = (
            f"∠{pc}=90°の直角三角形{pa}{pb}{pc}で、{pa}{pc}={leg_a}cm, "
            f"{pb}{pc}={leg_b}cm である。斜辺{pa}{pb}の長さを求めよ"
        )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "leg_a": leg_a, "leg_b": leg_b,
            "wording": wording, "labels": pa + pb + pc,
        },
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.pythagorean_hypotenuse"),
    )


# ---------------------------------------------------------------------------
# g3_l51.knowledge Lv2: 直角の頂点の位置から斜辺を判別する
# ---------------------------------------------------------------------------
_IDENTIFY_HYPOTENUSE_CONCEPTS = ["pythagorean.identify_hypotenuse"]


@register_recipe("math.identify_hypotenuse", provides_concepts=_IDENTIFY_HYPOTENUSE_CONCEPTS)
def identify_hypotenuse_recipe(ctx: CellContext, rng: Rng) -> MR:
    """直角の頂点の位置から、斜辺がどの辺かを判別する（g3_l51.knowledge Lv2・answer-first）。"""
    # 頂点名をアルファベット順に直したぶん組合せが減ったので、**問いの言い回し**を
    # 軸に足す（実物も「斜辺はどの辺か」「いちばん長い辺はどれか」と言い分ける）。
    (v,) = _draw_named_figures([3], rng)
    pa, pb, pc = v
    labels = pa + pb + pc
    right_angle_index = int(draw({"int_set": [0, 1, 2]}, rng))
    phrasing = int(draw({"int_set": [0, 1, 2]}, rng))

    solver = REGISTRY.solver("math.identify_hypotenuse")
    sol = cast(Solution, solver(labels, right_angle_index))
    assert isinstance(sol.answer, ChoiceAnswer)
    right_angle_vertex = labels[right_angle_index]
    if phrasing == 0:
        statement = f"∠{right_angle_vertex}=90°の三角形{labels}で斜辺はどの辺か答えよ"
    elif phrasing == 1:
        statement = (
            f"三角形{labels}が∠{right_angle_vertex}=90°の直角三角形であるとき、"
            "斜辺はどの辺か答えよ"
        )
    else:
        statement = (
            f"直角三角形{labels}で直角の頂点が{right_angle_vertex}であるとき、"
            "斜辺はどの辺か答えよ"
        )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"labels": labels, "right_angle_index": right_angle_index,
                "phrasing": str(phrasing)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.identify_hypotenuse"),
    )


# ---------------------------------------------------------------------------
# g3_l52.find_value Lv2: 3辺の長さから三平方の定理の逆で直角三角形かを確かめる
# ---------------------------------------------------------------------------
_VERIFY_RIGHT_TRIANGLE_CONCEPTS = ["pythagorean.verify_right_triangle"]


@register_recipe(
    "math.verify_right_triangle_from_sides", provides_concepts=_VERIFY_RIGHT_TRIANGLE_CONCEPTS
)
def verify_right_triangle_from_sides_recipe(ctx: CellContext, rng: Rng) -> MR:
    """3辺の長さから三平方の定理の逆で直角三角形であるかを確かめる

    （g3_l52.find_value Lv2・answer-first）。is_right(bool)で真のピタゴラス数
    (原始三つ組×倍率)か、最大辺をずらした非直角三角形かを切り替える。
    """
    p = ctx.spec_level.params
    is_right = bool(draw([True, False], rng))
    for _ in range(200):
        triple = cast("tuple[int, int, int]", draw(_PRIMITIVE_TRIPLES, rng))
        k = int(draw(p["scale_domain"], rng))
        a, b, c = triple[0] * k, triple[1] * k, triple[2] * k
        if not is_right:
            delta = int(draw(p["delta_domain"], rng))
            c += delta
            # 三角形として成り立たない3辺（7・24・33 や 5・12・19）が出ていた。
            # 「直角三角形ではない」は正しくても、その三角形自体が存在しない。
            if not _is_triangle(a, b, c):
                continue
        solver = REGISTRY.solver("math.verify_right_triangle_from_sides")
        sol = cast(Solution, solver(a, b, c))
        assert isinstance(sol.answer, SymbolicAnswer)
        if sol.answer.display == ("直角三角形である" if is_right else "直角三角形ではない"):
            break
    else:
        raise ValueError("verify_right_triangle_from_sides_recipe: 有効な3辺を構成できず")

    statement = f"3辺の長さが {a}cm, {b}cm, {c}cm である三角形が直角三角形であるかどうかを、三平方の定理の逆を用いて確かめよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"side_a": a, "side_b": b, "side_c": c},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.verify_right_triangle_from_sides"),
    )


# ---------------------------------------------------------------------------
# g3_l52.knowledge Lv2: 3辺の関係から直角三角形かを判別する
# ---------------------------------------------------------------------------
_JUDGE_RIGHT_TRIANGLE_SIDES_CONCEPTS = ["pythagorean.judge_right_triangle"]


@register_recipe(
    "math.judge_right_triangle_from_three_sides",
    provides_concepts=_JUDGE_RIGHT_TRIANGLE_SIDES_CONCEPTS,
)
def judge_right_triangle_from_three_sides_recipe(ctx: CellContext, rng: Rng) -> MR:
    """3辺の長さから直角三角形かを判別する（g3_l52.knowledge Lv2・answer-first）。"""
    p = ctx.spec_level.params
    is_right = bool(draw([True, False], rng))
    expected = "直角三角形である" if is_right else "直角三角形ではない"
    for _ in range(200):
        triple = cast("tuple[int, int, int]", draw(_PRIMITIVE_TRIPLES, rng))
        k = int(draw(p["scale_domain"], rng))
        a, b, c = triple[0] * k, triple[1] * k, triple[2] * k
        if not is_right:
            delta = int(draw(p["delta_domain"], rng))
            c += delta
            # 三角形として成り立たない3辺（7・24・33 や 5・12・19）が出ていた。
            # 「直角三角形ではない」は正しくても、その三角形自体が存在しない。
            if not _is_triangle(a, b, c):
                continue
        solver = REGISTRY.solver("math.judge_right_triangle_from_three_sides")
        sol = cast(Solution, solver(a, b, c))
        assert isinstance(sol.answer, ChoiceAnswer)
        if sol.answer.correct == expected:
            break
    else:
        raise ValueError("judge_right_triangle_from_three_sides_recipe: 有効な3辺を構成できず")

    statement = f"3辺の長さが {a}cm, {b}cm, {c}cm である三角形は直角三角形であるといえるか答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"side_a": a, "side_b": b, "side_c": c},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_right_triangle_from_three_sides"),
    )
