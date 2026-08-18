"""円まわりの図（円周角と中心角・2本の弦の交点・おうぎ形）。

★**円の単元は図が1枚も無かった。** 「円Hの周上に点Lがある。弧JKに対する中心角
∠JHK=168° のとき、同じ弧JKに対する円周角∠JLKの大きさを求めよ」のように、
どの点が円周上のどこにあるかを全部ことばで述べていた。円周角の問題は
「同じ弧を見ている」ことが図で一目で分かることに意味があるので、ここは図が要る。

座標は `geometry_figure.render_construction_svg` に渡す（点・線分・円・角の印を
受け取る宣言的な描き手）。ここでは**円周上のどこに点を置くか**を決める。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.visuals.geometry_figure import render_construction_svg

_R = 3.0  # 図の座標系での円の半径（画素へは描き手が写す）


def _on_circle(deg: float) -> tuple[float, float]:
    """中心を原点とする円周上の点（角度は度・反時計回り・右向きが 0°）。"""
    t = math.radians(deg)
    return (_R * math.cos(t), _R * math.sin(t))


def inscribed_angle_svg(
    center: str, a: str, b: str, p: str, central_deg: float,
    central_label: str, inscribed_label: str,
) -> str:
    """中心角と円周角を同じ弧に対して示す図（g3_l47.find_value Lv1）。

    弧 AB の中心角を `central_deg` に取り、その弧を見込む円周角の頂点 P を
    **反対側の弧の真ん中**に置く（どちらの弧を見ているかが図で分かるように）。
    """
    half = central_deg / 2
    # 弧 AB を上側に取る。A と B は中心から見て ±half の位置。
    deg_a, deg_b = 90 - half, 90 + half
    coords = {
        center: (0.0, 0.0),
        a: _on_circle(deg_a),
        b: _on_circle(deg_b),
        p: _on_circle(270.0),          # 反対側の弧の中央
    }
    params: dict[str, Any] = {
        "coords": coords,
        "circles": [[[0.0, 0.0], _R]],
        "segments": [(center, a), (center, b), (p, a), (p, b)],
        "angle_marks": [
            [center, a, b, central_label],
            [p, a, b, inscribed_label],
        ],
    }
    return render_construction_svg(params)


def two_chords_svg(
    a: str, b: str, c: str, d: str, t: str,
    bac_deg: float, acd_deg: float,
    bac_label: str, acd_label: str, x_label: str,
) -> str:
    """円周上の4点と、交わる2本の弦（対角線）の図（g3_l47.find_value Lv3）。

    A, B, C, D はこの順に円周上。∠BAC は弧 BC の、∠ACD は弧 AD の円周角なので、
    **弧の大きさから4点の位置が決まる**（図と本文の数が必ず一致する）。
    交わるのは対角線 AC と BD で、その交点が T。
    """
    arc_bc = 2 * bac_deg
    arc_ad = 2 * acd_deg
    rest = 360.0 - arc_bc - arc_ad          # 弧AB と 弧CD の合計
    arc_ab = arc_cd = rest / 2
    # A から反時計回りに B, C, D の順に並べる（この順に円周上）。
    deg_a = 140.0
    deg_b = deg_a - arc_ab
    deg_c = deg_b - arc_bc
    deg_d = deg_c - arc_cd
    coords = {
        a: _on_circle(deg_a), b: _on_circle(deg_b),
        c: _on_circle(deg_c), d: _on_circle(deg_d),
    }
    # T = 対角線 AC と BD の交点。
    (ax, ay), (bx, by) = coords[a], coords[b]
    (cx, cy), (dx, dy) = coords[c], coords[d]
    det = (cx - ax) * (dy - by) - (cy - ay) * (dx - bx)
    s = ((bx - ax) * (dy - by) - (by - ay) * (dx - bx)) / det
    coords[t] = (ax + s * (cx - ax), ay + s * (cy - ay))
    params: dict[str, Any] = {
        "coords": coords,
        "circles": [[[0.0, 0.0], _R]],
        "segments": [(a, c), (b, d)],
        "angle_marks": [
            [a, b, c, bac_label],
            [c, a, d, acd_label],
            [t, a, b, x_label],
        ],
    }
    return render_construction_svg(params)


def sector_svg(
    center: str, a: str, b: str, central_deg: float,
    radius_label: str, angle_label: str,
) -> str:
    """おうぎ形（半径と中心角に名前）（g1_l46.find_value）。

    弧そのものは描き手が円を全部描いてしまうので、ここでは**円は描かず**、
    半径2本と、弧を表す折れ線（円周上の点を細かく取る）で作る。
    """
    half = central_deg / 2
    deg_a, deg_b = 90 - half, 90 + half
    coords: dict[str, tuple[float, float]] = {
        center: (0.0, 0.0), a: _on_circle(deg_a), b: _on_circle(deg_b),
    }
    # 弧は 24 分割の折れ線で描く（中間点は名前も丸も出さない）。
    arc_names = []
    for i in range(1, 24):
        name = f"_arc{i}"
        coords[name] = _on_circle(deg_a + (deg_b - deg_a) * i / 24)
        arc_names.append(name)
    chain = [a, *arc_names, b]
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(center, a), (center, b)]
        + [(chain[i], chain[i + 1]) for i in range(len(chain) - 1)],
        "angle_marks": [[center, a, b, angle_label]],
        # 半径の長さは半径の**まん中**に書く（端に書くと点の名前とぶつかる）。
        "segment_labels": [[center, a, radius_label]],
        "hidden_points": arc_names,
    }
    return render_construction_svg(params)


def circle_terms_svg(center: str, a: str, b: str, angle_label: str) -> str:
    """円の中心と、円周上の2点を結ぶ2本の半径（g1_l45.knowledge の用語の図）。"""
    coords = {center: (0.0, 0.0), a: _on_circle(55.0), b: _on_circle(150.0)}
    params: dict[str, Any] = {
        "coords": coords,
        "circles": [[[0.0, 0.0], _R]],
        "segments": [(center, a), (center, b)],
        "angle_marks": [[center, a, b, angle_label]],
    }
    return render_construction_svg(params)


def concyclic_svg(
    p_: str, q: str, r: str, s: str,
    equal_label: str, spr_label: str, x_label: str,
) -> str:
    """直線PQの同じ側にある2点R、Sから、PQを同じ大きさで見込む図（g3_l48.find_value Lv2）。

    円周角の定理の逆を使う問題なので、**円は描かない**（描いたら「同一円周上に
    ある」という結論を図に書いたことになる）。R と S が PQ の同じ側にあることと、
    2つの角が等しいことだけを示す。
    """
    coords = {
        p_: (-2.6, 0.0), q: (2.6, 0.0),
        r: (-1.0, 2.6), s: (1.4, 2.2),
    }
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(p_, q), (p_, r), (r, q), (p_, s), (s, q), (p_, r), (r, s)],
        "angle_marks": [
            [r, p_, q, equal_label],
            [s, p_, q, equal_label],
            [p_, s, r, spr_label],
            [q, s, r, x_label],
        ],
    }
    return render_construction_svg(params)


def equal_division_polygon_svg(labels: str, vertex: str, a: str, b: str, x_label: str) -> str:
    """円周を n 等分した点を結んだ多角形（g3_l50.find_value Lv3）。

    どの点とどの点のあいだに弧がいくつ入るかは、図で数えるのがいちばん確かで、
    そこがこの問題の中身。`vertex` で `a` と `b` を見込む角に名前を付ける。
    """
    n = len(labels)
    coords = {
        name: _on_circle(90.0 + 360.0 * i / n) for i, name in enumerate(labels)
    }
    params: dict[str, Any] = {
        "coords": coords,
        "circles": [[[0.0, 0.0], _R]],
        "segments": [(labels[i], labels[(i + 1) % n]) for i in range(n)]
        + [(vertex, a), (vertex, b)],
        "angle_marks": [[vertex, a, b, x_label]],
    }
    return render_construction_svg(params)


__all__ = [
    "circle_terms_svg",
    "concyclic_svg",
    "equal_division_polygon_svg",
    "inscribed_angle_svg",
    "sector_svg",
    "two_chords_svg",
]
