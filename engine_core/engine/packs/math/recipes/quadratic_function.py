"""関数 y=ax² まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C6（g3 二次関数 y=ax²）クラスタのうち、放物線の描画を必要としない5つの独立ソルバ
（`engine/packs/math/solvers/quadratic_function.py`）に対応する recipe を集約する。
乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.visuals.graph import tick_labels_from_params
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.recipes.polynomial import _domain_candidates, _fmt_poly_x_terms
from engine.packs.math.solvers.quadratic_function import _shoelace_area


def _parabola_points_params(a: object, x_a: object, x_b: object) -> dict[str, object]:
    """放物線と、その上の2点A・Bが収まる描画情報。

    ★**直線ABと点Pは描かない。** 直線ABの式は (1) の答えで、P は最後の答え。
    描いてよいのは本文が与えている放物線と2点まで。

    ★**縦横同じ縮尺では読めない。** x が ±5 なのに y が -75 まで下がるので、
    `grid_mode="signed_quantity"`（軸ごとに独立な縮尺）で描く。
    """
    ai, xa, xb = int(sympy.sympify(a)), int(sympy.sympify(x_a)), int(sympy.sympify(x_b))
    return {
        "curve_kind": "parabola", "coeff": str(ai),
        "grid_mode": "signed_quantity",
        "pts": [str((0, 0)), str((xa, ai * xa * xa)), str((xb, ai * xb * xb))],
        # ★放物線に式を、A・B・O に点名を書く。**本文がすべて与えている情報**
        # （放物線の式・2点の x 座標・原点）なので、答え（直線 AB の式・点 P）は
        # 漏れない。図に無いせいで、どの点が A でどの点が B か決まらなかった。
        "label_equations": True,
        "label_pts": [str((xa, ai * xa * xa)), str((xb, ai * xb * xb)), str((0, 0))],
        "label_names": ["A", "B", "O"],
    }


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# math.evaluate_quadratic_function（g3_l32.calculation Lv1）
# y=ax² に x の値を代入して y を求める。a・x は 0 を除く整数。
# ---------------------------------------------------------------------------
_EVAL_QF_CONCEPTS = ["quadratic_function.evaluate"]


@register_recipe("math.evaluate_quadratic_function", provides_concepts=_EVAL_QF_CONCEPTS)
def evaluate_quadratic_function_recipe(ctx: CellContext, rng: Rng) -> MR:
    """y=ax² に x を代入して y を求める（g3_l32.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]
    a = int(draw({"int_set": a_cands}, rng))
    x0 = int(draw({"int_set": x_cands}, rng))

    solver = REGISTRY.solver("math.evaluate_quadratic_function")
    sol = cast(Solution, solver(a, x0))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Integer(a) * sympy.Integer(x0) ** 2
    assert (expected - sympy.sympify(sol.answer.srepr)).equals(0)

    expr = _fmt_poly_x_terms([(a, 2)])

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"a": a, "x": x0},
        given={"expression": f"y = {expr}", "input_value": f"x = {x0}"},
        sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_quadratic_function"),
    )


# ---------------------------------------------------------------------------
# math.y_range_over_quadratic_domain（g3_l34.find_value Lv2/Lv3）
# ---------------------------------------------------------------------------
_RANGE_CONCEPTS = ["quadratic_function.y_range"]


def _construct_range_one_sided(rng: Rng, p: dict[str, object]) -> tuple[int, int, int]:
    """Lv2: 0の片側（単調区間）の変域を構成する。"""
    a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]
    a = int(draw({"int_set": a_cands}, rng))
    side = str(draw(["pos", "neg"], rng))
    if side == "pos":
        x_lo, x_hi = sorted(int(v) for v in draw_many(
            {"int_range": [1, 9], "distinct": ["value"]}, rng, k=2,
        ))
    else:
        x_lo, x_hi = sorted(int(v) for v in draw_many(
            {"int_range": [-9, -1], "distinct": ["value"]}, rng, k=2,
        ))
    return a, x_lo, x_hi


def _construct_range_straddles(rng: Rng, p: dict[str, object]) -> tuple[int, int, int]:
    """Lv3: 0をまたぐ変域を構成する（頂点(0,0)を含むかの吟味が必要になる）。"""
    a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]
    a = int(draw({"int_set": a_cands}, rng))
    x_lo = int(draw({"int_range": [-9, -1]}, rng))
    x_hi = int(draw({"int_range": [1, 9]}, rng))
    return a, x_lo, x_hi


@register_recipe("math.y_range_over_quadratic_domain", provides_concepts=_RANGE_CONCEPTS)
def y_range_over_quadratic_domain_recipe(ctx: CellContext, rng: Rng) -> MR:
    """y=ax² の変域を求める（g3_l34.find_value Lv2/Lv3・answer-first）。"""
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])
    if mode == "one_sided":
        a, x_lo, x_hi = _construct_range_one_sided(rng, p)
    elif mode == "straddles_zero":
        a, x_lo, x_hi = _construct_range_straddles(rng, p)
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.y_range_over_quadratic_domain")
    sol = cast(Solution, solver(a, x_lo, x_hi, mode))
    assert isinstance(sol.answer, SymbolicAnswer)

    expr = _fmt_poly_x_terms([(a, 2)])
    condition = f"関数 y = {expr} について、x の変域が {x_lo} ≦ x ≦ {x_hi} のときの y の変域を求めよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="domain_range", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"a": a, "x_lo": x_lo, "x_hi": x_hi, "mode": mode},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.y_range_over_quadratic_domain"),
    )


# ---------------------------------------------------------------------------
# math.rate_of_change_quadratic（g3_l35.find_value Lv2/Lv3）
# Lv2: mode_set=["forward"]。Lv3: mode_set=["solve_for_a","compare_intervals"]（1level内で分岐）。
# ---------------------------------------------------------------------------
_ROC_CONCEPTS = ["quadratic_function.rate_of_change"]

_ROC_ASKED_BY_MODE: dict[str, str] = {"forward": "rate_of_change", "solve_for_a": "value"}


@register_recipe("math.rate_of_change_quadratic", provides_concepts=_ROC_CONCEPTS)
def rate_of_change_quadratic_recipe(ctx: CellContext, rng: Rng) -> MR:
    """y=ax² の変化の割合を求める・逆算する・比較する（g3_l35.find_value・answer-first）。"""
    p = ctx.spec_level.params
    mode = str(draw(cast("list[str]", p["mode_set"]), rng))
    a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]

    if mode == "forward":
        a = int(draw({"int_set": a_cands}, rng))
        x1, x2 = sorted(int(v) for v in draw_many(
            {"int_range": [-9, 9], "distinct": ["value"]}, rng, k=2,
        ))
        solver = REGISTRY.solver("math.rate_of_change_quadratic")
        sol = cast(Solution, solver(a, x1, x2, mode))
        expr = _fmt_poly_x_terms([(a, 2)])
        condition = (
            f"関数 y = {expr} について、x の値が {x1} から {x2} まで増加するときの"
            f"変化の割合を求めよ"
        )
        params: dict[str, object] = {"a": a, "x1": x1, "x2": x2, "mode": mode}

    elif mode == "solve_for_a":
        a = int(draw({"int_set": a_cands}, rng))
        # x1+x2 が確実に非0になるよう、両方とも正の範囲から選ぶ（鉄則⑤: 構成時に0除算を排除）。
        x1, x2 = sorted(int(v) for v in draw_many(
            {"int_range": [1, 9], "distinct": ["value"]}, rng, k=2,
        ))
        rate = sympy.Integer(a) * (x1 + x2)
        solver = REGISTRY.solver("math.rate_of_change_quadratic")
        sol = cast(Solution, solver(rate, x1, x2, mode))
        assert isinstance(sol.answer, SymbolicAnswer)
        assert (sympy.Integer(a) - sympy.sympify(sol.answer.srepr)).equals(0)
        condition = (
            f"関数 y = ax² について、x の値が {x1} から {x2} まで"
            f"増加するときの変化の割合が {rate} であった。このとき a の値を求めよ"
        )
        params = {"a": str(rate), "x1": x1, "x2": x2, "mode": mode}

    else:
        raise ValueError(f"未知の mode: {mode!r}")

    assert isinstance(sol.answer, SymbolicAnswer)
    sub_question = SubQuestionMR(
        label="(1)", asked=_ROC_ASKED_BY_MODE[mode], answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.rate_of_change_quadratic"),
    )


# ---------------------------------------------------------------------------
# math.intersection_parabola_line（g3_l37.find_value Lv2/Lv3/Lv4）
# answer-first: 交点の x 座標 xA,xB(相異・非0の整数)と比例定数 a(非0) を先に決め、
# m=a(xA+xB), b=-a・xA・xB を逆算する（xA≠xB・a≠0 により b は自動的に非0＝O,A,B が同一直線上
# にならないことが構成的に保証される・鉄則⑤）。
# ---------------------------------------------------------------------------
_INTERSECTION_CONCEPTS = ["quadratic_function.intersection_with_line"]

# 線分ABの長さ |xB - xA|・√(1 + m²) の、根号の中の上限。
_MAX_SEGMENT_RADICAND = 65

_INTERSECTION_QUESTION_BY_MODE: dict[str, str] = {
    "find_intersection": "この交点 A, B の座標をすべて求めよ",
    "segment_and_area": (
        "線分 AB の長さと、原点 O と2点 A, B を結んでできる三角形 OAB の面積を求めよ"
    ),
    "equal_area_point": (
        "原点を O とするとき、y 軸上に O と異なる点 P をとる。"
        "三角形 PAB の面積が三角形 OAB の面積と等しくなるような点 P の座標を求めよ"
    ),
}

_INTERSECTION_ASKED_BY_MODE: dict[str, str] = {
    "find_intersection": "intersection", "segment_and_area": "area", "equal_area_point": "coordinate",
}


def _parabola_line_pts(a: object, m: object, b: object) -> list[str]:
    """放物線 y=ax² と直線 y=mx+b の交点・原点が収まる点の並び（描画範囲用）。

    交点は ax² = mx + b の解。図は**与えられた式のとおり**に描くので、
    本文と図が食い違わない。
    """
    xs = sympy.solve(
        sympy.Eq(sympy.sympify(a) * sympy.Symbol("x") ** 2,
                 sympy.sympify(m) * sympy.Symbol("x") + sympy.sympify(b)),
        sympy.Symbol("x"),
    )
    pts = [str((0, 0)), str((0, int(sympy.sympify(b))))]
    for x in xs:
        xi = int(x)
        pts.append(str((xi, int(sympy.sympify(a)) * xi * xi)))
    return pts


@register_recipe("math.intersection_parabola_line", provides_concepts=_INTERSECTION_CONCEPTS)
def intersection_parabola_line_recipe(ctx: CellContext, rng: Rng) -> MR:
    """放物線と直線の交点・線分長・面積・逆算を求める（g3_l37.find_value・answer-first）。"""
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]
    for _ in range(200):
        a = int(draw({"int_set": a_cands}, rng))
        xA, xB = (int(v) for v in draw_many({"int_set": x_cands, "distinct": ["value"]}, rng, k=2))
        m = a * (xA + xB)
        # AB = |xB - xA|・√(1 + m²) なので、m が大きいと根号の中が跳ね上がる
        # （5√442 が出ていた）。定義域は広いまま、答えの根号の中で測って引き直す。
        if mode != "segment_and_area" or 1 + m * m <= _MAX_SEGMENT_RADICAND:
            break
    else:
        raise ValueError("intersection_parabola_line_recipe: 根号の中が上限に収まる組を構成できず")

    b = -a * xA * xB
    assert b != 0  # xA≠xB・a≠0 より構成的に保証（O,A,B 同一直線上の退化を排除）

    solver = REGISTRY.solver("math.intersection_parabola_line")
    sol = cast(Solution, solver(a, m, b, mode))
    assert isinstance(sol.answer, SymbolicAnswer)

    expr_qf = _fmt_poly_x_terms([(a, 2)])
    expr_line = _fmt_poly_x_terms([(m, 1), (b, 0)])
    setup = f"放物線 y = {expr_qf} と直線 y = {expr_line} が2点 A, B で交わっている"
    question = _INTERSECTION_QUESTION_BY_MODE[mode]
    condition = f"{setup}。{question}"

    sub_question = SubQuestionMR(
        label="(1)", asked=_INTERSECTION_ASKED_BY_MODE[mode], answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "a": a, "m": m, "b": b, "mode": mode,
            # 図のための描画情報。交点の x 座標は本文の式から決まるので、
            # 放物線と直線の両方が収まる範囲を取れる。
            "curve_kind": "parabola", "coeff": str(a), "line": [str(m), str(b)],
            "pts": _parabola_line_pts(a, m, b),
            # 放物線と直線に式を添える（どちらがどの式か図から決まらなかった）。
            # 交点 A・B の座標はこのセルの答えなので**点名を付けない**が、
            # **原点 O は答えではない**ので打つ（本文が「原点を O とする」と
            # 名指ししていて、三角形 OAB の頂点になる）。
            "label_equations": True,
            "label_pts": [str((0, 0))],
            "label_names": ["O"],
        },
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params({
                "pts": _parabola_line_pts(a, m, b),
                "curve_kind": "parabola", "coeff": str(a), "line": [str(m), str(b)],
                "label_equations": True, "label_names": ["O"],
            }),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="curve", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.intersection_parabola_line"),
    )


# ---------------------------------------------------------------------------
# g3_l37.word_problem Lv3/Lv4: 放物線と直線が交わる図形の融合
#
# 構成は find_value と同じ answer-first（交点の x 座標 xA,xB と比例定数 a を先に決め、
# m=a(xA+xB), b=-a·xA·xB を逆算する）。違うのは**何を問うか**:
#   Lv3 = 誘導あり3小問（直線ABの式 → 三角形OABの面積 → 等積になる放物線上の点）
#   Lv4 = 誘導なし1小問（直線ABとx軸の交点をCとして、三角形OABと三角形OBCの面積比）
# ---------------------------------------------------------------------------
_WP_PARABOLA_GUIDED_CONCEPTS = ["quadratic_function.word_problem_parabola_line_guided"]
_WP_PARABOLA_RATIO_CONCEPTS = ["quadratic_function.word_problem_parabola_area_ratio"]


def _parabola_scene(p: Any, rng: Rng) -> tuple[int, int, int, int, int, str]:
    """(a, xA, xB, m, b, 放物線と2点を述べた場面文)。

    【組合せ数】a の候補 × xA,xB の相異な組。既定（a が 6 通り・x が 12 通りから2つ）で
    6 × 12 × 11 = 792 通り（≫250）。

    【退化の封じ方】a≠0・xA≠xB により b≠0 が構成的に保証される（O・A・B が同一直線上に
    ならない＝三角形 OAB がつぶれない）。さらに、等積の点 P の x 座標 m/a = xA+xB が
    0 や xA・xB と一致する組（P が原点や A・B と重なる）を外す。
    """
    # a = ±1 は表示が "y = x²" / "y = -x²" となり係数が本文に現れない。word_problem の
    # params 忠実性契約（numbers の値はすべて本文に現れる）を満たせないので外す。
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if abs(v) > 1]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]
    while True:
        a = int(draw({"int_set": a_cands}, rng))
        xA, xB = (int(v) for v in draw_many({"int_set": x_cands, "distinct": ["value"]}, rng, k=2))
        if xA > xB:
            xA, xB = xB, xA
        if xA + xB in (0, xA, xB):
            continue  # P が原点・A・B と重なる組は使わない
        break
    m, b = a * (xA + xB), -a * xA * xB
    expr_qf = _fmt_poly_x_terms([(a, 2)])
    scenario = (
        f"放物線 y = {expr_qf} 上に2点 A, B があり、A の x 座標は {xA}、"
        f"B の x 座標は {xB} である。原点を O とする。"
    )
    return a, xA, xB, m, b, scenario


@register_recipe(
    "math.word_problem_parabola_line_guided", provides_concepts=_WP_PARABOLA_GUIDED_CONCEPTS
)
def word_problem_parabola_line_guided_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導あり3小問の放物線×直線の融合（g3_l37.word_problem Lv3）。"""
    p = ctx.spec_level.params
    a, xA, xB, m, b, scenario = _parabola_scene(p, rng)
    yA, yB = a * xA**2, a * xB**2

    line_sol = cast(
        Solution,
        REGISTRY.solver("math.linear_expr_from_two_points")((xA, yA), (xB, yB), "slope_then_intercept"),
    )
    area_sol = cast(
        Solution, REGISTRY.solver("math.intersection_parabola_line")(a, m, b, "triangle_area")
    )
    point_sol = cast(Solution, REGISTRY.solver("math.parabola_equal_area_point")(a, m, b))
    for sol in (line_sol, area_sol, point_sol):
        assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 逆算した直線 y=mx+b が、2点から求めた直線の式と一致する。
    x = sympy.Symbol("x")
    assert (sympy.sympify(line_sol.answer.srepr) - (m * x + b)).equals(0), (
        f"直線の式が逆算した m,b と一致しない: {line_sol.answer.display}"
    )

    tags = dict(
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx)
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # 本文に出ている数だけ（傾き m・切片 b・面積・答えの点は導出値なので置かない）。
        params={"numbers": {"a": str(a), "x_a": str(xA), "x_b": str(xB)},
                **_parabola_points_params(a, xA, xB)},
        given={"scenario": scenario},
        context_slots={
            "ask_1": "直線 AB の式を求めよ。",
            "ask_2": "三角形 OAB の面積を求めよ。",
            "ask_3": (
                "この放物線上に、直線 AB について原点と同じ側に、原点と異なる点 P をとる。"
                "三角形 PAB の面積が三角形 OAB の面積と等しくなるとき、点 P の x 座標を求めよ。"
            ),
        },
        sub_questions=[
            SubQuestionMR(label="(1)", asked="formulation", answer=line_sol.answer, steps=line_sol.steps, **tags),
            SubQuestionMR(label="(2)", asked="value", answer=area_sol.answer, steps=area_sol.steps, **tags),
            SubQuestionMR(label="(3)", asked="value", answer=point_sol.answer, steps=point_sol.steps, **tags),
        ],
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params(_parabola_points_params(a, xA, xB)),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="curve", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.word_problem_parabola_line_guided"),
    )


@register_recipe(
    "math.word_problem_parabola_area_ratio", provides_concepts=_WP_PARABOLA_RATIO_CONCEPTS
)
def word_problem_parabola_area_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導なし・面積比を自分で構成する（g3_l37.word_problem Lv4）。"""
    p = ctx.spec_level.params
    while True:
        a, xA, xB, m, b, scenario = _parabola_scene(p, rng)
        if m == 0:
            continue  # 直線が x 軸と交わらない
        area_a = abs(a * (xA * xB) * (xB - xA)) / 2
        if area_a == 0:
            continue
        try:
            sol = cast(Solution, REGISTRY.solver("math.parabola_line_area_ratio")(a, m, b))
        except ValueError:
            continue  # 比が 1:1 に潰れる等の退化は引き直す
        break
    assert isinstance(sol.answer, SymbolicAnswer)
    ratio_p, ratio_q = sympy.sympify(sol.answer.srepr)
    assert ratio_p != ratio_q, "比が 1:1 に潰れている"

    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"numbers": {"a": str(a), "x_a": str(xA), "x_b": str(xB)},
                **_parabola_points_params(a, xA, xB)},
        given={"scenario": scenario},
        context_slots={
            "ask_value": (
                "直線 AB と x 軸との交点を C とするとき、三角形 OAB の面積と"
                "三角形 OBC の面積の比を、できるだけ簡単な整数の比で求めよ。"
            )
        },
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
        ],
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params(_parabola_points_params(a, xA, xB)),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="curve", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.word_problem_parabola_area_ratio"),
    )


# ---------------------------------------------------------------------------
# math.solve_quadratic_motion_area（g3_l38.find_value Lv2/Lv3）
# 正方形 ABCD（1辺 s）の周上を B から B→C→D の順に動く点 P。道のり d だけを扱う
# （Lv2 は「BP=d cm のとき」と道のりを直接与える。Lv3 は速さ v・時間 t を明示し d=v・t を提示）。
# ---------------------------------------------------------------------------
_QMOTION_CONCEPTS = ["quadratic_function.motion_area"]


@register_recipe("math.solve_quadratic_motion_area", provides_concepts=_QMOTION_CONCEPTS)
def solve_quadratic_motion_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正方形の周上を動く点 P による三角形 ABP の面積を求める（g3_l38.find_value）。"""
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])
    if mode == "single_segment":
        s = int(draw(p["s_domain"], rng))
        d = int(draw({"int_range": [1, s - 1]}, rng))
        condition = (
            f"1辺 {s}cm の正方形 ABCD の辺 BC 上を点 P が B から C に向かって動く。"
            f"BP={d}cm のときの三角形 ABP の面積を求めよ"
        )
        params: dict[str, object] = {"s": s, "d": d, "mode": mode}
    elif mode == "case_split":
        s = int(draw(p["s_domain"], rng))
        d = int(draw({"int_range": [1, 2 * s - 1]}, rng))
        # 速さ v(整数の約数)・時間 t=d/v を提示できるよう、d の約数から v を選ぶ。
        v_cands = [v for v in range(1, d + 1) if d % v == 0]
        v = int(draw({"int_set": v_cands}, rng))
        t = d // v
        condition = (
            f"1辺 {s}cm の正方形 ABCD の周上を、点 P が B を出発して B→C→D の順に毎秒 {v}cm で"
            f"動く。出発してから {t} 秒後の三角形 ABP の面積を求めよ"
        )
        params = {"s": s, "d": d, "mode": mode}
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.solve_quadratic_motion_area")
    sol = cast(Solution, solver(s, d, mode))
    assert isinstance(sol.answer, SymbolicAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="area", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.solve_quadratic_motion_area"),
    )


__all__ = [
    "evaluate_quadratic_function_recipe",
    "y_range_over_quadratic_domain_recipe",
    "rate_of_change_quadratic_recipe",
    "intersection_parabola_line_recipe",
    "word_problem_parabola_line_guided_recipe",
    "word_problem_parabola_area_ratio_recipe",
    "solve_quadratic_motion_area_recipe",
]


# ===========================================================================
# exam_l2（入試融合・放物線と直線の融合）— C13
#
# 5セルのうち3つ（find_value Lv3・graph_table Lv2・word_problem Lv3）は台帳 example の
# 内容が g3_l37 と実質同じなので、同じ recipe を family から共有する（同じ問題を
# 二重に書き起こして食い違いを作らない）。ここに足すのは残る2つ——
#   ・find_value Lv4: 交点の x 座標から係数 a を逆算し、面積まで進む
#   ・word_problem Lv4: 等積の点を誘導なしで構成する
# ===========================================================================
_EXAM_L2_COEFFICIENT_CONCEPTS = ["exam.parabola_coefficient_from_intersection"]
_EXAM_L2_EQUAL_AREA_CONCEPTS = ["exam.parabola_equal_area_point_solo"]


@register_recipe(
    "math.exam_parabola_coefficient_from_intersection",
    provides_concepts=_EXAM_L2_COEFFICIENT_CONCEPTS,
)
def exam_parabola_coefficient_from_intersection_recipe(ctx: CellContext, rng: Rng) -> MR:
    """交点の x 座標から放物線の係数を逆算し、三角形の面積まで求める（exam_l2.find_value Lv4）。

    answer-first: 先に答えの a と2つの交点 xA・xB を決め、直線 y=mx+b を
    m=a(xA+xB)、b=−a·xA·xB で逆算する（実行時の判定ではなく構成時に整数を保証する）。
    本文に出るのは直線の式と A の x 座標だけで、a と面積は出さない。
    """
    p = ctx.spec_level.params
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]
    cands: list[tuple[int, int, int]] = []
    for a in a_cands:
        for xa in x_cands:
            for xb in x_cands:
                a_i, xa_i, xb_i = int(a), int(xa), int(xb)
                if xa_i >= xb_i:
                    continue
                m, b = a_i * (xa_i + xb_i), -a_i * xa_i * xb_i
                if b == 0:
                    continue  # 直線が原点を通ると三角形 OAB がつぶれる
                area2 = abs(a_i * xa_i * xb_i * (xb_i - xa_i))  # 面積の2倍
                if area2 % 2:
                    continue  # 面積を整数にする
                area = area2 // 2
                # 答え（a・面積）が本文の数値（m・b・xA）と一致する組は外す（G-Q5t）。
                text_nums = {abs(m), abs(b), abs(xa_i)}
                if {abs(a_i), area} & text_nums:
                    continue
                cands.append((a_i, xa_i, xb_i))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    a, xa, xb = cands[idx]
    m, b = a * (xa + xb), -a * xa * xb
    (v,) = _draw_named_figures([2], rng)
    la, lb = v

    sol = cast(
        Solution, REGISTRY.solver("math.parabola_coefficient_from_intersection")(m, b, xa, la + lb)
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    a_val, area = sympy.sympify(sol.answer.srepr)
    assert a_val == sympy.Integer(a), f"逆算した a が構成と一致しない: {a_val} != {a}"
    assert area > 0

    line_txt = _fmt_line_mx_plus_b(m, b)
    condition = (
        f"放物線 y=ax² と直線 {line_txt} が2点{la}、{lb}で交わり、"
        f"{la}の x座標が{xa}である。このとき a の値を求め、"
        f"さらに三角形O{la}{lb}の面積を求めよ。ただしOは原点とする"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"m": m, "b": b, "x_a": xa, "labels": la + lb},
        given={"condition": condition},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
        ],
        visual_plan=None,
        provenance=Provenance(recipe="math.exam_parabola_coefficient_from_intersection"),
    )


def _fmt_line_mx_plus_b(m: int, b: int) -> str:
    """直線 y=mx+b を教科書表記で書く（係数 ±1 と 0 の扱いをそろえる）。"""
    if m == 0:
        return f"y={b}"
    term = "x" if m == 1 else ("-x" if m == -1 else f"{m}x")
    if b == 0:
        return f"y={term}"
    return f"y={term}{'+' if b > 0 else '-'}{abs(b)}"


@register_recipe(
    "math.exam_parabola_equal_area_solo", provides_concepts=_EXAM_L2_EQUAL_AREA_CONCEPTS
)
def exam_parabola_equal_area_solo_recipe(ctx: CellContext, rng: Rng) -> MR:
    """等積の点を誘導なしで構成する（exam_l2.word_problem Lv4）。

    g3_l37.word_problem Lv3 では同じ問いが3つめの小問（＝直線 AB の式と面積を
    先に出させたあと）だったが、ここは誘導なしなので「線分 AB を共通の底辺とみる」
    ところから自分で構成する。答えが一意に決まるよう、点を**直線 AB について原点と
    同じ側**に限る（反対側の平行線と放物線の交点は構成によって 0〜2 個と揺れるため、
    そこまで含めると「すべて求めよ」が安定した問いにならない）。
    """
    p = ctx.spec_level.params
    a, xA, xB, m, b, scenario = _parabola_scene(p, rng)
    sol = cast(Solution, REGISTRY.solver("math.parabola_equal_area_point")(a, m, b))
    assert isinstance(sol.answer, SymbolicAnswer)
    xP = sympy.sympify(sol.answer.srepr)
    assert xP not in (0, xA, xB), f"P が原点や A・B と重なる: {xP}"
    # 恒真: 求めた P で三角形 PAB の面積が三角形 OAB と等しい。
    yA, yB, yP = a * xA**2, a * xB**2, a * xP**2
    area_oab = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), (xA, yA), (xB, yB)])
    area_pab = _shoelace_area([(xP, yP), (xA, yA), (xB, yB)])
    assert (area_pab - area_oab).equals(0), f"面積が等しくならない: {area_pab} != {area_oab}"

    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"numbers": {"a": str(a), "x_a": str(xA), "x_b": str(xB)},
                **_parabola_points_params(a, xA, xB)},
        given={"scenario": scenario},
        context_slots={
            "ask_value": (
                "この放物線上に、直線 AB について原点と同じ側に、原点と異なる点 P を"
                "とりたい。三角形 OAB と三角形 PAB の面積が等しくなるとき、"
                "点 P の x 座標を求めよ。"
            )
        },
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=_effective_cause_tags(ctx),
            )
        ],
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params(_parabola_points_params(a, xA, xB)),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="curve", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.exam_parabola_equal_area_solo"),
    )
