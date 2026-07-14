"""確率まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C12（確率）クラスタの非 visual セル群（g1_l59・g2_l51〜54）に対応する recipe を集約する。
乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

import itertools
from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# math.relative_frequency（g1_l59.calculation Lv1 / g2_l51.find_value Lv2）
# ---------------------------------------------------------------------------
_RELATIVE_FREQUENCY_G1_CONCEPTS = ["probability.relative_frequency_basic"]
_RELATIVE_FREQUENCY_G2_CONCEPTS = ["probability.relative_frequency_estimate"]


@register_recipe("math.relative_frequency_g1", provides_concepts=_RELATIVE_FREQUENCY_G1_CONCEPTS)
def relative_frequency_g1_recipe(ctx: CellContext, rng: Rng) -> MR:
    """さいころの相対度数（g1_l59.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    total = int(draw(p["total_domain"], rng))
    occurred = int(draw({"int_range": [1, total - 1]}, rng))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(occurred, total))

    statement = f"さいころを{total}回投げたところ、1の目が{occurred}回出た。1の目が出た相対度数を求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": occurred, "total": total},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.relative_frequency_g1"),
    )


@register_recipe("math.relative_frequency_g2", provides_concepts=_RELATIVE_FREQUENCY_G2_CONCEPTS)
def relative_frequency_g2_recipe(ctx: CellContext, rng: Rng) -> MR:
    """びんのふたなどの相対度数から確率を推定する（g2_l51.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    total = int(draw(p["total_domain"], rng))
    occurred = int(draw({"int_range": [1, total - 1]}, rng))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(occurred, total))

    condition = (
        f"あるびんのふたを{total}回投げたところ、表が向いた回数が{occurred}回であった。"
        f"この結果から、このふたを投げたとき表が出る確率を分数で推定せよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": occurred, "total": total},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.relative_frequency_g2"),
    )


# ---------------------------------------------------------------------------
# math.probability_single_die（g2_l51.find_value Lv1 / g2_l52.find_value Lv1）
# ---------------------------------------------------------------------------
_SINGLE_DIE_CONCEPTS = ["probability.count_single_space"]

_SINGLE_CONDITION_TEXT: dict[str, str] = {
    "even": "偶数の目が出る",
    "odd": "奇数の目が出る",
}


def _draw_die_condition(rng: Rng) -> tuple[str, str, int]:
    """さいころの条件（偶数/奇数/以上/以下）を構成する。戻り値: (condition, text, target)"""
    kind = str(draw(["even", "odd", "at_least", "at_most"], rng))
    if kind in ("even", "odd"):
        return kind, _SINGLE_CONDITION_TEXT[kind], 0
    target = int(draw({"int_range": [2, 5]}, rng))
    if kind == "at_least":
        return kind, f"{target}以上の目が出る", target
    return kind, f"{target}以下の目が出る", target


def _draw_cards_condition(rng: Rng, n: int) -> tuple[str, str, int]:
    """カード1〜Nの条件（偶数/奇数/倍数/以上/以下）を構成する。

    さいころ(6面)だけでは条件の組合せが少なすぎ dup_rate が構造的に閾値を超えるため、
    「1〜Nの番号カードから1枚引く」という同じ数え上げスキルの上位互換（Nを広くとれる）
    に一般化して自由度を広げる（鉄則②。同じ単元の word_problem 階層でも実際に使われて
    いる題材＝spec との整合性あり）。
    """
    kind = str(draw(["even", "odd", "at_least", "at_most", "multiple_of"], rng))
    if kind in ("even", "odd"):
        text = "偶数である" if kind == "even" else "奇数である"
        return kind, text, 0
    if kind == "multiple_of":
        k = int(draw({"int_set": [2, 3, 4, 5]}, rng))
        return kind, f"{k}の倍数である", k
    target = int(draw({"int_range": [2, n - 1]}, rng))
    if kind == "at_least":
        return kind, f"{target}以上である", target
    return kind, f"{target}以下である", target


@register_recipe("math.probability_single_die", provides_concepts=_SINGLE_DIE_CONCEPTS)
def probability_single_die_recipe(ctx: CellContext, rng: Rng) -> MR:
    """硬貨・1個のさいころ・番号カードで条件付き確率を求める（g2_l51/l52.find_value・

    answer-first）。spec_level.params["space_choices"]（例: ["die6","cards_n"] や
    ["die6","coin2","cards_n"]）からどの試行を扱うかを選ぶ。
    """
    p = ctx.spec_level.params
    space_choices = cast("list[str]", p["space_choices"])
    space_name = str(draw(space_choices, rng))
    size = 0
    target: int | str
    if space_name == "coin2":
        condition, target = "equals", "表"
        statement = "10円硬貨を1枚投げるとき、表が出る確率を求めよ"
    elif space_name == "cards_n":
        n = int(draw(p["n_domain"], rng))
        size = n
        condition, condition_text, target = _draw_cards_condition(rng, n)
        statement = (
            f"1から{n}までの番号が1つずつ書かれた{n}枚のカードから1枚を引く。"
            f"引いたカードの番号が{condition_text}確率を求めよ"
        )
    else:  # die6
        condition, condition_text, target = _draw_die_condition(rng)
        statement = f"1個のさいころを投げるとき、{condition_text}確率を求めよ"

    solver = REGISTRY.solver("math.probability_single_die")
    sol = cast(Solution, solver(space_name, condition, target, size))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"space_name": space_name, "condition": condition, "target": target, "size": size},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_single_die"),
    )


# ---------------------------------------------------------------------------
# math.probability_two_dice（g2_l52.find_value Lv3）
# ---------------------------------------------------------------------------
_TWO_DICE_CONCEPTS = ["probability.count_two_dice"]


def _construct_two_dice(rng: Rng, faces: int) -> tuple[str, int, str]:
    """条件（和/積）と目標値を、該当数が0でも全数でもなくなるよう構成する。

    面数 faces を6固定にせず広くとる（大小2個のさいころ「等」＝desc の想定どおり。
    6面だけでは条件の組合せが少なすぎ dup_rate が構造的に閾値を超えるため鉄則②で一般化）。
    """
    kind = str(draw(["sum_equals", "sum_at_least", "product_equals", "product_at_least"], rng))
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    if kind in ("sum_equals", "sum_at_least"):
        sums = sorted({a + b for a, b in pairs})
        target = int(draw({"int_set": sums}, rng))
        text = (
            f"出た目の和が{target}になる確率を、表を作って求めよ" if kind == "sum_equals"
            else f"出た目の和が{target}以上になる確率を、表を作って求めよ"
        )
    else:
        products = sorted({a * b for a, b in pairs})
        cands = [v for v in products if v > min(products)]  # 全数(該当=全pairs)を避ける
        target = int(draw({"int_set": cands}, rng))
        text = (
            f"出た目の積が{target}になる確率を求めよ" if kind == "product_equals"
            else f"出た目の積が{target}以上になる確率を求めよ"
        )
    return kind, target, text


@register_recipe("math.probability_two_dice", provides_concepts=_TWO_DICE_CONCEPTS)
def probability_two_dice_recipe(ctx: CellContext, rng: Rng) -> MR:
    """大小2個のさいころの和・積条件の確率を求める（g2_l52.find_value Lv3・answer-first）。"""
    p = ctx.spec_level.params
    faces = int(draw(p["faces_domain"], rng))
    kind, target, text = _construct_two_dice(rng, faces)
    face_phrase = "" if faces == 6 else f"1から{faces}までの目が出る"
    condition = f"{face_phrase}大小2個のさいころを同時に投げるとき、{text}"

    solver = REGISTRY.solver("math.probability_two_dice")
    sol = cast(Solution, solver(faces, kind, target))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"faces": faces, "condition": kind, "target": target},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_two_dice"),
    )


# ---------------------------------------------------------------------------
# math.probability_ordered_selection（g2_l53.find_value Lv2）
# ---------------------------------------------------------------------------
_ORDERED_SELECTION_CONCEPTS = ["probability.count_ordered_selection"]


_ROLE_NAMES = ["委員長", "副委員長", "書記", "会計"]


@register_recipe("math.probability_ordered_selection", provides_concepts=_ORDERED_SELECTION_CONCEPTS)
def probability_ordered_selection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """n人から役職を順に選ぶとき特定の1人が選ばれる確率を求める（g2_l53.find_value Lv2）。

    n（人数）に加え、選ぶ役職の数 r（2〜4）・対象の人が選ばれる役職の位置 target_index を
    構成時に振ることで、n だけに頼らず自由度を広げる（鉄則②。答えは常に 1/n で不変だが、
    構成そのものは相異なる場面として妥当）。
    """
    p = ctx.spec_level.params
    n = int(draw(p["n_domain"], rng))
    r = int(draw({"int_range": [2, min(4, n - 1)]}, rng))
    target_index = int(draw({"int_range": [0, r - 1]}, rng))
    roles = "、".join(_ROLE_NAMES[:r])
    condition = (
        f"{n}人の生徒から、{roles}を1人ずつ順に選ぶ。選び方は全部で何通りあるか樹形図で数え、"
        f"生徒Aが{_ROLE_NAMES[target_index]}に選ばれる確率を求めよ"
    )

    solver = REGISTRY.solver("math.probability_ordered_selection")
    sol = cast(Solution, solver(n, r, target_index))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(1, n))

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"n": n, "r": r, "target_index": target_index},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_ordered_selection"),
    )


# ---------------------------------------------------------------------------
# math.probability_combination_selection（g2_l53.find_value Lv3）
# ---------------------------------------------------------------------------
_COMBINATION_SELECTION_CONCEPTS = ["probability.count_combination_selection"]


@register_recipe(
    "math.probability_combination_selection", provides_concepts=_COMBINATION_SELECTION_CONCEPTS
)
def probability_combination_selection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """玉を同時に2個取り出すとき両方が同じ色である確率を求める（g2_l53.find_value Lv3）。"""
    p = ctx.spec_level.params
    count_target = int(draw(p["count_target_domain"], rng))  # target色の個数(≧2)
    count_other = int(draw(p["count_other_domain"], rng))
    color_pair = cast("list[str]", draw(p["color_pairs"], rng))
    target_color, other_color = color_pair

    counts = {target_color: count_target, other_color: count_other}
    condition = (
        f"{target_color}玉{count_target}個、{other_color}玉{count_other}個が入った袋から"
        f"玉を2個同時に取り出す。取り出した2個がともに{target_color}玉である確率を求めよ"
    )

    solver = REGISTRY.solver("math.probability_combination_selection")
    sol = cast(Solution, solver(counts, 2, target_color))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"counts": counts, "r": 2, "target_color": target_color},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_combination_selection"),
    )


# ---------------------------------------------------------------------------
# math.probability_complement（g2_l54.find_value Lv2）
# ---------------------------------------------------------------------------
_COMPLEMENT_CONCEPTS = ["probability.complement"]


@register_recipe("math.probability_complement", provides_concepts=_COMPLEMENT_CONCEPTS)
def probability_complement_recipe(ctx: CellContext, rng: Rng) -> MR:
    """出た目の和が特定の値になる確率から、ならない確率(余事象)を求める（g2_l54.find_value Lv2）。

    さいころの面数 faces を6固定にせず広くとる（大小2個のさいころ「等」。6面だけでは
    (和の目標値)の組合せが少なすぎ dup_rate が構造的に閾値を超えるため鉄則②で一般化）。
    """
    p = ctx.spec_level.params
    faces = int(draw(p["faces_domain"], rng))
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    sums = sorted({a + b for a, b in pairs})
    target = int(draw({"int_set": sums}, rng))
    favorable = len([1 for a, b in pairs if a + b == target])
    p_num, p_den = favorable, len(pairs)

    face_phrase = "" if faces == 6 else f"1から{faces}までの目が出る"
    condition = (
        f"{face_phrase}大小2個のさいころを同時に投げるとき、出た目の和が{target}になる確率が"
        f"{p_num}/{p_den}である。出た目の和が{target}にならない確率を求めよ"
    )

    solver = REGISTRY.solver("math.probability_complement")
    sol = cast(Solution, solver(p_num, p_den))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert (sympy.Rational(p_num, p_den) + sympy.sympify(sol.answer.srepr) - 1).equals(0)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"p_num": p_num, "p_den": p_den},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_complement"),
    )


# ---------------------------------------------------------------------------
# math.probability_at_least_one（g2_l54.find_value Lv3）
# ---------------------------------------------------------------------------
_AT_LEAST_ONE_CONCEPTS = ["probability.at_least_one_via_complement"]


@register_recipe("math.probability_at_least_one", provides_concepts=_AT_LEAST_ONE_CONCEPTS)
def probability_at_least_one_recipe(ctx: CellContext, rng: Rng) -> MR:
    """独立試行で少なくとも1回は条件が起こる確率を余事象で求める（g2_l54.find_value Lv3）。

    硬貨(space_size=2)だけでなく、さいころ(space_size=faces)で「特定の目」「偶数の目」等の
    条件も選べるようにし、trials(試行回数)だけに頼らず自由度を広げる（鉄則②。硬貨だけでは
    dup_rate が構造的に閾値を超えるため一般化）。
    """
    p = ctx.spec_level.params
    trials = int(draw(p["trials_domain"], rng))
    # coin は trials しか自由度がなく単独では dup_rate が閾値を超えるため、faces も振れる
    # die_face/die_even の比重を高くする（鉄則②。リストの重複要素で一様抽選の重みを付ける）。
    kind = str(draw(["coin", "die_face", "die_face", "die_face", "die_even", "die_even", "die_even"], rng))
    if kind == "coin":
        space_size, favorable_size = 2, 1
        condition = f"{trials}枚の硬貨を同時に投げるとき、少なくとも1枚は表が出る確率を、余事象を利用して求めよ"
    elif kind == "die_face":
        faces = int(draw({"int_range": [4, 30]}, rng))
        space_size, favorable_size = faces, 1
        condition = (
            f"1個のさいころ（1から{faces}までの目が出る）を{trials}回投げるとき、"
            f"少なくとも1回は1の目が出る確率を、余事象を利用して求めよ"
        )
    else:  # die_even
        faces = int(draw({"int_set": list(range(4, 31, 2))}, rng))
        space_size, favorable_size = faces, faces // 2
        condition = (
            f"1個のさいころ（1から{faces}までの目が出る）を{trials}回投げるとき、"
            f"少なくとも1回は偶数の目が出る確率を、余事象を利用して求めよ"
        )

    # coin2/die の "favorable" を index0..favorable_size-1 とする solver 側の規約に合わせる。
    solver = REGISTRY.solver("math.probability_at_least_one")
    sol = cast(Solution, solver(space_size, favorable_size, trials))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"space_size": space_size, "favorable_size": favorable_size, "trials": trials},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_at_least_one"),
    )


# ---------------------------------------------------------------------------
# math.judge_equally_likely（g2_l51.knowledge Lv2）
# ---------------------------------------------------------------------------
_JUDGE_EQUALLY_LIKELY_CONCEPTS = ["probability.judge_equally_likely"]

# (場面文テンプレ, is_equally_likely)。テンプレは {n} に枚数等の数量を埋める1スロットを
# 持ち、dup 分散（surface の variety）に使う。画びょう等、結果によって起こりやすさが
# 違う場面は False。
_EQUALLY_LIKELY_SCENARIOS: list[tuple[str, bool]] = [
    ("1枚の10円硬貨を投げて、表と裏のどちらが出るか", True),
    ("1個のさいころを投げて、1から6までのどの目が出るか", True),
    ("1から{n}までの番号が書かれたカードから1枚を引いて、どの番号が出るか", True),
    ("画びょうを1個投げて、上向きと下向きのどちらになるか", False),
    ("形のいびつなさいころを投げて、どの目が出るか", False),
    ("当たりが1本だけ入っている{n}本のくじから1本引いて、当たりか外れか", False),
]


@register_recipe("math.judge_equally_likely", provides_concepts=_JUDGE_EQUALLY_LIKELY_CONCEPTS)
def judge_equally_likely_recipe(ctx: CellContext, rng: Rng) -> MR:
    """場面が「同様に確からしい」かを判別する（g2_l51.knowledge Lv2・answer-first）。"""
    idx = int(draw({"int_range": [0, len(_EQUALLY_LIKELY_SCENARIOS) - 1]}, rng))
    template, is_equally_likely = _EQUALLY_LIKELY_SCENARIOS[idx]
    n = int(draw({"int_range": [3, 100]}, rng))
    statement = template.format(n=n) if "{n}" in template else template

    solver = REGISTRY.solver("math.judge_equally_likely")
    sol = cast(Solution, solver(is_equally_likely))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "同様に確からしいといえる" if is_equally_likely else "同様に確からしいとはいえない"
    assert sol.answer.correct == expected

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"scenario_index": idx, "n": n, "is_equally_likely": str(is_equally_likely)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_equally_likely"),
    )


# ---------------------------------------------------------------------------
# math.interpret_relative_frequency_limit（g1_l59.knowledge Lv2）
# ---------------------------------------------------------------------------
_INTERPRET_RELATIVE_FREQ_CONCEPTS = ["probability.interpret_relative_frequency_limit"]


@register_recipe(
    "math.interpret_relative_frequency_limit", provides_concepts=_INTERPRET_RELATIVE_FREQ_CONCEPTS
)
def interpret_relative_frequency_limit_recipe(ctx: CellContext, rng: Rng) -> MR:
    """試行回数を増やすと相対度数が近づく値の意味を解釈する（g1_l59.knowledge Lv2）。"""
    p = ctx.spec_level.params
    n = int(draw(p["number_domain"], rng))
    statement = (
        f"びんのふたを{n}回より多く投げて表が出た相対度数を調べたところ、投げる回数を"
        f"増やすにつれてその値がしだいに一定の値に近づいた。この一定の値は何を表していると考えられるか"
    )

    solver = REGISTRY.solver("math.interpret_relative_frequency_limit")
    sol = cast(Solution, solver(None))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"n": n},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.interpret_relative_frequency_limit"),
    )


__all__ = [
    "relative_frequency_g1_recipe",
    "relative_frequency_g2_recipe",
    "probability_single_die_recipe",
    "probability_two_dice_recipe",
    "probability_ordered_selection_recipe",
    "probability_combination_selection_recipe",
    "probability_complement_recipe",
    "probability_at_least_one_recipe",
    "judge_equally_likely_recipe",
    "interpret_relative_frequency_limit_recipe",
]
