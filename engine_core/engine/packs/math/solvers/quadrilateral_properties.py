"""平行四辺形・特別な平行四辺形・等積変形まわりの独立再計算ソルバ群

（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C9（g2 図形・平行と合同・三角形と四角形）クラスタの g2_l46/l47/l49/l50 を扱う:
  - `math.parallelogram_opposite_properties`: g2_l46.find_value Lv1（対辺の長さ・
    対角の大きさを求める・Tuple答え）
  - `math.identify_parallelogram_condition`: g2_l47.knowledge Lv2（条件からどの
    平行四辺形の条件によるかを判別・ChoiceAnswer）
  - `math.special_parallelogram_diagonal_value`: g2_l49.find_value Lv1（対角線の
    性質から辺・角を求める）
  - `math.classify_quadrilateral_from_diagonal_condition`: g2_l49.knowledge Lv2
    （対角線の条件からどの四角形になるかを判別・ChoiceAnswer）
  - `math.equal_area_transform_value`: g2_l50.find_value Lv2（等積変形で面積を
    求める）

平行四辺形の性質の想起（対辺対角相等・5条件・特別な平行四辺形の対角線・等積変形の
根拠）は既存の `math.recall_rule` ハブに topic を追加して対応する。

narration には数字を書かない。ChoiceAnswer の correct/distractor は digit-free
（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_measure

_PARALLELOGRAM_CONDITION_NAMES: dict[str, str] = {
    "opposite_sides_parallel": "二組の対辺がそれぞれ平行である条件",
    "opposite_sides_equal": "二組の対辺の長さがそれぞれ等しい条件",
    "opposite_angles_equal": "二組の対角の大きさがそれぞれ等しい条件",
    "diagonals_bisect": "対角線がそれぞれの中点で交わる条件",
    "one_pair_parallel_and_equal": "一組の対辺が平行でその長さが等しい条件",
}


@register_solver("math.parallelogram_opposite_properties")
def parallelogram_opposite_properties(side_value: object, angle_value: object) -> Solution:
    """平行四辺形の対辺の長さ・対角の大きさを求める（g2_l46.find_value Lv1）。

    side_value/angle_value（わかっている辺の長さ・角の大きさ）だけから、平行四辺形
    では対辺の長さ・対角の大きさがそれぞれ等しいという恒真の性質で計算する
    （double-solve）。答えは Tuple(辺の長さ, 角の大きさ) の SymbolicAnswer。
    """
    sv = sympy.sympify(str(side_value))
    av = sympy.sympify(str(angle_value))
    disp = f"辺の長さ {sympy.sstr(sv)}cm、角の大きさ {sympy.sstr(av)}°"
    srepr = sympy.srepr(sympy.Tuple(sv, av))
    steps = [
        Step(
            op="identify_given_side_and_angle",
            args=[], result_srepr="", result_display=f"{sympy.sstr(sv)} と {sympy.sstr(av)}°",
            narration="平行四辺形のうち、わかっている辺の長さと角の大きさを読み取る。",
        ),
        Step(
            op="apply_opposite_side_and_angle_property",
            args=[], result_srepr=srepr, result_display=disp,
            narration="平行四辺形では対辺の長さ・対角の大きさがそれぞれ等しいことから、"
            "求める辺の長さと角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.identify_parallelogram_condition")
def identify_parallelogram_condition(condition_key: object) -> Solution:
    """示されている条件が、平行四辺形になるための5条件のうちどれによるかを判別する

    （g2_l47.knowledge Lv2）。condition_key だけから判定する（具体的な場面文は
    recipe が構成する surface であり double-solve）。答えは ChoiceAnswer。
    """
    key = str(condition_key)
    if key not in _PARALLELOGRAM_CONDITION_NAMES:
        raise ValueError(f"未知の condition_key: {key!r}")
    correct = _PARALLELOGRAM_CONDITION_NAMES[key]
    distractors = [v for k, v in _PARALLELOGRAM_CONDITION_NAMES.items() if k != key]
    steps = [
        Step(
            op="identify_given_elements",
            args=[], result_srepr="", result_display="",
            narration="四角形で示されている、等しい・平行である要素が何かを読み取る。",
        ),
        Step(
            op="match_parallelogram_condition",
            args=[], result_srepr=correct, result_display=correct,
            narration="平行四辺形になるための5条件のうち、示されている要素がどれに当てはまるかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="parallelogram.identify_condition"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.special_parallelogram_diagonal_value")
def special_parallelogram_diagonal_value(shape: object, value: object) -> Solution:
    """特別な平行四辺形の対角線の性質から、辺の長さ・角の大きさを求める

    （g2_l49.find_value Lv1）。shape("rectangle"/"square"の場合は対角線の長さが
    等しく中点で交わることから半分の長さを、"rhombus"の場合は対角線が垂直に交わる
    ことから直角を、それぞれ恒真の性質で計算する（double-solve）。
    """
    sh = str(shape)
    v = sympy.sympify(str(value))
    if sh == "rhombus":
        # **与えられた対角線の長さを使う問いにする。** 前は答えが 90° だけで、
        # 本文の「AC=24cm」がどこにも使われない飾りになっていた（実物の問題は
        # 与件を必ず使う）。ひし形も対角線がそれぞれの中点で交わるので、
        # 半分の長さと直角の両方を問える。
        half = sympy.Rational(v, 2)
        result = sympy.Tuple(half, sympy.Integer(90))
        disp = f"線分の長さ {fmt_measure(half)}cm、角の大きさ 90°"
        narration = (
            "ひし形の対角線はそれぞれの中点で交わり、しかも垂直に交わることから、"
            "交点から頂点までの長さと、交点にできる角の大きさを求める。"
        )
    else:
        result = sympy.Rational(v, 2)
        disp = f"{fmt_measure(result)}cm"
        narration = "対角線の長さが等しく、それぞれの中点で交わることから、交点から頂点までの長さを求める。"
    srepr = sympy.srepr(result)
    # op 名は shape によらず一定にする（G-FP: 同一 signature の fp はセルによらず一定でなければ
    # ならない。shape 分岐は narration/result だけに留め、op 名自体を分岐させない）。
    steps = [
        Step(
            op="identify_given_diagonal_value",
            args=[], result_srepr="", result_display=f"{sympy.sstr(v)}",
            narration="対角線についてわかっている長さや、四角形の種類を読み取る。",
        ),
        Step(
            op="apply_diagonal_property", args=[], result_srepr=srepr, result_display=disp,
            narration=narration,
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.classify_quadrilateral_from_diagonal_condition")
def classify_quadrilateral_from_diagonal_condition(equal: object, perpendicular: object) -> Solution:
    """対角線の条件（等しい／垂直に交わる）から、平行四辺形がどんな四角形になるかを判別する

    （g2_l49.knowledge Lv2）。equal/perpendicular（bool相当）だけから判定する
    （具体的な場面文は recipe が構成する surface であり double-solve）。答えは
    ChoiceAnswer（4択：正方形／長方形／ひし形／平行四辺形のまま）。
    """
    eq = str(equal).lower() in ("true", "1")
    pe = str(perpendicular).lower() in ("true", "1")
    names = {
        (True, True): "正方形",
        (True, False): "長方形",
        (False, True): "ひし形",
        (False, False): "平行四辺形のまま（特別な四角形にはならない）",
    }
    correct = names[(eq, pe)]
    distractors = [v for k, v in names.items() if k != (eq, pe)]
    steps = [
        Step(
            op="check_diagonal_conditions",
            args=[], result_srepr=("yes" if eq else "no") + ("yes" if pe else "no"),
            result_display=(
                ("長さは等しい" if eq else "長さは等しくない")
                + "／"
                + ("垂直に交わる" if pe else "垂直には交わらない")
            ),
            narration="対角線が等しいか、垂直に交わるか、それぞれの条件を確認する。",
        ),
        Step(
            op="classify_quadrilateral",
            args=[], result_srepr=correct, result_display=correct,
            narration="対角線の条件の組み合わせから、平行四辺形がどんな四角形になるかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="quadrilateral.classify_from_diagonal"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.equal_area_transform_value")
def equal_area_transform_value(area_value: object) -> Solution:
    """等積変形でつくった三角形の面積を求める（g2_l50.find_value Lv2）。

    area_value（もとの図形の面積）だけから、等積変形は面積を変えない、という恒真の
    性質で計算する（double-solve）。答えは面積の SymbolicAnswer。
    """
    v = sympy.sympify(str(area_value))
    disp = fmt_measure(v)
    srepr = sympy.srepr(v)
    steps = [
        Step(
            op="identify_original_area",
            args=[], result_srepr="", result_display="",
            # **1手目に面積の値を出さない。** 等積変形では答えがもとの面積と同じ値に
            # なるので、値を出すと**解説の1行目がもう答え**になる（走査が指摘）。
            # ここで確かめるのは「どの図形の面積がわかっているか」であって値ではない。
            narration="等積変形をする前の、面積がわかっている図形はどれかを確かめる。",
        ),
        Step(
            op="apply_equal_area_transform",
            args=[], result_srepr=srepr, result_display=disp,
            # **「等積変形だから等積」はトートロジーで、教えることが1つも無い。**
            # 実際に効いているのは「平行だから底辺が共通で高さが等しい」で、
            # そこがこの単元の中身。理由を述べる形に直す。
            narration="対角線をひいて分けると、平行な直線にはさまれた三角形は"
            "底辺が共通で高さも等しいので、面積が変わらない。",
            detail="もとの四角形を対角線で2つの三角形に分けると、一方は"
            "平行な直線にはさまれた三角形になる。その三角形を平行線にそって移しても"
            "底辺と高さが変わらないので面積は同じ。だから全体の面積も変わらない。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
