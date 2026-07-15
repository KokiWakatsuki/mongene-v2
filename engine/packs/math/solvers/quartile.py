"""四分位数・箱ひげ図まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（データ列）から答えと steps を導く（recipe の構成値は
見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C11（データ・統計）クラスタのうち g2_l55〜g2_l57（四分位数・箱ひげ図）の非 visual セル
（箱ひげ図を「かく/読む」visual セルは対象外）を扱う:
  - `math.median_value`: g2_l55.calculation Lv1（中央値=第2四分位数）
  - `math.quartiles_iqr`: g2_l55.calculation Lv3（第1/第3四分位数・四分位範囲）
  - `math.five_number_summary`: g2_l56.calculation Lv1（最小値・最大値・第1/第3四分位数）
  - `math.classify_distribution_statistic`: g2_l57.knowledge Lv1（統計量が分布の何を表すか判別）

四分位数は「中央値を境に下組/上組に分け、それぞれの中央値をとる」教科書式（データ数が
奇数のときは中央値を除いて2等分、偶数のときはそのまま2等分）で計算する。

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _median_of(seq: list[int]) -> sympy.Rational | sympy.Integer:
    m = len(seq)
    if m % 2 == 1:
        return sympy.Integer(seq[m // 2])
    return sympy.Rational(seq[m // 2 - 1] + seq[m // 2], 2)


def _split_halves(sorted_data: list[int]) -> tuple[list[int], list[int]]:
    n = len(sorted_data)
    mid = n // 2
    if n % 2 == 1:
        return sorted_data[:mid], sorted_data[mid + 1 :]
    return sorted_data[:mid], sorted_data[mid:]


# ---------------------------------------------------------------------------
# g2_l55.calculation Lv1: 中央値（第2四分位数）
# ---------------------------------------------------------------------------
@register_solver("math.median_value")
def median_value(data: object) -> Solution:
    """データを大きさの順に並べ、中央値（第2四分位数）を求める（g2_l55.calculation Lv1）。

    データの値の列だけから計算する（double-solve）。答えは単一値の SymbolicAnswer。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    ordered = sorted(vals)
    median = _median_of(ordered)
    disp = sympy.sstr(median)
    srepr = sympy.srepr(median)
    steps = [
        Step(
            op="sort_data",
            args=[],
            result_srepr="",
            result_display="データを大きさの順に並べる",
            narration="データを大きさの順に並べかえる。",
        ),
        Step(
            op="compute_median",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="並べたデータの中央にある値（中央値）を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l55.calculation Lv3: 第1/第3四分位数・四分位範囲
# ---------------------------------------------------------------------------
@register_solver("math.quartiles_iqr")
def quartiles_iqr(data: object) -> Solution:
    """第1四分位数・第3四分位数・四分位範囲を求める（g2_l55.calculation Lv3）。

    データの値の列だけから計算する（double-solve、データ数の偶奇いずれにも対応）。
    答えは Tuple(第1四分位数, 第3四分位数, 四分位範囲) の SymbolicAnswer。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    ordered = sorted(vals)
    lower, upper = _split_halves(ordered)
    q1 = _median_of(lower)
    q3 = _median_of(upper)
    iqr = q3 - q1
    disp = f"第1四分位数 {q1}、第3四分位数 {q3}、四分位範囲 {iqr}"
    srepr = sympy.srepr(sympy.Tuple(q1, q3, iqr))
    steps = [
        Step(
            op="split_into_halves",
            args=[],
            result_srepr="",
            result_display="中央値を境に下組と上組に分ける",
            narration="データを大きさの順に並べ、中央値を境に下組と上組に分ける。",
        ),
        Step(
            op="compute_q1_q3",
            args=[],
            result_srepr="",
            result_display="下組・上組それぞれの中央値を求める",
            narration="下組の中央値を第一四分位数、上組の中央値を第三四分位数とする。",
        ),
        Step(
            op="compute_iqr",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="上組の中央値から下組の中央値をひき、四分位範囲を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l56.calculation Lv1: 最小値・最大値・第1/第3四分位数（5数要約の一部）
# ---------------------------------------------------------------------------
@register_solver("math.five_number_summary")
def five_number_summary(data: object) -> Solution:
    """最小値・最大値・第1四分位数・第3四分位数を求める（g2_l56.calculation Lv1）。

    データの値の列だけから計算する（double-solve）。答えは
    Tuple(最小値, 最大値, 第1四分位数, 第3四分位数) の SymbolicAnswer。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    ordered = sorted(vals)
    lower, upper = _split_halves(ordered)
    q1 = _median_of(lower)
    q3 = _median_of(upper)
    v_min = sympy.Integer(ordered[0])
    v_max = sympy.Integer(ordered[-1])
    disp = f"最小値 {v_min}、最大値 {v_max}、第1四分位数 {q1}、第3四分位数 {q3}"
    srepr = sympy.srepr(sympy.Tuple(v_min, v_max, q1, q3))
    steps = [
        Step(
            op="identify_min_max",
            args=[],
            result_srepr="",
            result_display="データを大きさの順に並べ両端の値を読み取る",
            narration="データを大きさの順に並べ、いちばん小さい値といちばん大きい値を求める。",
        ),
        Step(
            op="compute_q1_q3",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="中央値を境に下組と上組に分け、それぞれの中央値を第一四分位数・第三四分位数とする。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l57.knowledge Lv1: 統計量が分布の何を表すか判別する
# ---------------------------------------------------------------------------
_CENTER_ROLE = "データの中心（真ん中あたり）の位置を表す"
_SPREAD_ROLE = "データの散らばりの度合いを表す"
_STATISTIC_ROLE: dict[str, str] = {
    "median": _CENTER_ROLE,
    "range": _SPREAD_ROLE,
    "iqr": _SPREAD_ROLE,
}


@register_solver("math.quartiles_full_summary")
def quartiles_full_summary(data: object) -> Solution:
    """第1四分位数・第2四分位数(中央値)・第3四分位数・四分位範囲を求める（exam_l7.find_value Lv3）。

    データの値の列だけから計算する（double-solve、データ数の偶奇いずれにも対応）。答えは
    Tuple(第1四分位数, 第2四分位数, 第3四分位数, 四分位範囲) の SymbolicAnswer。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    ordered = sorted(vals)
    lower, upper = _split_halves(ordered)
    q1 = _median_of(lower)
    q2 = _median_of(ordered)
    q3 = _median_of(upper)
    iqr = q3 - q1
    disp = f"第1四分位数 {q1}、第2四分位数(中央値) {q2}、第3四分位数 {q3}、四分位範囲 {iqr}"
    srepr = sympy.srepr(sympy.Tuple(q1, q2, q3, iqr))
    steps = [
        Step(
            op="compute_median",
            args=[],
            result_srepr="",
            result_display="データ全体の中央値を求める",
            narration="データを大きさの順に並べ、データ全体の中央値（第二四分位数）を求める。",
        ),
        Step(
            op="split_into_halves",
            args=[],
            result_srepr="",
            result_display="中央値を境に下組と上組に分ける",
            narration="中央値を境に下組と上組に分ける。",
        ),
        Step(
            op="compute_q1_q3_iqr",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="下組・上組それぞれの中央値を第一・第三四分位数とし、その差から四分位範囲を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


@register_solver("math.classify_distribution_statistic")
def classify_distribution_statistic(concept: object) -> Solution:
    """中央値・範囲・四分位範囲が分布の何を表すかを判別する（g2_l57.knowledge Lv1）。

    concept（統計量の種類）だけから判定する（double-solve）。答えは ChoiceAnswer。
    narration に数字は書かない。
    """
    c = str(concept)
    if c not in _STATISTIC_ROLE:
        raise ValueError(f"未知の concept: {c!r}")
    correct = _STATISTIC_ROLE[c]
    other = _SPREAD_ROLE if correct == _CENTER_ROLE else _CENTER_ROLE
    steps = [
        Step(
            op="identify_statistic",
            args=[],
            result_srepr=c,
            result_display="対象の統計量が何を求めた値かを読み取る",
            narration="対象の統計量が、データのどのような性質から求められた値かを読み取る。",
        ),
        Step(
            op="classify_distribution_statistic",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その値が、データの中心の位置と散らばりの度合いのどちらを表すかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id=f"distribution_statistic.role.{c}")
    return Solution(answer=answer, steps=steps)
