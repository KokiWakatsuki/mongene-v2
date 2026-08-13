"""四分位数・箱ひげ図まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（データ列）から答えと steps を導く（recipe の構成値は
見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C11（データ・統計）クラスタのうち g2_l55〜g2_l57（四分位数・箱ひげ図）を扱う:
  - `math.median_value`: g2_l55.calculation Lv1（中央値=第2四分位数）
  - `math.quartiles_iqr`: g2_l55.calculation Lv3（第1/第3四分位数・四分位範囲）
  - `math.five_number_summary`: g2_l56.calculation Lv1（最小値・最大値・第1/第3四分位数）
  - `math.classify_distribution_statistic`: g2_l57.knowledge Lv1（統計量が分布の何を表すか判別）
  - `math.read_box_plot_values`: g2_l56.graph_table Lv1（箱ひげ図から値を読む）
  - `math.draw_box_plot_features`: g2_l56.graph_table Lv3（データから5数要約を求めかく）
  - `math.compare_box_plots_center_spread`: g2_l57.graph_table Lv1（2本の中央値と範囲を読む）
  - `math.compare_box_plots_iqr`: g2_l57.graph_table Lv3（2本の四分位範囲を比べる）
  - `math.compare_box_plot_statistic`: g2_l57.word_problem Lv2（統計量が大きいのはどちらか）
  - `math.judge_box_plot_trend_claim`: g2_l57.word_problem Lv3（傾向の主張の当否）
  - `math.judge_box_plot_stability_claim`: g2_l57.word_problem Lv4（主張の妥当性の批判的判断）

四分位数は「中央値を境に下組/上組に分け、それぞれの中央値をとる」教科書式（データ数が
奇数のときは中央値を除いて2等分、偶数のときはそのまま2等分）で計算する。

箱ひげ図を「読む」ソルバは **five_number をそのまま受け取らない**。受け取るのは図に
実際に描かれている情報＝目もりの間隔（axis_step）と、箱ひげの各位置が左から何目もり目に
あるか（box_ticks）だけで、そこから値を復元する（`math.read_number_line_point` が
「区間左端・等分数・目もり位置」から値を復元するのと同じ形）。答えを params から
読み直すだけの検証にならないための設計。

narration には数字を書かない（漢数字は可・"第一四分位数" のように書く）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    ChoiceAnswer,
    Feature,
    GraphAnswer,
    Solution,
    Step,
    SymbolicAnswer,
)
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


# ---------------------------------------------------------------------------
# 箱ひげ図の visual セル（g2_l56 / g2_l57 の graph_table）
#
# 「読む」系ソルバの入力は図に描かれているものだけ:
#   axis_lo   … 数直線の左端の目もりが表す値
#   axis_step … 目もり1つぶんの値
#   box_ticks … 箱ひげの5か所が左端から何目もり目にあるか（[最小,Q1,中央,Q3,最大]）
# five_number（＝答え）は渡さない。ここで axis_lo + axis_step * tick として復元する。
# ---------------------------------------------------------------------------
_QUARTILE_LABEL_JP = ("最小値", "第一四分位数", "中央値", "第三四分位数", "最大値")

# read_target -> (five_number のどの位置を読むか, 表示ラベル)
# ラベルの序数は**漢数字**で書く（"第3四分位数" と書くと answer.display に数値トークン
# "3" が生まれ、問題文の "3" と衝突して G-Q5t が誤検出する）。
_BOX_READ_TARGETS: dict[str, tuple[tuple[int, int], tuple[str, str]]] = {
    "median_q3": ((2, 3), ("中央値", "第三四分位数")),
    "q1_median": ((1, 2), ("第一四分位数", "中央値")),
    "min_max": ((0, 4), ("最小値", "最大値")),
}


def _fmt_half(value: sympy.Expr) -> str:
    """整数はそのまま、分母2の分数は小数で書く（四分位数は整数か x.5 にしかならない）。

    それ以外が来たら分数のまま出す——構成が崩れた合図を隠さないため。
    """
    rational = sympy.Rational(value)
    if rational.q == 1:
        return str(int(rational))
    if rational.q == 2:
        return f"{float(rational):.1f}"
    return str(rational)


def _restore_five(axis_lo: object, axis_step: object, box_ticks: object) -> list[sympy.Integer]:
    """目もりの位置から5数要約を復元する（狭義単調増加＝退化なしを強制）。"""
    lo = int(str(axis_lo))
    step = int(str(axis_step))
    if step <= 0:
        raise ValueError(f"目もりの間隔は正: {step!r}")
    ticks = [int(str(t)) for t in cast("list[object]", box_ticks)]
    if len(ticks) != 5:
        raise ValueError("box_ticks は [最小値, Q1, 中央値, Q3, 最大値] の5つ")
    if any(ticks[i] >= ticks[i + 1] for i in range(4)):
        raise ValueError(f"box_ticks が狭義単調増加でない（箱やひげが潰れる）: {ticks}")
    return [sympy.Integer(lo + step * t) for t in ticks]


@register_solver("math.read_box_plot_values")
def read_box_plot_values(
    axis_lo: object, axis_step: object, box_ticks: object, read_target: object
) -> Solution:
    """箱ひげ図から指定された2つの値を読み取る（g2_l56.graph_table Lv1）。

    図に描かれている情報（目もりの間隔と箱ひげの位置）だけから値を復元する。
    答えは Tuple(値1, 値2) の SymbolicAnswer。
    """
    five = _restore_five(axis_lo, axis_step, box_ticks)
    key = str(read_target)
    if key not in _BOX_READ_TARGETS:
        raise ValueError(f"未知の read_target: {key!r}")
    idx, labels = _BOX_READ_TARGETS[key]
    values = [five[i] for i in idx]
    disp = "、".join(f"{lab} {v}" for lab, v in zip(labels, values, strict=True))
    srepr = sympy.srepr(sympy.Tuple(*values))
    steps = [
        Step(
            op="read_axis_step",
            args=[],
            result_srepr="",
            result_display="数直線の目もり一つぶんの大きさを読む",
            narration="数直線の目もりを見て、目もり一つぶんがどれだけの大きさを表すかを読み取る。",
        ),
        Step(
            op="read_box_plot_values",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="たずねられた位置（箱の線・ひげの先）が数直線のどこにあたるかを数えて値にする。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.draw_box_plot_features")
def draw_box_plot_features(data: object) -> Solution:
    """データから5数要約を求め、箱ひげ図の特徴量として返す（g2_l56.graph_table Lv3）。

    データの値の列だけから計算する（double-solve）。答えは GraphAnswer で、features は
    最小値・第1四分位数・中央値・第3四分位数・最大値の5点＝かく対象そのもの。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    if len(vals) < 8:
        raise ValueError(f"箱ひげ図をかくには8個以上のデータが必要: {len(vals)}")
    ordered = sorted(vals)
    lower, upper = _split_halves(ordered)
    five: list[sympy.Expr] = [
        sympy.Integer(ordered[0]),
        _median_of(lower),
        _median_of(ordered),
        _median_of(upper),
        sympy.Integer(ordered[-1]),
    ]
    if any(five[i] >= five[i + 1] for i in range(4)):
        raise ValueError(f"5数要約が狭義単調増加でない（箱やひげが潰れる）: {five}")

    kinds = ("min", "q1", "median", "q3", "max")
    # **四分位数は小数で書く**（EVALUATION D-5/R-7。個数が偶数の組では中央値どうしの
    # 平均になるので `27/2` `91/2` と仮分数で出ていた。教科書は 13.5・45.5 と書く。
    # 整数データの四分位数は必ず整数か x.5 なので、小数は必ず書き切れる）。
    features = [
        Feature(kind=k, srepr=sympy.srepr(v), display=f"{lab} {_fmt_half(v)}")
        for k, lab, v in zip(kinds, _QUARTILE_LABEL_JP, five, strict=True)
    ]
    disp = "、".join(f.display for f in features)
    steps = [
        Step(
            op="sort_data",
            args=[],
            result_srepr="",
            result_display="データを大きさの順に並べる",
            narration="データを大きさの順に並べかえる。",
        ),
        Step(
            op="compute_five_number",
            args=[],
            result_srepr="",
            result_display=disp,
            narration="両端の値を読み、中央値を境に下組と上組に分けてそれぞれの中央値を求める。",
        ),
        Step(
            op="draw_box_plot",
            args=[],
            result_srepr="",
            result_display="求めた五つの値を数直線上にとって箱とひげをかく",
            narration="求めた五つの値を数直線上にとり、四分位数を結んだ箱と、両端まで伸ばしたひげをかく。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features), steps=steps)


@register_solver("math.compare_box_plots_center_spread")
def compare_box_plots_center_spread(
    axis_lo: object, axis_step: object, box_ticks_a: object, box_ticks_b: object
) -> Solution:
    """2本の箱ひげ図から、それぞれの中央値と範囲を読み取る（g2_l57.graph_table Lv1）。

    答えは Tuple(中央値A, 中央値B, 範囲A, 範囲B) の SymbolicAnswer。
    """
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    med_a, med_b = a[2], b[2]
    range_a, range_b = a[4] - a[0], b[4] - b[0]
    values = [med_a, med_b, range_a, range_b]
    disp = f"Aの中央値 {med_a}、Bの中央値 {med_b}、Aの範囲 {range_a}、Bの範囲 {range_b}"
    srepr = sympy.srepr(sympy.Tuple(*values))
    steps = [
        Step(
            op="read_axis_step",
            args=[],
            result_srepr="",
            result_display="数直線の目もり一つぶんの大きさを読む",
            narration="数直線の目もりを見て、目もり一つぶんがどれだけの大きさを表すかを読み取る。",
        ),
        Step(
            op="read_medians",
            args=[],
            result_srepr="",
            result_display=f"Aの中央値 {med_a}、Bの中央値 {med_b}",
            narration="それぞれの箱の中にひかれた線の位置を読み、中央値を求める。",
        ),
        Step(
            op="read_ranges",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="それぞれのひげの両端の値を読み、その差から範囲を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.compare_box_plots_iqr")
def compare_box_plots_iqr(
    axis_lo: object, axis_step: object, box_ticks_a: object, box_ticks_b: object
) -> Solution:
    """2本の箱ひげ図の四分位範囲を比べ、その差を求める（g2_l57.graph_table Lv3）。

    答えは Tuple(四分位範囲A, 四分位範囲B, 差) の SymbolicAnswer。差は絶対値。
    """
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    iqr_a, iqr_b = a[3] - a[1], b[3] - b[1]
    diff = abs(iqr_a - iqr_b)
    if diff == 0:
        raise ValueError("二つの四分位範囲が等しい（散らばりの違いを読み取れない）")
    values = [iqr_a, iqr_b, diff]
    disp = f"Aの四分位範囲 {iqr_a}、Bの四分位範囲 {iqr_b}、その差 {diff}"
    srepr = sympy.srepr(sympy.Tuple(*values))
    steps = [
        Step(
            op="read_axis_step",
            args=[],
            result_srepr="",
            result_display="数直線の目もり一つぶんの大きさを読む",
            narration="数直線の目もりを見て、目もり一つぶんがどれだけの大きさを表すかを読み取る。",
        ),
        Step(
            op="read_quartiles_both",
            args=[],
            result_srepr="",
            result_display="それぞれの箱の左端と右端の値を読む",
            narration="それぞれの箱の左端と右端の位置を読み、第一四分位数と第三四分位数を求める。",
        ),
        Step(
            op="compute_iqr_both",
            args=[],
            result_srepr="",
            result_display=f"Aの四分位範囲 {iqr_a}、Bの四分位範囲 {iqr_b}",
            narration="それぞれについて第三四分位数から第一四分位数をひき、四分位範囲を求める。",
        ),
        Step(
            op="compare_iqr_difference",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="二つの四分位範囲を比べ、大きいほうから小さいほうをひいて違いを求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# 箱ひげ図の文章題（g2_l57.word_problem Lv2/Lv3/Lv4）
#
# 「どちらか」「いえるか」「妥当か」を判定する ChoiceAnswer 系。判定規準は
# 決定論（同じ図なら必ず同じ結論）で、かつ教科書が根拠に使う量だけで書けること。
# ---------------------------------------------------------------------------
# statistic -> (five_number のどの位置の差か, 表示名)。median は差ではなく値そのもの。
_BOX_STATISTIC: dict[str, tuple[tuple[int, int], str]] = {
    "median": ((2, 2), "中央値"),
    "range": ((0, 4), "範囲"),
    "iqr": ((1, 3), "四分位範囲"),
}


def _statistic_value(five: list[sympy.Integer], statistic: str) -> sympy.Integer:
    (lo_i, hi_i), _ = _BOX_STATISTIC[statistic]
    if lo_i == hi_i:
        return five[hi_i]
    return five[hi_i] - five[lo_i]


@register_solver("math.compare_box_plot_statistic")
def compare_box_plot_statistic(
    axis_lo: object,
    axis_step: object,
    box_ticks_a: object,
    box_ticks_b: object,
    statistic: object,
) -> Solution:
    """2本の箱ひげ図で、指定の統計量が大きいのはどちらかを答える（g2_l57.word_problem Lv2）。

    答えは ChoiceAnswer（"A" / "B"）。値が等しいと「どちらか」に答えが定まらないので弾く。
    """
    s = str(statistic)
    if s not in _BOX_STATISTIC:
        raise ValueError(f"未知の statistic: {s!r}")
    name = _BOX_STATISTIC[s][1]
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    va, vb = _statistic_value(a, s), _statistic_value(b, s)
    if va == vb:
        raise ValueError(f"AとBの{name}が等しく、どちらが大きいか定まらない")
    correct, other = ("A", "B") if va > vb else ("B", "A")
    steps = [
        Step(
            op=f"read_{s}_both",
            args=[],
            result_srepr="",
            result_display=f"AとBの{name}を読む",
            narration=f"AとBそれぞれの箱ひげ図から{name}を読み取る。",
        ),
        Step(
            op=f"compare_{s}",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=f"読み取った二つの{name}を比べ、大きいほうを答える。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id=f"box_plot.compare.{s}")
    return Solution(answer=answer, steps=steps)


_TREND_CLAIM_YES = "いえる"
_TREND_CLAIM_NO = "いえない"


@register_solver("math.judge_box_plot_trend_claim")
def judge_box_plot_trend_claim(
    axis_lo: object, axis_step: object, box_ticks_a: object, box_ticks_b: object
) -> Solution:
    """「Bのほうが大きい傾向がある」といえるかを判断する（g2_l57.word_problem Lv3）。

    判定規準（決定論・複数の観点）: 第一四分位数・中央値・第三四分位数の**三つとも**
    B が A を上回るとき「いえる」。一つでも下回れば、観点によって結論が変わるので
    「いえない」。答えは ChoiceAnswer。
    """
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    all_above = all(b[i] > a[i] for i in (1, 2, 3))
    correct = _TREND_CLAIM_YES if all_above else _TREND_CLAIM_NO
    other = _TREND_CLAIM_NO if all_above else _TREND_CLAIM_YES
    steps = [
        Step(
            op="read_quartiles_both",
            args=[],
            result_srepr="",
            result_display="AとBの四分位数を読む",
            narration="AとBそれぞれの箱ひげ図から、第一四分位数・中央値・第三四分位数を読み取る。",
        ),
        Step(
            op="compare_center",
            args=[],
            result_srepr="",
            result_display="中央値を比べる",
            narration="まん中の位置を表す中央値を比べ、どちらが大きいかを見る。",
        ),
        Step(
            op="compare_quartile_positions",
            args=[],
            result_srepr="",
            result_display="箱の左端と右端も比べる",
            narration="中央値だけでは決められないので、箱の左端と右端の位置も同じように比べる。",
        ),
        Step(
            op="judge_trend_claim",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="三つの四分位数がそろって上回っているかどうかで、傾向があるといえるかを判断する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="box_plot.judge_trend_claim"
    )
    return Solution(answer=answer, steps=steps)


_VALID_CLAIM_YES = "妥当である"
_VALID_CLAIM_NO = "妥当でない"


@register_solver("math.judge_box_plot_stability_claim")
def judge_box_plot_stability_claim(
    axis_lo: object, axis_step: object, box_ticks_a: object, box_ticks_b: object
) -> Solution:
    """「Aのほうが安定して多い」という主張の妥当性を判断する（g2_l57.word_problem Lv4）。

    「多い」＝中央値が大きい、「安定している」＝四分位範囲が小さい、と読み替える。
    両方を満たすときだけ主張は妥当。片方しか満たさないときは、支持する根拠と反論の
    根拠が同時に存在するので妥当でない。答えは ChoiceAnswer。
    """
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    med_a, med_b = _statistic_value(a, "median"), _statistic_value(b, "median")
    iqr_a, iqr_b = _statistic_value(a, "iqr"), _statistic_value(b, "iqr")
    if med_a == med_b or iqr_a == iqr_b:
        raise ValueError("中央値または四分位範囲が等しく、主張の当否が定まらない")
    valid = bool(med_a > med_b and iqr_a < iqr_b)
    correct = _VALID_CLAIM_YES if valid else _VALID_CLAIM_NO
    other = _VALID_CLAIM_NO if valid else _VALID_CLAIM_YES
    steps = [
        Step(
            op="read_medians_both",
            args=[],
            result_srepr="",
            result_display="AとBの中央値を読む",
            narration="「多い」といえるかを見るために、AとBそれぞれの中央値を読み取る。",
        ),
        Step(
            op="read_iqr_both",
            args=[],
            result_srepr="",
            result_display="AとBの四分位範囲を求める",
            narration="「安定している」といえるかを見るために、箱の幅から四分位範囲を求める。",
        ),
        Step(
            op="weigh_support_and_counter",
            args=[],
            result_srepr="",
            result_display="主張を支持する根拠と反論となる根拠を並べる",
            narration="主張を支持する根拠と、反論となる根拠を、それぞれどの量から言えるか整理する。",
        ),
        Step(
            op="judge_claim_validity",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="二つの根拠がそろって主張を支えているかどうかで、主張の当否を判断する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="box_plot.judge_stability_claim"
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# exam_l7（入試融合・データの活用）— C13
# ---------------------------------------------------------------------------
@register_solver("math.read_box_plot_single_statistic")
def read_box_plot_single_statistic(
    axis_lo: object, axis_step: object, box_ticks: object, statistic: object
) -> Solution:
    """箱ひげ図から統計量を1つだけ読み取る（exam_l7.word_problem Lv3 の (1)）。

    `math.read_box_plot_values` が2つ組で読むのに対し、こちらは中央値なら中央値だけを
    答える。指定できるのは `_BOX_STATISTIC` の鍵（中央値・範囲・四分位範囲）で、
    範囲・四分位範囲は差として求める。
    """
    s = str(statistic)
    if s not in _BOX_STATISTIC:
        raise ValueError(f"未知の statistic: {s!r}")
    name = _BOX_STATISTIC[s][1]
    five = _restore_five(axis_lo, axis_step, box_ticks)
    value = _statistic_value(five, s)
    srepr = sympy.srepr(value)
    disp = f"{name} {value}"
    steps = [
        Step(
            op="read_axis_step", args=[], result_srepr="",
            result_display="数直線の目もり一つぶんの大きさを読む",
            narration="数直線の目もりを見て、目もり一つぶんがどれだけの大きさを表すかを読み取る。",
        ),
        Step(
            op=f"read_{s}_value", args=[], result_srepr=srepr, result_display=disp,
            narration=f"箱ひげ図の{name}にあたる位置が数直線のどこかを数えて、値にする。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


_SPREAD_CLAIM_YES = "正しいといえる"
_SPREAD_CLAIM_NO = "正しいとはいえない"


@register_solver("math.judge_spread_claim_by_two_measures")
def judge_spread_claim_by_two_measures(
    axis_lo: object, axis_step: object, box_ticks_a: object, box_ticks_b: object
) -> Solution:
    """「Aのほうがばらつきが大きい」という主張の当否を、2つの指標から判断する。

    exam_l7.word_problem Lv4。ばらつきの指標は**四分位範囲と範囲の2つ**あり、
    どちらでも A が大きければ主張は正しいといえる。片方でしか A が大きくないときは
    指標の取り方で結論が変わるので「正しいとはいえない」——これが入試で問われる
    「主張の妥当性」の中身で、四分位範囲だけを見て即断すると落とす。

    中央値が等しい構成（＝ばらつきだけが論点になる）を前提にする。等しくない場合や
    どちらかの指標が引き分けになる場合は判断が定まらないので例外にする。
    """
    a = _restore_five(axis_lo, axis_step, box_ticks_a)
    b = _restore_five(axis_lo, axis_step, box_ticks_b)
    if _statistic_value(a, "median") != _statistic_value(b, "median"):
        raise ValueError("中央値が等しくない（ばらつきだけの主張にならない）")
    iqr_a, iqr_b = _statistic_value(a, "iqr"), _statistic_value(b, "iqr")
    rng_a, rng_b = _statistic_value(a, "range"), _statistic_value(b, "range")
    if iqr_a == iqr_b or rng_a == rng_b:
        raise ValueError("四分位範囲または範囲が等しく、主張の当否が定まらない")
    valid = bool(iqr_a > iqr_b and rng_a > rng_b)
    correct = _SPREAD_CLAIM_YES if valid else _SPREAD_CLAIM_NO
    other = _SPREAD_CLAIM_NO if valid else _SPREAD_CLAIM_YES
    steps = [
        Step(
            op="read_iqr_both", args=[], result_srepr="",
            result_display="AとBの四分位範囲を求める",
            narration="箱の幅にあたる四分位範囲を、AとBそれぞれについて求める。",
        ),
        Step(
            op="read_range_both", args=[], result_srepr="",
            result_display="AとBの範囲を求める",
            narration="ひげの先から先までの幅にあたる範囲も、AとBそれぞれについて求める。",
        ),
        Step(
            op="check_measures_agree", args=[], result_srepr="",
            result_display="二つの指標が同じ側を指すかを確かめる",
            narration="ばらつきの指標は一つではないので、四分位範囲と範囲が同じ側を指しているかを確かめる。",
        ),
        Step(
            op="judge_spread_claim", args=[], result_srepr=correct, result_display=correct,
            narration="二つの指標がそろって主張を支えていれば正しいといえ、"
                      "食い違えば指標の取り方で結論が変わるので正しいとはいえない。",
        ),
    ]
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=[other], fact_id="box_plot.judge_spread_claim"
        ),
        steps=steps,
    )
