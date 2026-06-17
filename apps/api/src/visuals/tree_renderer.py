"""TreeRenderer（§17.3, §18.3）

確率の樹形図を SVG で描画する（svgwrite ベース、graphviz 依存なし）。
"""
from __future__ import annotations

from typing import Dict, Literal, Tuple

import svgwrite

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL

Direction = Literal["TB", "LR"]


class TreeRenderer(VisualComponent):
    def __init__(
        self,
        direction: Direction = "TB",
        show_probabilities: bool = True,
        image_width: int = 500,
        image_height: int = 400,
    ) -> None:
        self.direction: Direction = direction
        self.show_probabilities = show_probabilities
        self.image_width = image_width
        self.image_height = image_height

    def render(self, dsl: VisualDSL) -> str:
        nodes: Dict[str, Tuple[float, float, str]] = {}
        edges: list[Tuple[str, str, str]] = []

        node_count = sum(1 for e in dsl.elements if e["type"] == "node")
        node_index = 0
        for el in dsl.elements:
            t = el["type"]
            if t == "node":
                # 単純に縦/横方向に並べる
                if self.direction == "TB":
                    x = (node_index + 1) * self.image_width / (node_count + 1)
                    y = 50 if node_index == 0 else 50 + 60 * (node_index)
                else:
                    x = 50 + 80 * node_index
                    y = (node_index + 1) * self.image_height / (node_count + 1)
                nodes[el["id"]] = (x, y, el.get("label", el["id"]))
                node_index += 1
            elif t == "edge":
                edges.append((el["from"], el["to"], el.get("label", "")))

        dwg = svgwrite.Drawing(size=(self.image_width, self.image_height))
        for node_id, (x, y, label) in nodes.items():
            dwg.add(dwg.circle(center=(x, y), r=15, fill="white", stroke="black"))
            dwg.add(dwg.text(label, insert=(x - 10, y + 4), font_size=10))

        for src, dst, edge_label in edges:
            if src not in nodes or dst not in nodes:
                continue
            x1, y1, _ = nodes[src]
            x2, y2, _ = nodes[dst]
            dwg.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke="black", stroke_width=1))
            if edge_label and self.show_probabilities:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                dwg.add(dwg.text(edge_label, insert=(mx + 3, my - 3), font_size=10))

        return dwg.tostring()
