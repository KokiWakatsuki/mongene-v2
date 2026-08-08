"""確率の利用（form=word_problem・C14 の確率クラスタ）。

g2_l51〜l54 の非 visual find_value 群（`engine/packs/math/recipes/probability.py`）が
既に持っている solver 群にそのまま委ねる＝**新 solver ゼロ**。文章題としての違いは
「場面文＋(誘導なら)複数小問」という骨格だけで、数学（数え上げ・包除・余事象）は
既存 solver がやる。

## 1つの recipe で6セルを賄う設計

`word_problem_linear.py`/`word_problem_system.py` と同じ償却。params の
`scenario_kind` が

  1. 場面の数値を answer-first で引く関数（`_SCENE_BUILDERS`）
  2. その数値から solver を呼んで解く関数（`SOLVE_BUILDERS`）

の対を選ぶ。`SOLVE_BUILDERS` は recipe と checker が**同じ関数を呼ぶ**（word_problem_linear
の `solve_scene` と同じ設計）: 独立性は「checker は params の場面文の数値だけから
solver を呼び直す」ところにあり、recipe 側の答えを信用しない。

## 6セルの対応

  - g2_l51 Lv2 (`bag_one_draw`): 袋から玉1個。(1)全部で何通りか (2)該当色の確率
    （誘導あり2小問）。`math.probability_combination_selection`（r=1）を流用。
  - g2_l51 Lv3 (`multiple_union`): 1〜N のカードで「aの倍数、またはbの倍数」。
    重複を引く包除（P(A)+P(B)-P(A∩B)）。`math.probability_single_die`
    （condition="multiple_of"）を3回呼んで合成する（新 solver を作らず「重なりを
    引く」計算だけをここでやる＝word_problem_system の salt_mixture 等と同じ
    「solver の出力を sympy でそのまま合成する」パターン）。
  - g2_l52 Lv3 (`two_dice_product_at_least`): 大小2個のさいころの積が条件以上。
    `math.probability_two_dice`（condition="product_at_least"）をそのまま使う。
  - g2_l53 Lv3 (`lottery_at_least_one`): 戻さずに2本引いて少なくとも一方が当たる。
    「両方はずれ」を `math.probability_combination_selection` で求め、
    `math.probability_complement` で余事象をとる（g2_l54.find_value の
    `probability_at_least_one_recipe` とは別経路＝戻さない抽選は組合せの余事象で
    表せるため、独立試行の複合ではなく combination+complement の合成で足りる）。
  - g2_l54 Lv2 (`two_balls_complement`): 玉を2個同時に取り出す。(1)2個とも target色
    (2)それを利用して少なくとも1個が other色（誘導あり・余事象を明示）。
    `math.probability_combination_selection` → `math.probability_complement`。
  - g2_l54 Lv3 (`dice_repeat_at_least_one`): さいころを繰り返し投げて少なくとも1回
    特定の目。`math.probability_at_least_one` をそのまま使う（誘導なし）。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている数値（玉の個数・カード枚数・さいころの
面数・くじの本数…）そのもので、答え（確率）は入っていない。checker は同じ
`SOLVE_BUILDERS` を通して solver を呼び直す。

## narration に数字を書かない

`multiple_union` と `lottery_at_least_one` は solver を複数回合成するので、solver
自身の steps をそのまま見せると（"玉を区別して…" 等）題材の語彙とズレる場面がある
ため、この2つは合成後の意味に沿った steps をここで組み直す（値は result_display
のみに置き、narration には数字も題材語彙のズレも残さない）。それ以外
（`bag_one_draw` の (2)・`two_dice_product_at_least`・`two_balls_complement`・
`dice_repeat_at_least_one`）は既存 solver の Solution をそのまま使う（steps も
含めて double-solve）。
"""
from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many

RECIPE_NAME = "math.word_problem_probability"

_PROBABILITY_WP_CONCEPTS = [
    "probability.word_problem_bag_one_draw",
    "probability.word_problem_multiple_union",
    "probability.word_problem_two_dice_product",
    "probability.word_problem_lottery_at_least_one",
    "probability.word_problem_two_balls_complement",
    "probability.word_problem_dice_repeat_at_least_one",
    "probability.word_problem_coin_toss_count_and_probability",
    "probability.word_problem_two_digit_cards",
    "probability.word_problem_at_least_two_colors",
    # exam_l5.word_problem（入試融合・確率）— C13。既存の確率資産の再利用なので
    # exam_fusion.py ではなくこのモジュールに置く（exam_l3 を motion.py に置いたのと同じ判断）。
    "exam.dice_guided_total_and_events",
    "exam.at_least_one_by_complement",
]


# ---------------------------------------------------------------------------
# 場面文（recipe が組む）と、そこから solver に渡す数値
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProbabilityScene:
    """場面文と、そこから solve に渡す数値。

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す辞書（params にそのまま載り、
    checker が同じ関数へ渡す）。`ask_texts` は小問文（誘導なしは長さ1）。
    """

    numbers: dict[str, Any]
    scenario: str
    ask_texts: tuple[str, ...]
    # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
    slots: dict[str, str]


def _split_pair(token: str) -> tuple[str, str]:
    """"Aさん|Bさん" → ("Aさん", "Bさん")。"""
    left, _, right = str(token).partition("|")
    return left, right


def _draw_distinct_tokens(candidates: list[Any], rng: Rng, k: int) -> list[Any]:
    idxs = draw_many({"int_range": [0, len(candidates) - 1], "distinct": ["value"]}, rng, k=k)
    return [candidates[int(i)] for i in idxs]


def _draw_index(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


# 構成条件を満たすまでの有界リトライ回数（無限ループを作らないための上限）。
_MAX_DRAW_RETRIES = 40


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「場面の数値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_bag_one_draw(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l51 Lv2: 袋から玉1個。(1)全部で何通りか (2)該当色の確率。"""
    count_a, count_b = int(numbers["count_a"]), int(numbers["count_b"])
    color_a, color_b = str(numbers["color_a"]), str(numbers["color_b"])
    target_color = str(numbers["target_color"])
    if target_color == color_a:
        target_count, other_color, other_count = count_a, color_b, count_b
    else:
        target_count, other_color, other_count = count_b, color_a, count_a

    total = count_a + count_b
    total_solution = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(sympy.Integer(total)), display=f"{total}通り"),
        steps=[
            Step(
                op="count_all_outcomes",
                args=[],
                result_srepr=sympy.srepr(sympy.Integer(total)),
                result_display=f"{total}通り",
                narration="袋の中にある玉の個数をすべて数えて、起こりうる場合の数を求める。",
            ),
        ],
    )
    solver = REGISTRY.solver("math.probability_combination_selection")
    prob_solution = cast(
        Solution,
        solver({target_color: target_count, other_color: other_count}, 1, target_color),
    )
    return [total_solution, prob_solution]


def solve_multiple_union(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l51 Lv3: 「aの倍数、またはbの倍数」。P(A)+P(B)-P(A∩B)（包除）。"""
    n, div_a, div_b = int(numbers["n"]), int(numbers["div_a"]), int(numbers["div_b"])
    solver = REGISTRY.solver("math.probability_single_die")
    sol_a = cast(Solution, solver("cards_n", "multiple_of", div_a, n))
    sol_b = cast(Solution, solver("cards_n", "multiple_of", div_b, n))
    lcm_ab = div_a * div_b // math.gcd(div_a, div_b)
    sol_ab = cast(Solution, solver("cards_n", "multiple_of", lcm_ab, n))
    assert isinstance(sol_a.answer, SymbolicAnswer)
    assert isinstance(sol_b.answer, SymbolicAnswer)
    assert isinstance(sol_ab.answer, SymbolicAnswer)
    p_a = sympy.sympify(sol_a.answer.srepr)
    p_b = sympy.sympify(sol_b.answer.srepr)
    p_ab = sympy.sympify(sol_ab.answer.srepr)
    p_final = cast(sympy.Rational, p_a + p_b - p_ab)

    steps = [
        Step(
            op="count_condition_a",
            args=[],
            result_srepr="",
            result_display="一方の倍数の場合の数を数える",
            narration="一方の倍数の条件にあてはまる場合の数を数え、その確率を求める。",
        ),
        Step(
            op="count_condition_b",
            args=[],
            result_srepr="",
            result_display="もう一方の倍数の場合の数を数える",
            narration="もう一方の倍数の条件にあてはまる場合の数を数え、その確率を求める。",
        ),
        Step(
            op="count_overlap",
            args=[],
            result_srepr="",
            result_display="両方の倍数に共通する場合の数を数える",
            narration="両方の倍数に共通してあてはまる場合の数を数え、その確率を求める。",
        ),
        Step(
            op="apply_inclusion_exclusion",
            args=[],
            result_srepr=sympy.srepr(p_final),
            result_display=f"{p_final}",
            narration="重なっている分を引いて、どちらかの倍数である確率を求める。",
        ),
    ]
    return [Solution(answer=SymbolicAnswer(srepr=sympy.srepr(p_final), display=f"{p_final}"), steps=steps)]


def solve_two_dice_product_at_least(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l52 Lv3: 大小2個のさいころの積が条件以上。"""
    faces, target = int(numbers["faces"]), int(numbers["target"])
    solver = REGISTRY.solver("math.probability_two_dice")
    sol = cast(Solution, solver(faces, "product_at_least", target))
    return [sol]


def solve_lottery_at_least_one(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l53 Lv3: 戻さずに2本引いて少なくとも一方が当たる（余事象＝両方はずれ）。"""
    n, k = int(numbers["n"]), int(numbers["k"])
    counts = {"当たり": k, "はずれ": n - k}
    combo_solver = REGISTRY.solver("math.probability_combination_selection")
    sol_lose = cast(Solution, combo_solver(counts, 2, "はずれ"))
    assert isinstance(sol_lose.answer, SymbolicAnswer)
    p_lose = sympy.sympify(sol_lose.answer.srepr)
    complement_solver = REGISTRY.solver("math.probability_complement")
    sol_final = cast(Solution, complement_solver(p_lose.p, p_lose.q))
    assert isinstance(sol_final.answer, SymbolicAnswer)

    steps = [
        Step(
            op="compute_both_lose_probability",
            args=[],
            result_srepr="",
            result_display="2本とも外れる場合を数える",
            narration="戻さずに2本引いたとき、2本とも外れる場合を数えて、その確率を求める。",
        ),
        Step(
            op="subtract_from_one",
            args=[],
            result_srepr=sol_final.answer.srepr,
            result_display=sol_final.answer.display,
            narration="1から、2本とも外れる確率をひいて、少なくとも一方が当たる確率を求める。",
        ),
    ]
    return [Solution(answer=sol_final.answer, steps=steps)]


def solve_two_balls_complement(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l54 Lv2: (1)2個ともtarget色 (2)それを利用して少なくとも1個がother色。"""
    count_target, count_other = int(numbers["count_target"]), int(numbers["count_other"])
    target_color, other_color = str(numbers["target_color"]), str(numbers["other_color"])
    counts = {target_color: count_target, other_color: count_other}
    combo_solver = REGISTRY.solver("math.probability_combination_selection")
    sol_target = cast(Solution, combo_solver(counts, 2, target_color))
    assert isinstance(sol_target.answer, SymbolicAnswer)
    p_target = sympy.sympify(sol_target.answer.srepr)
    complement_solver = REGISTRY.solver("math.probability_complement")
    sol_other = cast(Solution, complement_solver(p_target.p, p_target.q))
    return [sol_target, sol_other]


def solve_dice_repeat_at_least_one(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l54 Lv3: さいころを繰り返し投げて少なくとも1回特定の目。"""
    faces, trials = int(numbers["faces"]), int(numbers["trials"])
    solver = REGISTRY.solver("math.probability_at_least_one")
    sol = cast(Solution, solver(faces, 1, trials))
    return [sol]


def solve_coin_toss_guided(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l52 Lv2: 硬貨を同時に投げる。(1)出方は全部で何通りか (2)表がちょうど k 枚。

    新 solver は `math.count_coin_toss_outcomes` / `math.probability_coin_toss` の
    2本（どちらも 2^n 通りを itertools で列挙し直す）。台帳の「樹形図に表せ」は
    frame が作図小問を持てないので「全部で何通りか」に置き換えている
    （理由は family の source_desc に明記）。
    """
    coins, count = int(numbers["coins"]), int(numbers["face_count"])
    face = str(numbers["face"])
    count_solver = REGISTRY.solver("math.count_coin_toss_outcomes")
    prob_solver = REGISTRY.solver("math.probability_coin_toss")
    return [
        cast(Solution, count_solver(coins)),
        cast(Solution, prob_solver(coins, count, face)),
    ]


def solve_two_digit_cards_guided(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l53 Lv2: 数字カードを2枚並べて2けたの整数。(1)何通りか (2)条件を満たす確率。

    カードの数字は `digit_1`, `digit_2`, … と1枚ずつ params に置く（本文に出ている
    数がそのまま params に載る、という word_problem の不変条件を守るため。リストを
    1つのキーに詰めると文字列としては本文に現れない）。
    """
    digits = [int(v) for k, v in sorted(numbers.items()) if k.startswith("digit_")]
    condition = str(numbers["condition"])
    count_solver = REGISTRY.solver("math.count_two_digit_from_cards")
    prob_solver = REGISTRY.solver("math.probability_two_digit_from_cards")
    return [
        cast(Solution, count_solver(digits)),
        cast(Solution, prob_solver(digits, condition)),
    ]


def solve_at_least_two_colors(numbers: Mapping[str, Any]) -> list[Solution]:
    """g2_l54 Lv4: 3色の玉から同時に取り出して「少なくとも2色ふくまれる」確率。

    新 solver ゼロ＝既存 solver の合成。「少なくとも2色」の余事象は「全部同じ色」で、
    これは色ごとの `math.probability_combination_selection`（r 個すべてがその色）の
    和になる。その和を `math.probability_complement` に渡して 1−p を得る。
    steps は合成後の意味（余事象のとらえ方）に沿ってここで組み直す。
    """
    draws = int(numbers["draws"])
    counts = {
        str(numbers[f"color_{s}"]): int(numbers[f"count_{s}"]) for s in ("a", "b", "c")
    }
    combo_solver = REGISTRY.solver("math.probability_combination_selection")
    p_same = sympy.Integer(0)
    for color in counts:
        sol = cast(Solution, combo_solver(counts, draws, color))
        assert isinstance(sol.answer, SymbolicAnswer)
        p_same += sympy.sympify(sol.answer.srepr)
    p_same = sympy.Rational(p_same)
    complement_solver = REGISTRY.solver("math.probability_complement")
    sol_final = cast(Solution, complement_solver(p_same.p, p_same.q))
    assert isinstance(sol_final.answer, SymbolicAnswer)
    steps = [
        Step(
            op="take_complement_event",
            args=[],
            result_srepr="",
            result_display="余事象は「取り出した玉が全部同じ色」",
            narration=(
                "求める事象の余事象を考える。色が一種類しかふくまれない場合、"
                "つまり取り出した玉が全部同じ色である場合が、それにあたる。"
            ),
        ),
        Step(
            op="sum_same_color_probabilities",
            args=[],
            result_srepr=sympy.srepr(p_same),
            result_display=str(p_same),
            narration=(
                "色ごとに、取り出した玉がすべてその色になる確率を求め、"
                "それらをたして、全部同じ色になる確率を求める。"
            ),
        ),
        Step(
            op="compute_complement_probability",
            args=[],
            result_srepr=sol_final.answer.srepr,
            result_display=sol_final.answer.display,
            narration="全体の確率から、いま求めた確率をひいて、求める確率とする。",
        ),
    ]
    return [Solution(answer=sol_final.answer, steps=steps)]


_DICE_QUANTITY_KIND = {"和": "sum", "積": "product"}
_PARITY_TARGET = {"偶数": 0, "奇数": 1}


def solve_exam_dice_guided_three(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l5 Lv3: 大小2個のさいころ。(1)全場合の総数 (2)和(積)が指定の値 (3)積(和)の偶奇。

    新 solver は `math.count_two_dice_outcomes`（樹形図・表で整理した結果である総数）
    の1本だけで、(2)(3) は既存 `math.probability_two_dice` に condition を渡すだけ。
    (2) が和なら (3) は積、(2) が積なら (3) は和——同じ量を2回問わないよう入れ替える。
    """
    faces = int(numbers["faces"])
    # 条件は「和／積」「偶数／奇数」という**場面文に出ている語のまま** params に載せる
    # （params の値がすべて given.scenario に現れる、という word_problem の不変条件を
    # 満たすため。"sum"/"product" のような内部表現にすると本文に出ない値になる）。
    target_kind = _DICE_QUANTITY_KIND[str(numbers["target_quantity"])]
    target = int(numbers["target"])
    parity_kind = _DICE_QUANTITY_KIND[str(numbers["parity_quantity"])]
    parity = _PARITY_TARGET[str(numbers["parity_word"])]
    count_solver = REGISTRY.solver("math.count_two_dice_outcomes")
    dice_solver = REGISTRY.solver("math.probability_two_dice")
    return [
        cast(Solution, count_solver(faces)),
        cast(Solution, dice_solver(faces, f"{target_kind}_equals", target)),
        cast(Solution, dice_solver(faces, f"{parity_kind}_parity", parity)),
    ]


def solve_exam_at_least_one_by_complement(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l5 Lv4: 袋から同時に取り出して少なくとも1個が対象の色（誘導なし・余事象）。

    既存の `math.probability_at_least_one` は**もとに戻す独立試行**のものなので、
    同時に取り出す場面には使えない（新 solver
    `math.probability_at_least_one_by_complement` が余事象を組合せで数える）。
    """
    count_target = int(numbers["count_target"])
    count_other = int(numbers["count_other"])
    draws = int(numbers["draws"])
    solver = REGISTRY.solver("math.probability_at_least_one_by_complement")
    return [cast(Solution, solver(count_target, count_other, draws))]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "bag_one_draw": solve_bag_one_draw,
    "coin_toss_guided": solve_coin_toss_guided,
    "two_digit_cards_guided": solve_two_digit_cards_guided,
    "at_least_two_colors": solve_at_least_two_colors,
    "multiple_union": solve_multiple_union,
    "two_dice_product_at_least": solve_two_dice_product_at_least,
    "lottery_at_least_one": solve_lottery_at_least_one,
    "two_balls_complement": solve_two_balls_complement,
    "dice_repeat_at_least_one": solve_dice_repeat_at_least_one,
    "exam_dice_guided_three": solve_exam_dice_guided_three,
    "exam_at_least_one_by_complement": solve_exam_at_least_one_by_complement,
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ。数値を引いて場面文と numbers を組む）
# ---------------------------------------------------------------------------
def _scene_bag_one_draw(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    color_a, color_b = (str(v) for v in _draw_distinct_tokens(list(p["color_candidates"]), rng, 2))
    count_a = int(draw(p["count_domain"], rng))
    count_b = int(draw(p["count_domain"], rng))
    target_index = int(draw({"int_range": [0, 1]}, rng))
    target_color = color_a if target_index == 0 else color_b

    scenario = (
        f"袋の中に{color_a}玉が{count_a}個、{color_b}玉が{count_b}個入っている。"
        "この袋から玉を1個取り出すとき、玉の取り出し方は同様に確からしいものとする。"
    )
    ask_texts = (
        "玉の取り出し方は全部で何通りあるか答えよ。",
        f"取り出した玉が{target_color}玉である確率を求めよ。",
    )
    numbers = {
        "count_a": count_a,
        "count_b": count_b,
        "color_a": color_a,
        "color_b": color_b,
        # index ではなく色名そのものを持つ（数値は全部 given.scenario に出ている値だけ
        # にする規約。0/1 は場面文に現れない内部フラグなので params に置かない）。
        "target_color": target_color,
    }
    return ProbabilityScene(
        numbers=numbers, scenario=scenario, ask_texts=ask_texts,
        slots={"color_a": color_a, "color_b": color_b},
    )


def _multiple_union_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(枚数N, 倍数a, 倍数b) の候補列挙。

    a<b・どちらもいずれかがもう一方を割り切らない（でないと「aの倍数またはbの倍数」が
    実質1条件に退化する）・lcm(a,b)<=N（重なりが実在し、包除の引き算が空振りしない）
    組だけを残す。
    """
    divisors = [int(v) for v in p["divisor_candidates"]]
    n_lo, n_hi = (int(v) for v in p["n_range"])
    out: list[tuple[int, int, int]] = []
    for n in range(n_lo, n_hi + 1):
        for a in divisors:
            for b in divisors:
                if a >= b:
                    continue
                if b % a == 0 or a % b == 0:
                    continue
                lcm_ab = a * b // math.gcd(a, b)
                if lcm_ab > n:
                    continue
                out.append((n, a, b))
    return out


def _scene_multiple_union(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    cands = _multiple_union_candidates(p)
    n, div_a, div_b = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    # 数値は given.scenario にすべて置く（G-Q5t の whitelist は mr.given だけを見るため、
    # ask 側にしか出さない数値は「given に無いのに答えの分母/分子と一致する」で
    # 誤検出される＝踏んだ罠）。ask は数値を含まない指示文だけにする。
    scenario = (
        f"1から{n}までの番号が1つずつ書かれた{n}枚のカードから1枚を引く。"
        f"引いたカードの番号が{div_a}の倍数であるか、{div_b}の倍数であるかを考える。"
    )
    ask_texts = ("そのどちらかの倍数である確率を求めよ。",)
    numbers = {"n": n, "div_a": div_a, "div_b": div_b}
    return ProbabilityScene(numbers=numbers, scenario=scenario, ask_texts=ask_texts, slots={})


def _two_dice_product_at_least_candidates(faces: int) -> list[int]:
    """faces×faces の積のうち、最小値（=全数該当・退化）を除いた候補。"""
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    products = sorted({a * b for a, b in pairs})
    return [v for v in products if v > min(products)]


def _scene_two_dice_product_at_least(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    faces = int(draw(p["faces_domain"], rng))
    cands = _two_dice_product_at_least_candidates(faces)
    target = int(draw({"int_set": cands}, rng))
    face_phrase = "" if faces == 6 else f"1から{faces}までの目が出る"
    # target も given.scenario に置く（ask にしか出さないと whitelist されず G-Q5t が
    # 偽陽性になる＝踏んだ罠。ask は数値を含まない指示文だけにする）。
    scenario = f"{face_phrase}大小2個のさいころを同時に投げる。出た目の積が{target}以上になるかどうかを考える。"
    ask_texts = ("この確率を求めよ。",)
    numbers = {"faces": faces, "target": target}
    return ProbabilityScene(numbers=numbers, scenario=scenario, ask_texts=ask_texts, slots={})


def _scene_lottery_at_least_one(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    n = int(draw(p["n_domain"], rng))
    # k(当たり本数)>=1・はずれ(n-k)>=2（戻さず2本引いて「両方はずれ」が起こりうる必要）。
    # 当たりが少数派になる範囲に抑える（くじ引きとして自然な場面にする）。
    k = int(draw({"int_range": [1, max(1, (n - 1) // 2)]}, rng))
    first, second = _split_pair(str(_draw_index(list(p["person_pair_candidates"]), rng)))
    scenario = (
        f"当たりくじ{k}本を含む{n}本のくじから、{first}と{second}がこの順に1本ずつ引く。"
        "引いたくじはもとにもどさないものとする。"
    )
    ask_texts = ("少なくとも一方が当たる確率を求めよ。",)
    numbers = {"n": n, "k": k}
    return ProbabilityScene(
        numbers=numbers, scenario=scenario, ask_texts=ask_texts,
        slots={"first": first, "second": second},
    )


def _scene_two_balls_complement(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    color_a, color_b = (str(v) for v in _draw_distinct_tokens(list(p["color_candidates"]), rng, 2))
    count_target = int(draw(p["count_target_domain"], rng))
    count_other = int(draw(p["count_other_domain"], rng))
    scenario = (
        f"{color_a}玉{count_target}個、{color_b}玉{count_other}個が入った袋から"
        f"玉を2個同時に取り出す。少なくとも1個が{color_b}玉である確率を求めたい。"
    )
    ask_texts = (
        f"2個とも{color_a}玉である確率を求めよ。",
        f"それを利用して、少なくとも1個が{color_b}玉である確率を求めよ。",
    )
    numbers = {
        "count_target": count_target,
        "count_other": count_other,
        "target_color": color_a,
        "other_color": color_b,
    }
    return ProbabilityScene(
        numbers=numbers, scenario=scenario, ask_texts=ask_texts,
        slots={"color_a": color_a, "color_b": color_b},
    )


def _scene_dice_repeat_at_least_one(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    faces = int(draw(p["faces_domain"], rng))
    trials = int(draw(p["trials"], rng))
    # target_face は solver には渡らない（favorable_size=1 は目の値によらない）が、
    # 場面文に出す数値なので numbers に含める（params の全数値が given に現れる規約）。
    # ask にしか出さないと G-Q5t の whitelist（mr.given だけを見る）に載らず偽陽性に
    # なる＝踏んだ罠。target_face も given.scenario に置き、ask は指示文だけにする。
    target_face = int(draw({"int_range": [1, faces]}, rng))
    scenario = f"1から{faces}までの目が出るさいころを{trials}回投げる。{target_face}の目に注目する。"
    ask_texts = ("少なくとも1回は、その目が出る確率を求めよ。",)
    numbers = {"faces": faces, "trials": trials, "target_face": target_face}
    return ProbabilityScene(numbers=numbers, scenario=scenario, ask_texts=ask_texts, slots={})


def _scene_coin_toss_guided(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    """g2_l52 Lv2: 硬貨を同時に投げる（誘導あり2小問）。

    注目する面の枚数 k は 0 と n を避ける（0枚・全部同じ面は「樹形図で数える」意味が
    薄く、場合の数を数える練習にならない）。

    場面の枠組みは2通りを引く。どちらも教科書に出る言い方で、しかも
    **「同時に投げても硬貨は区別して数える」という単元の要点**を、金種違いの側が
    目に見える形で示す:
      - same_kind: 「10円硬貨を4枚同時に投げる」
      - mixed:     「10円硬貨、50円硬貨、100円硬貨の3枚を同時に投げる」
    この2枠組み＋金種の組合せが dup の主な自由度になる（枚数と枚数条件だけだと
    9通りしかなく、実測 dup_rate 0.55＝閾値の2倍超だった）。

    注目する面と枚数は **given.scenario 側に置く**。ask にしか出ない数値は G-Q5t の
    whitelist（mr.given だけを見る）に載らず、答え（確率）の分子・分母と衝突して
    偽陽性になる（既知の罠。dice_repeat_at_least_one と同じ扱い）。
    """
    candidates = [str(v) for v in p["coin_candidates"]]
    coins = int(draw(p["coins_domain"], rng))
    face_count = int(draw({"int_range": [1, coins - 1]}, rng))
    face = str(_draw_index(list(p["face_candidates"]), rng))
    mixed = int(draw({"int_range": [0, 1]}, rng)) == 1 and coins <= len(candidates)
    if mixed:
        kinds = [str(v) for v in _draw_distinct_tokens(candidates, rng, coins)]
        subject = "、".join(kinds) + f"の{coins}枚を"
    else:
        kinds = [str(_draw_index(candidates, rng))]
        subject = f"{kinds[0]}を{coins}枚"
    # slots は1金種につき1キー（値がそのまま場面文に現れる、という word_problem の
    # 不変条件を満たすため。連結した1文字列にすると本文に出ない文字列になる）。
    coin_slots = {f"coin_{i + 1}": kind for i, kind in enumerate(kinds)}
    scenario = (
        f"{subject}同時に投げる。どの硬貨も表と裏の出方は同様に確からしいものとする。"
        f"ちょうど{face_count}枚が{face}になる場合に注目する。"
    )
    ask_texts = (
        "表と裏の出方は全部で何通りあるか答えよ。",
        "注目している場合が起こる確率を求めよ。",
    )
    return ProbabilityScene(
        numbers={"coins": coins, "face_count": face_count, "face": face},
        scenario=scenario,
        ask_texts=ask_texts,
        slots=coin_slots,
    )


def _scene_two_digit_cards_guided(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    """g2_l53 Lv2: 数字カードを並べて2けたの整数をつくる（誘導あり2小問）。

    条件語（偶数／奇数）は **given.scenario 側に置く**。ask にしか出ない語や数値は
    G-Q5t の whitelist（mr.given だけを見る）に載らないため（既知の罠）。
    """
    card_count = int(draw(p["card_count_domain"], rng))
    # カードに偶数と奇数がどちらも含まれるまで有界リトライする。全部奇数（1,3,5,7 等・
    # 1〜9 から4枚引くと約5%で起こる）だと「偶数になる確率」が 0 に潰れ、確率の問題
    # として退化する（ゲートは 0 を不正とはみなさないので構成側で防ぐしかない）。
    digits: list[int] = []
    for _ in range(_MAX_DRAW_RETRIES):
        digits = sorted(int(v) for v in draw_many(p["digit_domain"], rng, k=card_count))
        if any(d % 2 == 0 for d in digits) and any(d % 2 == 1 for d in digits):
            break
    else:  # pragma: no cover - 有界リトライを使い切る確率は 0.05^N で無視できる
        raise RuntimeError("偶数と奇数を両方含むカードの組を引けなかった")
    condition = str(_draw_index(list(p["condition_candidates"]), rng))
    digits_text = "、".join(str(d) for d in digits)
    scenario = (
        f"{digits_text}の数字が1つずつ書かれた{card_count}枚のカードがある。"
        f"この中から2枚を続けて引き、引いた順に並べて2けたの整数をつくる。"
        f"できた整数が{condition}になるかどうかを考える。"
    )
    ask_texts = (
        "できる2けたの整数は全部で何通りあるか答えよ。",
        "できた整数がその条件にあてはまる確率を求めよ。",
    )
    numbers: dict[str, Any] = {f"digit_{i + 1}": d for i, d in enumerate(digits)}
    numbers["card_count"] = card_count
    numbers["condition"] = condition
    return ProbabilityScene(
        numbers=numbers,
        scenario=scenario,
        ask_texts=ask_texts,
        slots={},
    )


def _scene_at_least_two_colors(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    """g2_l54 Lv4: 3色の玉から同時に取り出し「少なくとも2色」（誘導なし1小問）。

    非退化: どの色も `draws` 個以上ある色が少なくとも1つは要る（全色が draws 未満だと
    余事象「全部同じ色」が起こりえず、答えが常に 1 になって場合分けが空振りする）。
    """
    colors = [str(v) for v in _draw_distinct_tokens(list(p["color_candidates"]), rng, 3)]
    draws = int(draw(p["draws_domain"], rng))
    counts: list[int] = []
    for _ in range(3):
        counts.append(int(draw(p["count_domain"], rng)))
    # 少なくとも1色は draws 個以上（余事象が起こりうる）ことを構成で保証する。
    if max(counts) < draws:
        counts[0] = draws
    scenario = (
        f"袋の中に{colors[0]}玉が{counts[0]}個、{colors[1]}玉が{counts[1]}個、"
        f"{colors[2]}玉が{counts[2]}個入っている。"
        f"この袋から玉を{draws}個同時に取り出すとき、取り出し方は同様に確からしいものとする。"
    )
    ask_texts = ("取り出した玉に少なくとも2色がふくまれる確率を求めよ。",)
    numbers = {
        "color_a": colors[0], "count_a": counts[0],
        "color_b": colors[1], "count_b": counts[1],
        "color_c": colors[2], "count_c": counts[2],
        "draws": draws,
    }
    return ProbabilityScene(
        numbers=numbers,
        scenario=scenario,
        ask_texts=ask_texts,
        # 色名は numbers 側にすでに1色ずつ入っている（dup_key は params 全体を見るので
        # slots に重ねる必要はない）。
        slots={},
    )


def _exam_dice_target_candidates(faces: int, kind: str) -> list[int]:
    """出る目の和(積)としてありうる値のうち、確率が 0 にも 1 にも潰れないもの。

    「ありえない値」（積が7など）を引くと確率が 0 になり、数え上げの練習にならない
    （0 や 1 に潰れる構成はどのゲートも弾かないので、構成の段階で外す＝既知の罠）。
    """
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    out: list[int] = []
    for value in sorted({(a + b if kind == "sum" else a * b) for a, b in pairs}):
        hit = sum(1 for a, b in pairs if (a + b if kind == "sum" else a * b) == value)
        if 0 < hit < len(pairs):
            out.append(value)
    return out


def _scene_exam_dice_guided_three(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    """exam_l5 Lv3: 大小2個のさいころ（誘導あり3小問・整理 → 和(積)の値 → 偶奇）。

    注目する値 `target` は **given.scenario に置く**。ask にしか出ない数値は G-Q5t の
    whitelist（mr.given だけを見る）に載らず、答えの分子・分母（srepr が
    Rational(p, q) なので p・q が別々のトークンになる）と衝突して偽陽性になる
    （既知の罠）。scenario に出したうえで ask で言い直すのは安全。

    dup の自由度は 場面の言い方(8) × 注目する値(和11+積18) × 偶奇(2) ≈ 464 通り。
    """
    faces = int(draw(p["faces_domain"], rng))
    framing = str(_draw_index(list(p["dice_scene_set"]), rng))
    quantity = str(_draw_index(["和", "積"], rng))
    target = int(
        draw({"int_set": _exam_dice_target_candidates(faces, _DICE_QUANTITY_KIND[quantity])}, rng)
    )
    # (2) が和なら (3) は積、(2) が積なら (3) は和（同じ量を2回問わない）。
    parity_quantity = "積" if quantity == "和" else "和"
    parity_word = str(_draw_index(["偶数", "奇数"], rng))

    # 面数は標準の6でも省かずに書く（word_problem の不変条件＝params の数値は本文に
    # 必ず出ている、を満たすため。contract の忠実性検査がこれを機械的に見ている）。
    scenario = (
        f"1から{faces}までの目が出る{framing}。どの目が出ることも同様に確からしいものとする。"
        f"出る目の{quantity}が{target}になる場合と、"
        f"出る目の{parity_quantity}が{parity_word}になる場合について考える。"
    )
    ask_texts = (
        "出る目の組合せは全部で何通りあるか、樹形図または表に整理して答えよ。",
        f"出る目の{quantity}が{target}になる確率を求めよ。",
        f"出る目の{parity_quantity}が{parity_word}になる確率を求めよ。",
    )
    numbers = {
        "faces": faces,
        "target_quantity": quantity,
        "target": target,
        "parity_quantity": parity_quantity,
        "parity_word": parity_word,
    }
    return ProbabilityScene(
        numbers=numbers, scenario=scenario, ask_texts=ask_texts,
        slots={"framing": framing},
    )


def _scene_exam_at_least_one_by_complement(p: Mapping[str, Any], rng: Rng) -> ProbabilityScene:
    """exam_l5 Lv4: 袋から同時に取り出して少なくとも1個が対象の色（誘導なし1小問）。

    非退化: 取り出す個数 `draws` は対象でない側の個数以下にする（そうでないと対象が
    必ず1個は入ってしまい、確率が 1 に潰れて余事象を考える意味がなくなる）。
    """
    container, item, counter = str(_draw_index(list(p["container_set"]), rng)).split("|")
    color_target, color_other = (
        str(v) for v in _draw_distinct_tokens(list(p["color_candidates"]), rng, 2)
    )
    count_target = int(draw(p["count_target_domain"], rng))
    count_other = int(draw(p["count_other_domain"], rng))
    draws = int(draw(p["draws_domain"], rng))
    if draws > count_other:
        # 余事象（対象の色が1個も入らない）が起こりうるところまで取り出す個数を戻す。
        draws = count_other
    scenario = (
        f"{container}の中に、{color_target}い{item}が{count_target}{counter}と"
        f"{color_other}い{item}が{count_other}{counter}入っている。"
        f"この{container}から同時に{draws}{counter}取り出す。"
        f"どの{item}が取り出されることも同様に確からしいものとする。"
    )
    ask_texts = (
        f"取り出した{item}のうち、少なくとも1{counter}が{color_target}い{item}である"
        "確率を求めよ。",
    )
    numbers = {
        "count_target": count_target,
        "count_other": count_other,
        "draws": draws,
        "color_target": color_target,
        "color_other": color_other,
    }
    return ProbabilityScene(
        numbers=numbers, scenario=scenario, ask_texts=ask_texts,
        slots={"container": container, "item": item},
    )


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], ProbabilityScene]] = {
    "bag_one_draw": _scene_bag_one_draw,
    "coin_toss_guided": _scene_coin_toss_guided,
    "two_digit_cards_guided": _scene_two_digit_cards_guided,
    "at_least_two_colors": _scene_at_least_two_colors,
    "multiple_union": _scene_multiple_union,
    "two_dice_product_at_least": _scene_two_dice_product_at_least,
    "lottery_at_least_one": _scene_lottery_at_least_one,
    "two_balls_complement": _scene_two_balls_complement,
    "dice_repeat_at_least_one": _scene_dice_repeat_at_least_one,
    "exam_dice_guided_three": _scene_exam_dice_guided_three,
    "exam_at_least_one_by_complement": _scene_exam_at_least_one_by_complement,
}


# ---------------------------------------------------------------------------
# recipe（6セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_PROBABILITY_WP_CONCEPTS)
def word_problem_probability(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_BUILDERS[kind](p, rng)
    solutions = SOLVE_BUILDERS[kind](scene.numbers)
    assert len(solutions) == len(scene.ask_texts)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})",
            asked="value",
            answer=sol.answer,
            steps=sol.steps,
            concept_tags=concept_tags,
            cause_tags=cause_tags,
        )
        for i, sol in enumerate(solutions)
    ]

    context_slots = dict(scene.slots)
    if len(scene.ask_texts) == 1:
        context_slots["ask_value"] = scene.ask_texts[0]
    else:
        # 誘導あり（2小問＝wp_probability_guided_v1／3小問＝wp_guided_three_v1）。
        for i, ask_text in enumerate(scene.ask_texts):
            context_slots[f"ask_{i + 1}"] = ask_text

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 場面文が読者に見せている数値だけ（答えは入れない）。checker はここから
            # solver を呼び直す。
            "scenario_kind": kind,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given={"scenario": scene.scenario},
        context_slots=context_slots,
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "ProbabilityScene",
    "SOLVE_BUILDERS",
    "solve_bag_one_draw",
    "solve_multiple_union",
    "solve_two_dice_product_at_least",
    "solve_lottery_at_least_one",
    "solve_two_balls_complement",
    "solve_dice_repeat_at_least_one",
    "solve_exam_dice_guided_three",
    "solve_exam_at_least_one_by_complement",
    "word_problem_probability",
]
