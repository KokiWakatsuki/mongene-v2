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
import re
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


_DEG = re.compile(r"^(\d+(?:\.\d+)?)\s*°$")


def _angle_at(v: tuple[float, float], a: tuple[float, float],
              b: tuple[float, float]) -> float:
    v1 = (a[0] - v[0], a[1] - v[1])
    v2 = (b[0] - v[0], b[1] - v[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    if not n:
        return 0.0
    d = (v1[0] * v2[0] + v1[1] * v2[1]) / n
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


def _concyclic_coords(
    p_: str, q: str, r: str, s: str, equal_label: str, spr_label: str
) -> dict[str, tuple[float, float]]:
    """P, Q を同じ大きさ θ で見込む弧の上に R, S を置く。

    弦 PQ の半分を a とすると、円周角 θ の円は半径 a/sin θ・中心が弦から
    a·cos θ/sin θ 離れたところ。**中心がどちら側かは数値で確かめる**（θ が鈍角だと
    向きが変わるので、式で決め打ちにしない）。

    S は弧の真ん中あたりに置き、R は **∠SPR が与えられた値になる位置**を弧の上で
    二分探索して決める。見つからない（∠SPR が大きすぎる）ときは、いちばん近い位置。
    """
    a = 2.6
    m_eq = _DEG.match(equal_label.strip())
    theta = math.radians(float(m_eq.group(1))) if m_eq else math.radians(70.0)
    theta = max(math.radians(20.0), min(math.radians(160.0), theta))
    radius = a / math.sin(theta)
    offset = a * math.cos(theta) / math.sin(theta)
    P, Q = (-a, 0.0), (a, 0.0)

    def arc_point(centre_y: float, t: float) -> tuple[float, float]:
        return (radius * math.cos(t), centre_y + radius * math.sin(t))

    # 中心の向きを数値で選ぶ（弧の上の点から見込む角が θ になるほう）。
    best_centre = None
    for centre_y in (-offset, offset):
        top = (0.0, centre_y + radius)
        if top[1] <= 0.05:
            continue
        if abs(_angle_at(top, P, Q) - math.degrees(theta)) < 0.5:
            best_centre = centre_y
            break
    if best_centre is None:
        best_centre = -offset
    # 弧の上を、P 側から Q 側へ向かう媒介変数の範囲で取る（y > 0 の側）。
    t_p = math.atan2(0.0 - best_centre, -a)
    t_q = math.atan2(0.0 - best_centre, a)
    if t_p < t_q:
        t_p += 2 * math.pi
    # t_q → t_p が y>0 の弧（中心が下なら上側）。両端は P, Q なので内側を使う。
    def at(frac: float) -> tuple[float, float]:
        return arc_point(best_centre, t_q + (t_p - t_q) * frac)

    if at(0.5)[1] <= 0.05:      # 選んだ弧が下側だったら反対に回す
        def at(frac: float) -> tuple[float, float]:  # noqa: F811
            return arc_point(best_centre, t_q - (t_p - t_q) * frac)

    m_spr = _DEG.match(spr_label.strip())
    want = float(m_spr.group(1)) if m_spr else 0.0
    if not want:
        return {p_: P, q: Q, r: at(0.75), s: at(0.35)}
    # ★**S の位置は1つに決め打ちしない。** ∠SPR が θ に近い（弧の端まで使う）ときは
    # S を P 寄りに置かないと届かない。いくつか試して、いちばん近いものを採る
    # （0.35 固定だと 40seed のうち 2件で 37.5° になっていた）。
    best: tuple[tuple[bool, float], tuple[float, float], tuple[float, float]] | None = None
    for f_s in (0.12, 0.18, 0.25, 0.32, 0.40, 0.48):
        s_try = at(f_s)
        if s_try[1] < 0.25:
            continue
        lo, hi = f_s + 0.05, 0.99
        for _ in range(40):
            mid = (lo + hi) / 2
            if _angle_at(P, s_try, at(mid)) < want:
                lo = mid
            else:
                hi = mid
        r_try = at((lo + hi) / 2)
        err = abs(_angle_at(P, s_try, r_try) - want)
        if r_try[1] < 0.25:
            continue
        # ★同じ角度になる置き方は何通りもある。**端（P・Q）から離れたものを採る**——
        # 近いと点とラベルが重なって、どの角のラベルか読めない
        # （∠XUW=43°・θ=76° の回で W が U の 65px 手前に来ていた）。
        room = min(math.dist(pt, end)
                   for pt in (s_try, r_try) for end in (P, Q))
        score = (err > 0.5, -room)      # まず角度が合うもの、次に広いもの
        if best is None or score < best[0]:
            best = (score, r_try, s_try)
    if best is None:
        return {p_: P, q: Q, r: at(0.75), s: at(0.35)}
    return {p_: P, q: Q, r: best[1], s: best[2]}


def concyclic_svg(
    p_: str, q: str, r: str, s: str,
    equal_label: str, spr_label: str, x_label: str,
) -> str:
    """直線PQの同じ側にある2点R、Sから、PQを同じ大きさで見込む図（g3_l48.find_value Lv2）。

    円周角の定理の逆を使う問題なので、**円は描かない**（描いたら「同一円周上に
    ある」という結論を図に書いたことになる）。R と S が PQ の同じ側にあることと、
    2つの角が等しいことだけを示す。

    ★**「2つの角が等しい」を図でも等しく描く。** 以前は座標を
    `r:(-1.0,2.6), s:(1.4,2.2)` に決め打ちしていたので、∠PRQ と ∠PSQ は
    **85.8° と 89.8°**（等しくもない）なのに、どちらにも「76°」と印字していた。
    この問題の前提そのものが図から読めない状態だった（図つきの逆翻訳で発覚し、
    点の座標から測って確認）。

    R と S を**PQ を同じ大きさで見込む弧の上**に置くと、∠PRQ = ∠PSQ が図でも
    成り立つ（円は描かないが、位置は弧の上にとる）。∠SPR も与えられた値になるよう、
    弧の上で数値的に探す。**厳密に描くと ∠SQR（＝答え）も測れてしまうが、
    それは角度を追う図では避けられない**——前提が読めないほうが実害が大きい。
    """
    coords = _concyclic_coords(p_, q, r, s, equal_label, spr_label)
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
