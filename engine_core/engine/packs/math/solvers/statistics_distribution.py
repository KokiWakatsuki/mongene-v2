"""度数分布・代表値まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（階級構成・度数列・生データ列・mode）から答えと steps を
導く（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C11（データ・統計）クラスタのうち g1_l54〜g1_l57（度数分布表・相対度数・累積度数・代表値）
の非 visual セルを対象にする:
  - `math.frequency_table_value`: g1_l54.calculation Lv1（階級値・度数の合計）
  - `math.compare_relative_frequency`: g1_l55.calculation Lv2（2集団の相対度数比較）
  - `math.cumulative_frequency_value`: g1_l56.calculation Lv1（累積度数）
  - `math.cumulative_relative_frequency_and_complement`: g1_l56.calculation Lv2
    （累積相対度数・以上の割合%）
  - `math.representative_values_raw`: g1_l57.calculation Lv1（生データの平均値・中央値・最頻値）
  - `math.mean_from_grouped_table`: g1_l57.calculation Lv2（度数分布表からの平均値）
  - `math.judge_appropriate_representative_value`: g1_l57.knowledge Lv2（代表値の使い分け判別）
（g1_l55.calculation Lv1 は既存 `math.relative_frequency`(probability.py) を再利用。
 g1_l54/l55/l56/l57 knowledge Lv1 は既存 `math.term_recall` ハブに domain 追加で対応。）

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_measure


def _class_midpoint(class_start: int, class_width: int, index: int) -> sympy.Rational:
    lo = class_start + class_width * index
    return sympy.Rational(2 * lo + class_width, 2)


# ---------------------------------------------------------------------------
# g1_l54.calculation Lv1: 階級値・度数の合計
# ---------------------------------------------------------------------------
@register_solver("math.frequency_table_value")
def frequency_table_value(class_start: object, class_width: object, frequencies: object, target_index: object) -> Solution:
    """度数分布表の指定した階級の階級値と、度数の合計を求める（g1_l54.calculation Lv1）。

    階級の下端・階級の幅・各階級の度数・対象の階級番号だけから計算する（double-solve）。
    答えは Tuple(階級値, 度数の合計) の SymbolicAnswer。narration に数字は書かない。
    """
    start = int(str(class_start))
    width = int(str(class_width))
    freqs = [int(str(f)) for f in cast("list[object]", frequencies)]
    idx = int(str(target_index))
    midpoint = _class_midpoint(start, width, idx)
    total = sympy.Integer(sum(freqs))
    # 階級値は「量」なので有限小数で書く（実物は 57.5 と書き、115/2 とは書かない）。
    disp = f"階級値 {fmt_measure(midpoint)}、度数の合計 {total}"
    srepr = sympy.srepr(sympy.Tuple(midpoint, total))
    steps = [
        Step(
            op="compute_class_value",
            args=[],
            result_srepr=sympy.srepr(midpoint),
            result_display=fmt_measure(midpoint),
            narration="対象の階級の下端と上端の値の平均を求め、階級値とする。",
            detail=(
                f"({start + width * idx} + {start + width * (idx + 1)}) ÷ 2 を計算して、"
                f"階級値を求める。"
            ),
        ),
        Step(
            op="sum_frequencies",
            args=[],
            result_srepr=srepr,
            # **この手で得たのは度数の合計だけ。** 答え全体（階級値も含む）を
            # 括弧に写していたので、1手目で出した 57.5 が2度出ていた。
            result_display=str(total),
            narration="すべての階級の度数を足し合わせ、度数の合計を求める。",
            detail=f"{' + '.join(str(f) for f in freqs)} を計算して、度数の合計を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l55.calculation Lv2: 総度数の異なる2集団の相対度数を比較する
# ---------------------------------------------------------------------------
def _fmt_relative(v: sympy.Rational) -> str:
    """相対度数の表示。**割り切れるなら小数**、そうでなければ分数。

    相対度数は小数で答えるのが教材の作法（EVALUATION D-24）。
    recipe 側で割り切れる組だけを引くので、実際には常に小数になる。
    """
    q = int(v.q)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    if q != 1:
        return str(v)
    digits, r = 0, sympy.Rational(v)
    while r.q != 1:
        r *= 10
        digits += 1
    return f"{float(v):.{digits}f}" if digits else str(int(v))


@register_solver("math.compare_relative_frequency")
def compare_relative_frequency(freq_a: object, total_a: object, freq_b: object, total_b: object) -> Solution:
    """総度数の異なる2集団それぞれの相対度数を求め、どちらが大きいか比較する（g1_l55.calculation Lv2）。

    それぞれの度数・総度数だけから相対度数を求める（double-solve）。答えは
    Tuple(相対度数A, 相対度数B) の SymbolicAnswer（display にどちらが大きいかを含める）。
    """
    fa, ta = int(str(freq_a)), int(str(total_a))
    fb, tb = int(str(freq_b)), int(str(total_b))
    rel_a = sympy.Rational(fa, ta)
    rel_b = sympy.Rational(fb, tb)
    larger = "A" if rel_a > rel_b else "B"
    disp = f"A: {_fmt_relative(rel_a)}、B: {_fmt_relative(rel_b)}（{larger}のほうが大きい）"
    srepr = sympy.srepr(sympy.Tuple(rel_a, rel_b))
    steps = [
        Step(
            op="compute_relative_frequency_each",
            args=[],
            result_srepr="",
            result_display=f"A {_fmt_relative(rel_a)}、B {_fmt_relative(rel_b)}",
            narration="それぞれの集団について、対象の階級の度数を総度数でわり、相対度数を求める。",
        ),
        Step(
            op="compare_relative_frequency",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="求めた相対度数どうしを比べ、値が大きいほうを答える。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l56.calculation Lv1: 累積度数
# ---------------------------------------------------------------------------
@register_solver("math.cumulative_frequency_value")
def cumulative_frequency_value(frequencies: object, target_index: object) -> Solution:
    """指定した階級までの累積度数を求める（g1_l56.calculation Lv1）。

    各階級の度数の列と対象の階級番号だけから、いちばん小さい階級から積み上げて計算する
    （double-solve）。答えは整数の SymbolicAnswer。
    """
    freqs = [int(str(f)) for f in cast("list[object]", frequencies)]
    idx = int(str(target_index))
    cum = sympy.Integer(sum(freqs[: idx + 1]))
    steps = [
        Step(
            op="accumulate_frequency",
            args=[],
            result_srepr=sympy.srepr(cum),
            result_display=str(cum),
            narration="いちばん小さい階級から対象の階級まで、度数を順に足し合わせる。",
            detail=(
                f"いちばん小さい階級から順に "
                f"{' + '.join(str(f) for f in freqs[: idx + 1])} を足して、累積度数を求める。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(cum), display=str(cum))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l56.calculation Lv2: 累積相対度数・以上の割合(%)
# ---------------------------------------------------------------------------
@register_solver("math.cumulative_relative_frequency_and_complement")
def cumulative_relative_frequency_and_complement(frequencies: object, target_index: object) -> Solution:
    """累積相対度数と、その階級を超える部分の割合(%)を求める（g1_l56.calculation Lv2）。

    各階級の度数の列と対象の階級番号だけから計算する（double-solve）。答えは
    Tuple(累積相対度数, 超える部分の割合%) の SymbolicAnswer。
    """
    freqs = [int(str(f)) for f in cast("list[object]", frequencies)]
    idx = int(str(target_index))
    total = sum(freqs)
    cum = sum(freqs[: idx + 1])
    cum_rel = sympy.Rational(cum, total)
    percent_over = (1 - cum_rel) * 100
    # 割合(%) も相対度数と同じ作法で書く。生の Rational を埋めると 92.5% が
    # `185/2%` になっていた（百分率を分数で書く教材は無い）。
    disp = (
        f"累積相対度数 {_fmt_relative(cum_rel)}、"
        f"超える部分の割合 {_fmt_relative(percent_over)}%"
    )
    srepr = sympy.srepr(sympy.Tuple(cum_rel, percent_over))
    steps = [
        Step(
            op="accumulate_relative_frequency",
            args=[],
            result_srepr="",
            result_display=_fmt_relative(cum_rel),
            narration="対象の階級までの累積度数を求め、総度数でわって累積相対度数を求める。",
            detail=f"累積度数 {cum} を総度数 {total} でわる（{cum} ÷ {total}）。",
        ),
        Step(
            op="compute_complement_percent",
            args=[],
            result_srepr=srepr,
            # この手で得たのは「超える部分の割合」だけ（累積相対度数は前の手）。
            result_display=f"{_fmt_relative(percent_over)}%",
            # 「除く」は「わる」とも読める語なので、ひき算は「ひく」と書く。
            narration="全体の割合から累積相対度数をひいた残りを百分率になおし、超える部分の割合を求める。",
            detail=(
                f"1 - {_fmt_relative(cum_rel)} を計算し、100 をかけて百分率になおす。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l57.calculation Lv1: 生データから平均値・中央値・最頻値
# ---------------------------------------------------------------------------
@register_solver("math.representative_values_raw")
def representative_values_raw(data: object) -> Solution:
    """生データの平均値・中央値・最頻値を求める（g1_l57.calculation Lv1）。

    データの値の列だけから計算する（double-solve）。答えは
    Tuple(平均値, 中央値, 最頻値) の SymbolicAnswer。
    """
    vals = [int(str(v)) for v in cast("list[object]", data)]
    n = len(vals)
    mean = sympy.Rational(sum(vals), n)
    ordered = sorted(vals)
    if n % 2 == 1:
        median = sympy.Integer(ordered[n // 2])
    else:
        median = sympy.Rational(ordered[n // 2 - 1] + ordered[n // 2], 2)
    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    mode = sympy.Integer(max(counts, key=lambda k: counts[k]))
    # **代表値は小数で書き切れるなら小数**（EVALUATION D-5/D-28。平均値が `271/8`、
    # 中央値が `71/2` と仮分数で出ていた）。recipe が平均の割り切れる組だけを引くので
    # 平均は整数か小数第2位まで、中央値は個数が偶数のとき x.5 になりうる。
    disp = (
        f"平均値 {_fmt_relative(mean)}、中央値 {_fmt_relative(median)}、最頻値 {mode}"
    )
    srepr = sympy.srepr(sympy.Tuple(mean, median, mode))
    steps = [
        Step(
            op="compute_mean",
            args=[],
            result_srepr="",
            result_display=_fmt_relative(mean),
            narration="データの値をすべて足し合わせ、個数でわって平均値を求める。",
            detail=f"{sum(vals)} ÷ {n} を計算して、平均値を求める。",
        ),
        Step(
            op="compute_median",
            args=[],
            result_srepr="",
            result_display=_fmt_relative(median),
            narration="データを大きさの順に並べ、中央の値（個数が偶数のときは中央に並ぶ値どうしの平均）を求める。",
        ),
        Step(
            op="compute_mode",
            args=[],
            result_srepr=srepr,
            # **この手で得たのは最頻値だけ。** 答え全体を写していたので、
            # 前の2手で出した平均値・中央値が最後にもう一度並んでいた。
            result_display=str(mode),
            narration="もっとも個数が多く現れる値を求める。",
            detail=f"{mode} が {counts[int(mode)]} 回で、いちばん多く現れる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l57.calculation Lv2: 度数分布表から階級値を用いて平均値を求める
# ---------------------------------------------------------------------------
@register_solver("math.mean_from_grouped_table")
def mean_from_grouped_table(class_start: object, class_width: object, frequencies: object) -> Solution:
    """度数分布表の各階級の階級値を用いて平均値を求める（g1_l57.calculation Lv2）。

    階級の下端・階級の幅・各階級の度数の列だけから計算する（double-solve）。答えは
    単一値の SymbolicAnswer。
    """
    start = int(str(class_start))
    width = int(str(class_width))
    freqs = [int(str(f)) for f in cast("list[object]", frequencies)]
    total = sum(freqs)
    weighted_sum = sum(_class_midpoint(start, width, i) * f for i, f in enumerate(freqs))
    mean = sympy.Rational(weighted_sum, total)
    # 平均値は小数で書けるなら小数で（教科書は「20.5点」と書く。分数のままだと
    # 「694/23」のような、平均としては読めない値になる）。
    disp = _fmt_relative(mean)
    srepr = sympy.srepr(mean)
    steps = [
        Step(
            op="weight_by_class_value",
            args=[],
            result_srepr="",
            result_display="、".join(
                fmt_measure(_class_midpoint(start, width, i) * f)
                for i, f in enumerate(freqs)
            ),
            narration="各階級の階級値に、その階級の度数をかける。",
            detail="各階級の階級値に度数をかけて、" + "、".join(
                f"{fmt_measure(_class_midpoint(start, width, i))} × {f}"
                for i, f in enumerate(freqs)
            ) + " をそれぞれ計算する。",
        ),
        Step(
            op="divide_by_total",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="それらの積をすべて足し合わせ、度数の合計でわって平均値を求める。",
            detail=(
                f"{fmt_measure(sympy.Rational(weighted_sum))} ÷ {total} を計算して、"
                f"平均値を求める。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l57.knowledge Lv2: 分布の特徴に応じて適切な代表値を判別する
# ---------------------------------------------------------------------------
@register_solver("math.judge_appropriate_representative_value")
def judge_appropriate_representative_value(has_outliers: object) -> Solution:
    """分布の特徴（外れ値の有無）から適切な代表値を判別する（g1_l57.knowledge Lv2）。

    has_outliers（bool 相当）だけから判定する（具体的な場面文は recipe が構成する
    surface であり double-solve）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    truthy = str(has_outliers).lower() in ("true", "1")
    correct = "中央値" if truthy else "平均値"
    other = "平均値" if truthy else "中央値"
    steps = [
        Step(
            op="check_outliers",
            args=[],
            result_srepr=("has_outliers" if truthy else "no_outliers"),
            result_display=("極端な値がある" if truthy else "極端な値はない"),
            narration="分布の中に、極端に大きい値や小さい値が混じっているかどうかを調べる。",
        ),
        Step(
            op="judge_appropriate_representative_value",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="極端な値に影響されにくい代表値ほど、集団の「まん中あたり」を適切に表す。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other, "最頻値"],
        fact_id="representative_value.judge_appropriate",
    )
    return Solution(answer=answer, steps=steps)
