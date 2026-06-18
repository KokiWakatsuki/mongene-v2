"""TreeRenderer（§17.3, §18.3）

確率の樹形図を SVG で描画する（svgwrite ベース、graphviz 依存なし）。
ノード関係から木構造の階層を計算し、上→下に展開して Y 字レイアウト。
"""
from __future__ import annotations

from typing import Dict, List, Literal, Tuple

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
        # 1. ノードとエッジを抽出
        node_ids: List[str] = []
        node_labels: Dict[str, str] = {}
        edges: List[Tuple[str, str, str]] = []
        for el in dsl.elements:
            t = el["type"]
            if t == "node":
                node_ids.append(el["id"])
                node_labels[el["id"]] = el.get("label", el["id"])
            elif t == "edge":
                edges.append((el["from"], el["to"], el.get("label", "")))

        # 2. ノードの親子関係から階層を計算
        children: Dict[str, List[str]] = {nid: [] for nid in node_ids}
        parent: Dict[str, str] = {}
        for src, dst, _ in edges:
            if src in children and dst in node_ids:
                children[src].append(dst)
                parent[dst] = src

        # 根ノード（親を持たないノード）
        roots = [nid for nid in node_ids if nid not in parent]
        if not roots:
            roots = [node_ids[0]] if node_ids else []

        # 3. 各ノードの depth を計算
        depth: Dict[str, int] = {}

        def compute_depth(nid: str, d: int) -> None:
            depth[nid] = d
            for c in children.get(nid, []):
                compute_depth(c, d + 1)

        for r in roots:
            compute_depth(r, 0)
        max_depth = max(depth.values(), default=0)

        # 4. 各 depth レベルの幅を取得し、x 座標を割り当て
        by_depth: Dict[int, List[str]] = {}
        for nid, d in depth.items():
            by_depth.setdefault(d, []).append(nid)

        nodes_xy: Dict[str, Tuple[float, float]] = {}
        margin = 40
        if self.direction == "TB":
            level_h = (self.image_height - 2 * margin) / max(1, max_depth)
            for d, ids in by_depth.items():
                n = len(ids)
                level_w = self.image_width - 2 * margin
                for i, nid in enumerate(ids):
                    x = margin + level_w * (i + 1) / (n + 1)
                    y = margin + level_h * d
                    nodes_xy[nid] = (x, y)
        else:  # LR
            level_w = (self.image_width - 2 * margin) / max(1, max_depth)
            for d, ids in by_depth.items():
                n = len(ids)
                level_h = self.image_height - 2 * margin
                for i, nid in enumerate(ids):
                    x = margin + level_w * d
                    y = margin + level_h * (i + 1) / (n + 1)
                    nodes_xy[nid] = (x, y)

        # 5. SVG 描画
        dwg = svgwrite.Drawing(size=(self.image_width, self.image_height))

        # エッジ先に描画（ノードの下に来るように）
        for src, dst, edge_label in edges:
            if src not in nodes_xy or dst not in nodes_xy:
                continue
            x1, y1 = nodes_xy[src]
            x2, y2 = nodes_xy[dst]
            dwg.add(dwg.line(start=(x1, y1), end=(x2, y2), stroke="black", stroke_width=1))
            if edge_label and self.show_probabilities:
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                dwg.add(
                    dwg.text(
                        edge_label,
                        insert=(mx + 4, my - 4),
                        font_size=11,
                        font_family="Hiragino Sans, sans-serif",
                    )
                )

        # ノード（円 + ラベル）
        for nid in node_ids:
            if nid not in nodes_xy:
                continue
            x, y = nodes_xy[nid]
            dwg.add(dwg.circle(center=(x, y), r=18, fill="white", stroke="black", stroke_width=1.2))
            label = node_labels.get(nid, nid)
            dwg.add(
                dwg.text(
                    label,
                    insert=(x, y + 4),
                    font_size=12,
                    font_family="Hiragino Sans, sans-serif",
                    text_anchor="middle",
                )
            )

        return dwg.tostring()
