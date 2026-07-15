"""三平方の定理・その逆まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l51/l52 を扱う:
  - `math.pythagorean_hypotenuse`: g3_l51.find_value Lv1（直角をはさむ2辺から
    斜辺の長さを求める）
  - `math.identify_hypotenuse`: g3_l51.knowledge Lv2（直角の頂点の位置から斜辺
    を判別）
  - `math.verify_right_triangle_from_sides`: g3_l52.find_value Lv2（3辺の長さ
    から三平方の定理の逆で直角三角形かを確かめる・SymbolicAnswer の真偽値）
  - `math.judge_right_triangle_from_three_sides`: g3_l52.knowledge Lv2（同じ
    判定を ChoiceAnswer で答える）

定理・その逆の記述の想起（式の意味・逆の主張）は既存の `math.recall_rule` ハブに
topic を追加して対応する。

narration には数字を書かない。ChoiceAnswer の correct/distractor は digit-free
（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


@register_solver("math.pythagorean_hypotenuse")
def pythagorean_hypotenuse(leg_a: object, leg_b: object) -> Solution:
    """直角をはさむ2辺の長さから、斜辺の長さを求める（g3_l51.find_value Lv1）。

    leg_a/leg_b（直角をはさむ2辺の長さ）だけから、三平方の定理
    a²+b²=c² という恒真の性質で計算する（double-solve）。答えは斜辺の長さの
    SymbolicAnswer（整数または根号を含む簡約形）。
    """
    a = sympy.sympify(str(leg_a))
    b = sympy.sympify(str(leg_b))
    result = sympy.sqrt(a**2 + b**2)
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_two_legs",
            args=[], result_srepr="", result_display="直角をはさむ2辺の長さを読み取る",
            narration="直角三角形で、直角をはさむ2辺の長さを読み取る。",
        ),
        Step(
            op="apply_pythagorean_theorem",
            args=[], result_srepr=srepr, result_display=disp,
            narration="直角をはさむ2辺の長さの二乗の和が、斜辺の長さの二乗に等しいという"
            "三平方の定理から、斜辺の長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


def _side_name(labels: str, i: int, j: int) -> str:
    return f"辺{labels[i]}{labels[j]}"


@register_solver("math.identify_hypotenuse")
def identify_hypotenuse(labels: object, right_angle_index: object) -> Solution:
    """直角の頂点の位置から、斜辺がどの辺かを判別する（g3_l51.knowledge Lv2）。

    labels（3頂点の文字列）と right_angle_index（直角の頂点の位置）だけから、
    「直角の頂点に接していない辺が斜辺になる」という定義に従って機械的に決まる
    （double-solve）。答えは ChoiceAnswer。
    """
    lb = str(labels)
    ri = int(str(right_angle_index))
    other = [x for x in range(3) if x != ri]
    correct = _side_name(lb, other[0], other[1])
    distractors = [_side_name(lb, ri, other[0]), _side_name(lb, ri, other[1])]
    steps = [
        Step(
            op="identify_right_angle_vertex",
            args=[], result_srepr="", result_display="直角の頂点がどこかを読み取る",
            narration="直角三角形で、直角の頂点がどこかを読み取る。",
        ),
        Step(
            op="name_hypotenuse",
            args=[], result_srepr=correct, result_display=correct,
            narration="直角の頂点に接していない辺が斜辺になることから、斜辺を答える。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id="pythagorean.identify_hypotenuse")
    return Solution(answer=answer, steps=steps)


def _is_right_triangle_sorted(sides: tuple[int, int, int]) -> bool:
    p, q, r = sorted(sides)
    return p * p + q * q == r * r


@register_solver("math.verify_right_triangle_from_sides")
def verify_right_triangle_from_sides(side_a: object, side_b: object, side_c: object) -> Solution:
    """3辺の長さから、三平方の定理の逆で直角三角形であるかを確かめる

    （g3_l52.find_value Lv2）。3辺の長さだけから、最も長い辺の二乗と他の2辺の
    二乗の和を比べる恒真の判定で計算する（double-solve）。答えは真偽値の
    SymbolicAnswer。
    """
    a, b, c = int(str(side_a)), int(str(side_b)), int(str(side_c))
    is_right = _is_right_triangle_sorted((a, b, c))
    result = sympy.true if is_right else sympy.false
    disp = "直角三角形である" if is_right else "直角三角形ではない"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="compute_squares_and_compare",
            args=[], result_srepr="", result_display="最も長い辺と他の2辺の二乗の関係を調べる",
            narration="最も長い辺の長さの二乗と、他の2辺の長さの二乗の和を比べる。",
        ),
        Step(
            op="judge_by_pythagorean_converse",
            args=[], result_srepr=srepr, result_display=disp,
            narration="三平方の定理の逆から、直角三角形であるかどうかを判別する。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_right_triangle_from_three_sides")
def judge_right_triangle_from_three_sides(side_a: object, side_b: object, side_c: object) -> Solution:
    """3辺の長さから、三平方の定理の逆で直角三角形であるかを判別する

    （g3_l52.knowledge Lv2）。`math.verify_right_triangle_from_sides` と同じ
    判定を ChoiceAnswer で答える。
    """
    a, b, c = int(str(side_a)), int(str(side_b)), int(str(side_c))
    is_right = _is_right_triangle_sorted((a, b, c))
    correct = "直角三角形である" if is_right else "直角三角形ではない"
    other = "直角三角形ではない" if is_right else "直角三角形である"
    steps = [
        Step(
            op="compute_squares_and_compare",
            args=[], result_srepr="", result_display="最も長い辺と他の2辺の二乗の関係を調べる",
            narration="最も長い辺の長さの二乗と、他の2辺の長さの二乗の和を比べる。",
        ),
        Step(
            op="judge_by_pythagorean_converse",
            args=[], result_srepr=correct, result_display=correct,
            narration="三平方の定理の逆から、直角三角形であるかどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="pythagorean.judge_right_triangle")
    return Solution(answer=answer, steps=steps)
