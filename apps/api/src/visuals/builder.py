"""VisualBuilder（§37 _build_visual_dsl の実体）

Blueprint と sampled_nouns / logic_steps から VisualDSL を組み立てる。
"""
from __future__ import annotations

from typing import Any, Dict

import sympy

from apps.api.src.core.abc.atoms import NounAtom
from apps.api.src.core.abc.blueprint import BlueprintDefinition
from apps.api.src.core.abc.visuals import VisualDSL


def build_visual_dsl(
    blueprint: BlueprintDefinition,
    sampled_nouns: Dict[str, NounAtom],
    logic_steps: Dict[str, Any],
) -> VisualDSL | None:
    if blueprint.visual_slot is None or blueprint.visual_slot.component_type == "NullRenderer":
        return None

    component = blueprint.visual_slot.component_type
    if component == "3D_Renderer":
        return _build_3d(sampled_nouns)
    if component == "2D_Geometry_Renderer":
        return _build_2d_geometry(sampled_nouns)
    if component == "Graph_Renderer":
        return _build_graph(sampled_nouns)
    if component == "Tree_Renderer":
        return _build_tree(sampled_nouns)
    if component in {"Table_&_Chart_Renderer", "TableChart_Renderer"}:
        return _build_table_chart(sampled_nouns)
    return None


def _to_float(expr: sympy.Expr, default: float = 1.0) -> float:
    try:
        return float(sympy.nsimplify(expr).evalf())
    except Exception:
        return default


def _build_3d(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "PrismAtom":
            w = _to_float(sym.get("width", sympy.Integer(2)))
            d = _to_float(sym.get("depth", sympy.Integer(2)))
            h = _to_float(sym.get("height", sympy.Integer(3)))
            verts = [
                ("A0", (0, 0, 0)),
                ("B0", (w, 0, 0)),
                ("C0", (w, d, 0)),
                ("D0", (0, d, 0)),
                ("A1", (0, 0, h)),
                ("B1", (w, 0, h)),
                ("C1", (w, d, h)),
                ("D1", (0, d, h)),
            ]
            for vid, coords in verts:
                elements.append({"type": "vertex", "id": f"{slot_name}_{vid}", "coords": list(coords), "label": ""})
            edges = [
                ("A0", "B0"), ("B0", "C0"), ("C0", "D0"), ("D0", "A0"),
                ("A1", "B1"), ("B1", "C1"), ("C1", "D1"), ("D1", "A1"),
                ("A0", "A1"), ("B0", "B1"), ("C0", "C1"), ("D0", "D1"),
            ]
            for a, b in edges:
                elements.append({
                    "type": "edge_3d",
                    "from": f"{slot_name}_{a}",
                    "to": f"{slot_name}_{b}",
                    "dashed": False,
                })
        elif name == "PyramidAtom":
            s = _to_float(sym.get("base_side", sympy.Integer(2)))
            h = _to_float(sym.get("height", sympy.Integer(3)))
            apex = (s / 2, s / 2, h)
            base = [("A", (0, 0, 0)), ("B", (s, 0, 0)), ("C", (s, s, 0)), ("D", (0, s, 0))]
            for vid, coords in base:
                elements.append({"type": "vertex", "id": f"{slot_name}_{vid}", "coords": list(coords), "label": ""})
            elements.append({"type": "vertex", "id": f"{slot_name}_P", "coords": list(apex), "label": ""})
            for v in ("A", "B", "C", "D"):
                elements.append({
                    "type": "edge_3d",
                    "from": f"{slot_name}_{v}",
                    "to": f"{slot_name}_P",
                    "dashed": False,
                })
        elif name == "SphereAtom":
            r = _to_float(sym.get("radius", sympy.Integer(1)))
            elements.append({"type": "vertex", "id": f"{slot_name}_O", "coords": [0, 0, 0], "label": "O"})
            elements.append({"type": "vertex", "id": f"{slot_name}_R", "coords": [r, 0, 0], "label": f"r={r:.0f}"})
    return VisualDSL(render_type="3D", elements=elements)


def _build_2d_geometry(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    viewport = [-1.0, -1.0, 10.0, 10.0]
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "PolygonAtom":
            verts_raw = sym.get("vertices") or []
            verts = [[_to_float(v[0]), _to_float(v[1])] for v in verts_raw]
            if verts:
                elements.append({"type": "polygon", "vertices": verts, "filled": False})
        elif name == "CircleAtom":
            r = _to_float(sym.get("radius", sympy.Integer(1)))
            elements.append({"type": "circle", "center": [0, 0], "radius": r})
        elif name == "PointAtom":
            x = _to_float(sym.get("x", sympy.Integer(0)))
            y = _to_float(sym.get("y", sympy.Integer(0)))
            elements.append({"type": "point", "x": x, "y": y, "label": "P"})
    return VisualDSL(render_type="2D_Geometry", elements=elements, viewport=tuple(viewport))


def _build_graph(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "LinearFuncAtom":
            slope = _to_float(sym.get("slope", sympy.Integer(1)))
            intercept = _to_float(sym.get("intercept", sympy.Integer(0)))
            elements.append({"type": "function", "expr": f"{slope}*x + {intercept}", "domain": [-10, 10], "color": "black"})
        elif name == "QuadraticFuncAtom":
            a = _to_float(sym.get("coefficient_a", sympy.Integer(1)))
            elements.append({"type": "function", "expr": f"{a}*x**2", "domain": [-5, 5], "color": "black"})
        elif name == "InverseFuncAtom":
            c = _to_float(sym.get("constant", sympy.Integer(1)))
            elements.append({"type": "function", "expr": f"{c}/x", "domain": [0.5, 10], "color": "black"})
    elements.append({"type": "axis_label", "axis": "x", "label": "x"})
    elements.append({"type": "axis_label", "axis": "y", "label": "y"})
    return VisualDSL(render_type="Graph", elements=elements)


def _build_tree(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = [{"type": "node", "id": "root", "label": "始"}]
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "EventAtom":
            size = int(sym.get("sample_space_size", sympy.Integer(2)))
            for i in range(min(size, 6)):
                node_id = f"{slot_name}_{i}"
                elements.append({"type": "node", "id": node_id, "label": str(i + 1)})
                elements.append({"type": "edge", "from": "root", "to": node_id, "label": f"1/{size}"})
    return VisualDSL(render_type="Tree", elements=elements)


def _build_table_chart(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    for slot_name, atom in sampled_nouns.items():
        if type(atom).__name__ == "DataSetAtom":
            elements.append({"type": "header_row", "cells": ["指標", "値"]})
            sym = atom.get_symbols()
            for key in ("mean", "median", "q1", "q3"):
                if key in sym:
                    elements.append({"type": "data_row", "cells": [key, str(sym[key])]})
            break
    return VisualDSL(render_type="Table", elements=elements)
