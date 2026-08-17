"""統計的な探究（データの比較・結論づけ）の独立再計算ソルバ（§6.2 double-solve）。

solver は**データそのもの**だけから答えと steps を導く。純粋・決定論・厳密演算。

C11（g1_l58 データの比較と統計的探究プロセス）の word_problem クラスタ。

## 「理由を書いて答えよ」をどう採点可能にしたか

台帳の設問は「理由を書いて答えよ」「根拠を示して結論を述べよ」で、記述そのものを
engine が採点することはできない。そこで**結論を選択（ChoiceAnswer）として答えさせ、
根拠の組み立ては solution_steps が担う**——箱ひげ図の記述セル（g2_l57.word_problem）
で採ったのと同じ手にそろえる。

## 「どの指標で比べるかを自分で選ぶ」（Lv3）をどう成立させたか

指標を engine が固定すると台帳 desc の「自分で選び」から離れる。そこで
**どの代表値で比べても同じ結論になるデータだけを構成する**（平均値・中央値・
最頻値のすべてが同じ側を指す）。こうすると「自分で選んでよい」がそのまま成り立ち、
答えは一意に決まる。solver は3つの指標がすべて一致することを検算して、
一致しなければ例外にする（構成のミスを黙って通さない）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _ints(data: object) -> list[int]:
    return [int(str(v)) for v in list(data)]  # type: ignore[arg-type]


def _mean(vals: Sequence[int]) -> sympy.Rational:
    return sympy.Rational(sum(vals), len(vals))


def _median(vals: Sequence[int]) -> sympy.Rational:
    o = sorted(vals)
    n = len(o)
    if n % 2:
        return sympy.Integer(o[n // 2])
    return sympy.Rational(o[n // 2 - 1] + o[n // 2], 2)


def _mode(vals: Sequence[int]) -> sympy.Integer:
    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    top = max(counts.values())
    winners = sorted(k for k, c in counts.items() if c == top)
    if len(winners) != 1:
        raise ValueError(f"最頻値が一意に決まらない: {winners}")
    return sympy.Integer(winners[0])


def _range(vals: Sequence[int]) -> sympy.Integer:
    return sympy.Integer(max(vals) - min(vals))


def _steps(rows: list[tuple[str, ...]]) -> list[Step]:
    """(op, result_srepr, result_display, narration[, detail]) の列から Step を作る。"""
    return [
        Step(
            op=row[0], args=[], result_srepr=row[1], result_display=row[2],
            narration=row[3], detail=(row[4] if len(row) > 4 else ""),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# g1_l58.word_problem Lv2: 誘導あり（平均値 → 範囲 → どちらが安定しているか）
# ---------------------------------------------------------------------------
@register_solver("math.datasets_mean_pair")
def datasets_mean_pair(data_a: object, data_b: object) -> Solution:
    """2つのデータの平均値をそれぞれ求める。"""
    a, b = _ints(data_a), _ints(data_b)
    ma, mb = _mean(a), _mean(b)
    disp = f"Aの平均値 {ma}、Bの平均値 {mb}"
    srepr = sympy.srepr(sympy.Tuple(ma, mb))
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("sum_each_dataset", "", f"Aは{sum(a)}、Bは{sum(b)}",
             "それぞれのデータについて、値をすべて足し合わせる。"),
            ("divide_by_count", srepr, disp,
             "合計をデータの個数でわって、それぞれの平均値を求める。"),
        ]),
    )


@register_solver("math.datasets_range_pair")
def datasets_range_pair(data_a: object, data_b: object) -> Solution:
    """2つのデータの範囲（最大値−最小値）をそれぞれ求める。"""
    a, b = _ints(data_a), _ints(data_b)
    ra, rb = _range(a), _range(b)
    disp = f"Aの範囲 {ra}、Bの範囲 {rb}"
    srepr = sympy.srepr(sympy.Tuple(ra, rb))
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("find_max_and_min", "",
             f"Aは{min(a)}〜{max(a)}、Bは{min(b)}〜{max(b)}",
             "それぞれのデータを大きさの順に見て、最も大きい値と最も小さい値を見つける。"),
            ("subtract_min_from_max", srepr, disp,
             "最大値から最小値をひいて、それぞれの範囲を求める。"),
        ]),
    )


@register_solver("math.judge_more_stable")
def judge_more_stable(data_a: object, data_b: object) -> Solution:
    """散らばりが小さい（＝安定している）のはどちらかを判定する。

    範囲が小さいほうが安定。範囲が等しいと判定できないので例外にする
    （構成の段階で相異にすることを recipe に強制する）。
    """
    a, b = _ints(data_a), _ints(data_b)
    ra, rb = _range(a), _range(b)
    if ra == rb:
        raise ValueError("範囲が等しく、安定しているほうを決められない")
    correct = "A" if ra < rb else "B"
    other = "B" if correct == "A" else "A"
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=[other], fact_id="data_compare.more_stable"
        ),
        steps=_steps([
            ("compare_ranges", "", f"Aは{ra}、Bは{rb}",
             "求めた範囲どうしを比べ、値が小さいほうが散らばりが小さいことを確かめる。"),
            ("conclude_more_stable", correct, correct,
             "散らばりが小さいほうが、得点のばらつきが少なく安定しているといえる。"),
        ]),
    )


# ---------------------------------------------------------------------------
# g1_l58.word_problem Lv3: どの指標で比べても同じ結論になる（自分で選べる）
# ---------------------------------------------------------------------------
@register_solver("math.judge_group_by_any_statistic")
def judge_group_by_any_statistic(
    data_a: object, data_b: object, smaller_is_better: object
) -> Solution:
    """平均値・中央値・最頻値のどれで比べても同じ側になることを確かめ、結論を出す。

    `smaller_is_better` が真の場面（走る時間など）では値が小さいほうがよい。
    3つの指標が同じ側を指さない場合は例外にする＝「どの指標を選んでもよい」という
    設問の前提が崩れているので、構成をやり直させる。
    """
    a, b = _ints(data_a), _ints(data_b)
    smaller = str(smaller_is_better).lower() in ("true", "1")
    stats = [(_mean(a), _mean(b)), (_median(a), _median(b)), (_mode(a), _mode(b))]
    sides = set()
    for va, vb in stats:
        if va == vb:
            raise ValueError(f"指標の値が同じで比べられない: {va}")
        better_a = (va < vb) if smaller else (va > vb)
        sides.add("A" if better_a else "B")
    if len(sides) != 1:
        raise ValueError(f"指標によって結論が変わる（どれを選んでもよい前提が崩れる）: {stats}")
    correct = sides.pop()
    other = "B" if correct == "A" else "A"
    ma, mb = stats[0]
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=[other], fact_id="data_compare.any_statistic"
        ),
        steps=_steps([
            ("choose_statistic", "", "平均値",
             "平均値・中央値・最頻値のうち、どれで比べるかを自分で決める。"),
            ("compute_statistic_both", sympy.srepr(sympy.Tuple(ma, mb)),
             f"Aの平均値 {ma}、Bの平均値 {mb}",
             "選んだ指標の値を、二つの組それぞれについて求める。"),
            ("verify_same_conclusion", "", f"中央値でも{correct}",
             "ほかの代表値でも比べてみて、同じ側になることを確かめる。"),
            # **値の向きを言う。** 時間のように「小さいほうがよい」場面で
            # `Aの平均値 66、Bの平均値 70` から `A` と結論しても、
            # **なぜ小さいほうを選ぶのかが1行も無い**（生徒は大きいほうを選ぶ）。
            ("conclude_group", correct, correct,
             "求めた値を根拠として、どちらの組についていえるかを結論づける。",
             (f"この場面では値が小さいほうがあてはまるので、{ma} と {mb} を比べて"
              f"小さいほうの {correct} を選ぶ。")
             if smaller else
             (f"この場面では値が大きいほうがあてはまるので、{ma} と {mb} を比べて"
              f"大きいほうの {correct} を選ぶ。")),
        ]),
    )


# ---------------------------------------------------------------------------
# 「3つの選択肢から条件を満たすものを1つ選ぶ」型（g3_l58 Lv2 / g1_l58 Lv4）
#
# 選択肢は recipe が場面から組む surface で、solver が受け取るのは
# 「その選択肢が条件を満たすか」の真偽だけ（既存の judge_appropriate_survey_method /
# judge_sampling_bias と同じ規約）。solver は**条件を満たすものがちょうど1つ**である
# ことを確かめてから選ぶ——0個や2個の構成を黙って通さないための検算。
# ---------------------------------------------------------------------------
def _pick_unique(labels: object, flags: object) -> tuple[str, list[str]]:
    labs = [str(v) for v in list(labels)]  # type: ignore[arg-type]
    fl = [str(v).lower() in ("true", "1") for v in list(flags)]  # type: ignore[arg-type]
    if len(labs) != len(fl) or len(labs) < 2:
        raise ValueError("選択肢と真偽の数が合わない")
    hits = [i for i, ok in enumerate(fl) if ok]
    if len(hits) != 1:
        raise ValueError(f"条件を満たす選択肢がちょうど1つでない: {hits}")
    idx = hits[0]
    return labs[idx], [l for i, l in enumerate(labs) if i != idx]


@register_solver("math.choose_unbiased_sampling_method")
def choose_unbiased_sampling_method(labels: object, flags: object) -> Solution:
    """並んだ抽出方法のうち、偏りが生じにくいものを1つ選ぶ（g3_l58.word_problem Lv2）。"""
    correct, others = _pick_unique(labels, flags)
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=others, fact_id="sampling.choose_unbiased"
        ),
        steps=_steps([
            ("list_candidate_methods", "", "",
             "示されたそれぞれの方法について、どんな人が選ばれることになるかを考える。"),
            ("check_equal_chance", "", f"同じ機会になるのは「{correct}」だけ",
             "母集団にふくまれるすべての対象が、同じ機会で選ばれる方法になっているかを調べる。"),
            ("choose_unbiased_method", correct, correct,
             "一部の対象だけが選ばれやすい方法を除き、偏りが生じにくいものを選ぶ。"),
        ]),
    )


@register_solver("math.choose_valid_inquiry_plan")
def choose_valid_inquiry_plan(labels: object, flags: object) -> Solution:
    """並んだ調べ方のうち、問いに答えられるものを1つ選ぶ（g1_l58.word_problem Lv4）。"""
    correct, others = _pick_unique(labels, flags)
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=others, fact_id="inquiry.choose_valid_plan"
        ),
        steps=_steps([
            ("restate_question", "", "",
             "問いが何と何を比べるものなのかを、はっきりさせる。"),
            ("check_data_covers_comparison", "", f"そろうのは「{correct}」",
             "それぞれの調べ方で、比べたい相手のデータがそろうかどうかを調べる。"),
            ("check_sampling_is_fair", "", f"偏りが入らないのは「{correct}」",
             "集め方に偏りが入っていないか、一部の人だけに聞いていないかを調べる。"),
            ("choose_valid_plan", correct, correct,
             "比べる相手がそろい、偏りも入らない調べ方を選ぶ。"),
        ]),
    )


__all__ = [
    "datasets_mean_pair",
    "datasets_range_pair",
    "judge_more_stable",
    "judge_group_by_any_statistic",
    "choose_unbiased_sampling_method",
    "choose_valid_inquiry_plan",
]
