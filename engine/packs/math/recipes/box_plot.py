"""箱ひげ図の **graph_table** recipe（構成的生成・answer-first。実装設計 §6.1）。

C11（データの活用）クラスタの visual セル:
  - g2_l56.graph_table Lv1 `math.read_box_plot`            … 箱ひげ図から値を読む
  - g2_l56.graph_table Lv3 `math.draw_box_plot_from_data`  … データから求めてかく
  - g2_l57.graph_table Lv1 `math.read_two_box_plots`       … 2本から中央値と範囲を読む
  - g2_l57.graph_table Lv3 `math.compare_two_box_plots_iqr`… 2本の四分位範囲を比べる

図は `engine.packs.math.visuals.distribution_chart`（`math.box_plot`）に委ねる。
このモジュールは描画コードを持たない。

## params に何を置くかの判断（G-Q5t 漏洩と検証の穴の両にらみ）

置くのは**図に実際に描かれているもの**だけ:
  `axis_lo` / `axis_hi` / `axis_step` … 数直線の範囲と目もり（図に数値として出る）
  `box_ticks`(_a/_b)                  … 箱ひげの5か所が左から何目もり目か（図の位置）
  `five_number`(_b)                   … 上の tick から一意に決まる**描画座標**。
      visual（`render_box_plot_svg`）が要求するため置かざるを得ない。

「読む」セルの答え（中央値・第三四分位数など）は five_number の部分集合なので、
`five_number` を置くこと自体は「答えを params に置く」ことに近い。そこで
**solver には five_number を渡さない**。solver が受け取るのは `axis_lo`/`axis_step`/
`box_ticks` だけで、そこから値を復元する（`math.read_number_line_point` が
「区間左端・等分数・目もり位置」から点の値を復元するのと同じ形）。したがって
double-solve は「params の答えを読み直すだけ」にはならず、検証に穴があかない。
recipe 側では復元した five_number と描画用 five_number の一致を assert している。

G-Q5t（漏洩）の観点では、whitelist は `mr.given` から作られる。よって:
  - 「読む」セルの given は**数字を一切含めない**（場面文だけ）。テンプレにも数字を
    書かない。序数は漢数字で書く（"第三四分位数"。"第3四分位数" と書くと答えの値
    "3" と衝突して誤検出する）。
  - 「かく」セルの given はデータ列そのもの＝答えの最小値/最大値は必ず whitelist に
    乗る。四分位数が中間値になる場合も、その値は本文に現れないので漏洩しない。

## level_sep（op 列を変える）

  g2_l56: Lv1 = 図から読む2手（read_axis_step → read_box_plot_values）
          Lv3 = データから求めてかく3手（sort_data → compute_five_number → draw_box_plot）
          given も asked も相異（situation_params/read_box_plot ⇔ data_table/draw_box_plot）。
  g2_l57: Lv1 = 中央値と範囲を読む3手（read_axis_step → read_medians → read_ranges）
          Lv3 = 四分位範囲を比べる4手（read_axis_step → read_quartiles_both →
                compute_iqr_both → compare_iqr_difference）。

## 退化の防止（ゲートは素通りする）

  - `box_ticks` は狭義単調増加を強制（箱が潰れる Q1=Q3・ひげが無い 最小値=Q1 を排除）
  - 2本比較は A と B の 5 数要約が一致しないこと、かつ比べる統計量
    （Lv1=範囲 / Lv3=四分位範囲）が相異することを構成で保証
  - 「かく」セルはデータを相異値で引くので5数要約が必ず狭義単調増加になる
"""
from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.visuals.distribution_chart import (
    box_plot_labels,
    render_box_plot_solution_svg,
)

# 数直線の目もりの本数（左端 0 目もり目 〜 _TICK_COUNT 目もり目）。
_TICK_COUNT = 10
# 箱ひげを置いてよい目もり位置（両端は空けて、ひげの先が軸の端に貼りつかないようにする）。
_TICK_MIN = 1
_TICK_MAX = 9
# 5 か所の目もり位置の組み合わせ（狭義単調増加＝退化なしがここで構造的に保証される）。
_TICK_COMBOS: list[tuple[int, ...]] = list(itertools.combinations(range(_TICK_MIN, _TICK_MAX + 1), 5))

# 読み取る対象（solver 側の `_BOX_READ_TARGETS` と同じ鍵）。本文に出す語は漢数字。
_READ_TARGET_TEXT: dict[str, str] = {
    "median_q3": "中央値と第三四分位数の値",
    "q1_median": "第一四分位数と中央値の値",
    "min_max": "最小値と最大値の値",
}


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _scene(p: dict[str, Any], rng: Rng, key: str = "scene_set") -> list[str]:
    """場面を引く。`"語|語|…|目もり間隔"` のパイプ区切り文字列。

    量と数直線の目もりは独立に引くと「得点なのに軸が 0〜20」のような不整合が起きる。
    ドメイン記法（`validate_domain`）は list の要素に dict を許さないため、場面と
    目もり間隔を1本の文字列に束ねて1回で引く。**語に算用数字を書かない**
    （given がそのまま問題文に出るため。数を書くときは漢数字）。
    """
    parts = str(draw(cast("list[str]", p[key]), rng)).split("|")
    if len(parts) < 2:
        raise ValueError(f"場面の指定が不正（'語|…|目もり間隔' の形式）: {parts!r}")
    return parts


def _axis_from_step(step: int) -> tuple[int, int, int]:
    """(axis_lo, axis_hi, axis_step)。左端は 0 固定・右端は目もり本数から決まる。"""
    if step <= 0:
        raise ValueError(f"目もりの間隔は正: {step!r}")
    return 0, step * _TICK_COUNT, step


def _axis(p: dict[str, Any], rng: Rng) -> tuple[int, int, int]:
    """場面を持たないセル（「かく」）用。目もり間隔だけを引く。"""
    return _axis_from_step(int(draw({"int_set": list(p["axis_step_set"])}, rng)))


def _ticks(rng: Rng) -> list[int]:
    idx = int(draw({"int_set": list(range(len(_TICK_COMBOS)))}, rng))
    return list(_TICK_COMBOS[idx])


def _five_from_ticks(axis_lo: int, axis_step: int, ticks: list[int]) -> list[int]:
    return [axis_lo + axis_step * t for t in ticks]


def _plan(params: dict[str, Any], *, draw_box: bool) -> VisualPlan:
    """数直線＋目もり（＋読む対象の箱ひげ）の visual_plan。

    draw_box=False は「かく」セルの問題図＝数直線と目もりだけ（生徒が描き込む）。
    labels は `box_plot_labels` から機械的に作る（手で書かない・G-Q5v）。
    """
    elements = [VisualElement(kind="number_line", attrs={})]
    if draw_box:
        elements.append(VisualElement(kind="box_plot", attrs={}))
    return VisualPlan(style="box_plot", labels=box_plot_labels(params), elements=elements)


def _mr(
    ctx: CellContext,
    *,
    params: dict[str, Any],
    given: dict[str, str],
    context_slots: dict[str, str],
    sub_question: SubQuestionMR | None = None,
    sub_questions: list[SubQuestionMR] | None = None,
    visual_plan: VisualPlan,
    recipe: str,
) -> MR:
    subs = sub_questions if sub_questions is not None else [cast(SubQuestionMR, sub_question)]
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
        visual_plan=visual_plan,
        provenance=Provenance(recipe=recipe),
    )


def _sub_question(
    ctx: CellContext, *, asked: str, answer: Any, steps: list[Any], label: str = "(1)"
) -> SubQuestionMR:
    return SubQuestionMR(
        label=label,
        asked=asked,
        answer=answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )


# ---------------------------------------------------------------------------
# g2_l56.graph_table Lv1: 箱ひげ図から中央値・四分位数などを読む
# ---------------------------------------------------------------------------
_READ_BOX_PLOT_CONCEPTS = ["box_plot.read_values"]


@register_recipe("math.read_box_plot", provides_concepts=_READ_BOX_PLOT_CONCEPTS)
def read_box_plot_recipe(ctx: CellContext, rng: Rng) -> MR:
    """箱ひげ図から指定された二つの値を読み取る（g2_l56.graph_table Lv1・answer-first）。

    params の組合せ数 = 目もり位置 C(9,5)=126 × 場面がもつ相異な目もり間隔の数 ×
    読み取り対象 3。既定（間隔5種）で 1890 通り。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group, quantity, step_s = _scene(p, rng)
    axis_lo, axis_hi, axis_step = _axis_from_step(int(step_s))
    ticks = _ticks(rng)
    target = str(draw(cast("list[str]", p["read_target_set"]), rng))

    solver = REGISTRY.solver("math.read_box_plot_values")
    sol = cast(Solution, solver(axis_lo, axis_step, ticks, target))
    assert isinstance(sol.answer, SymbolicAnswer)

    five = _five_from_ticks(axis_lo, axis_step, ticks)
    params: dict[str, Any] = {
        "axis_lo": axis_lo,
        "axis_hi": axis_hi,
        "axis_step": axis_step,
        "box_ticks": ticks,
        "five_number": five,
        "read_target": target,
    }
    given = {
        "situation_params": f"{group}の{quantity}を表した箱ひげ図",
        "condition": _READ_TARGET_TEXT[target],
    }
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group": group, "quantity": quantity},
        sub_question=_sub_question(ctx, asked="read_box_plot", answer=sol.answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=True),
        recipe="math.read_box_plot",
    )


# ---------------------------------------------------------------------------
# g2_l56.graph_table Lv3: データから5数要約を求め箱ひげ図をかく
# ---------------------------------------------------------------------------
_DRAW_BOX_PLOT_CONCEPTS = ["box_plot.draw_from_data"]


@register_recipe("math.draw_box_plot_from_data", provides_concepts=_DRAW_BOX_PLOT_CONCEPTS)
def draw_box_plot_from_data_recipe(ctx: CellContext, rng: Rng) -> MR:
    """データから5数要約を求め箱ひげ図をかく（g2_l56.graph_table Lv3・answer-first）。

    データは**相異なる値**を引く（同値があると Q1=Q3 等の退化が起こりうる）。
    params の組合せ数はデータ列そのもの＝軸ごとに C(axis_hi-1, n) 通りで、
    最小の (axis_hi=20, n=8) でも C(19,8)=75582 通り。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    axis_lo, axis_hi, axis_step = _axis(p, rng)
    n = int(draw({"int_set": list(p["size_set"])}, rng))
    data = sorted(
        int(v)
        for v in draw_many(
            {"int_range": [axis_lo + 1, axis_hi - 1], "distinct": ["value"]}, rng, n
        )
    )

    solver = REGISTRY.solver("math.draw_box_plot_features")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, GraphAnswer)

    five = [sympy.sympify(f.srepr) for f in sol.answer.features]
    params: dict[str, Any] = {
        "data": data,
        "axis_lo": axis_lo,
        "axis_hi": axis_hi,
        "axis_step": axis_step,
        "five_number": [sympy.sstr(v) for v in five],
    }
    answer = GraphAnswer(
        features=list(sol.answer.features),
        solution_svg_ref=render_box_plot_solution_svg(params),
    )
    given = {"data_table": "、".join(str(v) for v in data)}
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={},
        sub_question=_sub_question(ctx, asked="draw_box_plot", answer=answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=False),
        recipe="math.draw_box_plot_from_data",
    )


# ---------------------------------------------------------------------------
# g2_l57.graph_table Lv1 / Lv3: 2本の箱ひげ図を並べて読む／比べる
# ---------------------------------------------------------------------------
def _two_series_where(
    axis_step: int,
    rng: Rng,
    predicate: Callable[[list[int], list[int]], bool],
    *,
    attempts: int = 300,
) -> tuple[int, int, int, list[int], list[int]]:
    """`predicate(ticks_a, ticks_b)` を満たす2群の目もり位置を引く。

    tick → 値は両群で同じ一次変換なので、tick 上の大小関係は値の大小関係と一致する。
    2本が完全に同じ（ticks_a == ticks_b）組はどの predicate でも捨てる。
    """
    axis_lo, axis_hi, axis_step = _axis_from_step(axis_step)
    for _ in range(attempts):
        ticks_a = _ticks(rng)
        ticks_b = _ticks(rng)
        if ticks_a == ticks_b:
            continue
        if predicate(ticks_a, ticks_b):
            return axis_lo, axis_hi, axis_step, ticks_a, ticks_b
    raise ValueError("条件を満たす2群の目もり位置を引けなかった")


def _two_series(
    axis_step: int, rng: Rng, *, compare_index: tuple[int, int]
) -> tuple[int, int, int, list[int], list[int]]:
    """2群ぶんの目もり位置を引く。

    `compare_index` は「比べる統計量」を作る tick の対（範囲=(0,4)・四分位範囲=(1,3)）。
    その差が A と B で一致する組は捨てる（比較が成り立たない退化を構成で排除する）。
    """
    lo_i, hi_i = compare_index

    def _decidable(ticks_a: list[int], ticks_b: list[int]) -> bool:
        return (ticks_a[hi_i] - ticks_a[lo_i]) != (ticks_b[hi_i] - ticks_b[lo_i])

    return _two_series_where(axis_step, rng, _decidable)


def _two_series_params(
    axis_lo: int, axis_hi: int, axis_step: int, ticks_a: list[int], ticks_b: list[int]
) -> dict[str, Any]:
    return {
        "axis_lo": axis_lo,
        "axis_hi": axis_hi,
        "axis_step": axis_step,
        "box_ticks_a": ticks_a,
        "box_ticks_b": ticks_b,
        "five_number": _five_from_ticks(axis_lo, axis_step, ticks_a),
        "five_number_b": _five_from_ticks(axis_lo, axis_step, ticks_b),
    }


_READ_TWO_BOX_PLOTS_CONCEPTS = ["box_plot.compare_center_spread"]


@register_recipe("math.read_two_box_plots", provides_concepts=_READ_TWO_BOX_PLOTS_CONCEPTS)
def read_two_box_plots_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2本の箱ひげ図から中央値と範囲を読む（g2_l57.graph_table Lv1・answer-first）。

    params の組合せ数 = C(9,5)² × 場面がもつ相異な目もり間隔の数 ＝ 既定（間隔5種）で
    79380 通り（ただし範囲が一致する組は除く）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group_a, group_b, quantity, step_s = _scene(p, rng)
    axis_lo, axis_hi, axis_step, ticks_a, ticks_b = _two_series(
        int(step_s), rng, compare_index=(0, 4)
    )

    solver = REGISTRY.solver("math.compare_box_plots_center_spread")
    sol = cast(Solution, solver(axis_lo, axis_step, ticks_a, ticks_b))
    assert isinstance(sol.answer, SymbolicAnswer)

    params = _two_series_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b)
    given = {
        "situation_params": (
            f"{group_a}をA、{group_b}をBとして、{quantity}を表した箱ひげ図"
            "（上がA、下がB）"
        )
    }
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group_a": group_a, "group_b": group_b, "quantity": quantity},
        sub_question=_sub_question(ctx, asked="read_box_plot", answer=sol.answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=True),
        recipe="math.read_two_box_plots",
    )


_COMPARE_TWO_BOX_PLOTS_IQR_CONCEPTS = ["box_plot.compare_iqr"]


@register_recipe(
    "math.compare_two_box_plots_iqr", provides_concepts=_COMPARE_TWO_BOX_PLOTS_IQR_CONCEPTS
)
def compare_two_box_plots_iqr_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2本の箱ひげ図の四分位範囲を比べる（g2_l57.graph_table Lv3・answer-first）。

    params の組合せ数は Lv1 と同じ骨格（四分位範囲が一致する組は除く）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group_a, group_b, quantity, step_s = _scene(p, rng)
    axis_lo, axis_hi, axis_step, ticks_a, ticks_b = _two_series(
        int(step_s), rng, compare_index=(1, 3)
    )

    solver = REGISTRY.solver("math.compare_box_plots_iqr")
    sol = cast(Solution, solver(axis_lo, axis_step, ticks_a, ticks_b))
    assert isinstance(sol.answer, SymbolicAnswer)

    params = _two_series_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b)
    given = {
        "situation_params": (
            f"{group_a}をA、{group_b}をBとして、{quantity}を表した箱ひげ図"
            "（上がA、下がB）"
        )
    }
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group_a": group_a, "group_b": group_b, "quantity": quantity},
        sub_question=_sub_question(ctx, asked="read_box_plot", answer=sol.answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=True),
        recipe="math.compare_two_box_plots_iqr",
    )


# ---------------------------------------------------------------------------
# g2_l57.word_problem Lv2 / Lv3 / Lv4: 2本の箱ひげ図から傾向を判断する
#
# 答えはいずれも ChoiceAnswer（記号・いえる/いえない・妥当/妥当でない）。
# ChoiceAnswer は数値トークンを持たないので、G-Q5t の漏洩検査は素通りする。それでも
# given は算用数字を含めない方針を守る（本文と図の一貫性・whitelist を汚さないため）。
# ---------------------------------------------------------------------------
def _wp_scenario(group_a: str, group_b: str, quantity: str, unit: str) -> str:
    return (
        f"{group_a}をA、{group_b}をBとして、{quantity}（{unit}）を表した箱ひげ図"
        "（上がA、下がB）"
    )


# 場面 = "集団A|集団B|量|単位|形容詞|目もり間隔"。形容詞は主張文に埋める語
# （時間なら「長い」・冊数なら「多い」・得点なら「高い」）。量ごとに自然な語が違うので
# 場面と一緒に持たせる。
def _wp_scene(p: dict[str, Any], rng: Rng) -> tuple[str, str, str, str, str, int]:
    group_a, group_b, quantity, unit, adjective, step_s = _scene(p, rng)
    return group_a, group_b, quantity, unit, adjective, int(step_s)


def _wp_params(
    axis_lo: int, axis_hi: int, axis_step: int, ticks_a: list[int], ticks_b: list[int]
) -> dict[str, Any]:
    """word_problem の params。

    word_problem の契約（engine_tests/contract/test_word_problem_params_faithfulness.py）は
    「`params["numbers"]` に置いた数は必ず本文に現れる」こと。この3セルは**数値を本文に
    一切書かない**（数はすべて図が与える＝生徒は箱ひげ図を読む）ので `numbers` は空。
    空であることは契約側でも検査される（本文に算用数字が1つでもあれば違反）ので、
    「numbers を空にして数値を素通りさせる」抜け道にはならない。

    図の幾何（軸・目もり位置・描画座標）は `numbers` の外に置く。これらは本文の数では
    なく図に描かれているものなので、本文照合の対象ではない。
    """
    return _two_series_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b) | {"numbers": {}}


_WP_COMPARE_GUIDED_CONCEPTS = ["box_plot.word_problem_compare_guided"]
# Lv2 の小問が比べる統計量（(1)=中央値・(2)=範囲）。op 名がこの値から決まるため、
# レベル内で固定＝fp は seed によらず安定する。
_WP_GUIDED_STATISTICS = ("median", "range")


@register_recipe(
    "math.word_problem_box_plot_compare", provides_concepts=_WP_COMPARE_GUIDED_CONCEPTS
)
def word_problem_box_plot_compare_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導あり・2群の中央値と範囲を比べる（g2_l57.word_problem Lv2・answer-first）。

    (1) 中央値が大きいのはどちらか → (2) 範囲が大きいのはどちらか、の2小問。
    どちらの比較も引き分けにならないよう構成で保証する。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group_a, group_b, quantity, unit, _adj, step = _wp_scene(p, rng)

    def _decidable(ta: list[int], tb: list[int]) -> bool:
        return ta[2] != tb[2] and (ta[4] - ta[0]) != (tb[4] - tb[0])

    axis_lo, axis_hi, axis_step, ticks_a, ticks_b = _two_series_where(step, rng, _decidable)

    solver = REGISTRY.solver("math.compare_box_plot_statistic")
    sols = [
        cast(Solution, solver(axis_lo, axis_step, ticks_a, ticks_b, s))
        for s in _WP_GUIDED_STATISTICS
    ]

    params = _wp_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b)
    given = {"scenario": _wp_scenario(group_a, group_b, quantity, unit)}
    subs = [
        _sub_question(ctx, asked="value", answer=s.answer, steps=s.steps, label=label)
        for s, label in zip(sols, ("(1)", "(2)"), strict=True)
    ]
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group_a": group_a, "group_b": group_b, "quantity": quantity},
        sub_questions=subs,
        visual_plan=_plan(params, draw_box=True),
        recipe="math.word_problem_box_plot_compare",
    )


_WP_JUDGE_TREND_CONCEPTS = ["box_plot.word_problem_judge_trend"]


@register_recipe(
    "math.word_problem_box_plot_trend", provides_concepts=_WP_JUDGE_TREND_CONCEPTS
)
def word_problem_box_plot_trend_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導なし・複数の観点から傾向の主張の当否を判断する（g2_l57.word_problem Lv3）。

    主張は常に「Bのほうが大きい傾向がある」。中央値は必ず B が上（＝主張には必ず
    一応の根拠がある）としたうえで、箱の左端・右端まで B が上回るかどうかで
    「いえる／いえない」が分かれる。両方の結論が同じ割合で出るよう構成する
    （どちらか一方に潰れると、図を見ずに答えられてしまう）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group_a, group_b, quantity, unit, adjective, step = _wp_scene(p, rng)
    want_supported = str(draw(["supported", "not_supported"], rng)) == "supported"

    def _matches(ta: list[int], tb: list[int]) -> bool:
        if tb[2] <= ta[2]:
            return False  # 中央値は必ず B が上（主張に一応の根拠がある形にする）
        return (tb[1] > ta[1] and tb[3] > ta[3]) is want_supported

    axis_lo, axis_hi, axis_step, ticks_a, ticks_b = _two_series_where(step, rng, _matches)

    solver = REGISTRY.solver("math.judge_box_plot_trend_claim")
    sol = cast(Solution, solver(axis_lo, axis_step, ticks_a, ticks_b))

    params = _wp_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b)
    given = {
        "scenario": _wp_scenario(group_a, group_b, quantity, unit),
        "quantities": f"「Bのほうが{quantity}が{adjective}傾向がある」という主張",
    }
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group_a": group_a, "group_b": group_b, "quantity": quantity},
        sub_question=_sub_question(ctx, asked="value", answer=sol.answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=True),
        recipe="math.word_problem_box_plot_trend",
    )


_WP_JUDGE_STABILITY_CONCEPTS = ["box_plot.word_problem_judge_stability"]


@register_recipe(
    "math.word_problem_box_plot_stability", provides_concepts=_WP_JUDGE_STABILITY_CONCEPTS
)
def word_problem_box_plot_stability_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導なし・主張を支持する根拠と反論を構成して批判的に判断する（g2_l57.word_problem Lv4）。

    主張は「Aのほうが安定して多い」。「多い」（中央値が大きい）は常に成り立たせて
    **支持する根拠を必ず1本用意**したうえで、「安定している」（四分位範囲が小さい）が
    成り立つかどうかで妥当／妥当でないが分かれる。妥当でない場合が反論の根拠を持つ側。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    group_a, group_b, quantity, unit, adjective, step = _wp_scene(p, rng)
    want_valid = str(draw(["valid", "invalid"], rng)) == "valid"

    def _matches(ta: list[int], tb: list[int]) -> bool:
        if ta[2] <= tb[2]:
            return False  # 「多い」は必ず成り立たせる（支持する根拠を1本残す）
        iqr_a, iqr_b = ta[3] - ta[1], tb[3] - tb[1]
        if iqr_a == iqr_b:
            return False
        return (iqr_a < iqr_b) is want_valid

    axis_lo, axis_hi, axis_step, ticks_a, ticks_b = _two_series_where(step, rng, _matches)

    solver = REGISTRY.solver("math.judge_box_plot_stability_claim")
    sol = cast(Solution, solver(axis_lo, axis_step, ticks_a, ticks_b))

    params = _wp_params(axis_lo, axis_hi, axis_step, ticks_a, ticks_b)
    given = {
        "scenario": _wp_scenario(group_a, group_b, quantity, unit),
        "quantities": f"「Aのほうが安定して{quantity}が{adjective}」という主張",
    }
    return _mr(
        ctx,
        params=params,
        given=given,
        context_slots={"group_a": group_a, "group_b": group_b, "quantity": quantity},
        sub_question=_sub_question(ctx, asked="value", answer=sol.answer, steps=sol.steps),
        visual_plan=_plan(params, draw_box=True),
        recipe="math.word_problem_box_plot_stability",
    )


__all__ = [
    "read_box_plot_recipe",
    "draw_box_plot_from_data_recipe",
    "read_two_box_plots_recipe",
    "compare_two_box_plots_iqr_recipe",
    "word_problem_box_plot_compare_recipe",
    "word_problem_box_plot_trend_recipe",
    "word_problem_box_plot_stability_recipe",
]
