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
  - `math.probability_coin_toss` / `math.count_coin_toss_outcomes`: 硬貨 n 枚同時
    （g2_l52.word_problem Lv2）
  - `math.probability_two_digit_from_cards` / `math.count_two_digit_from_cards`:
    数字カードを並べて2けたの整数（g2_l53.word_problem Lv2）

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


def _fmt_relative_frequency(p: sympy.Rational) -> str:
    """相対度数の表示。**割り切れるなら小数**、そうでなければ分数。

    相対度数（確率の推定値）は小数で答えるのが教材の作法で、「1292回投げて726回 →
    363/646」は約分しても意味を持たない。recipe 側で割り切れる組だけを引くので、
    ここは実際には常に小数になる（保険として分数も残す）。
    """
    q = int(p.q)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    if q != 1:
        return str(p)  # 割り切れない（＝小数で書けない）ので分数のまま
    digits = 0
    r = sympy.Rational(p)
    while r.q != 1:
        r *= 10
        digits += 1
    return f"{float(p):.{digits}f}" if digits else str(int(p))


# ---------------------------------------------------------------------------
# g1_l59.calculation Lv1 / g2_l51.find_value Lv2: 相対度数 = 起こった回数 ÷ 試行回数
# ---------------------------------------------------------------------------
@register_solver("math.relative_frequency")
def relative_frequency(
    occurred: object, total: object, as_decimal: object = True
) -> Solution:
    """起こった回数 ÷ 試行回数 で相対度数（確率の推定値）を求める。

    2つの整数だけから既約分数を計算する（double-solve）。narration に数字は書かない。
    `as_decimal=False` は表示を分数のままにする（**確率は分数で答えるのが教材の作法**で、
    小数で答えるのは相対度数のほう。同じ割り算でも書き方の作法が違う）。
    """
    o = sympy.Integer(int(str(occurred)))
    t = sympy.Integer(int(str(total)))
    if t == 0:
        raise ValueError("試行回数が0では相対度数が定まらない")
    p = sympy.Rational(o, t)
    disp = _fmt_relative_frequency(p) if bool(as_decimal) else _fmt_ratio(p)
    steps = [
        Step(
            op="divide_occurred_by_total",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=disp,
            # **「試行の総回数」と言えるのは実験のときだけ。** この solver は
            # 度数分布（100人のうち27人）と標本調査（400人のうち220人）からも
            # 呼ばれていて、そこに「試行」は無い（相対度数の定義は
            # 「その階級の度数 ÷ 度数の合計」）。3つの場面すべてで正しい言い方にする。
            #
            # **detail は narration を置きかえるので、目的（何を求めているか）を
            # 落とさないこと。** 最初 `27 を 100 でわる。` とだけ書いたら、
            # 1手のセルの解説が「まず、27 を 100 でわる。（0.27）」になり、
            # **何を求めた数なのかが1文字も無くなった**（走査の「解説が1文しかない」で出た）。
            narration=(
                "注目していることがらの数を、全体の数でわって、相対度数を求める。"
                if bool(as_decimal)
                else "あてはまる場合の数を、起こりうる場合の数でわって、確率を求める。"
            ),
            detail=(
                f"注目していることがらの数 {o} を、全体の数 {t} でわって、相対度数を求める。"
                if bool(as_decimal)
                else f"あてはまる場合の数 {o} を、起こりうる場合の数 {t} でわって、確率を求める。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=disp)
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



# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**数えた結果**（面③）。以前は「すべての場合を数え上げる」の
# ような指示の言い直しが入っていた。数え上げの問題では、**何通りあったか**こそが
# その手で得たもの。`narration` は触らない（ヒントは narration しか見ない）。
# ---------------------------------------------------------------------------
def _count_display(op: str, total: int, favorable: int) -> str:
    """数え上げの手の括弧（全部で何通り／あてはまるのは何通り）。"""
    if op.startswith("enumerate"):
        return f"全部で{total}通り"
    if op.startswith("count"):
        return f"あてはまるのは{favorable}通り"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


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
            result_display=_fmt_ratio(p) if i == len(ops) - 1
            else _count_display(op, len(space), len(favorable)),
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
    # **「大小」と決めつけない。** 問題文は「青いさいころと黄色いさいころ」の
    # ように色で区別することがあり、そのとき解説だけ「大小2個のさいころ」と
    # 呼ぶと問題文と食い違う。solver は色を知らないので中立に書く。
    "enumerate_all_pairs": "2個のさいころの目の組合せを、表などを使ってすべて数え上げる。",
    "count_favorable_pairs": "そのうち、求める条件にあてはまる組合せの数を数える。",
    "compute_probability": "条件にあてはまる組合せの数を、すべての組合せの数でわる。",
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
    elif cond == "product_parity":
        # target は 0=偶数 / 1=奇数（exam_l5.word_problem Lv3 の「積が偶数」）。
        favorable = [(a, b) for a, b in pairs if (a * b) % 2 == t]
    elif cond == "sum_parity":
        favorable = [(a, b) for a, b in pairs if (a + b) % 2 == t]
    # 以下は6面に戻したぶんの条件を、**教科書にある問い方**で足したもの
    # （面数を広げて組合せを稼ぐのはやめた。D-13 と同じ理由）。
    elif cond == "sum_at_most":
        favorable = [(a, b) for a, b in pairs if a + b <= t]
    elif cond == "diff_equals":
        favorable = [(a, b) for a, b in pairs if abs(a - b) == t]
    elif cond == "sum_multiple_of":
        favorable = [(a, b) for a, b in pairs if (a + b) % t == 0]
    elif cond == "at_least_one_equals":
        favorable = [(a, b) for a, b in pairs if t in (a, b)]
    elif cond == "same_faces":
        favorable = [(a, b) for a, b in pairs if a == b]
    else:
        raise ValueError(f"未知の condition: {cond!r}")
    p = sympy.Rational(len(favorable), len(pairs))
    ops = _TWO_DICE_STEPS
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(ops) - 1 else "",
            result_display=_fmt_ratio(p) if i == len(ops) - 1
            else _count_display(op, len(pairs), len(favorable)),
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
            result_display=_fmt_ratio(p) if i == len(ops) - 1
            else _count_display(op, len(perms), len(favorable)),
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
            result_display=_fmt_ratio(p) if i == len(ops) - 1
            else _count_display(op, len(combos), len(favorable)),
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

def _at_least_one_display(op: str, q_single, q) -> str:
    """余事象で解く手の括弧（この手で得た確率）。"""
    if op == "compute_single_trial_complement":
        return _fmt_ratio(q_single)
    if op == "compute_complement_probability":
        return _fmt_ratio(q)
    raise ValueError(f"途中の表示を組めない op: {op!r}")


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
                _fmt_ratio(p) if i == len(_AT_LEAST_ONE_STEPS) - 1
                else _at_least_one_display(op, q_single, q)
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
            result_display=("違いはない" if truthy else "違いがある"),
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


# ---------------------------------------------------------------------------
# g2_l52.word_problem Lv2: 硬貨を n 枚同時に投げて表がちょうど k 枚
# ---------------------------------------------------------------------------
_COIN_STEPS = ["enumerate_all_outcomes", "count_favorable_outcomes", "compute_probability"]

_COIN_NARRATION: dict[str, str] = {
    "enumerate_all_outcomes": "硬貨を区別して、表と裏の出方をすべて書き出す。",
    "count_favorable_outcomes": "書き出した出方のうち、条件にあてはまるものの数を数える。",
    "compute_probability": "条件にあてはまる出方の数を、すべての出方の数でわる。",
}



@register_solver("math.probability_coin_toss")
def probability_coin_toss(coins: object, count: object, face: object) -> Solution:
    """硬貨を coins 枚同時に投げて、face（表／裏）がちょうど count 枚出る確率を求める。

    硬貨を区別した 2^coins 通りの出方を itertools で列挙し直し、指定された面の枚数が
    count に等しいものを数える（recipe が数え上げた値は見ない＝真の double-solve）。
    「同時に投げる」場合も硬貨は区別して数えるのが確率の規約で、区別しないと
    同様に確からしくなくなる。
    """
    n_v, k_v, face_v = int(str(coins)), int(str(count)), str(face)
    if n_v <= 0:
        raise ValueError("硬貨の枚数は1以上であること")
    if not (0 <= k_v <= n_v):
        raise ValueError("指定した面の枚数は0以上、硬貨の枚数以下であること")
    if face_v not in ("表", "裏"):
        raise ValueError("face は 表 か 裏 であること")
    outcomes = list(itertools.product(("表", "裏"), repeat=n_v))
    favorable = [o for o in outcomes if o.count(face_v) == k_v]
    p = sympy.Rational(len(favorable), len(outcomes))
    steps = [
        Step(
            op=op, args=[],
            result_srepr=sympy.srepr(p) if i == len(_COIN_STEPS) - 1 else "",
            result_display=(
                _fmt_ratio(p) if i == len(_COIN_STEPS) - 1
                else _count_display(op, len(outcomes), len(favorable))
            ),
            narration=_COIN_NARRATION[op],
        )
        for i, op in enumerate(_COIN_STEPS)
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


@register_solver("math.count_coin_toss_outcomes")
def count_coin_toss_outcomes(coins: object) -> Solution:
    """硬貨を coins 枚同時に投げるときの、表と裏の出方の総数を求める（場合の数）。

    `probability_coin_toss` と同じ列挙を使うが、答えは確率ではなく通り数。
    台帳の「樹形図にすべて表せ」は frame が作図小問を持てないので「全部で何通りか」に
    置き換えて出題する（理由は family の source_desc に明記）。
    """
    n_v = int(str(coins))
    if n_v <= 0:
        raise ValueError("硬貨の枚数は1以上であること")
    total = len(list(itertools.product(("表", "裏"), repeat=n_v)))
    steps = [
        Step(
            op="enumerate_all_outcomes",
            args=[],
            result_srepr=sympy.srepr(sympy.Integer(total)),
            result_display=f"{total}通り",
            narration=(
                "硬貨を区別して、1枚ごとに表と裏の2通りがあることを枝分かれで書き出し、"
                "出方の総数を数える。"
            ),
        ),
    ]
    answer = SymbolicAnswer(
        srepr=sympy.srepr(sympy.Integer(total)), display=f"{total}通り"
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l53.word_problem Lv2: 数字カードを並べて2けたの整数をつくる
# ---------------------------------------------------------------------------
# 条件は**小問文に出る日本語のまま**を鍵にする。recipe は params["numbers"] に置いた
# 値がそのまま問題文に現れることを契約にしており（word_problem の不変条件）、
# "even" のような内部名を置くとその契約を破るため。
# 「3の倍数」のような数字を含む条件語は入れない: 条件語は小問文（ask）側にしか
# 出ず、G-Q5t の whitelist は given しか見ないので、答えの分母・分子と衝突して
# 偽陽性になる（既知の罠）。
_TWO_DIGIT_CONDITIONS: dict[str, str] = {
    # 条件語（小問文にそのまま出る） → narration に使う言い回し
    "偶数": "一の位が偶数になっているもの",
    "奇数": "一の位が奇数になっているもの",
}


def _two_digit_numbers(digits: list[int]) -> list[int]:
    """カードから2枚を順に引いて並べてできる2けたの整数をすべて列挙する。"""
    return [10 * a + b for a, b in itertools.permutations(digits, 2)]


def _satisfies_two_digit_condition(value: int, condition: str) -> bool:
    if condition == "偶数":
        return value % 2 == 0
    if condition == "奇数":
        return value % 2 == 1
    raise ValueError(f"未知の条件: {condition!r}")


@register_solver("math.probability_two_digit_from_cards")
def probability_two_digit_from_cards(digits: object, condition: object) -> Solution:
    """数字カードから2枚を続けて引いて並べた2けたの整数が、条件を満たす確率を求める。

    カードの数字の並べ方（順列）を itertools で列挙し直して2けたの整数をつくり、
    条件にあてはまる個数を数える（double-solve）。カードは1枚ずつ数字が異なる前提で、
    どのカードも同じ確からしさで引かれる。
    """
    ds = [int(str(d)) for d in cast("list[object]", digits)]
    cond = str(condition)
    numbers = _two_digit_numbers(ds)
    favorable = [v for v in numbers if _satisfies_two_digit_condition(v, cond)]
    p = sympy.Rational(len(favorable), len(numbers))
    phrase = _TWO_DIGIT_CONDITIONS[cond]
    steps = [
        Step(
            op="enumerate_all_two_digit_numbers",
            args=[],
            result_srepr="",
            result_display=f"{len(numbers)}通り",
            narration="十の位と一の位に置くカードの選び方を枝分かれで書き出し、できる整数をすべて数え上げる。",
        ),
        Step(
            op="count_favorable_numbers",
            args=[],
            result_srepr="",
            result_display=f"{len(favorable)}通り",
            narration=f"書き出した整数のうち、{phrase}の個数を数える。",
        ),
        Step(
            op="compute_probability",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=_fmt_ratio(p),
            narration="条件にあてはまる整数の個数を、できる整数の総数でわる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(p), display=_fmt_ratio(p))
    return Solution(answer=answer, steps=steps)


@register_solver("math.count_two_digit_from_cards")
def count_two_digit_from_cards(digits: object) -> Solution:
    """数字カードから2枚を続けて引いて並べてできる2けたの整数の総数を求める（場合の数）。

    台帳の「樹形図にすべて書き出せ」は frame が作図小問を持てないので「全部で何通りか」
    に置き換えて出題する（理由は family の source_desc に明記）。
    """
    ds = [int(str(d)) for d in cast("list[object]", digits)]
    total = len(_two_digit_numbers(ds))
    steps = [
        Step(
            op="enumerate_all_two_digit_numbers",
            args=[],
            result_srepr=sympy.srepr(sympy.Integer(total)),
            result_display=f"{total}通り",
            narration=(
                "十の位に置くカードの選び方それぞれについて、"
                "残ったカードから一の位を選ぶ選び方を枝分かれで書き出し、総数を数える。"
            ),
        ),
    ]
    answer = SymbolicAnswer(
        srepr=sympy.srepr(sympy.Integer(total)), display=f"{total}通り"
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
    "probability_coin_toss",
    "count_coin_toss_outcomes",
    "probability_two_digit_from_cards",
    "count_two_digit_from_cards",
    "judge_equally_likely",
    "interpret_relative_frequency_limit",
]


# ---------------------------------------------------------------------------
# exam_l5（入試融合・確率）— C13
# ---------------------------------------------------------------------------
_COUNT_PAIRS_STEPS = ["count_outcomes_of_each_die", "multiply_outcome_counts"]

_COUNT_PAIRS_NARRATION: dict[str, str] = {
    "count_outcomes_of_each_die": "一つのさいころで出る目が何通りあるかを数える。",
    "multiply_outcome_counts": "どちらのさいころも目の数は同じだけあるので、樹形図や表で整理すると、"
                               "組合せの総数はその積になる。",
}


@register_solver("math.count_two_dice_outcomes")
def count_two_dice_outcomes(faces: object) -> Solution:
    """大小2個のさいころで出る目の組合せの総数を求める（exam_l5.word_problem Lv3 の (1)）。

    「樹形図または表で整理せよ」という設問を採点可能にするため、**整理した結果である
    総数**を答えさせる（図そのものは engine が採点できない。組み立ては
    solution_steps が担う——記述型を選択・数値に落とす既存の手と同じ）。
    総数は列挙して数え直す（掛け算の結果を主張せず数える）。
    """
    f = int(str(faces))
    if f < 2:
        raise ValueError("さいころの面数は 2 以上であること")
    total = len(list(itertools.product(range(1, f + 1), range(1, f + 1))))
    if total != f * f:
        raise ValueError("列挙した総数が面数の積に一致しない")
    srepr = sympy.srepr(sympy.Integer(total))
    disp = f"{total}通り"
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_COUNT_PAIRS_STEPS) - 1 else "",
            result_display=disp if i == len(_COUNT_PAIRS_STEPS) - 1 else f"{f}通り",
            narration=_COUNT_PAIRS_NARRATION[op],
        )
        for i, op in enumerate(_COUNT_PAIRS_STEPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


_AT_LEAST_ONE_DRAW_STEPS = [
    "identify_complement_event",
    "count_complement_combinations",
    "compute_complement_probability",
    "subtract_from_one",
]

_AT_LEAST_ONE_DRAW_NARRATION: dict[str, str] = {
    # **この場面は「取り出す」。** 「一つも入らない」と書いていたので、
    # 袋に入れる場面のように読めた（問題文はどれも「取り出す」）。
    "identify_complement_event": "「少なくとも1つ」を直接数えると場合分けが増えるので、"
                                 "その反対の「1つも取り出されない」場合を考える。",
    # 題材は玉に限らない（カード・おはじき等）ので、narration は品名に触れない。
    "count_complement_combinations": "対象でないものだけを取り出す組合せが何通りあるかを数える。",
    "compute_complement_probability": "その数を、すべての取り出し方の数でわって、"
                                      "反対の場合の確率を求める。",
    "subtract_from_one": "全体の確率から反対の場合の確率をひいて、求める確率とする。",
}

def _at_least_one_draw_display(op: str, total: int, none_target: int, q) -> str:
    """余事象で数える手の括弧（この手で得たもの）。"""
    if op == "identify_complement_event":
        return "対象の色が1つも取り出されない場合"
    if op == "count_complement_combinations":
        return f"あてはまるのは {none_target}通り、全部で {total}通り"
    if op == "compute_complement_probability":
        return _fmt_ratio(q)
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.probability_at_least_one_by_complement")
def probability_at_least_one_by_complement(
    n_target: object, n_other: object, take: object
) -> Solution:
    """袋から同時に取り出したとき、少なくとも1個が対象の色である確率（exam_l5.word_problem Lv4）。

    既存の `math.probability_at_least_one` は**独立な試行を繰り返す**場面（もとに戻す）の
    ものなので、同時に取り出す場面（もとに戻さない）には使えない。ここは玉を区別した
    ラベルから全組合せを itertools で列挙し直し、余事象（対象の色が1個も入らない）の
    数を数えて 1 から引く（double-solve）。
    """
    a, b, k = int(str(n_target)), int(str(n_other)), int(str(take))
    if a < 1 or b < 1 or not (1 <= k <= a + b):
        raise ValueError("対象・それ以外は1個以上、取り出す個数は総数以下であること")
    if k > b:
        raise ValueError("余事象が空になり「少なくとも一つ」が必ず起こる（問いにならない）")
    balls = [f"t{i}" for i in range(a)] + [f"o{i}" for i in range(b)]
    combos = list(itertools.combinations(balls, k))
    none_target = [c for c in combos if all(x.startswith("o") for x in c)]
    q = sympy.Rational(len(none_target), len(combos))
    p = 1 - q
    if not (0 < p < 1):
        raise ValueError(f"確率が 0 または 1 に潰れている: {p}")
    srepr = sympy.srepr(p)
    disp = _fmt_ratio(p)
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_AT_LEAST_ONE_DRAW_STEPS) - 1 else "",
            result_display=(
                disp if i == len(_AT_LEAST_ONE_DRAW_STEPS) - 1
                else _at_least_one_draw_display(op, len(combos), len(none_target), q)
            ),
            narration=_AT_LEAST_ONE_DRAW_NARRATION[op],
        )
        for i, op in enumerate(_AT_LEAST_ONE_DRAW_STEPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
