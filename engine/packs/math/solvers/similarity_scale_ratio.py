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


@register_solver("math.similar_triangle_trapezoid_area_ratio")
def similar_triangle_trapezoid_area_ratio(ad: object, db: object) -> Solution:
    """DE∥BC、AD:DBの比から、三角形ADEと台形DBCEの面積比を求める

    （g3_l45.find_value Lv3）。ad/db だけから、まずADとAB全体の比になおし、
    三角形ADEと三角形ABCの面積比が相似比の二乗に等しいという既存の性質
    （math.similar_area_ratio と同じ関係）を使って三角形ABC全体との面積比を
    求め、三角形ABC全体の面積から三角形ADEの面積を除いた残りが台形DBCEの
    面積になるという合成で、三角形ADEと台形DBCEの面積比を導く
    （double-solve）。
    """
    a = sympy.Integer(int(str(ad)))
    b = sympy.Integer(int(str(db)))
    ab = a + b
    ade, whole = a * a, ab * ab
    trapezoid = whole - ade
    g = sympy.gcd(ade, trapezoid)
    ratio_num, ratio_den = ade // g, trapezoid // g
    result = sympy.Tuple(ratio_num, ratio_den)
    disp = f"三角形ADE:台形DBCE = {ratio_num}:{ratio_den}"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="convert_partial_to_whole_ratio",
            args=[], result_srepr="", result_display="ADとAB全体の比になおす",
            narration="ADとDBの比から、ADとAB全体の比になおす。",
        ),
        Step(
            op="square_similarity_ratio",
            args=[], result_srepr="",
            result_display="相似比を二乗して三角形ADEと三角形ABCの面積比を求める",
            narration="三角形ADEと三角形ABCは相似であることから、面積比は相似比の二乗に"
            "等しいことを使って、三角形ADEと三角形ABC全体の面積比を求める。",
        ),
        Step(
            op="compute_trapezoid_remainder_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration="三角形ABC全体の面積から三角形ADEの面積を除いた残りが台形の面積に"
            "なることから、三角形ADEと台形の面積比を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.similar_solid_ratio_from_volume")
def similar_solid_ratio_from_volume(vol_p: object, vol_q: object) -> Solution:
    """相似な2つの立体P, Qの体積から、相似比を逆算して表面積の比を求める

    （g3_l46.find_value Lv3）。vol_p/vol_q だけから、体積の比を最も簡単な
    整数の比に直し、体積比が相似比の三乗に等しいという恒真の性質から相似比を
    復元し、表面積比が相似比の二乗に等しいという既存の性質
    （math.similar_solid_surface_volume_ratio と同じ関係）を使って表面積の比を
    求める（double-solve）。
    """
    vp = int(str(vol_p))
    vq = int(str(vol_q))
    ratio = sympy.Rational(vp, vq)
    num, den = int(ratio.p), int(ratio.q)
    m_root, m_exact = sympy.integer_nthroot(num, 3)
    n_root, n_exact = sympy.integer_nthroot(den, 3)
    if not (m_exact and n_exact):
        raise ValueError("similar_solid_ratio_from_volume: 体積比が完全立方数比ではない")
    m, n = sympy.Integer(m_root), sympy.Integer(n_root)
    surface_num, surface_den = m * m, n * n
    result = sympy.Tuple(surface_num, surface_den)
    disp = f"表面積の比 {surface_num}:{surface_den}"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="reduce_volume_ratio",
            args=[], result_srepr="", result_display="体積の比を最も簡単な整数の比に直す",
            narration="PとQの体積の比を、最も簡単な整数の比に直す。",
        ),
        Step(
            op="extract_similarity_ratio_via_cube_root",
            args=[], result_srepr="", result_display="体積の比から相似比を求める",
            narration="体積の比は相似比の三乗に等しいことから、相似比を求める。",
        ),
        Step(
            op="square_ratio_for_surface_area",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な立体の表面積の比は相似比の二乗に等しいことから、表面積の比を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
