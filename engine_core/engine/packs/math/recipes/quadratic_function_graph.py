"""関数 y=ax² の graph_table（かく／読む）recipe 群（構成的生成・answer-first。§6.1）。

C6（g3 二次関数 y=ax²）の graph_table 8 セル:
  - g3_l33 Lv1「読む」: 放物線のグラフ上の2点の座標を読み取る
  - g3_l33 Lv2「かく」: 対応表から座標をとって放物線を2本かき、開き方を比べる
  - g3_l34 Lv2「かく」: 放物線をかき、x の変域に対応する部分をなぞって y の変域を読む
  - g3_l36 Lv2「かく」: 身のまわりの2乗に比例する現象の表からグラフをかく
  - g3_l37 Lv2「かく」: 放物線と直線をかき、囲まれた部分を斜線で示す
  - g3_l38 Lv2「読む」: 動点がつくる面積-時間グラフ（折れ線）から2つの値を読み取る
  - g3_l38 Lv3「かく」: 区間ごとに式が変わる面積のグラフ（折れ線）をかく

規約（既存の graph_table セルと共通）:
  - 「かく」セルの問題図は**空の方眼**（visual_plan.elements に描画対象を宣言しない）。
    模範解答図は visual 層の純ヘルパで描き GraphAnswer.solution_svg_ref に入れる。
  - 「読む」セルは given に式を出さない（計算で解けてしまう題材の破綻を避ける）。
  - visual_plan.labels は `tick_labels_from_params` から機械的に作る（G-Q5v）。
  - 乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。退化・範囲外は
    「候補を絞ってから draw する」ことで構成時に排除する（鉄則⑤）。
"""
from __future__ import annotations

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
from engine.packs.math.recipes.letter_expr import _draw_distinct_points
from engine.packs.math.recipes.polynomial import _domain_candidates, _fmt_poly_x_terms
from engine.packs.math.visuals.graph import (
    render_curve_domain_solution_svg,
    render_curve_line_solution_svg,
    render_curve_pair_solution_svg,
    render_curve_solution_svg,
    render_polyline_solution_svg,
    tick_labels_from_params,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _empty_grid_plan(params: dict[str, Any]) -> VisualPlan:
    """「かく」セルの問題図＝空の方眼（生徒が描き込む・描画対象を宣言しない）。"""
    return VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params),
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )


def _rational_candidates(dens_spec: Any, nums_spec: Any) -> list[sympy.Rational]:
    """比例定数 a の候補（分母 a_den_set・分子 a_num_domain の既約分数、0 を除く）。

    y=ax² は自由度が a ひとつしかないため、分母を許して候補数を確保する
    （台帳の example も y=(1/2)x²）。
    """
    dens = [int(v) for v in cast("list[int]", dens_spec)]
    nums = [v for v in _domain_candidates(cast("dict[str, object]", nums_spec)) if v != 0]
    out: list[sympy.Rational] = []
    for d in dens:
        for n in nums:
            r = sympy.Rational(n, d)
            if r.q != d:
                continue  # 既約でない（別の分母の候補と重複する）
            out.append(r)
    return out


def _mr_common(
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
# math.read_two_points_on_parabola（g3_l33.graph_table Lv1・読む）
#
# 放物線の頂点（原点）は a によらず一定＝それ自体を答えにすると退化するので、
# 「グラフ上の2点の座標を読み取る」を答えにする（頂点・開き方の性質は同 unit の
# knowledge Lv1 が受け持つ）。solver は既存の math.read_two_lattice_points を
# そのまま再利用する（新 solver ゼロ）。
# ---------------------------------------------------------------------------
_READ_PARABOLA_CONCEPTS = ["parabola_graph.read_points"]


@register_recipe("math.read_two_points_on_parabola", provides_concepts=_READ_PARABOLA_CONCEPTS)
def read_two_points_on_parabola(ctx: CellContext, rng: Rng) -> MR:
    """放物線のグラフ上の2点の座標を読み取る（g3_l33.graph_table Lv1・answer-first）。

    比例定数 a（非0の整数）と、読み取る2点の x 座標（非0・相異なる整数）を引く。
    グリッドに収まるよう |a·x²| ≦ value_bound を満たす候補だけに絞ってから draw する。
    given に式（y=ax²）は出さない——出すと「グラフから読む」題材が計算で解けてしまう。
    """
    p = ctx.spec_level.params
    bound = int(cast(int, p["value_bound"]))
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]

    a_ok = [a for a in a_cands if sum(1 for x in x_cands if abs(a) * x * x <= bound) >= 2]
    a = int(draw({"int_set": a_ok}, rng))
    x_ok = [x for x in x_cands if abs(a) * x * x <= bound]
    x1, x2 = sorted(int(v) for v in draw_many({"int_set": x_ok, "distinct": ["value"]}, rng, k=2))
    n1, n2 = _draw_distinct_points(2, rng)

    a_s = sympy.Integer(a)
    pt1 = (sympy.Integer(x1), a_s * x1**2)
    pt2 = (sympy.Integer(x2), a_s * x2**2)

    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = cast(Solution, solver(pt1, pt2))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Tuple(*pt1), sympy.Tuple(*pt2))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成した点 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    condition = (
        f"右の図は、関数 y = ax² のグラフである。このグラフ上で、x 座標が {x1} である点を {n1}、"
        f"x 座標が {x2} である点を {n2} とするとき、点 {n1} と点 {n2} の座標を"
        f"それぞれグラフから読み取れ"
    )

    params: dict[str, Any] = {
        "curve_kind": "parabola",
        "coeff": str(a_s),
        "pts": [str(pt1), str(pt2)],
        "x1": x1,
        "x2": x2,
        "labels": f"{n1}{n2}",
    }
    visual_plan = VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params),
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            VisualElement(kind="curve", attrs={}),
        ],
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="read_point", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given={"situation_params": condition},
        sub_question=sub_question, visual_plan=visual_plan,
        recipe="math.read_two_points_on_parabola",
    )


# ---------------------------------------------------------------------------
# math.draw_two_parabolas（g3_l33.graph_table Lv2・かく）
# ---------------------------------------------------------------------------
_DRAW_TWO_PARABOLAS_CONCEPTS = ["parabola_graph.draw_from_table"]


@register_recipe("math.draw_two_parabolas", provides_concepts=_DRAW_TWO_PARABOLAS_CONCEPTS)
def draw_two_parabolas(ctx: CellContext, rng: Rng) -> MR:
    """対応表から座標をとって放物線を2本かき、開き方を比べる（g3_l33.graph_table Lv2）。

    台帳の example（y=(1/2)x² の対応表をつくって放物線をかき、同じ座標軸に y=2x² を
    かいて開き方を比べる）をそのまま構造にする。比例定数 a を2つ（相異）と対応表の
    x の範囲を引き、|a·x²| ≦ value_bound を満たす候補だけに絞る（方眼が潰れない範囲）。
    """
    p = ctx.spec_level.params
    bound = int(cast(int, p["value_bound"]))
    x_lo = int(draw(p["table_lo_domain"], rng))
    x_hi = int(draw(p["table_hi_domain"], rng))
    m = max(abs(x_lo), abs(x_hi)) ** 2
    cands = [a for a in _rational_candidates(p["a_den_set"], p["a_num_domain"]) if abs(a) * m <= bound]
    a1 = sympy.nsimplify(draw({"int_set": cands}, rng))
    # a2 は |a2| ≠ |a1| に絞る（a1=a2 は2本が重なり、a1=-a2 は開き方の広さが等しいため
    # 「どちらの開き方がせまいか」の答えが一意に決まらない＝退化。構成時に排除する）。
    a2 = sympy.nsimplify(draw({"int_set": [c for c in cands if abs(c) != abs(a1)]}, rng))

    solver = REGISTRY.solver("math.draw_two_parabolas_features")
    sol = cast(Solution, solver(a1, a2, x_lo, x_hi))
    assert isinstance(sol.answer, GraphAnswer)
    # 開き方（|a| が大きいほどせまい）が構成どおりであることを確かめる。
    narrower = a1 if abs(a1) > abs(a2) else a2
    assert any(str(narrower) in f.display for f in sol.answer.features if f.kind == "narrower_curve")

    xs = list(range(x_lo, x_hi + 1))
    corner = max(abs(x_lo), abs(x_hi))
    params: dict[str, Any] = {
        "curve_kind": "parabola",
        "coeff": str(a1),
        "coeff2": str(a2),
        "table_lo": x_lo,
        "table_hi": x_hi,
        # 方眼の範囲は「2本の曲線が表の端で到達する点」で決める（決定論）。
        "pts": [
            str((sympy.Integer(-corner), max(abs(a1), abs(a2)) * corner**2)),
            str((sympy.Integer(corner), -max(abs(a1), abs(a2)) * corner**2)),
        ],
    }
    solution_svg = render_curve_pair_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    expr1 = f"y = {_fmt_poly_x_terms([(a1, 2)])}"
    expr2 = f"y = {_fmt_poly_x_terms([(a2, 2)])}"
    table_x = "、".join(str(v) for v in xs)
    given = {
        "expression": f"{expr1} と {expr2}",
        "situation_params": (
            f"x = {table_x} のときの y の値をそれぞれ求めて対応表をつくり、"
            f"その値を座標としてとって、同じ座標軸に放物線をかけ。また、開き方のちがいを比べよ"
        ),
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given=given, sub_question=sub_question,
        visual_plan=_empty_grid_plan(params), recipe="math.draw_two_parabolas",
    )


# ---------------------------------------------------------------------------
# math.draw_parabola_domain（g3_l34.graph_table Lv2・かく）
# ---------------------------------------------------------------------------
_DRAW_PARABOLA_DOMAIN_CONCEPTS = ["parabola_graph.domain_on_graph"]


@register_recipe("math.draw_parabola_domain", provides_concepts=_DRAW_PARABOLA_DOMAIN_CONCEPTS)
def draw_parabola_domain(ctx: CellContext, rng: Rng) -> MR:
    """放物線をかき、x の変域に対応する部分をなぞって y の変域を読む（g3_l34.graph_table Lv2）。

    x の変域の両端を先に引き（x_lo < x_hi）、その範囲で方眼に収まる比例定数だけに
    絞ってから a を引く（鉄則⑤: 実行時のリトライではなく構成時に保証）。
    """
    p = ctx.spec_level.params
    bound = int(cast(int, p["value_bound"]))
    x_lo, x_hi = sorted(
        int(v) for v in draw_many({**cast("dict[str, Any]", p["x_domain"]), "distinct": ["value"]}, rng, k=2)
    )
    m = max(abs(x_lo), abs(x_hi)) ** 2
    cands = [a for a in _rational_candidates(p["a_den_set"], p["a_num_domain"]) if abs(a) * m <= bound]
    a = sympy.nsimplify(draw({"int_set": cands}, rng))

    solver = REGISTRY.solver("math.draw_parabola_domain_features")
    sol = cast(Solution, solver(a, x_lo, x_hi))
    assert isinstance(sol.answer, GraphAnswer)

    corner = max(abs(x_lo), abs(x_hi))
    params: dict[str, Any] = {
        "curve_kind": "parabola",
        "coeff": str(a),
        "arc_x_lo": x_lo,
        "arc_x_hi": x_hi,
        "pts": [
            str((sympy.Integer(-corner), abs(a) * corner**2)),
            str((sympy.Integer(corner), -abs(a) * corner**2)),
        ],
    }
    solution_svg = render_curve_domain_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    given = {
        "expression": f"y = {_fmt_poly_x_terms([(a, 2)])}",
        "x_domain": f"{x_lo} ≦ x ≦ {x_hi}",
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given=given, sub_question=sub_question,
        visual_plan=_empty_grid_plan(params), recipe="math.draw_parabola_domain",
    )


# ---------------------------------------------------------------------------
# math.draw_phenomenon_curve（g3_l36.graph_table Lv2・かく）
# 身のまわりの2乗に比例する現象（斜面を転がる球・落下・制動距離）の表からグラフをかく。
# x も y も 0 以上の量で単位が違うので、座標平面ではなく量-量グラフ（grid_mode=quantity）。
# ---------------------------------------------------------------------------
_PHENOMENON_CONCEPTS = ["parabola_graph.phenomenon_table"]

# (場面文の書式, x の単位ラベル, y の単位ラベル, 比例定数の決まり方)。
# {a} は比例定数を入れない（式は与えず表だけを与える＝表からグラフをかく題材）。
#
# **場面によっては比例定数が現実で決まっている。** 前は a を 1〜20 から自由に引いて
# いたので、
#
#   「ある高さから物体を落とすとき… x: 0,1,2,3 ／ y: 0,13,52,117」 → y = 13x²
#
# が出ていた。自由落下は y ≒ 4.9x²（教材は 5x²）で、13x² の世界は存在しない。
# 制動距離の版は実際の 40 倍だった。
#
# 4つ目は取りうる比例定数の集合。5つ目は表の x が 0 から始まるか
# （動き出しの 0 秒は自然だが、「1辺 0cm の正方形」は図形にならない）。
#
# **斜面も「自由」ではない。** 一度そう書いて y = 13x² の坂を出した。
# 斜面を下る運動は a = (1/2)g·sinθ なので、**自由落下の 5 を超えられない**。
# 傾きで変わるのは 1〜4 の範囲だけ。
_SLOPE_A = (1, 2, 3, 4)
# 6つ目は題材（`{o}` に入る語）。**ありえる比例定数だけにすると組が減るので、
# 数ではなく題材で軸を戻す**（数を広げると y=13x² の坂に逆戻りする）。
_PHENOMENON_SCENES: list[tuple[str, str, str, tuple[int, ...], bool, tuple[str, ...]]] = [
    ("ある斜面で{o}を転がすとき、転がり始めてからの時間 x 秒と、その間に転がる距離 y m",
     "秒", "m", _SLOPE_A, True, ("ボール", "鉄の球", "ビー玉", "木の球")),
    ("なめらかな坂を{o}が下るとき、動き始めてからの時間 x 秒と、その間に進む距離 y m",
     "秒", "m", _SLOPE_A, True, ("台車", "そり", "空き缶")),
    ("ある高さから{o}を落とすとき、落ち始めてからの時間 x 秒と、その間に落ちる距離 y m",
     "秒", "m", (5,), True, ("物体", "小石", "おもり")),  # 自由落下 y ≒ 4.9x²（教材は 5x²）
    ("1辺の長さ x cm と、その{o}の面積 y cm²",
     "cm", "cm²", (1,), False, ("正方形", "正方形のタイル", "正方形の紙")),
    ("縦の長さ x cm と、横が縦の2倍である{o}の面積 y cm²",
     "cm", "cm²", (2,), False, ("長方形", "長方形の板", "長方形の花だん")),
    ("縦の長さ x cm と、横が縦の3倍である{o}の面積 y cm²",
     "cm", "cm²", (3,), False, ("長方形", "長方形の板", "長方形の花だん")),
    ("縦の長さ x cm と、横が縦の4倍である{o}の面積 y cm²",
     "cm", "cm²", (4,), False, ("長方形", "長方形の板", "長方形の花だん")),
    ("縦の長さ x cm と、横が縦の5倍である{o}の面積 y cm²",
     "cm", "cm²", (5,), False, ("長方形", "長方形の板", "長方形の花だん")),
    ("1辺の長さ x cm と、その{o}の表面積 y cm²",
     "cm", "cm²", (6,), False, ("立方体", "立方体の箱", "さいころの形の積み木")),
]


@register_recipe("math.draw_phenomenon_curve", provides_concepts=_PHENOMENON_CONCEPTS)
def draw_phenomenon_curve(ctx: CellContext, rng: Rng) -> MR:
    """2乗に比例する現象の表からグラフをかく（g3_l36.graph_table Lv2・answer-first）。

    表の行数 n・x の刻み d・比例定数 a を引く。y の最大値が方眼に収まるよう
    a·(n·d)² ≦ value_bound を満たす a だけに絞ってから draw する（鉄則⑤）。
    """
    p = ctx.spec_level.params
    bound = int(cast(int, p["value_bound"]))
    rows = int(draw(p["rows_domain"], rng))
    step = int(draw(p["step_domain"], rng))
    # **a を先に引き、その a と両立する場面だけから選ぶ。**
    # 場面を先に選ぶと、a が現実で決まっている場面（落下・図形）に抽選が集中して
    # 重複率が跳ねる（実測 0.49）。この順にすると a の広さが場面にも行き渡る。
    # 実在する場面が持てる比例定数だけ（YAML の a_domain との共通部分）。
    # 場面の側で決まっているので、a_domain を広げても現実の値は増えない。
    allowed = {v for s in _PHENOMENON_SCENES for v in s[3]}
    a_cands = [
        v for v in _domain_candidates(p["a_domain"])
        if v in allowed and v * (rows * step) ** 2 <= bound
    ]
    a = int(draw({"int_set": a_cands}, rng))
    ok = [i for i, s in enumerate(_PHENOMENON_SCENES) if a in s[3]]
    scene_idx = int(draw({"int_set": ok}, rng))
    scene, x_unit, y_unit, _allowed_a, from_zero, items = _PHENOMENON_SCENES[scene_idx]
    item = str(draw(list(items), rng))
    scene = scene.format(o=item)

    xs = [step * i for i in range(0 if from_zero else 1, rows + 1)]
    ys = [a * x * x for x in xs]

    solver = REGISTRY.solver("math.draw_quantity_curve_features")
    sol = cast(Solution, solver(a, xs))
    assert isinstance(sol.answer, GraphAnswer)
    assert len(sol.answer.features) == len(xs)

    params: dict[str, Any] = {
        "curve_kind": "parabola",
        "coeff": str(a),
        "rows": rows,
        "step": step,
        # 表の x がどこから始まるか。**checker は 0 決め打ちで組み直していた**ので、
        # 「1辺 0cm の正方形」を避けて 1 から始めた途端に G-Q1 が落ちた。
        "x_from": 0 if from_zero else 1,
        "scene": scene_idx,
        # 題材も params に載せる。**載せないと dup_key から見えず、軸を増やしても
        # 重複率が下がらない**（実測 0.40 → 0.35 で止まったのはこれ）。
        "item": item,
        "grid_mode": "quantity",
        "pts": [str((sympy.Integer(x), sympy.Integer(y))) for x, y in zip(xs, ys, strict=True)],
    }
    solution_svg = render_curve_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    table = (
        f"x（{x_unit}）: " + "、".join(str(v) for v in xs) + f" ／ y（{y_unit}）: "
        + "、".join(str(v) for v in ys)
    )
    given = {"situation_params": scene, "data_table": table}
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given=given, sub_question=sub_question,
        visual_plan=_empty_grid_plan(params), recipe="math.draw_phenomenon_curve",
    )


# ---------------------------------------------------------------------------
# math.draw_parabola_and_line（g3_l37.graph_table Lv2・かく）
# answer-first: 交点の x 座標 xA,xB（相異・非0の整数）と比例定数 a（非0）を先に決め、
# m=a(xA+xB), b=-a·xA·xB を逆算する（find_value 側 g3_l37 と同じ構成）。
# ---------------------------------------------------------------------------
_PARABOLA_LINE_CONCEPTS = ["parabola_graph.enclosed_region"]


@register_recipe("math.draw_parabola_and_line", provides_concepts=_PARABOLA_LINE_CONCEPTS)
def draw_parabola_and_line(ctx: CellContext, rng: Rng) -> MR:
    """放物線と直線をかき、囲まれた部分を斜線で示す（g3_l37.graph_table Lv2・answer-first）。"""
    p = ctx.spec_level.params
    bound = int(cast(int, p["value_bound"]))
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]

    a_ok = [a for a in a_cands if sum(1 for x in x_cands if abs(a) * x * x <= bound) >= 2]
    a = int(draw({"int_set": a_ok}, rng))
    x_ok = [x for x in x_cands if abs(a) * x * x <= bound]
    xa, xb = sorted(int(v) for v in draw_many({"int_set": x_ok, "distinct": ["value"]}, rng, k=2))
    n1, n2 = _draw_distinct_points(2, rng)

    m = a * (xa + xb)
    b = -a * xa * xb
    assert b != 0  # xa≠xb・a≠0 より構成的に保証（交点が2つ・囲まれた部分が退化しない）

    solver = REGISTRY.solver("math.draw_parabola_line_features")
    sol = cast(Solution, solver(a, m, b))
    assert isinstance(sol.answer, GraphAnswer)
    expected = {
        sympy.srepr(sympy.Tuple(sympy.Symbol("intersection"), sympy.Integer(x), sympy.Integer(a * x * x)))
        for x in (xa, xb)
    }
    assert {f.srepr for f in sol.answer.features} == expected, (
        f"double-solve 不一致: 構成した交点 {expected} != solver 再計算 "
        f"{ {f.srepr for f in sol.answer.features} }"
    )

    corner = max(abs(xa), abs(xb))
    ya, yb = a * xa * xa, a * xb * xb
    params: dict[str, Any] = {
        "curve_kind": "parabola",
        "coeff": str(a),
        "line_m": str(m),
        "line_b": str(b),
        "hatch_x_lo": xa,
        "hatch_x_hi": xb,
        "labels": f"{n1}{n2}",
        "pts": [
            str((sympy.Integer(-corner), sympy.Integer(max(ya, yb, 0)))),
            str((sympy.Integer(corner), sympy.Integer(min(ya, yb, 0)))),
        ],
    }
    solution_svg = render_curve_line_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    given = {
        "expression": f"y = {_fmt_poly_x_terms([(a, 2)])}",
        "line_a": f"y = {_fmt_poly_x_terms([(m, 1), (b, 0)]) if m != 0 else str(b)}",
        "situation_params": f"この放物線と直線の交点を {n1}、{n2} とする",
    }
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given=given, sub_question=sub_question,
        visual_plan=_empty_grid_plan(params), recipe="math.draw_parabola_and_line",
    )


# ---------------------------------------------------------------------------
# math.read_area_time_graph（g3_l38.graph_table Lv2・読む）
#
# 長方形 A=(0,0), B=(p,0), C=(p,q), D=(0,q) の周上を、点 P が B を出発して B→C→D の順に
# 毎秒 1cm で動く。三角形 ABP の面積 y は
#   0≦x≦q（P は辺 BC 上）: y=(p/2)x ／ q≦x≦q+p（P は辺 CD 上）: y=pq/2（一定）
# となり、グラフは折れ線になる。given に p・q を出さない（出すと計算で解けてしまう）。
# ---------------------------------------------------------------------------
_READ_AREA_TIME_CONCEPTS = ["parabola_graph.read_area_time"]


def _rect_area_at(p_side: int, q_side: int, t: int) -> sympy.Rational:
    """長方形の周上を動く点 P による三角形 ABP の面積（shoelace 公式・厳密値）。"""
    px, py = (sympy.Integer(p_side), sympy.Integer(t)) if t <= q_side else (
        sympy.Integer(p_side - (t - q_side)), sympy.Integer(q_side)
    )
    ax, ay = sympy.Integer(0), sympy.Integer(0)
    bx, by = sympy.Integer(p_side), sympy.Integer(0)
    return sympy.Rational(1, 2) * sympy.Abs(
        ax * (by - py) + bx * (py - ay) + px * (ay - by)
    )


@register_recipe("math.read_area_time_graph", provides_concepts=_READ_AREA_TIME_CONCEPTS)
def read_area_time_graph(ctx: CellContext, rng: Rng) -> MR:
    """動点がつくる面積-時間グラフから2つの値を読み取る（g3_l38.graph_table Lv2）。

    長方形の2辺 p・q を、面積の最大値 pq/2 と全体の時間 p+q が量-量グラフの
    目盛（1刻み）に収まる範囲に絞ってから引く（読み取りが格子点で確定する）。
    solver は既存の math.read_two_lattice_points をそのまま再利用する（新 solver ゼロ）。
    """
    p = ctx.spec_level.params
    area_max = int(cast(int, p["area_max"]))
    time_max = int(cast(int, p["time_max"]))
    p_cands = [v for v in _domain_candidates(p["side_p_domain"]) if v > 0 and v % 2 == 0]
    p_side = int(draw({"int_set": p_cands}, rng))
    q_cands = [
        v
        for v in _domain_candidates(p["side_q_domain"])
        if v > 0 and p_side * v <= 2 * area_max and p_side + v <= time_max
    ]
    q_side = int(draw({"int_set": q_cands}, rng))

    total = p_side + q_side
    t1, t2 = sorted(
        int(v) for v in draw_many({"int_range": [1, total], "distinct": ["value"]}, rng, k=2)
    )
    names = _draw_distinct_points(5, rng)
    na, nb, nc, nd, np_ = names

    y1 = _rect_area_at(p_side, q_side, t1)
    y2 = _rect_area_at(p_side, q_side, t2)
    pt1 = (sympy.Integer(t1), y1)
    pt2 = (sympy.Integer(t2), y2)

    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = cast(Solution, solver(pt1, pt2))
    assert isinstance(sol.answer, SymbolicAnswer)

    y_top = sympy.Rational(p_side * q_side, 2)
    poly_pts = [
        str((sympy.Integer(0), sympy.Integer(0))),
        str((sympy.Integer(q_side), y_top)),
        str((sympy.Integer(total), y_top)),
    ]
    params: dict[str, Any] = {
        "side_p": p_side,
        "side_q": q_side,
        "t1": t1,
        "t2": t2,
        "labels": "".join(names),
        "grid_mode": "quantity",
        "poly_pts": poly_pts,
        "pts": poly_pts,
    }
    condition = (
        f"右のグラフは、ある長方形 {na}{nb}{nc}{nd} の周上を点 {np_} が頂点 {nb} から"
        f"{nb}→{nc}→{nd} の順に一定の速さで動くときの、出発してからの時間 x 秒と"
        f"三角形 {na}{nb}{np_} の面積 y cm² の関係を表したものである。"
        f"x = {t1} のときと x = {t2} のときの面積を、それぞれグラフから読み取れ"
    )
    visual_plan = VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params),
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            VisualElement(kind="polyline", attrs={}),
        ],
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="read_point", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given={"situation_params": condition},
        sub_question=sub_question, visual_plan=visual_plan,
        recipe="math.read_area_time_graph",
    )


# ---------------------------------------------------------------------------
# math.draw_piecewise_area_graph（g3_l38.graph_table Lv3・かく）
# ---------------------------------------------------------------------------
_PIECEWISE_AREA_CONCEPTS = ["parabola_graph.piecewise_area"]


@register_recipe("math.draw_piecewise_area_graph", provides_concepts=_PIECEWISE_AREA_CONCEPTS)
def draw_piecewise_area_graph(ctx: CellContext, rng: Rng) -> MR:
    """区間ごとに式が変わる面積のグラフ（折れ線）をかく（g3_l38.graph_table Lv3）。

    1辺 s（偶数＝面積 s²/2 が整数）の正方形の周上を、点 P が A→B→C の順に毎秒 v で
    動く。v は s の約数に絞る（折れ点の時刻 s/v が整数＝目盛にのる）。面積は既存の
    solver（shoelace 公式）で再計算する（math.draw_piecewise_area_graph_features）。
    """
    p = ctx.spec_level.params
    s_cands = [v for v in _domain_candidates(p["side_domain"]) if v > 0 and v % 2 == 0]
    s = int(draw({"int_set": s_cands}, rng))
    v_cands = [v for v in _domain_candidates(p["speed_domain"]) if v > 0 and s % v == 0]
    v = int(draw({"int_set": v_cands}, rng))
    names = _draw_distinct_points(5, rng)
    na, nb, nc, nd, np_ = names

    solver = REGISTRY.solver("math.draw_piecewise_area_graph_features")
    sol = cast(Solution, solver(s, v))
    assert isinstance(sol.answer, GraphAnswer)

    t1 = sympy.Integer(s // v)
    area = sympy.Rational(s * s, 2)
    poly_pts = [
        str((sympy.Integer(0), sympy.Integer(0))),
        str((t1, area)),
        str((2 * t1, area)),
    ]
    params: dict[str, Any] = {
        "side": s,
        "speed": v,
        "labels": "".join(names),
        "grid_mode": "quantity",
        "poly_pts": poly_pts,
        "pts": poly_pts,
    }
    solution_svg = render_polyline_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    condition = (
        f"1辺が {s}cm の正方形 {na}{nb}{nc}{nd} の周上を、点 {np_} が {na} を出発して"
        f"{na}→{nb}→{nc} の順に毎秒 {v}cm で動く。出発してからの時間を x 秒、"
        f"三角形 {np_}{na}{nd} の面積を y cm² とするとき、x と y の関係を区間ごとに考えて"
        f"グラフにかけ"
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return _mr_common(
        ctx, params=params, given={"condition": condition}, sub_question=sub_question,
        visual_plan=_empty_grid_plan(params), recipe="math.draw_piecewise_area_graph",
    )


__all__ = [
    "read_two_points_on_parabola",
    "draw_two_parabolas",
    "draw_parabola_domain",
    "draw_phenomenon_curve",
    "draw_parabola_and_line",
    "read_area_time_graph",
    "draw_piecewise_area_graph",
]
