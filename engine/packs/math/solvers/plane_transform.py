"""平面図形の移動（平行移動・回転移動・対称移動）まわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（移動前の頂点座標＋移動の指定）から、移動後の頂点座標を
再計算する。純粋・決定論であること。乱数は引かない。答えは GraphAnswer（Feature の
集合＝各頂点の移動後座標。順序に依らない集合一致で double-solve 検証する。既存の
`math.draw_segment_features`（端点2つの集合一致）と同型）。

C7（g1 平面図形）クラスタの graph_table セル（g1_l38 平行移動・g1_l39 回転移動・
g1_l40 対称移動）を扱う。回転は反時計回り(CCW)・90/180/270° のみ対応（格子点→格子点
の閉じた式で trig を使わず厳密）。対称移動は x軸/y軸のみ対応（軸に平行でない直線ℓに
ついての対称移動は本セルでは扱わない）。

narration には数字を書かない（steps は恒真の手順説明のみで、具体的な移動量・座標は
recipe 側の given/params にのみ現れる）。
"""
from __future__ import annotations

from typing import Callable, cast

import sympy

from engine.core.contracts import Feature, GraphAnswer, Solution, Step
from engine.core.registry import register_solver


def _parse_xy(s: object) -> tuple[sympy.Integer, sympy.Integer]:
    """"(x, y)" 形の文字列/Tuple を (Integer, Integer) に変換する。"""
    t = sympy.sympify(str(s))
    return sympy.Integer(t[0]), sympy.Integer(t[1])


def _features_from_points(pts: list[tuple[sympy.Integer, sympy.Integer]]) -> list[Feature]:
    out = []
    for x, y in pts:
        disp = f"({x}, {y})"
        out.append(Feature(kind="point", srepr=sympy.srepr(sympy.Tuple(x, y)), display=disp))
    return out


# ---------------------------------------------------------------------------
# math.translate_polygon_features（g1_l38.graph_table Lv1/Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.translate_polygon_features")
def translate_polygon_features(points: object, dx: object, dy: object) -> Solution:
    """多角形を平行移動した後の各頂点の座標を求める（g1_l38.graph_table）。

    移動前の頂点座標の列と移動量(dx, dy)だけから計算する（double-solve）。
    答えは GraphAnswer（各頂点の移動後座標を Feature の集合で表す）。
    """
    pts = [_parse_xy(p) for p in cast("list[object]", points)]
    d_x, d_y = sympy.Integer(int(str(dx))), sympy.Integer(int(str(dy)))
    new_pts = [(x + d_x, y + d_y) for x, y in pts]
    steps = [
        Step(
            op="identify_translation_vector",
            args=[], result_srepr="", result_display="平行移動の向きと距離を読み取る",
            narration="平行移動の向きと距離を読み取る。",
        ),
        Step(
            op="translate_each_vertex",
            args=[], result_srepr="", result_display="各頂点を同じ向き・距離だけ移動する",
            narration="もとの図形の各頂点を、同じ向きに同じ距離だけ移動する。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=_features_from_points(new_pts)), steps=steps)


# ---------------------------------------------------------------------------
# math.rotate_polygon_features（g1_l39.graph_table Lv1/Lv2）
# ---------------------------------------------------------------------------
_RotateFormula = Callable[
    [sympy.Integer, sympy.Integer, sympy.Integer, sympy.Integer],
    tuple[sympy.Integer, sympy.Integer],
]
_ROTATE_FORMULAS: dict[int, _RotateFormula] = {
    90: lambda x, y, cx, cy: (cx - (y - cy), cy + (x - cx)),
    180: lambda x, y, cx, cy: (2 * cx - x, 2 * cy - y),
    270: lambda x, y, cx, cy: (cx + (y - cy), cy - (x - cx)),
}


@register_solver("math.rotate_polygon_features")
def rotate_polygon_features(points: object, center: object, angle_deg: object) -> Solution:
    """多角形を回転移動した後の各頂点の座標を求める（g1_l39.graph_table）。

    移動前の頂点座標の列・回転の中心・回転角(反時計回り・90/180/270のみ)だけから
    計算する（double-solve）。答えは GraphAnswer。
    """
    pts = [_parse_xy(p) for p in cast("list[object]", points)]
    cx, cy = _parse_xy(center)
    angle = int(str(angle_deg))
    if angle not in _ROTATE_FORMULAS:
        raise ValueError(f"未対応の回転角: {angle}")
    formula = _ROTATE_FORMULAS[angle]
    new_pts = [formula(x, y, cx, cy) for x, y in pts]
    steps = [
        Step(
            op="identify_center_and_angle",
            args=[], result_srepr="", result_display="回転の中心と回転角を読み取る",
            narration="回転の中心と、反時計回りの回転角を読み取る。",
        ),
        Step(
            op="rotate_each_vertex",
            args=[], result_srepr="", result_display="各頂点を回転の中心のまわりに回転させる",
            narration="もとの図形の各頂点を、回転の中心のまわりに同じ角だけ回転させる。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=_features_from_points(new_pts)), steps=steps)


# ---------------------------------------------------------------------------
# math.reflect_polygon_features（g1_l40.graph_table Lv1/Lv2）
# ---------------------------------------------------------------------------
_ReflectFormula = Callable[[sympy.Integer, sympy.Integer], tuple[sympy.Integer, sympy.Integer]]
_REFLECT_FORMULAS: dict[str, _ReflectFormula] = {
    "x_axis": lambda x, y: (x, -y),
    "y_axis": lambda x, y: (-x, y),
}


@register_solver("math.reflect_polygon_features")
def reflect_polygon_features(points: object, axis: object) -> Solution:
    """多角形を対称移動した後の各頂点の座標を求める（g1_l40.graph_table）。

    移動前の頂点座標の列・対称の軸(x軸/y軸のみ)だけから計算する（double-solve）。
    答えは GraphAnswer。
    """
    pts = [_parse_xy(p) for p in cast("list[object]", points)]
    ax = str(axis)
    if ax not in _REFLECT_FORMULAS:
        raise ValueError(f"未対応の対称の軸: {ax}")
    formula = _REFLECT_FORMULAS[ax]
    new_pts = [formula(x, y) for x, y in pts]
    steps = [
        Step(
            op="identify_axis",
            args=[], result_srepr="", result_display="対称の軸を読み取る",
            narration="対称移動の軸がどこにあるかを読み取る。",
        ),
        Step(
            op="reflect_each_vertex",
            args=[], result_srepr="", result_display="各頂点を軸について折り返す",
            narration="もとの図形の各頂点を、軸について反対側の同じ距離の位置に折り返す。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=_features_from_points(new_pts)), steps=steps)
