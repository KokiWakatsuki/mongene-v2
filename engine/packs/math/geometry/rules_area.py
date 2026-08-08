"""平行線と面積（等積変形）の規則カタログ（中学2年）。

対象単元: g2_l50（平行線と面積）。

面積の等しさは合同と違って**形が違ってよい**。教科書はどちらも「△ABC ＝ △DBC」と
書くので（合同は ≡）、述語も分けてある（`tri_area_eq`）。

書き方は `rules_congruence.py` に合わせる。`reason` はそのまま証明文の根拠欄に出る。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import Fact, Point, tri, tri_area_eq
from engine.packs.math.geometry.rule_base import Derivation, Rule


def _lines_through(facts: frozenset[Fact]) -> list[frozenset[Point]]:
    """一直線上にあると分かっている点の組（`collinear` の事実をまとめたもの）。"""
    return [frozenset(f.args) for f in facts if f.kind == "collinear"]


def _apply_common_base(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """底辺が共通で高さが等しい2つの三角形は面積が等しい（等積変形の中心）。

    PQ ∥ AB なら、AB を共通の底辺とする △PAB と △QAB は高さが等しい。
    """
    for f in facts:
        if f.kind not in ("parallel", "parallel_dir"):
            continue
        s1, s2 = (f.args[0], f.args[1]) if f.kind == "parallel" else (f.args[0], f.args[1])
        for base, top in ((s1, s2), (s2, s1)):
            if len({*base, *top}) != 4:
                continue
            t1, t2 = tri(base[0], base[1], top[0]), tri(base[0], base[1], top[1])
            if sorted(t1) == sorted(t2):
                continue
            yield tri_area_eq(t1, t2), (f,)


def _apply_equal_base(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """底辺が等しく高さが等しい2つの三角形は面積が等しい。

    底辺が同じ直線上にあり長さが等しく、頂点が同じ点なら高さも等しい。中線が三角形の
    面積を2等分することが、この規則から出る。
    """
    lines = _lines_through(facts)
    for f in facts:
        if f.kind != "seg_eq":
            continue
        b1, b2 = f.args
        if b1 == b2 or set(b1) & set(b2) == set():
            continue  # 端を共有しない2辺は「同じ直線上に並んでいる」形にならない
        on_one_line = any(set(b1) | set(b2) <= line for line in lines)
        if not on_one_line:
            continue
        for apex in points:
            if apex in set(b1) | set(b2):
                continue
            t1, t2 = tri(b1[0], b1[1], apex), tri(b2[0], b2[1], apex)
            if sorted(t1) == sorted(t2):
                continue
            yield tri_area_eq(t1, t2), (f,)


def _apply_congruent_area(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """合同な図形の面積は等しい。"""
    for f in facts:
        if f.kind != "tri_cong":
            continue
        t1, t2 = f.args
        if sorted(t1) == sorted(t2):
            continue
        yield tri_area_eq(t1, t2), (f,)


def _apply_area_transitive(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """面積が等しいことをつなぐ（等積変形の連鎖）。"""
    eqs = [f for f in facts if f.kind == "tri_area_eq"]
    for f1, f2 in itertools.permutations(eqs, 2):
        shared = set(f1.args) & set(f2.args)
        if len(shared) != 1:
            continue
        a = next(t for t in f1.args if t not in shared)
        b = next(t for t in f2.args if t not in shared)
        if a == b:
            continue
        yield tri_area_eq(a, b), (f1, f2)


AREA_RULES: tuple[Rule, ...] = (
    Rule(
        "use_equal_area_common_base",
        "底辺が共通で高さが等しい",
        _apply_common_base,
        ("area", "parallel"),
    ),
    Rule(
        "use_equal_area_equal_base",
        "底辺が等しく高さが等しい",
        _apply_equal_base,
        ("area",),
    ),
    Rule(
        "use_congruent_area",
        "合同な図形の面積は等しい",
        _apply_congruent_area,
        ("area", "congruence_property"),
    ),
    Rule(
        "use_equal_area_transitive",
        "面積の等しいものどうしは等しい",
        _apply_area_transitive,
        ("area",),
    ),
)

__all__ = ["AREA_RULES"]
