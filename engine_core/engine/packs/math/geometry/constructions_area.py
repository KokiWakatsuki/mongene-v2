"""平行線と面積（等積変形）の証明に使う構成カタログ（g2_l50）。

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ。
"""
from __future__ import annotations

from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import parallel


@register_construction("trapezoid_diagonals")
def trapezoid_diagonals(p: dict[str, Any]) -> Construction:
    """AD ∥ BC の台形 ABCD に、対角線 AC と BD を引いた図（等積変形の定番）。

    BC を共通の底辺とみると、A と D は BC に平行な直線 AD の上にあるので
    △ABC と △DBC は高さが等しい。
    """
    c = Construction()
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]) + 2.0, 0.0)
    top = float(p["angle"]) / 30.0 + 1.2
    c.free_point("A", float(p["offset"]) / 2.0, top)
    c.free_point("D", float(p["offset"]) / 2.0 + float(p["base"]) / 1.6 + 0.6, top)
    # 平行であることは**手順が保証している**（同じ高さに2点を置いた）。
    c.facts.add(parallel(("A", "D"), ("B", "C")))
    c.givens.append(parallel(("A", "D"), ("B", "C")))
    for x, y in (("A", "B"), ("B", "C"), ("C", "D"), ("A", "D"), ("A", "C"), ("B", "D")):
        c.connect(x, y)
    c.description = "右の図で、四角形ABCDは AD ∥ BC の台形であり、対角線ACとBDを引いた"
    return c


@register_construction("triangle_median")
def triangle_median(p: dict[str, Any]) -> Construction:
    """△ABC に、底辺 BC の中点 M と中線 AM を引いた図。

    「M は BC の中点だから BM ＝ CM」→「底辺が等しく高さが等しいので面積が等しい」
    という2段の筋道が出る（中線が三角形の面積を2等分する）。

    **点を増やせば深い証明が出る、とはならない。** はじめは台形に中点を足した5点の図
    （さらに平行線上に3つの頂点を並べて等積を transitive でつなぐ図）を試したが、
    どちらも図の質のフィルタに全部落ちた——頂点が並ぶと、そこを見込む角
    （∠ABD など）が 18°の下限を割る。等積変形の連鎖を図にするには、
    **図として読める配置が先に要る**。ここは4点に戻して深さ2を中点から取っている。
    """
    c = Construction()
    c.free_point("B", 0.0, 0.0)
    c.free_point("C", float(p["base"]) + 2.4, 0.0)
    c.free_point("A", float(p["offset"]) / 2.0 + 0.5, float(p["angle"]) / 22.0 + 1.6)
    c.midpoint_of("M", "B", "C")
    for x, y in (("A", "B"), ("B", "C"), ("C", "A"), ("A", "M")):
        c.connect(x, y)
    c.connect("A", "M", shared=True)
    c.description = "右の図で、△ABCの辺BCの中点をMとし、点Aと点Mを結んだ"
    return c


__all__ = ["trapezoid_diagonals", "triangle_median"]
