"""合同の証明に使う構成カタログ（docs/proof_engine_design_2026-08-08.md §5）。

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ（座標から
測らない）。だから「解き方が違う問題」は、**手順の組合せを変えること**で出てくる。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import (
    ang,
    ang_eq,
    ang_text,
    collinear,
    seg,
    seg_eq,
)


@register_construction("kite")
def kite(p: dict[str, Any]) -> Construction:
    """たこ形（AB=AD・CB=CD）に対角線 AC を引いた図。SSS の定番。"""
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", float(p["base"]), 0.0)
    c.point_on_circle("D", "A", "B", angle_deg=float(p["angle"]))
    c.point_on_perpendicular_bisector("C", "B", "D", offset=-float(p["offset"]))
    for x, y in (("A", "B"), ("A", "D"), ("B", "C"), ("D", "C")):
        c.connect(x, y)
    c.connect("A", "C", shared=True)
    return c


@register_construction("x_shape")
def x_shape(p: dict[str, Any]) -> Construction:
    """2本の線分が中点で交わる X 字型。中点 → 対頂角 → SAS。"""
    c = Construction()
    c.free_point("O", 0.0, 0.0)
    c.free_point("A", -float(p["base"]), float(p["angle"]) / 40.0)
    c.free_point("B", -float(p["offset"]) / 2.0, -2.0)
    c.reflected_point("D", "A", "O")
    c.reflected_point("C", "B", "O")
    for x, y in (("A", "D"), ("B", "C"), ("A", "B"), ("C", "D")):
        c.connect(x, y)
    # 条件を並べるだけだと「O は AD の中点、O は BC の中点 である」になって読めない。
    # 同じ点についての条件は、教科書のように1つの文にまとめる。
    c.description = "下の図で、線分ADとBCは点Oで交わっていて、点Oはそれぞれの中点である"
    return c


@register_construction("parallelogram")
def parallelogram(p: dict[str, Any]) -> Construction:
    """平行四辺形に対角線を引いた図（**対辺の長さは仮定として与える**）。

    平行四辺形の性質そのものを証明する単元では、この構成は使えない（示したいことが
    仮定に入ってしまう）。そちらは `constructions_parallelogram.py` にある、
    平行だけを仮定する構成を使う。
    """
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", float(p["base"]), 0.0)
    c.free_point("C", float(p["base"]) + float(p["offset"]) / 3.0, float(p["angle"]) / 25.0)
    c.translated_point("D", "A", "B", "C")
    for x, y in (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")):
        c.connect(x, y)
    c.connect("A", "C", shared=True)
    c.description = "平行四辺形ABCDで、対角線ACを引いた"
    return c


@register_construction("isosceles_median")
def isosceles_with_median(p: dict[str, Any]) -> Construction:
    """二等辺三角形 ABC（AB=AC）に、底辺 BC の中点 M を結んだ図。

    「底角が等しい」を**証明する**ための図。だからこのセルでは、その定理を規則から
    外して探索する（外さないと1手で終わってしまう）。
    """
    c = Construction()
    # **頂角 A を上に置く。** 図に起こして初めて気づいたが、offset の符号を負にすると
    # 二等辺三角形が上下逆さまに描かれる。教科書の図は例外なく頂角が上なので、
    # 逆さまの図はそれだけで「見たことのない図」になる。
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]), 0.0)
    c.point_on_perpendicular_bisector("A", "B", "C", offset=float(p["offset"]) + 1.0)
    c.midpoint_of("M", "B", "C")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("A", "M")):
        c.connect(x, y)
    c.connect("A", "M", shared=True)
    c.description = "AB ＝ AC である二等辺三角形ABCで、辺BCの中点をMとし、点Aと点Mを結んだ"
    return c


@register_construction("isosceles_bisector")
def isosceles_with_apex_bisector(p: dict[str, Any]) -> Construction:
    """二等辺三角形 ABC（AB=AC）に、頂角 A の二等分線を引いて底辺との交点を M とした図。

    `isosceles_median` と点の位置は同じだが、**与える条件が違う**——あちらは「M は
    BC の中点」、こちらは「AM は ∠A の二等分線」。だから証明の筋道も変わり
    （SSS ではなく SAS になる）、示せることも変わる（中点であること・垂直であること）。
    **図が同じでも条件が違えば別の問題である**というのは、市販の問題集がまさに
    そうやって問題を作り分けているところである。

    二等分線であることは**作図の手順が保証する**（角を測って一致を見たのではない）。
    二等辺三角形の頂角の二等分線は底辺の垂直二等分線と重なるので、その上に M をとれば
    ∠BAM ＝ ∠CAM は手順から言える。
    """
    c = Construction()
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]), 0.0)
    c.point_on_perpendicular_bisector("A", "B", "C", offset=float(p["offset"]) + 1.0)
    bx, _ = c.coords["B"]
    cx, _ = c.coords["C"]
    c.coords["M"] = ((bx + cx) / 2, 0.0)
    c.steps.append("∠Aの二等分線と辺BCとの交点をMとする")
    # M は辺 BC 上にある。図の質の検査が「∠BCM がつぶれている」と誤って弾かないよう、
    # **一直線に並べたのが構成の意図である**ことを事実として持たせる。
    c.facts.add(collinear("B", "M", "C"))
    bisect = ang_eq(ang("A", "B", "M"), ang("A", "C", "M"))
    c.facts.add(bisect)
    c.givens.append(bisect)
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("A", "M")):
        c.connect(x, y)
    c.connect("A", "M", shared=True)
    c.description = "AB ＝ AC である二等辺三角形ABCで、∠Aの二等分線と辺BCとの交点をMとした"
    return c


@register_construction("alternate_angle_cross")
def alternate_angle_cross(p: dict[str, Any]) -> Construction:
    """2直線 AC と BD が点Oで交わり、**錯角 ∠OAB ＝ ∠OCD が与えられた**図（g2_l32）。

    「錯角が等しければ2直線は平行」を1段で使う図。平行であることは**仮定に入れない**
    ——それが示すことだからである。角が等しいことは作図の手順が保証している
    （B を、∠OAB と等しい角の向きにとった）。
    """
    c = Construction()
    theta = math.radians(float(p["angle"]) / 2.0 + 20.0)
    arm = float(p["base"])
    other = float(p["offset"]) + 1.4
    c.free_point("O", 0.0, 0.0)
    c.free_point("A", -arm * math.cos(theta), arm * math.sin(theta))
    c.free_point("C", arm * math.cos(theta), -arm * math.sin(theta))
    # B は A から見て O の向こう側、D は C から見て O の向こう側（＝錯角の位置）。
    c.coords["B"] = (-arm * math.cos(theta) + other, arm * math.sin(theta) - other * 0.35)
    c.coords["D"] = (arm * math.cos(theta) - other, -arm * math.sin(theta) + other * 0.35)
    c.steps.append(
        f"{ang_text(ang('A', 'O', 'B'))}と{ang_text(ang('C', 'O', 'D'))}"
        "が等しくなるように点B、Dをとる"
    )
    for triple in (("A", "O", "C"), ("B", "O", "D")):
        c.facts.add(collinear(*triple))
        c.collinear_order.append(triple)
    equal = ang_eq(ang("A", "O", "B"), ang("C", "O", "D"))
    c.facts.add(equal)
    c.givens.append(equal)
    for x, y in (("A", "C"), ("B", "D"), ("A", "B"), ("C", "D")):
        c.connect(x, y)
    # **問題文の角名は、事実の側と同じ書き方にする。** 手で「∠OAB ＝ ∠OCD」と
    # 書いていたので、証明の「仮定より」の行だけ ∠BAO ＝ ∠DCO と出て、
    # 生徒が仮定を書き写すときに対応が取れなかった。`ang_text` から組む。
    c.description = (
        "下の図で、2直線ACとBDは点Oで交わっていて、"
        f"{ang_text(ang('A', 'O', 'B'))} ＝ {ang_text(ang('C', 'O', 'D'))} である"
    )
    return c


@register_construction("kite_diagonals")
def kite_diagonals(p: dict[str, Any]) -> Construction:
    """たこ形（AB=AD・CB=CD）に**対角線を2本とも**引き、交点を P とした図（g2_l40 Lv4）。

    `kite` との違いは対角線 BD と交点 P だけだが、**証明の性質が変わる**。
    たこ形1本の対角線では「合同 → 対応する辺（角）」の2手で終わるのに対し、
    ここは

      △ABC ≡ △ADC（3組の辺・深さ1）
        → ∠BAC ＝ ∠DAC（対応する角・深さ2）
        → △ABP ≡ △ADP（2組の辺とその間の角・深さ3）
        → BP ＝ DP（対応する辺・深さ4）

    と、**1つ目の合同から出た角を材料にして2つ目の合同を示す**。台帳 Lv4 の
    「複数三角形の合同を組み合わせ方針を自分で構成する」がちょうどこの形である。

    ∠BAP と ∠BAC が同じ角であることは、P が線分 AC の上にあることから
    `ray_classes` が吸収する（`intersection` が「間にある」を記録している）。
    AP が2つ目の合同の共通の辺になるので、その等式も持たせる——線としては対角線 AC の
    一部だが、証明では AP と書く辺である。
    """
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", float(p["base"]), 0.0)
    c.point_on_circle("D", "A", "B", angle_deg=float(p["angle"]))
    c.point_on_perpendicular_bisector("C", "B", "D", offset=-float(p["offset"]))
    for x, y in (("A", "B"), ("A", "D"), ("B", "C"), ("D", "C")):
        c.connect(x, y)
    c.intersection("P", ("A", "C"), ("B", "D"))
    c.connect("A", "C", shared=True)
    c.connect("B", "D")
    c.facts.add(seg_eq(seg("A", "P"), seg("A", "P")))
    # 交点Pは仮定ではなく**構成で置いた点**なので、条件を並べる既定の書き方では
    # 問題文に出てこない（結論の BP ＝ DP に、本文に無い点が出てしまう）。
    c.description = (
        "下の図で、AB ＝ AD、CB ＝ CD である四角形ABCDに対角線AC、BDを引き、"
        "その交点をPとした"
    )
    return c


@register_construction("isosceles_equal_segments")
def isosceles_equal_segments(p: dict[str, Any]) -> Construction:
    """二等辺三角形 ABC（AB=AC）の辺 AB、AC 上に BD ＝ CE となる点 D、E をとった図。

    g2_l41 Lv4（誘導なし・**性質を組み合わせて**方針を自分で立てる）のための図。
    Lv2/Lv3 が「二等辺三角形の性質そのものを証明する」ので底角の規則を外して探索する
    のに対し、ここは**その性質を道具として使う**側である。

      底角 ∠DBC ＝ ∠ECB（二等辺三角形の底角は等しい・深さ1）
        → △DBC ≡ △ECB（2組の辺とその間の角・深さ2）
        → DC ＝ EB（対応する辺・深さ3）

    ∠DBC が ∠ABC と同じ角であることは、D が辺 AB の上にあることから `ray_classes`
    が吸収する。D と E は**端点から等しい長さのところ**にとるので、図をゆらしても
    BD ＝ CE は保たれる（偶然の一致にならない）。

    base ＝ 底辺 BC、offset ＝ 高さ、angle ＝ BD の長さの取り方（辺の何割か）。
    """
    c = Construction()
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]), 0.0)
    c.point_on_perpendicular_bisector("A", "B", "C", offset=float(p["offset"]) + 1.0)
    (ax, ay), (bx, by), (cx, cy) = c.coords["A"], c.coords["B"], c.coords["C"]
    # 辺の何割のところに点をとるか。角度のパラメータを割合に**単調に**写す
    # （剰余で折り返すと、図をゆらしたときに割合が飛んで、偶然の一致の判定が
    # パラメータの連続な変化を見なくなる）。
    frac = 0.26 + max(0.0, float(p["angle"]) - 40.0) / 220.0
    c.coords["D"] = (bx + (ax - bx) * frac, by + (ay - by) * frac)
    c.coords["E"] = (cx + (ax - cx) * frac, cy + (ay - cy) * frac)
    c.steps.append("辺AB、AC上に、BD ＝ CE となる点D、Eをとる")
    for a_, m_, b_ in (("A", "D", "B"), ("A", "E", "C")):
        c.facts.add(collinear(a_, m_, b_))
        c.collinear_order.append((a_, m_, b_))
    equal = seg_eq(seg("B", "D"), seg("C", "E"))
    c.facts.add(equal)
    c.givens.append(equal)
    for x, y in (("A", "B"), ("A", "C"), ("D", "C"), ("B", "E")):
        c.connect(x, y)
    c.connect("B", "C", shared=True)
    c.description = (
        "AB ＝ AC である二等辺三角形ABCで、辺AB上に点D、辺AC上に点Eを、"
        "BD ＝ CE となるようにとり、点Dと点C、点Bと点Eをそれぞれ結んだ"
    )
    return c
