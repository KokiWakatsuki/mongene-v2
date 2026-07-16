"""三角形の相似条件まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l40 を扱う:
  - `math.similar_triangle_x_shape`: g3_l40.find_value Lv2（AB//CD の交わる2線分
    がつくる相似な三角形から対応辺の長さを求める）
  - `math.identify_similarity_condition`: g3_l40.knowledge Lv2（示されている条件
    からどの相似条件によるかを判別）

3つの相似条件の想起は既存の `math.recall_rule` ハブに topic を追加して対応する。

narration には数字を書かない。ChoiceAnswer の correct/distractor は digit-free
（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_SIMILARITY_CONDITION_NAMES: dict[str, str] = {
    "aa": "二組の角がそれぞれ等しい条件",
    "sas_ratio": "二組の辺の比とその間の角がそれぞれ等しい条件",
    "sss_ratio": "三組の辺の比がすべて等しい条件",
}


@register_solver("math.similar_triangle_x_shape")
def similar_triangle_x_shape(oa: object, ob: object, oc: object) -> Solution:
    """AB//CD の2線分が点Oで交わってできる相似な三角形OAB・OCDから、

    対応する辺OD の長さを求める（g3_l40.find_value Lv2）。oa/ob/oc（既知の
    3辺の長さ）だけから、平行線がつくる相似（対頂角＋錯角の等しさ）で
    OA:OC=OB:OD が成り立つという恒真の性質で計算する（double-solve）。
    """
    a = sympy.sympify(str(oa))
    b = sympy.sympify(str(ob))
    c = sympy.sympify(str(oc))
    result = b * c / a
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_similar_triangles_in_x_shape",
            args=[], result_srepr="", result_display="平行線がつくる相似な三角形を見つける",
            narration="AB//CD であることから、対頂角と錯角がそれぞれ等しくなる"
            "相似な三角形の組を見つける。",
        ),
        Step(
            op="apply_proportion",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な三角形の対応する辺の長さの比が等しいことから、"
            "求める辺の長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.identify_similarity_condition")
def identify_similarity_condition(condition_key: object) -> Solution:
    """示されている条件が、三角形の相似条件のうちどれによるかを判別する

    （g3_l40.knowledge Lv2）。condition_key だけから判定する（具体的な場面文は
    recipe が構成する surface であり double-solve）。答えは ChoiceAnswer。
    """
    key = str(condition_key)
    if key not in _SIMILARITY_CONDITION_NAMES:
        raise ValueError(f"未知の condition_key: {key!r}")
    correct = _SIMILARITY_CONDITION_NAMES[key]
    distractors = [v for k, v in _SIMILARITY_CONDITION_NAMES.items() if k != key]
    steps = [
        Step(
            op="identify_given_elements",
            args=[], result_srepr="", result_display="示されている等しい要素を読み取る",
            narration="2つの三角形で示されている、等しい角や辺の比が何かを読み取る。",
        ),
        Step(
            op="match_similarity_condition",
            args=[], result_srepr=correct, result_display=correct,
            narration="三角形の相似条件のうち、示されている要素がどれに当てはまるかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="similarity.identify_condition"
    )
    return Solution(answer=answer, steps=steps)
