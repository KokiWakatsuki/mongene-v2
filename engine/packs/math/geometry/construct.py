"""構成生成器＝作図手順から図を組む（docs/proof_engine_design_2026-08-08.md §5）。

**事実は構成手順が持つ。座標から測って作らない。** 円の上に点をとったなら
「中心からの距離が等しい」という事実は**手順そのものが保証している**のであって、
座標を測って一致を見たものではない（浮動小数の一致で事実を作ると、丸めで偽の事実が
混じる）。座標は図を描くためだけにある。

だから「解き方が違う問題」は、**手順の組合せを変えること**で出てくる。手順は
基本作図に対応しているので、組合せは無限にあり、しかもどれも実現可能な図になる
（ランダムな座標から図を作るとつぶれた三角形やありえない配置が出るが、この作り方では
原理的に出ない）。

いまの操作カタログ（合同系を出すのに要る最小限）:
  free_point                 自由な点
  point_on_circle            ある点を中心とし、ある線分を半径とする円の上の点
  point_on_perpendicular_bisector  2点から等距離の点（＝垂直二等分線上）
  midpoint                   線分の中点
  intersection               2直線の交点
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    collinear,
    midpoint,
    seg,
    seg_eq,
)

Coord = tuple[float, float]

# 図が読めるための下限（質のフィルタが使う）。
_MIN_POINT_GAP = 0.45   # 点どうしが近すぎない（ラベルが重なる）
_MIN_ANGLE_DEG = 18.0   # 三角形がつぶれていない


@dataclass
class Construction:
    """作図手順の記録。点の座標・生まれた事実・手順の説明を持つ。"""

    coords: dict[Point, Coord] = field(default_factory=dict)
    facts: set[Fact] = field(default_factory=set)
    steps: list[str] = field(default_factory=list)
    # 問題文に「与えられた条件」として書くべき事実（構成の副産物は書かない）。
    givens: list[Fact] = field(default_factory=list)
    # 図に線として描く線分。
    segments: list[tuple[Point, Point]] = field(default_factory=list)

    @property
    def points(self) -> list[Point]:
        return list(self.coords)

    # -- 操作 ---------------------------------------------------------------
    def free_point(self, name: Point, x: float, y: float) -> None:
        self._add(name, (x, y))
        self.steps.append(f"点{name}をとる")

    def point_on_circle(
        self, name: Point, center: Point, radius_to: Point, *, angle_deg: float
    ) -> None:
        """`center` を中心、`center`-`radius_to` を半径とする円の上に点をとる。

        生まれる事実は「中心からの距離が等しい」＝ `center name ＝ center radius_to`。
        """
        cx, cy = self.coords[center]
        rx, ry = self.coords[radius_to]
        r = math.hypot(rx - cx, ry - cy)
        rad = math.radians(angle_deg)
        self._add(name, (cx + r * math.cos(rad), cy + r * math.sin(rad)))
        fact = seg_eq(seg(center, name), seg(center, radius_to))
        self.facts.add(fact)
        self.givens.append(fact)
        self.steps.append(f"点{center}を中心とする半径{center}{radius_to}の円上に点{name}をとる")

    def point_on_perpendicular_bisector(
        self, name: Point, p: Point, q: Point, *, offset: float
    ) -> None:
        """線分 pq の垂直二等分線上に点をとる（＝p と q から等距離）。"""
        px, py = self.coords[p]
        qx, qy = self.coords[q]
        mx, my = (px + qx) / 2, (py + qy) / 2
        dx, dy = qx - px, qy - py
        n = math.hypot(dx, dy) or 1.0
        self._add(name, (mx - dy / n * offset, my + dx / n * offset))
        fact = seg_eq(seg(name, p), seg(name, q))
        self.facts.add(fact)
        self.givens.append(fact)
        self.steps.append(f"線分{p}{q}の垂直二等分線上に点{name}をとる")

    def midpoint_of(self, name: Point, p: Point, q: Point) -> None:
        px, py = self.coords[p]
        qx, qy = self.coords[q]
        self._add(name, ((px + qx) / 2, (py + qy) / 2))
        fact = midpoint(name, seg(p, q))
        self.facts.add(fact)
        self.facts.add(collinear(p, name, q))
        self.givens.append(fact)
        self.steps.append(f"線分{p}{q}の中点を{name}とする")

    def intersection(
        self, name: Point, line1: tuple[Point, Point], line2: tuple[Point, Point]
    ) -> None:
        """2直線の交点。交わらない（平行）なら構成できないので例外にする。"""
        (x1, y1), (x2, y2) = self.coords[line1[0]], self.coords[line1[1]]
        (x3, y3), (x4, y4) = self.coords[line2[0]], self.coords[line2[1]]
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-9:
            raise ValueError("2直線が平行で交点がない")
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
        self._add(name, (x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
        self.facts.add(collinear(line1[0], name, line1[1]))
        self.facts.add(collinear(line2[0], name, line2[1]))
        self.steps.append(
            f"直線{line1[0]}{line1[1]}と直線{line2[0]}{line2[1]}の交点を{name}とする"
        )

    def connect(self, p: Point, q: Point, *, shared: bool = False) -> None:
        """線分を引く（図に描く）。`shared=True` なら「共通」として証明に使える。"""
        self.segments.append(seg(p, q))
        if shared:
            self.facts.add(seg_eq(seg(p, q), seg(p, q)))

    # -- 内部 ---------------------------------------------------------------
    def _add(self, name: Point, xy: Coord) -> None:
        if name in self.coords:
            raise ValueError(f"点{name}は既にある")
        self.coords[name] = xy


# ---------------------------------------------------------------------------
# 図の質（座標を見て判定する。事実ではなく**見え方**の検査）
# ---------------------------------------------------------------------------
def figure_quality_problems(con: Construction) -> list[str]:
    """図として読めない構成を弾く。空リストなら合格。

    ここは「事実が正しいか」ではなく「**人が読める図か**」の検査である。
    つぶれた三角形や重なった点は、数学的には正しくても問題集の図にならない。
    """
    problems: list[str] = []
    names = con.points
    for i, p in enumerate(names):
        for q in names[i + 1:]:
            (x1, y1), (x2, y2) = con.coords[p], con.coords[q]
            if math.hypot(x2 - x1, y2 - y1) < _MIN_POINT_GAP:
                problems.append(f"点{p}と点{q}が近すぎる")
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            for c in names[j + 1:]:
                if len({a, b, c}) != 3:
                    continue
                angle = _angle_deg(con.coords[b], con.coords[a], con.coords[c])
                if angle < _MIN_ANGLE_DEG:
                    problems.append(f"∠{b}{a}{c}がつぶれている（{angle:.0f}°）")
    return sorted(set(problems))


def _angle_deg(p: Coord, vertex: Coord, q: Coord) -> float:
    ax, ay = p[0] - vertex[0], p[1] - vertex[1]
    bx, by = q[0] - vertex[0], q[1] - vertex[1]
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    cosv = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
    return math.degrees(math.acos(cosv))


__all__ = ["Construction", "Coord", "figure_quality_problems"]
