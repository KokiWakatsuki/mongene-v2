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
        x_min, y_min, x_max, y_max = dsl.viewport
        usable_w = self.image_width - 2 * self.margin
        usable_h = self.image_height - 2 * self.margin
        scale_x = usable_w / (x_max - x_min) if x_max != x_min else 1
        scale_y = usable_h / (y_max - y_min) if y_max != y_min else 1
        scale = min(scale_x, scale_y) if self.auto_scale else 1

        def transform(x: float, y: float) -> Tuple[float, float]:
            sx = self.margin + (x - x_min) * scale
            sy = self.image_height - self.margin - (y - y_min) * scale
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
                    dwg.add(dwg.text(el["label"], insert=(cx + 5, cy - 5), font_size=14))
            elif el_type == "line_segment":
                p1 = transform(*el["p1"])
                p2 = transform(*el["p2"])
                line = dwg.line(start=p1, end=p2, stroke="black", stroke_width=1)
                if el.get("dashed"):
                    line.dasharray([5, 5])
                dwg.add(line)
                if el.get("label"):
                    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                    dwg.add(dwg.text(el["label"], insert=(mx + 3, my - 3), font_size=12))
            elif el_type == "polygon":
                points = [transform(*v) for v in el["vertices"]]
                fill = "lightgray" if el.get("filled") else "none"
                dwg.add(
                    dwg.polygon(points=points, fill=fill, stroke="black", stroke_width=1)
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
                dwg.add(dwg.text(el["label"], insert=(vx + 8, vy - 8), font_size=12))
            elif el_type == "text":
                tx, ty = transform(el["x"], el["y"])
                dwg.add(dwg.text(el["content"], insert=(tx, ty), font_size=14))

        return dwg.tostring()
