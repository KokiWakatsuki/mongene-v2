"""円周角の証明に使う構成カタログ（g3_l49）。

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ。円周上の点は
「中心から半径だけ離れた、指定した角度の位置」にとるので、**どちらの弧の上にあるか**は
手順が決めている（座標を測って同じ側に見えると判定したのではない）。
"""
from __future__ import annotations

from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction


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


__all__ = ["circle_diameter", "circle_two_chords"]
