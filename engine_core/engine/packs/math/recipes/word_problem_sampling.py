"""標本調査の利用（form=word_problem・C14 の「標本調査の利用」クラスタ）。

`word_problem_linear.py` / `word_problem_system.py` で通した文章題の骨格を、
標本から母集団を推定する文章題に横展開する module。数学そのものは既存 solver
`math.sample_ratio_estimate` / `math.sample_ratio_solve_population`
（g3_l59.calculation Lv1 / g3_l60.calculation Lv2 が使っているものと同一）に
委ねる＝**新 solver ゼロ**。

## 1つの recipe で4セルを賄う設計

params の `scenario_kind` が

  1. 場面の数値を answer-first で引く関数（`_SCENE_DRAWERS`）
  2. どちらの既存 solver を呼ぶか（`_SAMPLING_SOLVERS`）

の対を選ぶ。賄うのは g3_l59（Lv2/Lv3）・g3_l60（Lv3/Lv4）の4セル。

## scenario_kind と level_sep（何が場面文に出ていて、何を求めるか）

  - g3_l59 Lv2 `mark_recapture_pond`（誘導あり・2小問）: 池の魚。あらかじめ印を
    つけて放した魚の総数（`known_estimate`）が場面文に出ており、再捕獲した標本
    での印つき比率から母集団を `math.sample_ratio_solve_population` で推定する。
    (1) 標本比率を求める→(2) 母集団を求める。
  - g3_l59 Lv3 `factory_defect_estimate`（誘導なし・1小問）: 工場の製品。母集団
    の大きさ（`population_size`）が場面文に出ており、標本の不良率から母集団中の
    不良品数を `math.sample_ratio_estimate` で推定する。l59 Lv2 と「場面文に出て
    いる量／求める量」が入れ替わる＝構造差。
  - g3_l60 Lv3 `lake_capture_recapture`（誘導あり・2小問）: 湖のコイ。捕獲再捕獲法
    そのもの（捕まえて印をつけてから戻し、後日また捕まえる手順）を場面文が明示
    する。数学は l59 Lv2 と同じ `sample_ratio_solve_population` だが、場面の描写
    が「あらかじめ放流」ではなく「捕獲→標識→放流→再捕獲」という手順になる。
  - g3_l60 Lv4 `red_ball_model`（誘導なし・1小問）: 白玉と赤玉。母集団そのもの
    （白玉の総数）は場面文に出ておらず、「同じ大きさの玉を既知数だけ加える」と
    いうモデル化の手順自体を読み取らせる。標本比率から「加えた玉を含む全体」を
    `sample_ratio_solve_population` で推定したあと、加えた分を引く最後の一手
    （`answer_offset`）が要る＝ほかの3セルにはない構造。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は標本の大きさ・標本内の該当個数・（母集団または既知個数）の
3値だけで、答え（母集団や推定個数）は入っていない。checker は同じ数値から solver
を呼び直して解き直す。
"""
from __future__ import annotations

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
from engine.core.rng import Rng, draw

RECIPE_NAME = "math.word_problem_sample_survey"

_SOLVER_ESTIMATE = "math.sample_ratio_estimate"
_SOLVER_SOLVE_POPULATION = "math.sample_ratio_solve_population"

_SAMPLING_SOLVERS: dict[str, str] = {
    "mark_recapture_pond": _SOLVER_SOLVE_POPULATION,
    "factory_defect_estimate": _SOLVER_ESTIMATE,
    "lake_capture_recapture": _SOLVER_SOLVE_POPULATION,
    "red_ball_model": _SOLVER_SOLVE_POPULATION,
}

_SAMPLING_CONCEPTS = [
    "sample_survey.word_problem_mark_recapture",
    "sample_survey.word_problem_defect_estimate",
    "sample_survey.word_problem_capture_recapture",
    "sample_survey.word_problem_population_modeling",
]

# 「標本での割合」ステップのダミー結果（第1手は値を出さない・§ find_equal_relation と同じ型）。
_RATIO_PLACEHOLDER = sympy.Symbol("r")


# ---------------------------------------------------------------------------
# 解く（recipe と checker が共有する「場面の数値 → solver → 求める量」の単一の真実）
# ---------------------------------------------------------------------------
def solve_scene(
    kind: str, numbers: Mapping[str, int], answer_offset: int
) -> tuple[Solution, sympy.Expr]:
    """場面の数値から既存 solver を呼び直し、`answer_offset` を足して求める量にする。

    x を解くのは既存 solver（`sample_ratio_estimate` / `sample_ratio_solve_population`）。
    最後の +offset だけこちらで合成する（`red_ball_model` の「白玉 = 全体 − 加えた赤玉」）。
    """
    solver_name = _SAMPLING_SOLVERS[kind]
    solver = REGISTRY.solver(solver_name)
    third = "population_size" if solver_name == _SOLVER_ESTIMATE else "known_estimate"
    sol = cast(
        Solution,
        solver(numbers["sample_size"], numbers["sample_count"], numbers[third]),
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    raw_value = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    answer_value = cast(sympy.Expr, raw_value + sympy.Integer(answer_offset))
    return sol, answer_value


def ratio_steps_and_answer(numbers: Mapping[str, int]) -> tuple[list[Step], SymbolicAnswer]:
    """(1) 標本での割合＝sample_count/sample_size（4セル共通の量。solver は問わない）。

    2手にするのは steps_prefix ヒントが len(steps)>=2 でないと出ないため（他クラスタと
    同じ「第1手はダミー結果・第2手が実際の値」の型）。narration に数字は書かない。
    """
    ratio = sympy.Rational(int(numbers["sample_count"]), int(numbers["sample_size"]))
    # **標本での割合は小数で答える**（相対度数と同じ作法・EVALUATION D-24）。
    # 「120匹中15匹 → 1/8」は約分しても割合として読めない（0.125 と書く）。
    disp = _fmt_ratio_as_decimal(ratio)
    srepr = sympy.srepr(ratio)
    steps = [
        Step(
            op="identify_sample_ratio_terms",
            args=[],
            result_srepr=sympy.srepr(_RATIO_PLACEHOLDER),
            result_display="標本の大きさと、そのうち該当するものの個数",
            narration="標本の中で、該当するものの個数と標本全体の個数を確認する。",
        ),
        Step(
            op="compute_sample_ratio",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="該当するものの個数を標本の大きさでわり、標本での割合を求める。",
        ),
    ]
    return steps, SymbolicAnswer(srepr=srepr, display=disp)


def _fmt_ratio_as_decimal(v: sympy.Rational) -> str:
    """割合の表示。割り切れるなら小数、そうでなければ分数（構成側で割り切れる組を引く）。"""
    q = int(v.q)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    if q != 1:
        return sympy.sstr(v)
    digits, r = 0, sympy.Rational(v)
    while r.q != 1:
        r *= 10
        digits += 1
    return f"{float(v):.{digits}f}" if digits else str(int(v))


def _derive_steps(answer_offset: int, narration: str, answer_value: sympy.Expr, unit: str) -> list[Step]:
    """求める量が solver の出力と違う場面（`red_ball_model`）だけが使う最後の一手。"""
    if answer_offset == 0:
        return []
    return [
        Step(
            op="derive_asked_quantity",
            args=[],
            result_srepr=sympy.srepr(answer_value),
            result_display=f"{answer_value}{unit}",
            narration=narration,
        ),
    ]


# ---------------------------------------------------------------------------
# 場面の抽選（answer-first。候補列挙して割り切れる組だけを残す）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SamplingScene:
    """場面文と、そこから solver に渡す数値。

    `numbers` は `solve_scene` に渡すキーワード（`sample_size`/`sample_count`/
    `known_estimate` または `population_size`）そのもの（params にそのまま載り、
    checker が同じキーで solver を呼ぶ）。
    """

    numbers: dict[str, int]
    scenario: str
    quantities: str
    ask_formulation: str
    ask_value: str
    answer_offset: int
    answer_unit: str
    derive_narration: str


def _draw_index(n: int, rng: Rng) -> int:
    return int(draw({"int_range": [0, n - 1]}, rng))


def _ratio_is_decimal(count: int, size: int) -> bool:
    """標本での割合 count/size が小数で書き切れるか。

    **(1) の答えは「標本での割合」で、小数で答えるのが教材の作法**（D-24）。
    「120匹中15匹 → 1/8」のような、約分しても割合として読めない答えを作らない。
    """
    q = size // math.gcd(count, size)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    return q == 1


def _candidates_solve_population(
    sizes: list[int], counts: list[int], knowns: list[int]
) -> list[tuple[int, int, int]]:
    """(標本の大きさ, 標本内の該当個数, 既知個数) の候補列挙（母集団 x を解く型）。

    x = known×size/count が整数になる（割り切れる）組だけを残す。count < size は
    「標本内の該当個数は標本全体より少ない」という非退化条件そのもの。x が場面文の
    他の数値と一致する組は除く（G-Q5t の自衛）。
    """
    out: list[tuple[int, int, int]] = []
    for size in sizes:
        for count in counts:
            if count >= size or not _ratio_is_decimal(count, size):
                continue
            for known in knowns:
                if (known * size) % count:
                    continue
                x = known * size // count
                if x in (known, size, count):
                    continue
                out.append((size, count, known))
    return out


def _candidates_estimate(
    sizes: list[int], counts: list[int], populations: list[int]
) -> list[tuple[int, int, int]]:
    """(標本の大きさ, 標本内の該当個数, 母集団の大きさ) の候補列挙（推定個数を解く型）。"""
    out: list[tuple[int, int, int]] = []
    for size in sizes:
        for count in counts:
            if count >= size or not _ratio_is_decimal(count, size):
                continue
            for population in populations:
                if (population * count) % size:
                    continue
                x = population * count // size
                if x in (population, size, count):
                    continue
                out.append((size, count, population))
    return out


def _scene_mark_recapture_pond(p: Mapping[str, Any], rng: Rng) -> SamplingScene:
    """g3_l59 Lv2: 池の魚。あらかじめ放した印つきの魚の総数から母集団を推定する（誘導あり）。"""
    cands = _candidates_solve_population(
        [int(v) for v in p["sample_size_candidates"]],
        [int(v) for v in p["sample_count_candidates"]],
        [int(v) for v in p["known_estimate_candidates"]],
    )
    size, count, known = cands[_draw_index(len(cands), rng)]
    return SamplingScene(
        numbers={"sample_size": size, "sample_count": count, "known_estimate": known},
        scenario=(
            f"ある池にいる魚の総数を調べるため、無作為に{size}匹の魚を調べたところ、"
            f"そのうち印のついた魚が{count}匹いた。この池にはあらかじめ印をつけた魚が"
            f"{known}匹放してある。"
        ),
        quantities="この池にいる魚の総数を x 匹とする。",
        ask_formulation="標本での印つきの魚の割合を求めよ。",
        ask_value="この池の魚のおよその総数を求めよ。",
        answer_offset=0,
        answer_unit="匹",
        derive_narration="",
    )


def _scene_factory_defect_estimate(p: Mapping[str, Any], rng: Rng) -> SamplingScene:
    """g3_l59 Lv3: 工場の製品。母集団の大きさから不良品数を推定する（誘導なし）。"""
    cands = _candidates_estimate(
        [int(v) for v in p["sample_size_candidates"]],
        [int(v) for v in p["sample_count_candidates"]],
        [int(v) for v in p["population_size_candidates"]],
    )
    size, count, population = cands[_draw_index(len(cands), rng)]
    return SamplingScene(
        numbers={"sample_size": size, "sample_count": count, "population_size": population},
        scenario=(
            f"ある工場で1日に作られる大量の製品から無作為に{size}個を取り出したところ、"
            f"不良品が{count}個含まれていた。この日に作られた製品は{population}個である。"
        ),
        quantities="",
        ask_formulation="",
        ask_value="この中に含まれる不良品はおよそ何個と推定できるか求めよ。",
        answer_offset=0,
        answer_unit="個",
        derive_narration="",
    )


def _scene_lake_capture_recapture(p: Mapping[str, Any], rng: Rng) -> SamplingScene:
    """g3_l60 Lv3: 湖のコイ。捕獲再捕獲法の手順を場面文が明示する（誘導あり）。"""
    cands = _candidates_solve_population(
        [int(v) for v in p["sample_size_candidates"]],
        [int(v) for v in p["sample_count_candidates"]],
        [int(v) for v in p["known_estimate_candidates"]],
    )
    size, count, known = cands[_draw_index(len(cands), rng)]
    return SamplingScene(
        numbers={"sample_size": size, "sample_count": count, "known_estimate": known},
        scenario=(
            f"湖にいるコイの数を調べるため、{known}匹のコイを捕まえて印をつけて湖にもどした。"
            f"数日後に同じ湖で{size}匹のコイを捕まえると、そのうち印のついたコイが{count}匹いた。"
        ),
        quantities="この湖にいるコイの総数を x 匹とする。",
        ask_formulation="この標本での印つきのコイの割合を求めよ。",
        ask_value="この湖にいるコイのおよその総数を求めよ。",
        answer_offset=0,
        answer_unit="匹",
        derive_narration="",
    )


def _scene_red_ball_model(p: Mapping[str, Any], rng: Rng) -> SamplingScene:
    """g3_l60 Lv4: 白玉と赤玉。既知数の玉を加えるモデル化＋差し引く一手が要る（誘導なし）。"""
    cands = _candidates_solve_population(
        [int(v) for v in p["sample_size_candidates"]],
        [int(v) for v in p["sample_count_candidates"]],
        [int(v) for v in p["red_ball_candidates"]],
    )
    size, count, red = cands[_draw_index(len(cands), rng)]
    return SamplingScene(
        numbers={"sample_size": size, "sample_count": count, "known_estimate": red},
        scenario=(
            "袋の中に大量の白玉が入っている。この袋の中の白玉の総数を、玉を数えずに"
            f"標本調査で推定したい。同じ大きさの赤玉を{red}個袋に加えてよくかき混ぜ、"
            f"無作為に{size}個を取り出したところ、そのうち赤玉が{count}個だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value="はじめに入っていた白玉のおよその総数を求めよ。",
        answer_offset=-red,
        answer_unit="個",
        derive_narration="求めた全体の個数から、はじめに加えた赤玉の個数を引いて、もとからあった白玉の総数を求める。",
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], SamplingScene]] = {
    "mark_recapture_pond": _scene_mark_recapture_pond,
    "factory_defect_estimate": _scene_factory_defect_estimate,
    "lake_capture_recapture": _scene_lake_capture_recapture,
    "red_ball_model": _scene_red_ball_model,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_SAMPLING_CONCEPTS)
def word_problem_sample_survey(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    scene = _SCENE_DRAWERS[kind](p, rng)
    sol, answer_value = solve_scene(kind, scene.numbers, scene.answer_offset)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    ratio_steps, ratio_answer = ratio_steps_and_answer(scene.numbers)
    derive_steps = _derive_steps(
        scene.answer_offset, scene.derive_narration, answer_value, scene.answer_unit
    )

    value_steps = [
        *([] if guided else ratio_steps),
        *sol.steps,
        *derive_steps,
    ]
    value_sq = SubQuestionMR(
        label="(2)" if guided else "(1)",
        asked="value",
        answer=SymbolicAnswer(
            srepr=sympy.srepr(answer_value), display=f"{answer_value}{scene.answer_unit}"
        ),
        steps=value_steps,
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )
    sub_questions = [value_sq]
    if guided:
        sub_questions.insert(
            0,
            SubQuestionMR(
                label="(1)",
                asked="formulation",
                answer=ratio_answer,
                steps=ratio_steps,
                concept_tags=concept_tags,
                cause_tags=cause_tags,
            ),
        )

    given = {"scenario": scene.scenario}
    if guided:
        given["quantities"] = scene.quantities

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
            # 誘導の有無（小問数）。checker はこれを見て返す Solution の数を決める。
            "guided": guided,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            "answer_offset": str(scene.answer_offset),
            "answer_unit": scene.answer_unit,
        },
        given=given,
        context_slots={
            "ask_formulation": scene.ask_formulation,
            "ask_value": scene.ask_value,
        },
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "SamplingScene",
    "ratio_steps_and_answer",
    "solve_scene",
    "word_problem_sample_survey",
]
