"""相似の構成カタログ（g3_l41/l42/l43/l44・exam_l6）。

登録は `@register_construction("名前")`。関数は `base` / `angle` / `offset` を受ける
（recipe が同じ手順を別のパラメータで組み直して、図がたまたま見せている性質を弾く）。

**相似の定番図は2つしかない。** 砂時計型（2直線が交わり、その両側に平行な線分がある）と
ピラミッド型（1点から出る2直線を平行線が切る）で、市販の問題集の相似の証明はほとんどが
このどちらかである。ここではその2つに、平行四辺形の中で相似を見つける図と、中点連結
定理の図を足してある。

**比を「測って」作らない。** 砂時計型は点Oについて片側を k 倍に伸ばしてとるので、
OA：OC ＝ OB：OD は**手順そのものが保証している**（長さを測って比を出したのではない）。
k を 1 にすると合同になってしまうので、必ず 1 から離す。
"""
from __future__ import annotations

from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import (
    Point,
    collinear,
    parallel_dir,
    parallelogram,
    ratio_eq,
    seg,
)

Coord = tuple[float, float]


def _line(c: Construction, a: Point, m: Point, b: Point) -> None:
    """点 m が点 a と点 b の間にあることを、事実と手順の記録の両方に入れる。

    事実（`collinear`）は「3点が一直線上」までしか言わないが、**どちらが遠いか**は
    `collinear_order` が持つ。これが無いと、同じ角を別の点の名前で書いた事実
    （∠OAB と ∠CAB）が別物のままになり、教科書の定番の証明が1つも出てこない。
    """
    c.facts.add(collinear(a, m, b))
    c.collinear_order.append((a, m, b))


def _cross_points(p: dict[str, Any]) -> tuple[dict[Point, Coord], float]:
    """砂時計型の4点と、相似比の k を返す。

    点Oを原点にとり、A・B の反対側へ k 倍に伸ばした点を C・D とする。
    こうすると OA：OC ＝ OB：OD ＝ 1：k が手順から言え、AB ∥ DC も同時に決まる。
    """
    b = 1.6 + float(p["base"]) / 3.0          # OA の長さ
    k = 1.35 + float(p["offset"]) / 8.0       # 相似比（1 から離す＝合同にしない）
    th = float(p["angle"])
    import math

    ra = math.radians(150.0 + th / 6.0)
    rb = math.radians(30.0 - th / 6.0)
    ax, ay = b * math.cos(ra), b * math.sin(ra)
    bx, by = b * 0.86 * math.cos(rb), b * 0.86 * math.sin(rb)
    return (
        {
            "O": (0.0, 0.0),
            "A": (ax, ay),
            "B": (bx, by),
            "C": (-k * ax, -k * ay),
            "D": (-k * bx, -k * by),
        },
        k,
    )


def _place(c: Construction, coords: dict[Point, Coord]) -> None:
    for name, xy in coords.items():
        c.coords[name] = xy


# ---------------------------------------------------------------------------
# g3_l41 相似条件を使った証明の進め方
# ---------------------------------------------------------------------------
@register_construction("similar_hourglass")
def similar_hourglass(p: dict[str, Any]) -> Construction:
    """砂時計型（線分ACとBDが点Oで交わり、AB ∥ DC）。相似の証明のいちばんの定番。

    対頂角 ∠AOB ＝ ∠COD と、錯角 ∠OAB ＝ ∠OCD の2組で △OAB ∽ △OCD がいえる。
    """
    c = Construction()
    coords, _k = _cross_points(p)
    _place(c, coords)
    c.steps.append("線分ACと線分BDが点Oで交わる図をかく")
    _line(c, "A", "O", "C")
    _line(c, "B", "O", "D")
    par = parallel_dir(("A", "B"), ("D", "C"))
    c.facts.add(par)
    c.givens.append(par)
    for x, y in (("A", "C"), ("B", "D"), ("A", "B"), ("D", "C")):
        c.connect(x, y)
    c.description = "下の図で、線分ACと線分BDは点Oで交わっており、AB ∥ DC である"
    return c


def _pgram_with_point_on_bc(p: dict[str, Any], ratio: float) -> Construction:
    """平行四辺形ABCDの辺BC上に点Mをとり、線分AMと対角線BDの交点をPとした図。

    **仮定は「平行四辺形である」ことだけ**にしてある（対辺が平行であることを事実として
    直接持たせると、錯角が深さ1で出てしまい、2段階の根拠づけにならない）。
    """
    import math

    c = Construction()
    b, t = 2.4 + float(p["base"]) / 2.2, 1.5 + float(p["offset"]) / 2.4
    th = math.radians(52.0 + float(p["angle"]) / 4.0)
    dx, dy = t * math.cos(th), t * math.sin(th)
    _place(c, {"A": (0.0, 0.0), "B": (b, 0.0), "C": (b + dx, dy), "D": (dx, dy)})
    c.steps.append("平行四辺形ABCDをかく")
    f = parallelogram("A", "B", "C", "D")
    c.facts.add(f)
    c.givens.append(f)
    for x, y in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        c.connect(x, y)
    bx, by = c.coords["B"]
    cx, cy = c.coords["C"]
    c.coords["M"] = (bx + (cx - bx) * ratio, by + (cy - by) * ratio)
    _line(c, "B", "M", "C")
    c.connect("A", "M")
    c.connect("B", "D")
    c.intersection("P", ("A", "M"), ("B", "D"))
    return c


@register_construction("similar_pgram_cross")
def similar_pgram_cross(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの辺BC上の点Mについて、AMと対角線BDの交点をPとした図。

    平行四辺形であること → 対辺が平行 → 錯角、という**2段階の根拠づけ**を経てから
    対頂角と組にする。台帳の Lv3 desc「共通角/等角の2段階の根拠づけ」がこの形。
    """
    # 辺BCを切る位置は `angle` から連続的に決める（中点にはしない——中点にすると
    # 中点連結の事実が増えて、この単元で見せたい筋道と別の証明が出てくる）。
    ratio = 0.30 + (float(p["angle"]) % 9.0) / 30.0
    c = _pgram_with_point_on_bc(p, ratio)
    c.description = (
        "下の図の平行四辺形ABCDで、辺BC上に点Mをとり、線分AMと対角線BDの交点をPとした"
    )
    return c


@register_construction("similar_pgram_median")
def similar_pgram_median(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの辺BCの**中点**Mについて、AMと対角線BDの交点をPとした図。

    `similar_pgram_cross` と点の置き方は同じだが、**Mが中点である**ことが仮定に入る。
    だから BM と AD の比が決まり、「BP：PD をどの三角形の相似から出すか」を自分で
    決める問題になる（台帳の Lv4 desc「どの三角形を相似とみるか自分で構成する」）。
    """
    c = _pgram_with_point_on_bc(p, 0.5)
    from engine.packs.math.geometry.facts import midpoint

    f = midpoint("M", seg("B", "C"))
    c.facts.add(f)
    c.givens.append(f)
    c.description = (
        "下の図の平行四辺形ABCDで、辺BCの中点をMとし、線分AMと対角線BDの交点をPとした"
    )
    return c


# ---------------------------------------------------------------------------
# g3_l42 平行線と線分の比の定理 / exam_l6 相似と面積比・体積比の融合
# ---------------------------------------------------------------------------
@register_construction("similar_pyramid")
def similar_pyramid(p: dict[str, Any]) -> Construction:
    """ピラミッド型（△ABCの辺AB上に点D、辺AC上に点Eがあり DE ∥ BC）。

    同位角が2組そろうので △ADE ∽ △ABC がいえ、そこから AD：AB ＝ AE：AC が出る
    ——これが平行線と線分の比の定理そのものである（だから g3_l42 では、その定理を
    規則から外して探索する）。
    """
    import math

    c = Construction()
    base = 3.4 + float(p["base"]) / 2.4
    height = 2.2 + float(p["offset"]) / 2.6
    apex_x = base * (0.30 + (float(p["angle"]) % 11.0) / 55.0)
    _place(c, {"B": (0.0, 0.0), "C": (base, 0.0), "A": (apex_x, height)})
    c.steps.append("△ABCをかく")
    t = 0.34 + (float(p["angle"]) % 7.0) / 26.0   # 辺を切る比（0.34〜0.57）
    for name, far in (("D", "B"), ("E", "C")):
        ax, ay = c.coords["A"]
        fx, fy = c.coords[far]
        c.coords[name] = (ax + (fx - ax) * t, ay + (fy - ay) * t)
    _line(c, "A", "D", "B")
    _line(c, "A", "E", "C")
    par = parallel_dir(("D", "E"), ("B", "C"))
    c.facts.add(par)
    c.givens.append(par)
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("D", "E")):
        c.connect(x, y)
    c.description = (
        "下の図の△ABCで、辺AB上に点D、辺AC上に点Eをとると、DE ∥ BC である"
    )
    return c


# ---------------------------------------------------------------------------
# g3_l43 平行線と線分の比の定理の逆と応用
# ---------------------------------------------------------------------------
@register_construction("ratio_hourglass")
def ratio_hourglass(p: dict[str, Any]) -> Construction:
    """砂時計型だが、**平行は仮定せず比だけを仮定する**図（OA：OC ＝ OB：OD）。

    示すのは AB ∥ DC のほう。対頂角と比から2組の辺の比とその間の角で相似を出し、
    対応する角が等しいこと（錯角）から平行にたどりつく——比の条件から平行を導く
    という、定理の逆そのものの筋道である。
    """
    c = Construction()
    coords, _k = _cross_points(p)
    _place(c, coords)
    c.steps.append("線分ACと線分BDが点Oで交わる図をかく")
    _line(c, "A", "O", "C")
    _line(c, "B", "O", "D")
    f = ratio_eq(seg("O", "A"), seg("O", "C"), seg("O", "B"), seg("O", "D"))
    c.facts.add(f)
    c.givens.append(f)
    for x, y in (("A", "C"), ("B", "D"), ("A", "B"), ("D", "C")):
        c.connect(x, y)
    c.description = (
        "下の図で、線分ACと線分BDは点Oで交わっており、OA：OC ＝ OB：OD である"
    )
    return c


# ---------------------------------------------------------------------------
# g3_l44 中点連結定理とその証明・利用
# ---------------------------------------------------------------------------
def _triangle(p: dict[str, Any]) -> dict[Point, Coord]:
    base = 3.8 + float(p["base"]) / 2.2
    height = 2.4 + float(p["offset"]) / 2.4
    apex_x = base * (0.26 + (float(p["angle"]) % 13.0) / 60.0)
    return {"B": (0.0, 0.0), "C": (base, 0.0), "A": (apex_x, height)}


@register_construction("midline_triangle")
def midline_triangle(p: dict[str, Any]) -> Construction:
    """△ABCの辺AB、ACの中点M、Nを結んだ図（中点連結定理をそのまま使う図）。"""
    c = Construction()
    _place(c, _triangle(p))
    c.steps.append("△ABCをかく")
    c.midpoint_of("M", "A", "B")
    c.midpoint_of("N", "A", "C")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("M", "N")):
        c.connect(x, y)
    c.description = "下の図の△ABCで、辺AB、辺ACの中点をそれぞれM、Nとし、点Mと点Nを結んだ"
    return c


@register_construction("midline_medial")
def midline_medial(p: dict[str, Any]) -> Construction:
    """△ABCの3辺の中点M、N、Pを結んだ図（**中点を結ぶ補助線を引いた**形）。

    中点連結定理を2回使って「同じ線分の半分どうしは等しい」でつなぎ、2組の対辺が
    それぞれ等しいことから平行四辺形を出す——補助線を引いてから2段階でたどる、
    台帳 Lv3 desc そのものの構成である。
    """
    c = Construction()
    _place(c, _triangle(p))
    c.steps.append("△ABCをかく")
    c.midpoint_of("M", "A", "B")
    c.midpoint_of("N", "A", "C")
    c.midpoint_of("P", "B", "C")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("M", "N"), ("N", "P"), ("P", "M")):
        c.connect(x, y)
    c.description = (
        "下の図の△ABCで、辺AB、辺AC、辺BCの中点をそれぞれM、N、Pとし、"
        "その3点を結んだ"
    )
    return c


__all__ = [
    "midline_medial",
    "midline_triangle",
    "ratio_hourglass",
    "similar_hourglass",
    "similar_pgram_cross",
    "similar_pgram_median",
    "similar_pyramid",
]
