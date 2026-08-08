"""合同の証明に使う構成カタログ（docs/proof_engine_design_2026-08-08.md §5）。

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ（座標から
測らない）。だから「解き方が違う問題」は、**手順の組合せを変えること**で出てくる。
"""
from __future__ import annotations

from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction


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
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]), 0.0)
    c.point_on_perpendicular_bisector("A", "B", "C", offset=-float(p["offset"]) - 1.0)
    c.midpoint_of("M", "B", "C")
    for x, y in (("A", "B"), ("A", "C"), ("B", "C"), ("A", "M")):
        c.connect(x, y)
    c.connect("A", "M", shared=True)
    return c
