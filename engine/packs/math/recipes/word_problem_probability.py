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


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "bag_one_draw": solve_bag_one_draw,
    "multiple_union": solve_multiple_union,
    "two_dice_product_at_least": solve_two_dice_product_at_least,
    "lottery_at_least_one": solve_lottery_at_least_one,
    "two_balls_complement": solve_two_balls_complement,
    "dice_repeat_at_least_one": solve_dice_repeat_at_least_one,
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


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], ProbabilityScene]] = {
    "bag_one_draw": _scene_bag_one_draw,
    "multiple_union": _scene_multiple_union,
    "two_dice_product_at_least": _scene_two_dice_product_at_least,
    "lottery_at_least_one": _scene_lottery_at_least_one,
    "two_balls_complement": _scene_two_balls_complement,
    "dice_repeat_at_least_one": _scene_dice_repeat_at_least_one,
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

    guided = len(scene.ask_texts) == 2
    context_slots = dict(scene.slots)
    if guided:
        context_slots["ask_1"] = scene.ask_texts[0]
        context_slots["ask_2"] = scene.ask_texts[1]
    else:
        context_slots["ask_value"] = scene.ask_texts[0]

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
    "word_problem_probability",
]
