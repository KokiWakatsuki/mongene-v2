"""統計的な探究（データの比較・標本調査の判断）の recipe（構成的生成・answer-first）。

C11 の word_problem クラスタ5セルを1つの recipe が mode で賄う:
  g1_l58 Lv2  誘導あり3小問（平均値 → 範囲 → どちらが安定しているか）
  g1_l58 Lv3  誘導ゆるい（どの代表値で比べても同じ結論になる＝指標を自分で選べる）
  g1_l58 Lv4  誘導なし（探究の進め方を3つから選ぶ）
  g3_l57 Lv2  全数調査か標本調査かを判断する
  g3_l58 Lv2  偏りの生じにくい抽出方法を選ぶ

## 「理由を書いて答えよ」をどう採点可能にしたか

結論を選択（ChoiceAnswer）で答えさせ、根拠の組み立ては solution_steps が担う。
箱ひげ図の記述セル（g2_l57.word_problem）・作問セル（g1_l27 Lv4）と同じ手にそろえる。

## params に何を置いたか

`numbers` は**本文に現れる数がすべて**（word_problem の params 忠実性契約）。
データ列が本文に出るセル（Lv2/Lv3）は、列の各値を `a01`, `a02`, … / `b01`, … という
キーで `numbers` に載せる。**列を `data_a`/`data_b` として別に持つと、`numbers` が
空のまま本文に数字が出て契約違反になる**（実際にそれで落とした）。checker は
`numbers` からキー順に列を組み直すので、真実は1か所だけ（二重管理にしない）。

判断を問うセル（標本調査・調べ方の選択）は、母集団の大きさだけが本文の数なので
`numbers` は `population` ひとつ。
"""
from __future__ import annotations

from typing import Any, cast

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

_CONCEPTS = [
    "data_inquiry.compare_mean_and_range",
    "data_inquiry.choose_statistic",
    "data_inquiry.design_plan",
    "sample_survey.judge_method_word_problem",
    "sample_survey.choose_unbiased_word_problem",
]


def _tags(ctx: CellContext) -> dict[str, list[str]]:
    return {
        "concept_tags": list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
        "cause_tags": list(ctx.spec_level.cause_tags),
    }


def _sub(ctx: CellContext, label: str, sol: Solution) -> SubQuestionMR:
    return SubQuestionMR(
        label=label, asked="value", answer=sol.answer, steps=sol.steps, **_tags(ctx)
    )


def _mr(
    ctx: CellContext, *, params: dict[str, Any], given: dict[str, str],
    context_slots: dict[str, str], subs: list[SubQuestionMR],
) -> MR:
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given=given,
        context_slots=context_slots,
        sub_questions=subs,
        visual_plan=None,
        provenance=Provenance(recipe="math.statistics_inquiry"),
    )


def data_numbers(data_a: list[int], data_b: list[int]) -> dict[str, str]:
    """データ列を `numbers`（本文に出ている数）の形にする。

    キーは `a01`,`a02`,…/`b01`,… とゼロ詰めにして、キー順に並べ直せば元の列に戻る
    ようにする（checker が使う）。列を別キーで二重に持たないための単一の真実。
    """
    out = {f"a{i + 1:02d}": str(v) for i, v in enumerate(data_a)}
    out.update({f"b{i + 1:02d}": str(v) for i, v in enumerate(data_b)})
    return out


def lists_from_numbers(numbers: dict[str, str]) -> tuple[list[int], list[int]]:
    """`numbers` からデータ列を組み直す（recipe と checker が共有）。"""
    a = [int(numbers[k]) for k in sorted(numbers) if k.startswith("a")]
    b = [int(numbers[k]) for k in sorted(numbers) if k.startswith("b")]
    return a, b


def _draw_population(p: dict[str, Any], rng: Rng) -> int:
    """母集団の大きさ。場面として自然な情報であると同時に dup の第2の軸。

    判断を問うセル（全数か標本か・どの抽出方法か・どの調べ方か）は、場面の種類が
    十数通りしかなく、それだけでは 100seed で dup≤0.20 に届かない
    （BRIEF「★単一パラメータのセルは原理的に通らない」）。母集団の大きさは答えを
    変えない（判断の根拠は「全部調べられるか」「同じ機会で選ばれるか」）ので、
    第2の軸として安全に足せる。
    """
    lo, hi, step = (int(v) for v in p["population_range"])
    return int(draw({"int_set": list(range(lo, hi + 1, step))}, rng))


def _draw_stable_pair(p: dict[str, Any], rng: Rng) -> tuple[list[int], list[int]]:
    """平均が等しく、範囲が相異なる2つのデータ（安定しているほうが一意に決まる）。

    【構成】共通の平均 m と個数 n を引き、A は m を中心に幅 wa、B は幅 wb（wa<wb）で
    対称に振る。対称に振るので平均は必ず m に一致し、範囲は 2·w になる。
    ＝「平均は同じなのに散らばりが違う」という、この設問がいちばん見せたい形。
    """
    n = int(draw({"int_set": [int(v) for v in p["size_set"]]}, rng))
    mean = int(draw({"int_range": [int(v) for v in p["mean_range"]]}, rng))
    wa = int(draw({"int_set": [int(v) for v in p["narrow_set"]]}, rng))
    wb = int(draw({"int_set": [v for v in (int(x) for x in p["wide_set"]) if v > wa]}, rng))

    def build(width: int, seed_shift: int) -> list[int]:
        """平均がちょうど mean・範囲がちょうど 2·width になるデータを作る。

        平均から ±k だけずれた値を**対にして**入れるので、平均は必ず mean に戻る。
        k には width を必ず1回入れる（範囲を 2·width にするため）。残りは 1..width
        から引くので、値が2種類だけに潰れず教科書のデータらしい散らばりになる。
        """
        half = n // 2
        offsets = [width]
        for i in range(half - 1):
            k = int(draw({"int_range": [1, width]}, rng)) if width > 1 else 1
            offsets.append(k if (i + seed_shift) % 2 == 0 else max(1, width - k + 1))
        vals: list[int] = []
        for k in offsets:
            vals.extend([mean - k, mean + k])
        if n % 2:
            vals.append(mean)
        return vals

    return build(wa, 0), build(wb, 1)


def _draw_agreeing_pair(p: dict[str, Any], rng: Rng) -> tuple[list[int], list[int]]:
    """平均値・中央値・最頻値のすべてが同じ側を指す2つのデータ。

    【構成】A のすべての値が B のすべての値より小さくなるように作る（帯を分ける）。
    こうすると3つの代表値は必ず同じ側になり、「どの指標を選んでもよい」が成り立つ。
    各データは中央の値を多数派にして最頻値を一意にする。
    """
    n = int(draw({"int_set": [int(v) for v in p["size_set"]]}, rng))
    base = int(draw({"int_range": [int(v) for v in p["base_range"]]}, rng))
    gap = int(draw({"int_set": [int(v) for v in p["gap_set"]]}, rng))
    spread = int(draw({"int_set": [int(v) for v in p["spread_set"]]}, rng))

    def build(center: int) -> list[int]:
        """中央の値を多数派にして最頻値を一意にしつつ、値が数種類は出るようにする。"""
        vals = [center] * (n - 4)
        vals += [center - spread, center + spread, center - 1, center + 1]
        return vals

    return build(base), build(base + gap)


@register_recipe("math.statistics_inquiry", provides_concepts=_CONCEPTS)
def statistics_inquiry_recipe(ctx: CellContext, rng: Rng) -> MR:
    """C11 の word_problem 5セルを mode で切り替える。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    mode = str(p["mode"])

    if mode == "compare_mean_range":
        data_a, data_b = _draw_stable_pair(p, rng)
        # 候補には敬称を含めない（本文側で「さん」を付けるため、二重にならないように）。
        names = str(draw(list(p["person_pair_set"]), rng)).split("|")
        subject = str(draw(list(p["subject_set"]), rng))
        mean_sol = cast(Solution, REGISTRY.solver("math.datasets_mean_pair")(data_a, data_b))
        range_sol = cast(Solution, REGISTRY.solver("math.datasets_range_pair")(data_a, data_b))
        judge_sol = cast(Solution, REGISTRY.solver("math.judge_more_stable")(data_a, data_b))
        scenario = (
            f"{names[0]}さんと{names[1]}さんの{subject}の記録が次のようにまとめられている。"
            f"A（{names[0]}さん）: {'、'.join(str(v) for v in data_a)}／"
            f"B（{names[1]}さん）: {'、'.join(str(v) for v in data_b)}"
        )
        return _mr(
            ctx,
            params={"mode": mode, "numbers": data_numbers(data_a, data_b)},
            given={"scenario": scenario},
            context_slots={
                "ask_1": "AとBそれぞれの平均値を求めよ。",
                "ask_2": "AとBそれぞれの範囲（最大値と最小値の差）を求めよ。",
                "ask_3": "(1)(2)をもとに、記録が安定しているのはAとBのどちらといえるか、記号で答えよ。",
            },
            subs=[
                _sub(ctx, "(1)", mean_sol),
                _sub(ctx, "(2)", range_sol),
                _sub(ctx, "(3)", judge_sol),
            ],
        )

    if mode == "choose_statistic":
        data_a, data_b = _draw_agreeing_pair(p, rng)
        smaller = bool(p["smaller_is_better"])
        subject = str(draw(list(p["subject_set"]), rng))
        sol = cast(
            Solution,
            REGISTRY.solver("math.judge_group_by_any_statistic")(data_a, data_b, smaller),
        )
        scenario = (
            f"A組とB組の{subject}の記録が次のようにまとめられている。"
            f"A組: {'、'.join(str(v) for v in data_a)}／"
            f"B組: {'、'.join(str(v) for v in data_b)}"
        )
        goal = str(p["goal_phrase"])
        return _mr(
            ctx,
            params={
                "mode": mode, "smaller_is_better": smaller,
                "numbers": data_numbers(data_a, data_b),
            },
            given={"scenario": scenario},
            context_slots={
                "ask_value": (
                    f"どちらの組のほうが{goal}といえるか、着目する代表値を自分で選び、"
                    "その値を求めたうえで記号で答えよ。"
                )
            },
            subs=[_sub(ctx, "(1)", sol)],
        )

    if mode == "design_plan":
        scene = str(draw(list(p["question_set"]), rng)).split("|")
        question, valid, bad1, bad2 = scene
        labels = [bad1, valid, bad2]
        flags = [0, 1, 0]
        # 母集団の大きさ。場面として自然な情報であると同時に、dup の第2の軸になる
        # （場面の種類だけだと候補が十数通りしかなく、100seed で dup≤0.20 に届かない）。
        size = _draw_population(p, rng)
        sol = cast(Solution, REGISTRY.solver("math.choose_valid_inquiry_plan")(labels, flags))
        return _mr(
            ctx,
            params={
                "mode": mode, "labels": labels, "flags": flags,
                "numbers": {"population": str(size)},
            },
            given={
                # 問いの主語は場面によって「この学校」「この市の中学生」などと変わるので、
                # 母集団の大きさは主語を決めつけない言い方で添える。
                "scenario": (
                    f"「{question}」という問いを、調べて確かめたい。"
                    f"調べたい集団には全部で{size}人がふくまれている。"
                )
            },
            context_slots={
                "ask_value": (
                    "この問いに答えるための調べ方として最も適切なものを、"
                    f"次から一つ選べ。ア {labels[0]}　イ {labels[1]}　ウ {labels[2]}"
                )
            },
            subs=[_sub(ctx, "(1)", sol)],
        )

    if mode == "judge_survey_method":
        scene = str(draw(list(p["scene_set"]), rng)).split("|")
        situation, needs_sample_s, unit_word = scene
        needs_sample = needs_sample_s == "sample"
        size = _draw_population(p, rng)
        sol = cast(
            Solution, REGISTRY.solver("math.judge_appropriate_survey_method")(needs_sample)
        )
        return _mr(
            ctx,
            params={
                "mode": mode, "needs_sample": needs_sample, "situation": situation,
                "numbers": {"population": str(size)},
            },
            given={"scenario": f"{situation}対象は全部で{size}{unit_word}ある。"},
            context_slots={
                "ask_value": (
                    "この調査は全数調査と標本調査のどちらで行うのが適切か、"
                    "理由を考えたうえで答えよ。"
                )
            },
            subs=[_sub(ctx, "(1)", sol)],
        )

    if mode == "choose_unbiased":
        scene = str(draw(list(p["scene_set"]), rng)).split("|")
        situation, unbiased, bad1, bad2 = scene
        labels = [bad1, unbiased, bad2]
        flags = [0, 1, 0]
        size = _draw_population(p, rng)
        sol = cast(
            Solution, REGISTRY.solver("math.choose_unbiased_sampling_method")(labels, flags)
        )
        return _mr(
            ctx,
            params={
                "mode": mode, "labels": labels, "flags": flags,
                "numbers": {"population": str(size)},
            },
            given={"scenario": f"{situation}母集団は全部で{size}人である。"},
            context_slots={
                "ask_value": (
                    "偏りが生じにくい抽出方法はどれか、理由を考えたうえで次から一つ選べ。"
                    f"ア {labels[0]}　イ {labels[1]}　ウ {labels[2]}"
                )
            },
            subs=[_sub(ctx, "(1)", sol)],
        )

    raise ValueError(f"未知の mode: {mode!r}")


__all__ = ["statistics_inquiry_recipe"]
