"""平面図形の「読む」図（Phase E 端物・g1_l37 / g2_l32 / g2_l44 の graph_table Lv1）。

3セルが共有する型は「**図の中の要素を記号で答える**」で、図に要るものは
  - 点と直線と垂線（点と直線の距離を表す線分はどれか）
  - 何本かの直線と、それぞれが横切る直線となす角（どれが平行か）
  - 直角三角形（斜辺と直角をはさむ2辺はどれか）
の3つ。どれも方眼も座標軸も要らない**素の平面図**なので、`graph.py`（座標平面）や
`plane_transform.py`（方眼上の多角形）には載らない。ここに小さく1本起こす。

描画の約束（既存の図資産と同じ）:
  - 色に情報を載せない（黒の実線・太さと線種だけで区別＝モノクロ印刷可・N-4 適合）
  - 点名・角の大きさは図の中に文字で書く（`VisualPlan.labels` で whitelist する）
  - **答えそのものは描かない**（どの線分が距離かを示す印は付けない・平行の印も付けない）
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext

_W, _H = 420, 300
_STROKE = '<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#000000" stroke-width="{w}"/>'


def _svg_open(width: int = _W, height: int = _H) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="none" stroke="none"/>',
    ]


def _line(x1: float, y1: float, x2: float, y2: float, *, w: float = 1.5) -> str:
    return _STROKE.format(x1=x1, y1=y1, x2=x2, y2=y2, w=w)


def _dot(x: float, y: float) -> str:
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="#000000"/>'


def _text(x: float, y: float, s: str, *, size: int = 13, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" '
        f'fill="#000000">{s}</text>'
    )


def _right_angle_mark(vx: float, vy: float, ax: float, ay: float, bx: float, by: float) -> str:
    """頂点 (vx,vy) から2方向 (ax,ay)/(bx,by) へ向かう内側に直角の記号を描く。"""
    m = 12.0
    ux, uy = ax - vx, ay - vy
    wx, wy = bx - vx, by - vy
    nu = math.hypot(ux, uy) or 1.0
    nw = math.hypot(wx, wy) or 1.0
    ux, uy = ux / nu * m, uy / nu * m
    wx, wy = wx / nw * m, wy / nw * m
    return (
        f'<polyline points="{vx + ux:.2f},{vy + uy:.2f} '
        f'{vx + ux + wx:.2f},{vy + uy + wy:.2f} {vx + wx:.2f},{vy + wy:.2f}" '
        f'fill="none" stroke="#000000" stroke-width="1.2"/>'
    )


# ---------------------------------------------------------------------------
# g1_l37.graph_table Lv1: 点と直線、垂線の足、直線上の2点
# ---------------------------------------------------------------------------
def render_point_and_line_svg(params: dict[str, Any]) -> str:
    """直線ℓ上に3点（垂線の足と左右の点）をとり、点Pから3本の線分を引いた図。

    params: line_name（ℓ/m/n）／point_p・point_foot・point_left・point_right（点名）／
    foot_ratio（垂線の足の横位置 0..1）／height（点Pの高さ px）。
    **どれが距離かは描かない**——直角の記号だけは垂線の定義そのものなので描く
    （問題文が「垂線を引いたとき、その足を H とする」と言っている＝与えられた条件）。
    """
    parts = _svg_open()
    y_line = 220.0
    x_lo, x_hi = 40.0, 380.0
    parts.append(_line(x_lo, y_line, x_hi, y_line))
    parts.append(_text(x_hi + 12, y_line + 4, str(params["line_name"]), anchor="end"))

    ratio = float(params["foot_ratio"])
    fx = x_lo + (x_hi - x_lo) * ratio
    px, py = fx, y_line - float(params["height"])
    lx = x_lo + (fx - x_lo) * 0.35
    rx = fx + (x_hi - fx) * 0.65

    for x in (lx, fx, rx):
        parts.append(_line(px, py, x, y_line))
    parts.append(_right_angle_mark(fx, y_line, fx, y_line - 20.0, fx + 20.0, y_line))

    for x, name, dy in (
        (lx, str(params["point_left"]), 18.0),
        (fx, str(params["point_foot"]), 18.0),
        (rx, str(params["point_right"]), 18.0),
    ):
        parts.append(_dot(x, y_line))
        parts.append(_text(x, y_line + dy, name))
    parts.append(_dot(px, py))
    parts.append(_text(px, py - 10.0, str(params["point_p"])))

    parts.append("</svg>")
    return "".join(parts)


def render_point_and_line(mr: "MR", ctx: "CellContext") -> str:
    return render_point_and_line_svg(mr.params)


# ---------------------------------------------------------------------------
# g2_l32.graph_table Lv1: 1本の横断線と、それが横切る何本かの直線＋なす角
# ---------------------------------------------------------------------------
def _clip_t(x: float, y: float, dx: float, dy: float, width: float, height: float) -> float:
    """(x,y) から向き (dx,dy) へ進めるとき、図の枠の内側にとどまる最大の距離。

    ラベルの分だけ余白を残す（右 34px・下 22px・左 10px・上 14px）。
    """
    limits = [1e9]
    if dx > 1e-9:
        limits.append((width - 34.0 - x) / dx)
    elif dx < -1e-9:
        limits.append((10.0 - x) / dx)
    if dy > 1e-9:
        limits.append((height - 22.0 - y) / dy)
    elif dy < -1e-9:
        limits.append((14.0 - y) / dy)
    return max(0.0, min(limits))


def render_parallel_candidates_svg(params: dict[str, Any]) -> str:
    """横断線1本と直線 n 本を描き、各交点に「横断線となす角」を度で書く。

    params: transversal_name（横断線の名）／base_name・base_angle（基準の直線と角）／
    names・angles（候補の直線と角）。

    **角は横断線から測って作る**（線の向き＝横断線の向きを angle だけ回したもの）。
    こうしないと図に書いた角度と実際の角度が食い違う（横断線を斜めにして
    「水平からの角」で線を引くと、書いた角と図が合わなくなる——最初に踏んだ）。
    横断線を縦にとると、同位角がそのまま見比べられて図が読みやすい。

    平行の印（矢羽根）は描かない——それを描くと答えが図に出てしまう。
    """
    names = [str(v) for v in params["names"]]
    angles = [float(v) for v in params["angles"]]
    rows = [(str(params["base_name"]), float(params["base_angle"]))] + list(
        zip(names, angles, strict=True)
    )

    width, height = 460, 90 + 58 * len(rows)
    parts = _svg_open(width, height)

    tx = 120.0
    ty1, ty2 = 30.0, float(height - 30)
    parts.append(_line(tx, ty1, tx, ty2, w=1.8))
    parts.append(_text(tx - 14.0, ty2 + 4.0, str(params["transversal_name"]), anchor="end"))

    for i, (name, angle) in enumerate(rows):
        cy = 66.0 + 58.0 * i
        rad = math.radians(angle)
        # 横断線の向き（下向き (0,1)）を angle だけ回した向き。angle=90 で水平。
        dx, dy = math.sin(rad), math.cos(rad)
        # 図の枠からはみ出さないところで線を止める（角が小さいと下へ抜けてしまい、
        # 直線名のラベルごと画面外に出る——最初に踏んだ）。
        t_back = _clip_t(tx, cy, -dx, -dy, width, height)
        t_fwd = _clip_t(tx, cy, dx, dy, width, height)
        back = min(55.0, t_back)
        fwd = min(235.0, t_fwd)
        parts.append(_line(tx - back * dx, cy - back * dy, tx + fwd * dx, cy + fwd * dy))
        parts.append(
            _text(tx + (fwd + 13.0) * dx, cy + (fwd + 13.0) * dy + 4.0, name, anchor="start")
        )
        # 角の記号（横断線の下向きと直線の向きの間に小さな弧）と、その大きさ。
        r = 26.0
        parts.append(
            f'<path d="M {tx:.2f} {cy + r:.2f} A {r:.2f} {r:.2f} 0 0 0 '
            f'{tx + r * dx:.2f} {cy + r * dy:.2f}" fill="none" stroke="#000000" '
            f'stroke-width="1.0"/>'
        )
        bx, by = (dx + 0.0) / 2.0, (dy + 1.0) / 2.0
        nb = math.hypot(bx, by) or 1.0
        parts.append(
            _text(tx + bx / nb * 46.0, cy + by / nb * 46.0 + 4.0, f"{angle:g}°", size=12)
        )

    parts.append("</svg>")
    return "".join(parts)


def render_parallel_candidates(mr: "MR", ctx: "CellContext") -> str:
    return render_parallel_candidates_svg(mr.params)


# ---------------------------------------------------------------------------
# g2_l44.graph_table Lv1: 直角三角形（直角の位置が引かれる）
# ---------------------------------------------------------------------------
def render_right_triangle_svg(params: dict[str, Any]) -> str:
    """直角三角形を1つ描く。頂点名は params の順（直角の頂点は right_angle_index）。

    直角の記号だけを描く（どれが斜辺かの印は描かない＝それが答え）。
    """
    labels = [str(v) for v in params["vertex_labels"]]
    idx = int(params["right_angle_index"])
    leg_a = float(params["leg_a_px"])
    leg_b = float(params["leg_b_px"])

    parts = _svg_open()
    # 直角の頂点を左下に置き、直角をはさむ2辺を右と上に伸ばす。
    vx, vy = 110.0, 230.0
    p_right = (vx + leg_a, vy)
    p_up = (vx, vy - leg_b)
    pts = {idx: (vx, vy)}
    others = [i for i in range(3) if i != idx]
    pts[others[0]] = p_right
    pts[others[1]] = p_up

    ordered = [pts[i] for i in range(3)]
    joined = " ".join(f"{x:.2f},{y:.2f}" for x, y in ordered)
    parts.append(f'<polygon points="{joined}" fill="none" stroke="#000000" stroke-width="1.8"/>')
    parts.append(_right_angle_mark(vx, vy, *p_right, *p_up))

    offsets = {idx: (-14.0, 16.0)}
    offsets[others[0]] = (14.0, 16.0)
    offsets[others[1]] = (-14.0, -8.0)
    for i in range(3):
        x, y = pts[i]
        ox, oy = offsets[i]
        parts.append(_dot(x, y))
        parts.append(_text(x + ox, y + oy, labels[i]))

    parts.append("</svg>")
    return "".join(parts)


def render_right_triangle(mr: "MR", ctx: "CellContext") -> str:
    return render_right_triangle_svg(mr.params)


register_visual("math.point_and_line")(render_point_and_line)
register_visual("math.parallel_candidates")(render_parallel_candidates)
register_visual("math.right_triangle_figure")(render_right_triangle)


__all__ = [
    "render_point_and_line",
    "render_point_and_line_svg",
    "render_parallel_candidates",
    "render_parallel_candidates_svg",
    "render_right_triangle",
    "render_right_triangle_svg",
]
