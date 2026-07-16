"""相似な図形まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C10（g3 図形・相似・円・三平方）クラスタの g3_l39 を扱う:
  - `math.similarity_ratio_transfer`: g3_l39.find_value Lv2（相似比を用い対応辺
    の長さを求める）
  - `math.identify_similar_corresponding_vertex`: g3_l39.knowledge Lv2（対応する
    頂点を判別）

相似・相似比の用語想起は既存の `math.term_recall` ハブに domain を追加して対応
する。

narration には数字を書かない。ChoiceAnswer の correct/distractor は digit-free
（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


@register_solver("math.similarity_ratio_transfer")
def similarity_ratio_transfer(ratio_num: object, ratio_den: object, known_side: object) -> Solution:
    """相似比 ratio_num:ratio_den を用い、既知の辺の長さから対応する辺の長さを求める

    （g3_l39.find_value Lv2）。ratio_num/ratio_den/known_side だけから、相似な
    図形では対応する辺の長さの比が相似比に等しいという恒真の性質で計算する
    （double-solve）。答えは対応する辺の長さの SymbolicAnswer。
    """
    m = sympy.sympify(str(ratio_num))
    n = sympy.sympify(str(ratio_den))
    v = sympy.sympify(str(known_side))
    result = v * n / m
    disp = sympy.sstr(result)
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op="identify_similarity_ratio",
            args=[], result_srepr="", result_display="相似比とわかっている辺の長さを読み取る",
            narration="2つの図形の相似比と、わかっている辺の長さを読み取る。",
        ),
        Step(
            op="apply_similarity_ratio",
            args=[], result_srepr=srepr, result_display=disp,
            narration="相似な図形では対応する辺の長さの比が相似比に等しいことから、"
            "対応する辺の長さを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.identify_similar_corresponding_vertex")
def identify_similar_corresponding_vertex(labels1: object, labels2: object, index: object) -> Solution:
    """相似な図形で、指定した頂点に対応する頂点を答える（g3_l39.knowledge Lv2）。

    labels1/labels2（対応順に並んだ頂点の文字列）と index（位置）だけから、対応
    関係の定義（同じ位置の頂点どうしが対応する）に従って機械的に決まる
    （double-solve）。答えは ChoiceAnswer。
    """
    lb2 = str(labels2)
    i = int(str(index))
    correct = lb2[i]
    distractors = [lb2[x] for x in range(len(lb2)) if x != i]
    steps = [
        Step(
            op="identify_correspondence_order",
            args=[], result_srepr="", result_display="頂点の対応する並びを確認する",
            narration="相似を表す式で、頂点がどの順に対応づけられているかを確認する。",
        ),
        Step(
            op="name_corresponding_vertex",
            args=[], result_srepr=correct, result_display=correct,
            narration="対応する位置にある頂点どうしが対応することから、対応する頂点を答える。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="similarity.identify_corresponding_vertex"
    )
    return Solution(answer=answer, steps=steps)
