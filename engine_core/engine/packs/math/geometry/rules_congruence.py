"""合同・二等辺・角の規則カタログ（docs/proof_engine_design_2026-08-08.md §5）。

**ここに載っている定理だけが証明に使われる。** だから「中学範囲の定理だけを載せる」
ことが、そのまま「出てくる証明が教科書の範囲に収まる」ことの保証になる。
単元を増やすことは、機構を触ることではなく**このカタログに定理を足すこと**である。

各規則は
  - `name`     規則の識別子（op 列に出る＝level_sep の材料になる）
  - `reason`   証明文の「根拠」欄に入る日本語（**教科書の言い回しに固定する**）
  - `apply`    図の点集合と既知の事実から、導ける事実を (結論, 前提) の形で返す関数
を持つ。`apply` は**足せる事実を全部返す**（前向き推論器が飽和させる）。

規則は「前提パターンのマッチ」を各規則の中で書く。総当たりで書けるのは、1つの図の
点が数個しかないからである（点 n 個なら三角形は C(n,3) 個・対応は 6 通り）。
汎用のパターンマッチ機構を作るより、規則ごとに素直に書いたほうが読める。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    ang,
    ang_eq,
    seg,
    seg_eq,
    tri_cong,
)
from engine.packs.math.geometry.rule_base import (
    Derivation,
    Rule,
    collinear_triples,
    pairs_of_triangles,
)


# ---------------------------------------------------------------------------
# 合同条件（3つ）
# ---------------------------------------------------------------------------
def _apply_sss(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for t1, t2 in pairs_of_triangles(points):
        premises = []
        for i in range(3):
            j = (i + 1) % 3
            premises.append(seg_eq(seg(t1[i], t1[j]), seg(t2[i], t2[j])))
        if all(p in facts for p in premises):
            yield tri_cong(t1, t2), tuple(premises)


def _apply_sas(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for t1, t2 in pairs_of_triangles(points):
        # 頂点 t[0] をはさむ2辺と、その間の角。
        premises = (
            seg_eq(seg(t1[0], t1[1]), seg(t2[0], t2[1])),
            seg_eq(seg(t1[0], t1[2]), seg(t2[0], t2[2])),
            ang_eq(ang(t1[0], t1[1], t1[2]), ang(t2[0], t2[1], t2[2])),
        )
        if all(p in facts for p in premises):
            yield tri_cong(t1, t2), premises


def _apply_asa(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for t1, t2 in pairs_of_triangles(points):
        # 辺 t[0]t[1] と、その両端の角。
        premises = (
            seg_eq(seg(t1[0], t1[1]), seg(t2[0], t2[1])),
            ang_eq(ang(t1[0], t1[1], t1[2]), ang(t2[0], t2[1], t2[2])),
            ang_eq(ang(t1[1], t1[0], t1[2]), ang(t2[1], t2[0], t2[2])),
        )
        if all(p in facts for p in premises):
            yield tri_cong(t1, t2), premises


# ---------------------------------------------------------------------------
# 合同な図形の性質（対応する辺・角が等しい）
# ---------------------------------------------------------------------------
def _apply_cong_parts(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for f in facts:
        if f.kind != "tri_cong":
            continue
        t1, t2 = f.args
        for i in range(3):
            j = (i + 1) % 3
            s1, s2 = seg(t1[i], t1[j]), seg(t2[i], t2[j])
            if s1 != s2:
                yield seg_eq(s1, s2), (f,)
        for i in range(3):
            a1 = ang(t1[i], t1[(i + 1) % 3], t1[(i + 2) % 3])
            a2 = ang(t2[i], t2[(i + 1) % 3], t2[(i + 2) % 3])
            if a1 != a2:
                yield ang_eq(a1, a2), (f,)


# ---------------------------------------------------------------------------
# 二等辺三角形（両向き）
# ---------------------------------------------------------------------------
def _apply_isosceles_base_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    degenerate = collinear_triples(facts)
    for a, b, c in itertools.permutations(points, 3):
        if frozenset({a, b, c}) in degenerate:
            continue  # 一直線上の3点は三角形にならない
        premise = seg_eq(seg(a, b), seg(a, c))
        if premise in facts:
            concl = ang_eq(ang(b, a, c), ang(c, a, b))
            if concl.args[0] != concl.args[1]:
                yield concl, (premise,)


def _apply_isosceles_from_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    degenerate = collinear_triples(facts)
    for a, b, c in itertools.permutations(points, 3):
        if frozenset({a, b, c}) in degenerate:
            continue
        premise = ang_eq(ang(b, a, c), ang(c, a, b))
        if premise in facts and premise.args[0] != premise.args[1]:
            yield seg_eq(seg(a, b), seg(a, c)), (premise,)


# ---------------------------------------------------------------------------
# 中点の定義
# ---------------------------------------------------------------------------
def _apply_midpoint(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for f in facts:
        if f.kind != "midpoint":
            continue
        m, (p, q) = f.args
        yield seg_eq(seg(p, m), seg(m, q)), (f,)


# ---------------------------------------------------------------------------
# 対頂角・平行線の錯角/同位角
# ---------------------------------------------------------------------------
def _apply_vertical_angles(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """2直線が点 O で**交わる**とき、対頂角は等しい。

    「A,O,C が一直線」「B,O,D が一直線」に加えて、**O が A と C の間・B と D の間**に
    あることが要る。`collinear` は3点を並べ替えて持ち、どれが真ん中かを持っていない
    ので、それだけで当てると**交わっていない配置にも当たってしまう**：
    △ABC の辺AB上に M、辺AC上に N をとった図で「A,M,B が一直線」「A,N,C が一直線」から
    ∠MAN ＝ ∠BAC を出し、「対頂角は等しいから」と書いていた——この2つは**同じ角**で
    あって対頂角ではない（頂点 A は M と B の間にない）。g2_l45.proof の
    「対頂角は等しいから ∠BAD ＝ ∠CAE」がこれで、正しくは「∠A は共通」。
    """
    collinears = [f for f in facts if f.kind == "collinear"]
    betweens = {f.args for f in facts if f.kind == "between"}

    def crosses_at(o: Point, ends: tuple[Point, ...]) -> bool:
        x, y = sorted(ends)
        return (o, (x, y)) in betweens

    for f1, f2 in itertools.combinations(collinears, 2):
        common = set(f1.args) & set(f2.args)
        if len(common) != 1:
            continue
        o = next(iter(common))
        ends1 = tuple(p for p in f1.args if p != o)
        ends2 = tuple(p for p in f2.args if p != o)
        if not (crosses_at(o, ends1) and crosses_at(o, ends2)):
            continue
        a, c = (p for p in f1.args if p != o)
        b, d = (p for p in f2.args if p != o)
        concl = ang_eq(ang(o, a, b), ang(o, c, d))
        if concl.args[0] != concl.args[1]:
            yield concl, (f1, f2)
        concl2 = ang_eq(ang(o, a, d), ang(o, c, b))
        if concl2.args[0] != concl2.args[1]:
            yield concl2, (f1, f2)


def _apply_alternate_angles(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """平行線の錯角は等しい。

    向きつきの平行 PQ ∥ RS（同じ向き）に対し、**第1の線の始点 P と第2の線の終点 S**を
    結ぶ直線を横断線とみると、∠QPS と ∠RSP が錯角になる。向きが分かっているから
    「錯角か同位角か」を座標を見ずに決められる（平行四辺形 ABCD で AD∥BC、対角線 AC を
    引いたときの ∠DAC ＝ ∠BCA がこれ）。
    """
    for f in facts:
        if f.kind != "parallel_dir":
            continue
        (p, q), (r, s) = f.args
        for (t1, h1), (t2, h2) in (((p, q), (r, s)), ((r, s), (p, q))):
            if len({t1, h1, t2, h2}) != 4:
                continue
            concl = ang_eq(ang(t1, h1, h2), ang(h2, t2, t1))
            if concl.args[0] != concl.args[1]:
                yield concl, (f,)


CONGRUENCE_RULES: tuple[Rule, ...] = (
    Rule("apply_sss", "3組の辺がそれぞれ等しい", _apply_sss, ("congruence",)),
    Rule("apply_sas", "2組の辺とその間の角がそれぞれ等しい", _apply_sas, ("congruence",)),
    Rule("apply_asa", "1組の辺とその両端の角がそれぞれ等しい", _apply_asa, ("congruence",)),
    Rule(
        "use_congruent_parts",
        "合同な図形では対応する辺（角）はそれぞれ等しい",
        _apply_cong_parts,
        ("congruence", "congruence_property"),
    ),
    Rule(
        "use_isosceles_base_angles",
        "二等辺三角形の底角は等しい",
        _apply_isosceles_base_angles,
        ("isosceles",),
    ),
    Rule(
        "conclude_isosceles",
        "2つの角が等しい三角形は二等辺三角形である",
        _apply_isosceles_from_angles,
        ("isosceles",),
    ),
    Rule("use_midpoint", "", _apply_midpoint, ("midpoint",), definitional=True),
    Rule("use_vertical_angles", "対頂角は等しい", _apply_vertical_angles, ("angle",)),
    Rule(
        "use_alternate_angles",
        "平行線の錯角は等しい",
        _apply_alternate_angles,
        ("parallel", "angle"),
    ),
)

__all__ = ["CONGRUENCE_RULES"]
