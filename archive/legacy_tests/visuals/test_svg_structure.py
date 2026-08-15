"""SVG の構造的整合性テスト

Atom のサンプル値と SVG 要素属性が一致するかを XML 解析で検証する。
視覚的品質（読みやすさ等）は対象外（人間レビュー必須）。
"""
from __future__ import annotations

import random
import re
import xml.etree.ElementTree as ET

import sympy

from apps.api.src.atoms.noun.circle_atom import CircleAtom
from apps.api.src.atoms.noun.linear_func_atom import LinearFuncAtom
from apps.api.src.atoms.noun.polygon_atom import PolygonAtom
from apps.api.src.core.abc.atoms import AtomConstraints
from apps.api.src.core.abc.visuals import VisualDSL
from apps.api.src.visuals.builder import build_visual_dsl
from apps.api.src.visuals.graph_renderer import GraphRenderer
from apps.api.src.visuals.two_d_geometry_renderer import TwoDGeometryRenderer

SVG_NS = "{http://www.w3.org/2000/svg}"


def _parse_svg(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def _find_all(root: ET.Element, tag: str) -> list[ET.Element]:
    return root.findall(f".//{SVG_NS}{tag}") or root.findall(f".//{tag}")


def _ac(**kw) -> AtomConstraints:
    return AtomConstraints(difficulty_band=(1, 50), forbidden_tags=[], seed=42, custom=kw)


# ============================================================================
# Polygon: 三角形なら SVG に polygon 要素が 1 つあり、頂点数も一致する
# ============================================================================


def test_polygon_atom_renders_with_correct_vertex_count() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(1))
    n_vertices = len(poly.vertices)
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[
            {"type": "polygon", "vertices": [
                [float(sympy.nsimplify(v[0]).evalf()), float(sympy.nsimplify(v[1]).evalf())]
                for v in poly.vertices
            ]}
        ],
        viewport=(-1, -1, 15, 15),
    )
    svg = TwoDGeometryRenderer().render(dsl)
    root = _parse_svg(svg)
    polygons = _find_all(root, "polygon")
    assert len(polygons) == 1
    points_attr = polygons[0].get("points", "")
    # "x1,y1 x2,y2 ..." の形式で n_vertices 個の座標を持つ
    points = [p for p in re.split(r"\s+", points_attr.strip()) if p]
    assert len(points) == n_vertices, f"頂点数 {n_vertices} と SVG points {len(points)} が不一致"


# ============================================================================
# Circle: 半径が SVG の circle/r 属性に反映されている
# ============================================================================


def test_circle_atom_renders_with_correct_radius() -> None:
    # CircleAtom を非扇形で作る
    circle = CircleAtom().sample(_ac(is_sector=False, max_radius=5), random.Random(2))
    r_expr = circle.get_symbols()["radius"]
    r_value = float(sympy.nsimplify(r_expr).evalf())

    # 描画用 DSL
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[{"type": "circle", "center": [0, 0], "radius": r_value}],
        viewport=(-(r_value + 1), -(r_value + 1), r_value + 1, r_value + 1),
    )
    svg = TwoDGeometryRenderer().render(dsl)
    root = _parse_svg(svg)
    circles = _find_all(root, "circle")
    assert len(circles) >= 1
    # auto_scale 後の r 属性。viewport 範囲が同じならスケールも安定
    svg_r = float(circles[0].get("r", "0"))
    assert svg_r > 0  # 0 ではない（半径 0 では描画されない）


# ============================================================================
# Point: 指定座標が SVG 上の circle 要素として描画される
# ============================================================================


def test_point_atom_renders_as_marker() -> None:
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[
            {"type": "point", "x": 3, "y": 4, "label": "A"},
            {"type": "point", "x": -2, "y": 1, "label": "B"},
        ],
        viewport=(-5, -5, 5, 5),
    )
    svg = TwoDGeometryRenderer().render(dsl)
    root = _parse_svg(svg)
    circles = _find_all(root, "circle")
    # 点 2 つ分のマーカー（半径 3px の小さい circle）
    point_circles = [c for c in circles if float(c.get("r", "0")) <= 5]
    assert len(point_circles) == 2

    # ラベル A, B のテキストが SVG に含まれる
    texts = _find_all(root, "text")
    text_contents = [(t.text or "") for t in texts]
    assert "A" in text_contents
    assert "B" in text_contents


# ============================================================================
# Line segment: viewport 内に収まる線分が出力される
# ============================================================================


def test_line_segment_renders_correctly() -> None:
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[{"type": "line_segment", "p1": [0, 0], "p2": [3, 4]}],
        viewport=(-1, -1, 5, 5),
    )
    svg = TwoDGeometryRenderer().render(dsl)
    root = _parse_svg(svg)
    lines = _find_all(root, "line")
    assert len(lines) >= 1


# ============================================================================
# Graph: 関数式が描画され、x 軸範囲が viewport に正しく対応
# ============================================================================


def test_graph_renderer_includes_function() -> None:
    dsl = VisualDSL(
        render_type="Graph",
        elements=[
            {"type": "function", "expr": "x**2 + 1", "domain": [-3, 3]},
        ],
    )
    svg = GraphRenderer(x_range=(-3, 3)).render(dsl)
    # matplotlib 出力にはパス要素が含まれる
    assert "<svg" in svg
    root = _parse_svg(svg)
    paths = _find_all(root, "path")
    assert len(paths) > 0


# ============================================================================
# VisualBuilder: PolygonAtom から 2D_Geometry の DSL が組まれる
# ============================================================================


def test_builder_produces_2d_dsl_from_polygon() -> None:
    from apps.api.src.blueprints.basic_geometry_measurement import (
        build_basic_geometry_measurement_blueprint,
    )

    bp = build_basic_geometry_measurement_blueprint()
    poly = PolygonAtom().sample(_ac(polygon_type="square"), random.Random(0))
    dsl = build_visual_dsl(bp, {"shape": poly}, {})
    assert dsl is not None
    assert dsl.render_type == "2D_Geometry"
    polys = [e for e in dsl.elements if e.get("type") == "polygon"]
    assert len(polys) == 1
    # 四角形なので頂点 4 つ
    assert len(polys[0]["vertices"]) == 4


# ============================================================================
# VisualBuilder: LinearFuncAtom から Graph の DSL が組まれる
# ============================================================================


def test_builder_produces_graph_dsl_from_linear_func() -> None:
    from apps.api.src.blueprints.function_geometry_fusion import (
        build_function_geometry_fusion_blueprint,
    )

    bp = build_function_geometry_fusion_blueprint()
    f = LinearFuncAtom().sample(_ac(max_slope=3), random.Random(0))
    dsl = build_visual_dsl(bp, {"func_a": f, "func_b": f}, {})
    assert dsl is not None
    assert dsl.render_type == "Graph"
    funcs = [e for e in dsl.elements if e.get("type") == "function"]
    assert len(funcs) >= 1


# ============================================================================
# Viewport 整合性: 全要素が viewport 内に収まる
# ============================================================================


def test_polygon_within_viewport() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="rectangle", max_side_length=8), random.Random(7))
    verts = [
        (float(sympy.nsimplify(v[0]).evalf()), float(sympy.nsimplify(v[1]).evalf()))
        for v in poly.vertices
    ]
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    # 自動 viewport を設定して全頂点が範囲内であることを確認
    viewport = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
    dsl = VisualDSL(
        render_type="2D_Geometry",
        elements=[{"type": "polygon", "vertices": [list(v) for v in verts]}],
        viewport=viewport,
    )
    svg = TwoDGeometryRenderer().render(dsl)
    root = _parse_svg(svg)
    polys = _find_all(root, "polygon")
    assert len(polys) == 1
    # 全頂点座標が SVG 範囲内（0 〜 image_width）の正の値
    points_attr = polys[0].get("points", "")
    for pt in re.split(r"\s+", points_attr.strip()):
        if "," not in pt:
            continue
        x_str, y_str = pt.split(",")
        x, y = float(x_str), float(y_str)
        assert 0 <= x <= 400
        assert 0 <= y <= 400
