"""規則の型と、規則を書くときの共通の道具（docs/proof_engine_design_2026-08-08.md §5）。

規則カタログは**単元クラスタごとに別のモジュール**に置く（`rules_congruence.py`、
`rules_parallelogram.py` …）。`rules.py` はそれらを束ねるだけにしてある。
こう分けたのは、単元を増やす作業が「1つのファイルに全部足す」形だと、
複数の単元を同時に進められないからである（同じ行を取り合う）。
"""
from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from engine.packs.math.geometry.facts import Fact, Point, tri

# 導出1件 = (結論, その根拠に使った前提の並び)
Derivation = tuple[Fact, tuple[Fact, ...]]


@dataclass(frozen=True)
class Rule:
    name: str
    reason: str
    apply: Callable[[list[Point], frozenset[Fact]], Iterable[Derivation]]
    # この規則がどの単元の道具か（質のフィルタが「単元に合った定理か」を見るのに使う）
    topics: tuple[str, ...] = ()
    # 定義を開くだけの規則か（「Oは中点だから AO＝DO」のように、証明文では前提と結論を
    # **1行にまとめて書く**。教科書が2行に分けないので、分けると冗長に見える）。
    definitional: bool = False


def triangles(points: list[Point]) -> list[tuple[Point, Point, Point]]:
    """図の点から作れる三角形の頂点の三つ組（順序つき）。

    合同の対応を扱うので順序つきで全通り出す。点が 6 個でも 120 通りで、
    総当たりして困る規模ではない。
    """
    return [tri(*p) for p in itertools.permutations(points, 3)]


def pairs_of_triangles(points: list[Point]) -> Iterable[tuple[tuple, tuple]]:
    """異なる2つの三角形の組（対応つき）。同じ頂点集合の別の対応も含む。"""
    for t1, t2 in itertools.combinations(triangles(points), 2):
        yield t1, t2


__all__ = ["Derivation", "Rule", "pairs_of_triangles", "triangles"]
