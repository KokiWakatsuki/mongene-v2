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


def _points(labels: object, default: str = "ABCDE") -> tuple[str, str, str, str, str]:
    """頂点の記号（A,B,C,D,E の順）。

    **問題文の頂点名は recipe が引く**ので、solver がここを固定にすると
    「三角形EABで…辺ABの長さを求めよ」と問うて「DE∥BC であることから、
    三角形ADEと三角形ABCが相似になる」と解説することになる（実際そうなっていた）。
    recipe から受け取り、無ければ既定を使う。
    """
    s = str(labels or default)
    if len(s) < 5:
        s = default
    return (s[0], s[1], s[2], s[3], s[4])


@register_solver("math.parallel_segment_ratio_length")
def parallel_segment_ratio_length(
    ad: object, db: object, de: object, labels: object = None
) -> Solution:
    """DE∥BC のとき、AD,DB,DE から辺BCの長さを求める（g3_l42.find_value Lv2）。

    ad/db/de だけから、DE∥BC により三角形ADE∽三角形ABCとなり
    AD:AB=DE:BC が成り立つという恒真の性質で計算する（double-solve）。
    `labels` は問題文の頂点名（A,B,C,D,E の順）で、解説の記号を問題文に
    合わせるためだけに使う（計算には効かない）。
    """
    pa, pb, pc, pd, pe = _points(labels)
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
            narration=f"{pd}{pe}∥{pb}{pc} であることから、三角形{pa}{pd}{pe}と"
            f"三角形{pa}{pb}{pc}が相似になることを見つける。",
        ),
        Step(
            op="apply_parallel_segment_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration=f"{pa}{pd}:{pa}{pb}={pd}{pe}:{pb}{pc} が成り立つことから、"
            f"辺{pb}{pc}の長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_parallel_from_ratio")
def judge_parallel_from_ratio(
    ad: object, db: object, ae: object, ec: object, labels: object = None
) -> Solution:
    """AD:DBとAE:ECの比を比べて、DE∥BCといえるかを確かめる（g3_l43.find_value Lv2）。

    ad/db/ae/ec だけから、AD:DB=AE:EC が成り立つならば平行線と線分の比の定理の
    逆によりDE∥BCといえるという恒真の判定で計算する（double-solve）。答えは
    真偽値のSymbolicAnswer。`labels` は問題文の頂点名（A,B,C,D,E の順）で、
    解説の記号を問題文に合わせるためだけに使う（判定には効かない）。
    """
    pa, pb, pc, pd, pe = _points(labels)
    a, b, c, d = int(str(ad)), int(str(db)), int(str(ae)), int(str(ec))
    is_parallel = a * d == b * c
    result = sympy.true if is_parallel else sympy.false
    disp = "平行である" if is_parallel else "平行ではない"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="compare_division_ratios",
            args=[], result_srepr="",
            result_display=f"{pa}{pd}:{pd}{pb}と{pa}{pe}:{pe}{pc}の比を比べる",
            narration=f"{pa}{pd}:{pd}{pb}と{pa}{pe}:{pe}{pc}の比が等しいかどうかを比べる。",
        ),
        Step(
            op="judge_by_parallel_ratio_converse",
            args=[], result_srepr=srepr, result_display=disp,
            narration=f"平行線と線分の比の定理の逆から、{pd}{pe}と{pb}{pc}が"
            "平行であるかどうかを判別する。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.parallel_lines_transversal_ratio")
def parallel_lines_transversal_ratio(ab: object, de: object, ef: object) -> Solution:
    """3本の平行線が2直線と交わってできる線分の比から、辺の長さを求める

    （g3_l42.find_value Lv3）。ab/de/ef だけから、3本の平行な直線が2本の直線と
    交わるとき対応する線分の比は等しいという恒真の性質 AB:BC=DE:EF から
    BC=AB*EF/DE を求める（double-solve）。
    """
    a = sympy.sympify(str(ab))
    d = sympy.sympify(str(de))
    e = sympy.sympify(str(ef))
    result = a * e / d
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_parallel_lines_cut_transversals",
            args=[], result_srepr="", result_display="3本の平行線が2直線を切る比例関係を見つける",
            narration="3本の平行な直線が2本の直線と交わるとき、対応する線分の比が等しくなることを見つける。",
        ),
        Step(
            op="apply_transversal_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration="対応する線分の比が等しいことから、比例式を立てて長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.parallel_ratio_judge_then_length")
def parallel_ratio_judge_then_length(
    ad: object, db: object, ae: object, ec: object, de: object, labels: object = None
) -> Solution:
    """AD:DBとAE:ECの比が等しいことからDE∥BCを確かめたうえで、DEの長さから

    辺BCの長さを求める（g3_l43.find_value Lv3）。既存の
    math.judge_parallel_from_ratio（逆による判定）と
    math.parallel_segment_ratio_length（DE∥BCからの長さ計算）をそのまま
    合成した double-solve。ad/db/ae/ec/de だけから計算する（新しい数学的
    計算は増やさない）。
    """
    judge_sol = judge_parallel_from_ratio(ad, db, ae, ec, labels)
    length_sol = parallel_segment_ratio_length(ad, db, de, labels)
    assert isinstance(length_sol.answer, SymbolicAnswer)
    steps = list(judge_sol.steps) + list(length_sol.steps)
    return Solution(answer=length_sol.answer, steps=steps)


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
