"""比例・反比例の利用（form=word_problem・C14 の「比例/反比例」クラスタ）。

`word_problem_linear.py` / `word_problem_system.py` で通した骨格を、比例・反比例の
利用（g1_l29・g1_l33）に横展開する module。数学そのものは既存 solver
`math.solve_direct_proportion_from_point` / `math.evaluate_direct_proportion` /
`math.solve_inverse_proportion_from_point` / `math.evaluate_inverse_proportion`
（`packs/math/solvers/proportion.py`）に委ねる＝**新 solver ゼロ**。

## この form の型（先行2クラスタとの違い＝2段構成の中身）

1次方程式・連立の利用は「立式 → 方程式を解く」の2段だったが、比例・反比例の利用は
「比例定数 a を決めて式 y=ax（y=a/x）をつくる → その式に目標の x をあてはめて値を
求める」の2段になる。(1) asked=formulation の答えは**式そのもの**（機械表現は
sympy 式・表示は "y = 4x" 等）で、(2) asked=value の答えは**数値**。

## 1つの recipe で4セルを賄う設計

params の `scenario_kind` が「場面の抽選」と「a の決め方＋値の求め方」の対を選ぶ
（先行2クラスタと同じ償却パターン）。

  - g1_l29（比例）Lv2 `direct_rate` ／ Lv3 `direct_unit_convert`:
    どちらも「1{単位}あたり a」という言い方が、x0=1 の点 (1, a) そのものなので
    `solve_direct_proportion_from_point(x0=1, y0=a, mode="integer")` で a を求める
    （`_formulate_direct_from_rate`）。Lv3 だけ、道のり(m)を距離(km)に直す最後の
    一手（`convert_unit`）が増える。
  - g1_l33（反比例）Lv2 `inverse_area` ／ Lv3 `inverse_worker_days`:
    Lv2 は面積という「積そのもの」が a として直接本文に与えられる場面なので、点の
    代入は経ずに y=a/x を直接組み立てる（`_formulate_inverse_from_area`・solver
    不要・word_problem_linear の `_formulate` と同じ「立式は sympy 直書き」の型）。
    Lv3 は「4人で6日」という具体的な1組の対応が本文にあるので、
    `solve_inverse_proportion_from_point(x0, y0, mode="basic")` で a=x0*y0 を求める
    （`_formulate_inverse_from_point`）。「a を直接与えるか、点から求めるか」が
    Lv2/Lv3 の構造差（G6）。

## 求める量の評価は `evaluate_direct_proportion` / `evaluate_inverse_proportion`

(2) の値は、(1) で決めた a と、場面が問う目標値（対応する長さ・時間・人数など）を
`evaluate_direct_proportion(a, x0, "basic")` / `evaluate_inverse_proportion(a, known,
"forward")` に渡して求める。

## params が持つのは「読者が見ている数値」だけ

`params["numbers"]` は場面文（given.scenario / given.quantities）または小問文
（context_slots.ask_value）のどちらかに現れる数値だけで、答えは入っていない。
誘導ありセルは「目標値」（15m・8cm など）が (2) の小問文（context_slots.ask_value）
にしか現れない——x はあくまで一般の変数（y=4x は 15 に依存しない）で、その値は
「x を固定した具体例」ではないため。これは g1_l24.word_problem（比例式の利用）の
`quantities` に目標値を置く型と同じく、テンプレの3ブロック（scenario/quantities/
小問文）のどこかに数値がある、という契約を保つ（checker が読み違いを検出できる
経路が閉じない）。checker は同じ関数を通して a を求め直し・値を求め直す。
"""
from __future__ import annotations

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

RECIPE_NAME = "math.word_problem_proportion"

_PROPORTION_CONCEPTS = [
    "direct_proportion.word_problem_rate",
    "direct_proportion.word_problem_unit_convert",
    "inverse_proportion.word_problem_area",
    "inverse_proportion.word_problem_worker_days",
]

_X = sympy.Symbol("x")


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → a → 式」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProportionFormulation:
    """(1) の答え: 比例/反比例の式 y=ax または y=a/x。"""

    a: sympy.Expr
    expr: sympy.Expr
    display: str
    steps: list[Step]


def _formulate_direct_from_rate(rate: int) -> ProportionFormulation:
    """「1{単位}あたり rate」は x0=1 の点 (1, rate) そのもの。

    g1_l29 Lv2/Lv3 共通（「1mの重さが4g」「分速80m」はどちらもこの型）。
    """
    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    sol = cast(Solution, solver(1, rate, "integer"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expr = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    return ProportionFormulation(
        a=sympy.Integer(rate), expr=expr, display=sol.answer.display, steps=sol.steps
    )


def _formulate_inverse_from_area(area: int) -> ProportionFormulation:
    """面積のように「積が a」と直接わかっている場面は、点の代入を経ずに直接
    y=a/x を組み立てる（g1_l33 Lv2）。新 solver ではなく sympy 直書き
    （word_problem_linear の `_formulate` と同じ型）。
    """
    a = cast(sympy.Expr, sympy.Integer(area))
    expr = cast(sympy.Expr, a / _X)
    display = f"y = {area}/x"
    steps = [
        Step(
            op="form_expression",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display=display,
            narration="縦と横の積が一定であることから、反比例の式を組み立てる。",
        )
    ]
    return ProportionFormulation(a=a, expr=expr, display=display, steps=steps)


def _formulate_inverse_from_point(x0: int, y0: int) -> ProportionFormulation:
    """「4人で6日」のような具体的な1組の対応から a=x0*y0 を求める（g1_l33 Lv3）。"""
    solver = REGISTRY.solver("math.solve_inverse_proportion_from_point")
    sol = cast(Solution, solver(x0, y0, "basic"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expr = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    return ProportionFormulation(
        a=sympy.Integer(x0 * y0), expr=expr, display=sol.answer.display, steps=sol.steps
    )


def _evaluate_direct(a: sympy.Expr, target: int, unit: str) -> tuple[SymbolicAnswer, list[Step]]:
    solver = REGISTRY.solver("math.evaluate_direct_proportion")
    sol = cast(Solution, solver(a, target, "basic"))
    assert isinstance(sol.answer, SymbolicAnswer)
    answer = SymbolicAnswer(srepr=sol.answer.srepr, display=f"{sol.answer.display}{unit}")
    return answer, sol.steps


def _evaluate_inverse(a: sympy.Expr, target: int, unit: str) -> tuple[SymbolicAnswer, list[Step]]:
    solver = REGISTRY.solver("math.evaluate_inverse_proportion")
    sol = cast(Solution, solver(a, target, "forward"))
    assert isinstance(sol.answer, SymbolicAnswer)
    answer = SymbolicAnswer(srepr=sol.answer.srepr, display=f"{sol.answer.display}{unit}")
    return answer, sol.steps


def _convert_m_to_km(meters: sympy.Expr) -> tuple[SymbolicAnswer, Step]:
    """道のりの単位を m から km に直す最後の一手（g1_l29 Lv3 だけが持つ）。

    候補列挙の時点で m が1000の倍数になる組しか残さないので、ここで端数は出ない。
    """
    km = sympy.Integer(int(meters) // 1000)
    step = Step(
        op="convert_unit",
        args=[],
        result_srepr=sympy.srepr(km),
        result_display=f"{km}km",
        narration="道のりの単位を m から km に直す。",
    )
    answer = SymbolicAnswer(srepr=sympy.srepr(km), display=f"{km}km")
    return answer, step


# ---------------------------------------------------------------------------
# 値（a を決めたあと、目標値をあてはめる）— recipe と checker が共有
# ---------------------------------------------------------------------------
def solve_direct_rate(
    numbers: Mapping[str, int],
) -> tuple[ProportionFormulation, SymbolicAnswer, list[Step]]:
    rate = int(numbers["rate"])
    length = int(numbers["length"])
    formulation = _formulate_direct_from_rate(rate)
    value, steps = _evaluate_direct(formulation.a, length, "g")
    return formulation, value, steps


def solve_direct_unit_convert(
    numbers: Mapping[str, int],
) -> tuple[ProportionFormulation, SymbolicAnswer, list[Step]]:
    rate = int(numbers["rate"])
    minutes = int(numbers["minutes"])
    formulation = _formulate_direct_from_rate(rate)
    meters_answer, meter_steps = _evaluate_direct(formulation.a, minutes, "m")
    meters = cast(sympy.Expr, sympy.sympify(meters_answer.srepr))
    km_answer, convert_step = _convert_m_to_km(meters)
    return formulation, km_answer, [*meter_steps, convert_step]


def solve_inverse_area(
    numbers: Mapping[str, int],
) -> tuple[ProportionFormulation, SymbolicAnswer, list[Step]]:
    area = int(numbers["area"])
    side = int(numbers["side"])
    formulation = _formulate_inverse_from_area(area)
    value, steps = _evaluate_inverse(formulation.a, side, "cm")
    return formulation, value, steps


def solve_inverse_worker_days(
    numbers: Mapping[str, int],
) -> tuple[ProportionFormulation, SymbolicAnswer, list[Step]]:
    workers0 = int(numbers["workers0"])
    days0 = int(numbers["days0"])
    workers1 = int(numbers["workers1"])
    formulation = _formulate_inverse_from_point(workers0, days0)
    value, steps = _evaluate_inverse(formulation.a, workers1, "日")
    return formulation, value, steps


_SOLVE_SCENE: dict[
    str, Callable[[Mapping[str, int]], tuple[ProportionFormulation, SymbolicAnswer, list[Step]]]
] = {
    "direct_rate": solve_direct_rate,
    "direct_unit_convert": solve_direct_unit_convert,
    "inverse_area": solve_inverse_area,
    "inverse_worker_days": solve_inverse_worker_days,
}


def solve_scene(
    kind: str, numbers: Mapping[str, int]
) -> tuple[ProportionFormulation, SymbolicAnswer, list[Step]]:
    """場面の数値から「a を決める → 式 → 値」を1本で通す（checker と共有）。"""
    return _SOLVE_SCENE[kind](numbers)


# ---------------------------------------------------------------------------
# 場面の抽選（answer-first。a と目標値を先に決め、場面の数値を組む）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProportionScene:
    """場面文と、そこから解き直しに渡す数値。

    `numbers` は `solve_scene(kind, numbers)` にそのまま渡す（params にそのまま
    載り、checker が同じ関数へ渡す）。
    """

    numbers: dict[str, int]
    scenario: str
    # 誘導ありのときだけ本文に出す変数の設定（誘導なしは空文字）。
    quantities: str
    ask_formulation: str
    ask_value: str
    slots: dict[str, str]


def _draw_index(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _direct_rate_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(1mあたりの重さ, 求める長さ) の組。長さ1は「1mの重さが…」と同じ問いになり
    計算不要の退化になるので除く。
    """
    rates = [int(v) for v in p["rate_candidates"]]
    len_lo, len_hi = (int(v) for v in p["length_range"])
    out: list[tuple[int, int]] = []
    for rate in rates:
        for length in range(len_lo, len_hi + 1):
            if length == 1:
                continue
            out.append((rate, length))
    return out


def _scene_direct_rate(p: Mapping[str, Any], rng: Rng) -> ProportionScene:
    """g1_l29 Lv2: 「1mの重さが a g」の{item}。指定した長さの重さを求める（誘導あり）。"""
    cands = _direct_rate_candidates(p)
    rate, length = cast("tuple[int, int]", _draw_index(cands, rng))
    item = str(_draw_index(list(p["item_candidates"]), rng))
    return ProportionScene(
        numbers={"rate": rate, "length": length},
        scenario=f"1mの重さが{rate}gの{item}がある。",
        quantities=f"この{item}xmの重さをygとする。",
        ask_formulation="yをxの式で表せ。",
        ask_value=f"この{item}{length}mの重さは何gか求めよ。",
        slots={"item": item},
    )


def _direct_unit_convert_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(分速, 歩いた時間) の組。道のり(m)が1000の倍数になり km に端数が出ない
    組だけを残す（構成時に「km に直しても割り切れる」を保証する）。
    """
    rates = [int(v) for v in p["speed_candidates"]]
    min_lo, min_hi = (int(v) for v in p["minutes_range"])
    km_max = int(p["km_max"])
    out: list[tuple[int, int]] = []
    for rate in rates:
        for minutes in range(min_lo, min_hi + 1):
            meters = rate * minutes
            if meters % 1000:
                continue
            km = meters // 1000
            if not (1 <= km <= km_max):
                continue
            out.append((rate, minutes))
    return out


def _scene_direct_unit_convert(p: Mapping[str, Any], rng: Rng) -> ProportionScene:
    """g1_l29 Lv3: 「分速 a m で歩く」人。指定した時間で歩く道のりを km で求める
    （誘導なし・単位変換）。
    """
    cands = _direct_unit_convert_candidates(p)
    rate, minutes = cast("tuple[int, int]", _draw_index(cands, rng))
    person = str(_draw_index(list(p["person_candidates"]), rng))
    return ProportionScene(
        numbers={"rate": rate, "minutes": minutes},
        scenario=f"分速{rate}mで歩く{person}がいる。歩いた時間と進んだ道のりは比例する。",
        quantities="",
        ask_formulation="",
        ask_value=f"この{person}が{minutes}分で歩く道のりは何kmか。式を立てて求めよ。",
        slots={"person": person},
    )


def _inverse_area_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(面積, 縦の長さ) の組。縦=横（正方形）になる組は「長方形」の題材と
    合わないので除く。横も長さの範囲内に収まる組だけを残す。
    """
    area_lo, area_hi = (int(v) for v in p["area_range"])
    side_lo, side_hi = (int(v) for v in p["side_range"])
    out: list[tuple[int, int]] = []
    for area in range(area_lo, area_hi + 1):
        for side in range(side_lo, side_hi + 1):
            if area % side:
                continue
            other = area // side
            if other == side or not (side_lo <= other <= side_hi):
                continue
            out.append((area, side))
    return out


def _scene_inverse_area(p: Mapping[str, Any], rng: Rng) -> ProportionScene:
    """g1_l33 Lv2: 面積 a cm² の長方形。縦の長さから横の長さを求める（誘導あり）。"""
    cands = _inverse_area_candidates(p)
    area, side = cast("tuple[int, int]", _draw_index(cands, rng))
    return ProportionScene(
        numbers={"area": area, "side": side},
        scenario=f"面積が{area}cm²の長方形がある。",
        quantities="縦をxcm、横をycmとする。",
        ask_formulation="yをxの式で表せ。",
        ask_value=f"縦が{side}cmのとき、横は何cmか求めよ。",
        slots={},
    )


def _inverse_worker_days_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(最初の人数, 最初の日数, 変えたあとの人数) の組。人数を変えない組・
    割り切れない組・答えが本文の数値と一致する組は除く（構成時の自衛）。
    """
    workers = [int(v) for v in p["workers_candidates"]]
    days = [int(v) for v in p["days_candidates"]]
    out: list[tuple[int, int, int]] = []
    for w0 in workers:
        for d0 in days:
            total = w0 * d0
            for w1 in workers:
                if w1 == w0 or total % w1:
                    continue
                answer = total // w1
                if answer in (w0, d0, w1):
                    continue
                out.append((w0, d0, w1))
    return out


def _scene_inverse_worker_days(p: Mapping[str, Any], rng: Rng) -> ProportionScene:
    """g1_l33 Lv3: 「w0人で d0日」かかる{job}。人数を変えたときの日数を求める
    （誘導なし）。
    """
    cands = _inverse_worker_days_candidates(p)
    workers0, days0, workers1 = cast("tuple[int, int, int]", _draw_index(cands, rng))
    job = str(_draw_index(list(p["job_candidates"]), rng))
    return ProportionScene(
        numbers={"workers0": workers0, "days0": days0, "workers1": workers1},
        scenario=(
            f"ある{job}を{workers0}人ですると{days0}日かかる。"
            f"この{job}をする人数x人と、かかる日数y日は反比例する。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"この{job}を{workers1}人でするとき、何日で終わるか。式を立てて求めよ。",
        slots={"job": job},
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], ProportionScene]] = {
    "direct_rate": _scene_direct_rate,
    "direct_unit_convert": _scene_direct_unit_convert,
    "inverse_area": _scene_inverse_area,
    "inverse_worker_days": _scene_inverse_worker_days,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_PROPORTION_CONCEPTS)
def word_problem_proportion(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    scene = _SCENE_DRAWERS[kind](p, rng)
    formulation, value_answer, value_steps = solve_scene(kind, scene.numbers)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    # 誘導なしのセルは (1) が無いので、立式の手順も value 側の模範解答に入れる
    # （でないと「解くところから始まる解説」になる）。
    value_sq = SubQuestionMR(
        label="(2)" if guided else "(1)",
        asked="value",
        answer=value_answer,
        steps=[*([] if guided else formulation.steps), *value_steps],
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
                answer=SymbolicAnswer(
                    srepr=sympy.srepr(formulation.expr), display=formulation.display
                ),
                steps=formulation.steps,
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
            # 場面文（または小問文）に読者が見ている数値だけ（答えは入れない）。
            "scenario_kind": kind,
            "guided": guided,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given=given,
        context_slots={
            **scene.slots,
            "ask_formulation": scene.ask_formulation,
            "ask_value": scene.ask_value,
        },
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "ProportionFormulation",
    "ProportionScene",
    "solve_direct_rate",
    "solve_direct_unit_convert",
    "solve_inverse_area",
    "solve_inverse_worker_days",
    "solve_scene",
    "word_problem_proportion",
]
