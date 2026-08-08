"""構成から図を描く（docs/proof_engine_design_2026-08-08.md §5）。

`geometry/construct.py` が持つ点の座標と線分をそのまま描く。**等しい辺には印を付ける**
——市販の問題集の図がそうなっていて、印が無いと問題文だけで条件を読むことになり、
図が図として働かない。印は「同じ本数の斜線」で表す（色に情報を載せない）。

答えそのもの（証明の結論）は描かない。たとえば「△ABC≡△ADC を示せ」の図に、合同を
表す印は付けない。描いてよいのは**与えられた条件**だけである。
"""
from __future__ import annotations

import math
from typing import Any

_W, _H = 420, 340
_MARGIN = 46


def _project(coords: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """図の座標を、余白つきで画面いっぱいに収まる画素座標へ移す（縦横比は保つ）。"""
    xs = [p[0] for p in coords.values()]
    ys = [p[1] for p in coords.values()]
    w = max(xs) - min(xs) or 1.0
    h = max(ys) - min(ys) or 1.0
    scale = min((_W - 2 * _MARGIN) / w, (_H - 2 * _MARGIN) / h)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return {
        name: (_W / 2 + (x - cx) * scale, _H / 2 - (y - cy) * scale)
        for name, (x, y) in coords.items()
    }


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


def _label_offset(
    name: str, pt: tuple[float, float], centroid: tuple[float, float]
) -> tuple[float, float]:
    """点名は図の重心と反対側に置く（線分の上に文字が乗らないように）。"""
    dx, dy = pt[0] - centroid[0], pt[1] - centroid[1]
    n = math.hypot(dx, dy) or 1.0
    return pt[0] + dx / n * 15.0, pt[1] + dy / n * 15.0 + 4.0


def render_construction_svg(params: dict[str, Any]) -> str:
    """params: coords（点→座標）／segments（描く線分）／equal_groups（等しい辺の組）。

    `equal_groups` は [[("A","B"),("A","D")], [("B","C"),("C","D")]] のような形で、
    グループごとに斜線の本数を変える（1本目のグループは1本、2本目は2本…）。
    """
    coords = {str(k): (float(v[0]), float(v[1])) for k, v in params["coords"].items()}
    px = _project(coords)
    cx = sum(p[0] for p in px.values()) / len(px)
    cy = sum(p[1] for p in px.values()) / len(px)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}" '
        f'width="{_W}" height="{_H}">',
        f'<rect x="0" y="0" width="{_W}" height="{_H}" fill="none" stroke="none"/>',
    ]
    for a, b in params["segments"]:
        (x1, y1), (x2, y2) = px[str(a)], px[str(b)]
        parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="#000000" stroke-width="1.6"/>'
        )
    for i, group in enumerate(params.get("equal_groups", [])):
        for a, b in group:
            parts.extend(_tick_marks(px[str(a)], px[str(b)], i + 1))
    for name, pt in px.items():
        parts.append(f'<circle cx="{pt[0]:.2f}" cy="{pt[1]:.2f}" r="3.2" fill="#000000"/>')
        lx, ly = _label_offset(name, pt, (cx, cy))
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="14" text-anchor="middle" '
            f'fill="#000000">{name}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


__all__ = ["render_construction_svg"]
