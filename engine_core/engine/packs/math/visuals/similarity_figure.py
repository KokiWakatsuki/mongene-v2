"""相似・平行線と比・三平方まわりの図。

★**このあたりの単元も図が1枚も無かった。** 「三角形EFGで、辺EF, EG上に点H, Jがあり、
HJ∥FGである」のように、点がどの辺のどこにあるかを毎回ことばで組み立てていた。
相似の単元は「どの三角形とどの三角形が対応しているか」を図で見ることに意味がある。

座標は `geometry_figure.render_construction_svg` に渡す。ここでは配置を決めるだけ。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.visuals.geometry_figure import render_construction_svg


def triangle_with_parallel_svg(
    apex: str, b: str, c: str, p: str, q: str,
    ratio: float, *, side_labels: list[tuple[str, str, str]] = (),
    parallel: bool = True,
) -> str:
    """三角形の2辺上に点をとり、底辺に平行な線分を引いた図。

    `apex` が頂点、`b`/`c` が底辺の両端、`p` が辺 apex-b 上、`q` が辺 apex-c 上の点。
    `ratio` は頂点から測った内分の比（0〜1）。`side_labels` は [(端1, 端2, 名前)] で
    線分に長さを書き入れる。`parallel` が False なら平行の印を出さない
    （「平行かどうかを調べる」問題では、平行だと決めつけた図にしない）。
    """
    coords = {apex: (0.0, 3.4), b: (-2.6, 0.0), c: (3.0, 0.0)}
    ax, ay = coords[apex]
    for name, end in ((p, b), (q, c)):
        ex, ey = coords[end]
        coords[name] = (ax + (ex - ax) * ratio, ay + (ey - ay) * ratio)
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(apex, b), (apex, c), (b, c), (p, q)],
    }
    if parallel:
        params["parallel_groups"] = [[(p, q), (b, c)]]
    params["segment_labels"] = [list(t) for t in side_labels]
    return render_construction_svg(params)


def x_shape_similar_svg(
    a: str, b: str, c: str, d: str, o: str,
    side_labels: list[tuple[str, str, str]] = (),
) -> str:
    """AB∥CD の2線分が点Oで交わる「X字型」の相似（g3_l40.find_value Lv2）。

    A と B が上の線分、C と D が下の線分。O は AC と BD の交点。
    """
    coords = {
        a: (-2.2, 2.2), b: (1.6, 2.2),
        c: (2.9, -2.2), d: (-2.9, -2.2),
        o: (0.0, 0.0),
    }
    # O は AC と BD の交点になるように、上下の線分を O 中心で向かい合わせに置く。
    coords[c] = (-coords[a][0] * 1.35, -coords[a][1] * 1.35)
    coords[d] = (-coords[b][0] * 1.35, -coords[b][1] * 1.35)
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (c, d), (a, c), (b, d)],
        "parallel_groups": [[(a, b), (d, c)]],
        "segment_labels": [list(t) for t in side_labels],
    }
    return render_construction_svg(params)


def three_parallels_svg(
    lines: tuple[str, str, str], left: tuple[str, str, str], right: tuple[str, str, str],
    side_labels: list[tuple[str, str, str]] = (),
) -> str:
    """3本の平行な直線を2本の直線が横切る図（g3_l42.find_value Lv3）。

    `lines` は3直線の名前、`left`/`right` はそれぞれの直線と交わる点の名前
    （上から順）。線分の比が読めるよう、間隔は与えられた長さに合わせず等間隔にせず、
    上の間隔を下より広くとる（比が 1:1 に見えると問題にならない）。
    """
    ys = (2.4, 0.4, -2.2)
    coords: dict[str, tuple[float, float]] = {}
    for i, (ln, lp, rp) in enumerate(zip(lines, left, right, strict=True)):
        y = ys[i]
        coords[lp] = (-1.8 + 0.5 * i, y)
        coords[rp] = (1.4 + 0.9 * i, y)
        coords[f"_l{i}a"] = (-3.6, y)
        coords[f"_l{i}b"] = (3.4, y)
    segments = [(f"_l{i}a", f"_l{i}b") for i in range(3)]
    segments += [(left[0], left[2]), (right[0], right[2])]
    params: dict[str, Any] = {
        "coords": coords,
        "segments": segments,
        "parallel_groups": [[(f"_l{i}a", f"_l{i}b") for i in range(3)]],
        "hidden_points": [f"_l{i}{s}" for i in range(3) for s in "ab"],
        "free_labels": [
            [f"_l{i}b", lines[i], 16, -6] for i in range(3)
        ],
        "segment_labels": [list(t) for t in side_labels],
    }
    return render_construction_svg(params)


def midpoint_connector_svg(
    apex: str, b: str, c: str, p: str, q: str, base_label: str
) -> str:
    """三角形の2辺の中点を結ぶ線分（中点連結定理・g3_l44）。"""
    return triangle_with_parallel_svg(
        apex, b, c, p, q, 0.5,
        side_labels=[(b, c, base_label)] if base_label else [],
    )


def isosceles_with_altitude_svg(
    apex: str, b: str, c: str, foot: str,
    leg_label: str, base_label: str,
) -> str:
    """二等辺三角形に頂点から底辺への垂線を引いた図（g3_l53.find_value Lv3）。"""
    coords = {apex: (0.0, 3.2), b: (-2.6, 0.0), c: (2.6, 0.0), foot: (0.0, 0.0)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(apex, b), (apex, c), (b, c), (apex, foot)],
        "equal_groups": [[(apex, b), (apex, c)]],
        "right_angles": [[foot, apex, c]],
        "segment_labels": [[apex, b, leg_label], [b, c, base_label]],
    }
    return render_construction_svg(params)


def _square_with_inscribed(
    side: float, cut: float, outer: tuple[str, str, str, str],
    inner: tuple[str, str, str, str],
) -> dict[str, Any]:
    """1辺 `side` の正方形の各辺を `cut : side-cut` に分ける点を結んだ配置。

    外側の正方形の4頂点が `outer`、内側にできる正方形の4頂点が `inner`。
    三平方の面積証明はどの型もこの形（外側の正方形の取り方だけが違う）。
    """
    p1, p2, p3, p4 = outer
    corners = {p1: (0.0, 0.0), p2: (side, 0.0), p3: (side, side), p4: (0.0, side)}
    order = [p1, p2, p3, p4]
    coords: dict[str, tuple[float, float]] = dict(corners)
    for i, name in enumerate(inner):
        sx, sy = corners[order[i]]
        ex, ey = corners[order[(i + 1) % 4]]
        t = cut / side
        coords[name] = (sx + (ex - sx) * t, sy + (ey - sy) * t)
    segments = [(order[i], order[(i + 1) % 4]) for i in range(4)]
    segments += [(inner[i], inner[(i + 1) % 4]) for i in range(4)]
    return {
        "coords": coords,
        "segments": segments,
        # 直角は**外側の正方形の角**にある（三角形の直角をはさむ2辺が正方形の辺）。
        # 印の1つ目が頂点なので、角の頂点を先頭に置くこと。
        "right_angles": [
            [order[(i + 1) % 4], inner[i], inner[(i + 1) % 4]] for i in range(4)
        ],
    }


def pythagoras_proof_svg(
    proof_id: str, letters: tuple[str, str, str],
    outer: str | None, inner: str | None,
) -> str:
    """三平方の定理を面積で示す配置（g3_l51.proof Lv3/Lv4）。

    ★**この単元は 13 問すべてが図なしだった。** 「合同な直角三角形4つを、斜辺が
    それぞれ1辺になるように並べて、1辺の長さが y の正方形PQRSをつくる。内側にできる
    四角形TUVWは、1辺の長さが q - a の正方形になる」——この配置を頭の中だけで
    組み立てられる中学生はいない。点検でも「図がなければ読解できない」と挙がった。

    型は3つ。`inner_square`（斜辺を1辺とする正方形の内側）、`outer_square`
    （直角をはさむ2辺の和を1辺とする正方形の内側）、`trapezoid`（台形2つ分）。
    辺の比は 3:4 に固定する（直角と大小関係がはっきり見える比）。
    """
    a_len, b_len = 3.0, 4.0
    hyp = math.hypot(a_len, b_len)
    la, lb, lc = letters
    # 記号が無い（誘導なし Lv4）ときは、頂点に名前を出さずに辺の長さだけ書く。
    o = tuple(outer) if outer else tuple(f"_o{i}" for i in range(4))
    n = tuple(inner) if inner else tuple(f"_i{i}" for i in range(4))
    hide = [] if outer else [*o, *n]

    if proof_id.startswith("trapezoid"):
        # 上底 a、下底 b、高さ a+b の台形。斜辺2本で直角二等辺三角形ができる。
        h = a_len + b_len
        names = (o[0], o[1], o[2], o[3]) if outer else o
        e, f, g, hh = names
        i_name = inner[0] if inner else "_i0"
        coords = {
            e: (0.0, h), f: (a_len, h), g: (b_len, 0.0), hh: (0.0, 0.0),
            # I は辺 EH 上で EI = 下底の長さ（E は上、H は下）。
            i_name: (0.0, h - b_len),
        }
        params: dict[str, Any] = {
            "coords": coords,
            "segments": [(e, f), (f, g), (g, hh), (hh, e), (f, i_name), (i_name, g)],
            "right_angles": [[e, f, hh], [hh, e, g]],
            "segment_labels": [
                [e, f, la], [hh, g, lb], [f, i_name, lc], [i_name, g, lc],
            ],
            "hidden_points": hide,
        }
        return render_construction_svg(params)

    if proof_id.startswith("outer_square"):
        # 1辺 a+b の正方形。各辺を a:b に分ける点を結ぶと1辺 c の正方形になる。
        params = _square_with_inscribed(a_len + b_len, a_len, o, n)
        params["segment_labels"] = [
            [o[0], n[0], la], [n[0], o[1], lb], [n[0], n[1], lc],
        ]
    else:
        # 1辺 c の正方形。各辺を a:b に分ける点を結ぶと1辺 b-a の正方形になる。
        params = _square_with_inscribed(hyp, a_len, o, n)
        # 斜辺の長さは**別の辺**に書く（下の辺には a と q がすでに載っている）。
        params["segment_labels"] = [
            [o[0], n[0], la], [n[0], o[1], lb], [o[3], o[0], lc],
        ]
    params["hidden_points"] = hide
    return render_construction_svg(params)


__all__ = [
    "isosceles_with_altitude_svg",
    "midpoint_connector_svg",
    "pythagoras_proof_svg",
    "three_parallels_svg",
    "triangle_with_parallel_svg",
    "x_shape_similar_svg",
]
