"""Visual Component の最低限テスト（SVG/HTML 文字列を返すこと）"""
from __future__ import annotations

from apps.api.src.core.abc.visuals import VisualDSL
from apps.api.src.visuals.graph_renderer import GraphRenderer
from apps.api.src.visuals.null_renderer import NullRenderer
from apps.api.src.visuals.table_chart_renderer import TableChartRenderer
from apps.api.src.visuals.three_d_renderer import ThreeDRenderer
from apps.api.src.visuals.tree_renderer import TreeRenderer
from apps.api.src.visuals.two_d_geometry_renderer import TwoDGeometryRenderer


def test_null_renderer_returns_empty() -> None:
    dsl = VisualDSL(render_type="Null", elements=[])
    assert NullRenderer().render(dsl) == ""


def test_2d_geometry_renderer_returns_svg() -> None:
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[
            {"type": "point", "x": 0, "y": 0, "label": "A"},
            {"type": "line_segment", "p1": [0, 0], "p2": [3, 4]},
            {"type": "polygon", "vertices": [[0, 0], [3, 0], [3, 4]]},
            {"type": "circle", "center": [0, 0], "radius": 2},
        ],
        viewport=(-2, -2, 5, 5),
    )
    out = TwoDGeometryRenderer().render(dsl)
    assert "<svg" in out


def test_3d_renderer_returns_svg() -> None:
    dsl = VisualDSL(
        render_type="3D",
        elements=[
            {"type": "vertex", "id": "A", "coords": [0, 0, 0]},
            {"type": "vertex", "id": "B", "coords": [1, 0, 0]},
            {"type": "edge_3d", "from": "A", "to": "B"},
        ],
    )
    out = ThreeDRenderer().render(dsl)
    assert "<svg" in out


def test_graph_renderer_returns_svg() -> None:
    dsl = VisualDSL(
        render_type="Graph",
        elements=[
            {"type": "function", "expr": "x**2", "domain": [-2, 2]},
            {"type": "point_on_graph", "x": 1, "y": 1, "label": "P"},
        ],
    )
    out = GraphRenderer(x_range=(-3, 3)).render(dsl)
    assert "<svg" in out


def test_table_chart_renderer_table() -> None:
    dsl = VisualDSL(
        render_type="Table",
        elements=[
            {"type": "header_row", "cells": ["階級", "度数"]},
            {"type": "data_row", "cells": ["0以上10未満", "5"]},
        ],
    )
    out = TableChartRenderer("table").render(dsl)
    assert "<table" in out
    assert "<th>階級</th>" in out


def test_table_chart_renderer_histogram() -> None:
    dsl = VisualDSL(
        render_type="Table",
        elements=[
            {"type": "bins", "bins": [(0, 10, 5), (10, 20, 8), (20, 30, 3)]},
        ],
    )
    out = TableChartRenderer("histogram").render(dsl)
    assert "<svg" in out


def test_tree_renderer_returns_svg() -> None:
    dsl = VisualDSL(
        render_type="Tree",
        elements=[
            {"type": "node", "id": "root", "label": "Start"},
            {"type": "node", "id": "n1", "label": "表"},
            {"type": "edge", "from": "root", "to": "n1", "label": "1/2"},
        ],
    )
    out = TreeRenderer().render(dsl)
    assert "<svg" in out
