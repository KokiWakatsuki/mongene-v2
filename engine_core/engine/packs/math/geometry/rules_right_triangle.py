"""直角三角形・正三角形・二等辺になるための条件の規則カタログ。

対象単元: g2_l42（二等辺になるための条件）・g2_l43（正三角形）・g2_l45（直角三角形の
合同条件）。

**書き方は `rules_congruence.py` に合わせる。** `reason` は教科書の言い回しに固定する
（「直角三角形の斜辺と1つの鋭角がそれぞれ等しい」など）。

規則の探索の仕方について。合同条件（`rules_congruence.py`）は三角形の組を総当たり
するが、ここの3つは**前提になる事実の側から引く**。直角三角形の合同条件は「直角が
どこにあるか」で三角形が決まってしまう（直角の頂点が最後・斜辺がその対辺）ので、
`right_angle` の事実を2つ選べば比べる三角形の候補は4通りしかない。内角の和の規則も
同じで、角の等式を2つ選べば三角形が決まる。点が増えても速度が落ちないのはこのため
——直角三角形の図は点が5個6個になりやすい。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    ang,
    ang_eq,
    right_angle,
    seg,
    seg_eq,
    tri_cong,
)
from engine.packs.math.geometry.rule_base import Derivation, Rule


# ---------------------------------------------------------------------------
# 直角三角形の合同条件（2つ）
# ---------------------------------------------------------------------------
def _right_triangles(facts: frozenset[Fact]) -> list[tuple[tuple[Point, Point, Point], Fact]]:
    """直角の事実から「**直角の頂点を最後に置いた**三角形」を列挙する。

    ∠ACB＝90° なら、比べる三角形は (A, B, C) か (B, A, C) の2通り
    ——どちらも斜辺は AB（直角の対辺）で、直角の頂点は C である。
    2通り出すのは「斜辺の両端のどちらを鋭角の頂点に選ぶか」の違いで、
    斜辺と1つの鋭角の条件はこの選び方で対応が変わる。
    """
    out: list[tuple[tuple[Point, Point, Point], Fact]] = []
    for f in facts:
        if f.kind != "right_angle":
            continue
        v, x, y = f.args[0]
        out.append(((x, y, v), f))
        out.append(((y, x, v), f))
    return out


def _apply_rha(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """斜辺と1つの鋭角がそれぞれ等しい。

    t = (鋭角の頂点, 斜辺のもう一方の端, 直角の頂点) の形で持つので、
    斜辺は t[0]t[1]、等しい鋭角は t[0] の角になる。
    """
    for (t1, r1), (t2, r2) in itertools.combinations(_right_triangles(facts), 2):
        if t1 == t2:
            continue
        premises = (
            r1,
            r2,
            seg_eq(seg(t1[0], t1[1]), seg(t2[0], t2[1])),
            ang_eq(ang(t1[0], t1[1], t1[2]), ang(t2[0], t2[1], t2[2])),
        )
        if all(p in facts for p in premises):
            yield tri_cong(t1, t2), premises


def _apply_rhs(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """斜辺と他の1辺がそれぞれ等しい。

    t[0]t[1] が斜辺、t[1]t[2] が「他の1辺」（直角をはさむ辺の一方）。
    """
    for (t1, r1), (t2, r2) in itertools.combinations(_right_triangles(facts), 2):
        if t1 == t2:
            continue
        premises = (
            r1,
            r2,
            seg_eq(seg(t1[0], t1[1]), seg(t2[0], t2[1])),
            seg_eq(seg(t1[1], t1[2]), seg(t2[1], t2[2])),
        )
        if premises[3].args[0] == premises[3].args[1]:
            continue  # 共通の辺は「他の1辺がそれぞれ等しい」にあたらない
        if all(p in facts for p in premises):
            yield tri_cong(t1, t2), premises


# ---------------------------------------------------------------------------
# 三角形の内角の和（2組の角が等しければ、残りの1組も等しい）
# ---------------------------------------------------------------------------
def _apply_third_angles(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """2つの三角形で2組の角がそれぞれ等しければ、残りの1組も等しい。

    中学の合同条件に「2角とその間にない辺」は無いので、教科書はこの規則を
    「三角形の内角の和は180°だから」と書いて**残りの角を作ってから**
    「1組の辺とその両端の角」に持ち込む。二等辺三角形になるための条件の証明が
    まさにこの形である。

    角の等式を2つ選べば三角形の3頂点が決まる（角の頂点と2つの腕で3点）ので、
    三角形の組を総当たりせずに、**角の等式の組から引く**。
    """
    collinear_triples = {frozenset(f.args) for f in facts if f.kind == "collinear"}
    eqs = [f for f in facts if f.kind == "ang_eq" and f.args[0] != f.args[1]]
    for f, g in itertools.combinations(eqs, 2):
        for a1, a2 in (f.args, (f.args[1], f.args[0])):
            for b1, b2 in (g.args, (g.args[1], g.args[0])):
                # 2つの角が同じ三角形の別の頂点の角か（頂点＋2つの腕＝3頂点）。
                t1, t2 = frozenset(a1), frozenset(b1)
                u1, u2 = frozenset(a2), frozenset(b2)
                if t1 != t2 or u1 != u2 or a1[0] == b1[0] or a2[0] == b2[0]:
                    continue
                # **「2つの三角形で」なので、同じ三角形の中で使ってはいけない。**
                # 正三角形（AB＝AC＝BC）で ∠ABC＝∠ACB と ∠BAC＝∠ACB から
                # ∠BAC＝∠ABC を出すのに当たっていた——これは推移律であって
                # 内角の和とは関係が無く、「三角形の内角の和は180°で、他の2組の角が
                # それぞれ等しいので」という**使っていない根拠**を書いていた。
                if t1 == u1:
                    continue
                if t1 in collinear_triples or u1 in collinear_triples:
                    continue  # 一直線に並んだ3点は三角形ではない
                third1 = ang(*_third_vertex(a1, b1))
                third2 = ang(*_third_vertex(a2, b2))
                concl = ang_eq(third1, third2)
                if concl.args[0] != concl.args[1]:
                    yield concl, (f, g)


def _apply_angle_transitive(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """角の等しいことをつなぐ（∠X ＝ ∠Z と ∠Y ＝ ∠Z から ∠X ＝ ∠Y）。

    **推移律を規則として持たせる。** 無かったので、正三角形（AB＝AC・BA＝BC）で
    2つの底角の等式をつなぐところに `use_third_angles`（三角形の内角の和）が
    当たり、「三角形の内角の和は180°で、他の2組の角がそれぞれ等しいので」という
    **使っていない根拠**が書かれていた。教科書はここを「③、④より」とだけ書く
    ——つないでいるのは内角の和ではなく、同じ角に等しいという関係である。

    面積の `use_equal_area_transitive` と同じ形（そちらは先に入っていた）。
    """
    eqs = [f for f in facts if f.kind == "ang_eq" and f.args[0] != f.args[1]]
    for f1, f2 in itertools.permutations(eqs, 2):
        shared = set(f1.args) & set(f2.args)
        if len(shared) != 1:
            continue
        a = next(x for x in f1.args if x not in shared)
        b = next(x for x in f2.args if x not in shared)
        if a == b:
            continue
        yield ang_eq(a, b), (f1, f2)


def _third_vertex(
    a: tuple[Point, Point, Point], b: tuple[Point, Point, Point]
) -> tuple[Point, Point, Point]:
    """同じ三角形の2つの角から、残りの1つの角（頂点と2つの腕）を作る。"""
    rest = [p for p in a if p not in (a[0], b[0])]
    return (rest[0], a[0], b[0])


RIGHT_TRIANGLE_RULES: tuple[Rule, ...] = (
    Rule(
        "apply_rha",
        "直角三角形の斜辺と1つの鋭角がそれぞれ等しい",
        _apply_rha,
        ("right_triangle", "congruence"),
    ),
    Rule(
        "apply_rhs",
        "直角三角形の斜辺と他の1辺がそれぞれ等しい",
        _apply_rhs,
        ("right_triangle", "congruence"),
    ),
    Rule(
        "use_third_angles",
        "三角形の内角の和は180°で、他の2組の角がそれぞれ等しい",
        _apply_third_angles,
        ("angle",),
    ),
    Rule(
        "use_equal_angle_transitive",
        "同じ角に等しい角どうしは等しい",
        _apply_angle_transitive,
        ("angle",),
    ),
)

__all__ = ["RIGHT_TRIANGLE_RULES"]
