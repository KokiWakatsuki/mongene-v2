"""三角形の合同条件・二等辺三角形・正三角形まわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C9（g2 図形・平行と合同・三角形と四角形）クラスタのうち g2_l37/l38/l41/l42/l43 の
非 visual セル群を扱う:
  - `math.isosceles_base_angle`: g2_l41.find_value Lv1（頂角から底角を求める）
  - `math.equilateral_triangle_properties`: g2_l43.find_value Lv1（1辺の長さから
    もう1辺と1つの内角を求める・Tuple答え）
  - `math.judge_isosceles_from_angle_condition`: g2_l42.knowledge Lv2（2角が
    等しいという条件から二等辺三角形といえるかを判別する）
  - `math.judge_equilateral_from_condition`: g2_l43.knowledge Lv2（辺と角の条件
    から正三角形といえるかを判別する）

用語・規則の想起（合同条件・仮定結論反例・二等辺/正三角形の性質）は既存の
`math.term_recall`/`math.recall_rule` ハブに domain/topic を追加して対応する。

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。ChoiceAnswer の
correct/distractor は漢数字のみ＝digit-free（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_measure


@register_solver("math.isosceles_base_angle")
def isosceles_base_angle(known_type: object, known_value: object) -> Solution:
    """二等辺三角形の頂角/底角の一方から、もう一方を求める（g2_l41.find_value Lv1）。

    known_type("apex"/"base")と既知の角の値だけから計算する（double-solve）。
    apex→base=(180-apex)/2、base→apex=180-2*base のどちらも同じ「内角の和180°・
    底角が等しい」性質の裏表であり、恒真。答えは単一値の SymbolicAnswer。
    """
    kt = str(known_type)
    known = sympy.sympify(str(known_value))
    if kt == "apex":
        result = (180 - known) / 2
        narration_id = (
            "三角形の内角の和から頂角をひいた残りを、等しい2つの底角で"
            "半分ずつに分けて底角の大きさを求める。"
        )
    else:
        result = 180 - 2 * known
        narration_id = (
            "等しい2つの底角の大きさを2つ分合わせてひくと、残りが頂角の大きさになる"
            "ことから頂角を求める。"
        )
    disp = fmt_measure(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_known_angle",
            args=[], result_srepr="", result_display=f"{fmt_measure(known)}°",
            narration="二等辺三角形の頂角・底角のうち、わかっているほうの大きさを読み取る。",
        ),
        Step(
            op="solve_remaining_angle",
            args=[], result_srepr=srepr, result_display=disp,
            narration=narration_id,
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.equilateral_triangle_properties")
def equilateral_triangle_properties(side: object, angle_label: object = "") -> Solution:
    """正三角形の1辺の長さから、もう1辺の長さと1つの内角の大きさを求める

    （g2_l43.find_value Lv1）。1辺の長さだけから計算する（double-solve、正三角形は
    3辺が等しく3内角も等しい）。答えは Tuple(辺の長さ, 内角) の SymbolicAnswer。

    `angle_label` は答えに書く頂点の名前（「∠G」）。頂点名を recipe 側で引くように
    したので、ここに "A" を焼き込んだままだと本文（正三角形GHJ）と答え（∠A）の
    記号が食い違う（`engine.eval.text_quality` が拾う）。
    """
    m = sympy.sympify(str(side))
    angle = sympy.Rational(180, 3)
    label = str(angle_label) or "A"
    disp = f"辺の長さ {sympy.sstr(m)}cm、∠{label} {sympy.sstr(angle)}°"
    srepr = sympy.srepr(sympy.Tuple(m, angle))
    steps = [
        Step(
            op="identify_given_side",
            args=[], result_srepr="", result_display=f"{sympy.sstr(m)}",
            narration="正三角形の与えられた1辺の長さを読み取る。",
        ),
        Step(
            op="apply_equilateral_property",
            args=[], result_srepr=srepr, result_display=disp,
            narration="正三角形は3辺の長さがすべて等しく、3つの内角もすべて等しく"
            "分け合うことから、もう1辺の長さと1つの内角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.judge_isosceles_from_angle_condition")
def judge_isosceles_from_angle_condition(is_equal: object) -> Solution:
    """2つの角が等しいという条件から二等辺三角形といえるかを判別する

    （g2_l42.knowledge Lv2）。is_equal(bool相当)だけから判定する（具体的な場面文は
    recipe が構成する surface であり double-solve）。答えは ChoiceAnswer。
    """
    truthy = str(is_equal).lower() in ("true", "1")
    correct = "二等辺三角形であるといえる" if truthy else "二等辺三角形であるとはいえない"
    other = "二等辺三角形であるとはいえない" if truthy else "二等辺三角形であるといえる"
    steps = [
        Step(
            op="check_two_angles_equal",
            args=[], result_srepr=("equal" if truthy else "not_equal"),
            result_display=("等しい" if truthy else "等しくない"),
            narration="示されている2つの角が、等しいといえる条件を満たしているかを確認する。",
        ),
        Step(
            op="judge_isosceles",
            args=[], result_srepr=correct, result_display=correct,
            narration="2つの角が等しければ、その対辺どうしも等しく二等辺三角形になるという性質から判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="isosceles.judge_from_angle")
    return Solution(answer=answer, steps=steps)


@register_solver("math.judge_equilateral_from_condition")
def judge_equilateral_from_condition(is_equilateral: object) -> Solution:
    """辺と角の条件から正三角形といえるかを判別する（g2_l43.knowledge Lv2）。

    is_equilateral(bool相当)だけから判定する（具体的な場面文は recipe が構成する
    surface であり double-solve）。答えは ChoiceAnswer。
    """
    truthy = str(is_equilateral).lower() in ("true", "1")
    correct = "正三角形であるといえる" if truthy else "正三角形であるとはいえない"
    other = "正三角形であるとはいえない" if truthy else "正三角形であるといえる"
    steps = [
        Step(
            op="check_side_and_angle_condition",
            args=[], result_srepr=("yes" if truthy else "no"),
            result_display=("条件を満たす" if truthy else "条件を満たさない"),
            # **答えの文字列を narration に書かない**（narration はそのままヒントに
            # なるので、「正三角形であるといえる」と書くと答えの先出しになる）。
            narration="示されている辺と角の条件が、その形になるための条件を満たしているかを確認する。",
        ),
        Step(
            op="judge_equilateral",
            args=[], result_srepr=correct, result_display=correct,
            narration="二等辺三角形の性質を重ね合わせて、正三角形であるといえるかどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="equilateral.judge_from_condition")
    return Solution(answer=answer, steps=steps)


_RIGHT_TRIANGLE_VALID_CONDITIONS = frozenset(
    {"hypotenuse_and_acute_angle", "hypotenuse_and_other_side"}
)


@register_solver("math.judge_right_triangle_congruence")
def judge_right_triangle_congruence(condition_type: object) -> Solution:
    """図から読み取れる条件から、直角三角形の合同条件を満たすかを判別する

    （g2_l44.knowledge Lv2）。condition_type だけから判定する（具体的な場面文は
    recipe が構成する surface であり double-solve）。答えは ChoiceAnswer。
    """
    ct = str(condition_type)
    truthy = ct in _RIGHT_TRIANGLE_VALID_CONDITIONS
    # 問いが「根拠とともに答えよ」なので、どの合同条件によるか（満たさないなら
    # 何が足りないか）まで答えに入れる。
    yes = "合同であるといえる（直角三角形の合同条件を満たすから）"
    no = "合同であるとはいえない（斜辺が等しいことが分かっていないから）"
    correct = yes if truthy else no
    other = no if truthy else yes
    steps = [
        Step(
            op="check_right_triangle_condition",
            args=[], result_srepr=("yes" if truthy else "no"),
            result_display=("合同条件にあてはまる" if truthy else "合同条件にあてはまらない"),
            narration="図から読み取れる条件が、直角三角形の合同条件（斜辺と1つの鋭角、"
            "または斜辺と他の1辺）を満たしているかを確認する。",
        ),
        Step(
            op="judge_right_triangle_congruence",
            args=[], result_srepr=correct, result_display=correct,
            narration="直角がすでに等しいことと合わせて、直角三角形の合同条件を満たすかどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="right_triangle.judge_congruence"
    )
    return Solution(answer=answer, steps=steps)
