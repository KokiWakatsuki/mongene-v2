"""VisualBuilder（§37 _build_visual_dsl の実体）

Blueprint と sampled_nouns / logic_steps から VisualDSL を組み立てる。
"""
from __future__ import annotations

import math
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
        if blueprint.blueprint_id == "BasicDifferenceStructure":
            # 設計書 §18.3: cutout_volume を主立体の内部に点線で描く
            return _build_3d_with_cutout_inside(sampled_nouns)
        if blueprint.blueprint_id == "PythagoreanSpaceStructure":
            solid_key = "solid" if "solid" in sampled_nouns else next(iter(sampled_nouns), None)
            display = {solid_key: sampled_nouns[solid_key]} if solid_key else sampled_nouns
            return _build_3d(display)
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


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def _build_3d_with_cutout_inside(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    """BasicDifferenceStructure 専用: 設計書 §18.3 に従い、
    主立体の中にくり抜く立体を cutout_volume 要素として内包して表示する。

    教科書スタイル: 主立体の図の中に錐体を点線で示す。
    """
    base_atom = sampled_nouns.get("base_solid")
    cutout_atom = sampled_nouns.get("cutout_solid")

    if base_atom is None:
        return _build_3d(sampled_nouns)

    # 主立体の要素
    dsl_base = _build_3d({"base_solid": base_atom})
    elements = list(dsl_base.elements)

    # くり抜く立体を cutout_volume 要素として主立体の内側に追加
    if cutout_atom is not None:
        name = type(cutout_atom).__name__
        sym = cutout_atom.get_symbols()

        if name == "PyramidAtom":
            s = _to_float(sym.get("base_side", sympy.Integer(2)))
            h = _to_float(sym.get("height", sympy.Integer(3)))
            # 底面中心を主立体の底面中心に合わせる
            base_sym = base_atom.get_symbols()
            cx = _to_float(base_sym.get("width", sympy.Integer(6))) / 2
            cy = _to_float(base_sym.get("depth", sympy.Integer(6))) / 2
            # cutout_volume 要素（設計書 §18.3 通り）
            elements.append({
                "type": "cutout_volume",
                "shape": "pyramid",
                "base": [
                    [cx - s/2, cy - s/2, 0], [cx + s/2, cy - s/2, 0],
                    [cx + s/2, cy + s/2, 0], [cx - s/2, cy + s/2, 0],
                ],
                "apex": [cx, cy, h],
                "base_side": s,
                "height": h,
            })
            # 錐体の寸法ラベル
            elements.append({"type": "vertex", "id": "_cut_label",
                              "coords": [cx + s + 0.5, cy, h / 2], "label": f"(底辺{_fmt(s)}cm)"})

        elif name == "SphereAtom":
            r = _to_float(sym.get("radius", sympy.Integer(1)))
            base_sym = base_atom.get_symbols()
            cx = _to_float(base_sym.get("width", sympy.Integer(6))) / 2
            cy = _to_float(base_sym.get("depth", sympy.Integer(6))) / 2
            elements.append({
                "type": "cutout_volume",
                "shape": "sphere",
                "center": [cx, cy, r],
                "radius": r,
            })
            # 球ワイヤーフレームも追加（球そのものが見えるように）
            elements.append({
                "type": "sphere_wireframe",
                "center": [cx, cy, r],
                "radius": r,
                "color": "#cc4400",
                "linewidth": 1.0,
            })
        elif name == "PrismAtom":
            # 小さい直方体のくり抜き
            w = _to_float(sym.get("width", sympy.Integer(2)))
            d = _to_float(sym.get("depth", sympy.Integer(2)))
            h = _to_float(sym.get("height", sympy.Integer(2)))
            base_sym = base_atom.get_symbols()
            bw = _to_float(base_sym.get("width", sympy.Integer(6)))
            bd = _to_float(base_sym.get("depth", sympy.Integer(6)))
            ox, oy = (bw - w) / 2, (bd - d) / 2
            elements.append({
                "type": "cutout_volume",
                "shape": "prism",
                "base": [[ox, oy, 0], [ox+w, oy, 0], [ox+w, oy+d, 0], [ox, oy+d, 0]],
                "height": h,
            })

    return VisualDSL(render_type="3D", elements=elements)


def _build_3d(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    """立体の 3D ワイヤフレームを組む。頂点ラベル + 寸法ラベル付き。"""
    elements: list[dict] = []
    # slot ごとにオフセットして重なりを防ぐ
    # 最初の solid のサイズを基準に横並び
    first_w = 0.0
    for atom in sampled_nouns.values():
        sym = atom.get_symbols()
        first_w = max(first_w, _to_float(sym.get("width", sympy.Integer(4))))
        break
    gap = first_w * 1.8  # 立体間の間隔
    offsets = [(0.0, 0.0, 0.0), (gap, 0.0, 0.0), (-gap, 0.0, 0.0)]

    for idx, (slot_name, atom) in enumerate(sampled_nouns.items()):
        ox, oy, oz = offsets[min(idx, len(offsets)-1)]
        name = type(atom).__name__
        sym = atom.get_symbols()

        if name == "PrismAtom":
            w = _to_float(sym.get("width", sympy.Integer(4)))
            d = _to_float(sym.get("depth", sympy.Integer(4)))
            h = _to_float(sym.get("height", sympy.Integer(6)))
            p = slot_name[:1].upper()  # vertex prefix

            verts_local = [
                (f"{p}A", (ox, oy, oz)),
                (f"{p}B", (ox+w, oy, oz)),
                (f"{p}C", (ox+w, oy+d, oz)),
                (f"{p}D", (ox, oy+d, oz)),
                (f"{p}E", (ox, oy, oz+h)),
                (f"{p}F", (ox+w, oy, oz+h)),
                (f"{p}G", (ox+w, oy+d, oz+h)),
                (f"{p}H", (ox, oy+d, oz+h)),
            ]
            labels = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G", "H": "H"}
            for vid, coords in verts_local:
                elements.append({"type": "vertex", "id": vid, "coords": list(coords), "label": vid[1]})
            edges = [
                ("A","B"),("B","C"),("C","D"),("D","A"),
                ("E","F"),("F","G"),("G","H"),("H","E"),
                ("A","E"),("B","F"),("C","G"),("D","H"),
            ]
            for a, b in edges:
                elements.append({"type": "edge_3d", "from": f"{p}{a}", "to": f"{p}{b}", "dashed": False})
            # 寸法ラベル（辺の中点の少し外側）
            elements.append({"type": "vertex", "id": f"{p}_lw", "coords": [ox+w/2, oy-1.0, oz], "label": f"{_fmt(w)} cm"})
            elements.append({"type": "vertex", "id": f"{p}_lh", "coords": [ox-1.5, oy, oz+h/2], "label": f"{_fmt(h)} cm"})
            elements.append({"type": "vertex", "id": f"{p}_ld", "coords": [ox+w+0.5, oy+d/2, oz], "label": f"{_fmt(d)} cm"})

        elif name == "PyramidAtom":
            s = _to_float(sym.get("base_side", sympy.Integer(4)))
            h = _to_float(sym.get("height", sympy.Integer(5)))
            apex = (ox+s/2, oy+s/2, oz+h)
            base = [
                ("A", (ox, oy, oz)), ("B", (ox+s, oy, oz)),
                ("C", (ox+s, oy+s, oz)), ("D", (ox, oy+s, oz)),
            ]
            for vid, coords in base:
                elements.append({"type": "vertex", "id": f"py{vid}", "coords": list(coords), "label": vid})
            elements.append({"type": "vertex", "id": "pyP", "coords": list(apex), "label": "P"})
            for a, b in [("A","B"),("B","C"),("C","D"),("D","A")]:
                elements.append({"type": "edge_3d", "from": f"py{a}", "to": f"py{b}", "dashed": False})
            for v in ("A","B","C","D"):
                elements.append({"type": "edge_3d", "from": f"py{v}", "to": "pyP", "dashed": False})
            # 寸法ラベル
            elements.append({"type": "vertex", "id": "py_ls", "coords": [ox+s/2, oy-1.0, oz], "label": f"{_fmt(s)} cm"})
            elements.append({"type": "vertex", "id": "py_lh", "coords": [ox+s/2, oy+s/2, oz+h+0.8], "label": f"h={_fmt(h)} cm"})

        elif name == "SphereAtom":
            r = _to_float(sym.get("radius", sympy.Integer(2)))
            # 教科書スタイルの球ワイヤーフレーム
            elements.append({
                "type": "sphere_wireframe",
                "center": [ox, oy, oz + r],  # 底面から r の高さに中心
                "radius": r,
                "color": "black",
            })
            elements.append({"type": "vertex", "id": "sO", "coords": [ox, oy, oz + r], "label": "O"})

    return VisualDSL(render_type="3D", elements=elements)


def _build_2d_geometry(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    viewport = [-1.0, -1.0, 10.0, 10.0]
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "PolygonAtom":
            verts_raw = getattr(atom, "vertices", None) or []
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
        elif name == "LineAngleAtom":
            new_elements, new_viewport = _build_line_angle(atom)
            elements.extend(new_elements)
            viewport = new_viewport
        elif name == "CircleAngleAtom":
            new_elements, new_viewport = _build_circle_angle(atom)
            elements.extend(new_elements)
            viewport = new_viewport
    return VisualDSL(render_type="2D_Geometry", elements=elements, viewport=tuple(viewport))


def _build_line_angle(atom: NounAtom) -> tuple[list[dict], list[float]]:
    """LineAngleAtom（平行線＋横断線）の DSL 要素を組み立てる。

    2 本の平行線 a, b と、それらを貫く横断線を描き、既知角 θ と
    relation_type（alternate/corresponding/co_interior）に応じた目標角を
    それぞれ arc + angle_label で示す。
    """
    theta = _to_float(atom.known_angle)
    rel = getattr(atom, "relation_type", "alternate")

    # tan の発散を避けるための安全域クランプ
    th = max(15.0, min(theta, 165.0))
    th_rad = math.radians(th)
    tan_th = math.tan(th_rad)
    if abs(tan_th) < 1e-6:
        tan_th = 1e-6 if tan_th >= 0 else -1e-6

    elements: list[dict] = []

    # 1. 平行な2直線
    elements.append({"type": "line_segment", "p1": [0.0, 7.0], "p2": [10.0, 7.0]})
    elements.append({"type": "line_segment", "p1": [0.0, 3.0], "p2": [10.0, 3.0]})

    # 2. 直線ラベル
    elements.append({"type": "text", "x": 10.2, "y": 7.0, "content": "a"})
    elements.append({"type": "text", "x": 10.2, "y": 3.0, "content": "b"})

    # 3. 横断線
    m = -tan_th
    p1 = (4.0, 7.0)
    p2_x = 4.0 + (3.0 - 7.0) / m
    p2 = (p2_x, 3.0)
    d = (math.cos(th_rad), -math.sin(th_rad))
    top_end = (p1[0] - 2.2 * d[0], p1[1] - 2.2 * d[1])
    bot_end = (p2[0] + 1.5 * d[0], p2[1] + 1.5 * d[1])
    elements.append({"type": "line_segment", "p1": list(top_end), "p2": list(bot_end)})

    # 4. 既知角（P1）
    elements.append({
        "type": "arc",
        "center": list(p1),
        "radius": 0.9,
        "start_angle": -th,
        "end_angle": 0.0,
    })
    elements.append({"type": "angle_label", "vertex": list(p1), "label": f"{int(round(theta))}°"})

    # 5. target角（P2、relation_type別）
    if rel == "alternate":
        start_angle, end_angle = 180.0 - th, 180.0
    elif rel == "corresponding":
        start_angle, end_angle = -th, 0.0
    else:  # co_interior
        start_angle, end_angle = 0.0, 180.0 - th

    elements.append({
        "type": "arc",
        "center": list(p2),
        "radius": 0.9,
        "start_angle": start_angle,
        "end_angle": end_angle,
    })
    elements.append({"type": "angle_label", "vertex": list(p2), "label": "x°"})

    viewport = [-1.0, 0.0, 12.0, 10.0]
    return elements, viewport


def _build_circle_angle(atom: NounAtom) -> tuple[list[dict], list[float]]:
    """CircleAngleAtom（円＋中心角＋円周角）の DSL 要素を組み立てる。"""
    gamma = _to_float(atom.central_angle)
    ox, oy, r = 5.0, 5.0, 4.0

    a_ang = 270.0 - gamma / 2.0
    b_ang = 270.0 + gamma / 2.0
    c_ang = 90.0

    def point_on_circle(ang_deg: float) -> tuple[float, float]:
        rad = math.radians(ang_deg)
        return (ox + r * math.cos(rad), oy + r * math.sin(rad))

    pa = point_on_circle(a_ang)
    pb = point_on_circle(b_ang)
    pc = point_on_circle(c_ang)

    elements: list[dict] = []
    elements.append({"type": "circle", "center": [ox, oy], "radius": r})
    elements.append({"type": "point", "x": ox, "y": oy, "label": "O"})
    elements.append({"type": "point", "x": pa[0], "y": pa[1], "label": "A"})
    elements.append({"type": "point", "x": pb[0], "y": pb[1], "label": "B"})
    elements.append({"type": "point", "x": pc[0], "y": pc[1], "label": "C"})

    elements.append({"type": "line_segment", "p1": [ox, oy], "p2": list(pa), "dashed": True})
    elements.append({"type": "line_segment", "p1": [ox, oy], "p2": list(pb), "dashed": True})
    elements.append({"type": "line_segment", "p1": list(pc), "p2": list(pa)})
    elements.append({"type": "line_segment", "p1": list(pc), "p2": list(pb)})

    # 中心角: A_ang(=270-γ/2) から B_ang(=270+γ/2) へ反時計回りで270を通る小弧
    elements.append({
        "type": "arc",
        "center": [ox, oy],
        "radius": 1.0,
        "start_angle": a_ang,
        "end_angle": b_ang,
    })
    elements.append({"type": "angle_label", "vertex": [ox, oy], "label": f"{int(round(gamma))}°"})

    # 円周角: C から見た A, B 方向の角度（atan2）
    def angle_from(origin: tuple[float, float], target: tuple[float, float]) -> float:
        return math.degrees(math.atan2(target[1] - origin[1], target[0] - origin[0]))

    ang_ca = angle_from(pc, pa)
    ang_cb = angle_from(pc, pb)

    # 小さい方の弧（差が180未満）になるよう start/end を選ぶ
    diff = (ang_cb - ang_ca) % 360.0
    if diff <= 180.0:
        start_c, end_c = ang_ca, ang_ca + diff
    else:
        start_c, end_c = ang_cb, ang_cb + (360.0 - diff)

    elements.append({
        "type": "arc",
        "center": list(pc),
        "radius": 1.0,
        "start_angle": start_c,
        "end_angle": end_c,
    })
    elements.append({"type": "angle_label", "vertex": list(pc), "label": "x°"})

    viewport = [0.0, 0.0, 10.0, 10.0]
    return elements, viewport


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
        elif name == "PointAtom":
            label = str(sym.get("label", sympy.Symbol("A")))
            elements.append({
                "type": "point_on_graph",
                "x": _to_float(sym.get("x", sympy.Integer(0))),
                "y": _to_float(sym.get("y", sympy.Integer(0))),
                "label": label,
            })
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
