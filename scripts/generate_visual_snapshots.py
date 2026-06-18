"""図形 SVG のスナップショット生成

代表 lesson から各 Visual Component を呼び出し、生成された SVG をハッシュ化して
スナップショットファイルに保存する。回帰検出で利用する。

数学的正しさは pytest では検証不可（人間レビュー必須）。
代わりに「過去の生成結果と比較して同一かどうか」を検出する。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from apps.api.src.core.abc.visuals import VisualDSL
from apps.api.src.visuals.graph_renderer import GraphRenderer
from apps.api.src.visuals.three_d_renderer import ThreeDRenderer
from apps.api.src.visuals.table_chart_renderer import TableChartRenderer
from apps.api.src.visuals.tree_renderer import TreeRenderer
from apps.api.src.visuals.two_d_geometry_renderer import TwoDGeometryRenderer

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "reports" / "visual_snapshots"
SNAPSHOT_INDEX = SNAPSHOT_DIR / "index.json"


def _hash_svg(svg: str) -> str:
    return hashlib.sha256(svg.encode()).hexdigest()[:16]


def _fixtures() -> List[Dict[str, Any]]:
    return [
        {
            "name": "2d_triangle",
            "renderer": TwoDGeometryRenderer(),
            "dsl": VisualDSL(
                render_type="2D_Geometry",
                elements=[
                    {"type": "polygon", "vertices": [[0, 0], [3, 0], [0, 4]]},
                    {"type": "point", "x": 0, "y": 0, "label": "A"},
                    {"type": "point", "x": 3, "y": 0, "label": "B"},
                    {"type": "point", "x": 0, "y": 4, "label": "C"},
                ],
                viewport=(-1, -1, 5, 5),
            ),
        },
        {
            "name": "2d_circle_with_sector",
            "renderer": TwoDGeometryRenderer(),
            "dsl": VisualDSL(
                render_type="2D_Geometry",
                elements=[
                    # 全体の円
                    {"type": "circle", "center": [0, 0], "radius": 3},
                    # 扇形を構成: 半径線 2 本 + 弧
                    {"type": "line_segment", "p1": [0, 0], "p2": [3, 0]},
                    {"type": "line_segment", "p1": [0, 0], "p2": [1.5, 2.598]},  # 60 度
                    {"type": "arc", "center": [0, 0], "radius": 3, "start_angle": 0, "end_angle": 60},
                    {"type": "point", "x": 0, "y": 0, "label": "O"},
                    {"type": "angle_label", "vertex": [0.5, 0.3], "rays": [[1, 0], [0.5, 0.866]], "label": "60°"},
                ],
                viewport=(-4, -4, 4, 4),
            ),
        },
        {
            "name": "3d_cube",
            "renderer": ThreeDRenderer(),
            "dsl": VisualDSL(
                render_type="3D",
                elements=[
                    # 立方体 8 頂点
                    {"type": "vertex", "id": "A", "coords": [0, 0, 0], "label": "A"},
                    {"type": "vertex", "id": "B", "coords": [2, 0, 0], "label": "B"},
                    {"type": "vertex", "id": "C", "coords": [2, 2, 0], "label": "C"},
                    {"type": "vertex", "id": "D", "coords": [0, 2, 0], "label": "D"},
                    {"type": "vertex", "id": "E", "coords": [0, 0, 2], "label": "E"},
                    {"type": "vertex", "id": "F", "coords": [2, 0, 2], "label": "F"},
                    {"type": "vertex", "id": "G", "coords": [2, 2, 2], "label": "G"},
                    {"type": "vertex", "id": "H", "coords": [0, 2, 2], "label": "H"},
                    # 12 辺
                    {"type": "edge_3d", "from": "A", "to": "B"},
                    {"type": "edge_3d", "from": "B", "to": "C"},
                    {"type": "edge_3d", "from": "C", "to": "D"},
                    {"type": "edge_3d", "from": "D", "to": "A"},
                    {"type": "edge_3d", "from": "E", "to": "F"},
                    {"type": "edge_3d", "from": "F", "to": "G"},
                    {"type": "edge_3d", "from": "G", "to": "H"},
                    {"type": "edge_3d", "from": "H", "to": "E"},
                    {"type": "edge_3d", "from": "A", "to": "E"},
                    {"type": "edge_3d", "from": "B", "to": "F"},
                    {"type": "edge_3d", "from": "C", "to": "G"},
                    {"type": "edge_3d", "from": "D", "to": "H"},
                ],
            ),
        },
        {
            "name": "graph_parabola",
            "renderer": GraphRenderer(x_range=(-3, 3)),
            "dsl": VisualDSL(
                render_type="Graph",
                elements=[
                    {"type": "function", "expr": "x**2", "domain": [-3, 3]},
                    {"type": "point_on_graph", "x": 1, "y": 1, "label": "P"},
                ],
            ),
        },
        {
            "name": "tree_dice",
            "renderer": TreeRenderer(),
            "dsl": VisualDSL(
                render_type="Tree",
                elements=[
                    {"type": "node", "id": "root", "label": "Start"},
                    {"type": "node", "id": "h", "label": "表"},
                    {"type": "node", "id": "t", "label": "裏"},
                    {"type": "edge", "from": "root", "to": "h", "label": "1/2"},
                    {"type": "edge", "from": "root", "to": "t", "label": "1/2"},
                ],
            ),
        },
        {
            "name": "table_histogram",
            "renderer": TableChartRenderer("histogram"),
            "dsl": VisualDSL(
                render_type="Table",
                elements=[
                    {"type": "bins", "bins": [(0, 10, 5), (10, 20, 8), (20, 30, 3)]},
                ],
            ),
        },
    ]


def main() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    fixtures = _fixtures()
    index: Dict[str, Any] = {}
    for fx in fixtures:
        svg = fx["renderer"].render(fx["dsl"])
        h = _hash_svg(svg)
        path = SNAPSHOT_DIR / f"{fx['name']}.svg"
        path.write_text(svg, encoding="utf-8")
        index[fx["name"]] = {
            "svg_path": str(path.relative_to(REPO_ROOT)),
            "hash": h,
            "elements_count": len(fx["dsl"].elements),
        }
        print(f"  {fx['name']}: hash={h}, {len(svg)} bytes")
    SNAPSHOT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Index: {SNAPSHOT_INDEX}")


if __name__ == "__main__":
    main()
