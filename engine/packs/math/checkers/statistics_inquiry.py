"""統計的な探究（C11 word_problem 5セル）の double_solve checker（§6.2）。

params が持つのは**本文に出ているもの**（データ列・選択肢・場面の真偽）と、
どのセルかを示す `mode` だけで、答え（平均値・範囲・どちらが安定か・どの選択肢か）は
入っていない。checker は同じ solver を呼び直して独立に再計算する。

**mode を params に置いて明示する**のが要点。params の形（どのキーがあるか）から
セルを推測すると、似た形のセルが増えたときに黙って別の solver を呼ぶ
（実際に g3_l58 で signature を見て推測していて取り違えた）。

返す Solution の数は mode から決める（MR の小問数を見ない）。形をなぞると
「小問が1つ減っていても気づかない」ので、G-Q1 の個数照合が意味を持つようにする。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker
from engine.packs.math.recipes.statistics_inquiry import lists_from_numbers


@register_checker("math.statistics_inquiry.double_solve")
def double_solve_statistics_inquiry(mr: MR) -> list[Solution]:
    p = mr.params
    mode = str(p["mode"])

    if mode == "compare_mean_range":
        a, b = lists_from_numbers(p["numbers"])
        return [
            cast(Solution, REGISTRY.solver("math.datasets_mean_pair")(a, b)),
            cast(Solution, REGISTRY.solver("math.datasets_range_pair")(a, b)),
            cast(Solution, REGISTRY.solver("math.judge_more_stable")(a, b)),
        ]
    if mode == "choose_statistic":
        return [
            cast(
                Solution,
                REGISTRY.solver("math.judge_group_by_any_statistic")(
                    *lists_from_numbers(p["numbers"]), p["smaller_is_better"]
                ),
            )
        ]
    if mode == "judge_survey_method":
        return [
            cast(
                Solution,
                REGISTRY.solver("math.judge_appropriate_survey_method")(p["needs_sample"]),
            )
        ]
    if mode == "choose_unbiased":
        return [
            cast(
                Solution,
                REGISTRY.solver("math.choose_unbiased_sampling_method")(
                    p["labels"], p["flags"]
                ),
            )
        ]
    if mode == "design_plan":
        return [
            cast(
                Solution,
                REGISTRY.solver("math.choose_valid_inquiry_plan")(p["labels"], p["flags"]),
            )
        ]
    raise ValueError(f"未知の mode: {mode!r}")


__all__ = ["double_solve_statistics_inquiry"]
