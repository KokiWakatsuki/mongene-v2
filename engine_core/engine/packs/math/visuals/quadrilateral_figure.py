"""四角形・合同な三角形まわりの図。

★**この単元も図なしだった。** 「平行四辺形DEFGで、DE=16cm、∠E=41°であるとき、
辺FGの長さと∠Gの大きさを求めよ」——どの辺が対辺でどの角が対角かは、図があれば
一目で分かる。ことばだけだと、頂点の並びから四角形を組み立て直すことになる。

**図を出してはいけない問いもある。** 「∠B=∠C のとき二等辺三角形といえるか」
「対角線が等しく垂直に交わるとき、どんな四角形か」のように**判定そのものが答え**
である問いは、縮尺どおりの図を出すと答えが図に書いてあることになる。そういうセルは
図を付けない（判断の理由は family の source_desc に書く）。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.visuals.geometry_figure import render_construction_svg


def parallelogram_svg(
    names: str, side_label: str, angle_label: str,
    x_side_label: str, x_angle_label: str,
) -> str:
    """平行四辺形（対辺に平行の印・となり合う角に名前）（g2_l46.find_value Lv1）。

    `names` は4頂点（この順に一周する）。`side_label`/`angle_label` が与えられた辺と角、
    `x_side_label`/`x_angle_label` が求める対辺と対角。
    """
    a, b, c, d = names
    coords = {a: (0.0, 0.0), b: (3.6, 0.0), c: (4.8, 2.4), d: (1.2, 2.4)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, d), (d, a)],
        "parallel_groups": [[(a, b), (d, c)], [(b, c), (a, d)]],
        # 名前の無い印は出さない（与えられた値と紛らわしい）。
        "angle_marks": [
            m for m in ([b, a, c, angle_label], [d, c, a, x_angle_label]) if m[3]
        ],
        "segment_labels": [
            t for t in ([a, b, side_label], [c, d, x_side_label]) if t[2]
        ],
    }
    return render_construction_svg(params)


def quadrilateral_with_diagonals_svg(
    names: str, o: str, *, kind: str,
    diagonal_label: str = "", x_label: str = "",
) -> str:
    """対角線をひいた四角形（正方形・長方形・ひし形）（g2_l49.find_value Lv1）。

    `kind` は "square"／"rectangle"／"rhombus"。対角線の交点が `o`。
    """
    a, b, c, d = names
    if kind == "rhombus":
        coords = {a: (0.0, -2.2), b: (3.0, 0.0), c: (0.0, 2.2), d: (-3.0, 0.0)}
        equal = [[(a, b), (b, c), (c, d), (d, a)]]
    elif kind == "rectangle":
        coords = {a: (0.0, 0.0), b: (4.4, 0.0), c: (4.4, 2.6), d: (0.0, 2.6)}
        equal = []
    else:  # square
        coords = {a: (0.0, 0.0), b: (3.4, 0.0), c: (3.4, 3.4), d: (0.0, 3.4)}
        equal = [[(a, b), (b, c), (c, d), (d, a)]]
    coords[o] = (
        (coords[a][0] + coords[c][0]) / 2, (coords[a][1] + coords[c][1]) / 2
    )
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, d), (d, a), (a, c), (b, d)],
        "segment_labels": [
            t for t in ([[a, c, diagonal_label]] if diagonal_label else [])
            + ([[o, b, x_label]] if x_label else [])
        ],
    }
    if equal:
        params["equal_groups"] = equal
    return render_construction_svg(params)


def congruent_triangles_svg(
    first: str, second: str, side_label: str, angle_label: str,
) -> str:
    """合同な2つの三角形を並べた図（g2_l36.find_value Lv1）。

    対応する順に頂点を並べる（△ABC≡△LMN なら A↔L、B↔M、C↔N）。
    2つ目は少し傾けて置く——同じ向きに並べると「同じ図をもう一度描いた」ように
    見えて、対応を読み取る問題にならない。
    """
    a, b, c = first
    l, m, n = second
    base = {"A": (0.0, 0.0), "B": (3.2, 0.0), "C": (1.1, 2.4)}
    coords = {a: base["A"], b: base["B"], c: base["C"]}
    # 2つ目は 155° 回して右に置く（合同だが向きが違う）。
    t = math.radians(155)
    dx = 6.4
    for name, key in ((l, "A"), (m, "B"), (n, "C")):
        x, y = base[key]
        coords[name] = (dx + x * math.cos(t) - y * math.sin(t),
                        1.6 + x * math.sin(t) + y * math.cos(t))
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, a), (l, m), (m, n), (n, l)],
        # **求めるほうには名前を付けない。** 問題文に無い記号（x・y）を図に足すと、
        # 本文と図で呼び名が食い違う。与えられた値だけを書けば、対応は頂点の名前で
        # 読み取れる（それを読み取ることがこの問題の中身）。
        "angle_marks": [[b, a, c, angle_label]],
        "segment_labels": [[a, b, side_label]],
    }
    return render_construction_svg(params)


def equilateral_svg(names: str, side_label: str, angle_label: str) -> str:
    """正三角形（3辺に同じ印）（g2_l43.find_value Lv1）。"""
    a, b, c = names
    coords = {a: (0.0, 0.0), b: (3.4, 0.0), c: (1.7, 3.4 * math.sqrt(3) / 2)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, a)],
        "equal_groups": [[(a, b), (b, c), (c, a)]],
        "angle_marks": [[a, b, c, angle_label]],
        "segment_labels": [[a, b, side_label]],
    }
    return render_construction_svg(params)


def equal_area_transform_svg(names: str, q: str, area_label: str) -> str:
    """等積変形の配置（g2_l50.find_value Lv2）。

    四角形 LMNP で、頂点 P を通り対角線 LN に平行な直線をひき、辺 MN の延長との
    交点を Q とする。**延長線を引くところまで図に描く**——ことばだけだと
    「辺MNの延長」がどちらへ伸びるのかが読み取りにくい。
    """
    l, m, n, p = names
    coords = {l: (0.0, 2.6), m: (0.4, 0.0), n: (3.6, 0.0), p: (4.6, 2.2)}
    # Q は直線 MN（x 軸）上で、P を通り LN に平行な直線との交点。
    lx, ly = coords[l]
    nx, ny = coords[n]
    px, py = coords[p]
    dx, dy = nx - lx, ny - ly
    t = (coords[m][1] - py) / dy
    coords[q] = (px + dx * t, 0.0)
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(l, m), (m, n), (n, p), (p, l), (l, n), (p, q), (n, q)],
        "parallel_groups": [[(l, n), (p, q)]],
        "segment_labels": [[l, m, area_label]] if area_label else [],
    }
    return render_construction_svg(params)


def triangle_with_altitude_svg(
    apex: str, b: str, c: str, foot: str,
    side_labels: list[tuple[str, str, str]] = (),
    *, angle_marks: list[list[Any]] = (), equal_legs: bool = False,
    apex_x: float = 0.0,
) -> str:
    """三角形に頂点から底辺へ垂線を引いた図（g3_l53 の各レベル）。"""
    coords = {apex: (apex_x, 3.2), b: (-2.8, 0.0), c: (2.8, 0.0), foot: (apex_x, 0.0)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(apex, b), (apex, c), (b, c), (apex, foot)],
        "right_angles": [[foot, apex, c]],
        "segment_labels": [list(t) for t in side_labels],
    }
    if equal_legs:
        params["equal_groups"] = [[(apex, b), (apex, c)]]
    if angle_marks:
        params["angle_marks"] = [list(m) for m in angle_marks]
    return render_construction_svg(params)


def quadrilateral_with_one_diagonal_svg(
    names: str, side_labels: list[tuple[str, str, str]] = ()
) -> str:
    """対角線を1本ひいた四角形（g3_l52.proof Lv3）。

    ∠PQR が直角であることを**示す**問題なので、直角の印は描かない
    （描いたら結論を図に書いたことになる）。三角形の形も直角に見えないよう、
    与えられた3辺の長さのとおりには描かない。
    """
    a, b, c, d = names
    coords = {a: (0.0, 2.8), b: (0.6, 0.0), c: (4.2, 0.4), d: (3.8, 3.2)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, d), (d, a), (a, c)],
        "segment_labels": [list(t) for t in side_labels],
    }
    return render_construction_svg(params)


def plain_triangle_svg(names: str, side_labels: list[tuple[str, str, str]] = ()) -> str:
    """3辺の長さだけを書いた三角形（g3_l52.proof Lv3）。

    「∠PQR が直角であることを説明せよ」という問題なので、**直角の印は描かないし、
    直角に見える形にも描かない**（描いたら結論を図に書いたことになる）。
    """
    a, b, c = names
    coords = {a: (0.0, 0.0), b: (3.8, 0.6), c: (1.6, 3.0)}
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [(a, b), (b, c), (c, a)],
        "segment_labels": [list(t) for t in side_labels],
    }
    return render_construction_svg(params)


__all__ = [
    "congruent_triangles_svg",
    "equal_area_transform_svg",
    "equilateral_svg",
    "parallelogram_svg",
    "plain_triangle_svg",
    "quadrilateral_with_diagonals_svg",
    "quadrilateral_with_one_diagonal_svg",
    "triangle_with_altitude_svg",
]
