"""合同な図形の対応関係まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C9（g2 図形・平行と合同・三角形と四角形）クラスタの g2_l36 を扱う:
  - `math.congruence_transfer_values`: g2_l36.find_value Lv1（対応する辺の長さ・
    角の大きさを求める・Tuple答え）
  - `math.congruence_symbol_and_side`: g2_l36.knowledge Lv1（合同記号＋対応する辺
    の判別・ChoiceAnswer）
  - `math.congruence_corresponding_pair`: g2_l36.knowledge Lv2（対応する角・辺を
    それぞれ判別・ChoiceAnswer）

narration には数字を書かない。ChoiceAnswer の correct/distractor は digit-free
（鉄則①）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_SIDE_PAIRS: list[tuple[int, int]] = [(0, 1), (1, 2), (2, 0)]


def _side_name(labels: str, i: int, j: int) -> str:
    return f"辺{labels[i]}{labels[j]}"


def _angle_name(labels: str, i: int) -> str:
    return f"∠{labels[i]}"


def _other_side_pair(i: int, j: int) -> tuple[int, int]:
    for a, b in _SIDE_PAIRS:
        if {a, b} != {i, j}:
            return a, b
    raise AssertionError("unreachable")  # pragma: no cover


@register_solver("math.congruence_transfer_values")
def congruence_transfer_values(side_value: object, angle_value: object) -> Solution:
    """合同な図形の対応する辺の長さ・角の大きさを求める（g2_l36.find_value Lv1）。

    side_value/angle_value（わかっている辺の長さ・角の大きさ）だけから、合同な図形
    では対応する辺・角も同じ大きさになる、という恒真の性質で計算する（double-solve）。
    答えは Tuple(辺の長さ, 角の大きさ) の SymbolicAnswer。
    """
    sv = sympy.sympify(str(side_value))
    av = sympy.sympify(str(angle_value))
    disp = f"辺の長さ {sympy.sstr(sv)}、角の大きさ {sympy.sstr(av)}°"
    srepr = sympy.srepr(sympy.Tuple(sv, av))
    steps = [
        Step(
            op="identify_given_correspondence",
            args=[], result_srepr="", result_display=f"{sympy.sstr(sv)} と {sympy.sstr(av)}°",
            narration="合同である2つの図形のうち、わかっている辺の長さと角の大きさが、"
            "それぞれどの辺・角に対応するかを読み取る。",
        ),
        Step(
            op="transfer_by_congruence",
            args=[], result_srepr=srepr, result_display=disp,
            narration="合同な図形では対応する辺の長さ・角の大きさがそれぞれ等しいことから、"
            "求める辺の長さと角の大きさを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.congruence_symbol_and_side")
def congruence_symbol_and_side(p_labels: object, q_labels: object, i: object, j: object) -> Solution:
    """合同記号と、指定した辺に対応する辺を答える（g2_l36.knowledge Lv1）。

    p_labels/q_labels（対応順に並んだ3頂点の文字列）と位置インデックス i, j だけから、
    対応関係の定義（同じ位置の頂点どうしが対応する）に従って機械的に決まる
    （double-solve）。答えは ChoiceAnswer（合同記号＋対応する辺を1文にまとめた答え）。
    """
    p = str(p_labels)
    q = str(q_labels)
    ii, jj = int(str(i)), int(str(j))
    given_side = _side_name(p, ii, jj)
    correct_side = _side_name(q, ii, jj)
    wrong_side = _side_name(q, *_other_side_pair(ii, jj))
    correct = f"合同を表す記号は≡であり、{given_side}に対応する辺は{correct_side}である"
    wrong_symbol = f"合同を表す記号は∽であり、{given_side}に対応する辺は{correct_side}である"
    wrong_correspondence = f"合同を表す記号は≡であり、{given_side}に対応する辺は{wrong_side}である"
    steps = [
        Step(
            op="recall_congruence_symbol",
            args=[], result_srepr="", result_display="合同を表す記号を思い出す",
            narration="2つの図形が合同であることを表すのに使う記号を思い出す。",
        ),
        Step(
            op="identify_side_correspondence",
            args=[], result_srepr="", result_display=f"{p_labels} と {q_labels}",
            narration="合同を表す式で、頂点がどの順に対応づけられているかを確認する。",
        ),
        Step(
            op="name_corresponding_side",
            args=[], result_srepr=correct, result_display=correct,
            narration="対応する位置にある頂点どうしが結ぶ辺が、対応する辺になることから読み取る。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct,
        distractors=[wrong_symbol, wrong_correspondence],
        fact_id="congruence.symbol_and_correspondence",
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.congruence_corresponding_pair")
def congruence_corresponding_pair(
    p_labels: object, q_labels: object, angle_i: object, side_i: object, side_j: object
) -> Solution:
    """指定した角・辺に対応する角・辺をそれぞれ答える（g2_l36.knowledge Lv2）。

    p_labels/q_labels（対応順に並んだ3頂点の文字列）と位置インデックス
    angle_i, side_i, side_j だけから、対応関係の定義に従って機械的に決まる
    （double-solve）。答えは ChoiceAnswer（対応する角・辺を1文にまとめた答え）。
    """
    p = str(p_labels)
    q = str(q_labels)
    ai = int(str(angle_i))
    si, sj = int(str(side_i)), int(str(side_j))
    given_angle = _angle_name(p, ai)
    given_side = _side_name(p, si, sj)
    correct_angle = _angle_name(q, ai)
    correct_side = _side_name(q, si, sj)
    wrong_angle = next(_angle_name(q, x) for x in range(3) if x != ai)
    wrong_side = _side_name(q, *_other_side_pair(si, sj))
    correct = f"{given_angle}に対応する角は{correct_angle}、{given_side}に対応する辺は{correct_side}"
    wrong_a = f"{given_angle}に対応する角は{wrong_angle}、{given_side}に対応する辺は{correct_side}"
    wrong_s = f"{given_angle}に対応する角は{correct_angle}、{given_side}に対応する辺は{wrong_side}"
    steps = [
        Step(
            op="identify_angle_correspondence",
            args=[], result_srepr="", result_display=f"{p} と {q}",
            narration="合同を表す式で、角の頂点がどの位置に対応づけられているかを確認する。",
        ),
        Step(
            op="name_corresponding_angle",
            args=[], result_srepr=correct_angle, result_display=correct_angle,
            narration="対応する位置にある頂点にできる角が、対応する角になることから読み取る。",
        ),
        Step(
            op="identify_side_correspondence",
            args=[], result_srepr="", result_display=f"{p} と {q}",
            narration="合同を表す式で、辺の両端の頂点がどの位置に対応づけられているかを確認する。",
        ),
        Step(
            op="name_corresponding_side",
            args=[], result_srepr=correct_side, result_display=correct_side,
            narration="対応する位置にある頂点どうしが結ぶ辺が、対応する辺になることから読み取る。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct,
        distractors=[wrong_a, wrong_s],
        fact_id="congruence.identify_corresponding_pair",
    )
    return Solution(answer=answer, steps=steps)
