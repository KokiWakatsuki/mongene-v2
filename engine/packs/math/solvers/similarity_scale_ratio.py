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
            args=[], result_srepr="", result_display=f"{area_ratio_num}:{area_ratio_den}",
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
            args=[], result_srepr="", result_display=f"{surface_num}:{surface_den}",
            narration="相似な立体の表面積の比は相似比の二乗に等しいことから、表面積の比を求める。",
        ),
        Step(
            op="cube_ratio_for_volume",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な立体の体積の比は相似比の三乗に等しいことから、体積の比を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


def _points(labels: object, default: str = "ABCDE") -> tuple[str, str, str, str, str]:
    """頂点の記号（A,B,C,D,E の順）。

    **問題文の頂点名は recipe が引く**ので、solver がここを固定にすると
    「三角形AKJ の面積を求めよ」と問うて「三角形ADE:台形DBCE = 4:21」と答える
    ことになる（実際そうなっていた）。recipe から受け取り、無ければ既定を使う。
    """
    s = str(labels or default)
    if len(s) < 5:
        s = default
    return (s[0], s[1], s[2], s[3], s[4])


@register_solver("math.similar_triangle_trapezoid_area_ratio")
def similar_triangle_trapezoid_area_ratio(
    ad: object, db: object, labels: object = None
) -> Solution:
    """DE∥BC、AD:DBの比から、三角形ADEと台形DBCEの面積比を求める

    （g3_l45.find_value Lv3）。ad/db だけから、まずADとAB全体の比になおし、
    三角形ADEと三角形ABCの面積比が相似比の二乗に等しいという既存の性質
    （math.similar_area_ratio と同じ関係）を使って三角形ABC全体との面積比を
    求め、三角形ABC全体の面積から三角形ADEの面積を除いた残りが台形DBCEの
    面積になるという合成で、三角形ADEと台形DBCEの面積比を導く
    （double-solve）。
    """
    pa, pb, pc, pd, pe = _points(labels)
    small = f"三角形{pa}{pd}{pe}"
    whole_tri = f"三角形{pa}{pb}{pc}"
    trap = f"台形{pd}{pb}{pc}{pe}"
    a = sympy.Integer(int(str(ad)))
    b = sympy.Integer(int(str(db)))
    ab = a + b
    ade, whole = a * a, ab * ab
    trapezoid = whole - ade
    g = sympy.gcd(ade, trapezoid)
    ratio_num, ratio_den = ade // g, trapezoid // g
    result = sympy.Tuple(ratio_num, ratio_den)
    disp = f"{small}:{trap} = {ratio_num}:{ratio_den}"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="convert_partial_to_whole_ratio",
            args=[], result_srepr="",
            result_display=f"{pa}{pd}:{pa}{pb} = {a}:{ab}",
            narration=f"{pa}{pd}と{pd}{pb}の比から、{pa}{pd}と{pa}{pb}全体の比になおす。",
        ),
        Step(
            op="square_similarity_ratio",
            args=[], result_srepr="",
            result_display=f"{ade}:{whole}",
            narration=f"{small}と{whole_tri}は相似であることから、面積比は相似比の二乗に"
            f"等しいことを使って、{small}と{whole_tri}全体の面積比を求める。",
        ),
        Step(
            op="compute_trapezoid_remainder_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration=f"{whole_tri}全体の面積から{small}の面積を除いた残りが台形の面積に"
            f"なることから、{small}と台形の面積比を求める。",
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
            args=[], result_srepr="", result_display=f"{num}:{den}",
            narration="PとQの体積の比を、最も簡単な整数の比に直す。",
        ),
        Step(
            op="extract_similarity_ratio_via_cube_root",
            args=[], result_srepr="", result_display=f"{m}:{n}",
            narration="体積の比は相似比の三乗に等しいことから、相似比を求める。",
        ),
        Step(
            op="square_ratio_for_surface_area",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な立体の表面積の比は相似比の二乗に等しいことから、表面積の比を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.trapezoid_diagonal_area_ratios")
def trapezoid_diagonal_area_ratios(ad: object, bc: object) -> Solution:
    """台形の対角線の交点まわりの面積比を求める（exam_l6.word_problem Lv4）。

    AD∥BC の台形 ABCD で対角線 AC・BD の交点を P とすると、AD∥BC から
    △APD∽△CPB（X字型の相似）で相似比は AD:BC。したがって
      ・△APD:△CPB は相似比の二乗（既存 math.similar_area_ratio と同じ性質）
      ・AP:PC = AD:BC で、△APD と △APB は BD 上の PD・PB を底辺とし頂点 A を
        共有するので、面積の比は PD:PB = AD:BC
    という**二つの異なる比の使い方**を合成する。答えは
    Tuple(△APD:△CPB の分子, 同分母, △APD が △APB の何倍か)。
    ad/bc だけから計算する（double-solve）。
    """
    a = sympy.Integer(int(str(ad)))
    b = sympy.Integer(int(str(bc)))
    if a <= 0 or b <= 0 or a == b:
        raise ValueError("AD と BC は正で、互いに異なること（等しいと平行四辺形になる）")
    g = sympy.gcd(a**2, b**2)
    ratio_num, ratio_den = a**2 // g, b**2 // g
    times = sympy.Rational(a, b)
    result = sympy.Tuple(ratio_num, ratio_den, times)
    disp = (
        f"三角形APD:三角形BPC = {ratio_num}:{ratio_den}、"
        f"三角形APDは三角形APBの{sympy.sstr(times)}倍"
    )
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_x_shape_similarity",
            args=[], result_srepr="",
            result_display="三角形APD と 三角形BPC",
            narration="AD と BC が平行であることから、対頂角と錯角が等しく、"
            "対角線の交点をはさむ2つの三角形が相似であることがわかる。",
        ),
        Step(
            op="square_similarity_ratio",
            args=[], result_srepr="", result_display=f"{ratio_num}:{ratio_den}",
            narration="相似な図形の面積比は相似比の二乗に等しいことから、"
            "2つの三角形の面積の比を求める。",
        ),
        Step(
            op="compare_triangles_sharing_apex",
            args=[], result_srepr=srepr, result_display=disp,
            narration="対角線上の2つの線分の比が相似比と同じであることを使う。"
            "頂点を共有する2つの三角形の面積の比は、その底辺の比に等しいので、"
            "一方が他方の何倍かが求まる。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
