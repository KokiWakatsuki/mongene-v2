"""度数分布・代表値まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C11（データ・統計）クラスタのうち g1_l54〜g1_l57 の非 visual セル群に対応する recipe を
集約する。乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

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


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _as_unimodal(freqs: list[int], rng: Rng) -> list[int]:
    """度数を**山が1つ**の並びに直す（値は変えず並べ替えるだけ）。

    階級ごとに独立に引くと 3・12・2・8 のようなギザギザの表になる。実物の度数分布は
    ほぼ単峰で、生徒が「分布の形」を読み取れるのはそのため。大きい順に取り出して
    山の左右へ交互に置くと必ず単峰になる（`distribution_chart._as_unimodal` と同じ手）。
    """
    vals = sorted(freqs, reverse=True)
    left: list[int] = []
    right: list[int] = []
    flip = int(draw({"int_range": [0, 1]}, rng))
    for i, v in enumerate(vals[1:]):
        (left if (i + flip) % 2 == 0 else right).append(v)
    return [*reversed(left), vals[0], *right]


def _draw_frequency_table(
    rng: Rng, p: dict[str, object], n_classes: int
) -> tuple[int, int, list[int]]:
    """度数分布表の（下端, 階級の幅, 度数列）を引く。

    **階級の幅は候補から引き、下端はその幅の倍数にする。** 前は幅を 5〜10 の整数、
    下端を 0〜20 の整数から独立に引いていたので「3分以上13分未満」（幅10なのに
    3から始まる）や「7分以上16分未満」（幅9）が出て、階級値が 77/2 のような
    分数になっていた。実物の度数分布表は 0・10・20…のように区切りのいい所から
    始まり、幅は 5・10・20 のどれかである。

    **度数は単峰に並べ替える。** 独立に引くと 3・12・2・8 のギザギザになる。
    """
    width = int(draw(p["class_width_candidates"], rng))
    start_max = int(p.get("class_start_max", 0))
    starts = [v for v in range(0, start_max + 1, width)] or [0]
    start = int(draw({"int_set": starts}, rng))
    freqs = _as_unimodal(
        [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)], rng
    )
    return start, width, freqs


def _format_frequency_table_text(start: int, width: int, freqs: list[int], unit: str) -> str:
    parts = []
    for i, f in enumerate(freqs):
        lo = start + width * i
        hi = lo + width
        parts.append(f"{lo}{unit}以上{hi}{unit}未満…{f}人")
    return "、".join(parts)


# ---------------------------------------------------------------------------
# g1_l54.calculation Lv1: 階級値・度数の合計
# ---------------------------------------------------------------------------
_FREQUENCY_TABLE_VALUE_CONCEPTS = ["frequency_table.compute_value"]


@register_recipe("math.frequency_table_value", provides_concepts=_FREQUENCY_TABLE_VALUE_CONCEPTS)
def frequency_table_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """度数分布表の階級値・度数の合計を求める（g1_l54.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n_classes = 4
    start, width, freqs = _draw_frequency_table(rng, cast("dict[str, object]", p), n_classes)
    target_index = int(draw({"int_range": [0, n_classes - 1]}, rng))

    solver = REGISTRY.solver("math.frequency_table_value")
    sol = cast(Solution, solver(start, width, freqs, target_index))
    assert isinstance(sol.answer, SymbolicAnswer)

    table_text = _format_frequency_table_text(start, width, freqs, "分")
    lo = start + width * target_index
    hi = lo + width
    statement = (
        f"次の度数分布表について、{lo}分以上{hi}分未満の階級の階級値を求めよ。"
        f"また、度数の合計を求めよ。〔階級と度数：{table_text}〕"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"class_start": start, "class_width": width, "frequencies": freqs, "target_index": target_index},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.frequency_table_value"),
    )


# ---------------------------------------------------------------------------
# g1_l55.calculation Lv1: 1階級の相対度数（既存 math.relative_frequency を再利用）
# ---------------------------------------------------------------------------
# 度数分布表の総度数（きりのよい人数で調べる）。相対度数が小数で書き切れる組だけを引く。
# 相対度数を小数第2位までに絞ったぶん、総度数の候補を増やして組を確保する。
_STATS_TOTALS = (20, 25, 40, 50, 60, 75, 80, 100, 120, 125, 150, 160, 175,
                 200, 240, 250, 300, 400, 500)


# 1つの階級が占める割合の上限・下限。
# **割り切れるかどうかだけを見ていたので「125人のうち109人」（相対度数 0.872）が出た。**
# 1つの階級に87%が入る度数分布は、階級に分ける意味がない。実物の度数分布表で
# 1階級が占めるのは 0.05〜0.45 くらい（階級は4〜6個）。
_CLASS_SHARE = (0.04, 0.45)


@lru_cache(maxsize=4)
def _stats_frequency_pairs(totals: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    """相対度数が**小数第2位まで**で書ける組（`(100·o) % t == 0`）。

    前は第3位まで許していたので「125人のうち29人 → 0.232」が出ていた。
    実物の度数分布表の相対度数は 0.35・0.20 と2桁で書く（合計が 1.00 になる表を
    作るため、教科書はそもそも総度数を 20・25・40・50 のようにとる）。
    """
    lo, hi = _CLASS_SHARE
    return tuple(
        (t, o)
        for t in totals
        for o in range(1, t)
        if (100 * o) % t == 0 and lo <= o / t <= hi
    )


def _draw_frequency_pair(p: Mapping[str, object], rng: Rng) -> tuple[int, int]:
    totals = tuple(int(v) for v in cast("list[int]", p.get("total_set") or _STATS_TOTALS))
    cands = _stats_frequency_pairs(totals)
    return cands[int(draw({"int_set": list(range(len(cands)))}, rng))]


_RELATIVE_FREQUENCY_STATS_CONCEPTS = ["relative_frequency.compute_single"]


@register_recipe("math.relative_frequency_stats_single", provides_concepts=_RELATIVE_FREQUENCY_STATS_CONCEPTS)
def relative_frequency_stats_single_recipe(ctx: CellContext, rng: Rng) -> MR:
    """度数分布表の1階級の相対度数を求める（g1_l55.calculation Lv1・answer-first）。

    **相対度数は小数で答えるのが教材の作法**（D-19/D-24）。総度数と度数を独立に
    引いていたので「123人のうち72人 → 24/41」という、割合として使えない答えが
    出ていた。割合が小数第3位までで書き切れる組だけを引く。
    """
    p = ctx.spec_level.params
    total, occurred = _draw_frequency_pair(p, rng)

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(occurred, total))

    statement = (
        f"{total}人のうち、ある階級の度数が{occurred}人であった。"
        "この階級の相対度数を小数で求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": occurred, "total": total},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.relative_frequency_stats_single"),
    )


# ---------------------------------------------------------------------------
# g1_l55.calculation Lv2: 総度数の異なる2集団の相対度数を比較する
# ---------------------------------------------------------------------------
_COMPARE_RELATIVE_FREQUENCY_CONCEPTS = ["relative_frequency.compare_groups"]
_SCHOOL_NAMES = ["A中学", "B中学", "C中学", "D中学"]


@register_recipe("math.compare_relative_frequency", provides_concepts=_COMPARE_RELATIVE_FREQUENCY_CONCEPTS)
def compare_relative_frequency_recipe(ctx: CellContext, rng: Rng) -> MR:
    """総度数の異なる2集団の相対度数を求め比較する（g1_l55.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    # **相対度数は小数で答える**（EVALUATION D-24）。度数を独立に引いていたので
    # 「A: 27/40、B: 7/30」という、割合として比べにくい答えが出ていた。
    # 割合が小数第3位までで書き切れる度数だけを引く。
    total_a = int(draw(p["total_domain"], rng))
    total_b = int(draw({"int_set": [v for v in _domain_int_set(p["total_domain"]) if v != total_a]}, rng))
    # 1階級が占める割合の上限も要る（`_CLASS_SHARE`）。割り切れるかだけを見ていたので
    # 「通学時間1〜10分の階級に 27/40（68%）と 21/30（70%）」＝全員が10分未満の学校、
    # という度数分布が出ていた。
    share_lo, share_hi = _CLASS_SHARE
    freq_a = int(draw({"int_set": [f for f in range(1, total_a)
                                   if (1000 * f) % total_a == 0
                                   and share_lo <= f / total_a <= share_hi]}, rng))
    # **相対度数が同じになる組は除く。** 「A: 0.4、B: 0.4」なのに答えが
    # 「Bのほうが大きい」になっていた（solver が非厳密比較で B を返す）。
    # 割合が等しい場合は「どちらが大きいか」という問い自体が成り立たない。
    freq_b = int(draw({"int_set": [f for f in range(1, total_b)
                                   if (1000 * f) % total_b == 0
                                   and share_lo <= f / total_b <= share_hi
                                   and f * total_a != freq_a * total_b]}, rng))
    name_a, name_b = _SCHOOL_NAMES[0], _SCHOOL_NAMES[1]
    # **階級は幅の倍数の所から始める。** 前は下端 0〜40・幅 5〜10 を独立に引いていて
    # 「10分以上17分未満」「31分以上40分未満」が出ていた。実物の階級は
    # 0・10・20…から始まり、幅は 5・10 のどれか。
    width = int(draw(p["class_width_candidates"], rng))
    lo = int(draw({"int_set": list(range(0, int(p["class_lo_max"]) + 1, width))}, rng))
    hi = lo + width

    solver = REGISTRY.solver("math.compare_relative_frequency")
    sol = cast(Solution, solver(freq_a, total_a, freq_b, total_b))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"{name_a}は生徒{total_a}人、{name_b}は生徒{total_b}人で通学時間を調べた。"
        f"{lo}分以上{hi}分未満の階級の度数が{name_a}は{freq_a}人、{name_b}は{freq_b}人であった。"
        f"それぞれの相対度数を求め、この階級の割合が大きいのはどちらの中学か答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"freq_a": freq_a, "total_a": total_a, "freq_b": freq_b, "total_b": total_b},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.compare_relative_frequency"),
    )


def _domain_int_set(spec: object) -> list[int]:
    d = cast("dict[str, object]", spec)
    if "int_set" in d:
        return [int(str(v)) for v in cast("list[object]", d["int_set"])]
    lo, hi = cast("list[int]", d["int_range"])
    return list(range(lo, hi + 1))


# ---------------------------------------------------------------------------
# g1_l56.calculation Lv1: 累積度数
# ---------------------------------------------------------------------------
_CUMULATIVE_FREQUENCY_CONCEPTS = ["cumulative_frequency.compute"]


@register_recipe("math.cumulative_frequency_value", provides_concepts=_CUMULATIVE_FREQUENCY_CONCEPTS)
def cumulative_frequency_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """指定した階級までの累積度数を求める（g1_l56.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n_classes = 4
    start, width, freqs = _draw_frequency_table(rng, cast("dict[str, object]", p), n_classes)
    target_index = int(draw({"int_range": [1, n_classes - 1]}, rng))

    solver = REGISTRY.solver("math.cumulative_frequency_value")
    sol = cast(Solution, solver(freqs, target_index))
    assert isinstance(sol.answer, SymbolicAnswer)

    table_text = _format_frequency_table_text(start, width, freqs, "分")
    # **「〜の階級まで」が指すのは、対象の階級そのものの区間。**
    # 前は下端を表の先頭に固定していたので「20分以上60分未満の階級まで」と書いていた
    # ——20〜60 は階級ではない（表の階級は 20〜30・30〜40…）。実物は
    # 「40分以上50分未満の階級までの累積度数」と、最後に足す階級の名前で書く。
    lo = start + width * target_index
    hi = lo + width
    statement = (
        f"次の度数分布表で、{lo}分以上{hi}分未満の階級までの累積度数を求めよ。"
        f"〔階級と度数：{table_text}〕"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"frequencies": freqs, "target_index": target_index},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.cumulative_frequency_value"),
    )


# ---------------------------------------------------------------------------
# g1_l56.calculation Lv2: 累積相対度数・以上の割合(%)
# ---------------------------------------------------------------------------
_CUMULATIVE_RELATIVE_FREQUENCY_CONCEPTS = ["cumulative_frequency.compute_relative_and_complement"]


@register_recipe(
    "math.cumulative_relative_frequency_and_complement",
    provides_concepts=_CUMULATIVE_RELATIVE_FREQUENCY_CONCEPTS,
)
def cumulative_relative_frequency_and_complement_recipe(ctx: CellContext, rng: Rng) -> MR:
    """累積相対度数と超える部分の割合(%)を求める（g1_l56.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    total = int(draw(p["total_domain"], rng))
    n_classes = 4
    # 各階級に重みをつけて total を按分し、単調でない自然な分布を構成する（合計は total で不変）。
    weights = [int(draw({"int_range": [1, 5]}, rng)) for _ in range(n_classes)]
    wsum = sum(weights)
    freqs = [max(1, round(total * w / wsum)) for w in weights]
    freqs[-1] += total - sum(freqs)
    if freqs[-1] < 1:
        base = total // n_classes
        freqs = [base] * n_classes
        for i in range(total - base * n_classes):
            freqs[i] += 1
    # 按分の重みを独立に引くと 18・27・9・46 のようなギザギザになる。実物の睡眠時間の
    # 分布は単峰（真ん中の階級がいちばん多い）なので、値を変えずに並べ替える。
    freqs = _as_unimodal(freqs, rng)
    target_index = int(draw({"int_range": [0, n_classes - 2]}, rng))
    # 階級を「1区間目…」と書き、境界の時刻を別に引いていたので、どの区間が
    # 「8時間未満」なのかが表から読めず、問題として解けなかった。階級に実際の
    # 時間の範囲を書き、境界はその階級の上端として導く。
    start_hour = int(draw(p["start_domain"], rng))
    boundary_hour = start_hour + target_index + 1

    solver = REGISTRY.solver("math.cumulative_relative_frequency_and_complement")
    sol = cast(Solution, solver(freqs, target_index))
    assert isinstance(sol.answer, SymbolicAnswer)

    table_text = "、".join(
        f"{start_hour + i}時間以上{start_hour + i + 1}時間未満…{f}人"
        for i, f in enumerate(freqs)
    )
    statement = (
        f"生徒{total}人の睡眠時間を調べた度数分布表がある。{boundary_hour}時間未満の生徒までの"
        f"累積相対度数を求めよ。また、睡眠時間が{boundary_hour}時間以上の生徒は全体の何％か求めよ。"
        f"〔階級と度数：{table_text}〕"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"frequencies": freqs, "target_index": target_index},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.cumulative_relative_frequency_and_complement"),
    )


# ---------------------------------------------------------------------------
# g1_l57.calculation Lv1: 生データから平均値・中央値・最頻値
# ---------------------------------------------------------------------------
_REPRESENTATIVE_VALUES_RAW_CONCEPTS = ["representative_value.compute_raw"]


@register_recipe("math.representative_values_raw", provides_concepts=_REPRESENTATIVE_VALUES_RAW_CONCEPTS)
def representative_values_raw_recipe(ctx: CellContext, rng: Rng) -> MR:
    """生データの平均値・中央値・最頻値を求める（g1_l57.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(p["n_domain"], rng))
    # 一意な最頻値を保証するため、まず相異なる値を n-1 個引き、うち1つを複製する。
    pool = _domain_int_set(p["value_domain"])
    rng_state = rng
    distinct = []
    remaining = list(pool)
    for _ in range(n - 2):
        v = int(draw({"int_set": remaining}, rng_state))
        distinct.append(v)
        remaining = [x for x in remaining if x != v]
    dup_value = int(draw({"int_set": distinct}, rng_state))
    # **最後の1つは、平均値が割り切れる値だけから引く。**（EVALUATION D-28 と同じ根。
    # 値を独立に引いていたので合計271・個数8で「平均値 271/8」という、教材にならない
    # 答えが出ていた。定義域は狭めず、**答えの大きさ側で**割り切れる組に限る。）
    partial = sum(distinct) + dup_value
    divisible = [v for v in remaining if (partial + v) % n == 0]
    last = int(draw({"int_set": divisible or remaining}, rng_state))
    distinct.append(last)
    data = distinct + [dup_value]
    # 出現順をシャッフル（辞書順そのままだと surface が単調になりやすいので軽く混ぜる）。
    for i in range(len(data) - 1, 0, -1):
        j = int(draw({"int_range": [0, i]}, rng_state))
        data[i], data[j] = data[j], data[i]

    solver = REGISTRY.solver("math.representative_values_raw")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = f"次の{n}個のデータの平均値・中央値・最頻値をそれぞれ求めよ。〔{data_text}〕"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.representative_values_raw"),
    )


# ---------------------------------------------------------------------------
# g1_l57.calculation Lv2: 度数分布表から階級値を用いて平均値を求める
# ---------------------------------------------------------------------------
_MEAN_FROM_GROUPED_TABLE_CONCEPTS = ["representative_value.compute_grouped_mean"]


@register_recipe("math.mean_from_grouped_table", provides_concepts=_MEAN_FROM_GROUPED_TABLE_CONCEPTS)
def mean_from_grouped_table_recipe(ctx: CellContext, rng: Rng) -> MR:
    """度数分布表の階級値を用いて平均値を求める（g1_l57.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    n_classes = 4
    # **平均値が小数で書き切れる度数の組だけを引く。** 度数を独立に引いていたので
    # 合計が23人になり「平均値 694/23」という、教材にならない答えが出ていた
    # （教科書は度数の合計を割り切れる人数にとる）。
    solver = REGISTRY.solver("math.mean_from_grouped_table")
    for _ in range(200):
        start, width, freqs = _draw_frequency_table(rng, cast("dict[str, object]", p), n_classes)
        sol = cast(Solution, solver(start, width, freqs))
        assert isinstance(sol.answer, SymbolicAnswer)
        mean = sympy.Rational(sympy.sympify(sol.answer.srepr))
        q = int(mean.q)
        while q % 2 == 0:
            q //= 2
        while q % 5 == 0:
            q //= 5
        if q == 1 and mean.q in (1, 2, 4, 5, 10, 20):  # 小数第2位までで書き切れる
            break
    else:
        raise ValueError("mean_from_grouped_table_recipe: 平均が小数になる度数を構成できず")

    table_text = _format_frequency_table_text(start, width, freqs, "点")
    statement = f"次の度数分布表について、各階級の階級値を用いて平均値を求めよ。〔階級と度数：{table_text}〕"

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"class_start": start, "class_width": width, "frequencies": freqs},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.mean_from_grouped_table"),
    )


# ---------------------------------------------------------------------------
# g1_l57.knowledge Lv2: 分布の特徴に応じて適切な代表値を判別する
# ---------------------------------------------------------------------------
_JUDGE_APPROPRIATE_REPRESENTATIVE_VALUE_CONCEPTS = ["representative_value.judge_appropriate"]
# 人数を教材の数（きりのよい人数）に絞ったぶん、場面の種類で組合せを戻す。
_REPRESENTATIVE_VALUE_SCENARIOS: list[tuple[str, bool]] = [
    ("少数の非常に高い値が混じっている{n}人の年収のデータ", True),
    ("少数のきわめて大きい記録が混じっている{n}人の資産額のデータ", True),
    ("1つだけ極端に大きい値が混じっている{n}人のテストの得点のデータ", True),
    ("1人だけ飛びぬけて長い{n}人の通学時間のデータ", True),
    ("少数のとても大きい値が混じっている{n}人の1か月の読書時間のデータ", True),
    ("1つだけ極端に大きい記録が混じっている{n}人のハンドボール投げの記録のデータ", True),
    ("少数のきわめて高い値が混じっている{n}世帯の貯蓄額のデータ", True),
    ("{n}人の身長がどれも近い範囲に集まっているデータ", False),
    ("{n}人の体重が大きく偏りなく分布しているデータ", False),
    ("{n}人の通学時間がどれも近い範囲に集まっているデータ", False),
    ("{n}人の握力の記録がどれも近い範囲に集まっているデータ", False),
    ("{n}人の反復横とびの記録が大きく偏りなく分布しているデータ", False),
    ("{n}人の睡眠時間がどれも近い範囲に集まっているデータ", False),
    ("{n}人の数学のテストの得点が大きく偏りなく分布しているデータ", False),
]


@register_recipe(
    "math.judge_appropriate_representative_value",
    provides_concepts=_JUDGE_APPROPRIATE_REPRESENTATIVE_VALUE_CONCEPTS,
)
def judge_appropriate_representative_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """分布の特徴から適切な代表値を判別する（g1_l57.knowledge Lv2・answer-first）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_range": [0, len(_REPRESENTATIVE_VALUE_SCENARIOS) - 1]}, rng))
    template, has_outliers = _REPRESENTATIVE_VALUE_SCENARIOS[idx]
    n = int(draw(p["n_domain"], rng))
    scenario = template.format(n=n)

    solver = REGISTRY.solver("math.judge_appropriate_representative_value")
    sol = cast(Solution, solver(has_outliers))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = f"{scenario}で、集団の「まん中あたり」を表す代表値としては平均値と中央値のどちらが適切か、理由とともに答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"scenario_index": idx, "n": n, "has_outliers": str(has_outliers)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_appropriate_representative_value"),
    )
