"""円周角の証明に使う構成カタログ（g3_l49）。

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ。円周上の点は
「中心から半径だけ離れた、指定した角度の位置」にとるので、**どちらの弧の上にあるか**は
手順が決めている（座標を測って同じ側に見えると判定したのではない）。
"""
from __future__ import annotations

from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import seg, seg_eq


@register_construction("circle_two_chords")
def circle_two_chords(p: dict[str, Any]) -> Construction:
    """円の周上の4点 A・B・C・D と、弦 AC と BD の交点 P（円周角の定番の図）。

    弧 BC に対する円周角 ∠BAC ＝ ∠BDC、弧 AD に対する円周角 ∠ABD ＝ ∠ACD、
    そして対頂角 ∠APB ＝ ∠DPC が出る。
    """
    c = Construction()
    r = 2.0 + float(p["base"]) / 6.0
    spread = float(p["angle"])
    c.points_on_circle(
        "O",
        (0.0, 0.0),
        r,
        {
            "A": 90.0 + spread / 2.0,
            "B": 180.0 + float(p["offset"]) * 4.0,
            "C": 270.0 + spread / 3.0,
            "D": 30.0 - float(p["offset"]) * 2.0,
        },
    )
    for x, y in (("A", "C"), ("B", "D")):
        c.connect(x, y)
    c.intersection("P", ("A", "C"), ("B", "D"))
    for x, y in (("A", "B"), ("C", "D")):
        c.connect(x, y)
    c.description = "右の図で、4点A、B、C、Dは円Oの周上にあり、弦ACと弦BDの交点をPとする"
    return c


@register_construction("circle_diameter")
def circle_diameter(p: dict[str, Any]) -> Construction:
    """直径 AB と、円周上の点 C・D（半円の弧に対する円周角＝90° の定番の図）。

    中心 O を描くので、半径が等しいこと（OA ＝ OB ＝ OC）も使える。
    """
    c = Construction()
    r = 2.0 + float(p["base"]) / 6.0
    c.points_on_circle(
        "O",
        (0.0, 0.0),
        r,
        {
            "A": 180.0,
            "B": 0.0,
            "C": float(p["angle"]) / 2.0 + 40.0,
            "D": 220.0 + float(p["offset"]) * 3.0,
        },
        draw_center=True,
    )
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("A", "D"), ("B", "D")):
        c.connect(x, y)
    c.description = "右の図で、線分ABは円Oの直径であり、2点C、Dは円Oの周上にある"
    return c


@register_construction("circle_equal_chords")
def circle_equal_chords(p: dict[str, Any]) -> Construction:
    """円に内接する四角形ABCDで **AB ＝ DC**、弦ACと弦BDの交点をPとした図。

    **等しい弦は等しい弧に対応する**ので、AB ＝ DC は「弧ABと弧DCが同じ角度だけ張る」
    ように点をとることで手順が保証する（長さを測って一致を見たのではない）。
    弧の張る角を `angle`、下側の弦の回転量を `offset` で決める——回転量を 0 にすると
    A と C、B と D がそれぞれ直径の両端になってしまい、P が中心に落ちて図がつぶれる。

    ここから出るのは「弧BCに対する円周角 ∠BAC ＝ ∠BDC」「弧ADに対する円周角
    ∠ABD ＝ ∠ACD」で、これに仮定 AB ＝ DC を合わせると △ABP ≡ △DCP が
    1組の辺とその両端の角で示せる（教科書の定番）。
    """
    c = Construction()
    r = 2.0 + float(p["base"]) / 6.0
    a = float(p["angle"])            # 等しい2つの弦が張る弧
    s = 24.0 + float(p["offset"]) * 8.0  # 下側の弦の回転量
    c.points_on_circle(
        "O",
        (0.0, 0.0),
        r,
        {
            "A": 90.0 + a / 2.0,
            "B": 90.0 - a / 2.0,
            "C": 270.0 + a / 2.0 - s,
            "D": 270.0 - a / 2.0 - s,
        },
    )
    for x, y in (("A", "B"), ("D", "C")):
        c.connect(x, y)
    fact = seg_eq(seg("A", "B"), seg("D", "C"))
    c.facts.add(fact)
    c.givens.append(fact)
    for x, y in (("A", "C"), ("B", "D")):
        c.connect(x, y)
    c.intersection("P", ("A", "C"), ("B", "D"))
    c.description = (
        "右の図で、4点A、B、C、Dは円Oの周上にあり、AB ＝ DC である。"
        "弦ACと弦BDの交点をPとする"
    )
    return c


@register_construction("circle_thales_isosceles")
def circle_thales_isosceles(p: dict[str, Any]) -> Construction:
    """直径AB と、その両側に AC ＝ AD となるようにとった円周上の2点C・D。

    **AC ＝ AD は手順が保証する**——直径ABを軸として C と D を対称の位置にとるので、
    弧ACと弧ADが同じだけ張る。半円の弧に対する円周角は 90° なので △ABC と △ABD は
    ともに直角三角形になり、斜辺ABが共通・AC ＝ AD から直角三角形の合同がいえる。
    """
    c = Construction()
    r = 2.0 + float(p["base"]) / 6.0
    phi = 22.0 + float(p["angle"]) / 3.0   # 直径から測った C・D の位置
    tilt = float(p["offset"]) * 3.0        # 図全体の傾き（見た目だけを変える）
    c.points_on_circle(
        "O",
        (0.0, 0.0),
        r,
        {"A": 180.0 + tilt, "B": tilt, "C": tilt + phi, "D": tilt - phi},
        draw_center=True,
    )
    # 中心Oは線分ABの上にある。**この「間にある」を記録しないと**、頂点Aから見た
    # 半直線AOと半直線ABが別物に見えて、∠CAO と ∠CAB が別の角として扱われる
    # （教科書は ∠CAB と書く）。
    c.collinear_order.append(("A", "O", "B"))
    for x, y in (("A", "C"), ("B", "C"), ("A", "D"), ("B", "D")):
        c.connect(x, y)
    c.connect("A", "B", shared=True)
    fact = seg_eq(seg("A", "C"), seg("A", "D"))
    c.facts.add(fact)
    c.givens.append(fact)
    c.description = (
        "右の図で、線分ABは円Oの直径であり、2点C、Dは円Oの周上の直径ABの両側に"
        "AC ＝ AD となるようにとった点である"
    )
    return c


@register_construction("circle_diameter_chords")
def circle_diameter_chords(p: dict[str, Any]) -> Construction:
    """直径ABの同じ側に AC ＝ BD となるようにとった2点C・Dと、弦ACと弦BDの交点P。

    **AC ＝ BD は手順が保証する**——ABの垂直二等分線を軸として C と D を対称の位置に
    とるので、弧ACと弧BDが同じだけ張る。半円の弧に対する円周角が 90° であることから
    △BAC と △ABD はどちらも斜辺をABとする直角三角形になり、斜辺が共通・他の1辺が
    等しいので合同（→ AD ＝ BC）。その先に、同じ弧に対する円周角を2組選べば
    △ADP ≡ △BCP まで進む——**どの三角形と、どの弧の円周角に着目するかを自分で
    決める**のがこの図の発展の型である。
    """
    c = Construction()
    r = 2.0 + float(p["base"]) / 6.0
    gamma = 30.0 + float(p["angle"]) / 2.0   # 点Bから測ったCの位置（Dは対称の位置）
    tilt = float(p["offset"]) * 3.0          # 図全体の傾き（見た目だけを変える）
    c.points_on_circle(
        "O",
        (0.0, 0.0),
        r,
        {
            "A": 180.0 + tilt,
            "B": tilt,
            "C": gamma + tilt,
            "D": 180.0 - gamma + tilt,
        },
        draw_center=True,
    )
    # 中心Oは線分ABの上にある（`circle_thales_isosceles` と同じ理由で記録が要る）。
    # ここは交点Pもあるので、記録しないと「対頂角は等しい」の規則が頂点Aを交点と
    # 見なして ∠BAC ＝ ∠CAO という**同じ角の言い換えを対頂角として**出してしまう。
    c.collinear_order.append(("A", "O", "B"))
    for x, y in (("A", "C"), ("B", "D"), ("A", "D"), ("B", "C")):
        c.connect(x, y)
    c.connect("A", "B", shared=True)
    fact = seg_eq(seg("A", "C"), seg("B", "D"))
    c.facts.add(fact)
    c.givens.append(fact)
    c.intersection("P", ("A", "C"), ("B", "D"))
    c.description = (
        "右の図で、線分ABは円Oの直径であり、2点C、Dは円Oの周上のABと同じ側に"
        "AC ＝ BD となるようにとった点である。弦ACと弦BDの交点をPとする"
    )
    return c


__all__ = [
    "circle_diameter",
    "circle_diameter_chords",
    "circle_equal_chords",
    "circle_thales_isosceles",
    "circle_two_chords",
]
