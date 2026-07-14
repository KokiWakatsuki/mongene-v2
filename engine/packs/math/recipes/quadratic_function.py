"""関数 y=ax² まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C6（g3 二次関数 y=ax²）クラスタのうち、放物線の描画を必要としない5つの独立ソルバ
（`engine/packs/math/solvers/quadratic_function.py`）に対応する recipe を集約する。
乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, CellContext, Provenance, Solution, SubQuestionMR, SymbolicAnswer
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.recipes.polynomial import _domain_candidates, _fmt_poly_x_terms


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

_INTERSECTION_QUESTION_BY_MODE: dict[str, str] = {
    "find_intersection": "この交点 A, B の座標をすべて求めよ",
    "segment_and_area": (
        "線分 AB の長さと、原点 O と2点 A, B を結んでできる三角形 OAB の面積を求めよ"
    ),
    "bisecting_point": (
        "原点を O とするとき、y 軸上に点 P をとり、三角形 OAB の面積を"
        "三角形 PAB の面積が2等分するような点 P の座標を求めよ"
    ),
}

_INTERSECTION_ASKED_BY_MODE: dict[str, str] = {
    "find_intersection": "intersection", "segment_and_area": "area", "bisecting_point": "coordinate",
}


@register_recipe("math.intersection_parabola_line", provides_concepts=_INTERSECTION_CONCEPTS)
def intersection_parabola_line_recipe(ctx: CellContext, rng: Rng) -> MR:
    """放物線と直線の交点・線分長・面積・逆算を求める（g3_l37.find_value・answer-first）。"""
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])
    a_cands = [v for v in _domain_candidates(p["a_domain"]) if v != 0]
    x_cands = [v for v in _domain_candidates(p["x_domain"]) if v != 0]
    a = int(draw({"int_set": a_cands}, rng))
    xA, xB = (int(v) for v in draw_many({"int_set": x_cands, "distinct": ["value"]}, rng, k=2))

    m = a * (xA + xB)
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
        params={"a": a, "m": m, "b": b, "mode": mode},
        given={"condition": condition}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.intersection_parabola_line"),
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
    "solve_quadratic_motion_area_recipe",
]
