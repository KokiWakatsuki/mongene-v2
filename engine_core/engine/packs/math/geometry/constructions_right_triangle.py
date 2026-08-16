"""直角三角形・正三角形・二等辺になるための条件の構成カタログ（g2_l42/l43/l45）。

登録は `@register_construction("名前")`。関数は `base` / `angle` / `offset` を受ける
（recipe が同じ手順を別のパラメータで組み直して、図がたまたま見せている性質を弾く）。

**このクラスタの構成が守っていること（循環を作らないための約束）**

- g2_l42（二等辺になるための条件）の構成には、**二等辺であることを仮定に入れない**。
  「AB ＝ AC」を仮定に置くと「二等辺 → 底角が等しい」と「2角が等しい → 二等辺」で
  往復してしまい、示したいことが1手で出る。だから l42 の2つの構成は、角の条件
  （二等分線・垂直）と、対称な位置にとった点の長さの条件だけを仮定にしている。
- g2_l43（正三角形）の Lv3 も同じで、**結論になる三角形（△DEF 側）の辺の等しさは
  仮定に入れない**。仮定として置いてよいのは、材料になる正三角形 ABC の方だけである。
- 直角は `right_angle`（∠ABC ＝ 90°）で持つ。直角三角形の合同条件は「直角の頂点が
  どれか」を要求するので、`perp`（2直線が垂直）ではなく角の側で持たないと使えない。

**垂線の足は座標で置く。** `construct.py` に「垂線の足」の操作が無いためだが、事実の
出どころは座標ではなく手順である——足を下ろした以上その角は直角である、という
**手順が保証する事実**を `right_angle` として持たせ、足が線分のどこに落ちたかは
`collinear_order` に記録する（同じ半直線を別の点の名前で書く問題をこれで吸収する）。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import (
    ang,
    ang_eq,
    collinear,
    right_angle,
    seg,
    seg_eq,
)

Coord = tuple[float, float]


# ---------------------------------------------------------------------------
# 図を組むための小道具
# ---------------------------------------------------------------------------
def _rotator(deg: float):
    """図全体を少し傾ける。

    教科書の図は毎回きっちり水平ではない。傾きは**事実を1つも変えない**
    （長さも角も回転で不変）ので、質のフィルタにも証明にも影響しない。
    """
    r = math.radians(deg)
    cos, sin = math.cos(r), math.sin(r)

    def rot(x: float, y: float) -> Coord:
        return (x * cos - y * sin, x * sin + y * cos)

    return rot


def _foot(p: Coord, a: Coord, b: Coord) -> Coord:
    """点 p から直線 ab に下ろした垂線の足の座標。"""
    (ax, ay), (bx, by) = a, b
    dx, dy = bx - ax, by - ay
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)
    return (ax + t * dx, ay + t * dy)


def _put(c: Construction, name: str, xy: Coord, step: str) -> None:
    """作図手順で決まった点を置く（`construct.py` に無い操作をここで書くとき用）。"""
    if name in c.coords:  # pragma: no cover - 構成の書き誤り
        raise ValueError(f"点{name}は既にある")
    c.coords[name] = xy
    c.steps.append(step)


def _between(c: Construction, a: str, m: str, b: str) -> None:
    """「点 m は点 a と点 b の間にある」を記録する。

    一直線に並べたのが構成の意図であることを事実にしておかないと、図の質の検査が
    「∠amb がつぶれている」と誤って弾く。並びの記録は `ray_classes` にも要る
    （辺 AC 上の点 D について ∠BCD と ∠BCA を同じ角として扱うため）。
    """
    c.facts.add(collinear(a, m, b))
    c.collinear_order.append((a, m, b))


# ---------------------------------------------------------------------------
# g2_l45 直角三角形の合同条件を使った証明
# ---------------------------------------------------------------------------
@register_construction("bisector_perp_feet")
def bisector_perp_feet(p: dict[str, Any]) -> Construction:
    """∠AOB の二等分線上の点 P から、2辺に垂線をひいて足を A、B とした図。

    直角三角形の合同条件の教科書の例題そのもの。斜辺 OP が共通で、二等分線が作る
    1つの鋭角が等しいので「斜辺と1つの鋭角がそれぞれ等しい」が**直接**使える
    （深さ1で合同が出る＝誘導ありの Lv2）。

    base ＝ OP の長さ、angle ＝ ∠AOB、offset ＝ 図の傾き。
    """
    c = Construction()
    rot = _rotator((float(p["offset"]) - 2.6) * 6.0)
    op = float(p["base"])
    half = math.radians(float(p["angle"]) / 2.0)
    c.free_point("O", *rot(0.0, 0.0))
    c.free_point("P", *rot(op, 0.0))
    d = op * math.cos(half)
    for name, sign in (("A", 1.0), ("B", -1.0)):
        _put(
            c,
            name,
            rot(d * math.cos(half), sign * d * math.sin(half)),
            f"点Pから半直線O{name}に垂線をひき、その足を{name}とする",
        )
        c.facts.add(right_angle(name, "O", "P"))
    bisect = ang_eq(ang("O", "A", "P"), ang("O", "B", "P"))
    c.facts.add(bisect)
    c.givens.append(bisect)
    for x, y in (("O", "A"), ("O", "B"), ("A", "P"), ("B", "P")):
        c.connect(x, y)
    c.connect("O", "P", shared=True)
    c.description = (
        "右の図で、半直線OPは∠AOBの二等分線であり、∠OAP ＝ ∠OBP ＝ 90° である"
    )
    return c


def _isosceles_with_altitudes(p: dict[str, Any]) -> Construction:
    """AB ＝ AC の二等辺三角形に、B と C から対辺への垂線をひいた図（下の2つの土台）。

    垂線の足 D、E は**対辺の内側**に落ちる（頂角を 90° 未満にとってあるので、
    足が辺の外に出ることはない）。
    """
    c = Construction()
    rot = _rotator((float(p["offset"]) - 2.6) * 5.0)
    b = float(p["base"])
    apex = math.radians(float(p["angle"]))
    h = (b / 2.0) / math.tan(apex / 2.0)
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(b, 0.0))
    c.point_on_perpendicular_bisector("A", "B", "C", offset=h)
    for name, frm, side in (("D", "B", ("A", "C")), ("E", "C", ("A", "B"))):
        _put(
            c,
            name,
            _foot(c.coords[frm], c.coords[side[0]], c.coords[side[1]]),
            f"点{frm}から辺{side[0]}{side[1]}に垂線をひき、その足を{name}とする",
        )
        _between(c, side[0], name, side[1])
        c.facts.add(right_angle(name, frm, side[0]))
        c.facts.add(right_angle(name, frm, side[1]))
    for x, y in (("A", "B"), ("A", "C"), ("B", "D"), ("C", "E")):
        c.connect(x, y)
    c.connect("B", "C", shared=True)
    return c


@register_construction("isosceles_two_altitudes")
def isosceles_two_altitudes(p: dict[str, Any]) -> Construction:
    """二等辺三角形の2本の垂線。**補助線として直角三角形を2つ作る**Lv3 の図。

    底角が等しいこと（二等辺三角形の性質）を先に出してから、斜辺 BC が共通なので
    「斜辺と1つの鋭角」で △CBD ≡ △BCE を示し、対応する辺で BD ＝ CE を得る
    ——3段の導出になる。
    """
    c = _isosceles_with_altitudes(p)
    c.description = (
        "AB ＝ AC である二等辺三角形ABCで、頂点Bから辺ACにひいた垂線の足をD、"
        "頂点Cから辺ABにひいた垂線の足をEとする"
    )
    return c


@register_construction("isosceles_two_altitudes_cross")
def isosceles_two_altitudes_cross(p: dict[str, Any]) -> Construction:
    """上の図に、2本の垂線の交点 P を足したもの（Lv4）。

    結論が △PBC の2辺の等しさになるので、**どの直角三角形を合同にすればよいかが
    問題文から読み取れない**——垂線が作る直角三角形に自分で目をつけ、合同から
    対応する角を出し、二等辺になるための条件でしめくくる4段の導出になる。
    """
    c = _isosceles_with_altitudes(p)
    c.intersection("P", ("B", "D"), ("C", "E"))
    c.description = (
        "AB ＝ AC である二等辺三角形ABCで、頂点Bから辺ACにひいた垂線の足をD、"
        "頂点Cから辺ABにひいた垂線の足をEとし、線分BDとCEの交点をPとする"
    )
    return c


# ---------------------------------------------------------------------------
# g2_l42 二等辺三角形になるための条件
# ---------------------------------------------------------------------------
@register_construction("bisector_perp_base")
def bisector_perp_base(p: dict[str, Any]) -> Construction:
    """∠A の二等分線が底辺 BC と垂直に交わる図。**二等辺であることは仮定しない。**

    仮定は「∠BAD ＝ ∠CAD」と「∠ADB ＝ ∠ADC（＝90°）」の2つだけ。三角形の内角の和から
    残りの1組の角（∠B と ∠C）が等しいことが出て、2角が等しい三角形は二等辺三角形
    である、で終わる——教科書の誘導（「∠B ＝ ∠C を導いて証明せよ」）そのものの筋道。

    base ＝ BC、angle ＝ ∠BAC、offset ＝ 図の傾き。
    """
    c = Construction()
    rot = _rotator((float(p["offset"]) - 2.6) * 5.0)
    b = float(p["base"])
    apex = math.radians(float(p["angle"]))
    h = (b / 2.0) / math.tan(apex / 2.0)
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(b, 0.0))
    _put(c, "A", rot(b / 2.0, h), "点Aをとる")
    _put(c, "D", rot(b / 2.0, 0.0), "∠Aの二等分線と辺BCとの交点をDとする")
    _between(c, "B", "D", "C")
    bisect = ang_eq(ang("A", "B", "D"), ang("A", "C", "D"))
    c.facts.add(bisect)
    c.givens.append(bisect)
    # AD ⊥ BC。**証明が使うのは「∠ADB ＝ ∠ADC」の方**なので、直角であることと
    # 2つの直角が等しいことの両方を手順が持つ（教科書も「AD⊥BCより
    # ∠ADB ＝ ∠ADC ＝ 90°」と1行で書く）。
    c.facts.add(right_angle("D", "A", "B"))
    c.facts.add(right_angle("D", "A", "C"))
    c.facts.add(ang_eq(ang("D", "A", "B"), ang("D", "A", "C")))
    for x, y in (("A", "B"), ("A", "C"), ("B", "C")):
        c.connect(x, y)
    c.connect("A", "D", shared=True)
    c.description = "右の図の△ABCで、∠Aの二等分線と辺BCとの交点をDとすると、AD ⊥ BC である"
    return c


@register_construction("two_equal_cevians")
def two_equal_cevians(p: dict[str, Any]) -> Construction:
    """辺 AB 上の点 D と辺 AC 上の点 E について、BD ＝ CE・BE ＝ CD である図。

    仮定は長さの等式2つだけ（**二等辺であることは仮定しない**）。BC を共通の辺として
    △DBC ≡ △ECB が3組の辺で言え、対応する角から ∠ABC ＝ ∠ACB が出て、二等辺になる
    ための条件で終わる——誘導なしで角の等しさを合同から導く Lv3 の形。

    base ＝ BC、angle ＝ ∠BAC、offset ＝ D と E を辺のどのあたりにとるか。
    """
    c = Construction()
    rot = _rotator((float(p["offset"]) - 2.6) * 4.0)
    b = float(p["base"])
    apex = math.radians(float(p["angle"]))
    h = (b / 2.0) / math.tan(apex / 2.0)
    t = 0.30 + float(p["offset"]) / 20.0  # 頂点 A から見た辺上の位置
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(b, 0.0))
    _put(c, "A", rot(b / 2.0, h), "点Aをとる")
    for name, far in (("D", "B"), ("E", "C")):
        ax, ay = c.coords["A"]
        fx, fy = c.coords[far]
        _put(
            c,
            name,
            (ax + (fx - ax) * t, ay + (fy - ay) * t),
            f"辺A{far}上に点{name}をとる",
        )
        _between(c, "A", name, far)
    for f in (seg_eq(seg("B", "D"), seg("C", "E")), seg_eq(seg("B", "E"), seg("C", "D"))):
        c.facts.add(f)
        c.givens.append(f)
    for x, y in (("A", "B"), ("A", "C"), ("B", "E"), ("C", "D")):
        c.connect(x, y)
    c.connect("B", "C", shared=True)
    c.description = (
        "右の図の△ABCで、辺AB上に点D、辺AC上に点Eを、BD ＝ CE、BE ＝ CD となるようにとる"
    )
    return c


# ---------------------------------------------------------------------------
# g2_l43 正三角形の性質と条件
# ---------------------------------------------------------------------------
def _equilateral(c: Construction, b: float, rot) -> None:
    """正三角形 ABC を置く（頂角 A を上に）。

    作図としては「線分 BC の両端を中心とする半径 BC の円の交点を A とする」であり、
    AB ＝ AC も BA ＝ BC も**この手順が保証している**（座標を測って一致を見ていない）。

    **CA ＝ CB は出さない。** 3組目を仮定に入れると結論が一手（推移律）で出てしまい、
    「二等辺の重ね合わせで示す」という Lv2 の設計（family YAML の【深さ】）が
    成り立たなくなる。3辺が等しいことは示す側にあるので、仮定は2組までにとどめる。
    """
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(b, 0.0))
    _put(
        c,
        "A",
        rot(b / 2.0, b * math.sqrt(3.0) / 2.0),
        "点Bを中心とする半径BCの円と、点Cを中心とする半径CBの円の交点をAとする",
    )
    c.facts.add(seg_eq(seg("A", "B"), seg("A", "C")))
    c.facts.add(seg_eq(seg("B", "A"), seg("B", "C")))
    for x, y in (("A", "B"), ("A", "C"), ("B", "C")):
        c.connect(x, y)


@register_construction("equilateral")
def equilateral(p: dict[str, Any]) -> Construction:
    """正三角形 ABC だけの図（Lv2）。

    3辺が等しいことを、**AB ＝ AC の二等辺**と**BA ＝ BC の二等辺**の2通りに見ると、
    底角の等しさが2組出る。そのうち2組が同じ三角形の3つの角についてのものなので、
    残りの1組も等しい——「二等辺の重ね合わせで正三角形の3つの角が等しいことを示す」
    という教科書の証明そのもの。

    正三角形は1辺の長さだけで形が決まる（相似を除いて1通り）ので、angle と offset は
    図の向きだけを変える。
    """
    c = Construction()
    rot = _rotator((float(p["angle"]) - 60.0) * 0.35 + (float(p["offset"]) - 2.6) * 2.5)
    _equilateral(c, float(p["base"]), rot)
    # 3辺の等しさは description で書く（3辺に別々の印を付けると、同じ辺に本数の違う
    # 印が2種類のることになって図が読めなくなる）。
    c.description = "右の図の△ABCで、AB ＝ AC ＝ BC である"
    return c


@register_construction("equilateral_points_on_sides")
def equilateral_points_on_sides(p: dict[str, Any]) -> Construction:
    """正三角形 ABC の辺 BC 上に D、辺 CA 上に E を、BD ＝ CE となるようにとった図（Lv3）。

    正三角形の1辺と1つの角、そして BD ＝ CE で △ABD ≡ △BCE（2組の辺とその間の角）。
    どの2つの三角形を比べるかが問題文に書かれていないので、**方針を自分で構成する**
    ことになる。

    base ＝ 1辺、angle ＝ 図の傾き、offset ＝ BD を辺のどのあたりにとるか。
    """
    c = Construction()
    rot = _rotator((float(p["angle"]) - 60.0) * 0.35)
    b = float(p["base"])
    _equilateral(c, b, rot)
    t = float(p["offset"]) / 9.0
    for name, frm, to in (("D", "B", "C"), ("E", "C", "A")):
        fx, fy = c.coords[frm]
        tx, ty = c.coords[to]
        _put(
            c,
            name,
            (fx + (tx - fx) * t, fy + (ty - fy) * t),
            f"辺{frm}{to}上に、{frm}{name}が等しくなるように点{name}をとる",
        )
        _between(c, frm, name, to)
    equal = seg_eq(seg("B", "D"), seg("C", "E"))
    c.facts.add(equal)
    c.givens.append(equal)
    for x, y in (("A", "D"), ("B", "E")):
        c.connect(x, y)
    c.description = (
        "正三角形ABCの辺BC上に点D、辺CA上に点Eを、BD ＝ CE となるようにとる"
    )
    return c


@register_construction("triangle_equal_angles")
def triangle_equal_angles(p: dict[str, Any]) -> Construction:
    """3つの角が等しい三角形ABC（**辺の長さは仮定しない**）。g2_l43 Lv3 の図。

    正三角形に**なるための条件**を示す回なので、辺が等しいことを仮定に入れてはいけない
    （`equilateral` は3辺の等しさを仮定するので、こちらでは使えない——あれは性質を
    示す図である）。与えるのは角の等しさだけで、「2つの角が等しい三角形は二等辺
    三角形である」を2回使って3辺の等しさにたどりつく。

    図としては正三角形を描く（角が等しい三角形は正三角形なのだから、そう描くほかない）。
    仮定に入っているのは角の等しさだけである、というのは事実の側の話である。
    """
    c = Construction()
    rot = _rotator((float(p["angle"]) - 60.0) * 0.35 + (float(p["offset"]) - 2.6) * 2.5)
    b = float(p["base"])
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(b, 0.0))
    c.free_point("A", *rot(b / 2.0, b * math.sqrt(3.0) / 2.0))
    for x, y in (("A", "B"), ("B", "C"), ("C", "A")):
        c.connect(x, y)
    for first, second in ((("A", "B", "C"), ("B", "A", "C")), (("B", "A", "C"), ("C", "A", "B"))):
        f = ang_eq(ang(*first), ang(*second))
        c.facts.add(f)
        c.givens.append(f)
    c.steps.append("∠A、∠B、∠Cが等しくなるように三角形ABCをとる")
    c.description = "右の図の△ABCで、∠A ＝ ∠B ＝ ∠C である"
    return c


# ---------------------------------------------------------------------------
# g2_l42 Lv3 二等辺になるための条件（角の等しさを導出の途中で作る図）
# ---------------------------------------------------------------------------
@register_construction("equal_altitudes")
def equal_altitudes(p: dict[str, Any]) -> Construction:
    """△ABC の頂点 B、C から対辺に垂線 BD、CE をひき、**BD ＝ CE** を与えた図。

    g2_l42 Lv3（誘導なし・**角の等しさを合同で導いて**二等辺を構成する）のための図。
    Lv2 の `bisector_perp_base` が角の等しさを仮定として与えるのに対し、ここは
    角の等しさが**導出の途中に出てくる**——それが台帳 Lv3 の desc そのものである。

      △CBD ≡ △BCE（直角三角形の斜辺と他の1辺・深さ1／斜辺 BC は共通）
        → ∠ACB ＝ ∠ABC（対応する角・深さ2）
        → AB ＝ AC（2つの角が等しい三角形は二等辺三角形・深さ3）

    **二等辺であることは仮定に入れない**（このクラスタの約束）。A は座標としては
    BC の垂直二等分線上に置くが、`point_on_perpendicular_bisector` は使わない
    ——あの操作は「AB ＝ AC」を仮定として出してしまい、示すことが無くなる。
    2本の垂線の長さが等しければ三角形は二等辺になるので、図がそう見えるのは
    正しく、ゆらしても保たれる（＝偶然の一致ではない）。

    ∠BCD が ∠BCA と同じ角であることは、D が辺 AC の上にあることから
    `ray_classes` が吸収する。

    base ＝ 底辺 BC、offset ＝ 高さ、angle ＝ 図の傾き。
    """
    c = Construction()
    rot = _rotator((float(p["angle"]) - 70.0) / 5.0)
    bc = float(p["base"])
    height = float(p["offset"]) + 1.6
    c.free_point("B", *rot(0.0, 0.0))
    c.free_point("C", *rot(bc, 0.0))
    _put(c, "A", rot(bc / 2.0, height), "点Aをとる")
    for foot, frm, opp in (("D", "B", ("A", "C")), ("E", "C", ("A", "B"))):
        _put(
            c,
            foot,
            _foot(c.coords[frm], c.coords[opp[0]], c.coords[opp[1]]),
            f"点{frm}から辺{opp[0]}{opp[1]}に垂線をひき、その足を{foot}とする",
        )
        _between(c, opp[0], foot, opp[1])
        # 垂線を下ろした以上、足のところの角は**どちらの向きに見ても**直角である。
        # 直角三角形の合同条件は「直角の頂点がどれか」から三角形を決めるので、
        # 使う側の書き方（斜辺が BC になる書き方）で持っていないと引き当てられない。
        for arm in opp:
            c.facts.add(right_angle(foot, frm, arm))
    equal = seg_eq(seg("B", "D"), seg("C", "E"))
    c.facts.add(equal)
    c.givens.append(equal)
    for x, y in (("A", "B"), ("A", "C"), ("B", "D"), ("C", "E")):
        c.connect(x, y)
    c.connect("B", "C", shared=True)
    c.description = (
        "右の図の△ABCで、頂点Bから辺ACに垂線BDを、頂点Cから辺ABに垂線CEをひくと、"
        "BD ＝ CE であった"
    )
    return c
