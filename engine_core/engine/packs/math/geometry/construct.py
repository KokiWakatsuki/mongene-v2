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

import itertools
import math
from dataclasses import dataclass, field

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    between,
    collinear,
    midpoint,
    on_circle,
    parallel_dir,
    same_arc,
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
    # 問題文の書き出し（「平行四辺形ABCDで」のように、条件を並べるより自然な言い方が
    # あるときに使う。空なら givens を並べて書く）。
    description: str = ""
    # 図に描く円（中心の座標と半径）。中心を点として描くかどうかとは別に持つ
    # ——円周角の図では中心 O を描かないのがふつうだが、円そのものは描く。
    circles: list[tuple[Coord, float]] = field(default_factory=list)
    # 「点 m が点 a と点 b の間にある」という手順の記録（a, m, b の順）。
    # **同じ半直線を別の点で呼んでしまう問題**を解くのに要る（`ray_classes`）。
    collinear_order: list[tuple[Point, Point, Point]] = field(default_factory=list)

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

    def points_on_circle(
        self,
        center: Point,
        center_xy: Coord,
        radius: float,
        placements: dict[Point, float],
        *,
        draw_center: bool = False,
    ) -> None:
        """1つの円の周上に、指定した角度の位置へ点をまとめてとる。

        **どちらの弧の上にあるかは、手順（角度）が決めている**——座標を測って
        「同じ側に見える」と判定しているのではない。円周角の定理は「同じ弧に対する」
        という条件つきの定理なので、ここが手順から出ていないと定理を機械的に使えない。

        `draw_center` が真のときだけ中心を点として図に置き、`on_circle` の事実を出す
        （＝「半径は等しい」が使えるようになる）。円周角の図では中心を描かないのが
        ふつうなので既定は偽——描かない中心について「OA ＝ OB」と書く証明は、
        図に無い線分の話になってしまう。

        直径になっている2点（角度差 180°）には、中心が中点であることと3点が一直線に
        あることを出す（半円の弧に対する円周角＝90° の規則が、ここを見る）。
        """
        self.circles.append((center_xy, radius))
        cx, cy = center_xy
        if draw_center:
            self._add(center, center_xy)
        for name, deg in placements.items():
            rad = math.radians(deg)
            self._add(name, (cx + radius * math.cos(rad), cy + radius * math.sin(rad)))
            if draw_center:
                self.facts.add(on_circle(name, center))
        self.steps.append(
            f"円{center}の周上に点{'、点'.join(placements)}をとる"
        )
        names = list(placements)
        for a, b in itertools.combinations(names, 2):
            if draw_center and _is_diameter(placements[a], placements[b]):
                self.facts.add(midpoint(center, seg(a, b)))
                self.facts.add(collinear(a, center, b))
                self.facts.add(between(center, a, b))
            for p, q in itertools.combinations([n for n in names if n not in (a, b)], 2):
                if _on_same_arc(placements[a], placements[b], placements[p], placements[q]):
                    self.facts.add(same_arc((a, b), p, q))

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

    def reflected_point(self, name: Point, p: Point, center: Point) -> None:
        """点 p を点 center について対称移動した点（＝center が p と name の中点）。

        X 字型（2本の線分が中点で交わる図）を作るための操作。対頂角の規則が効くように
        「一直線上にある」ことも同時に出す。
        """
        px, py = self.coords[p]
        cx, cy = self.coords[center]
        self._add(name, (2 * cx - px, 2 * cy - py))
        fact = midpoint(center, seg(p, name))
        self.facts.add(fact)
        self.facts.add(collinear(p, center, name))
        self.collinear_order.append((p, center, name))
        self.givens.append(fact)
        self.steps.append(f"点{p}を点{center}について対称移動した点を{name}とする")

    def translated_point(self, name: Point, base: Point, frm: Point, to: Point) -> None:
        """点 base を、ベクトル frm→to だけ平行移動した点。

        平行四辺形を作る操作。**向きつきの平行**が出るので、錯角の規則がそのまま効く
        （向きの分からない平行だけでは、錯角か同位角かを座標なしに決められない）。
        """
        bx, by = self.coords[base]
        fx, fy = self.coords[frm]
        tx, ty = self.coords[to]
        self._add(name, (bx + tx - fx, by + ty - fy))
        for u_, v_ in (((base, name), (frm, to)), ((base, frm), (name, to))):
            self.facts.add(parallel_dir(u_, v_))
            self.facts.add(seg_eq(seg(*u_), seg(*v_)))
        self.steps.append(f"点{base}をベクトル{frm}{to}だけ平行移動した点を{name}とする")

    def midpoint_of(self, name: Point, p: Point, q: Point) -> None:
        px, py = self.coords[p]
        qx, qy = self.coords[q]
        self._add(name, ((px + qx) / 2, (py + qy) / 2))
        fact = midpoint(name, seg(p, q))
        self.facts.add(fact)
        self.facts.add(collinear(p, name, q))
        self.collinear_order.append((p, name, q))
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
        # 交点が線分の**内側**に落ちたかは手順の出力（媒介変数）そのもので、
        # 図を測って一致を見たものではない。内側なら「間にある」を記録する
        # （同じ半直線を別の点で呼ぶ問題を解くのに要る＝`ray_classes`）。
        for (u, v), s_ in ((line1, t), (line2, _param_on(self.coords, line2, (x1 + t * (x2 - x1), y1 + t * (y2 - y1))))):
            if 1e-6 < s_ < 1 - 1e-6:
                self.collinear_order.append((u, name, v))
        self.steps.append(
            f"直線{line1[0]}{line1[1]}と直線{line2[0]}{line2[1]}の交点を{name}とする"
        )

    def between_facts(self) -> frozenset[Fact]:
        """「点 m が2点の間にある」事実の一覧。

        **`collinear_order` から1か所で出す。** `collinear` は3点を並べ替えて持つので
        どれが真ん中かを持っておらず、対頂角の規則がそれだけで当たると
        「交わっていない配置」にも当たってしまう（`facts.between` の docstring）。

        真ん中がどれかを知っているのは作図の手順で、それは `collinear_order` に
        入っている。**各作図の関数で個別に足すと、足し忘れた図だけ対頂角が使えなくなる**
        ——実際 `constructions_similarity._line` を足し忘れて g3_l41.proof.Lv3
        （砂時計型）が生成できなくなった。出す場所を1つにして、忘れる余地を消す。
        """
        return frozenset(between(m, a, b) for a, m, b in self.collinear_order)

    def ray_classes(self) -> dict[tuple[Point, Point], tuple[Point, ...]]:
        """「頂点から見て**同じ半直線の上にある点**」の組を返す。

        弦 AC と BD の交点を P とした図で、△PAB の頂点 A の角は ∠BAP と書くが、
        円周角の定理が出すのは ∠BAC である。P は線分 AC の上にあるので**この2つは
        同じ角**なのに、点の名前が違うので別の事実になってしまう。角を作るところで
        名前をそろえないと、教科書の定番の証明（円周角 → 相似）が1つも出てこない。

        戻り値は (頂点, 腕の点) → その半直線を指す点の並び。並びの先頭が代表で、
        **頂点から最も遠い点**をとる（教科書が ∠BAP ではなく ∠BAC と書くのに合わせる）。

        どちらが遠いかは座標を測ったのではなく、`collinear_order`（手順が記録した
        「間にある」の関係）から決まる。
        """
        farther: dict[tuple[Point, Point], Point] = {}
        for a, m, b in self.collinear_order:
            farther[(a, m)] = b
            farther[(b, m)] = a

        def rep(v: Point, x: Point) -> Point:
            seen = {x}
            while (v, x) in farther:
                x = farther[(v, x)]
                if x in seen:  # pragma: no cover - 手順が輪を作ったとき
                    break
                seen.add(x)
            return x

        members: dict[tuple[Point, Point], list[Point]] = {}
        for v in self.coords:
            for x in self.coords:
                if x == v:
                    continue
                members.setdefault((v, rep(v, x)), []).append(x)
        out: dict[tuple[Point, Point], tuple[Point, ...]] = {}
        for (v, r), xs in members.items():
            if len(xs) == 1:
                continue
            ordered = (r, *sorted(x for x in xs if x != r))
            for x in xs:
                out[(v, x)] = ordered
        return out

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


def _param_on(coords: dict[Point, Coord], line: tuple[Point, Point], pt: Coord) -> float:
    """線分 line 上での位置（端点を 0 と 1 とする媒介変数）。`intersection` が使う。"""
    (ax, ay), (bx, by) = coords[line[0]], coords[line[1]]
    dx, dy = bx - ax, by - ay
    n2 = dx * dx + dy * dy
    if n2 < 1e-12:  # pragma: no cover - 端点が重なる線分は作らない
        return -1.0
    return ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / n2


def _is_diameter(deg_a: float, deg_b: float) -> bool:
    """円周上の2点が直径の両端か（角度が 180° 離れているか）。"""
    return abs((deg_a - deg_b) % 360.0 - 180.0) < 1e-6


def _on_same_arc(deg_a: float, deg_b: float, deg_p: float, deg_q: float) -> bool:
    """弦 ab について、点 p と点 q が同じ側の弧の上にあるか。

    a から b へ反時計回りに進む弧の内側にあるかどうかで2つの弧に分ける。両方が内側、
    または両方が外側なら同じ弧である。端点と重なる配置は構成の誤りなので偽を返す。
    """
    span = (deg_b - deg_a) % 360.0
    if span < 1e-6:
        return False

    def inside(deg: float) -> bool | None:
        t = (deg - deg_a) % 360.0
        if t < 1e-6 or abs(t - span) < 1e-6:
            return None
        return t < span

    ip, iq = inside(deg_p), inside(deg_q)
    if ip is None or iq is None:
        return False
    return ip == iq


# ---------------------------------------------------------------------------
# 図の質（座標を見て判定する。事実ではなく**見え方**の検査）
# ---------------------------------------------------------------------------
def figure_quality_problems(con: Construction) -> list[str]:
    """図として読めない構成を弾く。空リストなら合格。

    ここは「事実が正しいか」ではなく「**人が読める図か**」の検査である。
    つぶれた三角形や重なった点は、数学的には正しくても問題集の図にならない。

    **一直線上にあると分かっている3点は対象外**（X字型のように、まっすぐ並べたことが
    構成の意図である場合まで「つぶれている」と弾いてしまった）。

    **角の検査は「2辺とも図に描かれている角」だけを見る。** はじめは3点の組をすべて
    見ていたが、それだと平行四辺形の辺の中点Mについて ∠ACM のような**誰も見ない角**
    （CM は線として描かれていない）で図が落ちた。実際、中点連結定理の図・ピラミッド型・
    平行四辺形の応用など、教科書の定番の図がことごとく落ちていた。描かれていない角は
    つぶれて見えようがないので、読めるかどうかの検査の対象ではない。
    """
    collinear_triples = {
        frozenset(f.args) for f in con.facts if f.kind == "collinear"
    }
    drawn = {frozenset(s) for s in con.segments}
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
                if len({a, b, c}) != 3 or frozenset({a, b, c}) in collinear_triples:
                    continue
                if frozenset({a, b}) not in drawn or frozenset({a, c}) not in drawn:
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
