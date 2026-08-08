"""平行線・三角形・多角形の角まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（角度の数値・多角形の辺の数など）から答えと steps を
導く（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C9（g2 図形・平行と合同）クラスタのうち g2_l31〜l35（角度追跡）の非 visual セル群を
扱う:
  - `math.solve_angle_by_equality_relation`: g2_l31/l32.find_value Lv1（対頂角・同位角・
    錯角はすべて等しい、という関係を1つ直接使って角を求める）
  - `math.solve_zigzag_angle_sum`: g2_l31/l32.find_value Lv2（平行線間で折れ曲がった線の
    角を、頂点を通る補助線で2つの錯角に分けて求める＝ x = 角1 + 角2）
  - `math.triangle_third_angle`: g2_l33.find_value Lv1（内角の和180°で第3の角を求める）
  - `math.polygon_interior_sum_and_angle`: g2_l34.find_value Lv1（正n角形の内角の和と
    1つの内角）
  - `math.polygon_sides_from_interior_sum`: g2_l34.find_value Lv2（内角の和から辺の数を
    逆算する）
  - `math.regular_polygon_exterior_angle`: g2_l35.find_value Lv1（正n角形の1つの外角）
  - `math.polygon_sides_from_interior_angle`: g2_l35.find_value Lv2（1つの内角から
    外角の和360°を使って辺の数を逆算する）
  - `math.judge_parallel_from_angle_condition`: g2_l32.knowledge Lv2（同位角/錯角が等しい
    という条件から2直線が平行といえるかを判別する）

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_ANGLE_RELATION_NARRATION = {
    "vertical": "2直線が交わってできる対頂角の関係を確認する。",
    "corresponding": "平行な2直線と1本の直線がつくる同位角の関係を確認する。",
    "alternate": "平行な2直線と1本の直線がつくる錯角の関係を確認する。",
}


@register_solver("math.solve_angle_by_equality_relation")
def solve_angle_by_equality_relation(relation: object, angle: object) -> Solution:
    """対頂角/同位角/錯角の関係を1つ使い、等しい角を求める（g2_l31/l32.find_value Lv1）。

    角の値と関係の種類だけから計算する（double-solve、恒真の等しさ）。答えは単一値の
    SymbolicAnswer。
    """
    r = str(relation)
    a = sympy.sympify(str(angle))
    disp = sympy.sstr(a)
    srepr = sympy.srepr(a)
    steps = [
        Step(
            op="identify_angle_relation",
            args=[], result_srepr=r, result_display="角の位置関係を読み取る",
            narration=_ANGLE_RELATION_NARRATION.get(r, "角の位置関係を読み取る。"),
        ),
        Step(
            op="apply_angle_equality",
            args=[], result_srepr=srepr, result_display=disp,
            narration="その関係にある角は等しいという性質から、求める角の大きさを決める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.solve_zigzag_angle_sum")
def solve_zigzag_angle_sum(angle1: object, angle2: object) -> Solution:
    """平行線間で折れ曲がった角を、頂点を通る補助線で2つに分けて求める

    （g2_l31/l32.find_value Lv2）。x = 角1 + 角2（恒真、double-solve）。答えは単一値の
    SymbolicAnswer。
    """
    a1 = sympy.sympify(str(angle1))
    a2 = sympy.sympify(str(angle2))
    total = a1 + a2
    disp = sympy.sstr(total)
    srepr = sympy.srepr(total)
    steps = [
        Step(
            op="draw_auxiliary_line",
            args=[], result_srepr="", result_display="折れ曲がった点を通り2直線に平行な補助線をひく",
            narration="折れ曲がった点を通り、2直線に平行な補助線をひく。",
        ),
        Step(
            op="sum_alternate_angles",
            args=[], result_srepr=srepr, result_display=disp,
            narration="補助線で分けられた2つの角がそれぞれ錯角として等しいことから、求める角の大きさを合計して決める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.triangle_third_angle")
def triangle_third_angle(angle_a: object, angle_b: object) -> Solution:
    """三角形の内角の和180°から第3の角を求める（g2_l33.find_value Lv1）。

    残り2つの内角の値だけから計算する（double-solve）。答えは単一値の SymbolicAnswer。
    """
    a = sympy.sympify(str(angle_a))
    b = sympy.sympify(str(angle_b))
    c = 180 - a - b
    disp = sympy.sstr(c)
    srepr = sympy.srepr(c)
    steps = [
        Step(
            op="identify_two_interior_angles",
            args=[], result_srepr="", result_display="わかっている2つの内角を読み取る",
            narration="わかっている2つの内角の大きさを読み取る。",
        ),
        Step(
            op="subtract_from_sum",
            args=[], result_srepr=srepr, result_display=disp,
            narration="三角形の内角の和が一直線の角(平角)に等しいことから、残りの内角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.polygon_interior_sum_and_angle")
def polygon_interior_sum_and_angle(sides: object) -> Solution:
    """正n角形の内角の和と1つの内角の大きさを求める（g2_l34.find_value Lv1）。

    辺の数 n だけから計算する（double-solve）。答えは Tuple(内角の和, 1つの内角) の
    SymbolicAnswer。
    """
    n = sympy.Integer(int(str(sides)))
    total = 180 * (n - 2)
    one_angle = total / n
    disp = f"内角の和 {sympy.sstr(total)}°、1つの内角 {sympy.sstr(one_angle)}°"
    srepr = sympy.srepr(sympy.Tuple(total, one_angle))
    steps = [
        Step(
            op="apply_interior_sum_formula",
            args=[], result_srepr="", result_display="内角の和の公式にあてはめる",
            narration="一直線の角(平角)を、頂点の数より二少ない数だけ集めた大きさが内角の和になる、"
            "という公式に辺の数をあてはめる。",
        ),
        Step(
            op="divide_for_one_angle",
            args=[], result_srepr=srepr, result_display=disp,
            narration="正多角形はすべての内角が等しいことから、内角の和を辺の数でわって1つの内角を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.polygon_sides_from_interior_sum")
def polygon_sides_from_interior_sum(interior_sum: object) -> Solution:
    """多角形の内角の和から辺の数(何角形か)を逆算する（g2_l34.find_value Lv2）。

    内角の和の値だけから計算する（double-solve）。答えは単一値(辺の数)の SymbolicAnswer。
    """
    total = sympy.sympify(str(interior_sum))
    n = total / 180 + 2
    disp = sympy.sstr(n)
    srepr = sympy.srepr(n)
    steps = [
        Step(
            op="form_interior_sum_equation",
            args=[], result_srepr="", result_display="内角の和の公式に、わからない辺の数をあてはめ方程式をつくる",
            narration="内角の和の公式に、わからない辺の数をあてはめて方程式をつくる。",
        ),
        Step(
            op="solve_for_sides",
            args=[], result_srepr=srepr, result_display=disp,
            narration="方程式を辺の数について解き、何角形かを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.regular_polygon_exterior_angle")
def regular_polygon_exterior_angle(sides: object) -> Solution:
    """正n角形の1つの外角の大きさを求める（g2_l35.find_value Lv1）。

    辺の数 n だけから計算する（double-solve、外角の和は常に360°）。答えは単一値の
    SymbolicAnswer。
    """
    n = sympy.Integer(int(str(sides)))
    ext = sympy.Rational(360, n)
    disp = sympy.sstr(ext)
    srepr = sympy.srepr(ext)
    steps = [
        Step(
            op="recall_exterior_sum_constant",
            args=[], result_srepr="", result_display="多角形の外角の和がつねに一定であることを思い出す",
            narration="多角形の外角の和は、辺の数によらずつねに一定であることを思い出す。",
        ),
        Step(
            op="divide_by_sides",
            args=[], result_srepr=srepr, result_display=disp,
            narration="正多角形はすべての外角が等しいことから、外角の和を辺の数でわって1つの外角を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.polygon_sides_from_interior_angle")
def polygon_sides_from_interior_angle(interior_angle: object) -> Solution:
    """正多角形の1つの内角の大きさから辺の数(正何角形か)を求める（g2_l35.find_value Lv2）。

    1つの内角の値だけから計算する（double-solve、外角=180°-内角・辺の数=外角の和/外角）。
    答えは単一値(辺の数)の SymbolicAnswer。
    """
    interior = sympy.sympify(str(interior_angle))
    ext = 180 - interior
    n = 360 / ext
    disp = sympy.sstr(n)
    srepr = sympy.srepr(n)
    steps = [
        Step(
            op="compute_exterior_from_interior",
            args=[], result_srepr="", result_display="内角ととなり合う外角の大きさを求める",
            narration="内角ととなり合う外角は、一直線の角(平角)から内角をひいて求める。",
        ),
        Step(
            op="divide_exterior_sum",
            args=[], result_srepr=srepr, result_display=disp,
            narration="外角の和がつねに一定であることから、その値を1つの外角でわって辺の数を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_parallel_from_angle_condition")
def judge_parallel_from_angle_condition(is_equal: object) -> Solution:
    """同位角/錯角が等しいという条件から2直線が平行といえるかを判別する

    （g2_l32.knowledge Lv2）。is_equal(bool相当)だけから判定する（具体的な場面文は
    recipe が構成する surface であり double-solve）。答えは ChoiceAnswer。
    """
    truthy = str(is_equal).lower() in ("true", "1")
    correct = "平行であるといえる" if truthy else "平行であるとはいえない"
    other = "平行であるとはいえない" if truthy else "平行であるといえる"
    steps = [
        Step(
            op="check_angle_equality",
            args=[], result_srepr=("equal" if truthy else "not_equal"),
            result_display="同位角や錯角が等しいかどうかを確認する",
            narration="示されている同位角や錯角が、等しいといえる条件を満たしているかを確認する。",
        ),
        Step(
            op="judge_parallel",
            args=[], result_srepr=correct, result_display=correct,
            narration="その条件を満たしていれば2直線は平行であるという性質から判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="parallel_lines.judge_from_angle")
    return Solution(answer=answer, steps=steps)


_ARROWHEAD_OPS = [
    "draw_auxiliary_line",
    "apply_exterior_angle_first",
    "apply_exterior_angle_second",
    "sum_two_exterior_angles",
]

_ARROWHEAD_NARRATION: dict[str, str] = {
    "draw_auxiliary_line": "頂点Aと内部の点Dを結んだ直線を、Dの向こう側までのばす補助線を引く。"
                           "この1本で、もとの図が2つの三角形に分かれる。",
    "apply_exterior_angle_first": "一方の三角形について、外角は隣り合わない2つの内角の和に"
                                  "等しいことを使い、のばした線とDBがつくる角を求める。",
    "apply_exterior_angle_second": "もう一方の三角形についても同じように、"
                                   "のばした線とDCがつくる角を求める。",
    "sum_two_exterior_angles": "求める角は、いま求めた2つの角を合わせたものだから、"
                               "それらをたして求める。",
}

_ARROWHEAD_PHRASE: dict[str, str] = {
    "draw_auxiliary_line": "補助線を引いて2つの三角形に分ける",
    "apply_exterior_angle_first": "一方の三角形の外角を求める",
    "apply_exterior_angle_second": "もう一方の三角形の外角を求める",
}


@register_solver("math.arrowhead_angle")
def arrowhead_angle(angle_a: object, angle_b: object, angle_c: object) -> Solution:
    """三角形の内部の点がつくる角を、外角の性質を2回使って求める（g2_l33.find_value Lv2）。

    三角形ABCの内部に点Dがあり、BとD、CとDを結んだとき、
        ∠BDC = ∠BAC + ∠ABD + ∠ACD
    （AD をのばす補助線を引くと、2つの三角形の外角の和になる）。いわゆるブーメラン型で、
    「補助線を引いて複数の三角形にまたがる」多段の角の追跡そのもの。
    3つの角の値だけから計算する（double-solve）。
    """
    a = sympy.sympify(str(angle_a))
    b = sympy.sympify(str(angle_b))
    c = sympy.sympify(str(angle_c))
    for value in (a, b, c):
        if value <= 0:
            raise ValueError("角の大きさは正であること")
    total = a + b + c
    if total >= 180:
        raise ValueError("内部の点がつくる角が平角以上になり、図が成立しない")
    srepr = sympy.srepr(total)
    disp = sympy.sstr(total)
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_ARROWHEAD_OPS) - 1 else "",
            result_display=disp if i == len(_ARROWHEAD_OPS) - 1 else _ARROWHEAD_PHRASE[op],
            narration=_ARROWHEAD_NARRATION[op],
        )
        for i, op in enumerate(_ARROWHEAD_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
