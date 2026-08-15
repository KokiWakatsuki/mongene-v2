"""相似の規則カタログ（相似条件・相似の性質・平行線と線分の比・中点連結定理）。

対象単元: g3_l41（相似条件）・g3_l42/l43（平行線と線分の比）・g3_l44（中点連結定理）・
exam_l6（融合問題の中で相似を示す）。

**書き方は `rules_congruence.py` に合わせる。** `reason` は教科書の言い回しに固定する
（「2組の角がそれぞれ等しい」など）。`reason` はそのまま証明文の根拠欄に出るので、
**「①、②より、〜ので」「〜から」の両方の形にはめて読める述語の形**にしてある
（`render_text.render_proof`）。だから「中点連結定理」ではなく
「中点連結定理が成り立つ」と書く——前者だと「①、②より、中点連結定理ので」になる。

**総当たりの入口を facts 側にとってある。** 合同条件は三角形の組（点6個で 7140 組）を
総当たりしても足りるが、相似条件は合同より後の単元で図の点が増えるうえ、
規則そのものが「角の等式2つ」「辺の比の等式」から出発できる形をしている。
だから 2組の角（`_apply_similar_aa`）は**角の等式をグループにまとめてから**組み、
辺の比を使う条件は**比の等式が1つも無ければ即座に打ち切る**。

**一直線上の点の順序について（意図的な割り切り）。** 事実の集合には「点Mが点Bと点Cの
間にある」という述語が無く、`collinear` は3点が同じ直線上にあることしか言わない。
対頂角の規則（`rules_congruence.use_vertical_angles`）が既に「共有点が真ん中にある」
ことを前提に書かれているのと同じ割り切りで、ここでも交点は線分の内側にあるものとして
扱う。構成カタログ側で、そうなる図だけを作ること。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    ang,
    ang_eq,
    collinear,
    parallel,
    parallel_dir,
    ratio_eq,
    seg,
    seg_eq,
    seg_half,
    tri_sim,
)
from engine.packs.math.geometry.rule_base import (
    Derivation,
    Rule,
    collinear_triples,
    pairs_of_triangles,
)


def _tri_angles(t: tuple[Point, Point, Point]) -> list[tuple[Point, Point, Point]]:
    """三角形の3つの内角（頂点の並びと同じ順）。"""
    return [ang(t[i], t[(i + 1) % 3], t[(i + 2) % 3]) for i in range(3)]


def _tri_sides(t: tuple[Point, Point, Point]) -> list[tuple[Point, Point]]:
    """三角形の3つの辺（辺 i は頂点 i と頂点 i+1 を結ぶ）。"""
    return [seg(t[i], t[(i + 1) % 3]) for i in range(3)]


# ---------------------------------------------------------------------------
# 相似条件（3つ）
# ---------------------------------------------------------------------------
def _apply_similar_aa(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """2組の角がそれぞれ等しい。

    角の等式 ∠v1 ＝ ∠v2 は「三角形{v1,p,q}の頂点v1の角と、三角形{v2,r,s}の頂点v2の角が
    等しい」と読める。だから**3点の組が同じ角の等式どうし**を集めれば、そのうち2つで
    三角形の相似が言える。三角形の組を総当たりするより桁で速く、しかも同じ結果になる。
    """
    degenerate = collinear_triples(facts)
    groups: dict[tuple[frozenset[Point], frozenset[Point]], list[Fact]] = {}
    for f in facts:
        if f.kind != "ang_eq":
            continue
        a1, a2 = f.args
        k1, k2 = frozenset(a1), frozenset(a2)
        if k1 == k2 or k1 in degenerate or k2 in degenerate:
            continue
        groups.setdefault((k1, k2), []).append(f)
    for (k1, k2), fs in groups.items():
        for f, g in itertools.combinations(fs, 2):
            v1, w1 = f.args[0][0], g.args[0][0]
            v2, w2 = f.args[1][0], g.args[1][0]
            if v1 == w1 or v2 == w2:
                continue  # 同じ頂点の角を2回使っても2組にならない
            x1 = next(iter(k1 - {v1, w1}))
            x2 = next(iter(k2 - {v2, w2}))
            yield tri_sim((v1, w1, x1), (v2, w2, x2)), (f, g)


def _apply_similar_sas(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """2組の辺の比とその間の角がそれぞれ等しい。"""
    if not any(f.kind == "ratio_eq" for f in facts):
        return  # 比の等式が無ければこの条件は使えない（総当たりに入らない）
    degenerate = collinear_triples(facts)
    for t1, t2 in pairs_of_triangles(points):
        if frozenset(t1) in degenerate or frozenset(t2) in degenerate:
            continue
        if sorted(t1) == sorted(t2):
            continue
        angle = ang_eq(_tri_angles(t1)[0], _tri_angles(t2)[0])
        if angle.args[0] == angle.args[1]:
            continue
        ratio = ratio_eq(
            seg(t1[0], t1[1]), seg(t2[0], t2[1]), seg(t1[0], t1[2]), seg(t2[0], t2[2])
        )
        if ratio.args[0] == ratio.args[1]:
            continue
        if ratio in facts and angle in facts:
            yield tri_sim(t1, t2), (ratio, angle)


def _apply_similar_sss(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """3組の辺の比がすべて等しい。"""
    if not any(f.kind == "ratio_eq" for f in facts):
        return
    degenerate = collinear_triples(facts)
    for t1, t2 in pairs_of_triangles(points):
        if frozenset(t1) in degenerate or frozenset(t2) in degenerate:
            continue
        if sorted(t1) == sorted(t2):
            continue
        s1, s2 = _tri_sides(t1), _tri_sides(t2)
        premises = (
            ratio_eq(s1[0], s2[0], s1[1], s2[1]),
            ratio_eq(s1[1], s2[1], s1[2], s2[2]),
        )
        if any(p.args[0] == p.args[1] for p in premises):
            continue
        if all(p in facts for p in premises):
            yield tri_sim(t1, t2), premises


# ---------------------------------------------------------------------------
# 相似な図形の性質
# ---------------------------------------------------------------------------
def _apply_similar_ratio(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """相似な図形の対応する辺の比は等しい。

    △ADE ∽ △ABC から出るのは AD：AB ＝ AE：AC の形（**対応する辺どうしの比を並べる**）で、
    これが平行線と線分の比の結論そのものになる。
    """
    for f in facts:
        if f.kind != "tri_sim":
            continue
        t1, t2 = f.args
        s1, s2 = _tri_sides(t1), _tri_sides(t2)
        for i, j in itertools.combinations(range(3), 2):
            concl = ratio_eq(s1[i], s2[i], s1[j], s2[j])
            if concl.args[0] == concl.args[1]:
                continue
            yield concl, (f,)


def _apply_similar_angles(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """相似な図形の対応する角はそれぞれ等しい。"""
    for f in facts:
        if f.kind != "tri_sim":
            continue
        t1, t2 = f.args
        for a1, a2 in zip(_tri_angles(t1), _tri_angles(t2)):
            if a1 != a2:
                yield ang_eq(a1, a2), (f,)


# ---------------------------------------------------------------------------
# 平行線と角（相似の定番図＝ピラミッド型に要る）
# ---------------------------------------------------------------------------
def _pyramid_configs(
    facts: frozenset[Fact],
) -> Iterable[tuple[Point, Point, Point, Point, Point, tuple[Fact, ...]]]:
    """ピラミッド型の配置を facts から拾う。

    「点Aから出る2直線の上に点D・Bと点E・Cがあり、DE ∥ BC（同じ向き）」という配置を
    (a, d, e, b, c, 前提) で返す。向きつきの平行を要求しているので、
    **D と B、E と C の対応が手順から決まっている**（座標を測っていない）。
    """
    colls = [f for f in facts if f.kind == "collinear"]
    for f in facts:
        if f.kind != "parallel_dir":
            continue
        (d, e), (b, c) = f.args
        if len({d, e, b, c}) != 4:
            continue
        for c1 in colls:
            if not {d, b} <= set(c1.args):
                continue
            for c2 in colls:
                if c2 is c1 or not {e, c} <= set(c2.args):
                    continue
                apex = (set(c1.args) - {d, b}) & (set(c2.args) - {e, c})
                if len(apex) != 1:
                    continue
                a = next(iter(apex))
                if a in {d, e, b, c}:
                    continue
                yield a, d, e, b, c, (f, c1, c2)


def _apply_corresponding_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    """平行線の同位角は等しい（ピラミッド型 ∠ADE ＝ ∠ABC）。

    `rules_congruence.use_alternate_angles` は錯角しか出さないので、DE ∥ BC の図で
    教科書が使う同位角がこれまで1つも出てこなかった（＝相似の定番図が作れなかった）。
    """
    for a, d, e, b, c, premises in _pyramid_configs(facts):
        for concl in (ang_eq(ang(d, a, e), ang(b, a, c)), ang_eq(ang(e, a, d), ang(c, a, b))):
            if concl.args[0] != concl.args[1]:
                yield concl, premises


def _apply_parallel_by_alternate_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    """錯角が等しいので2直線は平行である（砂時計型の逆向き）。

    2直線が点Oで交わり、その両側の ∠OAB ＝ ∠OCD が言えたら AB ∥ CD。
    """
    colls = [f for f in facts if f.kind == "collinear"]
    for c1, c2 in itertools.combinations(colls, 2):
        common = set(c1.args) & set(c2.args)
        if len(common) != 1:
            continue
        o = next(iter(common))
        if len(set(c1.args) | set(c2.args)) != 5:
            continue
        for a in (x for x in c1.args if x != o):
            other_a = next(x for x in c1.args if x not in (o, a))
            for b in (x for x in c2.args if x != o):
                other_b = next(x for x in c2.args if x not in (o, b))
                premise = ang_eq(ang(a, o, b), ang(other_a, o, other_b))
                if premise.args[0] == premise.args[1] or premise not in facts:
                    continue
                yield parallel(seg(a, b), seg(other_a, other_b)), (c1, c2, premise)


# ---------------------------------------------------------------------------
# 平行線と線分の比（g3_l42）とその逆（g3_l43）
# ---------------------------------------------------------------------------
def _apply_parallel_ratio(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """平行線と線分の比（DE ∥ BC ならば AD：AB ＝ AE：AC、AD：DB ＝ AE：EC）。

    **この定理を証明する単元（g3_l42）では `exclude_rules` で外す**——外さないと
    1手で終わってしまう（循環）。
    """
    for a, d, e, b, c, premises in _pyramid_configs(facts):
        for concl in (
            ratio_eq(seg(a, d), seg(a, b), seg(a, e), seg(a, c)),
            ratio_eq(seg(a, d), seg(d, b), seg(a, e), seg(e, c)),
        ):
            if concl.args[0] != concl.args[1]:
                yield concl, premises


def _apply_parallel_by_ratio(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """平行線と線分の比の定理の逆（AD：AB ＝ AE：AC ならば DE ∥ BC）。

    **この定理を使わずに示す単元（g3_l43）では `exclude_rules` で外す。**
    """
    colls = [f for f in facts if f.kind == "collinear"]
    for c1, c2 in itertools.combinations(colls, 2):
        common = set(c1.args) & set(c2.args)
        if len(common) != 1:
            continue
        a = next(iter(common))
        for d in (x for x in c1.args if x != a):
            b = next(x for x in c1.args if x not in (a, d))
            for e in (x for x in c2.args if x != a):
                c = next(x for x in c2.args if x not in (a, e))
                for premise in (
                    ratio_eq(seg(a, d), seg(a, b), seg(a, e), seg(a, c)),
                    ratio_eq(seg(a, d), seg(d, b), seg(a, e), seg(e, c)),
                ):
                    if premise.args[0] == premise.args[1] or premise not in facts:
                        continue
                    yield parallel(seg(d, e), seg(b, c)), (c1, c2, premise)


# ---------------------------------------------------------------------------
# 中点連結定理（g3_l44）
# ---------------------------------------------------------------------------
def _apply_midline(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """中点連結定理（2辺の中点を結ぶ線分は、残りの辺に平行で長さはその半分）。

    平行は**向きつき**で出せる——M ＝ (A+B)/2、N ＝ (A+C)/2 なら N－M ＝ (C－B)/2 で、
    向きまで手順が決めている。向きが分かるから、この平行がさらに錯角・同位角の規則に
    そのまま乗る（向きの無い平行では、そこで止まってしまう）。
    """
    degenerate = collinear_triples(facts)
    mids = sorted((f for f in facts if f.kind == "midpoint"), key=lambda f: (f.args[0], f.args[1]))
    for f1, f2 in itertools.combinations(mids, 2):
        m, s1 = f1.args
        n, s2 = f2.args
        shared = set(s1) & set(s2)
        if m == n or len(shared) != 1:
            continue
        a = next(iter(shared))
        b = next(x for x in s1 if x != a)
        c = next(x for x in s2 if x != a)
        if len({a, b, c, m, n}) != 5 or frozenset({a, b, c}) in degenerate:
            continue
        yield parallel_dir((m, n), (b, c)), (f1, f2)
        yield seg_half(seg(m, n), seg(b, c)), (f1, f2)


def _apply_midpoint_half(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """中点の定義（中点で分けた線分は、もとの線分の半分）。"""
    for f in facts:
        if f.kind != "midpoint":
            continue
        m, (p, q) = f.args
        yield seg_half(seg(p, m), seg(p, q)), (f,)
        yield seg_half(seg(m, q), seg(p, q)), (f,)


def _apply_equal_halves_of_same(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    """同じ線分の半分どうしは等しい。

    中点連結定理で出た「MN ＝ ½BC」と、中点の定義で出た「BP ＝ ½BC」を結ぶ行。
    教科書が1行で済ませているところなので、規則1つにまとめてある。
    """
    halves = sorted(
        (f for f in facts if f.kind == "seg_half"), key=lambda f: (f.args[1], f.args[0])
    )
    for f1, f2 in itertools.combinations(halves, 2):
        if f1.args[1] != f2.args[1]:
            continue
        concl = seg_eq(f1.args[0], f2.args[0])
        if concl.args[0] != concl.args[1]:
            yield concl, (f1, f2)


SIMILARITY_RULES: tuple[Rule, ...] = (
    # -- 相似条件（3つ） -----------------------------------------------------
    Rule(
        "conclude_similar_aa",
        "2組の角がそれぞれ等しい",
        _apply_similar_aa,
        ("similarity",),
    ),
    Rule(
        "conclude_similar_sas",
        "2組の辺の比とその間の角がそれぞれ等しい",
        _apply_similar_sas,
        ("similarity", "ratio"),
    ),
    Rule(
        "conclude_similar_sss",
        "3組の辺の比がすべて等しい",
        _apply_similar_sss,
        ("similarity", "ratio"),
    ),
    # -- 相似な図形の性質 -----------------------------------------------------
    Rule(
        "use_similar_ratio",
        "相似な図形の対応する辺の比は等しい",
        _apply_similar_ratio,
        ("similarity", "ratio"),
    ),
    Rule(
        "use_similar_angles",
        "相似な図形の対応する角はそれぞれ等しい",
        _apply_similar_angles,
        ("similarity",),
    ),
    # -- 平行線と角 -----------------------------------------------------------
    Rule(
        "use_corresponding_angles",
        "平行線の同位角は等しい",
        _apply_corresponding_angles,
        ("parallel", "angle"),
    ),
    Rule(
        "conclude_parallel_by_alternate_angles",
        "錯角が等しい",
        _apply_parallel_by_alternate_angles,
        # **これは2年（g2_l32「平行になるための条件」）の定理**。相似のモジュールに
        # 置いてあるのは実装の都合で、単元としては相似ではない——topics に similarity を
        # 入れていたせいで、2年の単元からこの定理が使えなくなっていた。
        ("parallel",),
    ),
    # -- 平行線と線分の比とその逆 ---------------------------------------------
    Rule(
        "use_parallel_ratio",
        "平行線と線分の比は等しい",
        _apply_parallel_ratio,
        ("ratio", "parallel"),
    ),
    Rule(
        "conclude_parallel_by_ratio",
        "平行線と線分の比の定理の逆が成り立つ",
        _apply_parallel_by_ratio,
        ("ratio", "parallel"),
    ),
    # -- 中点連結定理 ---------------------------------------------------------
    Rule(
        "use_midline",
        "中点連結定理が成り立つ",
        _apply_midline,
        ("similarity", "midpoint"),
    ),
    Rule(
        "use_midpoint_half",
        "",
        _apply_midpoint_half,
        ("similarity", "midpoint"),
        definitional=True,
    ),
    Rule(
        "use_equal_halves_of_same",
        "同じ線分の半分どうしは等しい",
        _apply_equal_halves_of_same,
        ("similarity", "midpoint"),
    ),
)

__all__ = ["SIMILARITY_RULES"]
