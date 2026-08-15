"""平行四辺形とその仲間（長方形・ひし形・正方形）の規則カタログ。

対象単元: g2_l46（性質）・g2_l47/l48（なるための条件）・g2_l49（特別な平行四辺形）。

**書き方は `rules_congruence.py` に合わせる。** 各規則は
`(結論の Fact, 前提の Fact の並び)` を yield する関数と、教科書の言い回しに固定した
`reason` を持つ。`reason` はそのまま証明文の根拠欄に出るので、市販の問題集の
模範解答と一字一句そろえること。

**四角形の総当たりについて。** 平行四辺形の条件は「四角形 ABCD が〜ならば」の形なので、
図の点から作れる四角形を総当たりする。頂点 4 個の並べ方は 24 通りあるが、同じ四角形を
表す書き方（回転4・裏返し2）を除くと**巡回順は 3 通り**しかない。点が 6 個でも
C(6,4)×3 ＝ 45 通りで、総当たりして困る規模ではない。

**健全性の限界（意図的な割り切り）。** 「2組の対辺がそれぞれ等しい」等の条件は、
四角形が**ねじれていない**（自己交差しない）ことを前提にした定理である。事実の集合には
「4点がこの順に凸な四角形をなす」という述語が無いので、ここでは
**3点が一直線に並んでいる四角形を除く**という弱い保護しか掛けていない。
構成カタログ側で、条件が意味を持つ図だけを作ること（図は必ず PNG に起こして目視する）。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    ang,
    ang_eq,
    midpoint,
    parallel_dir,
    parallelogram,
    rectangle,
    rhombus,
    right_angle,
    seg,
    seg_eq,
    square,
)
from engine.packs.math.geometry.rule_base import Derivation, Rule

Quad = tuple[Point, Point, Point, Point]


# ---------------------------------------------------------------------------
# 四角形の総当たり（同じ四角形を表す書き方を1つにまとめる）
# ---------------------------------------------------------------------------
def _quads(points: list[Point], facts: frozenset[Fact]) -> Iterable[Quad]:
    """図の点から作れる四角形を、巡回順ごとに1回ずつ返す。

    3点が一直線に並んでいる四角形は、四角形として読めないので除く（対角線の交点を
    図に入れると、そういう4点の組が必ず出てくる）。
    """
    collinear_triples = {frozenset(f.args) for f in facts if f.kind == "collinear"}
    for combo in itertools.combinations(sorted(set(points)), 4):
        if any(frozenset(t) in collinear_triples for t in itertools.combinations(combo, 3)):
            continue
        a = combo[0]
        for b, c, d in itertools.permutations(combo[1:]):
            # a を先頭に固定すると回転4通りが消え、b < d で裏返し2通りが消える。
            if b > d:
                continue
            yield a, b, c, d


def _quads_of_kind(facts: frozenset[Fact], kind: str) -> Iterable[tuple[Quad, Fact]]:
    """既に「平行四辺形である」等が分かっている四角形を、頂点の並びつきで返す。"""
    for f in facts:
        if f.kind == kind:
            q: Quad = f.args[0]
            for i in range(4):
                yield (q[i], q[(i + 1) % 4], q[(i + 2) % 4], q[(i + 3) % 4]), f


def _opposite_side_pairs(q: Quad) -> tuple[tuple[tuple, tuple], tuple[tuple, tuple]]:
    """四角形 ABCD の対辺の組（向きつき）。AB と DC、AD と BC。"""
    a, b, c, d = q
    return (((a, b), (d, c)), ((a, d), (b, c)))


def _opposite_angle_pairs(q: Quad) -> tuple[tuple[tuple, tuple], tuple[tuple, tuple]]:
    """四角形 ABCD の対角の組。∠DAB と ∠BCD、∠ABC と ∠CDA。"""
    a, b, c, d = q
    return (
        (ang(a, d, b), ang(c, b, d)),
        (ang(b, a, c), ang(d, c, a)),
    )


# ---------------------------------------------------------------------------
# 平行四辺形の性質（g2_l46 では、これを証明するので exclude_rules で外す）
# ---------------------------------------------------------------------------
def _apply_pgram_parallel(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """平行四辺形の定義（2組の対辺はそれぞれ平行）を開く。"""
    for q, f in _quads_of_kind(facts, "parallelogram"):
        for u, v in _opposite_side_pairs(q):
            yield parallel_dir(u, v), (f,)


def _apply_pgram_opposite_sides(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "parallelogram"):
        for u, v in _opposite_side_pairs(q):
            yield seg_eq(seg(*u), seg(*v)), (f,)


def _apply_pgram_opposite_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "parallelogram"):
        for a1, a2 in _opposite_angle_pairs(q):
            if a1 != a2:
                yield ang_eq(a1, a2), (f,)


def _apply_pgram_diagonals(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """平行四辺形の対角線はそれぞれの中点で交わる。

    交点は図に無いこともあるので、**2本の対角線の上に載っている点**が図にあるときだけ
    結論を出す（「一直線上にある」は構成手順が持っている事実）。
    """
    from engine.packs.math.geometry.facts import collinear

    for q, f in _quads_of_kind(facts, "parallelogram"):
        a, b, c, d = q
        for o in points:
            if o in q:
                continue
            c1, c2 = collinear(a, o, c), collinear(b, o, d)
            if c1 in facts and c2 in facts:
                yield midpoint(o, seg(a, c)), (f, c1, c2)
                yield midpoint(o, seg(b, d)), (f, c1, c2)


# ---------------------------------------------------------------------------
# 平行四辺形になるための条件（5つ）
# ---------------------------------------------------------------------------
def _apply_cond_parallel_pairs(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q in _quads(points, facts):
        (u1, v1), (u2, v2) = _opposite_side_pairs(q)
        premises = (parallel_dir(u1, v1), parallel_dir(u2, v2))
        if all(p in facts for p in premises):
            yield parallelogram(*q), premises


def _apply_cond_side_pairs(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for q in _quads(points, facts):
        (u1, v1), (u2, v2) = _opposite_side_pairs(q)
        premises = (seg_eq(seg(*u1), seg(*v1)), seg_eq(seg(*u2), seg(*v2)))
        if all(p in facts for p in premises):
            yield parallelogram(*q), premises


def _apply_cond_angle_pairs(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for q in _quads(points, facts):
        (a1, a2), (b1, b2) = _opposite_angle_pairs(q)
        premises = (ang_eq(a1, a2), ang_eq(b1, b2))
        if all(p in facts for p in premises):
            yield parallelogram(*q), premises


def _apply_cond_diagonals(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for q in _quads(points, facts):
        a, b, c, d = q
        for o in points:
            if o in q:
                continue
            premises = (midpoint(o, seg(a, c)), midpoint(o, seg(b, d)))
            if all(p in facts for p in premises):
                yield parallelogram(*q), premises


def _apply_cond_one_pair(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for q in _quads(points, facts):
        for u, v in _opposite_side_pairs(q):
            premises = (parallel_dir(u, v), seg_eq(seg(*u), seg(*v)))
            if all(p in facts for p in premises):
                yield parallelogram(*q), premises


# ---------------------------------------------------------------------------
# 補助（教科書がひとことで済ませている等式）
# ---------------------------------------------------------------------------
def _apply_equal_halves(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """等しい2つの線分をそれぞれ2等分したとき、半分どうしも等しい。

    「AB ＝ DC で、M、N はそれぞれの中点だから MB ＝ ND」——教科書はこれを1行で書く。
    中点の定義（`use_midpoint`）を2回使って等式をつなぐ形にすると、教科書に無い
    冗長な証明になるので、規則1つにまとめてある。
    """
    mids = [f for f in facts if f.kind == "midpoint"]
    for f1, f2 in itertools.permutations(mids, 2):
        m, s1 = f1.args
        n, s2 = f2.args
        if s1 == s2 or m == n:
            continue
        whole = seg_eq(s1, s2)
        if whole not in facts:
            continue
        for x in s1:
            for y in s2:
                concl = seg_eq(seg(m, x), seg(n, y))
                if concl.args[0] != concl.args[1]:
                    yield concl, (whole, f1, f2)


def _apply_perp_right_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    """垂直な2直線が点 O で交わるとき、そこにできる4つの角は直角で、どれも等しい。

    `perp` の事実からしか動かないので、垂直を仮定しない単元の探索には影響しない。
    """
    from engine.packs.math.geometry.facts import collinear

    for f in facts:
        if f.kind != "perp":
            continue
        (p, q), (r, s) = f.args
        for o in points:
            if o in (p, q, r, s):
                continue
            c1, c2 = collinear(p, o, q), collinear(r, o, s)
            if c1 not in facts or c2 not in facts:
                continue
            arms = [(x, y) for x in (p, q) for y in (r, s)]
            for x, y in arms:
                yield right_angle(o, x, y), (f, c1, c2)
            for (x1, y1), (x2, y2) in itertools.combinations(arms, 2):
                concl = ang_eq(ang(o, x1, y1), ang(o, x2, y2))
                if concl.args[0] != concl.args[1]:
                    yield concl, (f, c1, c2)


# ---------------------------------------------------------------------------
# 特別な平行四辺形（長方形・ひし形・正方形）
# ---------------------------------------------------------------------------
def _apply_rect_from_diagonals(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "parallelogram"):
        a, b, c, d = q
        premise = seg_eq(seg(a, c), seg(b, d))
        if premise in facts:
            yield rectangle(*q), (f, premise)


def _apply_rect_from_right_angle(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "parallelogram"):
        a, b, c, d = q
        premise = right_angle(a, d, b)
        if premise in facts:
            yield rectangle(*q), (f, premise)


def _apply_rhombus_from_sides(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "parallelogram"):
        a, b, c, _d = q
        premise = seg_eq(seg(a, b), seg(b, c))
        if premise in facts:
            yield rhombus(*q), (f, premise)


def _apply_rhombus_from_perp(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    from engine.packs.math.geometry.facts import perp

    for q, f in _quads_of_kind(facts, "parallelogram"):
        a, b, c, d = q
        premise = perp(seg(a, c), seg(b, d))
        if premise in facts:
            yield rhombus(*q), (f, premise)


def _apply_square_from_both(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "rectangle"):
        other = rhombus(*q)
        if other in facts:
            yield square(*q), (f, other)


def _apply_rect_diagonals_equal(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "rectangle"):
        a, b, c, d = q
        concl = seg_eq(seg(a, c), seg(b, d))
        if concl.args[0] != concl.args[1]:
            yield concl, (f,)


def _apply_rhombus_sides_equal(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    for q, f in _quads_of_kind(facts, "rhombus"):
        a, b, c, _d = q
        concl = seg_eq(seg(a, b), seg(b, c))
        if concl.args[0] != concl.args[1]:
            yield concl, (f,)


PARALLELOGRAM_RULES: tuple[Rule, ...] = (
    # -- 性質（g2_l46 で証明する。だから l46 では exclude_rules で外す） -------
    Rule(
        "use_parallelogram_parallel",
        "平行四辺形の2組の対辺はそれぞれ平行である",
        _apply_pgram_parallel,
        ("parallelogram", "parallel"),
    ),
    Rule(
        "use_parallelogram_opposite_sides",
        "平行四辺形の2組の対辺はそれぞれ等しい",
        _apply_pgram_opposite_sides,
        ("parallelogram",),
    ),
    Rule(
        "use_parallelogram_opposite_angles",
        "平行四辺形の2組の対角はそれぞれ等しい",
        _apply_pgram_opposite_angles,
        ("parallelogram",),
    ),
    Rule(
        "use_parallelogram_diagonals",
        "平行四辺形の対角線はそれぞれの中点で交わる",
        _apply_pgram_diagonals,
        ("parallelogram",),
    ),
    # -- 平行四辺形になるための条件（5つ） -----------------------------------
    Rule(
        "conclude_parallelogram_parallel_pairs",
        "2組の対辺がそれぞれ平行である",
        _apply_cond_parallel_pairs,
        ("parallelogram",),
    ),
    Rule(
        "conclude_parallelogram_side_pairs",
        "2組の対辺がそれぞれ等しい",
        _apply_cond_side_pairs,
        ("parallelogram",),
    ),
    Rule(
        "conclude_parallelogram_angle_pairs",
        "2組の対角がそれぞれ等しい",
        _apply_cond_angle_pairs,
        ("parallelogram",),
    ),
    Rule(
        "conclude_parallelogram_diagonals",
        "対角線がそれぞれの中点で交わる",
        _apply_cond_diagonals,
        ("parallelogram",),
    ),
    Rule(
        "conclude_parallelogram_one_pair",
        "1組の対辺が平行でその長さが等しい",
        _apply_cond_one_pair,
        ("parallelogram",),
    ),
    # -- 補助 ---------------------------------------------------------------
    Rule(
        "use_equal_halves",
        "等しい線分をそれぞれ2等分した線分は等しい",
        _apply_equal_halves,
        ("midpoint", "parallelogram"),
    ),
    Rule(
        "use_perpendicular_angles",
        "垂直に交わる2直線がつくる角はすべて直角である",
        _apply_perp_right_angles,
        ("special_quad", "angle"),
    ),
    # -- 特別な平行四辺形 -----------------------------------------------------
    Rule(
        "conclude_rectangle_by_diagonals",
        "対角線の長さが等しい平行四辺形は長方形である",
        _apply_rect_from_diagonals,
        ("special_quad",),
    ),
    Rule(
        "conclude_rectangle_by_right_angle",
        "1つの角が直角である平行四辺形は長方形である",
        _apply_rect_from_right_angle,
        ("special_quad",),
    ),
    Rule(
        "conclude_rhombus_by_sides",
        "となり合う辺が等しい平行四辺形はひし形である",
        _apply_rhombus_from_sides,
        ("special_quad",),
    ),
    Rule(
        "conclude_rhombus_by_diagonals",
        "対角線が垂直に交わる平行四辺形はひし形である",
        _apply_rhombus_from_perp,
        ("special_quad",),
    ),
    Rule(
        "conclude_square",
        "長方形でもひし形でもある四角形は正方形である",
        _apply_square_from_both,
        ("special_quad",),
    ),
    Rule(
        "use_rectangle_diagonals",
        "長方形の2本の対角線の長さは等しい",
        _apply_rect_diagonals_equal,
        ("special_quad",),
    ),
    Rule(
        "use_rhombus_sides",
        "ひし形の4つの辺はすべて等しい",
        _apply_rhombus_sides_equal,
        ("special_quad",),
    ),
)

__all__ = ["PARALLELOGRAM_RULES"]
