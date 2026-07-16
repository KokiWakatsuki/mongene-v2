"""相似比から面積比・表面積比・体積比を求めるまわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l45/l46 を扱う:
  - `math.similar_area_ratio`: g3_l45.find_value Lv2（相似比から面積比(2乗)を
    求め、既知の面積から対応する面積を求める）
  - `math.similar_solid_surface_volume_ratio`: g3_l46.find_value Lv2（相似比
    から表面積比(2乗)・体積比(3乗)を直接求める）

面積比が相似比の2乗、体積比が相似比の3乗であることの想起は既存の
`math.recall_rule` ハブに topic を追加して対応する。

narration には数字を書かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


@register_solver("math.similar_area_ratio")
def similar_area_ratio(ratio_num: object, ratio_den: object, known_area: object) -> Solution:
    """相似比から面積比を求め、既知の面積から対応する面積を求める

    （g3_l45.find_value Lv2）。ratio_num/ratio_den/known_area だけから、面積比
    が相似比の二乗に等しいという恒真の性質で計算する（double-solve）。
    known_area は ratio_num 側の図形の面積とし、答えは
    Tuple(面積比の分子, 面積比の分母, ratio_den 側の図形の面積)。
    """
    m = sympy.sympify(str(ratio_num))
    n = sympy.sympify(str(ratio_den))
    a = sympy.sympify(str(known_area))
    area_ratio_num, area_ratio_den = m**2, n**2
    other_area = a * area_ratio_den / area_ratio_num
    result = sympy.Tuple(area_ratio_num, area_ratio_den, other_area)
    disp = f"面積比 {area_ratio_num}:{area_ratio_den}、大きいほうの面積 {sympy.sstr(other_area)}"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="square_similarity_ratio",
            args=[], result_srepr="", result_display="相似比を二乗して面積比を求める",
            narration="相似な図形の面積比は相似比の二乗に等しいことから、面積比を求める。",
        ),
        Step(
            op="apply_area_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration="求めた面積比と、わかっている一方の面積から、もう一方の面積を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.similar_solid_surface_volume_ratio")
def similar_solid_surface_volume_ratio(ratio_num: object, ratio_den: object) -> Solution:
    """相似比から表面積比(2乗)・体積比(3乗)を直接求める（g3_l46.find_value Lv2）。

    ratio_num/ratio_den だけから、表面積比が相似比の二乗、体積比が相似比の三乗
    に等しいという恒真の性質で計算する（double-solve）。答えは
    Tuple(表面積比の分子, 表面積比の分母, 体積比の分子, 体積比の分母)。
    """
    m = sympy.sympify(str(ratio_num))
    n = sympy.sympify(str(ratio_den))
    surface_num, surface_den = m**2, n**2
    volume_num, volume_den = m**3, n**3
    result = sympy.Tuple(surface_num, surface_den, volume_num, volume_den)
    disp = f"表面積の比 {surface_num}:{surface_den}、体積の比 {volume_num}:{volume_den}"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="square_ratio_for_surface_area",
            args=[], result_srepr="", result_display="相似比を二乗して表面積の比を求める",
            narration="相似な立体の表面積の比は相似比の二乗に等しいことから、表面積の比を求める。",
        ),
        Step(
            op="cube_ratio_for_volume",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な立体の体積の比は相似比の三乗に等しいことから、体積の比を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
