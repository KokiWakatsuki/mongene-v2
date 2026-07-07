"""TwoDGeometryRenderer（§22.2 完全実装）

平面図形を SVG で描画する。
"""
from __future__ import annotations

import math
from typing import Tuple

import svgwrite

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL


class TwoDGeometryRenderer(VisualComponent):
    def __init__(
        self,
        show_axis: bool = False,
        auto_scale: bool = True,
        arrow_marker: bool = False,
        image_width: int = 400,
        image_height: int = 400,
        margin: int = 20,
    ) -> None:
        self.show_axis = show_axis
        self.auto_scale = auto_scale
        self.arrow_marker = arrow_marker
        self.image_width = image_width
        self.image_height = image_height
        self.margin = margin

    def render(self, dsl: VisualDSL) -> str:
        # --- 内容バウンディングボックスを計算し、有効 viewport とする ---
        xs: list[float] = []
        ys: list[float] = []

        def _add(px, py) -> None:
            xs.append(float(px))
            ys.append(float(py))

        for el in dsl.elements:
            et = el.get("type")
            if et == "point":
                _add(el["x"], el["y"])
            elif et == "text":
                _add(el["x"], el["y"])
            elif et == "angle_label":
                _add(el["vertex"][0], el["vertex"][1])
            elif et == "line_segment":
                _add(el["p1"][0], el["p1"][1])
                _add(el["p2"][0], el["p2"][1])
            elif et == "polygon":
                for v in el["vertices"]:
                    _add(v[0], v[1])
            elif et in ("circle", "arc"):
                cx, cy = el["center"]
                r = el["radius"]
                _add(cx - r, cy - r)
                _add(cx + r, cy + r)
            elif et in ("right_angle_mark", "angle_arc"):
                _add(el["vertex"][0], el["vertex"][1])
                _add(el["p1"][0], el["p1"][1])
                _add(el["p2"][0], el["p2"][1])
            elif et in ("tick_mark", "parallel_mark"):
                _add(el["p1"][0], el["p1"][1])
                _add(el["p2"][0], el["p2"][1])

        if xs and ys:
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            span = max(x_max - x_min, y_max - y_min, 1e-6)
            pad = span * 0.12
            x_min -= pad
            x_max += pad
            y_min -= pad
            y_max += pad
        else:
            # フォールバック: 座標を持つ要素が無ければ従来通り viewport を使う
            x_min, y_min, x_max, y_max = dsl.viewport

        usable_w = self.image_width - 2 * self.margin
        usable_h = self.image_height - 2 * self.margin
        scale_x = usable_w / (x_max - x_min) if x_max != x_min else 1
        scale_y = usable_h / (y_max - y_min) if y_max != y_min else 1
        scale = min(scale_x, scale_y) if self.auto_scale else 1
        content_w = (x_max - x_min) * scale
        content_h = (y_max - y_min) * scale
        off_x = (usable_w - content_w) / 2.0
        off_y = (usable_h - content_h) / 2.0

        def transform(x: float, y: float) -> Tuple[float, float]:
            sx = self.margin + off_x + (x - x_min) * scale
            sy = self.image_height - self.margin - off_y - (y - y_min) * scale
            return sx, sy

        dwg = svgwrite.Drawing(size=(self.image_width, self.image_height))

        if self.show_axis:
            origin = transform(0, 0)
            dwg.add(
                dwg.line(
                    start=(self.margin, origin[1]),
                    end=(self.image_width - self.margin, origin[1]),
                    stroke="gray",
                    stroke_width=0.5,
                )
            )
            dwg.add(
                dwg.line(
                    start=(origin[0], self.margin),
                    end=(origin[0], self.image_height - self.margin),
                    stroke="gray",
                    stroke_width=0.5,
                )
            )

        for el in dsl.elements:
            el_type = el["type"]
            if el_type == "point":
                cx, cy = transform(el["x"], el["y"])
                dwg.add(dwg.circle(center=(cx, cy), r=3, fill="black"))
                if el.get("label"):
                    dwg.add(dwg.text(el["label"], insert=(cx + 5, cy - 5), font_size=14, font_family="Hiragino Sans, sans-serif"))
            elif el_type == "line_segment":
                p1 = transform(*el["p1"])
                p2 = transform(*el["p2"])
                line = dwg.line(start=p1, end=p2, stroke="black", stroke_width=1)
                if el.get("dashed"):
                    line.dasharray([5, 5])
                dwg.add(line)
                if el.get("label"):
                    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                    dwg.add(dwg.text(el["label"], insert=(mx + 3, my - 3), font_size=12, font_family="Hiragino Sans, sans-serif"))
            elif el_type == "polygon":
                points = [transform(*v) for v in el["vertices"]]
                fill = "lightgray" if el.get("filled") else "none"
                dwg.add(
                    dwg.polygon(points=points, fill=fill, stroke="black", stroke_width=1)
                )
                labels = el.get("vertex_labels")
                if labels and points:
                    gx = sum(p[0] for p in points) / len(points)
                    gy = sum(p[1] for p in points) / len(points)
                    for (sx, sy), label in zip(points, labels):
                        dx, dy = sx - gx, sy - gy
                        norm = math.hypot(dx, dy)
                        if norm < 1e-9:
                            ox, oy = 6.0, -6.0
                        else:
                            ox, oy = dx / norm * 14.0, dy / norm * 14.0
                        dwg.add(
                            dwg.text(
                                label,
                                insert=(sx + ox, sy + oy),
                                font_size=14,
                                font_family="Hiragino Sans, sans-serif",
                            )
                        )
            elif el_type == "right_angle_mark":
                vx, vy = transform(*el["vertex"])
                p1x, p1y = transform(*el["p1"])
                p2x, p2y = transform(*el["p2"])
                d = 12.0
                n1 = math.hypot(p1x - vx, p1y - vy)
                n2 = math.hypot(p2x - vx, p2y - vy)
                if n1 > 1e-9 and n2 > 1e-9:
                    u1 = ((p1x - vx) / n1, (p1y - vy) / n1)
                    u2 = ((p2x - vx) / n2, (p2y - vy) / n2)
                    a = (vx + u1[0] * d, vy + u1[1] * d)
                    b = (vx + u1[0] * d + u2[0] * d, vy + u1[1] * d + u2[1] * d)
                    c = (vx + u2[0] * d, vy + u2[1] * d)
                    dwg.add(
                        dwg.polyline(
                            points=[a, b, c],
                            fill="none",
                            stroke="black",
                            stroke_width=1,
                        )
                    )
            elif el_type == "tick_mark":
                p1x, p1y = transform(*el["p1"])
                p2x, p2y = transform(*el["p2"])
                count = int(el.get("count", 1))
                mx, my = (p1x + p2x) / 2, (p1y + p2y) / 2
                length = math.hypot(p2x - p1x, p2y - p1y)
                if length > 1e-9:
                    tx, ty = (p2x - p1x) / length, (p2y - p1y) / length
                    nx, ny = -ty, tx
                    for i in range(count):
                        off = (i - (count - 1) / 2) * 5.0
                        ccx, ccy = mx + tx * off, my + ty * off
                        dwg.add(
                            dwg.line(
                                start=(ccx - nx * 5.0, ccy - ny * 5.0),
                                end=(ccx + nx * 5.0, ccy + ny * 5.0),
                                stroke="black",
                                stroke_width=1,
                            )
                        )
            elif el_type == "angle_arc":
                vx, vy = transform(*el["vertex"])
                p1x, p1y = transform(*el["p1"])
                p2x, p2y = transform(*el["p2"])
                count = int(el.get("count", 1))
                # スクリーン y は下向きなので反転して数学的角度に合わせる
                a1 = math.atan2(-(p1y - vy), p1x - vx)
                a2 = math.atan2(-(p2y - vy), p2x - vx)
                d = a2 - a1
                while d <= -math.pi:
                    d += 2 * math.pi
                while d > math.pi:
                    d -= 2 * math.pi
                for k in range(count):
                    r = 14.0 + 4.0 * k
                    pts = []
                    steps = 16
                    for i in range(steps + 1):
                        t = a1 + d * i / steps
                        px = vx + r * math.cos(t)
                        py = vy - r * math.sin(t)
                        pts.append((px, py))
                    dwg.add(
                        dwg.polyline(
                            points=pts, fill="none", stroke="black", stroke_width=1
                        )
                    )
            elif el_type == "parallel_mark":
                p1x, p1y = transform(*el["p1"])
                p2x, p2y = transform(*el["p2"])
                count = int(el.get("count", 1))
                length = math.hypot(p2x - p1x, p2y - p1y)
                if length > 1e-9:
                    mx, my = (p1x + p2x) / 2, (p1y + p2y) / 2
                    tx, ty = (p2x - p1x) / length, (p2y - p1y) / length
                    nx, ny = -ty, tx
                    s = 5.0
                    for k in range(count):
                        off = (k - (count - 1) / 2) * 6.0
                        cxs, cys = mx + tx * off, my + ty * off
                        tip = (cxs + tx * s, cys + ty * s)
                        arm1 = (cxs - tx * s + nx * s, cys - ty * s + ny * s)
                        arm2 = (cxs - tx * s - nx * s, cys - ty * s - ny * s)
                        dwg.add(
                            dwg.line(
                                start=arm1, end=tip, stroke="black", stroke_width=1
                            )
                        )
                        dwg.add(
                            dwg.line(
                                start=arm2, end=tip, stroke="black", stroke_width=1
                            )
                        )
            elif el_type == "circle":
                cx, cy = transform(*el["center"])
                r = el["radius"] * scale
                dwg.add(
                    dwg.circle(center=(cx, cy), r=r, fill="none", stroke="black", stroke_width=1)
                )
            elif el_type == "arc":
                cx, cy = transform(*el["center"])
                r = el["radius"] * scale
                start_rad = math.radians(el["start_angle"])
                end_rad = math.radians(el["end_angle"])
                steps = 20
                pts = []
                for i in range(steps + 1):
                    t = start_rad + (end_rad - start_rad) * i / steps
                    px = cx + r * math.cos(t)
                    py = cy - r * math.sin(t)
                    pts.append((px, py))
                dwg.add(dwg.polyline(points=pts, fill="none", stroke="black", stroke_width=1))
            elif el_type == "angle_label":
                vx, vy = transform(*el["vertex"])
                dwg.add(dwg.text(el["label"], insert=(vx + 8, vy - 8), font_size=12, font_family="Hiragino Sans, sans-serif"))
            elif el_type == "text":
                tx, ty = transform(el["x"], el["y"])
                dwg.add(dwg.text(el["content"], insert=(tx, ty), font_size=14, font_family="Hiragino Sans, sans-serif"))

        return dwg.tostring()
