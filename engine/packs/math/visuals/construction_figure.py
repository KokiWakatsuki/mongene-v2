"""基本作図（form: construction）の図を描く。

この form の図は2枚組である。

- **問題図**: 与えられたものだけ（線分・角・直線と点）。答えは何も描かない。
- **模範解答図**: 問題図に、コンパスの弧と作図した線を重ねたもの。
  `GraphAnswer.solution_svg_ref` に入り、開示制御の対象になる。

作図の図は**弧が交わって見える**ことが生命線である。半径が小さいと2つの弧が
交わらず、「交点をとる」という手順が図の上で成立しない。そこで弧の半径は必ず
交点ができる大きさから構成し（例: 垂直二等分線なら線分の長さの 0.7 倍＝半分より大きい）、
弧の角度範囲も交点を内側に含むように計算する。ここは目で見て決めるところなので、
`scratchpad/draw_construction_cells.py` で PNG に起こして確認している。

座標→画素の写像は**上限つきの等倍**にする（枠に合わせて必ず引き伸ばすのではない）。
引き伸ばすと、長さの違う線分がすべて同じ大きさに描かれてしまい、図の見た目の
多様性が消えるからである。

色に情報を載せない（すべて黒）。太さだけで、与えられた線／作図線／弧を区別する。
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext

_W, _H = 460, 360
_MARGIN = 46
_MAX_SCALE = 30.0          # 画素/単位の上限（小さい図を無理に引き伸ばさない）
_MIN_SPAN = 6.0            # 世界座標での最小の広がり（点だけの図が巨大にならないように）

_STROKE = "#000000"
_W_GIVEN = 1.7             # 与えられた線・作図した線（同じ太さ＝解答図として自然）
_W_ARC = 0.9               # コンパスの弧（細い）
_ARC_SAMPLES = 48

Pt = tuple[float, float]


# ---------------------------------------------------------------------------
# ベクトル
# ---------------------------------------------------------------------------
def _sub(a: Pt, b: Pt) -> Pt:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Pt, b: Pt) -> Pt:
    return (a[0] + b[0], a[1] + b[1])


def _mul(a: Pt, k: float) -> Pt:
    return (a[0] * k, a[1] * k)


def _norm(a: Pt) -> float:
    return math.hypot(a[0], a[1])


def _unit(a: Pt) -> Pt:
    n = _norm(a) or 1.0
    return (a[0] / n, a[1] / n)


def _deg(a: Pt) -> float:
    return math.degrees(math.atan2(a[1], a[0]))


def circle_intersections(c1: Pt, r1: float, c2: Pt, r2: float) -> list[Pt]:
    """2円の交点（無ければ空リスト）。作図の「弧の交点」を図の上で確定させる。"""
    d = _norm(_sub(c2, c1))
    if d < 1e-9 or d > r1 + r2 or d < abs(r1 - r2):
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = r1 * r1 - a * a
    if h2 < 0:
        return []
    h = math.sqrt(h2)
    ux, uy = _unit(_sub(c2, c1))
    mx, my = c1[0] + ux * a, c1[1] + uy * a
    return [(mx - uy * h, my + ux * h), (mx + uy * h, my - ux * h)]


# ---------------------------------------------------------------------------
# scene の要素（辞書で表す。recipe/solver からは組み立て関数だけを使う）
# ---------------------------------------------------------------------------
def point(at: Pt, name: str = "") -> dict[str, Any]:
    return {"kind": "point", "at": (float(at[0]), float(at[1])), "name": name}


def segment(a: Pt, b: Pt) -> dict[str, Any]:
    return {"kind": "segment", "a": (float(a[0]), float(a[1])), "b": (float(b[0]), float(b[1]))}


def line(p: Pt, d: Pt, name: str = "") -> dict[str, Any]:
    return {"kind": "line", "p": (float(p[0]), float(p[1])), "d": _unit(d), "name": name}


def ray(p: Pt, through: Pt) -> dict[str, Any]:
    """頂点 p から点 through の向きへ、少し延ばした半直線（角の辺）。"""
    d = _unit(_sub(through, p))
    end = _add(through, _mul(d, 0.18 * _norm(_sub(through, p))))
    return {"kind": "segment", "a": (float(p[0]), float(p[1])), "b": (float(end[0]), float(end[1]))}


def arc(c: Pt, r: float, a0: float, a1: float) -> dict[str, Any]:
    return {"kind": "arc", "c": (float(c[0]), float(c[1])), "r": float(r), "a0": a0, "a1": a1}


def arc_through(c: Pt, r: float, targets: list[Pt], pad: float = 14.0) -> dict[str, Any]:
    """中心 c 半径 r の弧を、`targets` の向きを内側に含むように張る。

    弧が「交点をまたいで」描かれていないと、交点が弧の端に乗って読めない。
    """
    angles = sorted(_deg(_sub(t, c)) for t in targets)
    if len(angles) == 1:
        return arc(c, r, angles[0] - pad, angles[0] + pad)
    # 角度差が 180 度を超える場合は反対回りに張る（例: 真上と真下）
    if angles[-1] - angles[0] > 180.0:
        angles = sorted((a + 360.0) % 360.0 for a in angles)
    return arc(c, r, angles[0] - pad, angles[-1] + pad)


# ---------------------------------------------------------------------------
# 投影（世界座標 → 画素）
# ---------------------------------------------------------------------------
def _scene_bbox(elements: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for el in elements:
        if el["kind"] == "point":
            xs.append(el["at"][0])
            ys.append(el["at"][1])
        elif el["kind"] == "segment":
            xs.extend([el["a"][0], el["b"][0]])
            ys.extend([el["a"][1], el["b"][1]])
        elif el["kind"] == "arc":
            cx, cy, r = el["c"][0], el["c"][1], el["r"]
            a0, a1 = el["a0"], el["a1"]
            for i in range(9):
                t = math.radians(a0 + (a1 - a0) * i / 8)
                xs.append(cx + r * math.cos(t))
                ys.append(cy + r * math.sin(t))
        elif el["kind"] == "line":
            xs.append(el["p"][0])
            ys.append(el["p"][1])
    if not xs:
        return (-1.0, -1.0, 1.0, 1.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _projector(elements: list[dict[str, Any]]):
    x0, y0, x1, y1 = _scene_bbox(elements)
    w = max(x1 - x0, _MIN_SPAN)
    h = max(y1 - y0, _MIN_SPAN)
    scale = min((_W - 2 * _MARGIN) / w, (_H - 2 * _MARGIN) / h, _MAX_SCALE)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def to_px(x: float, y: float) -> Pt:
        return (_W / 2 + (x - cx) * scale, _H / 2 - (y - cy) * scale)

    return to_px, scale


def _clip_line(p: Pt, d: Pt) -> tuple[Pt, Pt] | None:
    """画素座標の直線（点 p・向き d）を描画枠へ切り詰める（Liang-Barsky）。"""
    lo, hi = -1e9, 1e9
    pad = 6.0
    for num, den in (
        (p[0] - pad, -d[0]), (_W - pad - p[0], d[0]),
        (p[1] - pad, -d[1]), (_H - pad - p[1], d[1]),
    ):
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = num / den
        if den > 0:
            hi = min(hi, t)
        else:
            lo = max(lo, t)
    if lo >= hi:
        return None
    return (_add(p, _mul(d, lo)), _add(p, _mul(d, hi)))


def _on_px_segment(pt: Pt, a: Pt, b: Pt) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    if n2 < 1e-9:
        return False
    t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / n2
    if not -0.02 < t < 1.02:
        return False
    return math.hypot(a[0] + t * dx - pt[0], a[1] + t * dy - pt[1]) < 2.0


def _label_pos(pt: Pt, incident: list[Pt], center: Pt) -> Pt:
    """点名を、その点から出ている線の**すきまが最も広い向き**に置く（線に埋もれない）。"""
    if not incident:
        dx, dy = pt[0] - center[0], pt[1] - center[1]
        n = math.hypot(dx, dy) or 1.0
        return (pt[0] + dx / n * 15.0, pt[1] + dy / n * 15.0 + 4.5)
    angles = sorted(math.atan2(d[1], d[0]) for d in incident)
    gaps = [(angles[(i + 1) % len(angles)] - a) % (2 * math.pi) for i, a in enumerate(angles)]
    if len(angles) == 1:
        theta = angles[0] + math.pi
    else:
        best = max(range(len(gaps)), key=lambda i: gaps[i])
        theta = angles[best] + gaps[best] / 2
    return (pt[0] + math.cos(theta) * 15.0, pt[1] + math.sin(theta) * 15.0 + 4.5)


def render_scene(
    elements: list[dict[str, Any]], *, bbox_elements: list[dict[str, Any]] | None = None
) -> str:
    """scene（要素の並び）を SVG 文字列にする。`<text>` は点名・直線名だけ。

    `bbox_elements` を渡すと、**描かないがフレームには入れる**要素を指定できる。
    問題図と模範解答図で枠取りを揃えるために使う（同じ図が別の縮尺で出ると、
    「どこに何が足されたのか」が読み取りにくくなる）。
    """
    to_px, scale = _projector(bbox_elements if bbox_elements is not None else elements)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'width="{_W}" height="{_H}">',
        f'<rect x="0" y="0" width="{_W}" height="{_H}" fill="#ffffff" stroke="none"/>',
    ]
    drawn: list[tuple[Pt, Pt]] = []   # 画素座標の線分（ラベルの向き決めに使う）
    texts: list[tuple[Pt, str]] = []

    # 弧を先に描く（作図線・点の下になるように）
    for el in elements:
        if el["kind"] != "arc":
            continue
        cx, cy, r = el["c"][0], el["c"][1], el["r"]
        pts = []
        for i in range(_ARC_SAMPLES + 1):
            t = math.radians(el["a0"] + (el["a1"] - el["a0"]) * i / _ARC_SAMPLES)
            pts.append(to_px(cx + r * math.cos(t), cy + r * math.sin(t)))
        body = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        parts.append(
            f'<polyline points="{body}" fill="none" stroke="{_STROKE}" '
            f'stroke-width="{_W_ARC}"/>'
        )

    for el in elements:
        if el["kind"] == "segment":
            a, b = to_px(*el["a"]), to_px(*el["b"])
            drawn.append((a, b))
            parts.append(
                f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
                f'stroke="{_STROKE}" stroke-width="{_W_GIVEN}"/>'
            )
        elif el["kind"] == "line":
            p = to_px(*el["p"])
            d = (el["d"][0], -el["d"][1])
            clipped = _clip_line(p, d)
            if clipped is None:
                continue
            a, b = clipped
            drawn.append((a, b))
            parts.append(
                f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" '
                f'stroke="{_STROKE}" stroke-width="{_W_GIVEN}"/>'
            )
            if el["name"]:
                # 直線名は線の端（枠の内側）へ、線と垂直にずらして置く。枠のどちら側へ
                # ずらすかは**内側に残るほう**を選ぶ（下辺で切れた直線の名前が枠外に
                # はみ出して消えるのを、実際に SVG を見て見つけた）。
                tip = _add(b, _mul(d, -20.0))
                cand = [
                    (tip[0] - d[1] * 14.0, tip[1] + d[0] * 14.0 + 4.5),
                    (tip[0] + d[1] * 14.0, tip[1] - d[0] * 14.0 + 4.5),
                ]
                lx, ly = max(
                    cand,
                    key=lambda q: min(q[0] - 10, _W - 10 - q[0], q[1] - 14, _H - 10 - q[1]),
                )
                lx = min(max(lx, 12.0), _W - 12.0)
                ly = min(max(ly, 16.0), _H - 10.0)
                texts.append(((lx, ly), el["name"]))

    px_points = [(to_px(*el["at"]), el["name"]) for el in elements if el["kind"] == "point"]
    if px_points:
        cx = sum(p[0][0] for p in px_points) / len(px_points)
        cy = sum(p[0][1] for p in px_points) / len(px_points)
    else:
        cx, cy = _W / 2, _H / 2
    for pt, name in px_points:
        parts.append(f'<circle cx="{pt[0]:.2f}" cy="{pt[1]:.2f}" r="3.1" fill="{_STROKE}"/>')
        if not name:
            continue
        incident: list[Pt] = []
        for a, b in drawn:
            if not _on_px_segment(pt, a, b):
                continue
            for other in (a, b):
                v = _sub(other, pt)
                if _norm(v) > 4.0:
                    incident.append(_unit(v))
        texts.append((_label_pos(pt, incident, (cx, cy)), name))

    for (tx, ty), name in texts:
        parts.append(
            f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="15" text-anchor="middle" '
            f'fill="{_STROKE}">{name}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# 3つの基本作図の「弧の組」。作図手順そのものを図にしたもの。
# ---------------------------------------------------------------------------
def perp_bisector_arcs(a: Pt, b: Pt) -> tuple[list[dict[str, Any]], list[Pt]]:
    """線分 ab の垂直二等分線をひく弧（両端から等しい半径・半分より大きく取る）。"""
    r = 0.66 * _norm(_sub(b, a))
    cross = circle_intersections(a, r, b, r)
    arcs = [arc_through(a, r, cross, pad=12.0), arc_through(b, r, cross, pad=12.0)]
    return arcs, cross


def angle_bisector_arcs(o: Pt, p1: Pt, p2: Pt) -> tuple[list[dict[str, Any]], list[Pt], Pt]:
    """∠p1-o-p2 の二等分線をひく弧。戻り値は (弧, 2辺上の点, 二等分線上の交点)。"""
    r0 = 0.62 * min(_norm(_sub(p1, o)), _norm(_sub(p2, o)))
    q1 = _add(o, _mul(_unit(_sub(p1, o)), r0))
    q2 = _add(o, _mul(_unit(_sub(p2, o)), r0))
    r1 = 0.68 * _norm(_sub(q2, q1))
    cross = circle_intersections(q1, r1, q2, r1)
    far = max(cross, key=lambda p: _norm(_sub(p, o)))
    arcs = [
        arc_through(o, r0, [q1, q2], pad=12.0),
        arc_through(q1, r1, [far], pad=20.0),
        arc_through(q2, r1, [far], pad=20.0),
    ]
    return arcs, [q1, q2], far


def perpendicular_arcs(p: Pt, foot: Pt, d: Pt) -> tuple[list[dict[str, Any]], list[Pt], Pt]:
    """点 p から直線（足 foot・向き d）へ垂線をひく弧。戻り値は (弧, 直線上の2点, 交点)。"""
    u = _unit(d)
    dist = _norm(_sub(p, foot))
    s = max(0.75 * dist, 2.4)
    r0 = math.hypot(dist, s)
    m1 = _add(foot, _mul(u, -s))
    m2 = _add(foot, _mul(u, s))
    r1 = 0.80 * r0 if 0.80 * r0 > s * 1.05 else s * 1.15
    cross = circle_intersections(m1, r1, m2, r1)
    if dist > 1e-6:
        far = max(cross, key=lambda q: _norm(_sub(q, p)))
    else:
        far = cross[0]
    arcs = [
        arc_through(p, r0, [m1, m2], pad=14.0),
        arc_through(m1, r1, [far], pad=20.0),
        arc_through(m2, r1, [far], pad=20.0),
    ]
    return arcs, [m1, m2], far


# ---------------------------------------------------------------------------
# セルごとの2枚組（問題図・模範解答図）。枠取りは両者で揃える。
# ---------------------------------------------------------------------------
def _pair(given: list[dict[str, Any]], added: list[dict[str, Any]]) -> tuple[str, str]:
    full = given + added
    return render_scene(given, bbox_elements=full), render_scene(full)


def _bisector_ray(o: Pt, target: Pt, reach: float) -> dict[str, Any]:
    """頂点 o から target の向きへ長さ reach の線分（角の二等分線は半直線で描く）。"""
    return segment(o, _add(o, _mul(_unit(_sub(target, o)), reach)))


def figures_perp_bisector_segment(a: Pt, b: Pt, na: str, nb: str) -> tuple[str, str]:
    """線分と、その垂直二等分線（g1_l41 Lv1）。"""
    given = [segment(a, b), point(a, na), point(b, nb)]
    arcs, cross = perp_bisector_arcs(a, b)
    added = [*arcs, line(cross[0], _sub(cross[1], cross[0]))]
    return _pair(given, added)


def figures_two_points(a: Pt, b: Pt, na: str, nb: str) -> tuple[str, str]:
    """2点だけの図と、その垂直二等分線（g1_l44 Lv2）。線分は解答側で補助的にひく。"""
    given = [point(a, na), point(b, nb)]
    arcs, cross = perp_bisector_arcs(a, b)
    added = [segment(a, b), *arcs, line(cross[0], _sub(cross[1], cross[0]))]
    return _pair(given, added)


def figures_two_points_and_line(
    a: Pt, b: Pt, na: str, nb: str, lp: Pt, ld: Pt, lname: str, p: Pt, pname: str
) -> tuple[str, str]:
    """2点と直線ℓ。解答は垂直二等分線と、ℓ との交点 P（g1_l41 Lv2）。"""
    given = [line(lp, ld, lname), point(a, na), point(b, nb)]
    arcs, cross = perp_bisector_arcs(a, b)
    added = [segment(a, b), *arcs, line(cross[0], _sub(cross[1], cross[0])), point(p, pname)]
    return _pair(given, added)


def figures_angle(o: Pt, x: Pt, y: Pt, no: str, nx: str, ny: str) -> tuple[str, str]:
    """角と、その二等分線（g1_l42 Lv1）。"""
    given = [ray(o, x), ray(o, y), point(o, no), point(x, nx), point(y, ny)]
    arcs, _sides, far = angle_bisector_arcs(o, x, y)
    reach = 1.12 * max(_norm(_sub(x, o)), _norm(_sub(y, o)))
    added = [*arcs, _bisector_ray(o, far, reach)]
    return _pair(given, added)


def figures_angle_with_chord(
    o: Pt, x: Pt, y: Pt, no: str, nx: str, ny: str, p: Pt, pname: str
) -> tuple[str, str]:
    """角と2辺の端を結ぶ線分。解答は二等分線とその線分との交点 P（g1_l42 Lv2）。"""
    given = [ray(o, x), ray(o, y), segment(x, y), point(o, no), point(x, nx), point(y, ny)]
    arcs, _sides, far = angle_bisector_arcs(o, x, y)
    reach = 1.25 * _norm(_sub(p, o))
    added = [*arcs, _bisector_ray(o, far, reach), point(p, pname)]
    return _pair(given, added)


def figures_point_and_line(
    p: Pt, lp: Pt, ld: Pt, lname: str, pname: str, foot: Pt
) -> tuple[str, str]:
    """直線と点。解答はその点を通る垂線（g1_l43 Lv1）。"""
    given = [line(lp, ld, lname), point(p, pname)]
    arcs, _feet, far = perpendicular_arcs(p, foot, ld)
    added = [*arcs, line(p, _sub(far, p)) if _norm(_sub(far, p)) > 1e-6 else line(p, (-ld[1], ld[0]))]
    return _pair(given, added)


def figures_point_line_foot(
    p: Pt, lp: Pt, ld: Pt, lname: str, pname: str, foot: Pt, hname: str
) -> tuple[str, str]:
    """直線と点。解答は垂線・垂線の足 H・距離を表す線分 PH（g1_l43 Lv2）。"""
    given = [line(lp, ld, lname), point(p, pname)]
    arcs, _feet, far = perpendicular_arcs(p, foot, ld)
    added = [*arcs, line(p, _sub(far, p)), segment(p, foot), point(foot, hname)]
    return _pair(given, added)


def figures_three_points(
    a: Pt, b: Pt, c: Pt, na: str, nb: str, nc: str, center: Pt, pname: str
) -> tuple[str, str]:
    """3点。解答は垂直二等分線2本とその交点 P（g1_l44 Lv3）。"""
    given = [point(a, na), point(b, nb), point(c, nc)]
    arcs1, cross1 = perp_bisector_arcs(a, b)
    arcs2, cross2 = perp_bisector_arcs(b, c)
    added = [
        segment(a, b), segment(b, c),
        *arcs1, *arcs2,
        line(cross1[0], _sub(cross1[1], cross1[0])),
        line(cross2[0], _sub(cross2[1], cross2[0])),
        point(center, pname),
    ]
    return _pair(given, added)


def figures_triangle_bisector(
    a: Pt, b: Pt, c: Pt, na: str, nb: str, nc: str, p: Pt, pname: str
) -> tuple[str, str]:
    """三角形。解答は頂点の角の二等分線と対辺との交点 P（g1_l44 Lv4）。"""
    given = [
        segment(a, b), segment(b, c), segment(c, a),
        point(a, na), point(b, nb), point(c, nc),
    ]
    arcs, _sides, far = angle_bisector_arcs(a, b, c)
    reach = 1.05 * _norm(_sub(p, a))
    added = [*arcs, _bisector_ray(a, far, reach), point(p, pname)]
    return _pair(given, added)


# ---------------------------------------------------------------------------
# 図ビルダ入口（family の `visual_builder` から呼ばれる）
# ---------------------------------------------------------------------------
def render_construction_given(mr: "MR", ctx: "CellContext") -> str:
    """問題図は recipe が組んで `context_slots["figure_svg"]` に入れてある。

    ここで組み直すと recipe が引いたパラメータと食い違う恐れがあるので取り出すだけ。
    """
    return str(mr.context_slots["figure_svg"])


register_visual("math.construction_figure")(render_construction_given)


__all__ = [
    "render_scene",
    "point",
    "segment",
    "line",
    "ray",
    "arc",
    "arc_through",
    "circle_intersections",
    "perp_bisector_arcs",
    "angle_bisector_arcs",
    "perpendicular_arcs",
    "figures_perp_bisector_segment",
    "figures_two_points",
    "figures_two_points_and_line",
    "figures_angle",
    "figures_angle_with_chord",
    "figures_point_and_line",
    "figures_point_line_foot",
    "figures_three_points",
    "figures_triangle_bisector",
    "render_construction_given",
]
