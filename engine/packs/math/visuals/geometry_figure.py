"""構成から図を描く（docs/proof_engine_design_2026-08-08.md §5）。

`geometry/construct.py` が持つ点の座標と線分をそのまま描く。**等しい辺には印を付ける**
——市販の問題集の図がそうなっていて、印が無いと問題文だけで条件を読むことになり、
図が図として働かない。印は「同じ本数の斜線」で表す（色に情報を載せない）。

答えそのもの（証明の結論）は描かない。たとえば「△ABC≡△ADC を示せ」の図に、合同を
表す印は付けない。描いてよいのは**与えられた条件**だけである。
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext

_W, _H = 420, 340
_MARGIN = 46


def _projector(
    coords: dict[str, tuple[float, float]],
    circles: list[tuple[tuple[float, float], float]] = (),
):
    """図の座標を、余白つきで画面いっぱいに収まる画素座標へ移す（縦横比は保つ）。

    円は点より外へ広がるので、**円の外接する正方形も収まる範囲に入れる**
    （入れないと円が枠からはみ出して切れる）。戻り値は (写す関数, 倍率)。
    """
    xs = [p[0] for p in coords.values()]
    ys = [p[1] for p in coords.values()]
    for (ox, oy), r in circles:
        xs += [ox - r, ox + r]
        ys += [oy - r, oy + r]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    scale = min((_W - 2 * _MARGIN) / w, (_H - 2 * _MARGIN) / h)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def to_px(x: float, y: float) -> tuple[float, float]:
        return (_W / 2 + (x - cx) * scale, _H / 2 - (y - cy) * scale)

    return to_px, scale


def _tick_marks(p1: tuple[float, float], p2: tuple[float, float], count: int) -> list[str]:
    """線分の中央に、等しい辺を表す斜線を `count` 本つける。"""
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    # 線分に垂直な向き（斜線は少し傾けて描く＝教科書の見た目）。
    nx, ny = -uy, ux
    parts = []
    for i in range(count):
        off = (i - (count - 1) / 2) * 5.0
        bx, by = mx + ux * off, my + uy * off
        parts.append(
            f'<line x1="{bx + nx * 5 - ux * 2:.2f}" y1="{by + ny * 5 - uy * 2:.2f}" '
            f'x2="{bx - nx * 5 + ux * 2:.2f}" y2="{by - ny * 5 + uy * 2:.2f}" '
            f'stroke="#000000" stroke-width="1.2"/>'
        )
    return parts


def _on_segment(
    pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> bool:
    """点が線分の途中（端点を除く）に乗っているか。ラベルの向きを決めるためだけに使う。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    if n2 < 1e-9:
        return False
    t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / n2
    if not 0.02 < t < 0.98:
        return False
    return math.hypot(a[0] + t * dx - pt[0], a[1] + t * dy - pt[1]) < 1.5


def _label_offset(
    pt: tuple[float, float],
    centroid: tuple[float, float],
    incident: list[tuple[float, float]],
) -> tuple[float, float]:
    """点名を、その点から出ている線分の**すきまが最も広い向き**に置く。

    最初は「図の重心と反対側」に置いていたが、それだと**交点のラベルが読めない**
    （X字型の交点 O は重心そのものなので向きが定まらず、文字が線の上に乗った）。
    図に起こして初めて分かった——ゲートは図の中身を見ないので、ここは目で見て直すしかない。

    `incident` はその点から出ている線分の向き（単位ベクトル）。すきまの二等分方向に
    置けば、交点でも端点でも線を避けられる。線が1本も無いときだけ重心の反対側に置く。
    """
    if not incident:
        dx, dy = pt[0] - centroid[0], pt[1] - centroid[1]
        n = math.hypot(dx, dy) or 1.0
        return pt[0] + dx / n * 15.0, pt[1] + dy / n * 15.0 + 4.0
    angles = sorted(math.atan2(dy, dx) for dx, dy in incident)
    gaps = [(angles[(i + 1) % len(angles)] - a) % (2 * math.pi) for i, a in enumerate(angles)]
    best = max(range(len(gaps)), key=lambda i: gaps[i])
    theta = angles[best] + gaps[best] / 2
    return pt[0] + math.cos(theta) * 15.0, pt[1] + math.sin(theta) * 15.0 + 4.0


def render_construction_svg(params: dict[str, Any]) -> str:
    """params: coords（点→座標）／segments（描く線分）／equal_groups（等しい辺の組）。

    `equal_groups` は [[("A","B"),("A","D")], [("B","C"),("C","D")]] のような形で、
    グループごとに斜線の本数を変える（1本目のグループは1本、2本目は2本…）。
    """
    coords = {str(k): (float(v[0]), float(v[1])) for k, v in params["coords"].items()}
    circles = [
        ((float(c[0][0]), float(c[0][1])), float(c[1])) for c in params.get("circles", [])
    ]
    to_px, scale = _projector(coords, circles)
    px = {name: to_px(x, y) for name, (x, y) in coords.items()}
    cx = sum(p[0] for p in px.values()) / len(px)
    cy = sum(p[1] for p in px.values()) / len(px)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'width="{_W}" height="{_H}">',
        f'<rect x="0" y="0" width="{_W}" height="{_H}" fill="none" stroke="none"/>',
    ]
    # 円は先に描く（線分やラベルの下になるように）。
    for (ox, oy), r in circles:
        ox_px, oy_px = to_px(ox, oy)
        parts.append(
            f'<circle cx="{ox_px:.2f}" cy="{oy_px:.2f}" r="{r * scale:.2f}" '
            f'fill="none" stroke="#000000" stroke-width="1.6"/>'
        )
    for a, b in params["segments"]:
        (x1, y1), (x2, y2) = px[str(a)], px[str(b)]
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="#000000" stroke-width="1.6"/>'
        )
    for i, group in enumerate(params.get("equal_groups", [])):
        for a, b in group:
            parts.extend(_tick_marks(px[str(a)], px[str(b)], i + 1))
    # 各点から線が出ていく向き。端点だけでなく、**線分の途中にある点**も拾う
    # （X字型の交点 O は、どの線分の端点でもないが4方向に線が出ている）。
    # ここは見た目の話なので、座標を見て判定してよい（事実を作っているのではない）。
    incident: dict[str, list[tuple[float, float]]] = {name: [] for name in px}
    for a, b in params["segments"]:
        pa, pb = px[str(a)], px[str(b)]
        for name, pt in px.items():
            if name == str(a) or name == str(b):
                other = pb if name == str(a) else pa
                n = math.hypot(other[0] - pt[0], other[1] - pt[1]) or 1.0
                incident[name].append(((other[0] - pt[0]) / n, (other[1] - pt[1]) / n))
            elif _on_segment(pt, pa, pb):
                for other in (pa, pb):
                    n = math.hypot(other[0] - pt[0], other[1] - pt[1]) or 1.0
                    incident[name].append(((other[0] - pt[0]) / n, (other[1] - pt[1]) / n))
    for name, pt in px.items():
        parts.append(f'<circle cx="{pt[0]:.2f}" cy="{pt[1]:.2f}" r="3.2" fill="#000000"/>')
        lx, ly = _label_offset(pt, (cx, cy), incident[name])
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="14" text-anchor="middle" '
            f'fill="#000000">{name}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def render_construction(mr: "MR", ctx: "CellContext") -> str:
    """図ビルダとしての入口（family の `visual_builder` から呼ばれる）。

    証明セルの図は**構成そのもの**なので、recipe が図を組んだときに
    `context_slots["figure_svg"]` に入れてある。ここは取り出すだけでよい
    （もう一度組み直すと、recipe が引いたパラメータと食い違う恐れがある）。
    """
    return str(mr.context_slots["figure_svg"])


register_visual("math.geometry_construction")(render_construction)


__all__ = ["render_construction", "render_construction_svg"]
