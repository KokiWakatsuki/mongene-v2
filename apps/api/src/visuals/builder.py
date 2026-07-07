"""VisualBuilder（§37 _build_visual_dsl の実体）

Blueprint と sampled_nouns / logic_steps から VisualDSL を組み立てる。
"""
from __future__ import annotations

import json
import math
import re
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
        if blueprint.blueprint_id == "PythagoreanSpaceStructure":
            # 題材が「展開図を利用した表面上の最短距離」なので、立体ワイヤフレーム
            # ではなく 2D 展開図(net)を描く（表示専用・answer は不変）。
            return _build_net(sampled_nouns, logic_steps)
        if blueprint.blueprint_id == "BasicDifferenceStructure":
            # 設計書 §18.3: cutout_volume を主立体の内部に点線で描く
            return _build_3d_with_cutout_inside(sampled_nouns)
        return _build_3d(sampled_nouns)
    if component == "2D_Geometry_Renderer":
        if blueprint.blueprint_id in ("ProofStructure", "CongruenceFigureStructure"):
            return _build_congruence_proof(sampled_nouns, logic_steps)
        return _build_2d_geometry(sampled_nouns)
    if component == "Graph_Renderer":
        return _build_graph(sampled_nouns)
    if component == "Tree_Renderer":
        return _build_tree(sampled_nouns)
    if component in {"Table_&_Chart_Renderer", "TableChart_Renderer", "Table_Chart_Renderer"}:
        return _build_table_chart(sampled_nouns, logic_steps)
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


def _build_net(sampled_nouns: Dict[str, NounAtom], logic_steps: Dict[str, Any]) -> VisualDSL:
    """PythagoreanSpaceStructure 専用: 直方体の表面最短距離を、立体ではなく
    2D 展開図(net)として描く。verb が採用した展開パターン（3通りの最小）を
    a,b,h から再導出するだけ（表示専用・answer/logic_steps は不変）。
    PrismAtom 以外（pyramid 等）は今回対象外＝3D にフォールバック。
    """
    solids = [
        atom for atom in sampled_nouns.values()
        if type(atom).__name__ in ("PrismAtom", "PyramidAtom")
    ]
    if not solids:
        return _build_3d(sampled_nouns)
    solid = solids[0]
    if type(solid).__name__ != "PrismAtom":
        return _build_3d(sampled_nouns)

    sym = solid.get_symbols()
    a = _to_float(sym.get("width", sympy.Integer(4)))
    b = _to_float(sym.get("depth", sympy.Integer(4)))
    h = _to_float(sym.get("height", sympy.Integer(5)))

    # verb と同じ 3 パターンの距離を再計算し、採用パターン(最小)を選ぶ
    d = [math.hypot(a, b + h), math.hypot(b, a + h), math.hypot(a + b, h)]
    idx = d.index(min(d))

    elements: list[dict] = []

    if idx == 0:
        W, H = a, b + h
        fold = b  # 水平折り線 y=b
        vertical_fold = False
        # 寸法ラベル: 下辺=a, 左辺下部(0..b)=b, 左辺上部(b..b+h)=h
        dim_labels = [
            (W / 2, -0.8, a),      # 下辺
            (-0.9, b / 2, b),      # 左辺下部
            (-0.9, b + h / 2, h),  # 左辺上部
        ]
    elif idx == 1:
        W, H = b, a + h
        fold = a  # 水平折り線 y=a
        vertical_fold = False
        dim_labels = [
            (W / 2, -0.8, b),      # 下辺
            (-0.9, a / 2, a),      # 左辺下部
            (-0.9, a + h / 2, h),  # 左辺上部
        ]
    else:
        W, H = a + b, h
        fold = a  # 垂直折り線 x=a
        vertical_fold = True
        dim_labels = [
            (a / 2, -0.8, a),          # 下辺左(0..a)
            (a + b / 2, -0.8, b),      # 下辺右(a..a+b)
            (-0.9, H / 2, h),          # 左辺
        ]

    # 外枠矩形
    elements.append({
        "type": "polygon",
        "vertices": [[0, 0], [W, 0], [W, H], [0, H]],
        "filled": False,
    })
    # 折り線（破線）
    if vertical_fold:
        elements.append({"type": "line_segment", "p1": [fold, 0], "p2": [fold, H], "dashed": True})
    else:
        elements.append({"type": "line_segment", "p1": [0, fold], "p2": [W, fold], "dashed": True})
    # 最短経路（実線）
    elements.append({"type": "line_segment", "p1": [0, 0], "p2": [W, H]})
    # 端点ラベル
    elements.append({"type": "point", "x": 0, "y": 0, "label": "A"})
    elements.append({"type": "point", "x": W, "y": H, "label": "G"})
    # 寸法ラベル
    for lx, ly, val in dim_labels:
        elements.append({"type": "text", "x": lx, "y": ly, "content": f"{_fmt(val)}"})

    viewport = (-1.5, -1.5, W + 1.5, H + 1.5)
    return VisualDSL(render_type="2D_Geometry", elements=elements, viewport=tuple(viewport))


def _polygon_marks(polygon_type: str, verts: list[list[float]]) -> list[dict]:
    """polygon_type と頂点列から幾何記号要素を導出する。

    表示のみ。数値・answer には一切影響しない。頂点ラベルは polygon 要素側で付与し、
    ここでは right_angle_mark / tick_mark / angle_arc / parallel_mark を返す。
    """
    marks: list[dict] = []
    n = len(verts)
    if n == 0:
        return marks

    def _tick(i: int, count: int) -> dict:
        return {
            "type": "tick_mark",
            "p1": verts[i],
            "p2": verts[(i + 1) % n],
            "count": count,
        }

    def _angle_arc(vi: int, count: int) -> dict:
        return {
            "type": "angle_arc",
            "vertex": verts[vi],
            "p1": verts[(vi - 1) % n],
            "p2": verts[(vi + 1) % n],
            "count": count,
        }

    def _parallel(i: int, count: int) -> dict:
        return {
            "type": "parallel_mark",
            "p1": verts[i],
            "p2": verts[(i + 1) % n],
            "count": count,
        }

    # (b) 直角マーク
    if polygon_type == "right_triangle" and n >= 3:
        marks.append(
            {
                "type": "right_angle_mark",
                "vertex": verts[0],
                "p1": verts[1],
                "p2": verts[2],
            }
        )
    elif polygon_type in ("square", "rectangle") and n >= 3:
        marks.append(
            {
                "type": "right_angle_mark",
                "vertex": verts[0],
                "p1": verts[1],
                "p2": verts[-1],
            }
        )

    # (c) 等長マーク
    if polygon_type in ("square", "rhombus", "equilateral_triangle"):
        for i in range(n):
            marks.append(_tick(i, 1))
    elif polygon_type == "isoceles_triangle" and n >= 3:
        # verts=[底辺左, 底辺右, 頂点]。等しい2脚 = 辺(v1->v2), 辺(v2->v0)
        marks.append(_tick(1, 1))
        marks.append(_tick(2, 1))

    # (d) 等角マーク（angle_arc）
    if polygon_type == "equilateral_triangle" and n >= 3:
        # 正三角形: 全3頂点の内角が等しい
        for i in range(n):
            marks.append(_angle_arc(i, 1))
    elif polygon_type == "isoceles_triangle" and n >= 3:
        # verts=[底辺左v0, 底辺右v1, 頂点v2]。底角 = v0, v1
        marks.append(_angle_arc(0, 1))
        marks.append(_angle_arc(1, 1))

    # (e) 平行マーク（parallel_mark）
    if polygon_type == "parallelogram" and n >= 4:
        # 対辺が平行: 辺0/辺2 に count=1（水平対辺）、辺1/辺3 に count=2（斜辺対辺）
        marks.append(_parallel(0, 1))
        marks.append(_parallel(2, 1))
        marks.append(_parallel(1, 2))
        marks.append(_parallel(3, 2))
    elif polygon_type == "trapezoid" and n >= 4:
        # 上底・下底のみ平行: 辺0（下底）/辺2（上底）に count=1
        marks.append(_parallel(0, 1))
        marks.append(_parallel(2, 1))

    return marks


def _build_2d_geometry(sampled_nouns: Dict[str, NounAtom]) -> VisualDSL:
    elements: list[dict] = []
    viewport = [-1.0, -1.0, 10.0, 10.0]
    # 動点（MovingPointAtom）が同席する場合は PolygonAtom の辺上に点 P を描く（題材一致）
    has_mover = any(type(a).__name__ == "MovingPointAtom" for a in sampled_nouns.values())
    for slot_name, atom in sampled_nouns.items():
        name = type(atom).__name__
        sym = atom.get_symbols()
        if name == "PolygonAtom":
            verts_raw = getattr(atom, "vertices", None) or []
            verts = [[_to_float(v[0]), _to_float(v[1])] for v in verts_raw]
            if verts:
                polygon_type = getattr(atom, "polygon_type", "triangle")
                vertex_labels = [chr(ord("A") + i) for i in range(len(verts))]
                elements.append(
                    {
                        "type": "polygon",
                        "vertices": verts,
                        "filled": False,
                        "vertex_labels": vertex_labels,
                    }
                )
                elements.extend(_polygon_marks(polygon_type, verts))
                if has_mover and len(verts) >= 3:
                    # 点 P を辺 B→C（頂点[1]→[2]）の中点に描く（動点の代表位置・表示のみ）
                    bx, by = verts[1]
                    cx, cy = verts[2]
                    elements.append(
                        {
                            "type": "point",
                            "x": (bx + cx) / 2.0,
                            "y": (by + cy) / 2.0,
                            "label": "P",
                        }
                    )
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


def _build_congruence_proof(
    sampled_nouns: Dict[str, NounAtom],
    logic_steps: Dict[str, Any],
) -> VisualDSL:
    """ProofStructure 専用: 合同/相似の証明を 2 図形並置 + 対応マーク付きで描く。

    表示のみ。answer/logic_steps は不変（証明 template は sympy_expr=Integer(1)）。
    figure_b は figure_a の合同(平行移動)/相似(拡大+平行移動)コピーとして生成し、
    condition_set に応じて対応する辺・角に同じ count のマークを両図形へ打つ。
    """
    # 1. figure_a 取得（PolygonAtom を宣言順に集める）
    polygons = [a for a in sampled_nouns.values() if type(a).__name__ == "PolygonAtom"]
    if not polygons:
        return _build_2d_geometry(sampled_nouns)
    figure_a = polygons[0]
    verts_raw = getattr(figure_a, "vertices", None) or []
    base = [[_to_float(v[0]), _to_float(v[1])] for v in verts_raw]
    if not base:
        return _build_2d_geometry(sampled_nouns)

    # 2. proof 情報の抽出（既定値）
    proof_type = "congruence"
    condition_set = "SSS"
    labels_a = "ABC"
    labels_b = "DEF"
    step = logic_steps.get("proof") if logic_steps else None
    if step is not None:
        op = getattr(step, "operation_name", "")
        if "similarity" in op:
            proof_type = "similarity"
        ops = getattr(step, "operands", [])
        if len(ops) >= 3 and isinstance(ops[2], str):
            condition_set = ops[2]
        if len(ops) >= 4:
            try:
                tp = json.loads(ops[3])["to_prove"]
                found = re.findall(r"△(\w+)", tp)
                if len(found) >= 2:
                    labels_a = found[0][:3]
                    labels_b = found[1][:3]
            except Exception:
                pass

    # 3. RHS は直角三角形が要る（表示専用の正準直角三角形に置換）
    if proof_type == "congruence" and condition_set == "RHS":
        base = [[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]]

    n = len(base)

    # 4. figure_b を base の変換コピーで作る
    xs = [p[0] for p in base]
    ys = [p[1] for p in base]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    gap = max(w, 2.0) * 0.6 + 1.0
    if proof_type == "similarity":
        k = 1.4
        cx = sum(xs) / n
        cy = sum(ys) / n
        scaled = [[cx + (px - cx) * k, cy + (py - cy) * k] for px, py in base]
        sxs = [p[0] for p in scaled]
        dx = (max(xs) - min(sxs)) + gap
        fig_b = [[px + dx, py] for px, py in scaled]
    else:
        dx = w + gap
        fig_b = [[px + dx, py] for px, py in base]

    # 5. 要素生成
    def tick(verts: list[list[float]], i: int, c: int) -> dict:
        return {
            "type": "tick_mark",
            "p1": verts[i],
            "p2": verts[(i + 1) % len(verts)],
            "count": c,
        }

    def arc(verts: list[list[float]], vi: int, c: int) -> dict:
        m = len(verts)
        return {
            "type": "angle_arc",
            "vertex": verts[vi],
            "p1": verts[(vi - 1) % m],
            "p2": verts[(vi + 1) % m],
            "count": c,
        }

    def ramark(verts: list[list[float]], vi: int) -> dict:
        m = len(verts)
        return {
            "type": "right_angle_mark",
            "vertex": verts[vi],
            "p1": verts[(vi + 1) % m],
            "p2": verts[(vi - 1) % m],
        }

    elements: list[dict] = [
        {
            "type": "polygon",
            "vertices": base,
            "filled": False,
            "vertex_labels": list(labels_a)[:n],
        },
        {
            "type": "polygon",
            "vertices": fig_b,
            "filled": False,
            "vertex_labels": list(labels_b)[:n],
        },
    ]

    for verts in (base, fig_b):
        if proof_type == "similarity":
            # 相似: 辺の長さは等しくない → 対応角に arc のみ
            elements.append(arc(verts, 0, 1))
            elements.append(arc(verts, 1, 2))
        elif condition_set == "SAS":
            elements.append(tick(verts, 0, 1))
            elements.append(tick(verts, 1, 2))
            elements.append(arc(verts, 1, 1))
        elif condition_set == "ASA":
            elements.append(tick(verts, 0, 1))
            elements.append(arc(verts, 0, 1))
            elements.append(arc(verts, 1, 2))
        elif condition_set == "RHS":
            elements.append(ramark(verts, 0))
            elements.append(tick(verts, 1, 1))  # 斜辺 v1->v2
            elements.append(tick(verts, 0, 2))  # 脚 v0->v1
        else:  # SSS（およびその他）
            elements.append(tick(verts, 0, 1))
            elements.append(tick(verts, 1, 2))
            elements.append(tick(verts, 2, 3))

    # 6. viewport
    allx = [p[0] for p in base] + [p[0] for p in fig_b]
    ally = [p[1] for p in base] + [p[1] for p in fig_b]
    margin = 1.5
    viewport = (
        min(allx) - margin,
        min(ally) - margin,
        max(allx) + margin,
        max(ally) + margin,
    )

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


def _fmt_coord(v: sympy.Expr) -> str:
    """座標ラベル用に sympy 値を整数/分数の綺麗な文字列にする（表示専用）。"""
    try:
        s = sympy.nsimplify(v)
    except Exception:
        s = v
    if getattr(s, "is_integer", False):
        return str(int(s))
    return str(s)


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

    # --- 交点マーカー・三角形の塗り（表示専用: answer/logic_steps は不変） ---
    # (a) 関数 Atom（LinearFuncAtom / QuadraticFuncAtom）を収集
    x = sympy.Symbol("x")
    linear_atoms: list[NounAtom] = []
    func_atoms: list[NounAtom] = []  # Linear + Quadratic（宣言順）
    for atom in sampled_nouns.values():
        name = type(atom).__name__
        if name == "LinearFuncAtom":
            linear_atoms.append(atom)
            func_atoms.append(atom)
        elif name == "QuadraticFuncAtom":
            func_atoms.append(atom)

    filled_region_els: list[dict] = []
    intersection_els: list[dict] = []

    if len(func_atoms) >= 2:
        f1, f2 = func_atoms[0], func_atoms[1]
        try:
            e1 = f1.get_symbols()["expression"]
            e2 = f2.get_symbols()["expression"]
            sols = sympy.solve(e1 - e2, x)
            real_sols: list[sympy.Expr] = []
            for s in sols:
                # 実数解のみ
                if sympy.im(s) == 0 and s.is_real is not False:
                    real_sols.append(s)
                    y = e1.subs(x, s)
                    intersection_els.append({
                        "type": "intersection_point",
                        "x": float(s),
                        "y": float(y),
                        "label": f"({_fmt_coord(s)}, {_fmt_coord(y)})",
                    })

            # (c) 三角形の塗り（FGF のみ）: ちょうど2つの LinearFuncAtom、
            #     slope が異なり、実数交点がちょうど1つのとき y軸三角形を塗る
            is_two_linear = len(func_atoms) == 2 and len(linear_atoms) == 2
            if is_two_linear and len(real_sols) == 1:
                slope1 = f1.get_symbols().get("slope")
                slope2 = f2.get_symbols().get("slope")
                if slope1 is not None and slope2 is not None and sympy.simplify(slope1 - slope2) != 0:
                    b1 = float(f1.y_intercept())
                    b2 = float(f2.y_intercept())
                    x0 = float(real_sols[0])
                    y0 = float(e1.subs(x, real_sols[0]))
                    filled_region_els.append({
                        "type": "filled_region",
                        "vertices": [[0, b1], [0, b2], [x0, y0]],
                        "color": "#cccccc",
                        "alpha": 0.35,
                    })
        except Exception:
            # solve 失敗・複素数のみ・平行（解なし）等では交点/塗りを出さない
            pass

    # filled_region を先（背面）、intersection_point を後（前面）
    elements.extend(filled_region_els)
    elements.extend(intersection_els)

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


def _build_table_chart(
    sampled_nouns: Dict[str, NounAtom],
    logic_steps: Dict[str, Any] | None = None,
) -> VisualDSL:
    """統計 visual を metric に応じて 箱ひげ図 / ヒストグラム(SVG) で組む。

    表示のみ。値は DataSetAtom（verb 計算済）から載せるだけで answer/logic_steps は不変。
    - metric が q1/q3/iqr/median → 箱ひげ図（quartiles 要素）
    - それ以外（mean/mode/cumulative 系・既定）→ ヒストグラム（bins 要素）
    どちらも作れない場合のみ従来の header_row/data_row（HTML table）にフォールバック。
    """
    # DataSetAtom を探す
    atom = None
    for _slot_name, cand in sampled_nouns.items():
        if type(cand).__name__ == "DataSetAtom":
            atom = cand
            break

    if atom is None:
        return VisualDSL(render_type="Table", elements=[])

    # metric 判定: logic_steps["result"].operation_name = "analyze_q1" 等
    metric = "mean"
    if logic_steps:
        step = logic_steps.get("result")
        op = getattr(step, "operation_name", "") or ""
        if op.startswith("analyze_"):
            metric = op.replace("analyze_", "")

    sym = atom.get_symbols()
    vals = [_to_float(v) for v in getattr(atom, "values", [])]
    fd = getattr(atom, "frequency_distribution", []) or []

    def _boxplot_elements() -> list[dict] | None:
        if not vals:
            return None
        q1 = _to_float(sym["q1"]) if "q1" in sym else min(vals)
        med = _to_float(sym["median"]) if "median" in sym else sorted(vals)[len(vals) // 2]
        q3 = _to_float(sym["q3"]) if "q3" in sym else max(vals)
        return [{
            "type": "quartiles",
            "quartiles": {
                "min": min(vals),
                "q1": q1,
                "median": med,
                "q3": q3,
                "max": max(vals),
            },
        }]

    def _histogram_elements() -> list[dict] | None:
        if not fd:
            return None
        return [{
            "type": "bins",
            "bins": [[float(lo), float(hi), int(c)] for (lo, hi, c) in fd],
        }]

    elements: list[dict] | None
    if metric in ("q1", "q3", "iqr", "median"):
        elements = _boxplot_elements()
        if elements is None:
            elements = _histogram_elements()
    else:
        elements = _histogram_elements()
        if elements is None:
            elements = _boxplot_elements()

    # 両方作れない場合のみ従来の HTML table フォールバック
    if elements is None:
        elements = [{"type": "header_row", "cells": ["指標", "値"]}]
        for key in ("mean", "median", "q1", "q3"):
            if key in sym:
                elements.append({"type": "data_row", "cells": [key, str(sym[key])]})

    return VisualDSL(render_type="Table", elements=elements)
