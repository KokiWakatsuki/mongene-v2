"""分布のグラフ（ヒストグラム・度数折れ線・累積折れ線）の recipe 群（構成的生成・answer-first）。

C11（データ・統計）クラスタの **graph_table**（読む／かく）10 セル:
  g1_l54 Lv1/Lv2/Lv3・g1_l55 Lv1/Lv2/Lv3・g1_l56 Lv2/Lv3・g1_l58 Lv2/Lv3。

描画はすべて土台 `engine.packs.math.visuals.distribution_chart` に委ねる
（新しい描画コードは書かない）。問題図は登録 visual `math.frequency_chart` が
`mr.params` から描く: `visual_plan.elements` に kind="distribution" があれば分布を描き
（＝「読む」セル）、無ければ目盛だけの空のグラフ用紙（＝「かく」セル）になる。
`visual_plan.labels` は `frequency_chart_labels(params)` で機械的に作る（G-Q5v）。

params の規約（土台が読む名前）:
  class_lo / class_width / frequencies / frequencies_b(任意) / chart_kind

乱数は `engine.core.rng.draw` 以外で解釈しない。recipe は例外を投げない
（構成は全経路で成功するように書く。拒否ではなく構成で制約を満たす）。
"""
from __future__ import annotations

from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.visuals.distribution_chart import (
    frequency_chart_labels,
    render_frequency_chart_solution_svg,
)

# ---------------------------------------------------------------------------
# 題材（surface）: (題材名, 単位, 最初の階級の下限の候補, 階級の幅)
# 階級の幅は題材ごとに固定する（「身長が 0cm 以上 5cm 未満」のような不自然な階級を
# 作らないため）。下限は候補から抽選するので params の (class_lo, class_width) は
# 22 通りの相異なる組になる。
# ---------------------------------------------------------------------------
_SCENES: list[tuple[str, str, list[int], int]] = [
    ("通学時間", "分", [0, 5, 10], 5),
    ("数学のテストの得点", "点", [30, 40, 50], 10),
    ("ハンドボール投げの記録", "m", [8, 12, 16], 4),
    ("反復横とびの記録", "回", [30, 35, 40], 5),
    ("握力の記録", "kg", [10, 15, 20], 5),
    ("身長", "cm", [140, 145, 150], 5),
    ("立ち幅とびの記録", "cm", [140, 150, 160], 10),
    ("家庭学習の時間", "分", [0, 10, 20], 10),
]


def _scene(rng: Rng) -> tuple[str, str, int, int]:
    """題材・単位・最初の階級の下限・階級の幅を1組選ぶ。"""
    idx = int(draw({"int_range": [0, len(_SCENES) - 1]}, rng))
    name, unit, lo_choices, width = _SCENES[idx]
    lo = int(draw({"int_set": list(lo_choices)}, rng))
    return name, unit, lo, width


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _table_text(lo: int, width: int, freqs: list[int], unit: str) -> str:
    return "、".join(
        f"{lo + width * i}{unit}以上{lo + width * (i + 1)}{unit}未満…{f}人"
        for i, f in enumerate(freqs)
    )


def _unique_peak(freqs: list[int], rng: Rng, bonus: dict[str, Any]) -> tuple[list[int], int]:
    """最大の階級を一意にし、**山が1つ**の並びに直す。

    前は最大値を1つ持ち上げるだけで、他の階級は独立に引いたままだった。
    その結果 10・4・11・3・12 のような並びになり、**度数折れ線をかかせる問題で、
    かいた折れ線がギザギザになっていた**。実物の度数分布はほぼ単峰で、
    生徒が「分布の形」を読み取れるのはそのため。

    値は変えず、山の左を増加・右を減少に並べ替えるだけ。
    """
    peak = int(draw({"int_range": [0, len(freqs) - 1]}, rng))
    peak_val = max(freqs) + int(draw(bonus, rng))
    rest = sorted(freqs[1:], reverse=True)  # 1つ分は山の値に置き換わる
    left, right = rest[:peak], rest[peak:]
    return [*reversed(left), peak_val, *right], peak


def _visual_plan(params: dict[str, Any], *, drawn: bool) -> VisualPlan:
    """分布を描く（読む）／目盛だけの空のグラフ用紙（かく）の visual_plan。"""
    elements = [VisualElement(kind="chart_frame", attrs={}), VisualElement(kind="axis", attrs={})]
    if drawn:
        elements.append(VisualElement(kind="distribution", attrs={"chart_kind": params["chart_kind"]}))
    return VisualPlan(style="chart", labels=frequency_chart_labels(params), elements=elements)


def _mr(
    ctx: CellContext,
    *,
    params: dict[str, Any],
    given: dict[str, str],
    sub_question: SubQuestionMR,
    visual_plan: VisualPlan,
    recipe: str,
) -> MR:
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given=given,
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe=recipe),
    )


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv1（ヒストグラム）/ g1_l55.graph_table Lv1（度数折れ線）
# グラフから度数を読む・度数が最大の階級を読む。
# ---------------------------------------------------------------------------
_READ_CHART_CONCEPTS = [
    "frequency_chart.read_histogram",
    "frequency_polygon.read_chart",
]


@register_recipe("math.read_distribution_chart", provides_concepts=_READ_CHART_CONCEPTS)
def read_distribution_chart_recipe(ctx: CellContext, rng: Rng) -> MR:
    """分布のグラフから度数と最頻の階級を読む（answer-first・graph_table「読む」）。

    answer-first: 度数列を先に構成し（最大が一意になるよう1つだけ持ち上げる）、
    そこからグラフを描く。問われる階級は最頻の階級**以外**から選ぶので、2つの問いが
    同じ階級に潰れない。問題文には総度数と階級の作り方しか書かず、度数そのものは
    図からしか読めない。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    base = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)]
    freqs, peak = _unique_peak(base, rng, cast("dict[str, Any]", p["peak_bonus_domain"]))
    target = int(draw({"int_set": [i for i in range(n_classes) if i != peak]}, rng))

    solver = REGISTRY.solver("math.read_distribution_chart")
    sol = cast(Solution, solver(freqs, lo, width, target, unit))
    assert isinstance(sol.answer, SymbolicAnswer)

    chart_kind = str(draw(p["chart_kind"], rng))
    chart_word = "ヒストグラム" if chart_kind == "histogram" else "度数折れ線"
    t_lo = lo + width * target
    t_hi = t_lo + width
    statement = (
        f"ある中学校の{sum(freqs)}人の{scene}を調べ、{lo}{unit}から{width}{unit}ずつの階級に"
        f"分けて{chart_word}に表した。{t_lo}{unit}以上{t_hi}{unit}未満の階級の度数を答えよ。"
        f"また、度数がもっとも大きい階級を答えよ"
    )

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freqs,
        "target_index": target,
        "unit": unit,
        "chart_kind": chart_kind,
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="read_table", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"situation_params": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=True),
        recipe="math.read_distribution_chart",
    )


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv2: 生データ → 度数分布表 → ヒストグラムをかく
# ---------------------------------------------------------------------------
_TABULATE_CONCEPTS = ["frequency_chart.draw_histogram_from_raw_data"]


@register_recipe("math.tabulate_and_draw_histogram", provides_concepts=_TABULATE_CONCEPTS)
def tabulate_and_draw_histogram_recipe(ctx: CellContext, rng: Rng) -> MR:
    """生データを階級に分けて度数分布表を作りヒストグラムをかく（answer-first・「かく」）。

    answer-first: 各階級の度数を先に決め、その度数ぶんの値をその階級の範囲から引いて
    生データを作る。したがって solver が数え直した度数は必ず構成した度数に一致する
    （recipe 側でも突き合わせて assert する）。問題図は目盛だけの空のグラフ用紙。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    base = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)]
    freqs, _peak = _unique_peak(base, rng, cast("dict[str, Any]", p["peak_bonus_domain"]))

    data: list[int] = []
    for i, f in enumerate(freqs):
        c_lo = lo + width * i
        for _ in range(f):
            data.append(int(draw({"int_range": [c_lo, c_lo + width - 1]}, rng)))
    for i in range(len(data) - 1, 0, -1):
        j = int(draw({"int_range": [0, i]}, rng))
        data[i], data[j] = data[j], data[i]

    solver = REGISTRY.solver("math.tabulate_and_draw_histogram")
    sol = cast(Solution, solver(data, lo, width, n_classes, unit))
    assert isinstance(sol.answer, GraphAnswer)
    recounted = [
        int(sympy.sympify(f.srepr)[1]) for f in sol.answer.features
    ]
    assert recounted == freqs, f"double-solve 不一致: 構成した度数 {freqs} != 数え直し {recounted}"

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freqs,
        "data": data,
        "unit": unit,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    statement = (
        f"次の{len(data)}人の{scene}（単位{unit}）を、{lo}{unit}以上{lo + width}{unit}未満から"
        f"{width}{unit}ずつの階級に分けて度数分布表を作り、そのヒストグラムをかけ。"
        f"〔{'、'.join(str(v) for v in data)}〕"
    )
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_frequency_chart_solution_svg(params),
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"data_table": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=False),
        recipe="math.tabulate_and_draw_histogram",
    )


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv3（ヒストグラム）/ g1_l58.graph_table Lv2（度数折れ線）
# 2つの分布の散らばりと偏りを比べる。
# ---------------------------------------------------------------------------
_COMPARE_SHAPE_CONCEPTS = [
    "frequency_chart.compare_histogram_shapes",
    "distribution_comparison.read_overlaid_charts",
]
_GROUP_A = "A組"
_GROUP_B = "B組"
# 度数が 1 以上の階級が占める幅（＝散らばりの目安）の候補。2つの分布で必ず相異なる値を
# 選ぶので「散らばりが同じで比較にならない」退化が構成の段階で起きない。
_SPAN_CHOICES: tuple[int, ...] = (3, 4, 5, 6)


def _allocate(total: int, window: list[int], peak: int, offset: int, n_classes: int) -> list[int]:
    """総度数 total を window の階級に配り、peak の階級を一意の最大にする。

    window 外の階級は度数 0（＝分布の広がりが window の幅そのものになる）。
    """
    vals = {i: 1 for i in window}
    pool = total - len(window)
    boost = pool // 2
    vals[peak] += boost
    pool -= boost
    others = [i for i in window if i != peak]
    for k in range(pool):
        vals[others[(offset + k) % len(others)]] += 1
    # 一意最大の保証（構成上ほぼ常に成り立つが、成り立たないときは山へ振り替える）。
    for _ in range(len(window) * total):
        top_other = max(others, key=lambda i: (vals[i], -i))
        if vals[peak] > vals[top_other]:
            break
        if vals[top_other] <= 1:
            break
        vals[top_other] -= 1
        vals[peak] += 1
    return [vals.get(i, 0) for i in range(n_classes)]


@register_recipe("math.compare_distribution_shape", provides_concepts=_COMPARE_SHAPE_CONCEPTS)
def compare_distribution_shape_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2つの分布の散らばりと偏りをグラフの形から比べる（answer-first・「読む」）。

    answer-first: 2つの分布が占める階級の幅（＝散らばり）と山の位置（＝偏り）を
    先に**相異なる**ように選んでから度数を配る。どちらも同点になる退化（比較にならない
    2分布）は構成の段階で起こらない。総度数は両方そろえるので、度数のまま重ねて
    比べてよい。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    span_a = int(draw({"int_set": list(_SPAN_CHOICES)}, rng))
    span_b = int(draw({"int_set": [s for s in _SPAN_CHOICES if s != span_a]}, rng))
    start_a = int(draw({"int_range": [0, n_classes - span_a]}, rng))
    start_b = int(draw({"int_range": [0, n_classes - span_b]}, rng))
    window_a = list(range(start_a, start_a + span_a))
    window_b = list(range(start_b, start_b + span_b))
    peak_a = int(draw({"int_set": window_a}, rng))
    peak_b = int(draw({"int_set": [i for i in window_b if i != peak_a]}, rng))
    total = int(draw(p["total_domain"], rng))
    freq_a = _allocate(total, window_a, peak_a, int(draw({"int_range": [0, span_a - 1]}, rng)), n_classes)
    freq_b = _allocate(total, window_b, peak_b, int(draw({"int_range": [0, span_b - 1]}, rng)), n_classes)

    solver = REGISTRY.solver("math.compare_distribution_shape")
    sol = cast(Solution, solver(freq_a, freq_b, _GROUP_A, _GROUP_B))
    assert isinstance(sol.answer, ChoiceAnswer)

    chart_kind = str(draw(p["chart_kind"], rng))
    chart_word = "ヒストグラム" if chart_kind == "histogram" else "度数折れ線"
    statement = (
        f"{_GROUP_A}と{_GROUP_B}（どちらも{total}人）の{scene}を、{lo}{unit}から"
        f"{width}{unit}ずつの同じ階級に分けて、2つの{chart_word}を1つのグラフに重ねて"
        f"表した（{_GROUP_A}は実線、{_GROUP_B}は破線）。散らばりが大きいのはどちらの組か、"
        f"また値の大きいほうの階級に人数が偏っているのはどちらの組か、グラフの形をもとに答えよ"
    )

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freq_a,
        "frequencies_b": freq_b,
        "chart_kind": chart_kind,
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="read_table", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"condition": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=True),
        recipe="math.compare_distribution_shape",
    )


# ---------------------------------------------------------------------------
# g1_l55.graph_table Lv2: 相対度数を求め度数折れ線をかく
# ---------------------------------------------------------------------------
_RELATIVE_POLYGON_CONCEPTS = ["frequency_polygon.draw_relative_frequency"]


# 相対度数がすべて小数で書き切れる総度数（2 と 5 だけでできた数）。
# 度数を独立に引いていたので総度数が36人になり「相対度数は 1/6」と出ていた
# （EVALUATION D-24 の取りこぼし＝R-6）。教科書は総度数を 20・25・40・50 のような
# きりのよい人数にとる。度数の定義域（2〜12）は狭めていない。
_TERMINATING_TOTALS = (20, 25, 40, 50)


def _draw_terminating_freqs(p: Mapping[str, Any], n_classes: int, rng: Rng) -> list[int]:
    """総度数がきりのよい人数になる度数の組（各階級の相対度数が必ず小数で書ける）。

    最後の1つを「合計が目標になる値」に決めるだけで、他の階級は今までどおり自由に
    引く（組み合わせは十分残る）。目標に届かない引きになったら引き直す。
    """
    lo, hi = (int(v) for v in cast("list[object]", p["frequency_domain"]["int_range"]))
    for _ in range(200):
        total = int(draw({"int_set": list(_TERMINATING_TOTALS)}, rng))
        head = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes - 1)]
        last = total - sum(head)
        if lo <= last <= hi and len(set([*head, last])) > 1:
            return [*head, last]
    raise ValueError("_draw_terminating_freqs: 総度数がきりのよい人数になる度数を構成できず")


def _avoid_flat(freqs: list[int], rng: Rng) -> list[int]:
    """度数が全部同じ（分布の形が読めない）退化を1つだけ持ち上げて避ける。"""
    if len(set(freqs)) > 1:
        return freqs
    out = list(freqs)
    out[int(draw({"int_range": [0, len(out) - 1]}, rng))] += 1
    return out


def _as_unimodal(freqs: list[int], rng: Rng) -> list[int]:
    """度数を**山が1つ**の並びに直す（合計は変えない）。

    階級ごとに独立に引いていたので、度数が 10・4・11・3・12 のような並びになり、
    **度数折れ線をかかせる問題で、かいた折れ線がギザギザになっていた。**
    実物の度数分布はほぼ単峰で、生徒が「分布の形」を読み取れるのはそのため。

    値そのものは変えず、並べ替えるだけ（総度数がきりのよい人数になる、という
    `_draw_terminating_freqs` の条件を壊さない）。大きい順に取り出して、
    山の左右へ交互に置くと必ず単峰になる。どちら側から置き始めるかで山の位置が動く。
    """
    vals = sorted(freqs, reverse=True)
    left: list[int] = []
    right: list[int] = []
    flip = int(draw({"int_range": [0, 1]}, rng))
    for i, v in enumerate(vals[1:]):
        (left if (i + flip) % 2 == 0 else right).append(v)
    return [*reversed(left), vals[0], *right]


@register_recipe("math.relative_frequency_polygon", provides_concepts=_RELATIVE_POLYGON_CONCEPTS)
def relative_frequency_polygon_recipe(ctx: CellContext, rng: Rng) -> MR:
    """度数分布表から相対度数を求め、度数折れ線をかく（answer-first・「かく」）。

    度数分布表（本文に出る度数）を先に構成する。各階級の度数は 1 以上・総度数未満に
    なるので相対度数が 0 や 1 に潰れない。問題図は目盛だけの空のグラフ用紙で、
    模範解答図は度数折れ線つき。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    freqs = _as_unimodal(_draw_terminating_freqs(p, n_classes, rng), rng)

    solver = REGISTRY.solver("math.relative_frequency_polygon")
    sol = cast(Solution, solver(freqs, lo, width, unit))
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freqs,
        "unit": unit,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    statement = (
        f"次の度数分布表は、ある中学校の生徒{sum(freqs)}人の{scene}を調べたものである。"
        f"各階級の相対度数を求めて表を完成させ、この分布の度数折れ線をかけ。"
        f"〔階級と度数：{_table_text(lo, width, freqs, unit)}〕"
    )
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_frequency_chart_solution_svg(params),
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"data_table": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=False),
        recipe="math.relative_frequency_polygon",
    )


# ---------------------------------------------------------------------------
# g1_l55.graph_table Lv3: 総度数の異なる2集団を相対度数で比べる
# （solver は既存 math.compare_relative_frequency をそのまま再利用＝新 solver ゼロ）
# ---------------------------------------------------------------------------
_COMPARE_GROUPS_CONCEPTS = ["frequency_polygon.compare_groups_by_relative_frequency"]
_SCHOOL_A = "A校"
_SCHOOL_B = "B校"


@register_recipe(
    "math.compare_relative_frequency_chart", provides_concepts=_COMPARE_GROUPS_CONCEPTS
)
def compare_relative_frequency_chart_recipe(ctx: CellContext, rng: Rng) -> MR:
    """総度数の異なる2つの度数折れ線を相対度数で比べる（answer-first・「読む」）。

    answer-first: 2本の度数列を構成したあと、(a) 総度数が相異なる (b) 対象の階級の
    相対度数が相異なる の両方が成り立つまで、B の**対象外**の階級の度数を1ずつ足す。
    B の対象階級の度数は動かさないので相対度数は総度数について狭義単調に動き、
    (a)(b) をともに壊す値は高々2つ＝3回以内に必ず両立する（拒否ではなく構成で担保）。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)

    def _is_decimal(freq: int, total: int) -> bool:
        """相対度数が**小数第2位まで**で書き切れるか（グラフから読み取る問題なので）。

        前は「小数第3位まで」としていて 7/32 = 0.21875 が通っていた。5桁の
        相対度数はグラフの目盛からは読めない。実物の度数分布は総度数を
        20・25・40・50 のようにとり、相対度数は 0.35・0.20 と2桁で書ける。
        """
        return (sympy.Rational(freq, total) * 100).q == 1

    # 総度数を独立に決めていたので「A: 7/36、B: 3/35」という、割合として比べにくい
    # 答えが出ていた。**両方の相対度数が小数で書ける組**になるまで引き直す。
    # 相対度数を小数第2位までに絞ったぶん試行回数を増やす（200 回では 100 seed 中
    # 3 回まで構成に失敗していた＝`retry_stats` が拾った）。
    for _ in range(2000):
        freq_a = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)]
        freq_b = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)]
        target = int(draw({"int_range": [0, n_classes - 1]}, rng))
        filler = (target + 1) % n_classes

        total_a = sum(freq_a)
        for _ in range(4):
            total_b = sum(freq_b)
            distinct_total = total_b != total_a
            distinct_ratio = sympy.Rational(freq_b[target], total_b) != sympy.Rational(
                freq_a[target], total_a
            )
            if distinct_total and distinct_ratio:
                break
            freq_b[filler] += 1
        total_b = sum(freq_b)
        if (
            total_b != total_a
            and _is_decimal(freq_a[target], total_a)
            and _is_decimal(freq_b[target], total_b)
        ):
            break
    else:
        raise ValueError(
            "compare_relative_frequency_chart_recipe: 相対度数が小数になる度数を構成できず"
        )

    solver = REGISTRY.solver("math.compare_relative_frequency")
    sol = cast(Solution, solver(freq_a[target], total_a, freq_b[target], total_b))
    assert isinstance(sol.answer, SymbolicAnswer)

    t_lo = lo + width * target
    t_hi = t_lo + width
    statement = (
        f"{_SCHOOL_A}の生徒{total_a}人と{_SCHOOL_B}の生徒{total_b}人の{scene}を調べ、"
        f"{lo}{unit}から{width}{unit}ずつの同じ階級に分けて、2つの度数折れ線を1つの"
        f"グラフに重ねて表した（{_SCHOOL_A}は実線、{_SCHOOL_B}は破線）。"
        f"{t_lo}{unit}以上{t_hi}{unit}未満の階級について、それぞれの相対度数をグラフから"
        f"読み取って求め、この階級の割合が大きいのはどちらの学校か答えよ"
    )

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freq_a,
        "frequencies_b": freq_b,
        "target_index": target,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="read_table", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"condition": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=True),
        recipe="math.compare_relative_frequency_chart",
    )


# ---------------------------------------------------------------------------
# g1_l56.graph_table Lv2: 累積度数の表と折れ線をかく
# ---------------------------------------------------------------------------
_CUMULATIVE_CHART_CONCEPTS = ["cumulative_chart.draw_polyline"]


@register_recipe("math.cumulative_frequency_chart", provides_concepts=_CUMULATIVE_CHART_CONCEPTS)
def cumulative_frequency_chart_recipe(ctx: CellContext, rng: Rng) -> MR:
    """累積度数の欄を完成させ累積度数の折れ線をかく（answer-first・「かく」）。

    params には**本文に出ている度数**だけを置き、累積度数（導出値）は置かない。
    累積は土台の描画も solver も度数列から計算する。各階級の度数は 1 以上なので
    累積度数は真に増加し、度数が全部同じ（折れ線が直線に潰れる）退化も避ける。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    freqs = _as_unimodal(
        _avoid_flat([int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)], rng), rng)

    solver = REGISTRY.solver("math.cumulative_frequency_chart")
    sol = cast(Solution, solver(freqs, lo, width, unit))
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freqs,
        "unit": unit,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    statement = (
        f"次の度数分布表は、ある中学校の生徒{sum(freqs)}人の{scene}を調べたものである。"
        f"累積度数の欄を計算して表を完成させ、その累積度数を表す折れ線グラフをかけ。"
        f"〔階級と度数：{_table_text(lo, width, freqs, unit)}〕"
    )
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_frequency_chart_solution_svg(params),
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"data_table": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=False),
        recipe="math.cumulative_frequency_chart",
    )


# ---------------------------------------------------------------------------
# g1_l56.graph_table Lv3: 累積の折れ線から中央値のふくまれる階級を読む
# ---------------------------------------------------------------------------
_MEDIAN_CLASS_CONCEPTS = ["cumulative_chart.read_median_class"]


@register_recipe(
    "math.median_class_from_cumulative", provides_concepts=_MEDIAN_CLASS_CONCEPTS
)
def median_class_from_cumulative_recipe(ctx: CellContext, rng: Rng) -> MR:
    """累積度数の折れ線から中央値のふくまれる階級を読む（answer-first・「読む」）。

    答えが端の階級に寄って「読まなくても分かる」退化を構成で防ぐ: 5 階級・各階級の
    度数を下限3以上の範囲から引くと、どの階級の度数も残り4階級の合計を超えられない
    ので、中央値の階級は必ず内側（両端ではない）になる。さらに総度数を奇数に整えて
    「ちょうど半分」の同点（階級が一意に決まらない）を起こさない。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    freqs = _as_unimodal(
        _avoid_flat([int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)], rng), rng)
    if sum(freqs) % 2 == 0:
        freqs[int(draw({"int_range": [0, n_classes - 1]}, rng))] += 1

    solver = REGISTRY.solver("math.median_class_from_cumulative")
    sol = cast(Solution, solver(freqs, lo, width, unit))
    assert isinstance(sol.answer, SymbolicAnswer)

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freqs,
        "unit": unit,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    statement = (
        f"ある中学校の生徒{sum(freqs)}人の{scene}を、{lo}{unit}から{width}{unit}ずつの"
        f"階級に分け、累積度数を表す折れ線グラフに表した。累積度数が全体のちょうど半分に"
        f"達するのはどの階級か読み取り、この分布の中央値がふくまれる階級を答えよ"
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="read_table", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"situation_params": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=True),
        recipe="math.median_class_from_cumulative",
    )


# ---------------------------------------------------------------------------
# g1_l58.graph_table Lv3: 2分布の度数折れ線を1つのグラフに重ねてかく
# ---------------------------------------------------------------------------
_OVERLAY_CONCEPTS = ["distribution_comparison.construct_overlaid_charts"]


@register_recipe("math.overlay_frequency_polygons", provides_concepts=_OVERLAY_CONCEPTS)
def overlay_frequency_polygons_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2つの度数分布表を1つのグラフに重ねて度数折れ線でかく（answer-first・「かく」）。

    answer-first: 一方の度数列を作り、もう一方はそれを階級方向にずらした列にする。
    階級数を素数（5）にしてあるので、ずらし幅が 0 でない限り 2 本が一致することは
    「全階級が同じ度数」の場合しかなく、それは山を一意に立てる構成で除かれている。
    総度数がそろうので、度数のまま重ねて比べてよい（相対度数に直す必要がない）。
    山の位置も必ずずれるので「傾向のちがい」が読める。
    """
    p = ctx.spec_level.params
    n_classes = int(draw(p["n_classes"], rng))
    scene, unit, lo, width = _scene(rng)
    base = [int(draw(p["frequency_domain"], rng)) for _ in range(n_classes)]
    freq_a, _peak = _unique_peak(base, rng, cast("dict[str, Any]", p["peak_bonus_domain"]))
    shift = int(draw({"int_range": [1, n_classes - 1]}, rng))
    freq_b = freq_a[shift:] + freq_a[:shift]

    solver = REGISTRY.solver("math.overlay_frequency_polygons")
    sol = cast(Solution, solver(freq_a, freq_b, lo, width, _GROUP_A, _GROUP_B, unit))
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "class_lo": lo,
        "class_width": width,
        "frequencies": freq_a,
        "frequencies_b": freq_b,
        "unit": unit,
        "chart_kind": str(draw(p["chart_kind"], rng)),
    }
    statement = (
        f"{_GROUP_A}と{_GROUP_B}（どちらも{sum(freq_a)}人）の{scene}が、次の2つの度数分布表で"
        f"与えられている。2つの組の分布のちがいがはっきり伝わるように、それぞれの度数折れ線を"
        f"1つのグラフに重ねてかけ。"
        f"〔{_GROUP_A}：{_table_text(lo, width, freq_a, unit)}〕"
        f"〔{_GROUP_B}：{_table_text(lo, width, freq_b, unit)}〕"
    )
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_frequency_chart_solution_svg(params),
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr(
        ctx, params=params, given={"data_table": statement},
        sub_question=sub_question, visual_plan=_visual_plan(params, drawn=False),
        recipe="math.overlay_frequency_polygons",
    )


__all__ = [
    "read_distribution_chart_recipe",
    "tabulate_and_draw_histogram_recipe",
    "compare_distribution_shape_recipe",
    "relative_frequency_polygon_recipe",
    "compare_relative_frequency_chart_recipe",
    "cumulative_frequency_chart_recipe",
    "median_class_from_cumulative_recipe",
    "overlay_frequency_polygons_recipe",
]
