"""確率まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（試行の構造・条件）から答えと steps を導く（recipe の
構成値は見ない）。全事象は itertools で solver 自身が列挙し直す（recipe が数え上げた
「該当数」をそのまま信用しない＝真の double-solve）。純粋・決定論。乱数は引かない。

C12（確率）クラスタの非 visual セル群（g1_l59・g2_l51〜54）:
  - `math.relative_frequency`: 起こった回数÷試行回数（g1_l59.calculation Lv1・
    g2_l51.find_value Lv2）
  - `math.probability_single_die`: 1個のさいころ・硬貨の条件付き確率（g2_l51.find_value
    Lv1・g2_l52.find_value Lv1）
  - `math.probability_two_dice`: 2個のさいころの和・積条件（g2_l52.find_value Lv3）
  - `math.probability_ordered_selection`: n人から役職を順に選ぶ（順列・g2_l53.find_value
    Lv2）
  - `math.probability_combination_selection`: 玉を同時に取り出す（組合せ・g2_l53.find_value
    Lv3）
  - `math.probability_complement`: 余事象 1-p（g2_l54.find_value Lv2）
  - `math.probability_at_least_one`: 独立試行で少なくとも1回起こる確率（g2_l54.find_value
    Lv3）

narration には数字を書かない（"0"は"=0"の whitelist のみ許可）。
"""
from __future__ import annotations

import itertools
from typing import cast

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _fmt_ratio(p: sympy.Rational) -> str:
    return str(p)


# ---------------------------------------------------------------------------
# g1_l59.calculation Lv1 / g2_l51.find_value Lv2: 相対度数 = 起こった回数 ÷ 試行回数
# ---------------------------------------------------------------------------
@register_solver("math.relative_frequency")
def relative_frequency(occurred: object, total: object) -> Solution:
    """起こった回数 ÷ 試行回数 で相対度数（確率の推定値）を求める。

    2つの整数だけから既約分数を計算する（double-solve）。narration に数字は書かない。
    """
    o = sympy.Integer(int(str(occurred)))
    t = sympy.Integer(int(str(total)))
    if t == 0:
        raise ValueError("試行回数が0では相対度数が定まらない")
    p = sympy.Rational(o, t)
    steps = [
        Step(
            op="divide_occurred_by_total",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=_fmt_ratio(p),
            narration="ことがらが起こった回数を、試行の総回数でわる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l51.find_value Lv1 / g2_l52.find_value Lv1: 1個のさいころ・硬貨の条件付き確率
# ---------------------------------------------------------------------------
_SINGLE_SPACES: dict[str, list[int | str]] = {
    "die6": [1, 2, 3, 4, 5, 6],
    "coin2": ["表", "裏"],
}

_SINGLE_STEPS: dict[str, list[str]] = {
    "die6": ["enumerate_all_outcomes", "count_favorable", "compute_probability"],
    "coin2": ["enumerate_all_outcomes", "count_favorable", "compute_probability"],
}

_SINGLE_NARRATION: dict[str, str] = {
    "enumerate_all_outcomes": "起こりうるすべての場合を数え上げる。",
    "count_favorable": "そのうち、求める条件にあてはまる場合の数を数える。",
    "compute_probability": "条件にあてはまる場合の数を、すべての場合の数でわる。",
}

_SINGLE_PHRASE: dict[str, str] = {
    "enumerate_all_outcomes": "すべての場合を数え上げる",
    "count_favorable": "条件にあてはまる場合を数える",
}


def _single_favorable(space: list[int | str], condition: str, target: object) -> list[int | str]:
    if condition == "even":
        return [v for v in space if isinstance(v, int) and v % 2 == 0]
    if condition == "odd":
        return [v for v in space if isinstance(v, int) and v % 2 == 1]
    if condition == "at_least":
        return [v for v in space if isinstance(v, int) and v >= int(str(target))]
    if condition == "at_most":
        return [v for v in space if isinstance(v, int) and v <= int(str(target))]
    if condition == "equals":
        return [v for v in space if v == target]
    if condition == "multiple_of":
        return [v for v in space if isinstance(v, int) and v % int(str(target)) == 0]
    raise ValueError(f"未知の condition: {condition!r}")


def _resolve_single_space(space_name: str, size: int) -> list[int | str]:
    """space_name（"die6"／"coin2"／"cards_n"）と size（cards_n のときの上限 N）から

    実際の全事象リストを組む。die6/coin2 は固定サイズ（size は無視）、cards_n は
    1〜size の整数（size は N＝カード枚数。数え上げの自由度をさいころの6面に限定
    せず広げるための一般化＝「1〜N の番号カードから1枚引く」・鉄則②）。
    """
    if space_name == "cards_n":
        return list(range(1, size + 1))
    return _SINGLE_SPACES[space_name]


@register_solver("math.probability_single_die")
def probability_single_die(space_name: object, condition: object, target: object, size: object = 0) -> Solution:
    """1個のさいころ・硬貨・番号カードで条件を満たす確率を求める（g2_l51/l52.find_value）。

    space_name（"die6"／"coin2"／"cards_n"）・condition（判定条件の種類）・target（条件の値）・
    size（"cards_n"のときのカード枚数N。die6/coin2では無視）だけから、全事象を itertools で
    列挙し直し、該当数÷全体数を計算する（double-solve）。
    """
    sn = str(space_name)
    if sn not in ("die6", "coin2", "cards_n"):
        raise ValueError(f"未知の space_name: {sn!r}")
    space = _resolve_single_space(sn, int(str(size)))
    favorable = _single_favorable(space, str(condition), target)
    p = sympy.Rational(len(favorable), len(space))
    ops = _SINGLE_STEPS.get(sn, _SINGLE_STEPS["die6"])
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(ops) - 1 else "",
            result_display=_fmt_ratio(p) if i == len(ops) - 1 else _SINGLE_PHRASE.get(op, ""),
            narration=_SINGLE_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l52.find_value Lv3: 2個のさいころの和・積条件
# ---------------------------------------------------------------------------
_TWO_DICE_STEPS = ["enumerate_all_pairs", "count_favorable_pairs", "compute_probability"]

_TWO_DICE_NARRATION: dict[str, str] = {
    "enumerate_all_pairs": "大小2個のさいころの目の組合せを、表などを使ってすべて数え上げる。",
    "count_favorable_pairs": "そのうち、求める条件にあてはまる組合せの数を数える。",
    "compute_probability": "条件にあてはまる組合せの数を、すべての組合せの数でわる。",
}

_TWO_DICE_PHRASE: dict[str, str] = {
    "enumerate_all_pairs": "すべての目の組合せを数え上げる",
    "count_favorable_pairs": "条件にあてはまる組合せを数える",
}


@register_solver("math.probability_two_dice")
def probability_two_dice(faces: object, condition: object, target: object) -> Solution:
    """大小2個のさいころの目の和・積が条件を満たす確率を求める（g2_l52.find_value Lv3）。

    さいころの面数 faces・condition（"sum_equals"／"product_at_least"等）・target だけから
    全 faces×faces 通りを itertools で列挙し直し、該当数÷全体数を計算する（double-solve）。
    """
    f = int(str(faces))
    pairs = list(itertools.product(range(1, f + 1), range(1, f + 1)))
    cond = str(condition)
    t = int(str(target))
    if cond == "sum_equals":
        favorable = [(a, b) for a, b in pairs if a + b == t]
    elif cond == "product_at_least":
        favorable = [(a, b) for a, b in pairs if a * b >= t]
    elif cond == "product_equals":
        favorable = [(a, b) for a, b in pairs if a * b == t]
    elif cond == "sum_at_least":
        favorable = [(a, b) for a, b in pairs if a + b >= t]
    else:
        raise ValueError(f"未知の condition: {cond!r}")
    p = sympy.Rational(len(favorable), len(pairs))
    ops = _TWO_DICE_STEPS
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(ops) - 1 else "",
            result_display=_fmt_ratio(p) if i == len(ops) - 1 else _TWO_DICE_PHRASE.get(op, ""),
            narration=_TWO_DICE_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l53.find_value Lv2: n人から役職を順に選ぶ（順列）
# ---------------------------------------------------------------------------
_ORDERED_STEPS = ["enumerate_all_orderings", "count_favorable_orderings", "compute_probability"]

_ORDERED_NARRATION: dict[str, str] = {
    "enumerate_all_orderings": "役職の決め方を、樹形図などを使ってすべて数え上げる。",
    "count_favorable_orderings": "そのうち、求める人がその役職に選ばれる決め方の数を数える。",
    "compute_probability": "条件にあてはまる決め方の数を、すべての決め方の数でわる。",
}

_ORDERED_PHRASE: dict[str, str] = {
    "enumerate_all_orderings": "すべての決め方を数え上げる",
    "count_favorable_orderings": "条件にあてはまる決め方を数える",
}


@register_solver("math.probability_ordered_selection")
def probability_ordered_selection(n: object, r: object, target_index: object) -> Solution:
    """n人からr人を順に選ぶとき、特定の1人が特定の役職(位置)に選ばれる確率を求める

    （g2_l53.find_value Lv2）。n・r・target_index（0-indexed の役職位置。対象の人は
    人物リストの先頭=index0とみなす）だけから、全順列を itertools で列挙し直し、
    該当数÷全体数を計算する（double-solve）。
    """
    n_v, r_v, idx = int(str(n)), int(str(r)), int(str(target_index))
    people = list(range(n_v))
    perms = list(itertools.permutations(people, r_v))
    favorable = [perm for perm in perms if perm[idx] == 0]  # 人物0が対象
    p = sympy.Rational(len(favorable), len(perms))
    ops = _ORDERED_STEPS
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(ops) - 1 else "",
            result_display=_fmt_ratio(p) if i == len(ops) - 1 else _ORDERED_PHRASE.get(op, ""),
            narration=_ORDERED_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l53.find_value Lv3: 玉を同時に取り出す（組合せ。色ごとの個数から該当確率を求める）
# ---------------------------------------------------------------------------
_COMBO_STEPS = ["enumerate_all_combinations", "count_favorable_combinations", "compute_probability"]

_COMBO_NARRATION: dict[str, str] = {
    "enumerate_all_combinations": "玉を区別して、取り出し方をすべて数え上げる。",
    "count_favorable_combinations": "そのうち、求める条件にあてはまる取り出し方の数を数える。",
    "compute_probability": "条件にあてはまる取り出し方の数を、すべての取り出し方の数でわる。",
}

_COMBO_PHRASE: dict[str, str] = {
    "enumerate_all_combinations": "すべての取り出し方を数え上げる",
    "count_favorable_combinations": "条件にあてはまる取り出し方を数える",
}


@register_solver("math.probability_combination_selection")
def probability_combination_selection(counts: object, r: object, target_color: object) -> Solution:
    """色ごとの個数 counts（例 {"赤":2,"白":2}）の玉から r 個を同時に取り出すとき、

    取り出した r 個がすべて target_color である確率を求める（g2_l53.find_value Lv3）。
    区別した玉のラベルから全組合せを itertools で列挙し直し、該当数÷全体数を計算する
    （double-solve）。
    """
    counts_d = cast("dict[str, object]", counts)
    r_v = int(str(r))
    balls: list[str] = []
    for color, n in counts_d.items():
        for i in range(int(str(n))):
            balls.append(f"{color}{i}")
    combos = list(itertools.combinations(balls, r_v))
    tc = str(target_color)
    favorable = [c for c in combos if all(ball.rstrip("0123456789") == tc for ball in c)]
    p = sympy.Rational(len(favorable), len(combos))
    ops = _COMBO_STEPS
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(ops) - 1 else "",
            result_display=_fmt_ratio(p) if i == len(ops) - 1 else _COMBO_PHRASE.get(op, ""),
            narration=_COMBO_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l54.find_value Lv2: 余事象 1-p
# ---------------------------------------------------------------------------
@register_solver("math.probability_complement")
def probability_complement(p_num: object, p_den: object) -> Solution:
    """ある事象の起こる確率 p_num/p_den から、起こらない確率 1-p を求める

    （g2_l54.find_value Lv2）。確率の値だけから独立に再計算する（double-solve）。
    """
    p = sympy.Rational(int(str(p_num)), int(str(p_den)))
    if not (0 <= p <= 1):
        raise ValueError("確率は0以上1以下であること")
    q = 1 - p
    steps = [
        Step(
            op="subtract_from_one",
            args=[],
            result_srepr=sympy.srepr(q),
            result_display=_fmt_ratio(q),
            narration="1から、もとのことがらの起こる確率をひく。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(q), display=_fmt_ratio(q))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l54.find_value Lv3: 独立試行で少なくとも1回起こる確率（余事象で工夫）
# ---------------------------------------------------------------------------
_AT_LEAST_ONE_STEPS = [
    "compute_single_trial_complement", "compute_complement_probability", "subtract_from_one",
]

_AT_LEAST_ONE_NARRATION: dict[str, str] = {
    "compute_single_trial_complement": "1回の試行で条件が起こらない場合の数を数え、その確率を求める。",
    "compute_complement_probability": "独立な試行をくり返すので、すべての回で条件が起こらない確率は"
    "1回分の確率を試行回数だけかけ合わせたものになる。",
    "subtract_from_one": "1から、その余事象の確率をひいて、少なくとも1回起こる確率を求める。",
}

_AT_LEAST_ONE_PHRASE: dict[str, str] = {
    "compute_single_trial_complement": "1回分の余事象の確率を求める",
    "compute_complement_probability": "余事象の確率を求める",
}


@register_solver("math.probability_at_least_one")
def probability_at_least_one(space_size: object, favorable_size: object, trials: object) -> Solution:
    """1回の試行で「起こる」場合の数 favorable_size・全事象数 space_size・独立な試行回数

    trials だけから、少なくとも1回起こる確率を余事象で求める（g2_l54.find_value Lv3）。
    1回の試行で「起こらない」事象数（space_size - favorable_size）を itertools で小さな
    1試行分の空間から数え直し、独立試行の確率は掛け算で合成できることから
    q=((space_size-favorable_size)/space_size)^trials を計算し、1-q を答えとする
    （double-solve。space_size^trials の全列挙はしない＝計算量が試行回数に対して
    指数的に増えるのを避ける設計）。
    """
    n_v, f_v, k_v = int(str(space_size)), int(str(favorable_size)), int(str(trials))
    if not (0 < f_v < n_v):
        raise ValueError("favorable_size は 0 より大きく space_size 未満であること")
    single_trial_outcomes = list(range(n_v))
    not_favorable_outcomes = [o for o in single_trial_outcomes if o >= f_v]  # 規約: index0..f_v-1が起こる事象
    q_single = sympy.Rational(len(not_favorable_outcomes), n_v)
    q = q_single ** k_v
    p = 1 - q
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(_AT_LEAST_ONE_STEPS) - 1 else "",
            result_display=(
                _fmt_ratio(p) if i == len(_AT_LEAST_ONE_STEPS) - 1 else _AT_LEAST_ONE_PHRASE.get(op, "")
            ),
            narration=_AT_LEAST_ONE_NARRATION[op],
        )
        for i, op in enumerate(_AT_LEAST_ONE_STEPS)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l51.knowledge Lv2 / g1_l59.knowledge Lv2: 判別・解釈型（verify）
# ---------------------------------------------------------------------------
@register_solver("math.judge_equally_likely")
def judge_equally_likely(is_equally_likely: object) -> Solution:
    """場面が「同様に確からしい」かどうかを判別する（g2_l51.knowledge Lv2）。

    is_equally_likely（bool 相当）だけから判定する（具体的な場面文は recipe が構成する
    surface であり double-solve）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    truthy = str(is_equally_likely).lower() in ("true", "1")
    correct = "同様に確からしいといえる" if truthy else "同様に確からしいとはいえない"
    other = "同様に確からしいとはいえない" if truthy else "同様に確からしいといえる"
    steps = [
        Step(
            op="check_symmetry",
            args=[],
            result_srepr=("equally_likely" if truthy else "not_equally_likely"),
            result_display="それぞれの結果の起こりやすさに違いがあるかを調べる",
            narration="場面に登場するそれぞれの結果の起こりやすさに、違いがあるかどうかを調べる。",
        ),
        Step(
            op="judge_equally_likely",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="どの結果も同じ程度に起こると考えられるなら同様に確からしいといえ、そうでなければいえない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="probability.judge_equally_likely")
    return Solution(answer=answer, steps=steps)


@register_solver("math.interpret_relative_frequency_limit")
def interpret_relative_frequency_limit(dummy: object) -> Solution:
    """試行回数を増やすと相対度数が近づく値が何を表すかを説明する（g1_l59.knowledge Lv2）。

    説明対象は固定（相対度数の極限＝確率の意味）なので引数は使わず一意に定まる
    （double-solve・恒真）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    correct = "その事象の起こる確率"
    steps = [
        Step(
            op="recall_relative_frequency_limit",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="試行回数を増やしたときに相対度数が近づく値が、何を表すかを思い出す。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct,
        distractors=["起こった回数の合計", "試行回数そのもの", "起こらなかった回数の割合"],
        fact_id="probability.relative_frequency_limit",
    )
    return Solution(answer=answer, steps=steps)


__all__ = [
    "relative_frequency",
    "probability_single_die",
    "probability_two_dice",
    "probability_ordered_selection",
    "probability_combination_selection",
    "probability_complement",
    "probability_at_least_one",
    "judge_equally_likely",
    "interpret_relative_frequency_limit",
]
