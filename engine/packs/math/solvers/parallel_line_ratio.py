"""平行線と線分の比の定理・その逆・中点連結定理まわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l42/l43/l44 を扱う:
  - `math.parallel_segment_ratio_length`: g3_l42.find_value Lv2（DE∥BC のとき
    AD,DB,DE から BC を求める）
  - `math.judge_parallel_from_ratio`: g3_l43.find_value Lv2（AD:DB と AE:EC の
    比を比べて DE∥BC といえるかを確かめる・SymbolicAnswer の真偽値）
  - `math.midpoint_connector_length`: g3_l44.find_value Lv2（中点連結定理で
    MN=BC/2 を求める）

定理・その逆・中点連結定理の内容の想起は既存の `math.recall_rule` ハブに topic
を追加して対応する。

narration には数字を書かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


@register_solver("math.parallel_segment_ratio_length")
def parallel_segment_ratio_length(ad: object, db: object, de: object) -> Solution:
    """DE∥BC のとき、AD,DB,DE から辺BCの長さを求める（g3_l42.find_value Lv2）。

    ad/db/de だけから、DE∥BC により三角形ADE∽三角形ABCとなり
    AD:AB=DE:BC が成り立つという恒真の性質で計算する（double-solve）。
    """
    a = sympy.sympify(str(ad))
    b = sympy.sympify(str(db))
    e = sympy.sympify(str(de))
    result = e * (a + b) / a
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_similar_triangles_from_parallel",
            args=[], result_srepr="", result_display="平行線がつくる相似な三角形を見つける",
            narration="DE∥BC であることから、三角形ADEと三角形ABCが相似になることを見つける。",
        ),
        Step(
            op="apply_parallel_segment_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration="AD:AB=DE:BC が成り立つことから、辺BCの長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_parallel_from_ratio")
def judge_parallel_from_ratio(ad: object, db: object, ae: object, ec: object) -> Solution:
    """AD:DBとAE:ECの比を比べて、DE∥BCといえるかを確かめる（g3_l43.find_value Lv2）。

    ad/db/ae/ec だけから、AD:DB=AE:EC が成り立つならば平行線と線分の比の定理の
    逆によりDE∥BCといえるという恒真の判定で計算する（double-solve）。答えは
    真偽値のSymbolicAnswer。
    """
    a, b, c, d = int(str(ad)), int(str(db)), int(str(ae)), int(str(ec))
    is_parallel = a * d == b * c
    result = sympy.true if is_parallel else sympy.false
    disp = "平行である" if is_parallel else "平行ではない"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="compare_division_ratios",
            args=[], result_srepr="", result_display="AD:DBとAE:ECの比を比べる",
            narration="AD:DBとAE:ECの比が等しいかどうかを比べる。",
        ),
        Step(
            op="judge_by_parallel_ratio_converse",
            args=[], result_srepr=srepr, result_display=disp,
            narration="平行線と線分の比の定理の逆から、DEとBCが平行であるかどうかを判別する。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.midpoint_connector_length")
def midpoint_connector_length(bc: object) -> Solution:
    """中点連結定理で、中点を結ぶ線分の長さを求める（g3_l44.find_value Lv2）。

    bc（残りの辺の長さ）だけから、中点を結ぶ線分の長さは残りの辺の長さの半分に
    等しいという恒真の性質で計算する（double-solve）。
    """
    v = sympy.sympify(str(bc))
    result = v / 2
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_remaining_side",
            args=[], result_srepr="", result_display="残りの辺の長さを読み取る",
            narration="三角形の2辺の中点を結ぶ線分に対して、残りの辺の長さを読み取る。",
        ),
        Step(
            op="apply_midpoint_connector_theorem",
            args=[], result_srepr=srepr, result_display=disp,
            narration="中点を結ぶ線分の長さは、残りの辺の長さの半分に等しいことから、"
            "その長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
