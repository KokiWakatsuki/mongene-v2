"""確率まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C12（確率）クラスタの非 visual セル群（g1_l59・g2_l51〜54）に対応する recipe を集約する。
乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

import itertools
import math
from collections.abc import Mapping
from functools import lru_cache
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
from engine.packs.math.recipes.polynomial import _domain_candidates


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# math.relative_frequency（g1_l59.calculation Lv1 / g2_l51.find_value Lv2）
# ---------------------------------------------------------------------------
# 相対度数の実験の回数（教科書は 100・500・1000 のようなきりのよい回数で調べる）。
_FREQUENCY_TOTALS = (50, 80, 100, 120, 150, 160, 200, 240, 250, 300, 320, 400,
                     480, 500, 600, 750, 800, 1000, 1200, 1250, 1500, 1600, 2000)
# 投げる道具と、その道具で実際に起こりうる相対度数の幅（千分率で持つ）。
# 「さいころを800回投げて1の目が756回出た（相対度数0.945）」は実験の記録として
# ありえない。**数が小さいだけでは足りず、値が場面に対して現実的である必要がある。**
_FREQUENCY_TOOLS: list[tuple[str, int, int]] = [
    ("びんのふた", 250, 750),
    ("画びょう", 250, 750),
    ("ペットボトルのふた", 250, 750),
    ("おはじき", 250, 750),
    ("10円硬貨", 450, 550),
]
# さいころの1の目（理論値 1/6 のまわり）。
# 幅は回数で縮む（`_frequency_pairs`）。ここは 100回のときの幅。
_DIE_FACE_BAND = (110, 230)


@lru_cache(maxsize=16)
def _frequency_pairs(
    totals: tuple[int, ...], lo_permille: int, hi_permille: int
) -> tuple[tuple[int, int], ...]:
    """相対度数が小数第3位までで書き切れ、かつ場面としてありうる幅に入る組。

    **幅は回数が増えるほど狭める。** 幅を回数と無関係に持っていたので
    「さいころを2000回投げて1の目が262回（相対度数 0.131）」が出ていた。
    実験の記録は回数が増えるほど理論値に寄る（これがこの単元の見せ場そのもの）。
    許す幅を「真ん中 ± 半幅 × sqrt(100/回数)」にすると、100回で元の幅、
    2000回では 1/4.5 の幅になり、教科書の表と同じ寄り方をする。
    """
    center = (lo_permille + hi_permille) / 2
    half = (hi_permille - lo_permille) / 2
    out: list[tuple[int, int]] = []
    for t in totals:
        shrink = min(1.0, (100 / t) ** 0.5)
        lo = center - half * shrink
        hi = center + half * shrink
        out.extend(
            (t, o)
            for o in range(1, t)
            if (1000 * o) % t == 0 and lo * t <= 1000 * o <= hi * t
        )
    return tuple(out)


def _draw_frequency_pair(
    p: Mapping[str, object], rng: Rng, band: tuple[int, int]
) -> tuple[int, int]:
    """(試行回数, 起こった回数)。**相対度数が小数で書き切れる組だけ**を引く。

    相対度数（確率の推定値）は小数で答えるのが教材の作法。前は回数を独立に
    引いていたので「1292回投げて726回 → 363/646」という、約分しても意味を
    持たない答えが出ていた（EVALUATION の D-19/D-24）。
    """
    totals = tuple(int(v) for v in cast("list[int]", p.get("total_set") or _FREQUENCY_TOTALS))
    cands = _frequency_pairs(totals, band[0], band[1])
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    return cands[idx]


_RELATIVE_FREQUENCY_G1_CONCEPTS = ["probability.relative_frequency_basic"]
_RELATIVE_FREQUENCY_G2_CONCEPTS = ["probability.relative_frequency_estimate"]


@register_recipe("math.relative_frequency_g1", provides_concepts=_RELATIVE_FREQUENCY_G1_CONCEPTS)
def relative_frequency_g1_recipe(ctx: CellContext, rng: Rng) -> MR:
    """さいころの相対度数（g1_l59.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    total, occurred = _draw_frequency_pair(p, rng, _DIE_FACE_BAND)
    # 相対度数を回数に応じて理論値へ寄せたぶん組が減るので、**どの目を調べたか**を
    # 軸に足す（実物の教科書の表も「1の目」「2の目」…と目ごとに調べている）。
    face = str(draw(["1", "2", "3", "4", "5", "6"], rng))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(occurred, total))

    statement = (
        f"さいころを{total}回投げたところ、{face}の目が{occurred}回出た。"
        f"{face}の目が出た相対度数を小数で求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": occurred, "total": total, "face": face},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.relative_frequency_g1"),
    )


@register_recipe("math.relative_frequency_g2", provides_concepts=_RELATIVE_FREQUENCY_G2_CONCEPTS)
def relative_frequency_g2_recipe(ctx: CellContext, rng: Rng) -> MR:
    """びんのふたなどの相対度数から確率を推定する（g2_l51.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    tool_index = int(draw({"int_set": list(range(len(_FREQUENCY_TOOLS)))}, rng))
    tool, lo, hi = _FREQUENCY_TOOLS[tool_index]
    total, occurred = _draw_frequency_pair(p, rng, (lo, hi))

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(occurred, total))

    condition = (
        f"ある{tool}を{total}回投げたところ、表が向いた回数が{occurred}回であった。"
        f"この結果から、この{tool}を投げたとき表が出る確率を小数で推定せよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": occurred, "total": total, "tool": tool},
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


# 大小2個のさいころの問い方（どれも教科書にある形）。(条件, 文の型) で持つ。
# **面数は6に固定した**（17面・20面のさいころは存在しない。D-13 と同じ）。
# 面数を広げるかわりに、問い方の種類で組み合わせを稼ぐ。
_TWO_DICE_QUESTIONS: list[tuple[str, str]] = [
    ("sum_equals", "出た目の和が{t}になる確率を、表を作って求めよ"),
    ("sum_at_least", "出た目の和が{t}以上になる確率を、表を作って求めよ"),
    ("sum_at_most", "出た目の和が{t}以下になる確率を、表を作って求めよ"),
    ("sum_multiple_of", "出た目の和が{t}の倍数になる確率を、表を作って求めよ"),
    ("product_equals", "出た目の積が{t}になる確率を求めよ"),
    ("product_at_least", "出た目の積が{t}以上になる確率を求めよ"),
    ("diff_equals", "出た目の差が{t}になる確率を求めよ"),
    ("at_least_one_equals", "少なくとも一方が{t}の目である確率を求めよ"),
]


def _construct_two_dice(rng: Rng, faces: int) -> tuple[str, int, str]:
    """条件（和・積・差・倍数・少なくとも一方）と目標値を構成する。

    該当数が 0 でも全数でもない（＝確率が 0 でも 1 でもない）組だけを残す。
    """
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    cands: list[tuple[str, int]] = []
    for kind, _text in _TWO_DICE_QUESTIONS:
        if kind in ("sum_equals", "sum_at_least", "sum_at_most"):
            targets = sorted({a + b for a, b in pairs})
        elif kind == "sum_multiple_of":
            targets = [2, 3, 4, 5, 6]
        elif kind in ("product_equals", "product_at_least"):
            targets = sorted({a * b for a, b in pairs})
        elif kind == "diff_equals":
            targets = list(range(0, faces))
        else:  # at_least_one_equals
            targets = list(range(1, faces + 1))
        for t in targets:
            n = len(_two_dice_favorable(pairs, kind, t))
            if 0 < n < len(pairs):  # 確率が 0 でも 1 でもない
                cands.append((kind, t))
    kind, target = cands[int(draw({"int_set": list(range(len(cands)))}, rng))]
    text = dict(_TWO_DICE_QUESTIONS)[kind].format(t=target)
    return kind, target, text


def _two_dice_favorable(pairs: list[tuple[int, int]], kind: str, t: int) -> list[tuple[int, int]]:
    """該当する目の組（solver と同じ判定。構成時に退化を外すためだけに使う）。"""
    if kind == "sum_equals":
        return [(a, b) for a, b in pairs if a + b == t]
    if kind == "sum_at_least":
        return [(a, b) for a, b in pairs if a + b >= t]
    if kind == "sum_at_most":
        return [(a, b) for a, b in pairs if a + b <= t]
    if kind == "sum_multiple_of":
        return [(a, b) for a, b in pairs if (a + b) % t == 0]
    if kind == "product_equals":
        return [(a, b) for a, b in pairs if a * b == t]
    if kind == "product_at_least":
        return [(a, b) for a, b in pairs if a * b >= t]
    if kind == "diff_equals":
        return [(a, b) for a, b in pairs if abs(a - b) == t]
    return [(a, b) for a, b in pairs if t in (a, b)]  # at_least_one_equals


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
# **樹形図で数えられる人数に戻したぶんを、場面と名前の軸で稼ぐ。**
# 前は人数を 4〜60 で振っていて「51人の生徒から…樹形図で数え」＝124,950通りを
# 樹形図でかけ、という破綻した指示が出ていた（EVALUATION の D-7）。
_SELECTION_GROUPS = ["生徒", "部員", "班のメンバー", "係の候補", "委員の候補"]
_SELECTION_PERSONS = ["さくら", "みなみ", "あおい", "ひなた", "ゆうと", "はると", "りく", "かえで"]


@register_recipe("math.probability_ordered_selection", provides_concepts=_ORDERED_SELECTION_CONCEPTS)
def probability_ordered_selection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """n人から役職を順に選ぶとき特定の1人が選ばれる確率を求める（g2_l53.find_value Lv2）。

    n（人数）に加え、選ぶ役職の数 r（2〜4）・対象の人が選ばれる役職の位置 target_index を
    構成時に振ることで、n だけに頼らず自由度を広げる（鉄則②。答えは常に 1/n で不変だが、
    構成そのものは相異なる場面として妥当）。
    """
    p = ctx.spec_level.params
    # **樹形図で数えられる規模に収める。** 人数を4〜6に絞っても、役職を4つにすると
    # 6P4 = 360通りになり「樹形図で数えて」という指示が成り立たない。
    # 実物は「4人から委員長と副委員長」12通り〜「6人から2人」30通りくらい。
    # 人数と役職の数を**組で**選ぶ（片方だけ絞っても組み合わせで破綻する）。
    pairs = [(n_, r_) for n_ in _domain_candidates(cast("dict[str, object]", p["n_domain"]))
             for r_ in (2, 3, 4)
             if r_ < n_ and math.perm(int(n_), r_) <= 30]
    idx = int(draw({"int_range": [0, len(pairs) - 1]}, rng))
    n, r = int(pairs[idx][0]), int(pairs[idx][1])
    target_index = int(draw({"int_range": [0, r - 1]}, rng))
    group = str(draw(_SELECTION_GROUPS, rng))
    person = str(draw(_SELECTION_PERSONS, rng))
    roles = "、".join(_ROLE_NAMES[:r])
    condition = (
        # 「りくさんが書記に選ばれる確率」を問う以上、その人が候補に入っていることを
        # 問題文が言わなければならない（前は n 人の中にいるかどうかが書かれていなかった）。
        f"{person}さんをふくむ{n}人の{group}から、{roles}を1人ずつ順に選ぶ。"
        # 「数え、…確率を求めよ」は**2つ答えさせている**とも読める。答えは確率ひとつ
        # なので、通り数が手段だと分かる「数えて」にする（逆翻訳で読み手が両方を書いた）。
        f"選び方は全部で何通りあるか樹形図で数えて、"
        f"{person}さんが{_ROLE_NAMES[target_index]}に選ばれる確率を求めよ"
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
        params={"n": n, "r": r, "target_index": target_index,
                "group": group, "person": person},
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
    """ある条件が起こる確率から、起こらない確率(余事象)を求める（g2_l54.find_value Lv2）。

    **さいころは6面。** 面数を 4〜30 で振っていたので「1から20までの目が出る
    さいころ」が出ていた（D-13 と同じ・存在しない道具）。面数を広げるかわりに、
    問い方の種類（和・積・差・倍数・少なくとも一方）で組み合わせを稼ぐ。
    それでも問題空間は数十通りなので、残りは `dup_rate_max` で宣言する。
    """
    p = ctx.spec_level.params
    faces = int(draw(p["faces_domain"], rng))
    pairs = list(itertools.product(range(1, faces + 1), range(1, faces + 1)))
    for _ in range(200):
        kind, target, text = _construct_two_dice(rng, faces)
        favorable = len(_two_dice_favorable(pairs, kind, target))
        p_num, p_den = favorable, len(pairs)
        # 余事象の答え 1−p の分子・分母が本文の数と衝突する組は外す（G-Q5t）。
        answer = sympy.Rational(p_den - p_num, p_den)
        if {int(answer.p), int(answer.q)} & {p_num, p_den, target, 1}:
            continue
        break
    else:
        raise ValueError("probability_complement_recipe: 漏洩しない組を構成できず")

    # 「〜になる確率を求めよ」を「〜になる確率が p である。〜にならない確率を求めよ」に組み替える。
    happens = text.split("確率")[0]
    condition = (
        f"大小2個のさいころを同時に投げるとき、{happens}確率が"
        f"{p_num}/{p_den}である。{happens}ことがない確率を求めよ"
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
        # **問い方も記録する。** 和・積・差・倍数のどれを問うたかが params に無いと、
        # 同じ確率になる別の問題を dup_key が同一とみなす（原則2）。
        params={"p_num": p_num, "p_den": p_den, "condition": kind, "target": target},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.probability_complement"),
    )


# ---------------------------------------------------------------------------
# math.probability_at_least_one（g2_l54.find_value Lv3）
# ---------------------------------------------------------------------------
_AT_LEAST_ONE_CONCEPTS = ["probability.at_least_one_via_complement"]


def _at_least_one_scenes() -> list[tuple[int, int, str]]:
    """「少なくとも1回」の場面の一覧（全事象の大きさ, 当たりの大きさ, 場面の文）。

    **どれも問題集に実在する道具**で、数も現実の範囲に収める
    （硬貨2面・さいころ6面・くじやカードや玉は本数を明示する）。

    数を現実に戻すと組み合わせが激減し、`dup_rate ≤ 0.20` を通せない
    （8場面まで減らしたとき 0.76 まで跳ねた）。閾値には約250通り要るので、
    **道具の中身の数を軸にして**稼ぐ——当たりの本数・はずれの本数・カードの枚数は
    どれも問題集が実際に振っているところなので、現実味を損なわずに増やせる。
    これが「定義域を広げる」のではなく「軸を増やす」ということ。
    """
    out: list[tuple[int, int, str]] = []
    out.append((2, 1, "{t}枚の硬貨を同時に投げるとき、少なくとも1枚は表が出る"))
    for fav, what in ((1, "1の目が出る"), (3, "偶数の目が出る"),
                      (2, "5以上の目が出る"), (2, "3の倍数の目が出る")):
        out.append((6, fav, f"1個のさいころを{{t}}回投げるとき、少なくとも1回は{what}"))
    for hit in (1, 2, 3, 4):
        for miss in range(2, 13):
            out.append((
                hit + miss, hit,
                f"当たりが{hit}本、はずれが{miss}本入っているくじがある。"
                f"1本引いてはもとにもどすことを{{t}}回くり返すとき、少なくとも1回は当たる",
            ))
    for n in (4, 5, 6, 8, 10, 12, 15, 20):
        out.append((n, 1, f"1から{n}までの番号が書かれたカードが1枚ずつある。"
                          f"1枚引いてはもとにもどすことを{{t}}回くり返すとき、"
                          f"少なくとも1回は1のカードを引く"))
        out.append((n, n // 2, f"1から{n}までの番号が書かれたカードが1枚ずつある。"
                               f"1枚引いてはもとにもどすことを{{t}}回くり返すとき、"
                               f"少なくとも1回は偶数のカードを引く"))
    # 玉の色は問題集が実際に振っているところ（赤白・青白・赤青）。数は小さいまま増える。
    for target, other in (("赤", "白"), ("青", "白"), ("赤", "青")):
        for hit in (1, 2, 3, 4):
            for rest in range(2, 9):
                out.append((
                    hit + rest, hit,
                    f"袋の中に{target}い玉が{hit}個、{other}い玉が{rest}個入っている。"
                    f"1個取り出してはもとにもどすことを{{t}}回くり返すとき、"
                    f"少なくとも1回は{target}い玉が出る",
                ))
    return out


_AT_LEAST_ONE_SCENES = _at_least_one_scenes()


@register_recipe("math.probability_at_least_one", provides_concepts=_AT_LEAST_ONE_CONCEPTS)
def probability_at_least_one_recipe(ctx: CellContext, rng: Rng) -> MR:
    """独立試行で少なくとも1回は条件が起こる確率を余事象で求める（g2_l54.find_value Lv3）。

    **道具は実在するものだけを使う。** 以前は「1から28までの目が出るさいころ」を作って
    いた——`faces` を 4〜30 で振らないと dup_rate が閾値を超えるから、という理由で
    （そのことが当時のコメントに書かれていた）。存在しない道具を出しては教材にならない。

    代わりに**場面**を軸にする。硬貨・さいころ・くじ・番号カードはどれも問題集に実在し、
    それぞれ「何が当たりか」の条件を持てるので、数を現実の範囲に保ったまま
    組み合わせが増える（`_AT_LEAST_ONE_SCENES` の直積 × 試行回数）。
    """
    p = ctx.spec_level.params
    # **場面と回数の組は「答えの分母が教材の大きさに収まる」ものだけ。**
    # 余事象の確率の分母は（全事象の大きさ）^（回数）なので、20枚のカードを4回
    # 引かせると 20⁴=160000 になる（実際 29679/160000 が出ていた）。
    # 教科書の上限は 6⁴=1296 あたり。
    trials_lo, trials_hi = (int(v) for v in p["trials_domain"]["int_range"])
    den_max = int(p.get("denominator_max", 1296))
    pairs = [
        (i, t)
        for i, (space_size, _fav, _ph) in enumerate(_AT_LEAST_ONE_SCENES)
        for t in range(trials_lo, trials_hi + 1)
        if space_size**t <= den_max
    ]
    scene_index, trials = pairs[int(draw({"int_set": list(range(len(pairs)))}, rng))]
    space_size, favorable_size, phrase = _AT_LEAST_ONE_SCENES[scene_index]
    condition = phrase.format(t=trials) + "確率を、余事象を利用して求めよ"

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
        # **場面も記録する。** くじ「当たり1本・はずれ4本」とカード「1〜5」は
        # どちらも (5, 1) になるので、大きさだけでは別の問題だと分からない。
        # 場面が params に出ていないと dup_key が話の違いを見落とす。
        params={
            "space_size": space_size, "favorable_size": favorable_size,
            "trials": trials, "scene": scene_index,
        },
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
# 「同様に確からしい」の判定は、教科書がたくさんの例を並べるところ。
# **場面を増やして組み合わせを稼ぐ**（カードの枚数を87枚まで広げるのはやめた。D-13）。
_EQUALLY_LIKELY_SCENARIOS: list[tuple[str, bool]] = [
    # 同様に確からしい（どの結果も対等）
    ("1枚の10円硬貨を投げて、表と裏のどちらが出るか", True),
    ("1個のさいころを投げて、1から6までのどの目が出るか", True),
    ("1から{n}までの番号が書かれたカードから1枚を引いて、どの番号が出るか", True),
    ("同じ大きさの玉が{n}個入った袋から1個取り出して、どの玉が出るか", True),
    ("よく切った{n}枚のカードから1枚引いて、どのカードが出るか", True),
    ("1から{n}までの目が等しい幅で並んだルーレットを回して、どの目が止まるか", True),
    ("同じ大きさのビー玉{n}個から1個を選んで、どのビー玉が選ばれるか", True),
    ("番号の書かれた同じ大きさの球{n}個が入った抽選器から1個出して、どの球が出るか", True),
    # 同様に確からしいとはいえない（結果ごとに起こりやすさが違う）
    ("画びょうを1個投げて、上向きと下向きのどちらになるか", False),
    ("形のいびつなさいころを投げて、どの目が出るか", False),
    ("当たりが1本だけ入っている{n}本のくじから1本引いて、当たりか外れか", False),
    ("2枚の10円硬貨を同時に投げて、表の出る枚数が0枚・1枚・2枚のどれになるか", False),
    ("びんのふたを1個投げて、上向きと下向きのどちらになるか", False),
    ("大小2個のさいころを投げて、出た目の和が2から12までのどれになるか", False),
    ("大きさの違う玉が{n}個入った箱から1個取り出して、どの玉が出るか", False),
    ("赤玉1個と白玉{n}個が入った袋から1個取り出して、赤と白のどちらが出るか", False),
]


@register_recipe("math.judge_equally_likely", provides_concepts=_JUDGE_EQUALLY_LIKELY_CONCEPTS)
def judge_equally_likely_recipe(ctx: CellContext, rng: Rng) -> MR:
    """場面が「同様に確からしい」かを判別する（g2_l51.knowledge Lv2・answer-first）。"""
    idx = int(draw({"int_range": [0, len(_EQUALLY_LIKELY_SCENARIOS) - 1]}, rng))
    template, is_equally_likely = _EQUALLY_LIKELY_SCENARIOS[idx]
    # カードや玉の個数は教材の大きさに（87枚のカードは教材にならない。D-13 と同じ）。
    n = int(draw({"int_range": [3, 30]}, rng))
    scene = template.format(n=n) if "{n}" in template else template
    # **場面だけで切らない。** 前は「…17本のくじから1本引いて、当たりか外れか。」で
    # 問題文が終わっていて、生徒はどこにも「同様に確からしいか」と聞かれていなかった
    # （選択肢を見て初めて何を問われているか分かる状態）。問いを本文に書く。
    statement = f"{scene}。この場面で、起こりうる結果は同様に確からしいといえるか"

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
    # 回数を教材の粒度（きりのよい回数）に絞った分、道具で広さを戻す。
    tool = str(draw(["びんのふた", "画びょう", "ペットボトルのふた", "おはじき",
                     "10円硬貨", "コイン", "紙コップ", "消しゴム"], rng))
    face = str(draw(["表", "上向き"], rng))
    statement = (
        # 「{n}回より多く投げて」は重複率のために足した無意味な条件だった
        # （投げた回数は答え＝相対度数が近づく値の意味に関係しない）。
        f"{tool}を{n}回投げて{face}になった相対度数を調べたところ、投げる回数を"
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
        # surface も params に載せる（載せないと dup_key から見えない）。
        params={"n": n, "tool": tool, "face": face},
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
