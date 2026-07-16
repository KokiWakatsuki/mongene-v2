"""円周角の定理・その逆・弧の比例まわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l47/l48/l50 を扱う:
  - `math.inscribed_angle_from_central`: g3_l47.find_value Lv1（中心角から
    円周角=中心角の半分を求める）
  - `math.inscribed_angle_transfer_same_arc`: g3_l48.find_value Lv2（同じ弧に
    対する円周角は等しいことから角を転写する）
  - `math.judge_concyclic_from_angle`: g3_l48.knowledge Lv2（2つの角が等しいか
    どうかから4点が同一円周上にあるかを判別）
  - `math.arc_proportional_angle`: g3_l50.find_value Lv2（弧の長さが円周角に
    比例する関係から角を求める）

（g3_l49.find_value Lv2 は既存 solver `math.similarity_ratio_transfer` を
そのまま再利用する・新規solverなし）

円周角の定理・その逆・弧の比例の内容の想起は既存の `math.recall_rule` ハブに
topic を追加して対応する。

narration には数字を書かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


@register_solver("math.inscribed_angle_from_central")
def inscribed_angle_from_central(central_angle: object) -> Solution:
    """中心角から、同じ弧に対する円周角の大きさを求める（g3_l47.find_value Lv1）。

    central_angle（中心角の大きさ）だけから、円周角は中心角の半分に等しいという
    恒真の性質で計算する（double-solve）。
    """
    v = sympy.sympify(str(central_angle))
    result = v / 2
    disp = f"{sympy.sstr(result)}°"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_central_angle",
            args=[], result_srepr="", result_display="中心角の大きさを読み取る",
            narration="弧に対する中心角の大きさを読み取る。",
        ),
        Step(
            op="apply_inscribed_angle_theorem",
            args=[], result_srepr=srepr, result_display=disp,
            narration="同じ弧に対する円周角の大きさは、中心角の大きさの半分に等しいことから、"
            "円周角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.inscribed_angle_transfer_same_arc")
def inscribed_angle_transfer_same_arc(known_angle: object) -> Solution:
    """同じ弧に対する円周角は等しいことから、角の大きさを転写する

    （g3_l48.find_value Lv2）。known_angle だけから、同じ弧に対する円周角は
    すべて等しいという恒真の性質で計算する（double-solve）。
    """
    v = sympy.sympify(str(known_angle))
    disp = f"{sympy.sstr(v)}°"
    srepr = sympy.srepr(v)
    steps = [
        Step(
            op="identify_same_arc_angle",
            args=[], result_srepr="", result_display="同じ弧に対する角の大きさを読み取る",
            narration="4点が同一円周上にあることから、同じ弧に対応する角の大きさを読み取る。",
        ),
        Step(
            op="transfer_by_inscribed_angle_equality",
            args=[], result_srepr=srepr, result_display=disp,
            narration="同じ弧に対する円周角の大きさはすべて等しいことから、求める角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_concyclic_from_angle")
def judge_concyclic_from_angle(angle_c: object, angle_d: object) -> Solution:
    """直線ABの同じ側にある2点C,Dの角が等しいかどうかから、4点が同一円周上に

    あるかを判別する（g3_l48.knowledge Lv2）。angle_c/angle_d だけから、
    円周角の定理の逆（∠ACB=∠ADBならば同一円周上）という恒真の判定で計算する
    （double-solve）。答えは ChoiceAnswer。
    """
    c = sympy.sympify(str(angle_c))
    d = sympy.sympify(str(angle_d))
    is_concyclic = bool(c == d)
    correct = "同一円周上にあるといえる" if is_concyclic else "同一円周上にあるとはいえない"
    other = "同一円周上にあるとはいえない" if is_concyclic else "同一円周上にあるといえる"
    steps = [
        Step(
            op="compare_angles_on_same_side",
            args=[], result_srepr=("equal" if is_concyclic else "not_equal"),
            result_display="2つの角が等しいかどうかを確認する",
            narration="直線ABの同じ側にある2点C, Dでできる角が、等しいかどうかを確認する。",
        ),
        Step(
            op="judge_by_inscribed_angle_converse",
            args=[], result_srepr=correct, result_display=correct,
            narration="円周角の定理の逆から、4点が同一円周上にあるといえるかどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="circle.judge_concyclic")
    return Solution(answer=answer, steps=steps)


@register_solver("math.arc_proportional_angle")
def arc_proportional_angle(multiplier: object, known_angle: object) -> Solution:
    """弧の長さの倍率から、対応する円周角の大きさを求める（g3_l50.find_value Lv2）。

    multiplier/known_angle だけから、弧の長さは円周角の大きさに比例するという
    恒真の性質で計算する（double-solve）。
    """
    k = sympy.sympify(str(multiplier))
    v = sympy.sympify(str(known_angle))
    result = k * v
    disp = f"{sympy.sstr(result)}°"
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_arc_length_ratio",
            args=[], result_srepr="", result_display="弧の長さの比を読み取る",
            narration="2つの弧の長さの比を読み取る。",
        ),
        Step(
            op="apply_arc_angle_proportion",
            args=[], result_srepr=srepr, result_display=disp,
            narration="弧の長さは、その弧に対する円周角の大きさに比例することから、"
            "求める円周角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
