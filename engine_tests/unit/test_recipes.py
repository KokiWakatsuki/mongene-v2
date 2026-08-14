"""Task5b: 数学パック recipe（構成的生成・answer-first）の unit テスト。

各 recipe を実 FamilySpec YAML（engine/curriculum/math/families）から読んだ
CellContext で construct し、MR が正しく組み立てられること・signature が spec と
一致すること・double-solve（独立ソルバでの再確認）が全 seed で一致することを
検証する（H4/H5）。200 seed の property テストで例外なし・答え一致を確認する。
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

import pytest
import sympy

import engine.packs.math  # noqa: F401  (register_recipe/solver/template の副作用のため import)
from engine.core.contracts import CellContext, Coordinate, GenerateOptions
from engine.core.curriculum import load_curriculum
from engine.core.registry import REGISTRY
from engine.core.rng import derive_rng
from engine.core.spec.loader import load_family_dir
from engine.packs.math.visuals.graph import (
    compute_grid_spec_from_params,
    tick_labels_from_params,
)

FAMILIES_DIR = Path("engine/curriculum/math/families")


# ★spec / curriculum はテスト実行中は不変（property テストは読み取りのみ）。
# 以前は _make_ctx が毎回 58 family の YAML と curriculum を再パースしており（1回≈313ms）、
# property 1200 件で約 376 秒が再パースだけに費やされていた。lru_cache で 1 回に集約する。
@lru_cache(maxsize=1)
def _families():
    return load_family_dir(FAMILIES_DIR)


@lru_cache(maxsize=1)
def _curriculum():
    return load_curriculum()


def _make_ctx(family_name: str, level: int) -> CellContext:
    families = _families()
    spec_family = families[family_name]
    spec_level = spec_family.levels[str(level)]
    curriculum = _curriculum()
    unit = family_name.split(".")[1]
    form = spec_family.form
    return CellContext(
        subject="math",
        family=family_name,
        form=form,
        unit=unit,
        level=level,
        purpose="base",
        frame=REGISTRY.frame(form),
        spec_family=spec_family,
        spec_level=spec_level,
        curriculum_view=curriculum.curriculum_view(unit),
        requested=Coordinate(subject="math", unit=unit, form=form, level=level),
        options=GenerateOptions(),
    )


# ---------------------------------------------------------------------------
# math.linear_from_two_points（g2_l25.find_value Lv2/Lv3）
# ---------------------------------------------------------------------------
def test_linear_from_two_points_lv2_basic_construct():
    ctx = _make_ctx("math.g2_l25.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == ctx.spec_level.signature == "lf_expr_two_points_basic"
    assert mr.family == "math.g2_l25.find_value"
    assert set(mr.given.keys()) == {"point_a", "point_b"}
    assert len(mr.sub_questions) == 1
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    assert sq.concept_tags == ctx.spec_level.concept_tags
    assert sq.cause_tags == ["lf.confused_with_proportional", "lf.substitution_error"]
    # steps op 列: slope_then_intercept
    assert [s.op for s in sq.steps] == ["compute_slope", "compute_intercept", "form_expression"]


def test_linear_from_two_points_lv3_simultaneous_different_ops():
    ctx = _make_ctx("math.g2_l25.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "lf_expr_two_points_simultaneous"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["setup_simultaneous", "solve_simultaneous", "form_expression"]


@pytest.mark.parametrize("seed", range(200))
def test_linear_from_two_points_lv2_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l25.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    # 独立ソルバで再計算し、recipe が刻印した答えと一致することを確認する
    pts_strs = mr.params["pts"]
    p1 = sympy.sympify(pts_strs[0])
    p2 = sympy.sympify(pts_strs[1])
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]), mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


@pytest.mark.parametrize("seed", range(200))
def test_linear_from_two_points_lv3_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l25.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    pts_strs = mr.params["pts"]
    p1 = sympy.sympify(pts_strs[0])
    p2 = sympy.sympify(pts_strs[1])
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]), mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.linear_from_slope_point（g2_l24.find_value Lv1）
# ---------------------------------------------------------------------------
def test_linear_from_slope_point_lv1_construct():
    ctx = _make_ctx("math.g2_l24.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "lf_expr_slope_point_basic"
    assert set(mr.given.keys()) == {"slope", "point_a"}
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    # remedial G-Q7r の静的前提: Lv1 の concept_tags は intercept_from_point を含む
    assert "linear_function.intercept_from_point" in sq.concept_tags
    assert [s.op for s in sq.steps] == ["substitute_point", "compute_intercept", "form_expression"]


@pytest.mark.parametrize("seed", range(200))
def test_linear_from_slope_point_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l24.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    a = sympy.sympify(mr.params["a"])
    point = sympy.sympify(mr.params["point"])
    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol = solver(a, (point[0], point[1]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.linear_from_parallel_condition（g2_l24.find_value Lv3）
# ---------------------------------------------------------------------------
def test_linear_from_parallel_condition_lv3_construct():
    ctx = _make_ctx("math.g2_l24.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "lf_expr_parallel_condition"
    assert set(mr.given.keys()) == {"condition", "point_a"}
    assert mr.given["condition"].startswith("y = ")
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    assert [s.op for s in sq.steps] == ["read_parallel_slope", "compute_intercept", "form_expression"]


@pytest.mark.parametrize("seed", range(200))
def test_linear_from_parallel_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l24.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    a = sympy.sympify(mr.params["a"])
    point = sympy.sympify(mr.params["point"])
    solver = REGISTRY.solver("math.linear_expr_parallel_through_point")
    sol = solver(a, (point[0], point[1]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.graph_read_two_points（g2_l25.graph_table Lv2）
# ---------------------------------------------------------------------------
def test_graph_read_two_points_lv2_construct():
    ctx = _make_ctx("math.g2_l25.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "graph_read_two_lattice_points"
    # given は空: 直線は図で提示され、テキストに接地すべき given は無い（Task8 設計判断）
    assert mr.given == {}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_point"
    assert [s.op for s in sq.steps] == ["read_point", "read_point"]
    # visual_plan は非 None（frame.visual="required" を満たす）
    assert mr.visual_plan is not None
    assert mr.visual_plan.style == "grid"
    # labels は軸目盛の単独数値のみ（式や座標ペアそのものは載せない）
    for label in mr.visual_plan.labels:
        assert "," not in label  # 座標ペア表記なし
        assert "y" not in label  # 式（y = ...）なし
    # 答えの点マーカー（labeled_answer_point）を elements に含めない（幾何的リーク規則）
    assert all(el.kind != "labeled_answer_point" for el in mr.visual_plan.elements)


@pytest.mark.parametrize("seed", range(200))
def test_graph_read_two_points_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l25.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    pts_strs = mr.params["pts"]
    p1 = sympy.sympify(pts_strs[0])
    p2 = sympy.sympify(pts_strs[1])
    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.read_slope_intercept（g2_l21.graph_table Lv1）— 横展開#4（グラフから傾き・切片）
# ---------------------------------------------------------------------------
def test_read_slope_intercept_lv1_construct():
    ctx = _make_ctx("math.g2_l21.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "graph_read_slope_intercept"
    # given は空: 直線は図で提示され、テキストに接地すべき given は無い（式を出さない）
    assert mr.given == {}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_slope_intercept"
    assert sq.cause_tags == []  # cause_tags 空でも G-Q7 は通る
    assert [s.op for s in sq.steps] == ["read_slope", "read_intercept"]
    # visual_plan は非 None（frame.visual="required" を満たす）
    assert mr.visual_plan is not None
    assert mr.visual_plan.style == "grid"
    # labels は軸目盛の単独数値のみ（傾き・切片や式そのものは載せない）
    for label in mr.visual_plan.labels:
        assert "," not in label
        assert "y" not in label
        assert "傾き" not in label and "切片" not in label
    # 答えの点マーカー（labeled_answer_point）を elements に含めない（幾何的リーク規則）
    assert all(el.kind != "labeled_answer_point" for el in mr.visual_plan.elements)


@pytest.mark.parametrize("seed", range(200))
def test_read_slope_intercept_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l21.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    pts_strs = mr.params["pts"]
    p1 = sympy.sympify(pts_strs[0])
    p2 = sympy.sympify(pts_strs[1])
    solver = REGISTRY.solver("math.read_slope_intercept_from_graph")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答え (傾き, 切片) は構成した a, b と一致
    expected = sympy.Tuple(sympy.nsimplify(mr.params["a"]), sympy.nsimplify(mr.params["b"]))
    assert sol.answer.srepr == sympy.srepr(expected)


# ---------------------------------------------------------------------------
# math.solve_equation_for_y（g2_l26.calculation Lv1）— 横展開#5（ax+by=c→y=…）
# ---------------------------------------------------------------------------
def test_solve_equation_for_y_lv1_construct():
    ctx = _make_ctx("math.g2_l26.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "solve_two_var_equation_for_y"
    assert set(mr.given.keys()) == {"equation"}
    assert "=" in mr.given["equation"]  # ax+by=c の等式
    assert mr.visual_plan is None  # calculation は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert sq.cause_tags == []
    assert [s.op for s in sq.steps] == ["isolate_y_term", "divide_by_coefficient"]
    # 答えは y = mx + k の式（結果は整数係数の clean な式）
    assert sq.answer.display.startswith("y = ")


@pytest.mark.parametrize("seed", range(200))
def test_solve_equation_for_y_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l26.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    solver = REGISTRY.solver("math.solve_equation_for_y")
    sol = solver(
        sympy.sympify(mr.params["a"]),
        sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["c"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # y の係数 b は正・2 以上（非自明な除算）
    assert sympy.sympify(mr.params["b"]) >= 2


# ---------------------------------------------------------------------------
# math.evaluate_linear（g2_l19.calculation Lv1）— 横展開#6（y=ax+b に x を代入）
# ---------------------------------------------------------------------------
def test_evaluate_linear_lv1_construct():
    ctx = _make_ctx("math.g2_l19.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "evaluate_linear_at_x"
    assert set(mr.given.keys()) == {"expression", "input_value"}
    assert mr.given["expression"].startswith("y = ")
    assert mr.given["input_value"].startswith("x = ")
    assert mr.visual_plan is None  # calculation は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.cause_tags == []
    assert [s.op for s in sq.steps] == ["substitute_x", "evaluate"]


@pytest.mark.parametrize("seed", range(200))
def test_evaluate_linear_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l19.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    sol = solver(
        sympy.sympify(mr.params["a"]),
        sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["x0"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答え y = a*x0 + b と一致
    a = sympy.sympify(mr.params["a"]); b = sympy.sympify(mr.params["b"]); x0 = sympy.sympify(mr.params["x0"])
    assert sol.answer.srepr == sympy.srepr(sympy.nsimplify(a * x0 + b))


# ---------------------------------------------------------------------------
# math.point_on_line（g2_l22.calculation Lv1）— 横展開#7（通過点・evaluate 再利用）
# ---------------------------------------------------------------------------
def test_point_on_line_lv1_construct():
    ctx = _make_ctx("math.g2_l22.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "point_on_line_by_substitution"
    assert set(mr.given.keys()) == {"expression", "input_value"}
    assert mr.visual_plan is None  # calculation は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "coordinate"
    assert sq.cause_tags == []
    # evaluate_linear_at_x の substitute_x/evaluate を再利用し、末尾に座標組み立てを足す
    assert [s.op for s in sq.steps] == ["substitute_x", "evaluate", "form_coordinate"]
    assert sq.answer.display.startswith("(") and sq.answer.display.endswith(")")


@pytest.mark.parametrize("seed", range(200))
def test_point_on_line_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l22.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.point_on_line_at_x")
    sol = solver(
        sympy.sympify(mr.params["a"]),
        sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["x0"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 通過点 (x0, a*x0 + b) と一致
    a = sympy.sympify(mr.params["a"]); b = sympy.sympify(mr.params["b"]); x0 = sympy.sympify(mr.params["x0"])
    assert sol.answer.srepr == sympy.srepr(sympy.Tuple(sympy.nsimplify(x0), sympy.nsimplify(a * x0 + b)))


# ---------------------------------------------------------------------------
# math.draw_linear（g2_l22.graph_table Lv1）— 横展開#8・「かく」capability
# ---------------------------------------------------------------------------
def test_draw_linear_lv1_construct():
    ctx = _make_ctx("math.g2_l22.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_linear_from_slope_intercept"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert sq.answer.kind == "graph"  # 答えは GraphAnswer
    assert {f.kind for f in sq.answer.features} == {"slope", "intercept"}
    assert sq.answer.solution_svg_ref != ""  # 模範解答図（直線つき）を持つ
    assert 'stroke-width="2.5"' in sq.answer.solution_svg_ref  # 解答図には直線がある
    assert [s.op for s in sq.steps] == ["plot_intercept", "apply_slope", "draw_line"]
    # 問題図は空の方眼: visual_plan.elements に line を宣言しない
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_linear_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l22.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_linear_features")
    sol = solver(sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]))
    # 特徴点の srepr 集合が一致（GraphAnswer の double-solve＝§6.2 V1'）
    assert {f.srepr for f in sol.answer.features} == {f.srepr for f in mr.sub_questions[0].answer.features}
    # 期待特徴（傾き a・y切片の点 (0,b)）と一致
    a = sympy.nsimplify(mr.params["a"]); b = sympy.nsimplify(mr.params["b"])
    assert {f.srepr for f in sol.answer.features} == {sympy.srepr(a), sympy.srepr(sympy.Tuple(sympy.Integer(0), b))}


# ---------------------------------------------------------------------------
# math.draw_linear_from_equation（g2_l26.graph_table Lv1）— 横展開#9（変形してかく・合成）
# ---------------------------------------------------------------------------
def test_draw_from_equation_lv1_construct():
    ctx = _make_ctx("math.g2_l26.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_from_two_var_equation"
    assert set(mr.given.keys()) == {"equation"}
    assert "=" in mr.given["equation"]
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert sq.answer.kind == "graph"
    assert {f.kind for f in sq.answer.features} == {"slope", "intercept"}
    assert sq.answer.solution_svg_ref != ""
    # #5(変形)＋#8(作図)のコア合成: 手順が変形2手＋作図3手
    assert [s.op for s in sq.steps] == [
        "isolate_y_term", "divide_by_coefficient", "plot_intercept", "apply_slope", "draw_line",
    ]
    # 問題図は空の方眼
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_from_equation_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l26.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_from_equation")
    sol = solver(
        sympy.sympify(mr.params["eq_a"]),
        sympy.sympify(mr.params["eq_b"]),
        sympy.sympify(mr.params["eq_c"]),
    )
    assert {f.srepr for f in sol.answer.features} == {f.srepr for f in mr.sub_questions[0].answer.features}
    # 変形後の直線 y=mx+k（m=-A/B, k=C/B）の特徴と一致
    A = sympy.nsimplify(mr.params["eq_a"]); B = sympy.nsimplify(mr.params["eq_b"]); C = sympy.nsimplify(mr.params["eq_c"])
    m = -A / B; k = C / B
    assert {f.srepr for f in sol.answer.features} == {sympy.srepr(m), sympy.srepr(sympy.Tuple(sympy.Integer(0), k))}


# ---------------------------------------------------------------------------
# math.read_intersection_from_graph（g2_l27.graph_table Lv2）— 横展開#10（交点をグラフから読む）
# ---------------------------------------------------------------------------
def test_read_intersection_from_graph_lv2_construct():
    ctx = _make_ctx("math.g2_l27.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "read_intersection_two_lines_graph"
    assert set(mr.given.keys()) == {"line_a", "line_b"}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_intersection"
    assert sq.answer.kind == "symbolic"  # 交点座標（点）
    assert [s.op for s in sq.steps] == ["draw_line_1", "draw_line_2", "read_intersection"]
    # 問題図は空の方眼（生徒が2直線をかく）
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_read_intersection_from_graph_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l27.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.read_diagram_intersection（g2_l30.graph_table Lv2）— P1/C5（ダイヤ交点読み）
# ---------------------------------------------------------------------------
def test_read_diagram_intersection_lv2_construct():
    ctx = _make_ctx("math.g2_l30.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "read_diagram_intersection_graph"
    assert set(mr.given.keys()) == {"line_a", "line_b"}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_intersection"
    assert sq.answer.kind == "symbolic"  # 交点座標（点）
    assert [s.op for s in sq.steps] == ["draw_line_a", "draw_line_b", "read_intersection"]
    # 交点は第1象限の格子点（時間・道のり>0）
    x0, y0 = sympy.sympify(mr.params["pts"][0])
    assert x0 > 0 and y0 > 0
    assert mr.params["scenario"] in {"meet", "catchup"}
    # 問題図は空の方眼（生徒が2直線をかく）
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_read_diagram_intersection_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l30.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 交点は第1象限（時間・道のり>0）
    x0, y0 = sympy.sympify(mr.params["pts"][0])
    assert x0 > 0 and y0 > 0


# ---------------------------------------------------------------------------
# math.draw_special_lines（g2_l26.graph_table Lv2）— P1/C5（切片法＋特殊直線 x=k/y=k）
# ---------------------------------------------------------------------------
def test_draw_special_lines_lv2_construct():
    ctx = _make_ctx("math.g2_l26.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_intercept_method_with_special_line"
    assert set(mr.given.keys()) == {"equation", "equation2"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert sq.answer.kind == "graph"
    # 単一小問に3特徴（2交点＋特殊直線）を集約
    assert len(sq.answer.features) == 3
    assert [s.op for s in sq.steps] == [
        "find_x_intercept", "find_y_intercept", "draw_line", "draw_special_line",
    ]
    assert mr.params["axis"] in {"vertical", "horizontal"}
    # 問題図は空の方眼（生徒が描き込む）
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_special_lines_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l26.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_special_lines")
    sol = solver(
        sympy.sympify(mr.params["xi"]), sympy.sympify(mr.params["yi"]),
        mr.params["axis"], sympy.sympify(mr.params["k"]),
    )
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver


# ---------------------------------------------------------------------------
# math.draw_from_table（g2_l28.graph_table Lv2）— P1/C5（対応表からグラフをかく）
# ---------------------------------------------------------------------------
def test_draw_from_table_lv2_construct():
    ctx = _make_ctx("math.g2_l28.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_line_from_correspondence_table"
    assert set(mr.given.keys()) == {"data_table"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert sq.answer.kind == "graph"
    assert [s.op for s in sq.steps] == ["read_table_points", "plot_points", "draw_line"]
    # 表は x=0 を含む4点（切片が表に現れる）
    assert "| x | 0 |" in mr.given["data_table"]
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_from_table_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l28.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_linear_features")
    sol = solver(sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]))
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver


# ---------------------------------------------------------------------------
# math.draw_linear_fraction（g2_l22.graph_table Lv3）— P1/C5（分数傾き・格子点）
# ---------------------------------------------------------------------------
def test_draw_linear_fraction_lv3_construct():
    ctx = _make_ctx("math.g2_l22.graph_table", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_linear_fraction_slope"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert sq.answer.kind == "graph"
    assert len(sq.answer.features) == 3  # 傾き・切片・格子点
    assert [s.op for s in sq.steps] == [
        "plot_intercept", "apply_slope_denominator", "apply_slope_numerator",
        "mark_lattice_point", "draw_line",
    ]
    # 傾きは非整数（分母 q≥2）
    q = int(mr.params["q"])
    assert q >= 2
    slope = sympy.sympify(mr.params["a"])
    assert not slope.is_integer
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_linear_fraction_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l22.graph_table", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_linear_features_fraction")
    sol = solver(
        sympy.sympify(mr.params["p"]), sympy.sympify(mr.params["q"]),
        sympy.sympify(mr.params["b"]),
    )
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver


# ---------------------------------------------------------------------------
# math.draw_segment（g2_l23.graph_table Lv2）— P1/C5（端点開閉の線分）
# ---------------------------------------------------------------------------
def test_draw_segment_lv2_construct():
    ctx = _make_ctx("math.g2_l23.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "draw_segment_with_endpoints"
    assert set(mr.given.keys()) == {"expression", "x_domain"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_segment"
    assert sq.answer.kind == "graph"
    assert len(sq.answer.features) == 2  # 両端点
    assert {f.kind for f in sq.answer.features} <= {"endpoint_closed", "endpoint_open"}
    assert [s.op for s in sq.steps] == ["plot_endpoint_lo", "plot_endpoint_hi", "draw_segment"]
    assert sympy.sympify(mr.params["seg_x_lo"]) < sympy.sympify(mr.params["seg_x_hi"])
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(200))
def test_draw_segment_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l23.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.draw_segment_features")
    sol = solver(
        sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["seg_x_lo"]), sympy.sympify(mr.params["seg_x_hi"]),
        bool(mr.params["closed_lo"]), bool(mr.params["closed_hi"]),
    )
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver


# ---------------------------------------------------------------------------
# math.evaluate_linear_fraction（g2_l28.calculation Lv1）— P1/C5（分数係数の代入）
# ---------------------------------------------------------------------------
def test_evaluate_linear_fraction_lv1_construct():
    ctx = _make_ctx("math.g2_l28.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "evaluate_linear_fraction_at_x"
    assert set(mr.given.keys()) == {"expression", "input_value"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.kind == "symbolic"
    # 傾きは非整数（分数係数）だが、x0=分母の倍数なので答え y は整数
    assert not sympy.sympify(mr.params["a"]).is_integer
    assert sympy.sympify(sq.answer.srepr).is_integer
    assert mr.visual_plan is None  # calculation は図なし


@pytest.mark.parametrize("seed", range(200))
def test_evaluate_linear_fraction_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l28.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.evaluate_linear_at_x")
    sol = solver(
        sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["x0"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.knowledge_classify_line_signs（g2_l21.knowledge Lv2）— P1/C5（傾き/切片の符号判別）
# ---------------------------------------------------------------------------
def test_knowledge_classify_line_signs_lv2_construct():
    ctx = _make_ctx("math.g2_l21.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_classify_line_signs"
    assert set(mr.given.keys()) == {"statement"}
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert len(sq.answer.distractors) == 3  # 4分類のうち残り3つが妨害
    assert [s.op for s in sq.steps] == [
        "identify_slope_sign", "identify_intercept_sign", "combine_signs",
    ]
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_classify_line_signs_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l21.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.classify_line_by_signs")
    sol = solver(sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]))
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


# ---------------------------------------------------------------------------
# g2_l30.find_value Lv2 — P1/C5（ダイヤ交点を連立で求める・math.intersection 再利用）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(100))
def test_intersection_diagram_lv2_positive_quadrant(seed):
    ctx = _make_ctx("math.g2_l30.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "lf_intersection_diagram_substitute"
    assert set(mr.given.keys()) == {"line_a", "line_b"}
    sq = mr.sub_questions[0]
    assert sq.asked == "intersection"
    # 交点は第1象限（時刻・道のり>0）
    x0, y0 = sympy.sympify(sq.answer.srepr)
    assert x0 > 0 and y0 > 0
    # double-solve（intersection_of_two_lines 再利用）
    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    assert solver(line_a, line_b, mr.params["method"]).answer.srepr == sq.answer.srepr


# ---------------------------------------------------------------------------
# math.solve_time_from_area（g2_l29.find_value Lv3）— P1/C5（面積の式から時刻を逆算）
# ---------------------------------------------------------------------------
def test_solve_time_from_area_lv3_construct():
    ctx = _make_ctx("math.g2_l29.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_time_from_area"
    assert set(mr.given.keys()) == {"expression", "x_domain", "condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.kind == "symbolic"
    assert [s.op for s in sq.steps] == ["set_up_equation", "solve_for_x"]
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(200))
def test_solve_time_from_area_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l29.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.solve_time_from_area")
    sol = solver(sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["y_target"]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えの時刻は区間 0≦x≦x_max 内
    x_ans = sympy.sympify(sol.answer.srepr)
    assert 0 < x_ans <= sympy.sympify(mr.params["x_max"])


# ---------------------------------------------------------------------------
# math.solve_system_elimination_add（g2_l16.calculation Lv1）— P1/C2（足して消去）
# ---------------------------------------------------------------------------
def test_solve_system_elimination_add_lv1_construct():
    ctx = _make_ctx("math.g2_l16.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_elimination_add"
    assert set(mr.given.keys()) == {"equation_a", "equation_b"}
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert [s.op for s in sq.steps] == [
        "identify_opposite_coeff", "add_and_solve_x", "back_substitute",
    ]
    # y 係数が絶対値等しく符号逆（line_a[1] = -line_b[1]）
    assert sympy.sympify(mr.params["line_a"][1]) == -sympy.sympify(mr.params["line_b"][1])
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(200))
def test_solve_system_elimination_add_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l16.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_system_elimination（g2_l11.calculation Lv1）— 横展開#11（連立・加減法）
# ---------------------------------------------------------------------------
def test_solve_system_elimination_lv1_construct():
    ctx = _make_ctx("math.g2_l11.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_elimination_equal_coeff"
    assert set(mr.given.keys()) == {"equation_a", "equation_b"}
    assert mr.visual_plan is None  # calculation は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert sq.answer.kind == "symbolic"  # 解 (x,y)
    assert sq.answer.display.startswith("(")
    assert [s.op for s in sq.steps] == ["identify_equal_coeff", "eliminate_and_solve_x", "back_substitute"]
    # y の係数が両式で等しい（加減法で辺々引ける＝係数の絶対値が等しい）
    assert sympy.sympify(mr.params["line_a"][1]) == sympy.sympify(mr.params["line_b"][1])


@pytest.mark.parametrize("seed", range(200))
def test_solve_system_elimination_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l11.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_system_substitution（g2_l13.calculation Lv1/Lv2）— 横展開#12（連立・代入法）
# ---------------------------------------------------------------------------
def test_solve_system_substitution_lv1_construct():
    ctx = _make_ctx("math.g2_l13.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_substitution_direct"
    assert set(mr.given.keys()) == {"equation_a", "equation_b"}
    assert mr.visual_plan is None  # calculation は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert sq.answer.kind == "symbolic"  # 解 (x,y)
    assert sq.answer.display.startswith("(")
    # Lv1「そのまま代入」= 3 手（前処理なし）
    assert [s.op for s in sq.steps] == ["substitute_expr", "solve_for_x", "back_substitute"]
    # eq_a は解けた形 y = … で与えられる
    assert mr.given["equation_a"].startswith("y =")


def test_solve_system_substitution_lv2_construct():
    ctx = _make_ctx("math.g2_l13.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_substitution_transform"
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    # Lv2「変形して代入」= 前処理 isolate_variable を足した 4 手（Lv1 と op 列が相異＝level_sep）
    assert [s.op for s in sq.steps] == [
        "isolate_variable",
        "substitute_expr",
        "solve_for_y",
        "back_substitute",
    ]
    # eq_a は x の係数 1（変形して代入する対象）
    assert sympy.sympify(mr.params["line_a"][0]) == 1


@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("seed", range(200))
def test_solve_system_substitution_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l13.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_system_elim_scaled（g2_l12.calculation Lv2/Lv3）— 横展開#13（加減法・係数そろえ）
# ---------------------------------------------------------------------------
def test_solve_system_elim_scaled_lv2_construct():
    ctx = _make_ctx("math.g2_l12.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_elim_scale_one"
    assert set(mr.given.keys()) == {"equation_a", "equation_b"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert sq.answer.kind == "symbolic"
    # Lv2「片方を倍す」= 先頭 op が scale_one_equation
    assert [s.op for s in sq.steps] == ["scale_one_equation", "eliminate_and_solve_x", "back_substitute"]
    a1, b1 = sympy.sympify(mr.params["line_a"][0]), sympy.sympify(mr.params["line_a"][1])
    a2, b2 = sympy.sympify(mr.params["line_b"][0]), sympy.sympify(mr.params["line_b"][1])
    # eq_a の y 係数は 1（片方を倍して y をそろえる易しい変数）
    assert b1 == 1
    # x 係数は互いに素・大きさ≥2（偶然そろって倍不要＝l11 相当への退化を禁止）
    assert abs(a1) != abs(a2)
    assert abs(a1) >= 2 and abs(a2) >= 2
    assert math.gcd(int(abs(a1)), int(abs(a2))) == 1


def test_solve_system_elim_scaled_lv3_construct():
    ctx = _make_ctx("math.g2_l12.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_elim_scale_both"
    sq = mr.sub_questions[0]
    # Lv3「両式を倍す」= 先頭 op が scale_both_equations（Lv2 と op 列相異＝level_sep）
    assert [s.op for s in sq.steps] == ["scale_both_equations", "eliminate_and_solve_x", "back_substitute"]
    a1, b1 = sympy.sympify(mr.params["line_a"][0]), sympy.sympify(mr.params["line_a"][1])
    a2, b2 = sympy.sympify(mr.params["line_b"][0]), sympy.sympify(mr.params["line_b"][1])
    # x 係数も y 係数も互いに素・大きさ≥2＝どちらの変数も両式を倍す必要がある（真の Lv3）
    for u, v in ((a1, a2), (b1, b2)):
        assert abs(u) >= 2 and abs(v) >= 2
        assert math.gcd(int(abs(u)), int(abs(v))) == 1


@pytest.mark.parametrize("level", [2, 3])
@pytest.mark.parametrize("seed", range(200))
def test_solve_system_elim_scaled_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l12.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_system_preprocessed（g2_l14.calculation Lv2/Lv3）— 横展開#14（前処理を伴う連立）
# ---------------------------------------------------------------------------
def test_solve_system_preprocessed_lv2_construct():
    ctx = _make_ctx("math.g2_l14.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_expand_parens"
    assert set(mr.given.keys()) == {"equation_a", "equation_b"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert sq.answer.kind == "symbolic"
    # Lv2「かっこ展開」= 先頭 op が expand_parentheses
    assert [s.op for s in sq.steps] == ["expand_parentheses", "eliminate_and_solve_x", "back_substitute"]
    # 提示式はかっこを含む（未整理の見かけ）
    assert "(" in mr.given["equation_a"] or "(" in mr.given["equation_b"]


def test_solve_system_preprocessed_lv3_construct():
    ctx = _make_ctx("math.g2_l14.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_clear_fractions"
    sq = mr.sub_questions[0]
    # Lv3「分数払い」= 先頭 op が clear_denominators（Lv2 と op 列相異＝level_sep）
    assert [s.op for s in sq.steps] == ["clear_denominators", "eliminate_and_solve_x", "back_substitute"]
    # 提示式は分数（/）を含む（未整理の見かけ）
    assert "/" in mr.given["equation_a"] or "/" in mr.given["equation_b"]


@pytest.mark.parametrize("level", [2, 3])
@pytest.mark.parametrize("seed", range(200))
def test_solve_system_preprocessed_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l14.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_system_abc（g2_l15.calculation Lv2）— 横展開#15（A=B=C 形・単一レベル）
# ---------------------------------------------------------------------------
def test_solve_system_abc_construct():
    ctx = _make_ctx("math.g2_l15.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "solve_system_abc_form"
    assert set(mr.given.keys()) == {"equation"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert sq.answer.kind == "symbolic"
    assert sq.answer.display.startswith("(")
    assert [s.op for s in sq.steps] == ["split_abc_equation", "eliminate_and_solve_x", "back_substitute"]
    # A=B=C の見かけ（"=" が2つ）で提示される
    assert mr.given["equation"].count("=") == 2


@pytest.mark.parametrize("seed", range(200))
def test_solve_system_abc_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l15.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver(line_a, line_b, mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.knowledge_slope_direction（g2_l21.knowledge Lv1）— 横展開#16（knowledge form 初セル）
# ---------------------------------------------------------------------------
def test_knowledge_slope_direction_construct():
    ctx = _make_ctx("math.g2_l21.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_slope_direction"
    assert set(mr.given.keys()) == {"statement"}
    assert mr.visual_plan is None  # knowledge は図なし
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"  # 初の ChoiceAnswer 生成経路
    assert sq.answer.correct in {"右上がり", "右下がり"}
    assert sq.answer.distractors and sq.answer.correct not in sq.answer.distractors
    assert sq.answer.fact_id == "lf.slope_sign_to_direction"
    assert [s.op for s in sq.steps] == ["identify_slope_sign", "determine_direction"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_slope_direction_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l21.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 問題パラメータの傾き a だけから向きを再判定（切片 b は無関係）→ recipe の答えと一致
    a = sympy.sympify(mr.params["a"])
    solver = REGISTRY.solver("math.linear_direction_from_slope")
    sol = solver(a)
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id
    # 傾きの符号と向きの対応が正しい（規則の健全性）
    assert sol.answer.correct == ("右上がり" if a > 0 else "右下がり")


# ---------------------------------------------------------------------------
# math.knowledge_range_endpoint（g2_l23.knowledge Lv1）— 横展開#17（knowledge 償却の実証）
# ---------------------------------------------------------------------------
def test_knowledge_range_endpoint_construct():
    ctx = _make_ctx("math.g2_l23.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_range_endpoint"
    assert set(mr.given.keys()) == {"statement"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert sq.answer.correct in {"ふくまれる", "ふくまれない"}
    assert sq.answer.fact_id == "range.endpoint_inclusion"
    assert [s.op for s in sq.steps] == ["identify_inequality_type", "determine_inclusion"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_range_endpoint_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l23.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 包含は inclusive（不等号の等号の有無）だけから再判定（端点値・関数は無関係）
    solver = REGISTRY.solver("math.range_endpoint_inclusion")
    sol = solver(bool(mr.params["inclusive"]))
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.correct == ("ふくまれる" if mr.params["inclusive"] else "ふくまれない")


# ---------------------------------------------------------------------------
# math.knowledge_verify_solution（g2_l10.knowledge Lv2）— 横展開#18（連立の解の判定）
# ---------------------------------------------------------------------------
def test_knowledge_verify_solution_construct():
    ctx = _make_ctx("math.g2_l10.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_verify_solution"
    assert set(mr.given.keys()) == {"statement", "term_context"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert sq.answer.correct in {"解である", "解でない"}
    assert sq.answer.fact_id == "simultaneous.solution_verification"
    assert [s.op for s in sq.steps] == ["substitute_candidate", "judge_solution"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_verify_solution_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l10.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 候補と係数だけから代入判定（真偽ビットは見ない）→ recipe の答えと一致
    line_a = tuple(sympy.sympify(c) for c in mr.params["line_a"])
    line_b = tuple(sympy.sympify(c) for c in mr.params["line_b"])
    cand = sympy.sympify(mr.params["candidate"])
    solver = REGISTRY.solver("math.verify_system_solution")
    sol = solver(line_a, line_b, (cand[0], cand[1]))
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 代入検証の健全性: 「解である」⇔ 両式が成り立つ
    both_hold = all(
        sympy.simplify(line[0] * cand[0] + line[1] * cand[1] - line[2]) == 0
        for line in (line_a, line_b)
    )
    assert (sol.answer.correct == "解である") == both_hold


# ---------------------------------------------------------------------------
# math.knowledge_classify_linear（g2_l19.knowledge Lv2）— 横展開#19（与式が1次関数か判別・verify型）
# ---------------------------------------------------------------------------
def test_knowledge_classify_linear_construct():
    ctx = _make_ctx("math.g2_l19.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_classify_linear"
    assert set(mr.given.keys()) == {"statement"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert sq.answer.correct in {"1次関数である", "1次関数ではない"}
    assert sq.answer.fact_id == "lf.classify_linear_function"
    assert [s.op for s in sq.steps] == ["inspect_rate_of_change", "judge_linear"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_classify_linear_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l19.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 式 rhs だけから微分判定（category ビットは見ない）→ recipe の答えと一致
    rhs = sympy.sympify(mr.params["rhs"])
    solver = REGISTRY.solver("math.classify_linear_function")
    sol = solver(rhs)
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 判定の健全性: 「1次関数である」⇔ 導関数が x を含まない非ゼロ定数
    x = sympy.symbols("x")
    deriv = sympy.diff(rhs, x)
    is_linear = (not deriv.is_zero) and (x not in deriv.free_symbols)
    assert (sol.answer.correct == "1次関数である") == is_linear
    # category ビットと答えの整合（0=1次のみ「である」）
    assert (mr.params["category"] == 0) == is_linear


# ---------------------------------------------------------------------------
# math.knowledge_rate_constant（g2_l20.knowledge Lv1）— 横展開#22（P1・C5・答え固定型）
# ---------------------------------------------------------------------------
_RATE_CONSTANT_CORRECT = "変化の割合はつねに一定で、傾きに等しい"


def test_knowledge_rate_constant_construct():
    ctx = _make_ctx("math.g2_l20.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_rate_constant"
    assert set(mr.given.keys()) == {"statement"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert sq.answer.correct == _RATE_CONSTANT_CORRECT
    assert sq.answer.fact_id == "lf.rate_of_change_is_constant"
    assert [s.op for s in sq.steps] == ["recall_property", "select_correct"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_rate_constant_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l20.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 答え固定型: solver は引数なしで常に同じ正しい説明を返す
    solver = REGISTRY.solver("math.rate_of_change_is_constant")
    sol = solver()
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct == _RATE_CONSTANT_CORRECT
    # distractors は誤った説明（correct を含まない）
    assert _RATE_CONSTANT_CORRECT not in sol.answer.distractors


# ---------------------------------------------------------------------------
# math.knowledge_equation_solution_set（g2_l26.knowledge Lv1）— 横展開#23（P1・C5・答え固定）
# ---------------------------------------------------------------------------
def test_knowledge_equation_solution_set_construct():
    ctx = _make_ctx("math.g2_l26.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_equation_solution_set"
    assert set(mr.given.keys()) == {"statement"}
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.correct == "直線"
    assert sq.answer.fact_id == "lf.equation_solution_set_is_line"
    assert [s.op for s in sq.steps] == ["recall_property", "select_correct"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_equation_solution_set_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l26.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.equation_solution_set_shape")()
    assert sol.answer.correct == mr.sub_questions[0].answer.correct == "直線"


# ---------------------------------------------------------------------------
# math.knowledge_system_intersection（g2_l27.knowledge Lv1）— 横展開#24（P1・C5・答え固定）
# ---------------------------------------------------------------------------
def test_knowledge_system_intersection_construct():
    ctx = _make_ctx("math.g2_l27.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_system_intersection"
    assert set(mr.given.keys()) == {"statement"}
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.correct == "2つの直線の交点"
    assert sq.answer.fact_id == "lf.system_solution_is_intersection"
    assert [s.op for s in sq.steps] == ["recall_property", "select_correct"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_system_intersection_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l27.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.system_solution_is_intersection")()
    assert sol.answer.correct == mr.sub_questions[0].answer.correct == "2つの直線の交点"


# ---------------------------------------------------------------------------
# math.knowledge_coefficient_role（g2_l19.knowledge Lv1）— 横展開#21（P1・C5・用語想起）
# ---------------------------------------------------------------------------
def test_knowledge_coefficient_role_construct():
    ctx = _make_ctx("math.g2_l19.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "knowledge_coefficient_role"
    assert set(mr.given.keys()) == {"statement", "term_context"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert sq.answer.correct in {"傾き", "切片"}
    assert sq.answer.fact_id == "lf.coefficient_role"
    assert [s.op for s in sq.steps] == ["locate_part", "recall_term"]


@pytest.mark.parametrize("seed", range(200))
def test_knowledge_coefficient_role_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l19.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    which = mr.params["which"]
    solver = REGISTRY.solver("math.linear_coefficient_role")
    sol = solver(which)
    assert sol.answer.kind == "choice"
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # which（係数/定数項）で答えが変わる: slope→傾き / intercept→切片
    assert (which == "slope") == (sol.answer.correct == "傾き")
    assert (which == "intercept") == (sol.answer.correct == "切片")


# ---------------------------------------------------------------------------
# math.linear_slope_as_rate（g2_l21.calculation Lv1）— 横展開#20（P1・C5）
# ---------------------------------------------------------------------------
def test_linear_slope_as_rate_construct():
    ctx = _make_ctx("math.g2_l21.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "linear_slope_as_rate"
    assert set(mr.given.keys()) == {"expression"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.kind == "symbolic"
    assert [s.op for s in sq.steps] == ["compute_increment", "state_rate_of_change"]


@pytest.mark.parametrize("seed", range(200))
def test_linear_slope_as_rate_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l21.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    # 傾き a だけから変化の割合を再計算（切片 b は無関係）→ recipe の答えと一致
    a = sympy.sympify(mr.params["a"])
    solver = REGISTRY.solver("math.linear_slope_as_rate")
    sol = solver(a)
    assert sol.answer.kind == "symbolic"
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答え＝傾き a（x が1増えたときの y の増加量）
    assert sol.answer.srepr == sympy.srepr(a)
    # ±1・0 は除外されている（G-Q5t 衝突回避）
    assert a not in (0, 1, -1)


# ---------------------------------------------------------------------------
# math.rate_of_change（g2_l20.find_value Lv1）— 横展開の第1セル
# ---------------------------------------------------------------------------
def test_rate_of_change_lv1_construct():
    ctx = _make_ctx("math.g2_l20.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    assert mr.signature == "lf_rate_of_change_two_points"
    assert set(mr.given.keys()) == {"point_a", "point_b"}
    sq = mr.sub_questions[0]
    assert sq.asked == "rate_of_change"
    assert sq.cause_tags == []  # cause_tags 空でも G-Q7 は通る（concept_tags のみ非空必須）
    assert [s.op for s in sq.steps] == ["compute_differences", "compute_rate_of_change"]


@pytest.mark.parametrize("seed", range(200))
def test_rate_of_change_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l20.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    recipe = REGISTRY.recipe(ctx.spec_level.recipe)
    mr = recipe(ctx, rng)

    pts_strs = mr.params["pts"]
    p1 = sympy.sympify(pts_strs[0])
    p2 = sympy.sympify(pts_strs[1])
    solver = REGISTRY.solver("math.rate_of_change_from_two_points")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 変化の割合 = 傾き a と一致
    assert sol.answer.srepr == sympy.srepr(sympy.nsimplify(mr.params["a"]))


# ---------------------------------------------------------------------------
# math.intersection（g2_l27.find_value Lv2/Lv3）— 横展開の第2セル（2直線の交点）
# ---------------------------------------------------------------------------
def test_intersection_lv2_substitute_construct():
    ctx = _make_ctx("math.g2_l27.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "lf_intersection_substitute"
    assert set(mr.given.keys()) == {"line_a", "line_b"}
    assert mr.given["line_a"].startswith("y = ")  # Lv2 は傾き切片形
    sq = mr.sub_questions[0]
    assert sq.asked == "intersection"
    assert [s.op for s in sq.steps] == ["equate_expressions", "solve_for_x", "compute_y"]


def test_intersection_lv3_elimination_different_ops():
    ctx = _make_ctx("math.g2_l27.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "lf_intersection_elimination"
    assert "=" in mr.given["line_a"] and not mr.given["line_a"].startswith("y = ")  # 一般形
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["setup_system", "eliminate_variable", "back_substitute"]


@pytest.mark.parametrize("level", [2, 3])
@pytest.mark.parametrize("seed", range(100))
def test_intersection_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l27.find_value", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    A1, B1, C1 = (sympy.sympify(c) for c in mr.params["line_a"])
    A2, B2, C2 = (sympy.sympify(c) for c in mr.params["line_b"])
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = solver((A1, B1, C1), (A2, B2, C2), mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr

    # 交点が両直線を満たす（構成の恒真性を独立確認）: 独立に連立を解いて代入する
    x_sym, y_sym = sympy.symbols("x y")
    solution = sympy.solve(
        [sympy.Eq(A1 * x_sym + B1 * y_sym, C1), sympy.Eq(A2 * x_sym + B2 * y_sym, C2)],
        [x_sym, y_sym],
    )
    x0, y0 = solution[x_sym], solution[y_sym]
    assert A1 * x0 + B1 * y0 == C1
    assert A2 * x0 + B2 * y0 == C2


# ---------------------------------------------------------------------------
# math.solve_meeting_time_two_segment（C5 g2_l30.find_value Lv3 速さの変化・複数区間）
# ---------------------------------------------------------------------------
def test_solve_meeting_time_two_segment_lv3_construct():
    ctx = _make_ctx("math.g2_l30.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "meeting_time_two_segment"
    assert set(mr.given.keys()) == {"condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["set_up_second_segment_equation", "solve_for_x"]
    # 答えは自由変数を含まない正の値。
    val = sympy.sympify(sq.answer.srepr)
    assert not val.free_symbols
    assert val > 0


@pytest.mark.parametrize("seed", range(100))
def test_solve_meeting_time_two_segment_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l30.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_meeting_time_two_segment")
    sol = solver(
        mr.params["va"], mr.params["d"], mr.params["delay"],
        mr.params["v1"], mr.params["p1"], mr.params["v2"],
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 出会う時刻 t は確実に第2区間（delay+p1 より後）にある。
    va, d = sympy.Integer(mr.params["va"]), sympy.Integer(mr.params["d"])
    delay, v1, p1, v2 = (
        sympy.Integer(mr.params["delay"]), sympy.Integer(mr.params["v1"]),
        sympy.Integer(mr.params["p1"]), sympy.Integer(mr.params["v2"]),
    )
    t = sympy.sympify(sol.answer.srepr)
    assert t > delay + p1
    # 恒真: Aの位置とBの位置(第2区間の式)が時刻tで一致する。
    y_a = va * t
    y_b = d - v1 * p1 - v2 * (t - delay - p1)
    assert sympy.simplify(y_a - y_b) == 0


# ---------------------------------------------------------------------------
# math.y_range_from_domain / math.expr_from_range（g2_l23.find_value）— 横展開#3 変域
# ---------------------------------------------------------------------------
def test_y_range_lv2_forward_construct():
    ctx = _make_ctx("math.g2_l23.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "lf_y_range_forward"
    assert set(mr.given.keys()) == {"expression", "x_domain"}
    sq = mr.sub_questions[0]
    assert sq.asked == "domain_range"
    assert [s.op for s in sq.steps] == ["determine_sign", "eval_endpoints", "form_range"]


def test_expr_from_range_lv3_inverse_construct():
    ctx = _make_ctx("math.g2_l23.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "lf_expr_from_range_inverse"
    assert set(mr.given.keys()) == {"x_domain", "y_range", "condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"  # Lv2(domain_range) と asked が異なる＝別構造


@pytest.mark.parametrize("seed", range(200))
def test_y_range_lv2_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l23.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.y_range_over_domain")
    sol = solver(
        sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["x_lo"]), sympy.sympify(mr.params["x_hi"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


@pytest.mark.parametrize("seed", range(200))
def test_expr_from_range_lv3_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l23.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    p1 = sympy.sympify(mr.params["pts"][0])
    p2 = sympy.sympify(mr.params["pts"][1])
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = solver((p1[0], p1[1]), (p2[0], p2[1]), mr.params["method"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# provides_concepts の宣言確認（R6 の前提）
# ---------------------------------------------------------------------------
def test_recipes_declare_provides_concepts():
    assert REGISTRY.recipe_concepts("math.linear_from_two_points") == frozenset({
        "linear_function.slope_from_two_points",
        "linear_function.intercept_from_point",
        "linear_function.expression_from_two_points",
    })
    assert REGISTRY.recipe_concepts("math.linear_from_slope_point") == frozenset({
        "linear_function.expression_from_slope_point",
        "linear_function.intercept_from_point",
    })
    assert REGISTRY.recipe_concepts("math.linear_from_parallel_condition") == frozenset({
        "linear_function.parallel_condition",
        "linear_function.expression_from_slope_point",
    })
    assert REGISTRY.recipe_concepts("math.graph_read_two_points") == frozenset({
        "graph.read_lattice_points",
    })
    assert REGISTRY.recipe_concepts("math.read_slope_intercept") == frozenset({
        "graph.read_slope_intercept",
    })
    assert REGISTRY.recipe_concepts("math.solve_equation_for_y") == frozenset({
        "linear_function.solve_equation_for_y",
    })
    assert REGISTRY.recipe_concepts("math.evaluate_linear") == frozenset({
        "linear_function.evaluate_at_x",
    })
    assert REGISTRY.recipe_concepts("math.point_on_line") == frozenset({
        "linear_function.point_on_line",
    })
    assert REGISTRY.recipe_concepts("math.draw_linear") == frozenset({
        "linear_function.draw_graph",
    })
    assert REGISTRY.recipe_concepts("math.draw_linear_from_equation") == frozenset({
        "linear_function.draw_graph_from_equation",
    })
    assert REGISTRY.recipe_concepts("math.read_intersection_from_graph") == frozenset({
        "linear_function.read_intersection_from_graph",
    })
    assert REGISTRY.recipe_concepts("math.solve_system_elimination") == frozenset({
        "simultaneous_equations.solve_by_elimination",
    })
    assert REGISTRY.recipe_concepts("math.solve_system_substitution") == frozenset({
        "simultaneous_equations.solve_by_substitution",
    })
    assert REGISTRY.recipe_concepts("math.solve_system_elim_scaled") == frozenset({
        "simultaneous_equations.solve_by_elimination_scaled",
    })
    assert REGISTRY.recipe_concepts("math.solve_system_preprocessed") == frozenset({
        "simultaneous_equations.solve_with_preprocessing",
    })
    assert REGISTRY.recipe_concepts("math.solve_system_abc") == frozenset({
        "simultaneous_equations.solve_abc_form",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_slope_direction") == frozenset({
        "linear_function.slope_sign_to_direction",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_range_endpoint") == frozenset({
        "linear_function.range_endpoint_inclusion",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_verify_solution") == frozenset({
        "simultaneous_equations.verify_solution",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_classify_linear") == frozenset({
        "linear_function.classify_as_linear",
    })
    assert REGISTRY.recipe_concepts("math.linear_slope_as_rate") == frozenset({
        "linear_function.slope_as_rate_of_change",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_coefficient_role") == frozenset({
        "linear_function.coefficient_role",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_rate_constant") == frozenset({
        "linear_function.rate_of_change_is_constant",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_equation_solution_set") == frozenset({
        "linear_function.equation_solution_set_is_line",
    })
    assert REGISTRY.recipe_concepts("math.knowledge_system_intersection") == frozenset({
        "linear_function.system_solution_is_intersection",
    })
    assert REGISTRY.recipe_concepts("math.combine_like_terms") == frozenset({
        "polynomial.combine_like_terms_basic",
        "polynomial.combine_like_terms_mixed",
    })


# ---------------------------------------------------------------------------
# math.combine_like_terms（g2_l2.calculation Lv1/Lv2）— C2（数と式）クラスタ初セル
# ---------------------------------------------------------------------------
def test_combine_like_terms_lv1_construct():
    ctx = _make_ctx("math.g2_l2.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "combine_like_terms_single_var"
    assert set(mr.given.keys()) == {"expression"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert sq.answer.kind == "symbolic"
    assert [s.op for s in sq.steps] == ["group_like_terms", "add_coefficients"]
    # Lv1 は1種の文字（x）のみ
    assert mr.params["mode"] == "single_var"
    assert all(v == "x" for _, v in mr.params["terms"])


def test_combine_like_terms_lv2_construct():
    ctx = _make_ctx("math.g2_l2.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "combine_like_terms_mixed_vars"
    assert set(mr.given.keys()) == {"expression"}
    assert mr.visual_plan is None
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert sq.answer.kind == "symbolic"
    # Lv2 は先頭に「同類項を見分ける」1手を足した3手（level_sep=steps の op 列が相異）
    assert [s.op for s in sq.steps] == [
        "identify_like_terms",
        "group_like_terms",
        "add_coefficients",
    ]
    # Lv2 は2種の文字（a, b）が混在する（選別が必須になる構造）
    assert mr.params["mode"] == "mixed_vars"
    variables = {v for _, v in mr.params["terms"]}
    assert variables == {"a", "b"}


@pytest.mark.parametrize("seed", range(200))
def test_combine_like_terms_lv1_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l2.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    terms = mr.params["terms"]
    expr_str = "+".join(f"({c})*{v}" if v else f"({c})" for c, v in terms)
    solver = REGISTRY.solver("math.simplify_polynomial")
    sol = solver(expr_str)
    assert sol.answer.kind == "symbolic"
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr

    # 健全性: 答え（展開後）は sympy.expand(与式) と一致し、係数の絶対値は0/1にならない
    # （0=同類項が消える退化、1="x"/"-x" が与式中に部分文字列として現れる G-Q5t 漏洩を回避）。
    expected = sympy.expand(sympy.sympify(expr_str))
    assert sol.answer.srepr == sympy.srepr(expected)
    coeff = expected.as_coefficients_dict()[sympy.Symbol("x")]
    assert abs(coeff) not in (0, 1)


@pytest.mark.parametrize("seed", range(200))
def test_combine_like_terms_lv2_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l2.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    terms = mr.params["terms"]
    expr_str = "+".join(f"({c})*{v}" if v else f"({c})" for c, v in terms)
    solver = REGISTRY.solver("math.simplify_polynomial")
    sol = solver(expr_str)
    assert sol.answer.kind == "symbolic"
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr

    expected = sympy.expand(sympy.sympify(expr_str))
    assert sol.answer.srepr == sympy.srepr(expected)
    coeffs = expected.as_coefficients_dict()
    coeff_a = coeffs[sympy.Symbol("a")]
    coeff_b = coeffs[sympy.Symbol("b")]
    # 両方の文字が答えに残る（どちらかが完全に消える退化を回避）かつ絶対値は0/1にならない
    assert abs(coeff_a) not in (0, 1)
    assert abs(coeff_b) not in (0, 1)


# ---------------------------------------------------------------------------
# math.substitute_into_equation（g2_l10.calculation Lv1）— P1/C2（左辺の値を求める）
# ---------------------------------------------------------------------------
def test_substitute_into_equation_lv1_construct():
    ctx = _make_ctx("math.g2_l10.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "substitute_into_equation_lhs"
    assert set(mr.given.keys()) == {"equation", "candidate"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.kind == "symbolic"
    assert [s.op for s in sq.steps] == ["substitute_candidate", "compute_lhs"]
    a, b = sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"])
    xc, yc = sympy.sympify(mr.params["x_cand"]), sympy.sympify(mr.params["y_cand"])
    assert sympy.sympify(sq.answer.srepr) == a * xc + b * yc
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(200))
def test_substitute_into_equation_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l10.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.evaluate_two_var_lhs")
    sol = solver(
        sympy.sympify(mr.params["a"]), sympy.sympify(mr.params["b"]),
        sympy.sympify(mr.params["x_cand"]), sympy.sympify(mr.params["y_cand"]),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.add_or_subtract_polynomials（g2_l3.calculation Lv1/Lv2）— P1/C2（多項式の加減）
# ---------------------------------------------------------------------------
def test_add_polynomials_lv1_construct():
    ctx = _make_ctx("math.g2_l3.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "add_polynomials"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["remove_parentheses", "add_like_terms"]
    assert mr.params["is_subtraction"] is False


def test_subtract_polynomials_lv2_construct():
    ctx = _make_ctx("math.g2_l3.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "subtract_polynomials"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["distribute_negative_sign", "add_like_terms"]
    assert mr.params["is_subtraction"] is True


@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("seed", range(100))
def test_add_or_subtract_polynomials_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l3.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.add_or_subtract_polynomials")
    sol = solver(mr.params["expr_str"], mr.params["is_subtraction"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えは expand と一致
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(mr.params["expr_str"])))


# ---------------------------------------------------------------------------
# math.distribute_or_divide（g2_l5.calculation Lv1/Lv2）— P1/C2（分配・除法）
# ---------------------------------------------------------------------------
def test_distribute_multiply_lv1_construct():
    ctx = _make_ctx("math.g2_l5.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "distribute_multiply"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["distribute_multiplication"]
    assert mr.params["is_division"] is False


def test_divide_polynomial_lv2_construct():
    ctx = _make_ctx("math.g2_l5.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "divide_polynomial"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["convert_division_to_multiplication", "distribute"]
    assert mr.params["is_division"] is True
    # 割り切れる（答えは整数係数）
    ans = sympy.sympify(sq.answer.srepr)
    for c in ans.as_coefficients_dict().values():
        assert c == int(c)


@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("seed", range(100))
def test_distribute_or_divide_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l5.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.distribute_or_divide")
    sol = solver(mr.params["expr_str"], mr.params["is_division"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(mr.params["expr_str"])))


# ---------------------------------------------------------------------------
# math.compute_monomial_expression（g2_l4.calculation Lv1/Lv2/Lv3）— P1/C2（単項式乗除）
# ---------------------------------------------------------------------------
def test_multiply_monomials_lv1_construct():
    ctx = _make_ctx("math.g2_l4.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "multiply_monomials"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["multiply_coefficients", "combine_powers"]


def test_multiply_monomials_powers_lv2_construct():
    ctx = _make_ctx("math.g2_l4.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "multiply_monomials_powers"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "determine_sign", "multiply_coefficients", "combine_powers",
    ]


def test_monomial_mul_div_chain_lv3_construct():
    ctx = _make_ctx("math.g2_l4.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "monomial_mul_div_chain"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "convert_divisions_to_reciprocal", "multiply_coefficients", "combine_powers",
    ]
    # 答えは整数係数の単項式（factor-first で保証）
    ans = sympy.sympify(mr.sub_questions[0].answer.srepr)
    for c in ans.as_coefficients_dict().values():
        assert c == int(c)


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("seed", range(100))
def test_compute_monomial_expression_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l4.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    solver = REGISTRY.solver("math.compute_monomial_expression")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.simplify(sympy.sympify(mr.params["expr_str"])))


# ---------------------------------------------------------------------------
# math.combine_fractional_expressions（g2_l6.calculation Lv2/Lv3）— P1/C2（通分）
# ---------------------------------------------------------------------------
def test_combine_fractions_lv2_construct():
    ctx = _make_ctx("math.g2_l6.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "combine_fractions_add"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["find_common_denominator", "combine_numerators"]


def test_combine_fractions_lv3_construct():
    ctx = _make_ctx("math.g2_l6.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "combine_fractions_signed_integer"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "find_common_denominator", "distribute_signs", "add_integer_term",
    ]


@pytest.mark.parametrize("level", [2, 3])
@pytest.mark.parametrize("seed", range(100))
def test_combine_fractional_expressions_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l6.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.combine_fractional_expressions")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.together(sympy.sympify(mr.params["expr_str"])))
    assert sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.degree_of_expression（g2_l1.calculation Lv1）— P1/C2（次数）
# ---------------------------------------------------------------------------
def test_degree_of_expression_lv1_construct():
    ctx = _make_ctx("math.g2_l1.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "degree_of_expression"
    sq = mr.sub_questions[0]
    assert sq.asked == "degree"
    assert [s.op for s in sq.steps] == ["find_highest_degree_term", "read_degree"]


@pytest.mark.parametrize("seed", range(100))
def test_degree_of_expression_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l1.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.degree_of_expression")
    sol = solver(mr.params["expr_str"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えの次数は sympy.degree と一致
    expr = sympy.sympify(mr.params["expr_str"])
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(int(sympy.degree(expr, gen=sympy.Symbol("x")))))


# ---------------------------------------------------------------------------
# math.solve_for_variable（g2_l9.calculation Lv1/Lv2/Lv3）— P1/C2（等式変形）
# ---------------------------------------------------------------------------
def test_solve_for_variable_lv1_construct():
    ctx = _make_ctx("math.g2_l9.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "rearrange_move_only"
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    assert [s.op for s in sq.steps] == ["isolate_target"]


def test_solve_for_variable_lv2_construct():
    ctx = _make_ctx("math.g2_l9.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "rearrange_divide_coeff"
    assert [s.op for s in mr.sub_questions[0].steps] == ["isolate_target", "divide_by_coefficient"]


def test_solve_for_variable_lv3_construct():
    ctx = _make_ctx("math.g2_l9.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "rearrange_product_fraction"
    assert [s.op for s in mr.sub_questions[0].steps] == ["multiply_both_sides", "divide_by_coefficient"]


@pytest.mark.parametrize("level", [1, 2, 3])
@pytest.mark.parametrize("seed", range(100))
def test_solve_for_variable_double_solve_property(level, seed):
    ctx = _make_ctx("math.g2_l9.calculation", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_for_variable")
    sol = solver(mr.params["equation_str"], mr.params["target"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # solver の解が sympy.solve と一致
    lhs_s, rhs_s = mr.params["equation_str"].split("=")
    eq = sympy.Eq(sympy.sympify(lhs_s), sympy.sympify(rhs_s))
    expected = sympy.solve(eq, sympy.Symbol(mr.params["target"]))[0]
    assert sol.answer.srepr == sympy.srepr(expected)
    assert sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.express_number_property（g2_l7.calculation Lv1）— P1/C2（数の性質の式）
# ---------------------------------------------------------------------------
def test_express_number_property_lv1_construct():
    ctx = _make_ctx("math.g2_l7.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "consecutive_number_sum"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["expand_expression", "combine_like_terms"]


@pytest.mark.parametrize("seed", range(100))
def test_express_number_property_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l7.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.express_number_property")
    sol = solver(mr.params["expr_str"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(mr.params["expr_str"])))
    assert sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.combine_digit_number（g2_l8.calculation Lv1）— P1/C2（2けたの自然数）
# ---------------------------------------------------------------------------
def test_combine_digit_number_lv1_construct():
    ctx = _make_ctx("math.g2_l8.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "two_digit_number_property"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["express_swapped_number", "combine_like_terms"]


@pytest.mark.parametrize("seed", range(100))
def test_combine_digit_number_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l8.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.combine_digit_number")
    sol = solver(mr.params["expr_str"], mr.params["operation"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.expand(sympy.sympify(mr.params["expr_str"])))
    assert sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# C2 knowledge（用語想起・判別・ChoiceAnswer）— g2_l1/g2_l2/g2_l10
# ---------------------------------------------------------------------------
def test_poly_term_recall_lv1_construct():
    ctx = _make_ctx("math.g2_l1.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "poly_term_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert [s.op for s in sq.steps] == ["identify_description", "name_concept"]


def test_poly_classify_lv2_construct():
    ctx = _make_ctx("math.g2_l1.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "classify_monomial_or_polynomial"
    assert [s.op for s in mr.sub_questions[0].steps] == ["count_terms", "classify_type"]


@pytest.mark.parametrize("seed", range(80))
def test_poly_term_recall_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l1.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.poly_term_definition")(mr.params["concept"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


@pytest.mark.parametrize("seed", range(80))
def test_poly_classify_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l1.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.classify_monomial_or_polynomial")(mr.params["expr_str"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_like_terms_judge_lv1_construct():
    ctx = _make_ctx("math.g2_l2.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "like_terms_judge"
    assert [s.op for s in mr.sub_questions[0].steps] == ["compare_variable_parts", "judge_like_terms"]


@pytest.mark.parametrize("seed", range(80))
def test_like_terms_judge_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l2.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.judge_like_terms")(mr.params["term1"], mr.params["term2"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_system_term_recall_lv1_construct():
    ctx = _make_ctx("math.g2_l10.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "system_term_recall"
    assert [s.op for s in mr.sub_questions[0].steps] == ["identify_description", "name_concept"]


@pytest.mark.parametrize("seed", range(80))
def test_system_term_recall_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l10.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sol = REGISTRY.solver("math.system_term_definition")(mr.params["concept"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


# ---------------------------------------------------------------------------
# math.compute_signed_arithmetic（C1 g1 正の数・負の数の四則）— P2
# ---------------------------------------------------------------------------
def test_signed_addition_pair_lv1_construct():
    ctx = _make_ctx("math.g1_l3.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "addition_pair"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["determine_sum_sign", "add_magnitudes"]


def test_signed_addition_terms_lv2_construct():
    ctx = _make_ctx("math.g1_l3.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "addition_terms"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_as_term_sum", "group_by_sign", "total_terms",
    ]


def test_signed_subtraction_pair_lv1_construct():
    ctx = _make_ctx("math.g1_l4.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "subtraction_pair"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_subtraction_as_addition", "add_signed",
    ]


def test_signed_subtraction_terms_lv2_construct():
    ctx = _make_ctx("math.g1_l4.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "subtraction_terms"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_all_as_addition", "group_by_sign", "total_terms",
    ]


def test_signed_multiplication_pair_lv1_construct():
    ctx = _make_ctx("math.g1_l6.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "multiplication_pair"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "determine_product_sign", "multiply_magnitudes",
    ]


def test_signed_multiplication_chain_lv2_construct():
    ctx = _make_ctx("math.g1_l6.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "multiplication_chain"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "count_negative_factors", "multiply_all_magnitudes",
    ]


def test_signed_divide_pair_lv1_construct():
    ctx = _make_ctx("math.g1_l8.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "divide_pair"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_division_as_reciprocal", "multiply_signed",
    ]
    # 割り切れる（答えは整数）。
    assert sympy.sympify(mr.sub_questions[0].answer.srepr).is_Integer


def test_signed_divide_chain_lv2_construct():
    ctx = _make_ctx("math.g1_l8.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "divide_chain"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_all_as_reciprocal", "determine_product_sign", "multiply_all_magnitudes",
    ]


def test_signed_add_sub_terms_lv1_construct():
    ctx = _make_ctx("math.g1_l5.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "add_sub_terms"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "drop_parentheses_to_terms", "group_by_sign", "total_terms",
    ]


def test_signed_add_sub_terms_rational_lv2_construct():
    ctx = _make_ctx("math.g1_l5.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "add_sub_terms_rational"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "drop_parentheses_to_terms", "align_fractions", "total_terms",
    ]


def test_signed_power_single_lv1_construct():
    ctx = _make_ctx("math.g1_l7.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "power_single"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_power_as_product", "evaluate_power_with_sign",
    ]


def test_signed_power_sign_contrast_lv2_construct():
    ctx = _make_ctx("math.g1_l7.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "power_sign_contrast"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "identify_base_scope", "evaluate_power_with_sign",
    ]


def test_signed_power_neg_inside_is_negative():
    """Lv2 の -a^n 形（neg_inside）は常に負になる（指数の作用範囲の区別を確認）。"""
    ctx = _make_ctx("math.g1_l7.calculation", 2)
    found = False
    for seed in range(60):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        disp = mr.given["expression"]
        if disp.startswith("-") and "(" not in disp:
            found = True
            assert sympy.sympify(mr.sub_questions[0].answer.srepr) < 0
    assert found, "neg_inside(-a^n)形が60seed内で1つも出現しなかった"


def test_signed_four_operations_lv2_construct():
    ctx = _make_ctx("math.g1_l9.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "four_operations"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "evaluate_powers_and_parentheses", "multiply_and_divide", "add_and_subtract",
    ]


def test_signed_distributive_trick_lv3_construct():
    ctx = _make_ctx("math.g1_l9.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "distributive_trick"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "rewrite_as_round_plus_offset", "distribute_over_round", "combine_easy_parts",
    ]


def test_signed_absolute_value_lv1_construct():
    ctx = _make_ctx("math.g1_l2.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "absolute_value"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "locate_on_number_line", "read_distance_from_zero",
    ]
    # 絶対値は 0 以上。
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) >= 0


def test_signed_order_numbers_lv2_construct():
    ctx = _make_ctx("math.g1_l2.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "order_numbers"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "convert_to_common_form", "compare_on_number_line", "arrange_in_order",
    ]


@pytest.mark.parametrize("seed", range(100))
def test_order_signed_numbers_sorted_property(seed):
    """並べ替えの答えが実際に昇順/降順に整列していることを確認する。"""
    ctx = _make_ctx("math.g1_l2.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    ordered = sympy.sympify(mr.sub_questions[0].answer.srepr)  # Tuple
    vals = [sympy.Rational(x) for x in ordered]
    asc = mr.params["ascending"]
    expected = sorted(vals, reverse=not asc)
    assert vals == expected
    # 独立ソルバでの再計算と一致（double-solve）。
    sol = REGISTRY.solver("math.order_signed_numbers")(mr.params["numbers_str"], mr.params["ascending"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


_SIGNED_ARITHMETIC_CELLS = [
    ("math.g1_l2.calculation", 1),
    ("math.g1_l3.calculation", 1), ("math.g1_l3.calculation", 2),
    ("math.g1_l4.calculation", 1), ("math.g1_l4.calculation", 2),
    ("math.g1_l5.calculation", 1), ("math.g1_l5.calculation", 2),
    ("math.g1_l6.calculation", 1), ("math.g1_l6.calculation", 2),
    ("math.g1_l7.calculation", 1), ("math.g1_l7.calculation", 2),
    ("math.g1_l8.calculation", 1), ("math.g1_l8.calculation", 2),
    ("math.g1_l9.calculation", 2), ("math.g1_l9.calculation", 3),
]


@pytest.mark.parametrize("family,level", _SIGNED_ARITHMETIC_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_signed_arithmetic_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_numeric_expression")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    # 独立ソルバの答えが recipe の答えと一致し、かつ与式の厳密評価に等しい。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    expected = sympy.sympify(mr.params["expr_str"], rational=True)
    assert sol.answer.srepr == sympy.srepr(expected)
    # 答えは定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.factorize_integer（C1 g1_l11.calculation 素因数分解）— P2 bespoke
# ---------------------------------------------------------------------------
def test_factorize_basic_lv1_construct():
    ctx = _make_ctx("math.g1_l11.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "factorize_basic"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "divide_out_primes_in_order", "write_prime_power_form",
    ]


def test_factorize_advanced_lv2_construct():
    ctx = _make_ctx("math.g1_l11.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "factorize_advanced"
    # level_sep: Lv2 は「次の素数を順に試す」手順を先頭に足した3手順。
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "test_successive_prime_divisors", "divide_out_primes_in_order", "write_prime_power_form",
    ]


_FACTORIZE_CELLS = [
    ("math.g1_l11.calculation", 1),
    ("math.g1_l11.calculation", 2),
]


@pytest.mark.parametrize("family,level", _FACTORIZE_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_factorize_integer_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    n = int(mr.params["value"])
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.factorize_integer")
    sol = solver(mr.params["value"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 分解形（srepr）を評価すると対象数 N に戻り、底はすべて素数。
    factored = sympy.sympify(sol.answer.srepr)
    assert factored == n
    assert not factored.free_symbols
    assert all(sympy.isprime(p) for p in sympy.factorint(n))
    # given の対象数は問題文にそのまま出る（G-GND）。
    assert mr.given["expression"] == str(n)


# ---------------------------------------------------------------------------
# math.scientific_notation（C1 g1_l60.calculation 科学的記数法 a×10ⁿ）— P2 bespoke
# ---------------------------------------------------------------------------
def test_sci_notation_basic_lv1_construct():
    ctx = _make_ctx("math.g1_l60.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sci_notation_basic"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["locate_decimal_point", "write_scientific_form"]


def test_sci_notation_sigfig_lv2_construct():
    ctx = _make_ctx("math.g1_l60.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sci_notation_sigfig"
    # 有効数字の桁数は given に含まれ問題文に出る（whitelist 対象）。
    assert set(mr.given.keys()) == {"expression", "sig_figs"}
    # level_sep: Lv2 は四捨五入手順を先頭に足した3手順。
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "round_to_significant_figures", "locate_decimal_point", "write_scientific_form",
    ]


_SCI_NOTATION_CELLS = [
    ("math.g1_l60.calculation", 1),
    ("math.g1_l60.calculation", 2),
]


@pytest.mark.parametrize("family,level", _SCI_NOTATION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_scientific_notation_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.scientific_notation")
    sol = solver(mr.params["value"], mr.params["mode"], mr.params.get("sig_figs"))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えは a×10ⁿ 形（"<mantissa>E<exponent>"）。mantissa は 1 以上 10 未満、指数は 2〜9。
    mantissa_str, exp_str = sol.answer.srepr.split("E")
    mantissa = sympy.Rational(mantissa_str)
    exponent = int(exp_str)
    assert 1 <= mantissa < 10
    assert mantissa != 1  # "1以上" と衝突しないこと（G-Q5t）
    assert 2 <= exponent <= 9
    # 定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.read_number_line_point（C1 g1_l2.graph_table Lv1 数直線の点を読む）— P2 bespoke（図つき初 C1）
# ---------------------------------------------------------------------------
def test_read_number_line_point_lv1_construct():
    ctx = _make_ctx("math.g1_l2.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "number_line_read_point"
    # given は空: 数直線は図で提示され、テキストに接地すべき given は無い。
    assert mr.given == {}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_point"
    assert [s.op for s in sq.steps] == ["identify_interval", "read_point"]
    # 答えは分数（非整数）。目盛（整数）と一致しない＝図の目盛ラベルと衝突しない。
    ans_val = sympy.sympify(sq.answer.srepr)
    assert not ans_val.is_integer
    # visual_plan は非 None（frame.visual="required" を満たす）。
    assert mr.visual_plan is not None
    assert mr.visual_plan.style == "number_line"
    # labels は整数目盛の単独数値と点の記号「P」のみ（答えの分数は載せない）。
    assert "P" in mr.visual_plan.labels
    for label in mr.visual_plan.labels:
        assert "/" not in label  # 分数（答え）表記なし
    # 答えの点マーカー（labeled_answer_point）を elements に含めない（幾何的リーク規則）。
    assert all(el.kind != "labeled_answer_point" for el in mr.visual_plan.elements)


@pytest.mark.parametrize("seed", range(200))
def test_read_number_line_point_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l2.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a, k, i = int(mr.params["a"]), int(mr.params["k"]), int(mr.params["i"])
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.read_number_line_point")
    sol = solver(a, k, i)
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 答えは a + i/k（既約分数）で、目盛位置 i は 1..k-1 に収まる。
    assert sympy.sympify(sol.answer.srepr) == sympy.Rational(a * k + i, k)
    assert 2 <= k <= 5
    assert 1 <= i <= k - 1


# ---------------------------------------------------------------------------
# math.expand_product（C3 g3_l1〜l6.calculation 多項式の展開）— P2 展開コア能力
# ---------------------------------------------------------------------------
_EXPAND_CELLS = [
    ("math.g3_l1.calculation", 1), ("math.g3_l1.calculation", 2),
    ("math.g3_l2.calculation", 1), ("math.g3_l2.calculation", 2),
    ("math.g3_l3.calculation", 1), ("math.g3_l3.calculation", 2),
    ("math.g3_l4.calculation", 1), ("math.g3_l4.calculation", 2),
    ("math.g3_l5.calculation", 1),
    ("math.g3_l6.calculation", 2), ("math.g3_l6.calculation", 3),
    ("math.g3_l13.calculation", 2),
]


def test_expand_product_lv1_construct():
    ctx = _make_ctx("math.g3_l2.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "expand_binomial_product"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["expand_all_products", "combine_like_terms"]
    # 答えは展開後の多項式（自由変数を含む）で、与式（積の形）とは構造が異なる。
    assert sympy.sympify(sq.answer.srepr).free_symbols


@pytest.mark.parametrize("family,level", _EXPAND_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_expand_product_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.expand_expression")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 答えは与式を sympy.expand した結果に等しい。
    assert sympy.sympify(sol.answer.srepr) == sympy.expand(sympy.sympify(mr.params["expr_str"]))
    # 答えは自由変数を含む式（展開後の多項式）。
    assert sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.factor_polynomial（C3 g3_l7〜l11.calculation 因数分解）— P2 因数分解コア能力
# ---------------------------------------------------------------------------
_FACTOR_CELLS = [
    ("math.g3_l7.calculation", 1), ("math.g3_l7.calculation", 2),
    ("math.g3_l8.calculation", 1), ("math.g3_l8.calculation", 2),
    ("math.g3_l9.calculation", 1),
    ("math.g3_l10.calculation", 1),
    ("math.g3_l11.calculation", 2), ("math.g3_l11.calculation", 3),
]


def test_factor_polynomial_lv1_construct():
    ctx = _make_ctx("math.g3_l8.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "factor_sum_product"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["find_two_numbers", "write_factors"]
    # 答えは因数分解形（積または累乗）で、展開すると与式に戻る。
    factored = sympy.sympify(sq.answer.srepr)
    assert factored.is_Mul or factored.is_Pow
    assert sympy.expand(factored) == sympy.expand(sympy.sympify(mr.params["expr_str"]))


@pytest.mark.parametrize("family,level", _FACTOR_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_factor_polynomial_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.factor_expression")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    factored = sympy.sympify(sol.answer.srepr)
    # 恒真: 因数分解形は非自明（積または累乗）で、展開すると与式に戻る。
    assert factored.is_Mul or factored.is_Pow
    assert sympy.expand(factored) == sympy.expand(sympy.sympify(mr.params["expr_str"]))


# ---------------------------------------------------------------------------
# math.evaluate_arithmetic_via_identity（C3 g3_l12.calculation 式の計算の利用）
# ---------------------------------------------------------------------------
_ARITHMETIC_IDENTITY_CELLS = [
    ("math.g3_l12.calculation", 2), ("math.g3_l12.calculation", 3),
]


def test_evaluate_arithmetic_via_identity_lv2_construct():
    ctx = _make_ctx("math.g3_l12.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "evaluate_diff_of_squares_arithmetic"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["factor_difference_of_squares", "multiply_factors"]
    # 答えは自由変数を含まない整数。
    assert not sympy.sympify(sq.answer.srepr).free_symbols


def test_evaluate_arithmetic_via_identity_lv3_construct():
    ctx = _make_ctx("math.g3_l12.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "evaluate_symmetric_sum_of_squares"
    assert set(mr.given.keys()) == {"equation_a", "equation_b", "expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "express_via_elementary_symmetric", "substitute_and_compute",
    ]
    assert not sympy.sympify(sq.answer.srepr).free_symbols


@pytest.mark.parametrize("family,level", _ARITHMETIC_IDENTITY_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_evaluate_arithmetic_via_identity_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.evaluate_arithmetic_via_identity")
    sol = solver(mr.params["mode"], mr.params["value1"], mr.params["value2"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えは自由変数を含まない整数（工夫計算の最終値）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.simplify_radical（C3 g3_l14/l17〜l21.calculation 平方根の計算）— P2 平方根コア能力
# ---------------------------------------------------------------------------
_RADICAL_CELLS = [
    ("math.g3_l14.calculation", 1),
    ("math.g3_l17.calculation", 1), ("math.g3_l17.calculation", 2),
    ("math.g3_l18.calculation", 1), ("math.g3_l18.calculation", 2),
    ("math.g3_l19.calculation", 1),
    ("math.g3_l20.calculation", 1), ("math.g3_l20.calculation", 2),
    ("math.g3_l21.calculation", 2), ("math.g3_l21.calculation", 3),
    ("math.g3_l23.calculation", 2),
]


def test_simplify_radical_lv1_construct():
    ctx = _make_ctx("math.g3_l18.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_simplify_root"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["factor_out_square", "take_root_outside"]
    # 答えは与式と数学的に等しい（sympy の堅牢なゼロ判定 .equals を使う。evalf はハングする）。
    diff = sympy.sympify(mr.params["expr_str"]) - sympy.sympify(sq.answer.srepr)
    assert diff.equals(0)


@pytest.mark.parametrize("family,level", _RADICAL_CELLS)
@pytest.mark.parametrize("seed", range(60))
def test_simplify_radical_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.simplify_radical")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 答えは与式と数学的に等しい（.equals で堅牢にゼロ判定・evalf はハングする）。
    diff = sympy.sympify(mr.params["expr_str"]) - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0)


# ---------------------------------------------------------------------------
# math.evaluate_radical_substitution（C3 g3_l22.calculation 式の値）— √を含む値の代入
# ---------------------------------------------------------------------------
_RADICAL_SUBSTITUTION_CELLS = [
    ("math.g3_l22.calculation", 2),
    ("math.g3_l22.calculation", 3),
]


def _expand_radical_substitution_expected(params: dict) -> sympy.Expr:
    """params から独立に代入・展開した期待値（Lv2=x単独／Lv3=x,y共役組の両対応）。"""
    x = sympy.Symbol("x")
    subs_map: dict[sympy.Symbol, sympy.Expr] = {x: sympy.sympify(params["value_str"])}
    if "value_str_y" in params:
        y = sympy.Symbol("y")
        subs_map[y] = sympy.sympify(params["value_str_y"])
    return sympy.expand(sympy.sympify(params["expr_str"]).subs(subs_map))


def test_evaluate_radical_substitution_lv2_construct():
    ctx = _make_ctx("math.g3_l22.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_evaluate_expression_value"
    assert set(mr.given.keys()) == {"expression", "input_value"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_root_value", "expand_and_simplify"]
    # 答えは根号を含まない定数（自由変数なし）。
    result = sympy.sympify(sq.answer.srepr)
    assert not result.free_symbols
    # 恒真: 独立に構成値を代入・展開した結果と answer が一致する（.equals で堅牢にゼロ判定）。
    expected = _expand_radical_substitution_expected(mr.params)
    diff = expected - result
    assert diff.equals(0)


def test_evaluate_radical_substitution_lv3_construct():
    ctx = _make_ctx("math.g3_l22.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_evaluate_symmetric_pair_value"
    assert set(mr.given.keys()) == {"expression", "input_value"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_conjugate_pair_values", "expand_and_simplify"]
    # level_sep: Lv2 とは op 列が異なる（先頭 op 名が別）。
    assert sq.steps[0].op != "substitute_root_value"
    # 答えは根号を含まない定数（自由変数なし）。
    result = sympy.sympify(sq.answer.srepr)
    assert not result.free_symbols
    # 恒真: 独立に構成値の組(x,y)を代入・展開した結果と answer が一致する（.equals で堅牢にゼロ判定）。
    expected = _expand_radical_substitution_expected(mr.params)
    diff = expected - result
    assert diff.equals(0)


@pytest.mark.parametrize("family,level", _RADICAL_SUBSTITUTION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_evaluate_radical_substitution_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。value_str_y は
    # Lv3（2変数の対称式）のみ params に存在する。
    solver = REGISTRY.solver("math.evaluate_radical_substitution")
    sol = solver(
        mr.params["expr_str"], mr.params["value_str"], mr.params["mode"],
        mr.params.get("value_str_y"),
    )
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 答えは構成値を代入・展開した結果に等しい（.equals で堅牢にゼロ判定・evalf はハングする）。
    expected = _expand_radical_substitution_expected(mr.params)
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0)
    # 答えは根号を含まない定数（自由変数なし）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.find_side_from_area（C3 g3_l23.find_value 面積から1辺の長さ）
# ---------------------------------------------------------------------------
def test_find_side_from_area_lv2_construct():
    ctx = _make_ctx("math.g3_l23.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_find_side_from_area"
    assert set(mr.given.keys()) == {"condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["factor_out_square", "take_root_outside"]
    diff = sympy.sympify(mr.params["expr_str"]) - sympy.sympify(sq.answer.srepr)
    assert diff.equals(0)


@pytest.mark.parametrize("seed", range(100))
def test_find_side_from_area_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l23.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.simplify_radical")
    sol = solver(mr.params["expr_str"], "find_side_from_area")
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    diff = sympy.sympify(mr.params["expr_str"]) - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0)


# ---------------------------------------------------------------------------
# math.compare_radical_values（C3 g3_l15.calculation 平方根の大小関係）
# ---------------------------------------------------------------------------
_COMPARE_RADICAL_CELLS = [
    ("math.g3_l15.calculation", 1), ("math.g3_l15.calculation", 2),
]


def test_compare_radical_values_lv1_construct():
    ctx = _make_ctx("math.g3_l15.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_compare_pair"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["square_each_value", "compare_squares"]
    ordered = sympy.sympify(sq.answer.srepr)
    assert len(ordered) == 2
    assert ordered[0] < ordered[1]


def test_compare_radical_values_lv2_construct():
    ctx = _make_ctx("math.g3_l15.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "radical_compare_triplet"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == ["convert_to_squared_form", "compare_and_order"]
    ordered = sympy.sympify(sq.answer.srepr)
    assert len(ordered) == 3
    assert ordered[0] < ordered[1] < ordered[2]


@pytest.mark.parametrize("family,level", _COMPARE_RADICAL_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compare_radical_values_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.compare_radical_values")
    sol = solver(mr.params["exprs"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: 答えの集合は構成した値の集合と一致し、昇順になっている。
    ordered = sympy.sympify(sol.answer.srepr)
    assert set(sympy.sympify(e) for e in mr.params["exprs"]) == set(ordered)
    assert all(ordered[i] < ordered[i + 1] for i in range(len(ordered) - 1))


# ---------------------------------------------------------------------------
# math.convert_rational_decimal_form（C3 g3_l16.calculation 有理数の形）
# ---------------------------------------------------------------------------
_RATIONAL_FORM_CELLS = [
    ("math.g3_l16.calculation", 1), ("math.g3_l16.calculation", 2),
]


def test_convert_rational_decimal_form_lv1_construct():
    ctx = _make_ctx("math.g3_l16.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "fraction_to_repeating_decimal"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "long_division_track_remainders", "identify_repeating_block",
    ]
    # srepr は ASCII-only な正準形 "0.<非循環部>(<循環節>)"。
    assert sq.answer.srepr.startswith("0.")
    assert "(" in sq.answer.srepr and sq.answer.srepr.endswith(")")


def test_convert_rational_decimal_form_lv2_construct():
    ctx = _make_ctx("math.g3_l16.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "repeating_decimal_to_fraction"
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["set_up_algebraic_equation", "solve_for_fraction"]
    # 答えは既約分数（sympy Rational）で、自由変数を含まない。
    assert not sympy.sympify(sq.answer.srepr).free_symbols


@pytest.mark.parametrize("family,level", _RATIONAL_FORM_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_convert_rational_decimal_form_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    mode = mr.params["mode"]
    if mode == "fraction_to_repeating_decimal":
        solver = REGISTRY.solver("math.fraction_to_repeating_decimal")
        sol = solver(mr.params["p"], mr.params["q"])
    else:
        solver = REGISTRY.solver("math.repeating_decimal_to_fraction")
        sol = solver(mr.params["non_repeating"], mr.params["repeating"])
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# math.solve_quadratic（C3 g3_l24〜l28.calculation 2次方程式）— P2 二次方程式コア能力
# ---------------------------------------------------------------------------
_QUADRATIC_CELLS = [
    ("math.g3_l24.calculation", 1),
    ("math.g3_l25.calculation", 1), ("math.g3_l25.calculation", 2),
    ("math.g3_l26.calculation", 2), ("math.g3_l26.calculation", 3),
    ("math.g3_l27.calculation", 1), ("math.g3_l27.calculation", 2),
    ("math.g3_l28.calculation", 2), ("math.g3_l28.calculation", 3),
    ("math.g3_l29.calculation", 2),
    ("math.g3_l30.calculation", 2),
]


def test_solve_quadratic_lv1_construct():
    ctx = _make_ctx("math.g3_l27.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quad_solve_factoring"
    assert set(mr.given.keys()) == {"equation"}
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert [s.op for s in sq.steps] == ["factor_left_side", "apply_zero_product"]
    # 答えは解の Tuple。各解が方程式を満たす。
    lhs, rhs = mr.params["eq_str"].split("=", 1)
    eq_expr = sympy.sympify(lhs) - sympy.sympify(rhs)
    roots = sympy.sympify(sq.answer.srepr)
    assert len(roots) == 2
    for r in roots:
        assert eq_expr.subs(sympy.Symbol("x"), r).equals(0)


def test_solve_quadratic_product_form_construct():
    ctx = _make_ctx("math.g3_l29.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quad_solve_product_form"
    assert set(mr.given.keys()) == {"equation"}
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert [s.op for s in sq.steps] == [
        "expand_and_rearrange", "factor_left_side", "apply_zero_product",
    ]
    roots = sympy.sympify(sq.answer.srepr)
    assert len(roots) == 2


@pytest.mark.parametrize("family,level", _QUADRATIC_CELLS)
@pytest.mark.parametrize("seed", range(60))
def test_solve_quadratic_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.solve_quadratic")
    sol = solver(mr.params["eq_str"], mr.params["mode"], mr.params.get("value"))
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    lhs, rhs = mr.params["eq_str"].split("=", 1)
    eq_expr = sympy.sympify(lhs) - sympy.sympify(rhs)
    if mr.params.get("value") is None:
        # solve 系: 各解が方程式を満たす（恒真）。
        roots = sympy.sympify(sol.answer.srepr)
        assert len(roots) >= 1
        for r in roots:
            assert eq_expr.subs(sympy.Symbol("x"), r).equals(0)
    else:
        # evaluate 系: 答えは左辺に value を代入した値に等しい。
        expected = sympy.simplify(eq_expr.subs(sympy.Symbol("x"), sympy.nsimplify(sympy.sympify(mr.params["value"]))))
        assert sympy.sympify(sol.answer.srepr) == expected


# ---------------------------------------------------------------------------
# math.quadratic_rectangle_area_value（C3 g3_l30.find_value 長方形の面積条件）
# ---------------------------------------------------------------------------
def test_quadratic_rectangle_area_value_construct():
    ctx = _make_ctx("math.g3_l30.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quad_rectangle_area_positive_root"
    assert set(mr.given.keys()) == {"condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "expand_and_rearrange", "factor_left_side", "apply_zero_product", "select_positive_root",
    ]
    # 答えは正の値のみ（負の解は長さとして不適のため除外済み）。
    assert sympy.sympify(sq.answer.srepr) > 0


@pytest.mark.parametrize("seed", range(100))
def test_quadratic_rectangle_area_value_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l30.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    # 独立ソルバの答えが recipe の答えと一致する（double-solve）。
    solver = REGISTRY.solver("math.solve_quadratic")
    sol = solver(mr.params["eq_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    lhs, rhs = mr.params["eq_str"].split("=", 1)
    eq_expr = sympy.sympify(lhs) - sympy.sympify(rhs)
    root = sympy.sympify(sol.answer.srepr)
    assert eq_expr.subs(sympy.Symbol("x"), root).equals(0)
    assert root > 0


# ---------------------------------------------------------------------------
# math.solve_moving_point_area（C3 g3_l31.find_value 2次方程式の利用「動点」）
# ---------------------------------------------------------------------------
_MOTION_CELLS = [
    ("math.g3_l31.find_value", 2), ("math.g3_l31.find_value", 3),
]


def test_solve_moving_point_area_lv2_construct():
    ctx = _make_ctx("math.g3_l31.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "motion_area_single_segment"
    assert set(mr.given.keys()) == {"condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["locate_point_p", "compute_triangle_area"]
    # 面積は AP長×s÷2（点PがAB上・0<AP<s）に一致する。
    p, s = mr.params["v"] * mr.params["t"], mr.params["s"]
    assert 0 < p < s
    assert sympy.sympify(sq.answer.srepr) == sympy.Rational(p * s, 2)


def test_solve_moving_point_area_lv3_construct():
    ctx = _make_ctx("math.g3_l31.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "motion_area_two_segment"
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == [
        "determine_which_segment", "locate_point_p", "compute_triangle_area",
    ]
    # 点PはA→B→Cの2区間目（辺BC上）: s < v*t < 2s が確実に成り立つ。
    s, v, t = mr.params["s"], mr.params["v"], mr.params["t"]
    assert s < v * t < 2 * s
    # この区間では面積は s²/2 で一定になる。
    assert sympy.sympify(sq.answer.srepr) == sympy.Rational(s * s, 2)


def test_draw_area_time_graph_segment_lv2_construct():
    ctx = _make_ctx("math.g3_l31.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    assert mr.signature == "motion_area_time_graph_segment"
    assert set(mr.given.keys()) == {"condition"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_segment"
    assert sq.answer.kind == "graph"
    # 両端とも「到達の瞬間をふくむ」＝閉区間の端点2つ。
    assert [f.kind for f in sq.answer.features] == ["endpoint_closed", "endpoint_closed"]
    assert [s.op for s in sq.steps] == ["plot_endpoint_lo", "plot_endpoint_hi", "draw_segment"]
    # 時間-面積の量-量グラフ（第1象限・軸ごとに独立な目盛間隔）として描く。
    assert mr.params["grid_mode"] == "quantity"
    assert mr.visual_plan is not None
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}


@pytest.mark.parametrize("seed", range(100))
def test_draw_area_time_graph_segment_property(seed):
    """面積の式 y=(s·v/2)x（切片0）と、変域・端点・目盛が構成不変を満たす。"""
    ctx = _make_ctx("math.g3_l31.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    s, v, t_end = mr.params["side"], mr.params["speed"], mr.params["t_end"]
    # 1辺 s=v·t_end（P はちょうど t_end 秒で向かいの頂点に達する）・s は偶数。
    assert s == v * t_end
    assert s % 2 == 0
    # 直線は原点を通り傾きは s·v/2（底辺 s・高さ v·x の三角形の面積）。
    assert sympy.sympify(mr.params["b"]) == 0
    assert sympy.sympify(mr.params["a"]) == sympy.Rational(s * v, 2)
    assert sympy.sympify(mr.params["seg_x_lo"]) == 0
    assert sympy.sympify(mr.params["seg_x_hi"]) == t_end

    # 独立ソルバ（shoelace 公式・find_value と共有）で右端の面積を再計算すると s²/2。
    area = REGISTRY.solver("math.solve_moving_point_area")(s, v, t_end, "single_segment")
    assert sympy.sympify(area.answer.srepr) == sympy.Rational(s * s, 2)

    # 答えの端点は (0, 0) と (t_end, s²/2)（両端とも閉）。
    assert {f.srepr for f in mr.sub_questions[0].answer.features} == {
        sympy.srepr(sympy.Tuple(sympy.Integer(0), sympy.Integer(0), sympy.Integer(1))),
        sympy.srepr(sympy.Tuple(
            sympy.Integer(t_end), sympy.Rational(s * s, 2), sympy.Integer(1)
        )),
    }
    # 点名は正方形4頂点＋動点の5つが相異（surface の自由度＝dup 分散）。
    assert len(set(mr.params["labels"])) == 5


@pytest.mark.parametrize("family,level", _MOTION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_solve_moving_point_area_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_moving_point_area")
    sol = solver(mr.params["s"], mr.params["v"], mr.params["t"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 答えは自由変数を含まない非負の有理数。
    val = sympy.sympify(sol.answer.srepr)
    assert not val.free_symbols
    assert val >= 0


# ---------------------------------------------------------------------------
# math.count_significant_figures（C1 g1_l60.knowledge Lv2 有効数字の桁判別）— P2 bespoke
# ---------------------------------------------------------------------------
def test_count_significant_figures_lv2_construct():
    ctx = _make_ctx("math.g1_l60.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "approximation_judge_sigfig"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    # level_sep: 用語想起 Lv1 とは異なる op 列。
    assert [s.op for s in sq.steps] == [
        "find_first_significant_digit", "count_significant_digits",
    ]
    # 答えは漢数字の「○けた」で ASCII 数字を含まない（G-Q5t 素通り）。
    assert not any(ch.isdigit() for ch in sq.answer.correct)


@pytest.mark.parametrize("seed", range(200))
def test_count_significant_figures_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l60.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sq = mr.sub_questions[0]
    # 独立ソルバで再計算し一致（double-solve）。
    solver = REGISTRY.solver("math.count_significant_figures")
    sol = solver(mr.params["measurement"])
    assert sol.answer.correct == sq.answer.correct
    # 答え・誤選択肢いずれも ASCII 数字を含まない（G-Q5t 素通り）。
    assert not any(ch.isdigit() for ch in sol.answer.correct)
    assert all(not any(ch.isdigit() for ch in d) for d in sol.answer.distractors)
    assert sol.answer.correct not in sol.answer.distractors
    # 有効数字の桁数は、測定値の数字（小数点除去）から先頭0を除いた桁数に等しい。
    measurement = mr.params["measurement"]
    stripped = measurement.replace(".", "").lstrip("0")
    expected_count = len(stripped)
    kanji = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五"}
    assert sol.answer.correct == f"{kanji[expected_count]}けた"


# ---------------------------------------------------------------------------
# math.interpret_expression（C1 g1_l12.knowledge Lv2 式の意味の解釈）— P2 bespoke
# ---------------------------------------------------------------------------
def test_interpret_expression_lv2_construct():
    ctx = _make_ctx("math.g1_l12.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "letter_meaning_interpret"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    # level_sep: Lv1 規則想起とは異なる op 列。
    assert [s.op for s in sq.steps] == ["read_each_term_meaning", "combine_term_meanings"]
    # 品名で記述し ASCII 数字を含まない（G-Q5t 素通り）。
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert len(sq.answer.distractors) == 3


@pytest.mark.parametrize("seed", range(200))
def test_interpret_expression_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l12.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    sq = mr.sub_questions[0]
    # 独立ソルバで再計算し一致（double-solve）。
    solver = REGISTRY.solver("math.interpret_expression")
    sol = solver(mr.params["item_a"], mr.params["item_b"])
    assert sol.answer.correct == sq.answer.correct
    assert sol.answer.distractors == sq.answer.distractors
    # 答え・誤選択肢いずれも ASCII 数字を含まない（G-Q5t 素通り）。
    assert not any(ch.isdigit() for ch in sol.answer.correct)
    assert all(not any(ch.isdigit() for ch in d) for d in sol.answer.distractors)
    # 正解に両方の品名が含まれ、誤選択肢と重複しない。
    assert mr.params["item_a"] in sol.answer.correct
    assert mr.params["item_b"] in sol.answer.correct
    assert sol.answer.correct not in sol.answer.distractors

def test_letter_combine_linear_lv1_construct():
    ctx = _make_ctx("math.g1_l17.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "combine_linear"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["group_like_terms", "add_coefficients"]
    # 答えは一次式（x を含む）。
    assert sympy.Symbol("x") in sympy.sympify(sq.answer.srepr).free_symbols


def test_letter_expand_paren_linear_lv2_construct():
    ctx = _make_ctx("math.g1_l17.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "expand_paren_linear"
    assert [s.op for s in mr.sub_questions[0].steps] == ["remove_parentheses", "add_like_terms"]
    assert "(" in mr.given["expression"]  # かっこを含む


def test_letter_distribute_linear_lv1_construct():
    ctx = _make_ctx("math.g1_l18.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "distribute_linear"
    assert [s.op for s in mr.sub_questions[0].steps] == ["distribute_multiplication"]


def test_letter_distribute_divide_linear_lv2_construct():
    ctx = _make_ctx("math.g1_l18.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "distribute_divide_linear"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "distribute_multiplication", "convert_division_to_multiplication", "add_like_terms",
    ]
    assert "÷" in mr.given["expression"]  # 除法を含む


_LETTER_EXPR_CELLS = [
    ("math.g1_l17.calculation", 1), ("math.g1_l17.calculation", 2),
    ("math.g1_l18.calculation", 1), ("math.g1_l18.calculation", 2),
]


@pytest.mark.parametrize("family,level", _LETTER_EXPR_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_letter_expression_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_letter_expression")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    # 独立ソルバの答えが recipe の答えと一致し、かつ与式の厳密な整理に等しい。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    expected = sympy.expand(sympy.sympify(mr.params["expr_str"]))
    assert sol.answer.srepr == sympy.srepr(expected)
    # 答えは一次式（自由変数 x を含む＝定数に退化していない）。
    assert sympy.Symbol("x") in sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.compute_substitution（C1 g1 文字式・代入と式の値）— P2
# ---------------------------------------------------------------------------
def test_substitute_positive_lv1_construct():
    ctx = _make_ctx("math.g1_l16.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "substitute_positive"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_value", "compute_value"]
    # 代入する値は正（Lv1）。
    assert int(mr.params["subs_str"].split("=")[1]) > 0
    # 答えは定数（自由変数なし）。
    assert not sympy.sympify(sq.answer.srepr).free_symbols


def test_substitute_signed_lv2_construct():
    ctx = _make_ctx("math.g1_l16.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "substitute_signed"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "substitute_with_parentheses", "evaluate_powers", "compute_value",
    ]
    # 代入する値は負（Lv2）で、式は累乗を含む。
    assert int(mr.params["subs_str"].split("=")[1]) < 0
    assert "²" in mr.given["expression"]


_SUBSTITUTION_CELLS = [
    ("math.g1_l16.calculation", 1), ("math.g1_l16.calculation", 2),
]


@pytest.mark.parametrize("family,level", _SUBSTITUTION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_substitution_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_substitution")
    sol = solver(mr.params["expr_str"], mr.params["subs_str"], mr.params["mode"])
    # 独立ソルバの答えが recipe の答えと一致し、かつ代入評価に等しい。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    var_s, val_s = mr.params["subs_str"].split("=")
    expected = sympy.sympify(mr.params["expr_str"]).subs(
        sympy.Symbol(var_s.strip()), sympy.Integer(int(val_s))
    )
    assert sol.answer.srepr == sympy.srepr(expected)
    # 答えは定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.compute_notation（C1 g1 文字式・乗法/除法の表し方のきまり）— P2
# ---------------------------------------------------------------------------
def test_notation_product_basic_l13_lv1_construct():
    ctx = _make_ctx("math.g1_l13.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_product_basic"
    sq = mr.sub_questions[0]
    assert sq.asked == "simplified_expr"
    assert [s.op for s in sq.steps] == ["apply_product_rule"]
    assert "×" in mr.given["expression"]  # 未簡約（× を明示）
    assert sympy.sympify(sq.answer.srepr).free_symbols  # 答えは式（文字を含む）


def test_notation_product_powers_l13_lv2_construct():
    ctx = _make_ctx("math.g1_l13.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_product_powers"
    assert [s.op for s in mr.sub_questions[0].steps] == ["apply_product_rule", "combine_powers"]


def test_notation_quotient_basic_l14_lv1_construct():
    ctx = _make_ctx("math.g1_l14.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_quotient_basic"
    assert [s.op for s in mr.sub_questions[0].steps] == ["rewrite_as_fraction"]
    assert "÷" in mr.given["expression"]  # 除法を明示


def test_notation_quotient_mixed_l14_lv2_construct():
    ctx = _make_ctx("math.g1_l14.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_quotient_mixed"
    assert [s.op for s in mr.sub_questions[0].steps] == ["collect_numerator", "rewrite_as_fraction"]
    assert "×" in mr.given["expression"] and "÷" in mr.given["expression"]  # 乗除混合


_NOTATION_CELLS = [
    ("math.g1_l13.calculation", 1), ("math.g1_l13.calculation", 2),
    ("math.g1_l14.calculation", 1), ("math.g1_l14.calculation", 2),
]


@pytest.mark.parametrize("family,level", _NOTATION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_notation_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.simplify_notation")
    sol = solver(mr.params["expr_str"], mr.params["mode"])
    # 独立ソルバの答えが recipe の答えと一致し、かつ与式の正準化に等しい。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.sympify(mr.params["expr_str"]))
    # 答えは式（自由変数を含む＝定数に退化していない）。
    assert sympy.sympify(sol.answer.srepr).free_symbols
    # 答えの表示が与式に部分文字列として漏れない（記号 × ÷ の有無で構造的に非漏洩）。
    assert sol.answer.display.replace(" ", "") not in mr.given["expression"].replace(" ", "")


# ---------------------------------------------------------------------------
# math.term_recall / math.verify_equation_solution（C1 g1 数と式 knowledge）— P2
# ---------------------------------------------------------------------------
def test_letter_term_recall_l17_lv1_construct():
    ctx = _make_ctx("math.g1_l17.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "letter_term_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert [s.op for s in sq.steps] == ["identify_description", "name_concept"]


def test_equation_term_recall_l21_lv1_construct():
    ctx = _make_ctx("math.g1_l21.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equation_term_recall"
    assert [s.op for s in mr.sub_questions[0].steps] == ["identify_description", "name_concept"]


def test_verify_equation_solution_l21_lv2_construct():
    ctx = _make_ctx("math.g1_l21.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equation_verify_solution"
    assert [s.op for s in mr.sub_questions[0].steps] == ["substitute_candidate", "judge_solution"]


def test_number_term_recall_l2_lv1_construct():
    ctx = _make_ctx("math.g1_l2.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_term_recall"
    assert [s.op for s in mr.sub_questions[0].steps] == ["identify_description", "name_concept"]


def test_compare_signed_numbers_l2_lv2_construct():
    ctx = _make_ctx("math.g1_l2.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_compare_magnitude"
    assert [s.op for s in mr.sub_questions[0].steps] == ["compare_on_number_line", "judge_larger"]
    # 少なくとも一方は負（「負の数を含む大小」）。
    assert min(int(mr.params["a"]), int(mr.params["b"])) < 0


def test_inequality_symbol_recall_l20_lv1_construct():
    ctx = _make_ctx("math.g1_l20.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "inequality_symbol_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert [s.op for s in sq.steps] == ["identify_description", "name_concept"]
    # 答えは不等号記号（≧ ≦ < >）のいずれか＝数字トークンを含まない。
    assert sq.answer.correct in {"≧", "≦", "<", ">"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)


def test_number_set_term_recall_l10_lv1_construct():
    ctx = _make_ctx("math.g1_l10.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_set_term_recall"
    assert mr.params["concept"] in {"natural_number", "integer"}
    assert mr.sub_questions[0].answer.correct in {"自然数", "整数"}
    assert [s.op for s in mr.sub_questions[0].steps] == ["identify_description", "name_concept"]


def test_judge_set_closure_l10_lv2_construct():
    ctx = _make_ctx("math.g1_l10.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_set_closure"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"閉じている", "閉じていない"}
    assert [s.op for s in sq.steps] == ["check_operation_result", "judge_closure"]


@pytest.mark.parametrize("seed", range(100))
def test_judge_set_closure_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l10.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_set_closure")
    sol = solver(mr.params["number_set"], mr.params["operation"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 自然数の減法・除法／整数の除法は閉じていない。それ以外は閉じている。
    s, o = mr.params["number_set"], mr.params["operation"]
    not_closed = (s == "natural" and o in {"sub", "div"}) or (s == "integer" and o == "div")
    assert sol.answer.correct == ("閉じていない" if not_closed else "閉じている")
    assert not any(ch.isdigit() for ch in sol.answer.correct)


def test_power_term_recall_l7_lv1_construct():
    ctx = _make_ctx("math.g1_l7.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "power_term_recall"
    assert mr.sub_questions[0].answer.correct in {"指数", "底", "累乗"}
    assert [s.op for s in mr.sub_questions[0].steps] == ["identify_description", "name_concept"]


def test_laws_term_recall_l9_lv1_construct():
    ctx = _make_ctx("math.g1_l9.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "laws_term_recall"
    assert mr.sub_questions[0].answer.correct in {"交換法則", "結合法則", "分配法則"}


def test_prime_concepts_term_recall_l11_lv1_construct():
    ctx = _make_ctx("math.g1_l11.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "prime_concepts_term_recall"
    assert mr.sub_questions[0].answer.correct in {"素数", "合成数", "素因数"}


def test_approximation_term_recall_l60_lv1_construct():
    ctx = _make_ctx("math.g1_l60.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "approximation_term_recall"
    assert mr.sub_questions[0].answer.correct in {"近似値", "誤差", "有効数字"}


_TERM_RECALL_CELLS = [
    ("math.g1_l17.knowledge", 1),
    ("math.g1_l19.knowledge", 1),
    ("math.g1_l21.knowledge", 1),
    ("math.g1_l2.knowledge", 1),
    ("math.g1_l20.knowledge", 1),
    ("math.g1_l10.knowledge", 1),
    ("math.g1_l7.knowledge", 1),
    ("math.g1_l9.knowledge", 1),
    ("math.g1_l11.knowledge", 1),
    ("math.g1_l60.knowledge", 1),
    # C3 g3 用語想起
    ("math.g3_l14.knowledge", 1),
    ("math.g3_l16.knowledge", 1),
    ("math.g3_l22.knowledge", 1),
    ("math.g3_l24.knowledge", 1),
    ("math.g3_l26.knowledge", 1),
    # C4 g1 比例・反比例（用語想起）
    ("math.g1_l28.knowledge", 1),
    ("math.g1_l29.knowledge", 1),
    ("math.g1_l33.knowledge", 1),
    # C12 確率（用語想起）
    ("math.g1_l59.knowledge", 1),
    ("math.g2_l51.knowledge", 1),
    # C11 データ・統計（用語想起）
    ("math.g1_l54.knowledge", 1),
    ("math.g1_l55.knowledge", 1),
    ("math.g1_l56.knowledge", 1),
    ("math.g1_l57.knowledge", 1),
    ("math.g2_l55.knowledge", 1),
    ("math.g2_l56.knowledge", 1),
    ("math.g3_l57.knowledge", 1),
    ("math.g3_l58.knowledge", 1),
    ("math.g1_l30.knowledge", 1),
    # C7 g1 平面図形（用語想起）
    ("math.g1_l37.knowledge", 1),
    ("math.g1_l43.knowledge", 1),
    ("math.g1_l44.knowledge", 2),
    ("math.g1_l45.knowledge", 1),
    # C9 g2 平行と合同（用語想起）
    ("math.g2_l31.knowledge", 1),
    ("math.g2_l37.knowledge", 2),
    ("math.g2_l38.knowledge", 1),
    # C10 g3 相似・円・三平方（用語想起）
    ("math.g3_l39.knowledge", 1),
    # C8 g1 空間図形（用語想起）
    ("math.g1_l47.knowledge", 1),
    ("math.g1_l48.knowledge", 1),
    ("math.g1_l49.knowledge", 1),
    ("math.g1_l50.knowledge", 1),
]


@pytest.mark.parametrize("family,level", _TERM_RECALL_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_term_recall_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.term_recall_definition")
    sol = solver(mr.params["concept"], mr.params["domain"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id
    # 答えはテキスト（数字トークンなし）＝G-Q5t 素通り。
    assert not any(ch.isdigit() for ch in sol.answer.correct)
    assert mr.sub_questions[0].answer.correct not in mr.sub_questions[0].answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_verify_equation_solution_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l21.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.verify_equation_solution")
    sol = solver(mr.params["equation_str"], mr.params["value"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 構成の真偽ビットと判定が一致する。
    expected = "解である" if mr.params["is_solution"] == "True" else "解ではない"
    assert sol.answer.correct == expected


@pytest.mark.parametrize("seed", range(100))
def test_compare_signed_numbers_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l2.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.compare_signed_numbers")
    sol = solver(mr.params["a"], mr.params["b"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 大きいほうが答え（sympy で独立検証）。
    a, b = sympy.Integer(int(mr.params["a"])), sympy.Integer(int(mr.params["b"]))
    larger = a if a > b else b
    assert sympy.sympify(sol.answer.correct) == larger


def test_classify_number_sign_l1_lv1_construct():
    ctx = _make_ctx("math.g1_l1.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_classify_sign"
    sq = mr.sub_questions[0]
    assert sq.answer.kind == "choice"
    assert sq.answer.correct in {"正の数", "負の数"}
    assert [s.op for s in sq.steps] == ["read_number_sign", "classify_positive_negative"]
    assert int(mr.params["value"]) != 0


def test_represent_opposite_quantity_l1_lv2_construct():
    ctx = _make_ctx("math.g1_l1.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "number_opposite_quantity"
    sq = mr.sub_questions[0]
    assert sq.answer.kind == "choice"
    assert [s.op for s in sq.steps] == ["identify_base_direction", "assign_opposite_sign"]
    # 反対の向き＝正しい選択肢は負（given の正数と一致しない）。
    m = int(mr.params["magnitude"])
    assert sq.answer.correct == str(-m)
    assert sq.answer.distractors == [f"+{m}"]


@pytest.mark.parametrize("seed", range(100))
def test_classify_number_sign_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l1.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.classify_number_sign")
    sol = solver(mr.params["value"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 符号と分類が sympy で一致。
    v = sympy.Integer(int(mr.params["value"]))
    assert sol.answer.correct == ("正の数" if v > 0 else "負の数")
    assert not any(ch.isdigit() for ch in sol.answer.correct)


@pytest.mark.parametrize("seed", range(100))
def test_represent_opposite_quantity_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l1.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.represent_opposite_quantity")
    sol = solver(mr.params["positive_label"], mr.params["asked_label"], mr.params["magnitude"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 反対の向きなので正しい選択肢は負（絶対値＝magnitude）。
    assert sol.answer.correct == str(-int(mr.params["magnitude"]))
    assert sol.answer.correct not in sol.answer.distractors


def test_recall_rule_transposition_l22_lv1_construct():
    ctx = _make_ctx("math.g1_l22.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "transposition_rule_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.kind == "choice"
    assert [s.op for s in sq.steps] == ["read_rule_context", "recall_correct_rule"]
    assert mr.params["concept"] in {"definition", "sign_reason"}


def test_recall_rule_addition_sign_l3_lv1_construct():
    ctx = _make_ctx("math.g1_l3.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "addition_sign_rule_recall"
    assert mr.params["concept"] in {"same_sign", "different_sign"}
    assert [s.op for s in mr.sub_questions[0].steps] == ["read_rule_context", "recall_correct_rule"]


def test_recall_rule_subtraction_l4_lv1_construct():
    ctx = _make_ctx("math.g1_l4.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "subtraction_rule_recall"
    assert mr.params["concept"] == "to_addition"


def test_recall_rule_term_in_sum_l5_lv1_construct():
    ctx = _make_ctx("math.g1_l5.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "term_in_sum_rule_recall"
    assert mr.params["concept"] == "definition"


def test_recall_rule_speed_relation_l15_lv1_construct():
    ctx = _make_ctx("math.g1_l15.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "speed_relation_rule_recall"
    assert mr.params["concept"] in {"speed", "distance", "time"}
    assert "÷" in mr.sub_questions[0].answer.correct or "×" in mr.sub_questions[0].answer.correct


def test_recall_rule_letter_meaning_l12_lv1_construct():
    ctx = _make_ctx("math.g1_l12.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "letter_meaning_rule_recall"
    assert mr.params["concept"] == "benefit"


def test_recall_rule_product_sign_l6_lv1_construct():
    ctx = _make_ctx("math.g1_l6.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "product_sign_rule_recall"
    assert mr.params["concept"] in {"even_count", "odd_count"}


def test_recall_rule_reciprocal_l8_lv1_construct():
    ctx = _make_ctx("math.g1_l8.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "reciprocal_rule_recall"
    assert mr.params["concept"] == "division_rule"


def test_recall_rule_notation_product_l13_lv1_construct():
    ctx = _make_ctx("math.g1_l13.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_product_rule_recall"
    assert mr.params["concept"] in {"omit_times", "power"}


def test_recall_rule_notation_quotient_l14_lv1_construct():
    ctx = _make_ctx("math.g1_l14.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "notation_quotient_rule_recall"
    assert mr.params["concept"] == "as_fraction"


def test_term_recall_quadratic_coefficient_l26_lv1_construct():
    ctx = _make_ctx("math.g3_l26.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_coefficient_term_recall"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"a", "b", "c"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)


def test_recall_rule_multiplication_formula_l3_lv1_construct():
    ctx = _make_ctx("math.g3_l3.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "multiplication_formula_rule_recall"
    assert mr.params["concept"] in {
        "general_form", "perfect_square_form", "diff_of_squares_form",
    }


def test_recall_rule_sqrt_square_meaning_l14_lv2_construct():
    ctx = _make_ctx("math.g3_l14.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sqrt_square_meaning_rule_recall"
    assert mr.params["concept"] == "abs_value_rule"


def test_recall_rule_quadratic_solving_method_l28_lv2_construct():
    ctx = _make_ctx("math.g3_l28.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_solving_method_rule_recall"
    assert mr.params["concept"] in {"factoring_suitable", "formula_suitable"}


_RULE_RECALL_CELLS = [
    ("math.g1_l22.knowledge", 1),
    ("math.g1_l3.knowledge", 1),
    ("math.g1_l4.knowledge", 1),
    ("math.g1_l5.knowledge", 1),
    ("math.g1_l15.knowledge", 1),
    ("math.g1_l12.knowledge", 1),
    ("math.g1_l6.knowledge", 1),
    ("math.g1_l8.knowledge", 1),
    ("math.g1_l13.knowledge", 1),
    ("math.g1_l14.knowledge", 1),
    # C3 g3 規則・意味の想起
    ("math.g3_l2.knowledge", 1),
    ("math.g3_l7.knowledge", 1),
    ("math.g3_l15.knowledge", 1),
    ("math.g3_l3.knowledge", 1),
    ("math.g3_l14.knowledge", 2),
    ("math.g3_l28.knowledge", 2),
    # C12 確率（規則・意味の想起）
    ("math.g2_l54.knowledge", 1),
    # C9 g2 平行と合同（規則・意味の想起）
    ("math.g2_l32.knowledge", 1),
    ("math.g2_l33.knowledge", 1),
    ("math.g2_l34.knowledge", 1),
    ("math.g2_l35.knowledge", 1),
    ("math.g2_l37.knowledge", 1),
    ("math.g2_l41.knowledge", 1),
    ("math.g2_l42.knowledge", 1),
    ("math.g2_l43.knowledge", 1),
    ("math.g2_l44.knowledge", 1),
    ("math.g2_l46.knowledge", 1),
    ("math.g2_l47.knowledge", 1),
    ("math.g2_l49.knowledge", 1),
    ("math.g2_l50.knowledge", 1),
    ("math.g3_l51.knowledge", 1),
    ("math.g3_l52.knowledge", 1),
    ("math.g3_l40.knowledge", 1),
    ("math.g3_l42.knowledge", 1),
    ("math.g3_l43.knowledge", 1),
    ("math.g3_l44.knowledge", 1),
    ("math.g3_l45.knowledge", 1),
    ("math.g3_l46.knowledge", 1),
    ("math.g3_l47.knowledge", 1),
    ("math.g3_l48.knowledge", 1),
    ("math.g3_l50.knowledge", 1),
    # C8 g1 空間図形（球の公式の想起）
    ("math.g1_l53.knowledge", 1),
]


@pytest.mark.parametrize("family,level", _RULE_RECALL_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_recall_rule_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.recall_rule_statement")
    # labels は checker が渡すのと同じ経路（点名を使う規則は選択肢の記号を問題文に
    # 合わせる。渡さないと「三角形KFDで…」と問うて「ADとABの比」と答えることになる）。
    sol = solver(mr.params["topic"], mr.params["concept"], mr.params.get("labels"))
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id
    # 答えは規則の文（数字トークンなし）＝G-Q5t 素通り。
    assert not any(ch.isdigit() for ch in sol.answer.correct)
    assert sol.answer.correct not in sol.answer.distractors


# ---------------------------------------------------------------------------
# math.classify_rational_irrational（C3 g3_l16.knowledge Lv2 有理数/無理数の分類）
# ---------------------------------------------------------------------------
def test_classify_rational_irrational_lv2_construct():
    ctx = _make_ctx("math.g3_l16.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "classify_rational_irrational"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"有理数", "無理数"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert mr.params["kind"] in {"rational", "irrational"}


@pytest.mark.parametrize("seed", range(100))
def test_classify_rational_irrational_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l16.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.classify_rational_irrational")
    sol = solver(mr.params["value_str"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    expected = "有理数" if mr.params["kind"] == "rational" else "無理数"
    assert sol.answer.correct == expected


# ---------------------------------------------------------------------------
# math.verify_quadratic_solution（C3 g3_l24.knowledge Lv2 解の判定）
# ---------------------------------------------------------------------------
def test_verify_quadratic_solution_lv2_construct():
    ctx = _make_ctx("math.g3_l24.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "verify_quadratic_solution"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"解である", "解ではない"}
    assert [s.op for s in sq.steps] == ["substitute_candidate", "judge_solution"]


@pytest.mark.parametrize("seed", range(100))
def test_verify_quadratic_solution_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l24.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.verify_quadratic_solution")
    sol = solver(mr.params["eq_str"], mr.params["value"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 恒真: 候補値を左辺に代入した値が0かどうかで判定と一致する。
    lhs_s, rhs_s = mr.params["eq_str"].split("=")
    v = sympy.Rational(int(mr.params["value"]))
    lhs_v = sympy.sympify(lhs_s).subs(sympy.Symbol("x"), v)
    rhs_v = sympy.sympify(rhs_s).subs(sympy.Symbol("x"), v)
    expected = "解である" if sympy.simplify(lhs_v - rhs_v) == 0 else "解ではない"
    assert sol.answer.correct == expected


# ---------------------------------------------------------------------------
# math.compute_linear_equation（C1 g1 一次方程式・解法）— P2
# ---------------------------------------------------------------------------
def test_equation_equality_add_lv1_construct():
    ctx = _make_ctx("math.g1_l21.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equality_add"
    sq = mr.sub_questions[0]
    assert sq.asked == "solution"
    assert [s.op for s in sq.steps] == ["subtract_constant_both_sides", "state_solution"]
    assert sq.answer.display.startswith("x = ")


def test_equation_equality_multi_lv2_construct():
    ctx = _make_ctx("math.g1_l21.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equality_multi"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "subtract_constant_both_sides", "divide_both_sides",
    ]


def test_equation_transpose_constant_lv1_construct():
    ctx = _make_ctx("math.g1_l22.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "transpose_constant"
    assert [s.op for s in mr.sub_questions[0].steps] == ["transpose_constant", "state_solution"]


def test_equation_transpose_both_lv2_construct():
    ctx = _make_ctx("math.g1_l22.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "transpose_both"
    assert [s.op for s in mr.sub_questions[0].steps] == ["transpose_terms", "combine_and_divide"]
    # 両辺に文字がある（右辺にも x）。
    assert "x" in mr.given["equation"].split("=")[1]


_EQUATION_CELLS = [
    ("math.g1_l21.calculation", 1), ("math.g1_l21.calculation", 2),
    ("math.g1_l22.calculation", 1), ("math.g1_l22.calculation", 2),
]


@pytest.mark.parametrize("family,level", _EQUATION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_linear_equation_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_linear_equation")
    sol = solver(mr.params["equation_str"], mr.params["mode"])
    # 独立ソルバの答えが recipe の答えと一致する。
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 解が方程式を満たす（sympy で両辺一致）。
    lhs_s, rhs_s = mr.params["equation_str"].split("=")
    x0 = sympy.Rational(sympy.sympify(sol.answer.srepr))
    lhs_v = sympy.sympify(lhs_s).subs(sympy.Symbol("x"), x0)
    rhs_v = sympy.sympify(rhs_s).subs(sympy.Symbol("x"), x0)
    assert sympy.simplify(lhs_v - rhs_v) == 0
    # 答えは定数（自由変数を含まない）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols


# ---------------------------------------------------------------------------
# math.compute_linear_equation の利用系（C1 g1 一次方程式 l23/l25/l26/l27）— P2
# ---------------------------------------------------------------------------
def test_equation_expand_parens_l23_lv2_construct():
    ctx = _make_ctx("math.g1_l23.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "expand_parens"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "expand_parentheses", "transpose_and_solve",
    ]
    assert "(" in mr.given["equation"]  # かっこを含む


def test_equation_word_price_l25_lv1_construct():
    ctx = _make_ctx("math.g1_l25.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "word_price_equation"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "expand_parentheses", "transpose_and_solve",
    ]


def test_equation_shortage_l26_lv1_construct():
    ctx = _make_ctx("math.g1_l26.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "shortage_equation"
    # 過不足＝両辺に文字（transpose_both を流用）。
    assert [s.op for s in mr.sub_questions[0].steps] == ["transpose_terms", "combine_and_divide"]
    assert "x" in mr.given["equation"].split("=")[1]


def test_equation_speed_fraction_l27_lv2_construct():
    ctx = _make_ctx("math.g1_l27.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "speed_fraction_equation"
    assert [s.op for s in mr.sub_questions[0].steps] == ["clear_denominators", "combine_and_solve"]
    assert "/" in mr.given["equation"]  # 分数係数


def test_equation_clear_denominators_two_l23_lv3_construct():
    ctx = _make_ctx("math.g1_l23.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "clear_denominators_two"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "clear_denominators", "expand_and_transpose", "solve",
    ]
    assert "/" in mr.given["equation"]  # かっこ＋分数


def test_equation_proportion_l24_lv1_construct():
    ctx = _make_ctx("math.g1_l24.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "proportion_cross_multiply"
    assert [s.op for s in mr.sub_questions[0].steps] == ["cross_multiply", "solve_proportion"]
    assert ":" in mr.given["equation"]  # 表示は比例式
    # 表示（比例式）と solver 用の式（クロス乗算した線形式）は別物。
    assert ":" not in mr.params["equation_str"]


def test_equation_proportion_expand_l24_lv2_construct():
    ctx = _make_ctx("math.g1_l24.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "proportion_cross_multiply_expand"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "cross_multiply", "expand_parentheses", "transpose_and_solve",
    ]
    assert ":" in mr.given["equation"] and "(" in mr.given["equation"]  # (x+p):b=c:d


_EQUATION_WORD_CELLS = [
    ("math.g1_l23.calculation", 2),
    ("math.g1_l23.calculation", 3),
    ("math.g1_l24.calculation", 1),
    ("math.g1_l24.calculation", 2),
    ("math.g1_l25.calculation", 1),
    ("math.g1_l26.calculation", 1),
    ("math.g1_l27.calculation", 2),
]


@pytest.mark.parametrize("family,level", _EQUATION_WORD_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_compute_linear_equation_word_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_linear_equation")
    sol = solver(mr.params["equation_str"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 解が方程式を満たす。
    lhs_s, rhs_s = mr.params["equation_str"].split("=")
    x0 = sympy.Rational(sympy.sympify(sol.answer.srepr))
    lhs_v = sympy.sympify(lhs_s).subs(sympy.Symbol("x"), x0)
    rhs_v = sympy.sympify(rhs_s).subs(sympy.Symbol("x"), x0)
    assert sympy.simplify(lhs_v - rhs_v) == 0
    # 答えは定数（整数）。
    assert not sympy.sympify(sol.answer.srepr).free_symbols
    assert sympy.sympify(sol.answer.srepr).is_Integer


# ---------------------------------------------------------------------------
# C6 g3 二次関数 y=ax²（非visual13セル）
# ---------------------------------------------------------------------------
def test_evaluate_quadratic_function_lv1_construct():
    ctx = _make_ctx("math.g3_l32.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_function_evaluate"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_x", "compute_y"]
    assert mr.params["a"] != 0 and mr.params["x"] != 0
    expected = sympy.Integer(mr.params["a"]) * sympy.Integer(mr.params["x"]) ** 2
    assert (expected - sympy.sympify(sq.answer.srepr)).equals(0)


@pytest.mark.parametrize("seed", range(100))
def test_evaluate_quadratic_function_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l32.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_quadratic_function")
    sol = solver(mr.params["a"], mr.params["x"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_quadratic_function_terms_knowledge_lv1_construct():
    ctx = _make_ctx("math.g3_l32.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_function_terms_term_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.correct == "比例定数"
    assert not any(ch.isdigit() for ch in sq.answer.correct)


def test_quadratic_function_form_knowledge_lv2_construct():
    ctx = _make_ctx("math.g3_l32.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_function_form_rule_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    # level_sep: Lv1 用語想起（identify_description/name_concept）とは異なる op 列。
    assert [s.op for s in sq.steps] == ["read_rule_context", "recall_correct_rule"]
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


def test_y_range_over_quadratic_domain_lv2_construct():
    ctx = _make_ctx("math.g3_l34.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_y_range_one_sided"
    sq = mr.sub_questions[0]
    assert sq.asked == "domain_range"
    assert [s.op for s in sq.steps] == ["evaluate_endpoints", "order_by_magnitude"]
    assert mr.params["x_lo"] * mr.params["x_hi"] >= 0  # 0の片側（またがない）


def test_y_range_over_quadratic_domain_lv3_construct():
    ctx = _make_ctx("math.g3_l34.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_y_range_straddles_zero"
    sq = mr.sub_questions[0]
    # level_sep: Lv2 とは異なる op 列（頂点を含むかの吟味が追加）。
    assert [s.op for s in sq.steps] == [
        "check_domain_contains_vertex", "evaluate_endpoints", "combine_with_vertex",
    ]
    assert mr.params["x_lo"] < 0 < mr.params["x_hi"]


_QUADRATIC_Y_RANGE_CELLS = [
    ("math.g3_l34.find_value", 2), ("math.g3_l34.find_value", 3),
]


@pytest.mark.parametrize("family,level", _QUADRATIC_Y_RANGE_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_y_range_over_quadratic_domain_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.y_range_over_quadratic_domain")
    sol = solver(mr.params["a"], mr.params["x_lo"], mr.params["x_hi"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_rate_of_change_quadratic_lv2_construct():
    ctx = _make_ctx("math.g3_l35.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_roc_forward"
    sq = mr.sub_questions[0]
    assert sq.asked == "rate_of_change"
    assert [s.op for s in sq.steps] == ["evaluate_endpoints_roc", "compute_rate_of_change"]
    a, x1, x2 = mr.params["a"], mr.params["x1"], mr.params["x2"]
    expected = sympy.Integer(a) * (x1 + x2)  # y=ax² の変化の割合 = a(x1+x2)
    assert (expected - sympy.sympify(sq.answer.srepr)).equals(0)


def test_rate_of_change_quadratic_lv3_construct():
    ctx = _make_ctx("math.g3_l35.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_roc_solve_for_a"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv2（順算）とは異なる op 列（逆算）。
    assert [s.op for s in sq.steps] == ["set_up_rate_equation", "solve_for_coefficient"]
    assert mr.params["x1"] + mr.params["x2"] != 0


_QUADRATIC_ROC_CELLS = [
    ("math.g3_l35.find_value", 2), ("math.g3_l35.find_value", 3),
]


@pytest.mark.parametrize("family,level", _QUADRATIC_ROC_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_rate_of_change_quadratic_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.rate_of_change_quadratic")
    sol = solver(mr.params["a"], mr.params["x1"], mr.params["x2"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_quadratic_roc_property_knowledge_lv1_construct():
    ctx = _make_ctx("math.g3_l35.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_roc_property_rule_recall"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


def test_intersection_parabola_line_lv2_construct():
    ctx = _make_ctx("math.g3_l37.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_intersection_find"
    sq = mr.sub_questions[0]
    assert sq.asked == "intersection"
    assert [s.op for s in sq.steps] == ["set_up_equation", "solve_for_x", "compute_y"]
    assert mr.params["b"] != 0  # O,A,B が同一直線上にならない（構成的に保証）


def test_intersection_parabola_line_lv3_construct():
    ctx = _make_ctx("math.g3_l37.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_intersection_segment_area"
    sq = mr.sub_questions[0]
    assert sq.asked == "area"
    assert [s.op for s in sq.steps] == [
        "set_up_equation", "solve_for_x", "compute_y",
        "compute_segment_length", "compute_triangle_area",
    ]


def test_intersection_parabola_line_lv4_construct():
    ctx = _make_ctx("math.g3_l37.find_value", 4)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_intersection_equal_area_point"
    sq = mr.sub_questions[0]
    assert sq.asked == "coordinate"
    assert [s.op for s in sq.steps] == [
        "set_up_equation", "solve_for_x", "compute_y",
        "compute_triangle_area", "solve_for_equal_area_point",
    ]


_QUADRATIC_INTERSECTION_CELLS = [
    ("math.g3_l37.find_value", 2), ("math.g3_l37.find_value", 3), ("math.g3_l37.find_value", 4),
]


@pytest.mark.parametrize("family,level", _QUADRATIC_INTERSECTION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_intersection_parabola_line_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.intersection_parabola_line")
    sol = solver(mr.params["a"], mr.params["m"], mr.params["b"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_solve_quadratic_motion_area_lv2_construct():
    ctx = _make_ctx("math.g3_l38.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_motion_area_single_segment"
    sq = mr.sub_questions[0]
    assert sq.asked == "area"
    assert [s.op for s in sq.steps] == ["locate_point_p", "compute_triangle_area"]
    s, d = mr.params["s"], mr.params["d"]
    assert 0 < d < s
    # 三角形ABPの面積 = s・d÷2（P=(s,d)・底辺AB=s・高さ=d）。
    assert sympy.sympify(sq.answer.srepr) == sympy.Rational(s * d, 2)


def test_solve_quadratic_motion_area_lv3_construct():
    ctx = _make_ctx("math.g3_l38.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quadratic_motion_area_case_split"
    sq = mr.sub_questions[0]
    # level_sep: Lv2 とは異なる op 列（どの辺の上にいるかの判断が追加）。
    assert [s.op for s in sq.steps] == [
        "determine_which_segment", "locate_point_p", "compute_triangle_area",
    ]
    s, d = mr.params["s"], mr.params["d"]
    assert 0 < d < 2 * s


_QUADRATIC_MOTION_CELLS = [
    ("math.g3_l38.find_value", 2), ("math.g3_l38.find_value", 3),
]


@pytest.mark.parametrize("family,level", _QUADRATIC_MOTION_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_solve_quadratic_motion_area_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_quadratic_motion_area")
    sol = solver(mr.params["s"], mr.params["d"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    val = sympy.sympify(sol.answer.srepr)
    assert not val.free_symbols
    assert val >= 0


# ---------------------------------------------------------------------------
# C4（P3・g1 比例・反比例）— 非 visual 10 セル
# ---------------------------------------------------------------------------
_DIRECT_PROPORTION_EVALUATE_CELLS = [
    ("math.g1_l29.calculation", 1),
    ("math.g1_l29.calculation", 2),
]


def test_direct_proportion_evaluate_lv1_construct():
    ctx = _make_ctx("math.g1_l29.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "direct_proportion_evaluate_basic"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_x", "evaluate"]


def test_direct_proportion_evaluate_lv2_different_ops():
    ctx = _make_ctx("math.g1_l29.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "direct_proportion_evaluate_signed"
    # level_sep: Lv2 は符号確認の1手順が増え op 列が Lv1 と相異する。
    assert [s.op for s in mr.sub_questions[0].steps] == ["check_signs", "substitute_x", "evaluate"]


@pytest.mark.parametrize("family,level", _DIRECT_PROPORTION_EVALUATE_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_direct_proportion_evaluate_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_direct_proportion")
    sol = solver(mr.params["a"], mr.params["x0"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: y = a * x0
    a = sympy.sympify(mr.params["a"])
    x0 = sympy.sympify(mr.params["x0"])
    assert sympy.sympify(sol.answer.srepr) == a * x0


_INVERSE_PROPORTION_EVALUATE_CELLS = [
    ("math.g1_l33.calculation", 1),
    ("math.g1_l33.calculation", 2),
]


def test_inverse_proportion_evaluate_lv1_construct():
    ctx = _make_ctx("math.g1_l33.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "inverse_proportion_evaluate_forward"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["substitute_x", "evaluate"]


def test_inverse_proportion_evaluate_lv2_different_ops():
    ctx = _make_ctx("math.g1_l33.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "inverse_proportion_evaluate_backward"
    # level_sep: Lv2 は y から x を逆算するため op 列が Lv1 と相異する。
    assert [s.op for s in mr.sub_questions[0].steps] == ["substitute_y", "solve_for_x"]


@pytest.mark.parametrize("family,level", _INVERSE_PROPORTION_EVALUATE_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_inverse_proportion_evaluate_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.evaluate_inverse_proportion")
    sol = solver(mr.params["a"], mr.params["known"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 恒真: forward は y=a/known、backward は x=a/known（どちらも a/known で表せる）。
    a = sympy.sympify(mr.params["a"])
    known = sympy.sympify(mr.params["known"])
    assert sympy.sympify(sol.answer.srepr) == a / known


def test_judge_functional_relation_lv2_construct():
    ctx = _make_ctx("math.g1_l28.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_functional_relation"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"yはxの関数であるといえる", "yはxの関数であるとはいえない"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)


@pytest.mark.parametrize("seed", range(100))
def test_judge_functional_relation_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l28.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_functional_relation")
    sol = solver(mr.params["is_functional"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    expected = (
        "yはxの関数であるといえる" if mr.params["is_functional"] == "True"
        else "yはxの関数であるとはいえない"
    )
    assert sol.answer.correct == expected


def test_judge_direct_proportion_table_lv2_construct():
    ctx = _make_ctx("math.g1_l29.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_direct_proportion_table"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"比例するといえる", "比例するとはいえない"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)


@pytest.mark.parametrize("seed", range(100))
def test_judge_direct_proportion_table_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l29.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_direct_proportion_table")
    sol = solver(mr.params["xs"], mr.params["ys"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 恒真: 商 y/x の一定性と is_proportional が一致する。
    xs = [sympy.sympify(v) for v in mr.params["xs"]]
    ys = [sympy.sympify(v) for v in mr.params["ys"]]
    ratios = [ys[i] / xs[i] for i in range(len(xs))]
    expected_proportional = all(r == ratios[0] for r in ratios)
    assert expected_proportional == (mr.params["is_proportional"] == "True")


def test_judge_inverse_proportion_table_lv2_construct():
    ctx = _make_ctx("math.g1_l33.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_inverse_proportion_table"
    sq = mr.sub_questions[0]
    assert sq.answer.correct in {"反比例するといえる", "反比例するとはいえない"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)


@pytest.mark.parametrize("seed", range(100))
def test_judge_inverse_proportion_table_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l33.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_inverse_proportion_table")
    sol = solver(mr.params["xs"], mr.params["ys"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    # 恒真: 積 xy の一定性と is_inverse が一致する。
    xs = [sympy.sympify(v) for v in mr.params["xs"]]
    ys = [sympy.sympify(v) for v in mr.params["ys"]]
    products = [xs[i] * ys[i] for i in range(len(xs))]
    expected_inverse = all(p == products[0] for p in products)
    assert expected_inverse == (mr.params["is_inverse"] == "True")


# ---------------------------------------------------------------------------
# C12 確率（非visual14セル）
# ---------------------------------------------------------------------------
def test_relative_frequency_g1_lv1_construct():
    ctx = _make_ctx("math.g1_l59.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "relative_frequency_basic"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["divide_occurred_by_total"]
    o, t = mr.params["occurred"], mr.params["total"]
    assert 0 < o < t
    assert sympy.sympify(sq.answer.srepr) == sympy.Rational(o, t)


_RELATIVE_FREQUENCY_CELLS = [
    ("math.g1_l59.calculation", 1), ("math.g2_l51.find_value", 2),
]


@pytest.mark.parametrize("family,level", _RELATIVE_FREQUENCY_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_relative_frequency_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.relative_frequency")
    sol = solver(mr.params["occurred"], mr.params["total"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_interpret_relative_frequency_limit_construct():
    ctx = _make_ctx("math.g1_l59.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "interpret_relative_frequency_limit"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.correct == "その事象の起こる確率"
    assert not any(ch.isdigit() for ch in sq.answer.correct)


def test_probability_single_die_lv1_construct():
    ctx = _make_ctx("math.g2_l51.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_single_die_count"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "enumerate_all_outcomes", "count_favorable", "compute_probability",
    ]
    p_val = sympy.sympify(sq.answer.srepr)
    assert 0 <= p_val <= 1


_PROBABILITY_SINGLE_DIE_CELLS = [
    ("math.g2_l51.find_value", 1), ("math.g2_l52.find_value", 1),
]


@pytest.mark.parametrize("family,level", _PROBABILITY_SINGLE_DIE_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_probability_single_die_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_single_die")
    sol = solver(mr.params["space_name"], mr.params["condition"], mr.params["target"], mr.params["size"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_probability_two_dice_lv3_construct():
    ctx = _make_ctx("math.g2_l52.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_two_dice_count"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "enumerate_all_pairs", "count_favorable_pairs", "compute_probability",
    ]


@pytest.mark.parametrize("seed", range(100))
def test_probability_two_dice_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l52.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_two_dice")
    sol = solver(mr.params["faces"], mr.params["condition"], mr.params["target"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_probability_ordered_selection_construct():
    ctx = _make_ctx("math.g2_l53.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_ordered_selection"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sympy.sympify(sq.answer.srepr) == sympy.Rational(1, mr.params["n"])


@pytest.mark.parametrize("seed", range(100))
def test_probability_ordered_selection_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l53.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_ordered_selection")
    sol = solver(mr.params["n"], mr.params["r"], mr.params["target_index"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_probability_combination_selection_construct():
    ctx = _make_ctx("math.g2_l53.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_combination_selection"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    p_val = sympy.sympify(sq.answer.srepr)
    assert 0 <= p_val <= 1


@pytest.mark.parametrize("seed", range(100))
def test_probability_combination_selection_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l53.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_combination_selection")
    sol = solver(mr.params["counts"], mr.params["r"], mr.params["target_color"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_probability_complement_construct():
    ctx = _make_ctx("math.g2_l54.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_complement"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["subtract_from_one"]
    p_num, p_den = mr.params["p_num"], mr.params["p_den"]
    assert (sympy.Rational(p_num, p_den) + sympy.sympify(sq.answer.srepr) - 1).equals(0)


@pytest.mark.parametrize("seed", range(100))
def test_probability_complement_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l54.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_complement")
    sol = solver(mr.params["p_num"], mr.params["p_den"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_probability_at_least_one_construct():
    ctx = _make_ctx("math.g2_l54.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "probability_at_least_one"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv2（引き算1手順）とは異なる op 列。
    assert [s.op for s in sq.steps] == [
        "compute_single_trial_complement", "compute_complement_probability", "subtract_from_one",
    ]
    p_val = sympy.sympify(sq.answer.srepr)
    assert 0 <= p_val <= 1


@pytest.mark.parametrize("seed", range(100))
def test_probability_at_least_one_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l54.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.probability_at_least_one")
    sol = solver(mr.params["space_size"], mr.params["favorable_size"], mr.params["trials"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_equally_likely_construct():
    ctx = _make_ctx("math.g2_l51.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_equally_likely"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_equally_likely_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l51.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_equally_likely")
    sol = solver(mr.params["is_equally_likely"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C11 データ・統計（度数分布・代表値）: g1_l54〜g1_l57
# ---------------------------------------------------------------------------
def test_frequency_table_value_lv1_construct():
    ctx = _make_ctx("math.g1_l54.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "frequency_table_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert len(mr.params["frequencies"]) == 4


@pytest.mark.parametrize("seed", range(100))
def test_frequency_table_value_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l54.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.frequency_table_value")
    sol = solver(mr.params["class_start"], mr.params["class_width"], mr.params["frequencies"], mr.params["target_index"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_relative_frequency_stats_single_lv1_construct():
    ctx = _make_ctx("math.g1_l55.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "relative_frequency_stats_single"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert 0 < mr.params["occurred"] < mr.params["total"]


@pytest.mark.parametrize("seed", range(100))
def test_relative_frequency_stats_single_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l55.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.relative_frequency")
    sol = solver(mr.params["occurred"], mr.params["total"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_compare_relative_frequency_lv2_construct():
    ctx = _make_ctx("math.g1_l55.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "compare_relative_frequency"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv1（1手順）とは異なる op 列（2手順）。
    assert [s.op for s in sq.steps] == ["compute_relative_frequency_each", "compare_relative_frequency"]


@pytest.mark.parametrize("seed", range(100))
def test_compare_relative_frequency_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l55.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.compare_relative_frequency")
    sol = solver(mr.params["freq_a"], mr.params["total_a"], mr.params["freq_b"], mr.params["total_b"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_cumulative_frequency_value_lv1_construct():
    ctx = _make_ctx("math.g1_l56.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "cumulative_frequency_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["accumulate_frequency"]


@pytest.mark.parametrize("seed", range(100))
def test_cumulative_frequency_value_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l56.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.cumulative_frequency_value")
    sol = solver(mr.params["frequencies"], mr.params["target_index"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_cumulative_relative_frequency_and_complement_lv2_construct():
    ctx = _make_ctx("math.g1_l56.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "cumulative_relative_frequency_and_complement"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv1（累積のみ）とは異なる op 列（累積相対度数→補数%の2段）。
    assert [s.op for s in sq.steps] == ["accumulate_relative_frequency", "compute_complement_percent"]
    assert sum(mr.params["frequencies"]) > 0


@pytest.mark.parametrize("seed", range(100))
def test_cumulative_relative_frequency_and_complement_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l56.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.cumulative_relative_frequency_and_complement")
    sol = solver(mr.params["frequencies"], mr.params["target_index"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_representative_values_raw_lv1_construct():
    ctx = _make_ctx("math.g1_l57.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "representative_values_raw"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["compute_mean", "compute_median", "compute_mode"]


@pytest.mark.parametrize("seed", range(100))
def test_representative_values_raw_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l57.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.representative_values_raw")
    sol = solver(mr.params["data"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_mean_from_grouped_table_lv2_construct():
    ctx = _make_ctx("math.g1_l57.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "mean_from_grouped_table"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv1（生データ3値）とは異なる op 列（階級値の重み付け2段）。
    assert [s.op for s in sq.steps] == ["weight_by_class_value", "divide_by_total"]


@pytest.mark.parametrize("seed", range(100))
def test_mean_from_grouped_table_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l57.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.mean_from_grouped_table")
    sol = solver(mr.params["class_start"], mr.params["class_width"], mr.params["frequencies"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_appropriate_representative_value_construct():
    ctx = _make_ctx("math.g1_l57.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_appropriate_representative_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_appropriate_representative_value_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l57.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_appropriate_representative_value")
    sol = solver(mr.params["has_outliers"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C11 データ・統計（四分位数・箱ひげ図）: g2_l55〜g2_l57
# ---------------------------------------------------------------------------
def test_median_value_lv1_construct():
    ctx = _make_ctx("math.g2_l55.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "median_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert len(mr.params["data"]) % 2 == 1


@pytest.mark.parametrize("seed", range(100))
def test_median_value_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l55.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.median_value")
    sol = solver(mr.params["data"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_quartiles_iqr_lv3_construct():
    ctx = _make_ctx("math.g2_l55.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "quartiles_iqr"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    # level_sep: Lv1（sort_data/compute_median の2段）とは異なる op 列（3段）。
    assert [s.op for s in sq.steps] == ["split_into_halves", "compute_q1_q3", "compute_iqr"]


@pytest.mark.parametrize("seed", range(100))
def test_quartiles_iqr_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l55.calculation", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.quartiles_iqr")
    sol = solver(mr.params["data"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_five_number_summary_lv1_construct():
    ctx = _make_ctx("math.g2_l56.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "five_number_summary"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"


@pytest.mark.parametrize("seed", range(100))
def test_five_number_summary_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l56.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.five_number_summary")
    sol = solver(mr.params["data"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_classify_distribution_statistic_construct():
    ctx = _make_ctx("math.g2_l57.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "classify_distribution_statistic"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_classify_distribution_statistic_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l57.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.classify_distribution_statistic")
    sol = solver(mr.params["concept"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C11 データ・統計（標本調査）: g3_l57〜g3_l60
# ---------------------------------------------------------------------------
def test_sample_ratio_estimate_lv1_construct():
    ctx = _make_ctx("math.g3_l59.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sample_ratio_estimate"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert mr.params["population_size"] % mr.params["sample_size"] == 0


@pytest.mark.parametrize("seed", range(100))
def test_sample_ratio_estimate_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l59.calculation", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.sample_ratio_estimate")
    sol = solver(mr.params["sample_size"], mr.params["sample_count"], mr.params["population_size"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_sample_ratio_solve_population_lv2_construct():
    ctx = _make_ctx("math.g3_l60.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sample_ratio_solve_population"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert mr.params["known_estimate"] % mr.params["sample_count"] == 0


@pytest.mark.parametrize("seed", range(100))
def test_sample_ratio_solve_population_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l60.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.sample_ratio_solve_population")
    sol = solver(mr.params["sample_size"], mr.params["sample_count"], mr.params["known_estimate"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_appropriate_survey_method_construct():
    ctx = _make_ctx("math.g3_l57.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_appropriate_survey_method"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_appropriate_survey_method_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l57.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_appropriate_survey_method")
    sol = solver(mr.params["needs_sample"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_judge_sampling_bias_construct():
    ctx = _make_ctx("math.g3_l58.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_sampling_bias"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_sampling_bias_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l58.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_sampling_bias")
    sol = solver(mr.params["is_biased"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_explain_sample_ratio_rationale_construct():
    ctx = _make_ctx("math.g3_l59.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "explain_sample_ratio_rationale"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_explain_sample_ratio_rationale_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l59.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.explain_sample_ratio_rationale")
    sol = solver(mr.params["n"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C4 比例・反比例（非visual追加）: g1_l30/l31/l32/l34/l35
# ---------------------------------------------------------------------------
def test_solve_direct_proportion_from_point_lv1_construct():
    ctx = _make_ctx("math.g1_l32.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "solve_direct_proportion_integer"
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    assert [s.op for s in sq.steps] == ["substitute_point", "form_expression"]


@pytest.mark.parametrize("seed", range(100))
def test_solve_direct_proportion_from_point_lv1_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l32.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    sol = solver(mr.params["x0"], mr.params["y0"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_solve_direct_proportion_from_point_lv2_construct():
    ctx = _make_ctx("math.g1_l32.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "solve_direct_proportion_fraction"
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    # level_sep: Lv1（2段）とは異なる op 列（約分の1段が増える3段）。
    assert [s.op for s in sq.steps] == ["substitute_point", "simplify_fraction", "form_expression"]


@pytest.mark.parametrize("seed", range(100))
def test_solve_direct_proportion_from_point_lv2_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l32.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    sol = solver(mr.params["x0"], mr.params["y0"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_solve_inverse_proportion_from_point_lv1_construct():
    ctx = _make_ctx("math.g1_l35.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "solve_inverse_proportion_basic"
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    assert [s.op for s in sq.steps] == ["substitute_point", "form_expression"]


@pytest.mark.parametrize("seed", range(100))
def test_solve_inverse_proportion_from_point_lv1_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l35.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_inverse_proportion_from_point")
    sol = solver(mr.params["x0"], mr.params["y0"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_solve_inverse_proportion_from_point_lv2_construct():
    ctx = _make_ctx("math.g1_l35.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "solve_inverse_proportion_signed"
    sq = mr.sub_questions[0]
    assert sq.asked == "expression"
    # level_sep: Lv1（2段）とは異なる op 列（符号確認の1段が増える3段）。
    assert [s.op for s in sq.steps] == ["check_signs", "substitute_point", "form_expression"]


@pytest.mark.parametrize("seed", range(100))
def test_solve_inverse_proportion_from_point_lv2_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l35.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_inverse_proportion_from_point")
    sol = solver(mr.params["x0"], mr.params["y0"], mr.params["mode"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_proportion_graph_direction_construct():
    ctx = _make_ctx("math.g1_l31.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_proportion_graph_direction"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_proportion_graph_direction_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l31.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_proportion_graph_direction")
    sol = solver(mr.params["is_a_positive"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_judge_hyperbola_quadrants_construct():
    ctx = _make_ctx("math.g1_l34.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_hyperbola_quadrants"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_hyperbola_quadrants_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l34.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_hyperbola_quadrants")
    sol = solver(mr.params["is_a_positive"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C13 exam融合（既存solver合成セル）: exam_l5/exam_l7
# ---------------------------------------------------------------------------
def test_exam_probability_from_counts_construct():
    ctx = _make_ctx("math.exam_l5.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "exam_probability_from_counts"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert 0 < mr.params["occurred"] < mr.params["total"]


@pytest.mark.parametrize("seed", range(100))
def test_exam_probability_from_counts_double_solve_property(seed):
    ctx = _make_ctx("math.exam_l5.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.relative_frequency")
    sol = solver(mr.params["occurred"], mr.params["total"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_exam_relative_frequency_construct():
    ctx = _make_ctx("math.exam_l7.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "exam_relative_frequency"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert 0 < mr.params["occurred"] < mr.params["total"]


@pytest.mark.parametrize("seed", range(100))
def test_exam_relative_frequency_double_solve_property(seed):
    ctx = _make_ctx("math.exam_l7.calculation", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.relative_frequency")
    sol = solver(mr.params["occurred"], mr.params["total"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_exam_quartiles_full_summary_construct():
    ctx = _make_ctx("math.exam_l7.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "exam_quartiles_full_summary"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == ["compute_median", "split_into_halves", "compute_q1_q3_iqr"]


@pytest.mark.parametrize("seed", range(100))
def test_exam_quartiles_full_summary_double_solve_property(seed):
    ctx = _make_ctx("math.exam_l7.find_value", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.quartiles_full_summary")
    sol = solver(mr.params["data"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# C7 g1 平面図形（非visual追加）: g1_l38〜l46
# ---------------------------------------------------------------------------
def test_judge_point_line_distance_meaning_construct():
    ctx = _make_ctx("math.g1_l37.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_point_line_distance_meaning"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert sq.answer.correct == "垂線の長さ"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len({mr.params["pt"], mr.params["a"], mr.params["b"]}) == 3


@pytest.mark.parametrize("seed", range(100))
def test_judge_point_line_distance_meaning_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l37.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_point_line_distance_meaning")
    sol = solver("_")
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


def test_judge_transformation_invariant_parallel_construct():
    ctx = _make_ctx("math.g1_l38.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_transformation_invariant_parallel"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert mr.params["topic"] == "parallel_translation"
    assert sq.answer.correct == "変わらない"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


def test_judge_transformation_invariant_rotation_construct():
    ctx = _make_ctx("math.g1_l39.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_transformation_invariant_rotation"
    sq = mr.sub_questions[0]
    assert mr.params["topic"] == "rotation"
    assert sq.answer.correct == "等しい"


def test_judge_transformation_invariant_reflection_construct():
    ctx = _make_ctx("math.g1_l40.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_transformation_invariant_reflection"
    sq = mr.sub_questions[0]
    assert mr.params["topic"] == "reflection"
    assert sq.answer.correct == "垂直に二等分される"


@pytest.mark.parametrize(
    "family,level", [("math.g1_l38.knowledge", 1), ("math.g1_l39.knowledge", 1), ("math.g1_l40.knowledge", 1)]
)
@pytest.mark.parametrize("seed", range(100))
def test_judge_transformation_invariant_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_transformation_invariant")
    sol = solver(mr.params["topic"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


def test_judge_construction_property_perpendicular_bisector_construct():
    ctx = _make_ctx("math.g1_l41.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_construction_property_perpendicular_bisector"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert mr.params["topic"] == "perpendicular_bisector"
    assert sq.answer.correct == "等しい"
    assert len({mr.params["a"], mr.params["b"], mr.params["pt"]}) == 3


def test_judge_construction_property_angle_bisector_construct():
    ctx = _make_ctx("math.g1_l42.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_construction_property_angle_bisector"
    sq = mr.sub_questions[0]
    assert mr.params["topic"] == "angle_bisector"
    assert sq.answer.correct == "等しい"
    assert len({mr.params["o"], mr.params["a"], mr.params["b"], mr.params["pt"]}) == 4


@pytest.mark.parametrize(
    "family,level", [("math.g1_l41.knowledge", 1), ("math.g1_l42.knowledge", 1)]
)
@pytest.mark.parametrize("seed", range(100))
def test_judge_construction_property_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_construction_property")
    sol = solver(mr.params["topic"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


def test_judge_circle_property_construct():
    ctx = _make_ctx("math.g1_l45.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_circle_property"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert mr.params["concept"] in {"arc_central_angle_proportional", "tangent_perpendicular"}
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_circle_property_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l45.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_circle_property")
    sol = solver(mr.params["concept"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct
    assert sol.answer.fact_id == mr.sub_questions[0].answer.fact_id


def test_sector_arc_length_or_area_lv1_construct():
    ctx = _make_ctx("math.g1_l46.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sector_arc_length_or_area"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert mr.params["target"] in {"arc_length", "area"}
    assert "π" in sq.answer.display


@pytest.mark.parametrize("seed", range(100))
def test_sector_arc_length_or_area_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l46.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.sector_arc_length_or_area")
    sol = solver(mr.params["radius"], mr.params["angle"], mr.params["target"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    # 独立検算: 弧の長さ/面積の公式で sympy 恒真確認。
    r, a = sympy.Integer(mr.params["radius"]), sympy.Integer(mr.params["angle"])
    if mr.params["target"] == "arc_length":
        expected = 2 * sympy.pi * r * a / 360
    else:
        expected = sympy.pi * r * r * a / 360
    assert sympy.srepr(expected) == sol.answer.srepr


def test_sector_solve_central_angle_lv2_construct():
    ctx = _make_ctx("math.g1_l46.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "sector_solve_central_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sympy.Rational(mr.params["area_coeff"]) * 360 == mr.params["angle"] * mr.params["radius"] ** 2


@pytest.mark.parametrize("seed", range(100))
def test_sector_solve_central_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g1_l46.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.sector_solve_central_angle")
    sol = solver(mr.params["radius"], mr.params["area_coeff"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(mr.params["angle"]))


# ---------------------------------------------------------------------------
# C7 g1 平面図形（移動の visual 追加）: g1_l38/l39/l40.graph_table
# ---------------------------------------------------------------------------
def test_translate_polygon_grid_lv1_construct():
    ctx = _make_ctx("math.g1_l38.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "translate_polygon_grid"
    assert set(mr.given.keys()) == {"polygon_points", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert sq.answer.kind == "graph"
    assert len(sq.answer.features) == 3
    assert mr.visual_plan is not None
    assert mr.params["dx"] != 0 and mr.params["dy"] != 0


def test_translate_polygon_coordinate_lv2_construct():
    ctx = _make_ctx("math.g1_l38.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "translate_polygon_coordinate"
    assert set(mr.given.keys()) == {"polygon_coordinates", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert len(sq.answer.features) == 3


@pytest.mark.parametrize(
    "family,level", [("math.g1_l38.graph_table", 1), ("math.g1_l38.graph_table", 2)]
)
@pytest.mark.parametrize("seed", range(100))
def test_translate_polygon_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.translate_polygon_features")
    sol = solver(mr.params["pts"], mr.params["dx"], mr.params["dy"])
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver
    # 独立検算: 各頂点が (dx,dy) だけ平行移動されていることを sympy で確認。
    orig = [sympy.sympify(s) for s in mr.params["pts"]]
    expected = {
        sympy.srepr(sympy.Tuple(x + mr.params["dx"], y + mr.params["dy"])) for x, y in orig
    }
    assert set_recipe == expected


def test_rotate_polygon_grid_lv1_construct():
    ctx = _make_ctx("math.g1_l39.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "rotate_polygon_grid"
    assert set(mr.given.keys()) == {"polygon_points", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert len(sq.answer.features) == 3
    assert mr.params["angle"] in (90, 180, 270)
    assert sympy.sympify(mr.params["center"]) not in [sympy.sympify(s) for s in mr.params["pts"]]


def test_rotate_polygon_coordinate_lv2_construct():
    ctx = _make_ctx("math.g1_l39.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "rotate_polygon_coordinate"
    assert set(mr.given.keys()) == {"polygon_coordinates", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert len(sq.answer.features) == 3


@pytest.mark.parametrize(
    "family,level", [("math.g1_l39.graph_table", 1), ("math.g1_l39.graph_table", 2)]
)
@pytest.mark.parametrize("seed", range(100))
def test_rotate_polygon_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.rotate_polygon_features")
    sol = solver(mr.params["pts"], mr.params["center"], mr.params["angle"])
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver
    # 独立検算: 回転前後で中心からの距離が保たれることを sympy で確認（恒真の性質）。
    cx, cy = sympy.sympify(mr.params["center"])
    orig = [sympy.sympify(s) for s in mr.params["pts"]]
    orig_dists = {(x - cx) ** 2 + (y - cy) ** 2 for x, y in orig}
    new_dists = set()
    for f in sol.answer.features:
        x, y = sympy.sympify(f.srepr)
        new_dists.add((x - cx) ** 2 + (y - cy) ** 2)
    assert orig_dists == new_dists


def test_reflect_polygon_grid_lv1_construct():
    ctx = _make_ctx("math.g1_l40.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "reflect_polygon_grid"
    assert set(mr.given.keys()) == {"polygon_points", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert len(sq.answer.features) == 3
    assert mr.params["axis"] in ("x_axis", "y_axis")


def test_reflect_polygon_coordinate_lv2_construct():
    ctx = _make_ctx("math.g1_l40.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "reflect_polygon_coordinate"
    assert set(mr.given.keys()) == {"polygon_coordinates", "move_spec"}
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_transformed_polygon"
    assert len(sq.answer.features) == 3


@pytest.mark.parametrize(
    "family,level", [("math.g1_l40.graph_table", 1), ("math.g1_l40.graph_table", 2)]
)
@pytest.mark.parametrize("seed", range(100))
def test_reflect_polygon_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.reflect_polygon_features")
    sol = solver(mr.params["pts"], mr.params["axis"])
    set_recipe = {f.srepr for f in mr.sub_questions[0].answer.features}
    set_solver = {f.srepr for f in sol.answer.features}
    assert set_recipe == set_solver
    # 独立検算: 対称移動の公式(x軸: y反転／y軸: x反転)で sympy 恒真確認。
    orig = [sympy.sympify(s) for s in mr.params["pts"]]
    if mr.params["axis"] == "x_axis":
        expected = {sympy.srepr(sympy.Tuple(x, -y)) for x, y in orig}
    else:
        expected = {sympy.srepr(sympy.Tuple(-x, y)) for x, y in orig}
    assert set_recipe == expected


# ---------------------------------------------------------------------------
# C9 g2 図形（角度追跡）: g2_l31〜l35
# ---------------------------------------------------------------------------
def test_solve_angle_by_equality_relation_g2_l31_construct():
    ctx = _make_ctx("math.g2_l31.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "angle_equality_g2_l31"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert mr.params["relation"] in ("vertical", "corresponding", "alternate")
    assert sq.answer.srepr == sympy.srepr(sympy.Integer(mr.params["angle"]))


def test_solve_angle_by_equality_relation_g2_l32_construct():
    ctx = _make_ctx("math.g2_l32.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "angle_equality_g2_l32"
    assert mr.params["relation"] in ("corresponding", "alternate")


@pytest.mark.parametrize(
    "family,level", [("math.g2_l31.find_value", 1), ("math.g2_l32.find_value", 1)]
)
@pytest.mark.parametrize("seed", range(100))
def test_solve_angle_by_equality_relation_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_angle_by_equality_relation")
    sol = solver(mr.params["relation"], mr.params["angle"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(mr.params["angle"]))


@pytest.mark.parametrize(
    "family,level", [("math.g2_l31.find_value", 2), ("math.g2_l32.find_value", 2)]
)
@pytest.mark.parametrize("seed", range(100))
def test_solve_zigzag_angle_sum_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.solve_zigzag_angle_sum")
    sol = solver(mr.params["angle1"], mr.params["angle2"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(mr.params["angle1"] + mr.params["angle2"]))


def test_judge_parallel_from_angle_condition_construct():
    ctx = _make_ctx("math.g2_l32.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_parallel_from_angle_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    is_equal = mr.params["is_equal"] == "True"
    assert is_equal == (mr.params["angle_a"] == mr.params["angle_b"])


@pytest.mark.parametrize("seed", range(100))
def test_judge_parallel_from_angle_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l32.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_parallel_from_angle_condition")
    sol = solver(mr.params["is_equal"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_triangle_third_angle_construct():
    ctx = _make_ctx("math.g2_l33.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "triangle_third_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert mr.params["angle_a"] + mr.params["angle_b"] < 180


@pytest.mark.parametrize("seed", range(100))
def test_triangle_third_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l33.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.triangle_third_angle")
    sol = solver(mr.params["angle_a"], mr.params["angle_b"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    expected = 180 - mr.params["angle_a"] - mr.params["angle_b"]
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(expected))


def test_polygon_interior_sum_and_angle_construct():
    ctx = _make_ctx("math.g2_l34.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "polygon_interior_sum_and_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    n = mr.params["sides"]
    expected = sympy.Tuple(180 * (n - 2), sympy.Rational(180 * (n - 2), n))
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_polygon_interior_sum_and_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l34.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.polygon_interior_sum_and_angle")
    sol = solver(mr.params["sides"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_polygon_sides_from_interior_sum_construct():
    ctx = _make_ctx("math.g2_l34.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "polygon_sides_from_interior_sum"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Integer(mr.params["sides"]))
    assert mr.params["interior_sum"] == 180 * (mr.params["sides"] - 2)


@pytest.mark.parametrize("seed", range(100))
def test_polygon_sides_from_interior_sum_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l34.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.polygon_sides_from_interior_sum")
    sol = solver(mr.params["interior_sum"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_regular_polygon_exterior_angle_construct():
    ctx = _make_ctx("math.g2_l35.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "regular_polygon_exterior_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    n = mr.params["sides"]
    assert sq.answer.srepr == sympy.srepr(sympy.Rational(360, n))


@pytest.mark.parametrize("seed", range(100))
def test_regular_polygon_exterior_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l35.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.regular_polygon_exterior_angle")
    sol = solver(mr.params["sides"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_polygon_sides_from_interior_angle_construct():
    ctx = _make_ctx("math.g2_l35.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "polygon_sides_from_interior_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Integer(mr.params["sides"]))


@pytest.mark.parametrize("seed", range(100))
def test_polygon_sides_from_interior_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l35.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.polygon_sides_from_interior_angle")
    sol = solver(mr.params["interior_angle"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(mr.params["sides"]))


# ---------------------------------------------------------------------------
# C9 g2 図形（合同条件・二等辺三角形・正三角形）: g2_l37/l38/l41/l42/l43
# ---------------------------------------------------------------------------
def test_isosceles_base_angle_apex_to_base_construct():
    ctx = _make_ctx("math.g2_l41.find_value", 1)
    found_apex = False
    for seed in range(20):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        if mr.params["known_type"] == "apex":
            found_apex = True
            assert mr.signature == "isosceles_base_angle"
            sq = mr.sub_questions[0]
            assert sq.asked == "value"
            apex = mr.params["known_value"]
            assert sq.answer.srepr == sympy.srepr(sympy.Rational(180 - apex, 2))
            break
    assert found_apex, "20 seed 中に known_type=apex が1つも出なかった"


def test_isosceles_base_angle_base_to_apex_construct():
    ctx = _make_ctx("math.g2_l41.find_value", 1)
    found_base = False
    for seed in range(20):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        if mr.params["known_type"] == "base":
            found_base = True
            sq = mr.sub_questions[0]
            base = mr.params["known_value"]
            assert sq.answer.srepr == sympy.srepr(sympy.Integer(180 - 2 * base))
            break
    assert found_base, "20 seed 中に known_type=base が1つも出なかった"


@pytest.mark.parametrize("seed", range(100))
def test_isosceles_base_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l41.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.isosceles_base_angle")
    sol = solver(mr.params["known_type"], mr.params["known_value"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_equilateral_triangle_properties_construct():
    ctx = _make_ctx("math.g2_l43.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equilateral_triangle_properties"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    side = mr.params["side"]
    expected = sympy.Tuple(sympy.Integer(side), sympy.Rational(180, 3))
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_equilateral_triangle_properties_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l43.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.equilateral_triangle_properties")
    sol = solver(mr.params["side"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_isosceles_from_angle_condition_construct():
    ctx = _make_ctx("math.g2_l42.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_isosceles_from_angle_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    is_equal = mr.params["is_equal"] == "True"
    assert is_equal == (mr.params["angle_b"] == mr.params["angle_c"])
    assert mr.params["angle_b"] + mr.params["angle_c"] < 180


@pytest.mark.parametrize("seed", range(100))
def test_judge_isosceles_from_angle_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l42.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_isosceles_from_angle_condition")
    sol = solver(mr.params["is_equal"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_judge_equilateral_from_condition_construct():
    ctx = _make_ctx("math.g2_l43.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_equilateral_from_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len({mr.params["a"], mr.params["b"], mr.params["c"]}) == 3


@pytest.mark.parametrize("seed", range(100))
def test_judge_equilateral_from_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l43.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_equilateral_from_condition")
    sol = solver(mr.params["is_equilateral"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C9 g2 図形（合同な図形の対応関係）: g2_l36
# ---------------------------------------------------------------------------
def test_congruence_transfer_values_construct():
    ctx = _make_ctx("math.g2_l36.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "congruence_transfer_values"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    expected = sympy.Tuple(sympy.Integer(mr.params["side_value"]), sympy.Integer(mr.params["angle_value"]))
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_congruence_transfer_values_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l36.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.congruence_transfer_values")
    sol = solver(mr.params["side_value"], mr.params["angle_value"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_congruence_symbol_and_side_construct():
    ctx = _make_ctx("math.g2_l36.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "congruence_symbol_and_side"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len(set(mr.params["p_labels"]) | set(mr.params["q_labels"])) == 6


@pytest.mark.parametrize("seed", range(100))
def test_congruence_symbol_and_side_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l36.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.congruence_symbol_and_side")
    sol = solver(mr.params["p_labels"], mr.params["q_labels"], mr.params["i"], mr.params["j"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_congruence_corresponding_pair_construct():
    ctx = _make_ctx("math.g2_l36.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "congruence_corresponding_pair"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len(set(mr.params["p_labels"]) | set(mr.params["q_labels"])) == 6


@pytest.mark.parametrize("seed", range(100))
def test_congruence_corresponding_pair_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l36.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.congruence_corresponding_pair")
    sol = solver(
        mr.params["p_labels"], mr.params["q_labels"],
        mr.params["angle_i"], mr.params["side_i"], mr.params["side_j"],
    )
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C9 g2 図形（直角三角形の合同条件）: g2_l44
# ---------------------------------------------------------------------------
def test_judge_right_triangle_congruence_construct():
    ctx = _make_ctx("math.g2_l44.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_right_triangle_congruence"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len(set(mr.params["labels"])) == 6


@pytest.mark.parametrize("seed", range(100))
def test_judge_right_triangle_congruence_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l44.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_right_triangle_congruence")
    sol = solver(mr.params["condition_type"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C9 g2 図形（平行四辺形・特別な平行四辺形・等積変形）: g2_l46/l47/l49/l50
# ---------------------------------------------------------------------------
def test_parallelogram_opposite_properties_construct():
    ctx = _make_ctx("math.g2_l46.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "parallelogram_opposite_properties"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    expected = sympy.Tuple(sympy.Integer(mr.params["side_value"]), sympy.Integer(mr.params["angle_value"]))
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_parallelogram_opposite_properties_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l46.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.parallelogram_opposite_properties")
    sol = solver(mr.params["side_value"], mr.params["angle_value"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_identify_parallelogram_condition_construct():
    ctx = _make_ctx("math.g2_l47.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "identify_parallelogram_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len({mr.params["a"], mr.params["b"], mr.params["c"], mr.params["d"]}) == 4


@pytest.mark.parametrize("seed", range(100))
def test_identify_parallelogram_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l47.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.identify_parallelogram_condition")
    sol = solver(mr.params["condition_key"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_special_parallelogram_diagonal_value_construct():
    ctx = _make_ctx("math.g2_l49.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "special_parallelogram_diagonal_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    if mr.params["shape"] == "rhombus":
        assert sq.answer.srepr == sympy.srepr(sympy.Integer(90))
    else:
        assert sq.answer.srepr == sympy.srepr(sympy.Rational(mr.params["value"], 2))


@pytest.mark.parametrize("seed", range(100))
def test_special_parallelogram_diagonal_value_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l49.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.special_parallelogram_diagonal_value")
    sol = solver(mr.params["shape"], mr.params["value"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_special_parallelogram_diagonal_value_rhombus_construct():
    ctx = _make_ctx("math.g2_l49.find_value", 1)
    found_rhombus = False
    for seed in range(20):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        if mr.params["shape"] == "rhombus":
            found_rhombus = True
            assert mr.sub_questions[0].answer.srepr == sympy.srepr(sympy.Integer(90))
            break
    assert found_rhombus, "20 seed 中に shape=rhombus が1つも出なかった"


def test_classify_quadrilateral_from_diagonal_condition_construct():
    ctx = _make_ctx("math.g2_l49.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "classify_quadrilateral_from_diagonal_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_classify_quadrilateral_from_diagonal_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l49.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.classify_quadrilateral_from_diagonal_condition")
    sol = solver(mr.params["equal"], mr.params["perpendicular"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_equal_area_transform_value_construct():
    ctx = _make_ctx("math.g2_l50.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "equal_area_transform_value"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Integer(mr.params["area_value"]))


@pytest.mark.parametrize("seed", range(100))
def test_equal_area_transform_value_double_solve_property(seed):
    ctx = _make_ctx("math.g2_l50.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.equal_area_transform_value")
    sol = solver(mr.params["area_value"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# C10 g3 図形（三平方の定理・その逆）: g3_l51/l52
# ---------------------------------------------------------------------------
def test_pythagorean_hypotenuse_construct():
    ctx = _make_ctx("math.g3_l51.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "pythagorean_hypotenuse"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    a, b = mr.params["leg_a"], mr.params["leg_b"]
    assert sq.answer.srepr == sympy.srepr(sympy.sqrt(a**2 + b**2))


@pytest.mark.parametrize("seed", range(100))
def test_pythagorean_hypotenuse_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l51.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.pythagorean_hypotenuse")
    sol = solver(mr.params["leg_a"], mr.params["leg_b"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_identify_hypotenuse_construct():
    ctx = _make_ctx("math.g3_l51.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "identify_hypotenuse"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len(set(mr.params["labels"])) == 3


@pytest.mark.parametrize("seed", range(100))
def test_identify_hypotenuse_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l51.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.identify_hypotenuse")
    sol = solver(mr.params["labels"], mr.params["right_angle_index"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_verify_right_triangle_from_sides_construct():
    ctx = _make_ctx("math.g3_l52.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "verify_right_triangle_from_sides"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr in (sympy.srepr(sympy.true), sympy.srepr(sympy.false))


@pytest.mark.parametrize("seed", range(100))
def test_verify_right_triangle_from_sides_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l52.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.verify_right_triangle_from_sides")
    sol = solver(mr.params["side_a"], mr.params["side_b"], mr.params["side_c"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_verify_right_triangle_from_sides_both_outcomes_construct():
    ctx = _make_ctx("math.g3_l52.find_value", 2)
    found_true = False
    found_false = False
    for seed in range(30):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        if mr.sub_questions[0].answer.display == "直角三角形である":
            found_true = True
        else:
            found_false = True
        if found_true and found_false:
            break
    assert found_true and found_false, "30 seed 中に真偽両方が出なかった"


def test_judge_right_triangle_from_three_sides_construct():
    ctx = _make_ctx("math.g3_l52.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_right_triangle_from_three_sides"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_right_triangle_from_three_sides_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l52.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_right_triangle_from_three_sides")
    sol = solver(mr.params["side_a"], mr.params["side_b"], mr.params["side_c"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C10 g3 図形（相似な図形）: g3_l39
# ---------------------------------------------------------------------------
def test_similarity_ratio_transfer_construct():
    ctx = _make_ctx("math.g3_l39.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "similarity_ratio_transfer"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert math.gcd(mr.params["ratio_num"], mr.params["ratio_den"]) == 1
    expected = sympy.Rational(mr.params["known_side"]) * mr.params["ratio_den"] / mr.params["ratio_num"]
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_similarity_ratio_transfer_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l39.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = solver(mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_side"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_identify_similar_corresponding_vertex_construct():
    ctx = _make_ctx("math.g3_l39.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "identify_similar_corresponding_vertex"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors
    assert len(set(mr.params["labels1"])) == 4
    assert len(set(mr.params["labels2"])) == 4


@pytest.mark.parametrize("seed", range(100))
def test_identify_similar_corresponding_vertex_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l39.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.identify_similar_corresponding_vertex")
    sol = solver(mr.params["labels1"], mr.params["labels2"], mr.params["index"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C10 g3 図形（三角形の相似条件）: g3_l40
# ---------------------------------------------------------------------------
def test_similar_triangle_x_shape_construct():
    ctx = _make_ctx("math.g3_l40.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "similar_triangle_x_shape"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    oa, ob, oc = mr.params["oa"], mr.params["ob"], mr.params["oc"]
    expected = sympy.Rational(ob) * oc / oa
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_similar_triangle_x_shape_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l40.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similar_triangle_x_shape")
    sol = solver(mr.params["oa"], mr.params["ob"], mr.params["oc"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_identify_similarity_condition_construct():
    ctx = _make_ctx("math.g3_l40.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "identify_similarity_condition"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_identify_similarity_condition_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l40.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.identify_similarity_condition")
    sol = solver(mr.params["condition_key"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


# ---------------------------------------------------------------------------
# C10 g3 図形（証明済み相似からの求値）: g3_l41
# ---------------------------------------------------------------------------
def test_similarity_proven_ratio_length_construct():
    ctx = _make_ctx("math.g3_l41.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "similarity_proven_ratio_length"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert math.gcd(mr.params["ratio_num"], mr.params["ratio_den"]) == 1
    expected = sympy.Rational(mr.params["known_side"]) * mr.params["ratio_den"] / mr.params["ratio_num"]
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_similarity_proven_ratio_length_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l41.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = solver(mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_side"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# C10 g3 図形（平行線と線分の比の定理・その逆・中点連結定理）: g3_l42/l43/l44
# ---------------------------------------------------------------------------
def test_parallel_segment_ratio_length_construct():
    ctx = _make_ctx("math.g3_l42.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "parallel_segment_ratio_length"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    ad, db, de = mr.params["ad"], mr.params["db"], mr.params["de"]
    expected = sympy.Rational(de) * (ad + db) / ad
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_parallel_segment_ratio_length_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l42.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.parallel_segment_ratio_length")
    sol = solver(mr.params["ad"], mr.params["db"], mr.params["de"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_parallel_from_ratio_construct():
    ctx = _make_ctx("math.g3_l43.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_parallel_from_ratio"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr in (sympy.srepr(sympy.true), sympy.srepr(sympy.false))


@pytest.mark.parametrize("seed", range(100))
def test_judge_parallel_from_ratio_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l43.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_parallel_from_ratio")
    sol = solver(mr.params["ad"], mr.params["db"], mr.params["ae"], mr.params["ec"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_parallel_from_ratio_both_outcomes_construct():
    ctx = _make_ctx("math.g3_l43.find_value", 2)
    found_true = False
    found_false = False
    for seed in range(30):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        if mr.sub_questions[0].answer.display == "平行である":
            found_true = True
        else:
            found_false = True
        if found_true and found_false:
            break
    assert found_true and found_false, "30 seed 中に真偽両方が出なかった"


def test_midpoint_connector_length_construct():
    ctx = _make_ctx("math.g3_l44.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "midpoint_connector_length"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Rational(mr.params["bc"]) / 2)


@pytest.mark.parametrize("seed", range(100))
def test_midpoint_connector_length_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l44.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.midpoint_connector_length")
    sol = solver(mr.params["bc"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# C10 g3 図形（相似比から面積比・表面積比・体積比）: g3_l45/l46
# ---------------------------------------------------------------------------
def test_similar_area_ratio_construct():
    ctx = _make_ctx("math.g3_l45.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "similar_area_ratio"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    m, n, a = mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_area"]
    assert math.gcd(m, n) == 1
    expected = sympy.Tuple(sympy.Integer(m**2), sympy.Integer(n**2), sympy.Rational(a) * n**2 / m**2)
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_similar_area_ratio_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l45.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similar_area_ratio")
    sol = solver(mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_area"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_similar_solid_surface_volume_ratio_construct():
    ctx = _make_ctx("math.g3_l46.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "similar_solid_surface_volume_ratio"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    m, n = mr.params["ratio_num"], mr.params["ratio_den"]
    assert math.gcd(m, n) == 1
    expected = sympy.Tuple(sympy.Integer(m**2), sympy.Integer(n**2), sympy.Integer(m**3), sympy.Integer(n**3))
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_similar_solid_surface_volume_ratio_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l46.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similar_solid_surface_volume_ratio")
    sol = solver(mr.params["ratio_num"], mr.params["ratio_den"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# C10 g3 図形（円周角の定理・その逆・弧の比例）: g3_l47/l48/l49/l50
# ---------------------------------------------------------------------------
def test_inscribed_angle_from_central_construct():
    ctx = _make_ctx("math.g3_l47.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "inscribed_angle_from_central"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Rational(mr.params["central_angle"], 2))


@pytest.mark.parametrize("seed", range(100))
def test_inscribed_angle_from_central_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l47.find_value", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.inscribed_angle_from_central")
    sol = solver(mr.params["central_angle"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_inscribed_angle_transfer_same_arc_construct():
    ctx = _make_ctx("math.g3_l48.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "inscribed_angle_transfer_same_arc"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert sq.answer.srepr == sympy.srepr(sympy.Integer(mr.params["v2"]))


@pytest.mark.parametrize("seed", range(100))
def test_inscribed_angle_transfer_same_arc_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l48.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.inscribed_angle_transfer_same_arc")
    sol = solver(mr.params["v2"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_judge_concyclic_from_angle_construct():
    ctx = _make_ctx("math.g3_l48.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_concyclic_from_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "choice"
    assert not any(ch.isdigit() for ch in sq.answer.correct)
    assert sq.answer.correct not in sq.answer.distractors


@pytest.mark.parametrize("seed", range(100))
def test_judge_concyclic_from_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l48.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.judge_concyclic_from_angle")
    sol = solver(mr.params["angle_c"], mr.params["angle_d"])
    assert sol.answer.correct == mr.sub_questions[0].answer.correct


def test_circle_similar_chord_length_construct():
    ctx = _make_ctx("math.g3_l49.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "circle_similar_chord_length"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    m, n, v = mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_side"]
    assert math.gcd(m, n) == 1
    expected = sympy.Rational(v) * n / m
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_circle_similar_chord_length_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l49.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.similarity_ratio_transfer")
    sol = solver(mr.params["ratio_num"], mr.params["ratio_den"], mr.params["known_side"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


def test_arc_proportional_angle_construct():
    ctx = _make_ctx("math.g3_l50.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "arc_proportional_angle"
    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    expected = sympy.Integer(mr.params["multiplier"]) * mr.params["known_angle"]
    assert sq.answer.srepr == sympy.srepr(expected)


@pytest.mark.parametrize("seed", range(100))
def test_arc_proportional_angle_double_solve_property(seed):
    ctx = _make_ctx("math.g3_l50.find_value", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.arc_proportional_angle")
    sol = solver(mr.params["multiplier"], mr.params["known_angle"])
    assert sol.answer.srepr == mr.sub_questions[0].answer.srepr


# ---------------------------------------------------------------------------
# g2_l16.word_problem Lv2（form=word_problem の初回縦串・誘導つき2段小問）
# ---------------------------------------------------------------------------
def test_word_problem_price_count_construct():
    ctx = _make_ctx("math.g2_l16.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "word_problem_system_price_count"
    # 誘導の2段: (1) 立式 → (2) 値
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
        ("(1)", "formulation"),
        ("(2)", "value"),
    ]
    # given は場面と変数の設定に分かれ、どちらも本文に出る値を持つ
    assert set(mr.given) == {"scenario", "quantities"}
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(100))
def test_word_problem_price_count_property(seed):
    """全小問が独立に再計算で一致し、場面が退化しない（単価相異＝解が一意）。"""
    ctx = _make_ctx("math.g2_l16.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    _, _, total = (int(c) for c in mr.params["line_count"])
    price_a, price_b, cost = (int(c) for c in mr.params["line_cost"])
    assert price_a != price_b, "単価が同じ＝代金の式が個数の式の定数倍で解が定まらない"
    assert mr.params["item_a"] != mr.params["item_b"]

    # checker（list[Solution]）が両小問に一致する＝G-Q1 が通る形
    checker = REGISTRY.checker("math.word_problem_price_count.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # (2) の答え (a, b) は場面の数値を実際に満たす（総数と代金の両方）
    count_a, count_b = sympy.sympify(mr.sub_questions[1].answer.srepr)
    assert count_a + count_b == total
    assert price_a * count_a + price_b * count_b == cost
    # 場面文に総数と合計代金が現れる（誘導の材料が本文にある）
    assert f"{total}個" in mr.given["scenario"]
    assert f"{cost}円" in mr.given["scenario"]


# ---------------------------------------------------------------------------
# 1元1次方程式の利用（g1_l25/l26/l27 × Lv2/Lv3）＝1 recipe で6セル
# ---------------------------------------------------------------------------
_LINEAR_WP_CELLS = [
    ("math.g1_l25.word_problem", 2, "word_problem_price_count_one_unknown", True),
    ("math.g1_l25.word_problem", 3, "word_problem_price_count_diff", False),
    ("math.g1_l26.word_problem", 2, "word_problem_surplus_shortage", True),
    ("math.g1_l26.word_problem", 3, "word_problem_seat_shortage_exact", False),
    ("math.g1_l27.word_problem", 2, "word_problem_round_trip_distance", True),
    ("math.g1_l27.word_problem", 3, "word_problem_catch_up_time", False),
    ("math.g1_l24.word_problem", 2, "word_problem_proportion_pair", True),
    ("math.g1_l24.word_problem", 3, "word_problem_continued_ratio", False),
]


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _LINEAR_WP_CELLS)
def test_word_problem_linear_construct(family, level, signature, guided):
    """誘導ありは (1)立式→(2)値 の2小問、誘導なしは値の1小問（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    if guided:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
            ("(1)", "formulation"),
            ("(2)", "value"),
        ]
        assert set(mr.given) == {"scenario", "quantities"}
    else:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "value")]
        # 誘導なしは変数の設定を与えない（自分で x をおく）
        assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _LINEAR_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_linear_double_solve_property(seed, family, level, signature, guided):
    """全小問が checker の独立再計算と一致し、答えが方程式を実際に満たす。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_linear_equation.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # 場面の数値から組んだ方程式に、解 x を戻して恒真を確認する（構成の健全性）
    from engine.packs.math.recipes.word_problem_linear import FORMULATION_BUILDERS

    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    formulation = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)
    answer_value = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    coeff_m, coeff_n = (int(sympy.sympify(c)) for c in mr.params["answer_coeff"])
    x_value = sympy.Rational(answer_value - coeff_n, coeff_m)
    assert x_value.q == 1, "x は整数（answer-first で逆算しているので端数は出ない）"
    assert x_value > 0, "個数・人数・道のり・時間はすべて正"
    assert formulation.eq.subs(sympy.Symbol("x"), x_value) is sympy.true

    # 立式に使う数値はすべて given のどこかに現れている（＝読者に見えている数だけを
    # checker に渡している）。given のどこか、であって場面文限定ではない: 誘導ありの
    # 比例式セルのように「問われている個数」が変数の設定（quantities）側に出る場面が
    # ある。given → problem_text は G-GND が保証するので、この形で
    # 「本文の数値を読み違えても checker が気づかない」経路が閉じる。
    given_text = "".join(mr.given.values())
    for value in numbers.values():
        assert str(value) in given_text


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_linear_non_degenerate(seed):
    """非退化条件: 代金は単価相異（x が消えない）・過不足は a<b（同上）。"""
    ctx = _make_ctx("math.g1_l25.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["price_a"]) != int(numbers["price_b"])

    ctx = _make_ctx("math.g1_l26.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["per_a"]) < int(numbers["per_b"])
    assert int(numbers["shortage"]) >= 1, "「足りない数」は正でないと場面が成立しない"

    # 追いつきは vf > vs（でないと永遠に追いつけない）
    ctx = _make_ctx("math.g1_l27.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["speed_fast"]) > int(numbers["speed_slow"])


def test_word_problem_linear_derived_answer_is_not_x():
    """g1_l26 Lv3 は「文字＝脚数・答え＝人数」。answer_coeff の合成が効いている。"""
    ctx = _make_ctx("math.g1_l26.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    per_a, left_out = (int(sympy.sympify(mr.params["numbers"][k])) for k in ("per_a", "left_out"))
    assert [int(sympy.sympify(c)) for c in mr.params["answer_coeff"]] == [per_a, left_out]
    # 答え（人数）は x（脚数）と一致しない＝合成の最後の一手が入っている
    students = sympy.sympify(mr.sub_questions[0].answer.srepr)
    seats = sympy.Rational(students - left_out, per_a)
    assert students != seats
    assert mr.sub_questions[0].answer.display.endswith("人")


# ---------------------------------------------------------------------------
# 連立方程式の利用（g2_l17/g2_l18 × Lv2/Lv3/Lv4）＝1 recipe で6セル
# ---------------------------------------------------------------------------
_SYSTEM_WP_CELLS = [
    ("math.g2_l16.word_problem", 3, "word_problem_system_price_count_diff", False),
    ("math.g2_l17.word_problem", 2, "word_problem_distance_time_guided", True),
    ("math.g2_l17.word_problem", 3, "word_problem_time_split_solo", False),
    ("math.g2_l17.word_problem", 4, "word_problem_lap_meet_catch_up", False),
    ("math.g2_l18.word_problem", 2, "word_problem_percent_change_guided", True),
    ("math.g2_l18.word_problem", 3, "word_problem_salt_mixture_solo", False),
    ("math.g2_l18.word_problem", 4, "word_problem_two_containers", False),
]


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _SYSTEM_WP_CELLS)
def test_word_problem_system_construct(family, level, signature, guided):
    """誘導ありは (1)立式→(2)値 の2小問、誘導なしは値の1小問（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    if guided:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
            ("(1)", "formulation"),
            ("(2)", "value"),
        ]
        assert set(mr.given) == {"scenario", "quantities"}
    else:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "value")]
        # 誘導なしは変数の設定を与えない（自分で x, y をおく）
        assert set(mr.given) == {"scenario"}
        # 誘導なしでも模範解答は立式から始まる（解くところから始まらない）
        assert [s.op for s in mr.sub_questions[0].steps][:3] == [
            "set_variables",
            "formulate_first",
            "formulate_second",
        ]
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params
    # solver の setup_system は落としている（「2つの直線」は文章題の語彙ではない）
    assert all(
        s.op != "setup_system" for sq in mr.sub_questions for s in sq.steps
    )


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _SYSTEM_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_system_double_solve_property(seed, family, level, signature, guided):
    """全小問が checker の独立再計算と一致し、答えが連立を実際に満たす。"""
    from engine.packs.math.recipes.word_problem_system import (
        FORMULATION_BUILDERS,
        IDENTITY_ANSWER_MAP,
    )

    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_system_equations.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # 場面の数値から組んだ連立に、解 (x, y) を戻して恒真を確認する（構成の健全性）
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    formulation = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)
    asked = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    answer_map = [[int(sympy.sympify(v)) for v in row] for row in mr.params["answer_map"]]
    if answer_map == [list(row) for row in IDENTITY_ANSWER_MAP]:
        x_value, y_value = asked[0], asked[1]
    else:
        # 問われている量が m·x（例: 道のり = 速さ×時間）＝逆に割って x, y を復元する
        x_value = sympy.Rational(asked[0], answer_map[0][0])
        y_value = sympy.Rational(asked[1], answer_map[1][1])
    for eq in formulation.eqs:
        subbed = eq.subs({sympy.Symbol("x"): x_value, sympy.Symbol("y"): y_value})
        assert subbed is sympy.true, f"{eq} に ({x_value}, {y_value}) を戻すと偽"
    assert x_value.q == 1 and y_value.q == 1, "answer-first で逆算しているので端数は出ない"
    assert x_value > 0 and y_value > 0, "個数・人数・道のり・時間・濃度はすべて正"

    # params の数値はすべて given に現れている（＝読者に見えている数だけを持つ）。
    # これが崩れると「本文の数値を読み違えても checker が気づかない」経路ができる。
    given_text = "".join(mr.given.values())
    for value in numbers.values():
        assert str(value) in given_text


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_system_non_degenerate(seed):
    """非退化条件: det ≠ 0 を場面ごとの言葉で確認する。"""
    # 速さ: 歩き ≠ 自転車（det = 1/b − 1/a）
    ctx = _make_ctx("math.g2_l17.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["speed_walk"]) < int(numbers["speed_bike"])

    # 追いつきは「和で出会う時間 < 差で追いつく時間」（差 < 和）
    ctx = _make_ctx("math.g2_l17.word_problem", 4)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["meet_time"]) < int(numbers["catch_up_time"])

    # 食塩水は濃度相異（det = (b − a)/100）かつ混合後は2つのあいだ
    ctx = _make_ctx("math.g2_l18.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    lo, hi, mix = (int(numbers[k]) for k in ("percent_a", "percent_b", "percent_mix"))
    assert lo < mix < hi

    # 2容器は重さ相異（det = (Wa − Wb)/100）
    ctx = _make_ctx("math.g2_l18.word_problem", 4)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["weight_a"]) != int(numbers["weight_b"])


def test_word_problem_system_derived_answer_is_not_xy():
    """g2_l17 Lv3 は「文字＝時間・答え＝道のり」。answer_map の合成が効いている。"""
    ctx = _make_ctx("math.g2_l17.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    speed_slow, speed_fast = (
        int(sympy.sympify(mr.params["numbers"][k])) for k in ("speed_slow", "speed_fast")
    )
    assert [[int(sympy.sympify(v)) for v in row] for row in mr.params["answer_map"]] == [
        [speed_slow, 0, 0],
        [0, speed_fast, 0],
    ]
    # 最後の一手が steps に入っている（x, y をそのまま答えにしていない）
    assert mr.sub_questions[0].steps[-1].op == "derive_asked_quantities"
    assert mr.sub_questions[0].answer.display.endswith("m")


def test_word_problem_system_level_sep_places_letters_differently():
    """G6 の骨: 同じ「連立の利用」でも Lv ごとに文字を置く対象が違う。

    Lv2 は道のり（時間の式が分数係数）／Lv3 は時間（道のりの式が整数係数）／
    Lv4 は速さ（和と差の2式）。立式の係数行がそのまま違うことで確認する。
    """
    from engine.packs.math.recipes.word_problem_system import (
        FORMULATION_BUILDERS,
    )

    lines = {}
    for level in (2, 3, 4):
        ctx = _make_ctx("math.g2_l17.word_problem", level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
        lines[level] = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)

    # Lv2: 2つめの式の x, y の係数が 1/a, 1/b（分数）
    assert all(sympy.sympify(c).q > 1 for c in lines[2].line_b[:2])
    # Lv3: 2つめの式の係数は整数（速さそのもの）
    assert all(sympy.sympify(c).q == 1 for c in lines[3].line_b[:2])
    # Lv4: 和の式と差の式（y の係数の符号が逆）
    assert sympy.sympify(lines[4].line_a[1]) > 0
    assert sympy.sympify(lines[4].line_b[1]) < 0


# ---------------------------------------------------------------------------
# 比例式の利用（g1_l24 × Lv2/Lv3）: 表示は比例式・solver に渡すのは線形式
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("level", "guided"), [(2, True), (3, False)])
@pytest.mark.parametrize("seed", range(20))
def test_word_problem_proportion_display_is_a_ratio(seed, level, guided):
    """(1)/(2) の答えの表示が「a:b = c:x」形で、機械表現は線形式になっている。"""
    from engine.packs.math.recipes.word_problem_linear import FORMULATION_BUILDERS

    ctx = _make_ctx("math.g1_l24.word_problem", level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    formulation = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)
    # 表示は比例式（コロンが2つ）／機械表現はたすきがけ後の一次方程式
    assert formulation.display.count(":") == 2
    assert "=" in formulation.display
    assert formulation.eq.free_symbols == {sympy.Symbol("x")}
    # 答えは正の整数で、本文に出ている数値とは一致しない（G-Q5t の自衛）
    answer = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    assert answer.is_Integer and answer > 0
    assert answer not in set(numbers.values())


def test_word_problem_continued_ratio_needs_an_extra_step():
    """Lv3 は「連比の和を出す」一手が立式の前に入る＝Lv2 との op 列の差。"""
    ctx = _make_ctx("math.g1_l24.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    lv3 = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    ctx2 = _make_ctx("math.g1_l24.word_problem", 2)
    rng2 = derive_rng(ctx2.family, ctx2.level, ctx2.purpose, seed=1)
    lv2 = REGISTRY.recipe(ctx2.spec_level.recipe)(ctx2, rng2)

    assert [s.op for s in lv3.sub_questions[0].steps][:3] == [
        "sum_ratio_parts",
        "find_equal_relation",
        "formulate_equation",
    ]
    # Lv2 の立式は2手のまま（prelude_step 既定 None＝既存セルの steps 不変）
    assert [s.op for s in lv2.sub_questions[0].steps] == [
        "find_equal_relation",
        "formulate_equation",
    ]
    # params は連比の3項をそのまま持ち、和は立式ビルダー側で導く
    # （和は本文に出ていない数なので params に置くと検証に穴ができる）
    assert set(lv3.params["numbers"]) == {"ratio_1", "ratio_2", "ratio_3", "total"}


# ---------------------------------------------------------------------------
# 2次方程式の利用（g3_l29/g3_l30 × Lv2/Lv3）＝1 recipe で4セル
# ---------------------------------------------------------------------------
_QUADRATIC_WP_CELLS = [
    ("math.g3_l29.word_problem", 2, "word_problem_quadratic_consecutive_integers", True),
    ("math.g3_l29.word_problem", 3, "word_problem_quadratic_number_square_relation", False),
    ("math.g3_l30.word_problem", 2, "word_problem_quadratic_rectangle_area", True),
    ("math.g3_l30.word_problem", 3, "word_problem_quadratic_square_cut", False),
]


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _QUADRATIC_WP_CELLS)
def test_word_problem_quadratic_construct(family, level, signature, guided):
    """誘導ありは (1)立式→(2)値 の2小問、誘導なしは値の1小問（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    if guided:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
            ("(1)", "formulation"),
            ("(2)", "value"),
        ]
        assert set(mr.given) == {"scenario", "quantities"}
    else:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "value")]
        # 誘導なしは変数の設定を与えない（自分で x をおく）
        assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params
    # 解の吟味（不適解の除外）が解説に出る＝このクラスタの核
    assert any(
        s.op == "select_positive_root" for sq in mr.sub_questions for s in sq.steps
    )


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _QUADRATIC_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_quadratic_double_solve_property(seed, family, level, signature, guided):
    """全小問が checker の独立再計算と一致し、答え（正の解）が方程式を実際に満たす。"""
    from engine.packs.math.recipes.word_problem_quadratic import FORMULATION_BUILDERS

    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_quadratic.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # 場面の数値から組んだ方程式に、正の解を戻して恒真を確認する（構成の健全性）
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    formulation = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)
    answer_values = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    coeffs = [(int(sympy.sympify(m)), int(sympy.sympify(n))) for m, n in mr.params["answer_coeffs"]]
    # answer_coeffs[0] は常に (1, 0)（求める量の1つめは必ず x そのもの）
    assert coeffs[0] == (1, 0)
    x_value = answer_values[0]
    assert x_value == sympy.Integer(x_value), "x は整数（answer-first で逆算しているので端数は出ない）"
    assert x_value > 0, "場面が要求する量（整数・長さ）はすべて正"
    assert formulation.eq.subs(sympy.Symbol("x"), x_value) is sympy.true

    # 2つめの解（x を負にしたもの）は不適である＝場面の核（正の解しか採用しない理由）
    other_roots = [
        r
        for r in sympy.solve(sympy.Eq(formulation.eq.lhs - formulation.eq.rhs, 0), sympy.Symbol("x"))
        if r != x_value
    ]
    assert len(other_roots) == 1
    assert other_roots[0] < 0

    # params の数値はすべて given に現れている（＝読者に見えている数だけを持つ）。
    # 例外は「言葉で書かれている値」。連続する2数の差 gap は本文では数字ではなく
    # 「正の整数（差1）／正の偶数・正の奇数（差2）」という語で示されるので、
    # 数字としては現れない。答えを漏らす値ではない（積から解かないと x は出ない）。
    _WORD_ENCODED = {"gap"}
    given_text = "".join(mr.given.values())
    for key, value in numbers.items():
        if key in _WORD_ENCODED:
            continue
        assert str(value) in given_text


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_quadratic_non_degenerate(seed):
    """非退化条件: 各場面の構成上の不変量が保たれている。"""
    # 連続する2数: 積は x0(x0+g) 型で常に正（g=1 は整数、g=2 は偶数・奇数）。
    ctx = _make_ctx("math.g3_l29.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    gap = int(numbers["gap"])
    assert gap in (1, 2)
    assert int(numbers["product"]) >= 2 * (2 + gap)

    # 数の関係: multiplier < x0（m>0 を保証する範囲）は diff>0 で確認できる
    ctx = _make_ctx("math.g3_l29.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["diff"]) > 0
    assert int(numbers["multiplier"]) >= 2

    # 長方形の面積: 差は正（横が縦より長い）
    ctx = _make_ctx("math.g3_l30.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["diff"]) > 0
    assert int(numbers["area"]) > 0

    # 正方形の変形: 面積は1辺の2乗未満（縦の長さが正であることの必要条件）
    ctx = _make_ctx("math.g3_l30.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["area"]) < int(numbers["side"]) ** 2


def test_word_problem_quadratic_derived_answer_is_a_pair():
    """g3_l29 Lv2 は「文字＝小さい方の整数・答え＝2つの整数」。answer_coeffs の合成が効いている。"""
    ctx = _make_ctx("math.g3_l29.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    gap = int(mr.params["numbers"]["gap"])
    assert [[int(sympy.sympify(v)) for v in row] for row in mr.params["answer_coeffs"]] == [
        [1, 0],
        [1, gap],
    ]
    small, large = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    assert large == small + gap
    assert mr.sub_questions[-1].steps[-1].op == "derive_asked_quantity"


def test_word_problem_quadratic_level_sep_places_letters_differently():
    """G6 の骨: 同じ「2次方程式の利用」でも Lv・unit ごとに立式の見た目が違う。"""
    from engine.packs.math.recipes.word_problem_quadratic import FORMULATION_BUILDERS

    forms = {}
    for family, level in (
        ("math.g3_l29.word_problem", 2),
        ("math.g3_l29.word_problem", 3),
        ("math.g3_l30.word_problem", 2),
        ("math.g3_l30.word_problem", 3),
    ):
        ctx = _make_ctx(family, level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
        forms[(family, level)] = FORMULATION_BUILDERS[mr.params["scenario_kind"]](**numbers)

    # g3_l29 Lv2: 積の形 x(x+g)（g は 1 か 2）。g3_l29 Lv3: x² = nx + m（積の形ではない）。
    lv29_2 = forms[("math.g3_l29.word_problem", 2)].eq
    lv29_3 = forms[("math.g3_l29.word_problem", 3)].eq
    assert sympy.Poly(
        lv29_2.lhs - lv29_2.rhs, sympy.Symbol("x")
    ).coeff_monomial(sympy.Symbol("x")) in (1, 2)
    assert lv29_3.lhs == sympy.Symbol("x") ** 2
    # g3_l30 Lv2: 積の形 x(x+d)。g3_l30 Lv3: 差の平方 (s-x)(s+x)（他の3つと系統が違う）。
    lv30_2 = forms[("math.g3_l30.word_problem", 2)]
    lv30_3 = forms[("math.g3_l30.word_problem", 3)]
    assert "(" in lv30_2.display and lv30_2.display.startswith("x(")
    assert lv30_3.display.startswith("(") and " - x)" in lv30_3.display


# ---------------------------------------------------------------------------
# 標本調査の利用（g3_l59 Lv2/Lv3・g3_l60 Lv3/Lv4）＝1 recipe で4セル
# ---------------------------------------------------------------------------
_SAMPLING_WP_CELLS = [
    ("math.g3_l59.word_problem", 2, "word_problem_sample_mark_recapture_guided", True),
    ("math.g3_l59.word_problem", 3, "word_problem_sample_defect_estimate_solo", False),
    ("math.g3_l60.word_problem", 3, "word_problem_sample_capture_recapture_guided", True),
    ("math.g3_l60.word_problem", 4, "word_problem_sample_red_ball_model_solo", False),
]


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _SAMPLING_WP_CELLS)
def test_word_problem_sampling_construct(family, level, signature, guided):
    """誘導ありは (1)標本比率→(2)母集団 の2小問、誘導なしは値の1小問（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    if guided:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
            ("(1)", "formulation"),
            ("(2)", "value"),
        ]
        assert set(mr.given) == {"scenario", "quantities"}
    else:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "value")]
        # 誘導なしは変数の設定を与えない（自分で何を比率とみるか構成する）
        assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _SAMPLING_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_sampling_double_solve_property(seed, family, level, signature, guided):
    """全小問が checker の独立再計算と一致し、推定値が answer-first の整数構成を満たす。"""
    from engine.packs.math.recipes.word_problem_sampling import solve_scene

    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_sample_survey.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # 場面の数値から solver を呼び直した結果が、答えの整数性・正値性を満たす
    # （answer-first で候補列挙時に割り切れる組だけを残しているので端数は出ない）
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    offset = int(sympy.sympify(mr.params["answer_offset"]))
    _sol, answer_value = solve_scene(mr.params["scenario_kind"], numbers, offset)
    assert answer_value.is_Integer
    assert answer_value > 0
    answer_from_mr = sympy.sympify(mr.sub_questions[-1].answer.srepr)
    assert answer_value == answer_from_mr

    # 標本内の該当個数は標本の大きさより少ない（非退化条件そのもの）
    assert numbers["sample_count"] < numbers["sample_size"]

    # params の数値はすべて given のどこかに現れている（＝読者に見えている数だけを
    # checker に渡している）。
    given_text = "".join(mr.given.values())
    for value in numbers.values():
        assert str(value) in given_text


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_sampling_ratio_subquestion_is_a_fraction(seed):
    """誘導ありの (1) は sample_count/sample_size を約分した分数（母集団の値ではない）。"""
    for family, level in (
        ("math.g3_l59.word_problem", 2),
        ("math.g3_l60.word_problem", 3),
    ):
        ctx = _make_ctx(family, level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
        expected_ratio = sympy.Rational(numbers["sample_count"], numbers["sample_size"])
        ratio_answer = sympy.sympify(mr.sub_questions[0].answer.srepr)
        assert ratio_answer == expected_ratio
        # (1) の答えは母集団の値 (2) とは別物
        value_answer = sympy.sympify(mr.sub_questions[1].answer.srepr)
        assert ratio_answer != value_answer


def test_word_problem_sampling_derived_answer_is_not_population():
    """g3_l60 Lv4 は「solver が解くのは全体・答えは白玉」。answer_offset の合成が効いている。"""
    ctx = _make_ctx("math.g3_l60.word_problem", 4)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    offset = int(sympy.sympify(mr.params["answer_offset"]))
    assert offset < 0, "赤玉の個数を引く一手（負のオフセット）"
    # 最後の一手が steps に入っている（solver の出力をそのまま答えにしていない）
    assert mr.sub_questions[0].steps[-1].op == "derive_asked_quantity"
    assert mr.sub_questions[0].answer.display.endswith("個")

    # ほかの3セルは offset=0（solver の出力がそのまま答え）
    for family, level in (
        ("math.g3_l59.word_problem", 2),
        ("math.g3_l59.word_problem", 3),
        ("math.g3_l60.word_problem", 3),
    ):
        ctx2 = _make_ctx(family, level)
        rng2 = derive_rng(ctx2.family, ctx2.level, ctx2.purpose, seed=1)
        mr2 = REGISTRY.recipe(ctx2.spec_level.recipe)(ctx2, rng2)
        assert int(sympy.sympify(mr2.params["answer_offset"])) == 0


def test_word_problem_sampling_level_sep_uses_different_solver():
    """G6 の骨: g3_l59 Lv2/Lv3 は「場面文に出ている量／求める量」が入れ替わり、
    呼ぶ solver 自体が違う（数値域の違いだけの偽レベルではない）。
    """
    from engine.packs.math.recipes.word_problem_sampling import _SAMPLING_SOLVERS

    ctx2 = _make_ctx("math.g3_l59.word_problem", 2)
    rng2 = derive_rng(ctx2.family, ctx2.level, ctx2.purpose, seed=1)
    mr2 = REGISTRY.recipe(ctx2.spec_level.recipe)(ctx2, rng2)

    ctx3 = _make_ctx("math.g3_l59.word_problem", 3)
    rng3 = derive_rng(ctx3.family, ctx3.level, ctx3.purpose, seed=1)
    mr3 = REGISTRY.recipe(ctx3.spec_level.recipe)(ctx3, rng3)

    assert (
        _SAMPLING_SOLVERS[mr2.params["scenario_kind"]]
        != _SAMPLING_SOLVERS[mr3.params["scenario_kind"]]
    )
    # Lv2 は params.numbers に known_estimate（既知の印つき総数）を持つ
    assert "known_estimate" in mr2.params["numbers"]
    # Lv3 は params.numbers に population_size（既知の母集団）を持つ
    assert "population_size" in mr3.params["numbers"]


# ---------------------------------------------------------------------------
# 比例・反比例の利用（g1_l29/g1_l33 × Lv2/Lv3）＝1 recipe で4セル
# ---------------------------------------------------------------------------
_PROPORTION_WP_CELLS = [
    ("math.g1_l29.word_problem", 2, "word_problem_direct_proportion_rate", True),
    ("math.g1_l29.word_problem", 3, "word_problem_direct_proportion_unit_convert", False),
    ("math.g1_l33.word_problem", 2, "word_problem_inverse_proportion_area", True),
    ("math.g1_l33.word_problem", 3, "word_problem_inverse_proportion_worker_days", False),
]


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _PROPORTION_WP_CELLS)
def test_word_problem_proportion_construct(family, level, signature, guided):
    """誘導ありは (1)式→(2)値 の2小問、誘導なしは値の1小問（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    if guided:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
            ("(1)", "formulation"),
            ("(2)", "value"),
        ]
        assert set(mr.given) == {"scenario", "quantities"}
    else:
        assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "value")]
        # 誘導なしは変数の設定を与えない（自分で x, y をおく）
        assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "guided"), _PROPORTION_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_proportion_double_solve_property(seed, family, level, signature, guided):
    """全小問が checker の独立再計算と一致し、答えが a=xy(反比例)/y=ax(比例)を実際に満たす。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_proportion.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    from engine.packs.math.recipes.word_problem_proportion import solve_scene

    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    formulation, value_answer, _ = solve_scene(mr.params["scenario_kind"], numbers)
    # a は正の整数（answer-first で逆算しているので端数は出ない）
    assert formulation.a.is_Integer and formulation.a > 0
    # 値も正の整数（km 変換セルも1000の倍数だけを候補に残しているので端数は出ない）
    value = sympy.sympify(value_answer.srepr)
    assert value.is_Integer and value > 0

    # 読者が見ている数値（given か、誘導なし/目標値のみ小問文にある場合は
    # context_slots の ask_formulation/ask_value）はすべてどこかに現れている
    # （＝checker に渡す数値を隠していない）。
    given_text = "".join(mr.given.values())
    slot_text = "".join(
        str(v) for k, v in mr.context_slots.items() if k in ("ask_formulation", "ask_value")
    )
    readable_text = given_text + slot_text
    for num in numbers.values():
        assert str(num) in readable_text


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_proportion_non_degenerate(seed):
    """非退化条件: g1_l29 Lv2 は長さ≠1（重さそのまま聞き直しにならない）。
    g1_l33 Lv2 は縦≠横（正方形は「長方形」の題材と矛盾する）。
    g1_l33 Lv3 は人数を変える（同じ人数を聞き直す退化を避ける）。
    """
    ctx = _make_ctx("math.g1_l29.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["length"]) != 1

    ctx = _make_ctx("math.g1_l33.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    area, side = int(numbers["area"]), int(numbers["side"])
    assert area % side == 0
    assert side != area // side

    ctx = _make_ctx("math.g1_l33.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["workers1"]) != int(numbers["workers0"])


def test_word_problem_proportion_unit_convert_has_extra_step():
    """g1_l29 Lv3 は m→km の一手（convert_unit）が Lv2 に無い op として最後に入る。"""
    ctx = _make_ctx("math.g1_l29.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    lv3 = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert lv3.sub_questions[0].steps[-1].op == "convert_unit"
    assert lv3.sub_questions[0].answer.display.endswith("km")

    ctx2 = _make_ctx("math.g1_l29.word_problem", 2)
    rng2 = derive_rng(ctx2.family, ctx2.level, ctx2.purpose, seed=1)
    lv2 = REGISTRY.recipe(ctx2.spec_level.recipe)(ctx2, rng2)
    assert all(s.op != "convert_unit" for sq in lv2.sub_questions for s in sq.steps)


def test_word_problem_proportion_area_vs_worker_days_level_sep():
    """g1_l33 の G6 の骨: Lv2 は a（面積）が本文に直接与えられ点の代入が要らない
    （steps は form_expression の1手のみ）。Lv3 は a=x0*y0 を「4人で6日」のような
    1組の対応から求めるので、substitute_point が余分に入る。
    """
    ctx2 = _make_ctx("math.g1_l33.word_problem", 2)
    rng2 = derive_rng(ctx2.family, ctx2.level, ctx2.purpose, seed=1)
    lv2 = REGISTRY.recipe(ctx2.spec_level.recipe)(ctx2, rng2)
    assert [s.op for s in lv2.sub_questions[0].steps] == ["form_expression"]

    ctx3 = _make_ctx("math.g1_l33.word_problem", 3)
    rng3 = derive_rng(ctx3.family, ctx3.level, ctx3.purpose, seed=1)
    lv3 = REGISTRY.recipe(ctx3.spec_level.recipe)(ctx3, rng3)
    assert [s.op for s in lv3.sub_questions[0].steps][:2] == [
        "substitute_point",
        "form_expression",
    ]


# ---------------------------------------------------------------------------
# 関係を表す文章題（g1_l19 等式・g1_l20 不等式）＝1 recipe で4セル
#
# word_problem_linear/system と違い、値を求める小問が無い＝常に
# asked="formulation" の1小問（「解かずに関係を式で表す」台帳の型）。
# ---------------------------------------------------------------------------
_RELATION_WP_CELLS = [
    ("math.g1_l19.word_problem", 1, "word_problem_equality_price_count"),
    ("math.g1_l19.word_problem", 2, "word_problem_equality_both_sides"),
    ("math.g1_l20.word_problem", 1, "word_problem_inequality_price_count"),
    ("math.g1_l20.word_problem", 2, "word_problem_inequality_both_sides"),
]


@pytest.mark.parametrize(("family", "level", "signature"), _RELATION_WP_CELLS)
def test_word_problem_relation_construct(family, level, signature):
    """常に asked=formulation の1小問（値を求める小問は無い）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "formulation")]
    # x は場面文の中で直接定義される＝ given.quantities は使わない
    assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature"), _RELATION_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_relation_double_solve_property(seed, family, level, signature):
    """checker の独立再計算と一致し、params の全数値が given.scenario に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_relation.double_solve")
    solution = checker(mr)
    assert solution.answer.srepr == mr.sub_questions[0].answer.srepr

    # word_problem のセルの契約: params の全数値が given.scenario に文字列として現れる
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    for value in numbers.values():
        assert str(value) in mr.given["scenario"]

    # 答え（関係式）は必ず x を自由変数として含む式（値ではない）
    answer = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert answer.free_symbols == {sympy.Symbol("x")}


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_relation_non_degenerate(seed):
    """非退化条件: 両辺に文字のセルは mult=1（「1倍して」は不自然）を除外。"""
    for family, level in (
        ("math.g1_l19.word_problem", 2),
        ("math.g1_l20.word_problem", 2),
    ):
        ctx = _make_ctx(family, level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
        assert int(numbers["mult"]) != 1


@pytest.mark.parametrize("family", ["math.g1_l19.word_problem", "math.g1_l20.word_problem"])
def test_word_problem_relation_level_sep_is_structural(family):
    """Lv1 と Lv2 で steps の op 列が相異する（＝fp が分かれる・P-1 回帰の防止）。

    由来: 初稿は両レベルとも (find_relation, formulate_relation) の2手で、given/asked/
    小問数も同じだったため **fp が完全に一致**していた（eval の dup_rate が
    「同一 family 内で署名跨ぎ fp 衝突」として検出）。Lv2 は比べる数量が両方とも x の
    式になるので、それぞれを別々に表してから結ぶ3手にした。
    """
    ops = {}
    for level in (1, 2):
        ctx = _make_ctx(family, level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        ops[level] = [s.op for s in mr.sub_questions[0].steps]
    assert ops[1] == ["find_relation", "formulate_relation"]
    assert ops[2] == [
        "express_first_quantity",
        "express_second_quantity",
        "formulate_relation",
    ]
    assert ops[1] != ops[2]


def test_word_problem_relation_inequality_both_sides_answer_is_tuple():
    """Lv2 不等式は2条件を本文の記述順 Tuple(Gt, Lt) で機械表現する（And ではない）。"""
    ctx = _make_ctx("math.g1_l20.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    answer = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert isinstance(answer, sympy.Tuple)
    assert isinstance(answer[0], sympy.StrictGreaterThan)
    assert isinstance(answer[1], sympy.StrictLessThan)


# ---------------------------------------------------------------------------
# 数量を文字式で表す文章題（g1_l12 Lv1/Lv2・g1_l15 Lv1/Lv2/Lv3）＝1 recipe で5セル
# ---------------------------------------------------------------------------
_EXPR_WP_CELLS = [
    ("math.g1_l12.word_problem", 1, "word_problem_expression_price_count"),
    ("math.g1_l12.word_problem", 2, "word_problem_expression_discount"),
    ("math.g1_l15.word_problem", 1, "word_problem_expression_distance"),
    ("math.g1_l15.word_problem", 2, "word_problem_expression_unit_convert"),
    ("math.g1_l15.word_problem", 3, "word_problem_expression_profit_multi_letter"),
]


@pytest.mark.parametrize(("family", "level", "signature"), _EXPR_WP_CELLS)
def test_word_problem_expression_construct(family, level, signature):
    """1小問・誘導なし（asked=formulation・答えは式）＝frame の asked_vocab の骨。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "formulation")]
    # 変数の設定は場面文自身が担う（"x本"のように）ので given.quantities は使わない。
    assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）。
    assert "answer" not in mr.params
    # 答えは自由変数を含む式（定数に退化していない）。
    answer_expr = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert answer_expr.free_symbols


@pytest.mark.parametrize(("family", "level", "signature"), _EXPR_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_expression_double_solve_property(seed, family, level, signature):
    """checker（Solution単体）が MR の答えと一致し、答え表示が場面文に漏洩しない。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_expression.double_solve")
    solution = checker(mr)
    assert solution.answer.srepr == mr.sub_questions[0].answer.srepr

    # params の全数値/文字は given.scenario に文字列として現れる（誘導の材料が本文にある）。
    scenario = mr.given["scenario"]
    for value in mr.params["numbers"].values():
        assert value in scenario

    # G-Q5t 自衛: 答え表示（空白除去）が場面文+小問文（空白除去）に部分文字列で現れない。
    from engine.packs.math.recipes.letter_expr import _leaks

    given_full = scenario + mr.context_slots["ask_value"]
    answer_display = mr.sub_questions[0].answer.display
    assert not _leaks(answer_display, given_full), (
        f"答え表示 {answer_display!r} が場面文に部分文字列で現れている: {given_full!r}"
    )


def test_word_problem_expression_level_sep_is_structural():
    """G6 の骨: level_sep は「式の構造」で作る（単項式→分数係数→多文字の差）。"""
    from engine.packs.math.recipes.word_problem_expression import FORMULATION_BUILDERS

    # g1_l12 Lv1: 単項式（x 係数が整数）
    lv1 = _make_ctx("math.g1_l12.word_problem", 1)
    mr1 = REGISTRY.recipe(lv1.spec_level.recipe)(lv1, derive_rng(lv1.family, lv1.level, lv1.purpose, 1))
    numbers1 = mr1.params["numbers"]
    formulation1 = FORMULATION_BUILDERS[mr1.params["scenario_kind"]](**numbers1)
    poly1 = sympy.Poly(sympy.sympify(formulation1.expr_str), sympy.Symbol("x"))
    assert poly1.LC().is_Integer

    # g1_l12 Lv2: 割合が係数に入る（分数係数の1項＝同類項を実際にまとめている）
    lv2 = _make_ctx("math.g1_l12.word_problem", 2)
    mr2 = REGISTRY.recipe(lv2.spec_level.recipe)(lv2, derive_rng(lv2.family, lv2.level, lv2.purpose, 1))
    answer2 = sympy.sympify(mr2.sub_questions[0].answer.srepr)
    coeff2 = answer2.as_coefficients_dict()[sympy.Symbol("a")]
    assert coeff2.q > 1, "割引き後の係数は分数（同類項をまとめて1項に整理している）"

    # g1_l15 Lv3: 多文字の差（同類項でない2項＝ x*y - z の形が保たれる）
    lv3 = _make_ctx("math.g1_l15.word_problem", 3)
    mr3 = REGISTRY.recipe(lv3.spec_level.recipe)(lv3, derive_rng(lv3.family, lv3.level, lv3.purpose, 1))
    answer3 = sympy.sympify(mr3.sub_questions[0].answer.srepr)
    assert len(answer3.free_symbols) == 3
    assert isinstance(answer3, sympy.Add) and len(answer3.args) == 2


def test_word_problem_expression_profit_uses_distinct_letters():
    """g1_l15 Lv3: 3文字は毎回相異なる（重なると式の意味が壊れる）。letter_expr.py の
    `_NOTATION_LETTERS` プールから引く＝新しい抽選ヘルパを作らない。
    """
    ctx = _make_ctx("math.g1_l15.word_problem", 3)
    for seed in range(20):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        letters = set(mr.params["numbers"].values())
        assert len(letters) == 3, "count_letter/price_letter/cost_letter は相異なる"


# ---------------------------------------------------------------------------
# 1次関数の利用（g2_l28 Lv2/Lv3・g2_l30 Lv3）＝1 recipe で3セル
# ---------------------------------------------------------------------------
_LINEAR_FUNCTION_WP_CELLS = [
    ("math.g2_l28.word_problem", 2, "word_problem_linear_two_point_eval", "spring_two_point", 2),
    ("math.g2_l28.word_problem", 3, "word_problem_linear_piecewise_tank", "tank_piecewise", 3),
    ("math.g2_l30.word_problem", 3, "word_problem_linear_meeting_intersection", "meeting_intersection", 2),
]


@pytest.mark.parametrize(("family", "level", "signature", "kind", "n_sub"), _LINEAR_FUNCTION_WP_CELLS)
def test_word_problem_linear_function_construct(family, level, signature, kind, n_sub):
    """scenario_kind ごとに小問数が違う（level_sep の骨: 1直線=2小問／折れ線=3小問）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert mr.params["scenario_kind"] == kind
    assert len(mr.sub_questions) == n_sub
    assert mr.sub_questions[-1].asked == "value"
    assert all(sq.asked == "formulation" for sq in mr.sub_questions[:-1])
    assert set(mr.given) == {"scenario", "quantities"}
    assert mr.visual_plan is None
    # 答えは params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "kind", "n_sub"), _LINEAR_FUNCTION_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_linear_function_double_solve_property(seed, family, level, signature, kind, n_sub):
    """全小問が checker の独立再計算と一致し、params の数値が本文のどこかに現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_linear_function.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions) == n_sub
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # params の全数値が、この recipe の場面文(given)または小問文(context_slots の
    # ask_*)のどこかに文字列として現れる（本文の数値を読み違えても checker が
    # 気づかない経路が無いことの確認。word_problem のセル共通の property）。
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    visible_text = "".join(mr.given.values()) + "".join(
        v for k, v in mr.context_slots.items() if k.startswith("ask_")
    )
    for value in numbers.values():
        assert str(value) in visible_text


@pytest.mark.parametrize("seed", range(30))
def test_word_problem_linear_function_non_degenerate(seed):
    """非退化条件: ばねは x1≠x2、水そうは r1≠r2 かつ target が第2区間内、出会いは va≠vb。"""
    ctx = _make_ctx("math.g2_l28.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["x1"]) != int(numbers["x2"])

    ctx = _make_ctx("math.g2_l28.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    t1, r1, r2, target = (int(numbers[k]) for k in ("t1", "r1", "r2", "target"))
    assert r1 != r2
    # target は第2区間 (x>=t1) で実現する: 逆算した x0 が t1 より大きい
    b2 = r1 * t1 - r2 * t1
    x0 = sympy.Rational(target - b2, r2)
    assert x0 > t1

    ctx = _make_ctx("math.g2_l30.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    numbers = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng).params["numbers"]
    assert int(numbers["va"]) != int(numbers["vb"])


# ---------------------------------------------------------------------------
# 確率の利用（g2_l51/l52/l53/l54 の word_problem）＝1 recipe で6セル
# ---------------------------------------------------------------------------
#   (family, level, signature, 小問数)
# 小問数は level_sep の骨（誘導あり＝2ないし3小問・誘導なし＝1小問）。
_PROBABILITY_WP_CELLS = [
    ("math.g2_l51.word_problem", 2, "word_problem_bag_one_draw_guided", 2),
    ("math.g2_l51.word_problem", 3, "word_problem_multiple_union", 1),
    ("math.g2_l52.word_problem", 3, "word_problem_two_dice_product_at_least", 1),
    ("math.g2_l53.word_problem", 3, "word_problem_lottery_at_least_one", 1),
    ("math.g2_l54.word_problem", 2, "word_problem_two_balls_complement_guided", 2),
    ("math.g2_l54.word_problem", 3, "word_problem_dice_repeat_at_least_one", 1),
    ("math.g2_l52.word_problem", 2, "word_problem_coin_toss_count_and_probability", 2),
    ("math.g2_l53.word_problem", 2, "word_problem_two_digit_cards", 2),
    ("math.g2_l54.word_problem", 4, "word_problem_at_least_two_colors", 1),
    ("math.exam_l5.word_problem", 3, "exam_word_problem_dice_guided_three", 3),
    ("math.exam_l5.word_problem", 4, "exam_word_problem_at_least_one_complement", 1),
]

# 誘導ありセルのうち (1) が「全部で何通りか」＝場合の数（確率ではない）のもの。
# 確率の値域チェックの対象外にする（暗黙のすり抜けを作らないため明示列挙する）。
_COUNT_FIRST_SUB_QUESTION_SIGNATURES = frozenset({
    "word_problem_bag_one_draw_guided",
    "word_problem_coin_toss_count_and_probability",
    "word_problem_two_digit_cards",
    "exam_word_problem_dice_guided_three",
})


@pytest.mark.parametrize(("family", "level", "signature", "n_subs"), _PROBABILITY_WP_CELLS)
def test_word_problem_probability_construct(family, level, signature, n_subs):
    """小問はすべて value で、数は誘導の有無で決まる（＝level_sep の骨）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
        (f"({i + 1})", "value") for i in range(n_subs)
    ]
    # 確率の文章題は変数の設定（quantities）を持たない＝given は scenario のみ。
    assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    # 答え（確率）は params に入っていない（checker が独立に再計算できるようにするため）
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "n_subs"), _PROBABILITY_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_probability_double_solve_property(seed, family, level, signature, n_subs):
    """全小問が checker の独立再計算と一致し、params の全数値が given.scenario に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_probability.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # word_problem 共通の property: params の全数値が given.scenario に文字列として
    # 現れる（本文の数値を読み違えても checker が気づかない、という穴を作らないため）。
    # ただし faces=6（標準のさいころ）は既存 find_value 側と同じ規約で
    # 「1からNまでの目が出る」という前置きを省く（＝6という数値そのものは本文に
    # 出ない）。これは probability.py の probability_two_dice_recipe 等と同じ既存の
    # 慣習であり、この鍵だけ対象外にする。
    given_text = "".join(mr.given.values())
    for key, value in mr.params["numbers"].items():
        if key == "faces" and int(sympy.sympify(value)) == 6:
            continue
        # condition は「和が○以上になる」「積が○になる」のように**語で**本文に
        # 書かれる（"sum_at_least" という符号そのものは本文に出ない）。
        # 答えを漏らす値ではない（条件が分かっても数え上げは要る）。
        if key == "condition":
            continue
        assert str(value) in given_text
    for value in mr.params["slots"].values():
        assert str(value) in given_text

    # 答えは確率（0以上1以下の有理数）。ただし bag_one_draw の (1) は「何通りか」
    # という場合の数であって確率ではないので、その小問だけは対象外にする。
    for i, sol in enumerate(solutions):
        if signature in _COUNT_FIRST_SUB_QUESTION_SIGNATURES and i == 0:
            continue
        p = sympy.sympify(sol.answer.srepr)
        assert p.is_Rational
        assert 0 <= p <= 1


def test_word_problem_probability_non_degenerate(seed=1):
    """非退化条件: 包除は重なりが実在・くじは「両方はずれ」が起こりうる・積条件は退化しない。"""
    for level in (2, 3):
        ctx = _make_ctx("math.g2_l51.word_problem", level)
        for seed_i in range(10):
            rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed_i)
            mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
            if level == 3:
                numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
                lcm_ab = numbers["div_a"] * numbers["div_b"] // math.gcd(numbers["div_a"], numbers["div_b"])
                assert lcm_ab <= numbers["n"], "重なりが実在しないと包除の引き算が空振りする"
                assert numbers["div_a"] % numbers["div_b"] != 0
                assert numbers["div_b"] % numbers["div_a"] != 0

    ctx = _make_ctx("math.g2_l53.word_problem", 3)
    for seed_i in range(10):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed_i)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
        assert numbers["n"] - numbers["k"] >= 2, "戻さず2本引いて両方はずれる余地が要る"
        assert numbers["k"] >= 1


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_probability_counting_cells_non_degenerate(seed):
    """数え上げ系3セルの非退化: 答えが 0 や 1 に潰れる構成を作らない。"""
    # g2_l52 Lv2: 注目する枚数は 0 でも全部でもない（確率が 1/2^n に退化しない）。
    ctx = _make_ctx("math.g2_l52.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    coins = int(mr.params["numbers"]["coins"])
    face_count = int(mr.params["numbers"]["face_count"])
    assert 0 < face_count < coins
    assert str(mr.params["numbers"]["face"]) in ("表", "裏")
    assert int(sympy.sympify(mr.sub_questions[0].answer.srepr)) == 2**coins

    # g2_l53 Lv2: 条件を満たす整数が「全部」でも「ゼロ」でもない（偶数・奇数の両方が
    # できるように、カードに偶数と奇数がどちらも含まれている必要がある）。
    ctx = _make_ctx("math.g2_l53.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    p = sympy.sympify(mr.sub_questions[1].answer.srepr)
    assert 0 < p < 1, "条件を満たす整数が全部またはゼロだと確率の問題として退化する"

    # g2_l54 Lv4: 余事象「全部同じ色」が起こりうる（＝答えが常に 1 にならない）。
    ctx = _make_ctx("math.g2_l54.word_problem", 4)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    numbers = mr.params["numbers"]
    draws = int(numbers["draws"])
    counts = [int(numbers[f"count_{s}"]) for s in ("a", "b", "c")]
    assert max(counts) >= draws, "どの色も draws 個未満だと余事象が起こりえず答えが 1 に退化する"
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) < 1


def test_word_problem_probability_guided_uses_complement_of_first():
    """g2_l54 Lv2: (2)は(1)の余事象（2色しかないので「白が0個」＝「2個とも赤」）。"""
    ctx = _make_ctx("math.g2_l54.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    p1 = sympy.sympify(mr.sub_questions[0].answer.srepr)
    p2 = sympy.sympify(mr.sub_questions[1].answer.srepr)
    assert (p1 + p2).equals(1)


# ---------------------------------------------------------------------------
# 比例・反比例の利用＋相対度数としての確率（g1_l36 / g1_l59 の word_problem）
# ＝1 recipe で4セル
# ---------------------------------------------------------------------------
_PROPORTION_FREQUENCY_WP_CELLS = [
    ("math.g1_l36.word_problem", 2, "word_problem_proportion_judge_and_use", 2),
    ("math.g1_l36.word_problem", 3, "word_problem_proportion_meet_two_motions", 1),
    ("math.g1_l59.word_problem", 2, "word_problem_relative_frequency_predict", 2),
    ("math.g1_l59.word_problem", 3, "word_problem_defect_rate_estimate", 1),
]


@pytest.mark.parametrize(("family", "level", "signature", "n_sub"), _PROPORTION_FREQUENCY_WP_CELLS)
def test_word_problem_proportion_frequency_construct(family, level, signature, n_sub):
    """小問数が spec の asked と一致し、答えは params に入らない。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [sq.label for sq in mr.sub_questions] == [f"({i + 1})" for i in range(n_sub)]
    assert [sq.asked for sq in mr.sub_questions] == list(ctx.spec_level.asked)
    assert mr.visual_plan is None
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "n_sub"), _PROPORTION_FREQUENCY_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_proportion_frequency_double_solve_property(seed, family, level, signature, n_sub):
    """全小問が checker の独立再計算と一致し、params の全数値が場面文に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_proportion_frequency.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions) == n_sub
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # word_problem 共通の property: params の全数値が場面文（given＋小問文）に
    # 文字列として現れる＝本文の数値を取り違えても checker が気づかない穴を塞ぐ。
    shown = "".join(mr.given.values()) + "".join(str(v) for v in mr.context_slots.values())
    for value in mr.params["numbers"].values():
        assert str(value) in shown
    for value in mr.params["slots"].values():
        assert str(value) in shown


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_proportion_frequency_non_degenerate(seed):
    """非退化条件: 追いつきは後発が速い・実験の相対度数は 0<p<1・予測は整数。"""
    ctx = _make_ctx("math.g1_l36.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    assert numbers["speed_fast"] > numbers["speed_slow"], "後発が遅いと追いつけない"
    assert numbers["head_start"] > 0, "先発の出発が同時だと追いつく場面にならない"
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) > 0

    for family, level in (("math.g1_l59.word_problem", 2), ("math.g1_l59.word_problem", 3)):
        ctx = _make_ctx(family, level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        numbers = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
        occurred = numbers.get("occurred", numbers.get("defects"))
        total = numbers.get("total", numbers.get("sample"))
        assert 0 < occurred < total, "相対度数が 0 や 1 だと見積もりが退化する"
        # 予測（最後の小問）は整数個／整数回に収まる＝丸めの指示なしで一意に定まる。
        assert sympy.sympify(mr.sub_questions[-1].answer.srepr).is_Integer


# ---------------------------------------------------------------------------
# 平方根の利用＋既存クラスタの取りこぼし（g3_l23 / g1_l1 / g1_l11 の word_problem）
# ＝1 recipe で4セル
# ---------------------------------------------------------------------------
_SQRT_MISC_WP_CELLS = [
    ("math.g3_l23.word_problem", 2, "word_problem_square_plot_approx", 2),
    ("math.g3_l23.word_problem", 3, "word_problem_rectangle_ratio_side", 1),
    ("math.g1_l1.word_problem", 1, "word_problem_signed_reference", 2),
    ("math.g1_l11.word_problem", 2, "word_problem_square_multiplier", 2),
]


@pytest.mark.parametrize(("family", "level", "signature", "n_sub"), _SQRT_MISC_WP_CELLS)
def test_word_problem_sqrt_misc_construct(family, level, signature, n_sub):
    """小問数が spec の asked と一致し、答えは params に入らない。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [sq.label for sq in mr.sub_questions] == [f"({i + 1})" for i in range(n_sub)]
    assert [sq.asked for sq in mr.sub_questions] == list(ctx.spec_level.asked)
    assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "n_sub"), _SQRT_MISC_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_sqrt_misc_double_solve_property(seed, family, level, signature, n_sub):
    """全小問が checker の独立再計算と一致し、params の全数値が場面文に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_sqrt_misc.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions) == n_sub
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # word_problem 共通の property: params の全数値が場面文に現れる。
    for value in mr.params["numbers"].values():
        assert str(value) in mr.given["scenario"]


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_sqrt_misc_non_degenerate(seed):
    """非退化条件: 平方根セルは答えが必ず根号を含み、平方数化はかける数が1にならない。"""
    for level in (2, 3):
        ctx = _make_ctx("math.g3_l23.word_problem", level)
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        # 根号を使って表す小問（両レベルとも(1)）の答えは無理数＝a√b の形。
        side = sympy.sympify(mr.sub_questions[0].answer.srepr)
        assert not side.is_Rational, "根号が消えると『根号を使って表せ』が成り立たない"

    ctx = _make_ctx("math.g1_l11.word_problem", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    n = int(sympy.sympify(mr.params["numbers"]["n"]))
    multiplier = int(sympy.sympify(mr.sub_questions[1].answer.srepr))
    assert multiplier > 1, "かける数が1だと元の数がすでに平方数＝設問が退化する"
    assert multiplier != n, "かける数が元の数と一致すると問題文の数が答えになる（G-Q5t の実害）"
    assert sympy.sqrt(n * multiplier).is_Integer, "かけたあとが平方数になっていない"


# ---------------------------------------------------------------------------
# 関数 y=ax² の利用（g3_l32 / g3_l36 / g3_l38 の word_problem）＝1 recipe で4セル
# ---------------------------------------------------------------------------
_QUADRATIC_FUNCTION_WP_CELLS = [
    ("math.g3_l32.word_problem", 2, "word_problem_quadratic_given_equation"),
    ("math.g3_l36.word_problem", 2, "word_problem_quadratic_determine_then_evaluate"),
    ("math.g3_l36.word_problem", 3, "word_problem_quadratic_determine_then_inverse"),
    ("math.g3_l38.word_problem", 3, "word_problem_quadratic_moving_point_area"),
]


@pytest.mark.parametrize(("family", "level", "signature"), _QUADRATIC_FUNCTION_WP_CELLS)
def test_word_problem_quadratic_function_construct(family, level, signature):
    """小問の asked が spec と一致し、導出値（比例定数）も答えも params に入らない。"""
    from engine.packs.math.recipes.word_problem_quadratic_function import ASKED_KINDS

    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    kind = str(mr.params["scenario_kind"])
    assert [sq.asked for sq in mr.sub_questions] == list(ASKED_KINDS[kind])
    assert [sq.asked for sq in mr.sub_questions] == list(ctx.spec_level.asked)
    assert mr.visual_plan is None
    assert "answer" not in mr.params
    # 比例定数 a は本文に出ていない導出値なので params に置かない（置くと本文の数値を
    # 書き間違えても checker が通ってしまう）。
    assert "a" not in mr.params["numbers"] or kind == "given_equation"


@pytest.mark.parametrize(("family", "level", "signature"), _QUADRATIC_FUNCTION_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_quadratic_function_double_solve_property(seed, family, level, signature):
    """全小問が checker の独立再計算と一致し、params の全数値が本文に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_quadratic_function.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # word_problem 共通の property: params の全数値が場面文（given＋小問文）に現れる。
    shown = "".join(mr.given.values()) + "".join(str(v) for v in mr.context_slots.values())
    for value in mr.params["numbers"].values():
        assert str(value) in shown
    for value in mr.params["slots"].values():
        assert str(value) in shown


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_quadratic_function_non_degenerate(seed):
    """非退化条件: 落下は比例定数が自然な帯・動点は区間ごとに式の型が変わる。"""
    ctx = _make_ctx("math.g3_l36.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    x0, y0 = (int(mr.params["numbers"][k]) for k in ("x0", "y0"))
    assert sympy.Rational(y0, x0 * x0) in (4, 5, 6), "落下運動の比例定数は現実に近い帯に保つ"

    ctx = _make_ctx("math.g3_l38.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    first = sympy.sympify(mr.sub_questions[0].answer.srepr)
    second = sympy.sympify(mr.sub_questions[1].answer.srepr)
    assert first.has(sympy.Symbol("x")), "第1区間は x に比例する式でなければならない"
    assert not second.has(sympy.Symbol("x")), "第2区間は一定の面積でなければならない"
    # 点名は答えに影響しない surface だが、dup_key に効かせるため params に入れる。
    assert len(set(str(mr.params["slots"]["vertices"]))) == 4
    assert str(mr.params["slots"]["moving_point"]) not in str(mr.params["slots"]["vertices"])


# ---------------------------------------------------------------------------
# 三平方の定理の利用（g3_l53 / g3_l55 / g3_l56 の word_problem）＝1 recipe で3セル
# ---------------------------------------------------------------------------
_PYTHAGOREAN_WP_CELLS = [
    ("math.g3_l53.word_problem", 3, "word_problem_rhombus_diagonal_area_guided"),
    ("math.g3_l55.word_problem", 3, "word_problem_square_pyramid_height_volume_guided"),
    ("math.g3_l56.word_problem", 3, "word_problem_box_surface_shortest_path_guided"),
]


@pytest.mark.parametrize(("family", "level", "signature"), _PYTHAGOREAN_WP_CELLS)
def test_word_problem_pythagorean_construct(family, level, signature):
    """誘導あり2小問（どちらも value）で、答えは params に入らない。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [
        ("(1)", "value"),
        ("(2)", "value"),
    ]
    assert set(mr.given) == {"scenario"}
    assert mr.visual_plan is None
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature"), _PYTHAGOREAN_WP_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_word_problem_pythagorean_double_solve_property(seed, family, level, signature):
    """全小問が checker の独立再計算と一致し、params の全数値が場面文に現れる。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.word_problem_pythagorean.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr

    # word_problem 共通の property: params の全数値が場面文（given＋小問文）に現れる。
    shown = "".join(mr.given.values()) + "".join(str(v) for v in mr.context_slots.values())
    for value in mr.params["numbers"].values():
        assert str(value) in shown
    # 点名は答えに影響しない surface だが、dup_key に効かせるため params に入れる。
    for value in mr.params["slots"].values():
        assert str(value) in shown


@pytest.mark.parametrize("seed", range(20))
def test_word_problem_pythagorean_non_degenerate(seed):
    """非退化条件: 三平方が実際に使える（斜辺が他の辺より長い）形だけを構成する。"""
    ctx = _make_ctx("math.g3_l53.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    side, diagonal = (int(mr.params["numbers"][k]) for k in ("side", "diagonal"))
    assert diagonal < 2 * side, "対角線が辺の2倍以上だとひし形が閉じない"

    ctx = _make_ctx("math.g3_l55.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    base, lateral = (int(mr.params["numbers"][k]) for k in ("base_edge", "lateral_edge"))
    # 側辺は底面の対角線の半分より長い＝高さが正の実数になる（錐体が立つ）。
    assert 2 * lateral**2 > base**2

    ctx = _make_ctx("math.g3_l56.word_problem", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    for key in ("edge_a", "edge_b", "height"):
        assert int(mr.params["numbers"][key]) > 0


# ---------------------------------------------------------------------------
# C4 g1 比例・反比例 graph_table 横展開（g1_l30/l31/l32/l34/l35/l36・12セル）
#
# 「かく」セル（GraphAnswer）と「読む」セル（SymbolicAnswer）が混在するクラスタ。
# ゲートが素通りさせる退化（答えが 0 に潰れる／格子点でない／比べる3本が一意に
# 決まらない／問題図に答えを先出しする）を property で固定する。
# ---------------------------------------------------------------------------
_C4_GRAPH_CELLS = [
    ("math.g1_l30.graph_table", 1, "read_coordinate_from_components", "read_point", 3),
    ("math.g1_l30.graph_table", 2, "reflect_point_origin_and_x_axis", "read_point", 3),
    ("math.g1_l31.graph_table", 1, "read_value_on_proportion_graph", "read_point", 2),
    ("math.g1_l31.graph_table", 2, "draw_proportion_graph_two_points", "draw_graph", 4),
    ("math.g1_l31.graph_table", 3, "compare_three_proportion_graphs", "read_slope_intercept", 3),
    ("math.g1_l32.graph_table", 1, "read_lattice_point_on_proportion_graph", "read_point", 2),
    ("math.g1_l34.graph_table", 1, "read_value_on_hyperbola_graph", "read_point", 2),
    ("math.g1_l34.graph_table", 2, "draw_hyperbola_from_table", "draw_graph", 4),
    ("math.g1_l34.graph_table", 3, "compare_three_hyperbolas", "read_slope_intercept", 3),
    ("math.g1_l35.graph_table", 1, "read_lattice_point_on_hyperbola_graph", "read_point", 2),
    ("math.g1_l36.graph_table", 2, "graph_situation_proportion_read_value", "read_point", 4),
    ("math.g1_l36.graph_table", 3, "graph_two_plans_read_crossover", "read_intersection", 4),
]

# 「かく」セル = 答えの線/曲線を模範解答図だけに描くセル
_C4_DRAW_CELLS = {("math.g1_l31.graph_table", 2), ("math.g1_l34.graph_table", 2)}
# 問題図が空の方眼でなければならないセル（読む対象・答えを先出ししない）
_C4_EMPTY_GRID_CELLS = _C4_DRAW_CELLS | {
    ("math.g1_l30.graph_table", 1), ("math.g1_l30.graph_table", 2),
    ("math.g1_l31.graph_table", 3), ("math.g1_l34.graph_table", 3),
    ("math.g1_l36.graph_table", 2), ("math.g1_l36.graph_table", 3),
}


def _c4_mr(family: str, level: int, seed: int):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    return ctx, REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)


@pytest.mark.parametrize("family,level,signature,asked,n_steps", _C4_GRAPH_CELLS)
def test_c4_graph_construct(family, level, signature, asked, n_steps):
    ctx, mr = _c4_mr(family, level, 1)
    assert mr.signature == signature
    sq = mr.sub_questions[0]
    assert sq.asked == asked
    assert len(sq.steps) == n_steps
    assert sq.concept_tags  # G-Q7: 非空
    # 図は required（graph_table）。labels は実描画の軸目盛と機械的に一致する。
    assert mr.visual_plan is not None
    kinds = {e.kind for e in mr.visual_plan.elements}
    assert {"grid", "axis"} <= kinds
    if (family, level) in _C4_EMPTY_GRID_CELLS:
        assert kinds == {"grid", "axis"}, "かく/比べるセルの問題図は空の方眼"
    else:
        assert kinds & {"line", "curve"}, "読むセルは読む対象そのものを図に描く"


@pytest.mark.parametrize("family,level,signature,asked,n_steps", _C4_GRAPH_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_c4_graph_double_solve_property(seed, family, level, signature, asked, n_steps):
    """全 seed で double_solve checker（G-Q1 が呼ぶ実体）と答えが一致する。"""
    ctx, mr = _c4_mr(family, level, seed)
    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    sol = checker(mr)
    sq = mr.sub_questions[0]
    if sq.answer.kind == "graph":
        assert {f.srepr for f in sol.answer.features} == {f.srepr for f in sq.answer.features}
    else:
        assert sol.answer.srepr == sq.answer.srepr
    assert [s.op for s in sol.steps] == [s.op for s in sq.steps]


@pytest.mark.parametrize("family,level,signature,asked,n_steps", _C4_GRAPH_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_c4_graph_svg_texts_are_axis_ticks_only(seed, family, level, signature, asked, n_steps):
    """G-Q5v: 問題図の <text> は軸目盛だけで、visual_plan.labels に必ず含まれる。"""
    import re

    from engine.core.render.t1_template import render_visual

    ctx, mr = _c4_mr(family, level, seed)
    svg = render_visual(mr, ctx)
    assert svg is not None
    texts = re.findall(r"<text[^>]*>(.*?)</text>", svg)
    assert texts, "軸目盛が1つも描かれていない"
    assert set(texts) <= set(mr.visual_plan.labels)


@pytest.mark.parametrize("family,level", sorted(_C4_DRAW_CELLS))
@pytest.mark.parametrize("seed", range(10))
def test_c4_draw_cells_have_solution_figure_but_empty_problem_figure(seed, family, level):
    """「かく」セル: 模範解答図は線/曲線つき・問題図は空の方眼（答えの先出し禁止）。"""
    import re

    from engine.core.render.t1_template import render_visual

    ctx, mr = _c4_mr(family, level, seed)
    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph"
    assert answer.solution_svg_ref != ""
    assert 'stroke-width="2.5"' in answer.solution_svg_ref  # 解答図には答えの線/曲線がある
    problem_svg = render_visual(mr, ctx)
    assert 'stroke-width="2.5"' not in problem_svg, "問題図に答えの線/曲線が描かれている"
    # 解答図の <text> も軸目盛のみ（whitelist 外の注記を入れない）
    for t in re.findall(r"<text[^>]*>(.*?)</text>", answer.solution_svg_ref):
        assert t in mr.visual_plan.labels


@pytest.mark.parametrize("seed", range(50))
def test_c4_non_degenerate(seed):
    """ゲートが素通りさせる退化を構成側で塞げていることを固定する。"""
    # g1_l30 Lv1/Lv2: 軸上の点（座標の一方が 0）にしない
    for level in (1, 2):
        _, mr = _c4_mr("math.g1_l30.graph_table", level, seed)
        assert mr.params["x0"] != 0 and mr.params["y0"] != 0

    # g1_l31 Lv1: 比例定数が 0 でない＝答えが 0 に潰れない。読む点と示された点は相異。
    _, mr = _c4_mr("math.g1_l31.graph_table", 1, seed)
    a, x0, p = mr.params["a"], mr.params["x0"], mr.params["p"]
    assert a != 0 and x0 != 0 and p != x0
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) == a * x0 != 0

    # g1_l31 Lv2: 明示する2点は相異で、どちらも原点でない（原点だけでは直線が決まらない）
    _, mr = _c4_mr("math.g1_l31.graph_table", 2, seed)
    assert mr.params["p"] < mr.params["q"]
    assert mr.params["p"] != 0 and mr.params["q"] != 0 and mr.params["a"] != 0
    assert len({f.srepr for f in mr.sub_questions[0].answer.features}) == 3

    # g1_l31 Lv3 / g1_l34 Lv3: 負は1本だけ・絶対値最大は正の1本だけ（答えが一意）
    for family in ("math.g1_l31.graph_table", "math.g1_l34.graph_table"):
        _, mr = _c4_mr(family, 3, seed)
        vals = [mr.params["a1"], mr.params["a2"], mr.params["a3"]]
        assert len([v for v in vals if v < 0]) == 1
        biggest = max(vals, key=abs)
        assert biggest > 0, "最も急/最も離れたグラフが右下がりのものと同じになっている"
        assert [abs(v) for v in vals].count(abs(biggest)) == 1
        assert len(set(vals)) == 3

    # g1_l32 Lv1: 読み取る点は原点でない格子点で、直線 y=ax 上にある
    _, mr = _c4_mr("math.g1_l32.graph_table", 1, seed)
    pt = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert pt[0] != 0 and pt[1] != 0
    assert pt[0].is_Integer and pt[1].is_Integer
    assert sympy.Rational(pt[1], pt[0]) == sympy.sympify(mr.params["a"])

    # g1_l34 Lv1 / g1_l35 Lv1: 双曲線上の格子点（x0*y0 = a・どちらも 0 でない）
    for family, level in (("math.g1_l34.graph_table", 1), ("math.g1_l35.graph_table", 1)):
        _, mr = _c4_mr(family, level, seed)
        a, x0 = mr.params["a"], mr.params["x0"]
        assert a != 0 and x0 != 0
        assert sympy.Rational(a, x0).q == 1, "読み取る点が格子点になっていない"
        assert mr.params["curve_kind"] == "hyperbola"

    # g1_l34 Lv2: 表の x は相異な a の約数で、対応する y も方眼に収まる
    ctx, mr = _c4_mr("math.g1_l34.graph_table", 2, seed)
    a, xs = mr.params["a"], mr.params["xs"]
    t_max = int(ctx.spec_level.params["table_abs_max"])
    assert len(set(xs)) == len(xs) >= 3
    for x in xs:
        assert x > 0 and abs(a) % x == 0 and abs(a) // x <= t_max and x <= t_max

    # g1_l36 Lv2: たずねる x は測定値と相異・割合は 2 以上（答えが x_q に潰れない）
    _, mr = _c4_mr("math.g1_l36.graph_table", 2, seed)
    assert mr.params["a"] >= 2
    assert mr.params["x_q"] not in mr.params["xs"]
    assert len(set(mr.params["xs"])) == len(mr.params["xs"])
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) == mr.params["a"] * mr.params["x_q"]

    # g1_l36 Lv3: 交点は格子点で、A の単価が高く、固定費は差の倍数（＝グラフで読める）
    _, mr = _c4_mr("math.g1_l36.graph_table", 3, seed)
    pa, pb, fixed = mr.params["pa"], mr.params["pb"], mr.params["fixed"]
    assert pa > pb > 0 and fixed > 0
    assert fixed % (pa - pb) == 0
    pt = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert pt[0] == fixed // (pa - pb) > 0 and pt[1] == pa * pt[0]


@pytest.mark.parametrize("family", ["math.g1_l30.graph_table", "math.g1_l31.graph_table",
                                    "math.g1_l34.graph_table", "math.g1_l36.graph_table"])
def test_c4_graph_level_sep_is_structural(family):
    """level_sep: 同一 family のレベル間で fingerprint（given型・asked・op列）が相異する。"""
    from engine.core.signature import fingerprint_hash

    levels = [lv for fam, lv, *_ in _C4_GRAPH_CELLS if fam == family]
    fps = {}
    for level in levels:
        _, mr = _c4_mr(family, level, 1)
        fps[level] = fingerprint_hash(mr)
    assert len(set(fps.values())) == len(levels), f"fp が衝突: {fps}"


def test_c4_graph_recipe_concepts_declared():
    """R6: recipe が宣言する概念集合が spec の concept_tags を覆う。"""
    assert REGISTRY.recipe_concepts("math.read_coordinate_on_plane") == frozenset({
        "coordinate_plane.read_point_coordinate",
    })
    assert REGISTRY.recipe_concepts("math.draw_hyperbola_from_table") == frozenset({
        "inverse_proportion.draw_hyperbola",
    })
    assert REGISTRY.recipe_concepts("math.graph_two_plans_crossover") == frozenset({
        "direct_proportion.compare_two_plans_graph",
    })


# ---------------------------------------------------------------------------
# C6 g3 二次関数 y=ax² の graph_table（かく／読む）8 セル（横展開#116）
#
# ゲート（G-Q1/G-FP/dup）は「答えが 0 や 1 に潰れる退化」を素通りするので、
# ここでは各セルの**非退化条件**（頂点だけの答えにならない・2本の放物線が相異なる・
# 変域が潰れない・交点が2つある・折れ線が実際に折れる）を property で固定する。
# ---------------------------------------------------------------------------
_C6_GRAPH_CELLS = [
    ("math.g3_l33.graph_table", 1),
    ("math.g3_l33.graph_table", 2),
    ("math.g3_l34.graph_table", 2),
    ("math.g3_l36.graph_table", 2),
    ("math.g3_l37.graph_table", 2),
    ("math.g3_l38.graph_table", 2),
    ("math.g3_l38.graph_table", 3),
]

_C6_CHECKER_BY_CELL = {
    ("math.g3_l33.graph_table", 1): "math.read_two_points_on_parabola.double_solve",
    ("math.g3_l33.graph_table", 2): "math.draw_two_parabolas.double_solve",
    ("math.g3_l34.graph_table", 2): "math.draw_parabola_domain.double_solve",
    ("math.g3_l36.graph_table", 2): "math.draw_phenomenon_curve.double_solve",
    ("math.g3_l37.graph_table", 2): "math.draw_parabola_and_line.double_solve",
    ("math.g3_l38.graph_table", 2): "math.read_area_time_graph.double_solve",
    ("math.g3_l38.graph_table", 3): "math.draw_piecewise_area_graph.double_solve",
}

_SVG_TEXT_RE = re.compile(r"<text[^>]*>(.*?)</text>")


@pytest.mark.parametrize("family,level", _C6_GRAPH_CELLS)
@pytest.mark.parametrize("seed", range(40))
def test_c6_graph_table_double_solve_property(family, level, seed):
    """double-solve が全 seed で一致し、図（問題図/模範解答図）の規約を満たす。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker(_C6_CHECKER_BY_CELL[(family, level)])
    sol = checker(mr)
    sq = mr.sub_questions[0]
    if sq.answer.kind == "graph":
        assert {f.srepr for f in sol.answer.features} == {f.srepr for f in sq.answer.features}
    else:
        assert sol.answer.srepr == sq.answer.srepr

    # G-Q5v: 図の <text> は軸目盛だけ＝labels は tick_labels_from_params と機械的に一致。
    assert mr.visual_plan is not None
    assert mr.visual_plan.labels == tick_labels_from_params(mr.params)

    if sq.asked == "draw_graph":
        # 「かく」セル: 問題図は空の方眼（描画対象を宣言しない）／模範解答図は非空。
        assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}
        assert sq.answer.solution_svg_ref.startswith("<svg")
        # 模範解答図の <text> も軸目盛だけ（labels の集合に含まれる）。
        texts = _SVG_TEXT_RE.findall(sq.answer.solution_svg_ref)
        assert set(texts) <= set(mr.visual_plan.labels)
    else:
        # 「読む」セル: 読む対象が問題図に描かれている／given に式を出さない。
        assert {"curve", "polyline"} & {e.kind for e in mr.visual_plan.elements}
        assert "expression" not in mr.given


@pytest.mark.parametrize("seed", range(40))
def test_read_two_points_on_parabola_non_degenerate(seed):
    """g3_l33 Lv1: 読む2点が相異・非0の x で、頂点（原点）に潰れない。"""
    ctx = _make_ctx("math.g3_l33.graph_table", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a = sympy.sympify(mr.params["coeff"])
    x1, x2 = int(mr.params["x1"]), int(mr.params["x2"])
    assert a != 0
    assert x1 != 0 and x2 != 0 and x1 != x2
    # 答えは (x1, a·x1²), (x2, a·x2²)＝どちらも原点ではない。
    pts = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert pts == sympy.Tuple(
        sympy.Tuple(sympy.Integer(x1), a * x1**2), sympy.Tuple(sympy.Integer(x2), a * x2**2)
    )
    assert all(p != sympy.Tuple(sympy.Integer(0), sympy.Integer(0)) for p in pts)
    # 方眼に収まる（|a·x²| ≦ value_bound）＝図から座標が読める。
    bound = int(ctx.spec_level.params["value_bound"])
    assert max(abs(a * x1**2), abs(a * x2**2)) <= bound
    # 点名2つは相異（surface の自由度＝dup 分散）。
    assert len(set(mr.params["labels"])) == 2


@pytest.mark.parametrize("seed", range(40))
def test_draw_two_parabolas_non_degenerate(seed):
    """g3_l33 Lv2: 2本の放物線が相異なり、開き方の比較が一意に決まる。"""
    ctx = _make_ctx("math.g3_l33.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a1, a2 = sympy.sympify(mr.params["coeff"]), sympy.sympify(mr.params["coeff2"])
    assert a1 != 0 and a2 != 0
    assert a1 != a2, "同じ比例定数だと2本が重なり『開き方を比べる』が成立しない"
    assert abs(a1) != abs(a2), "絶対値が同じだと開き方の広さが等しく、比較が一意に決まらない"

    lo, hi = int(mr.params["table_lo"]), int(mr.params["table_hi"])
    assert lo < 0 < hi, "対応表は原点をまたぐ（頂点まわりの対称性が見える）"
    features = mr.sub_questions[0].answer.features
    # 頂点1つ＋各曲線の表の点＋開き方の比較1つ。
    assert [f.kind for f in features].count("vertex") == 1
    assert [f.kind for f in features].count("curve_point") == 2 * (hi - lo + 1)
    narrower = [f for f in features if f.kind == "narrower_curve"]
    assert len(narrower) == 1
    expected = a1 if abs(a1) > abs(a2) else a2
    assert sympy.srepr(sympy.Tuple(sympy.Symbol("narrower"), expected)) == narrower[0].srepr


@pytest.mark.parametrize("seed", range(40))
def test_draw_parabola_domain_non_degenerate(seed):
    """g3_l34 Lv2: 変域が潰れず、y の変域が頂点を含むかどうかで正しく決まる。"""
    ctx = _make_ctx("math.g3_l34.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a = sympy.sympify(mr.params["coeff"])
    lo, hi = int(mr.params["arc_x_lo"]), int(mr.params["arc_x_hi"])
    assert a != 0
    assert lo < hi, "x の変域が1点に潰れると『区間として把握』が成立しない"

    y_lo, y_hi = a * lo**2, a * hi**2
    candidates = [y_lo, y_hi] + ([sympy.Integer(0)] if lo < 0 < hi else [])
    expected = sympy.Tuple(sympy.Symbol("y_range"), min(candidates), max(candidates))
    y_range = [f for f in mr.sub_questions[0].answer.features if f.kind == "y_range"]
    assert len(y_range) == 1
    assert y_range[0].srepr == sympy.srepr(expected)
    # y の変域も1点に潰れない（a≠0 かつ lo<hi なら両端の y か頂点かで必ず幅が出る）。
    assert min(candidates) != max(candidates)


@pytest.mark.parametrize("seed", range(40))
def test_draw_phenomenon_curve_non_degenerate(seed):
    """g3_l36 Lv2: 現象のグラフが第1象限で単調に増加し、表が3行以上ある。"""
    ctx = _make_ctx("math.g3_l36.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a = sympy.sympify(mr.params["coeff"])
    rows, step = int(mr.params["rows"]), int(mr.params["step"])
    assert a > 0, "現象（距離）の比例定数は正＝第1象限の量-量グラフになる"
    assert rows >= 3 and step >= 1
    assert mr.params["grid_mode"] == "quantity"

    features = mr.sub_questions[0].answer.features
    assert len(features) == rows + 1
    ys = [a * (step * i) ** 2 for i in range(rows + 1)]
    assert ys == sorted(ys) and ys[0] == 0 and ys[-1] > 0, "0 から単調増加（値が潰れない）"
    assert ys[-1] <= int(ctx.spec_level.params["value_bound"])


@pytest.mark.parametrize("seed", range(40))
def test_draw_parabola_and_line_non_degenerate(seed):
    """g3_l37 Lv2: 放物線と直線が相異なる2点で交わり、囲まれた部分が潰れない。"""
    ctx = _make_ctx("math.g3_l37.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    a = sympy.sympify(mr.params["coeff"])
    m, b = sympy.sympify(mr.params["line_m"]), sympy.sympify(mr.params["line_b"])
    xa, xb = int(mr.params["hatch_x_lo"]), int(mr.params["hatch_x_hi"])
    assert a != 0
    assert b != 0, "直線が原点を通ると交点の一方が原点になり、囲まれた部分が退化しうる"
    assert xa < xb, "交点が1点に重なると囲まれた部分が消える"
    # 交点は ax²=mx+b の解そのもの（判別式が正＝2交点）。
    assert (m**2 + 4 * a * b) > 0
    x = sympy.Symbol("x")
    assert sorted(sympy.solve(sympy.Eq(a * x**2, m * x + b), x)) == [xa, xb]
    # 答えの特徴は交点2つだけ（答えを図に先出ししていない＝問題図は空の方眼）。
    assert [f.kind for f in mr.sub_questions[0].answer.features] == ["intersection"] * 2
    assert len(set(mr.params["labels"])) == 2


@pytest.mark.parametrize("seed", range(40))
def test_read_area_time_graph_non_degenerate(seed):
    """g3_l38 Lv2: 読み取りが格子点で確定し、面積-時間グラフが実際に折れる。"""
    ctx = _make_ctx("math.g3_l38.graph_table", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    p_side, q_side = int(mr.params["side_p"]), int(mr.params["side_q"])
    t1, t2 = int(mr.params["t1"]), int(mr.params["t2"])
    assert p_side > 0 and q_side > 0 and p_side % 2 == 0
    assert t1 < t2 and 1 <= t1 and t2 <= p_side + q_side
    # 量-量グラフの目盛が 1 刻み＝読み取る値が必ず格子点にのる。
    spec = compute_grid_spec_from_params(mr.params)
    assert spec.x_step == 1 and spec.y_step == 1

    # 折れ線は「増加する1次式 → 一定」の2区間（0 に潰れず、実際に折れる）。
    y_top = sympy.Rational(p_side * q_side, 2)
    assert y_top > 0
    assert mr.params["poly_pts"] == [
        str((sympy.Integer(0), sympy.Integer(0))),
        str((sympy.Integer(q_side), y_top)),
        str((sympy.Integer(p_side + q_side), y_top)),
    ]
    pts = sympy.sympify(mr.sub_questions[0].answer.srepr)
    for t, pt in ((t1, pts[0]), (t2, pts[1])):
        expected_y = sympy.Rational(p_side * t, 2) if t <= q_side else y_top
        assert pt == sympy.Tuple(sympy.Integer(t), expected_y)
    assert len(set(mr.params["labels"])) == 5


@pytest.mark.parametrize("seed", range(40))
def test_draw_piecewise_area_graph_non_degenerate(seed):
    """g3_l38 Lv3: 折れ点が目盛にのり、2区間の式（1次関数→一定）が実際に変わる。"""
    ctx = _make_ctx("math.g3_l38.graph_table", 3)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    s, v = int(mr.params["side"]), int(mr.params["speed"])
    assert s % 2 == 0, "1辺が偶数＝面積 s²/2 が整数（折れ点が目盛にのる）"
    assert s % v == 0, "速さが1辺の約数＝折れ点の時刻 s/v が整数"
    t1, area = s // v, sympy.Rational(s * s, 2)
    assert area > 0

    features = mr.sub_questions[0].answer.features
    assert {f.srepr for f in features} == {
        sympy.srepr(sympy.Tuple(sympy.Integer(0), sympy.Integer(0))),
        sympy.srepr(sympy.Tuple(sympy.Integer(t1), area)),
        sympy.srepr(sympy.Tuple(sympy.Integer(2 * t1), area)),
    }
    # 第1区間は傾き s·v/2 で増加し、第2区間は一定＝「区間ごとに式が変わる」。
    assert sympy.Rational(s * v, 2) * t1 == area
    assert sympy.Rational(s * v, 2) > 0
    # 面積は独立ソルバ（shoelace 公式・g3_l31 と共有）でも同じ値になる。
    for t, mode in ((t1, "single_segment"), (2 * t1, "two_segment")):
        sol = REGISTRY.solver("math.solve_moving_point_area")(s, v, t, mode)
        assert sympy.sympify(sol.answer.srepr) == area
    assert len(set(mr.params["labels"])) == 5


@pytest.mark.parametrize("seed", range(40))
def test_parabola_property_rule_recall_non_degenerate(seed):
    """g3_l33 knowledge Lv1: 正解が distractor と重ならず、答えに数字が出ない。"""
    ctx = _make_ctx("math.g3_l33.knowledge", 1)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    ans = mr.sub_questions[0].answer
    assert ans.kind == "choice"
    assert ans.correct not in ans.distractors
    assert len(ans.distractors) >= 2
    assert not re.search(r"\d", ans.correct), "選択肢に数字が出ると G-Q5t が誤検出する"
    assert mr.params["concept"] in {"shape_and_symmetry", "opening_direction", "opening_width"}


# ---------------------------------------------------------------------------
# C8 g1 空間図形（g1_l47/l48.knowledge Lv2 の判別型）
# ---------------------------------------------------------------------------
def test_judge_polyhedron_claim_lv2_construct():
    ctx = _make_ctx("math.g1_l47.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_polyhedron_claim"
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "choice")]
    assert set(mr.given) == {"statement"}
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(120))
def test_judge_polyhedron_claim_double_solve_property(seed):
    """全 seed で checker の独立再計算と一致し、答えが digit-free で op 列が不変。"""
    ctx = _make_ctx("math.g1_l47.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    sol = REGISTRY.checker("math.judge_polyhedron_claim.double_solve")(mr)
    answer = mr.sub_questions[0].answer
    assert sol.answer.correct == answer.correct
    assert sol.answer.fact_id == answer.fact_id
    # 答えは「正しい」「誤り」のテキスト（数字トークンなし）＝G-Q5t 素通り。
    assert answer.correct in ("正しい", "誤り")
    assert not any(ch.isdigit() for ch in answer.correct)
    assert answer.correct not in answer.distractors
    # 1レベル＝1 op 列（mode が変わっても不変・G-FP 安定）。
    assert [s.op for s in mr.sub_questions[0].steps] == ["read_claim", "judge_claim"]
    # surface（statement）も dup_key に効かせるため params に入れ、本文に出す。
    assert mr.params["statement"] == mr.given["statement"]
    if mr.params["mode"] == "element_count":
        # 主張されている個数は本文に出ている（params は「本文に出ている値」だけ）。
        assert mr.params["candidate"] in mr.given["statement"]
        assert mr.params["n"] in mr.given["statement"]
    else:
        assert mr.params["vertex"] in mr.given["statement"]


def test_judge_polyhedron_claim_not_degenerate():
    """答えが「正しい」「誤り」の一方に潰れず、両 mode が現れる（ゲートは退化を素通りする）。"""
    ctx = _make_ctx("math.g1_l47.knowledge", 2)
    corrects, modes = set(), set()
    for seed in range(120):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        corrects.add(mr.sub_questions[0].answer.correct)
        modes.add(mr.params["mode"])
    assert corrects == {"正しい", "誤り"}
    assert modes == {"element_count", "regular_condition"}


@pytest.mark.parametrize(
    ("n", "solid_type", "quantity", "expected"),
    [
        # 教科書の既知値: 五角柱は面7・辺15・頂点10、五角錐は面6・辺10・頂点6。
        (5, "prism", "faces", 7),
        (5, "prism", "edges", 15),
        (5, "prism", "vertices", 10),
        (5, "pyramid", "faces", 6),
        (5, "pyramid", "edges", 10),
        (5, "pyramid", "vertices", 6),
        # 正六面体（立方体）＝四角柱: 面6・辺12・頂点8。
        (4, "prism", "faces", 6),
        (4, "prism", "edges", 12),
        (4, "prism", "vertices", 8),
    ],
)
def test_polyhedron_element_count_known_values(n, solid_type, quantity, expected):
    """公式が教科書の既知値と一致する（オイラーの多面体定理も満たす）。"""
    from engine.packs.math.solvers.g1_space import true_element_count

    assert true_element_count(n, solid_type, quantity) == expected
    v = true_element_count(n, solid_type, "vertices")
    e = true_element_count(n, solid_type, "edges")
    f = true_element_count(n, solid_type, "faces")
    assert v - e + f == 2


@pytest.mark.parametrize(
    ("m", "k", "can_form"),
    [
        (3, 3, True), (3, 4, True), (3, 5, True),  # 正四面体・正八面体・正二十面体
        (4, 3, True),                              # 正六面体
        (5, 3, True),                              # 正十二面体
        (3, 6, False),                             # 角の和がちょうど一まわり＝平面
        (4, 4, False), (5, 4, False), (6, 3, False), (7, 3, False),
    ],
)
def test_regular_polyhedron_condition_known_values(m, k, can_form):
    """正多面体が5種類しかない根拠（頂点に集まる角の和 < 360°）を既知値で固定する。"""
    solver = REGISTRY.solver("math.judge_regular_polyhedron_condition")
    assert solver(m, k).answer.correct == ("正しい" if can_form else "誤り")


def test_judge_solid_position_lv2_construct():
    ctx = _make_ctx("math.g1_l48.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == "judge_solid_position"
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "choice")]
    assert set(mr.given) == {"statement"}
    assert mr.visual_plan is None


@pytest.mark.parametrize("seed", range(120))
def test_judge_solid_position_double_solve_property(seed):
    """全 seed で checker の独立再計算と一致し、引いた頂点ラベルが本文と params にある。"""
    ctx = _make_ctx("math.g1_l48.knowledge", 2)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    sol = REGISTRY.checker("math.judge_solid_position.double_solve")(mr)
    answer = mr.sub_questions[0].answer
    assert sol.answer.correct == answer.correct
    assert sol.answer.fact_id == answer.fact_id
    assert not any(ch.isdigit() for ch in answer.correct)
    assert answer.correct not in answer.distractors
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "read_position_query",
        "classify_relation",
    ]
    # draw した点ラベルは params に必ず含め、本文にも出す。
    labels = mr.params["labels"]
    assert len(labels) == 8 and len(set(labels)) == 8
    assert f"{labels[:4]}-{labels[4:]}" in mr.given["statement"]
    assert mr.params["first"] in mr.given["statement"]
    assert mr.params["second"] in mr.given["statement"]
    # 問われている辺・面は、引いたラベルだけで構成されている。
    assert set(mr.params["first"]) <= set(labels)
    assert set(mr.params["second"]) <= set(labels)


def test_judge_solid_position_not_degenerate():
    """3つの位置関係がすべて現れ、両 mode が現れる（答えが1つに潰れていない）。"""
    ctx = _make_ctx("math.g1_l48.knowledge", 2)
    by_mode: dict[str, set[str]] = {}
    for seed in range(200):
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
        by_mode.setdefault(mr.params["mode"], set()).add(mr.sub_questions[0].answer.correct)
    assert by_mode["edge_edge"] == {"平行", "垂直に交わる", "ねじれの位置"}
    assert by_mode["edge_face"] == {"平行", "面上にある", "垂直に交わる"}


def test_solid_position_known_relations():
    """標準ラベル ABCD-EFGH での位置関係を、図を手で追える既知値で固定する。"""
    solver = REGISTRY.solver("math.judge_solid_position_relation")
    labels = "ABCDEFGH"  # 底面 ABCD／上面 EFGH（E が A の真上）
    assert solver(labels, "edge_edge", "AB", "CD").answer.correct == "平行"
    assert solver(labels, "edge_edge", "AB", "EF").answer.correct == "平行"
    assert solver(labels, "edge_edge", "AB", "BC").answer.correct == "垂直に交わる"
    assert solver(labels, "edge_edge", "AB", "AE").answer.correct == "垂直に交わる"
    assert solver(labels, "edge_edge", "AB", "CG").answer.correct == "ねじれの位置"
    assert solver(labels, "edge_edge", "AB", "FG").answer.correct == "ねじれの位置"
    assert solver(labels, "edge_edge", "AB", "GH").answer.correct == "平行"
    assert solver(labels, "edge_face", "AB", "ABCD").answer.correct == "面上にある"
    assert solver(labels, "edge_face", "AB", "EFGH").answer.correct == "平行"
    assert solver(labels, "edge_face", "AB", "DCGH").answer.correct == "平行"
    assert solver(labels, "edge_face", "AE", "ABCD").answer.correct == "垂直に交わる"
    assert solver(labels, "edge_face", "AB", "ADHE").answer.correct == "垂直に交わる"


# ---------------------------------------------------------------------------
# 三平方の定理の利用（g3_l53/l54/l55/l56 の find_value ＋ g3_l53.knowledge）
# ＝ 1 recipe（math.pythagorean_find_value）で 10 セル ＋ 知識セル 1 つ
# ---------------------------------------------------------------------------
_PYTHAGOREAN_FV_CELLS = [
    ("math.g3_l53.find_value", 2, "pythagorean_missing_side_in_right_triangle", "value"),
    ("math.g3_l53.find_value", 3, "pythagorean_isosceles_height_and_area", "value"),
    ("math.g3_l53.find_value", 4, "pythagorean_height_from_special_angles", "value"),
    ("math.g3_l54.find_value", 2, "pythagorean_coordinate_distance", "value"),
    ("math.g3_l54.find_value", 3, "pythagorean_equidistant_point_on_x_axis", "coordinate"),
    ("math.g3_l55.find_value", 2, "pythagorean_box_diagonal", "value"),
    ("math.g3_l55.find_value", 3, "pythagorean_square_pyramid_height_volume", "value"),
    ("math.g3_l55.find_value", 4, "pythagorean_regular_tetrahedron_height_volume", "value"),
    ("math.g3_l56.find_value", 2, "pythagorean_box_surface_shortest_path", "value"),
    ("math.g3_l56.find_value", 4, "pythagorean_cone_surface_shortest_path", "value"),
]


@pytest.mark.parametrize(("family", "level", "signature", "asked"), _PYTHAGOREAN_FV_CELLS)
def test_pythagorean_find_value_construct(family, level, signature, asked):
    """find_value は小問1つ・given は condition のみ・答えは params に入らない。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed=1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", asked)]
    assert set(mr.given) == {"condition"}
    assert mr.visual_plan is None
    assert set(mr.params) == {"scenario_kind", "numbers", "slots"}
    assert "answer" not in mr.params


@pytest.mark.parametrize(("family", "level", "signature", "asked"), _PYTHAGOREAN_FV_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_pythagorean_find_value_double_solve_property(seed, family, level, signature, asked):
    """checker の独立再計算と一致し、params の全値が本文に現れる（params 忠実性）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)

    checker = REGISTRY.checker("math.pythagorean_find_value.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions) == 1
    assert solutions[0].answer.srepr == mr.sub_questions[0].answer.srepr

    shown = "".join(mr.given.values())
    for key, value in mr.params["numbers"].items():
        if key == "role":  # 問いの型（どの辺を求めるか）は語で本文に出る
            continue
        assert str(value) in shown, f"{key}={value} が本文に無い"
    # 点名は答えに影響しない surface だが、dup_key に効かせるため params に入れる。
    # 本文では離れた位置に出る（"正四角錐O-PQRS" の O と PQRS など）ので1文字ずつ見る。
    for value in mr.params["slots"].values():
        for ch in str(value):
            assert ch in shown, f"点名 {ch} が本文に無い"


@pytest.mark.parametrize(("family", "level", "signature", "asked"), _PYTHAGOREAN_FV_CELLS)
@pytest.mark.parametrize("seed", range(30))
def test_pythagorean_find_value_no_digit_in_narration(seed, family, level, signature, asked):
    """narration に数字を書かない（hints に流れて G-Q5t が漏洩と誤検出するため）。"""
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    for sq in mr.sub_questions:
        for step in sq.steps:
            assert not any(ch.isdigit() for ch in step.narration), step.narration


@pytest.mark.parametrize("seed", range(40))
def test_pythagorean_find_value_non_degenerate(seed):
    """答えが 0 や自明値に潰れる退化を構成側で禁じていることを固定する。"""
    # g3_l53 Lv2: 斜辺を問う枠は2辺とも正、辺を問う枠は 斜辺 > 既知の辺（答えが正）。
    ctx = _make_ctx("math.g3_l53.find_value", 2)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    n = mr.params["numbers"]
    assert int(n["known_a"]) > 0 and int(n["known_b"]) > 0
    if n["role"] == "leg":
        assert int(n["known_a"]) > int(n["known_b"])

    # g3_l53 Lv3: 底辺は偶数・三角形が成り立つ・針のように細くない。
    ctx = _make_ctx("math.g3_l53.find_value", 3)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    equal_side, base = (int(mr.params["numbers"][k]) for k in ("equal_side", "base"))
    assert base % 2 == 0 and base >= 4
    assert base < 2 * equal_side and 2 * base >= equal_side

    # g3_l54 Lv2: 座標軸に平行な線分（差の一方が 0）は直角三角形にならないので出さない。
    ctx = _make_ctx("math.g3_l54.find_value", 2)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    n = mr.params["numbers"]
    assert int(n["x1"]) != int(n["x2"]) and int(n["y1"]) != int(n["y2"])

    # g3_l54 Lv3: y の二乗が等しいと答えが中点に潰れる（三平方を使わずに解ける）。
    ctx = _make_ctx("math.g3_l54.find_value", 3)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    n = mr.params["numbers"]
    assert int(n["x1"]) != int(n["x2"])
    assert int(n["y1"]) ** 2 != int(n["y2"]) ** 2
    x_of_p = sympy.sympify(mr.sub_questions[0].answer.srepr)[0]
    assert x_of_p.is_Integer

    # g3_l55 Lv3: 側辺が底面の対角線の半分より長い＝高さが正の実数（錐体が立つ）。
    ctx = _make_ctx("math.g3_l55.find_value", 3)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    base_edge, lateral = (int(mr.params["numbers"][k]) for k in ("base_edge", "lateral_edge"))
    assert base_edge % 2 == 0
    assert 2 * lateral**2 > base_edge**2

    # g3_l56 Lv4: 中心角が 180°未満（弦が最短経路になる）かつ 60°でない（答えが母線と一致）。
    ctx = _make_ctx("math.g3_l56.find_value", 4)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    radius, slant = (int(mr.params["numbers"][k]) for k in ("radius", "slant"))
    central_angle = sympy.Rational(360 * radius, slant)
    assert 0 < central_angle < 180
    chord = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert chord > 0 and chord != slant


@pytest.mark.parametrize("seed", range(40))
def test_special_right_triangle_ratio_property(seed):
    """g3_l53.knowledge Lv1: 正答が特別な直角三角形の比になり、誤答と重ならない。"""
    ctx = _make_ctx("math.g3_l53.knowledge", 1)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    assert mr.signature == "special_right_triangle_ratio"
    assert set(mr.given) == {"statement"}
    assert mr.visual_plan is None

    checker = REGISTRY.checker("math.special_right_triangle_ratio.double_solve")
    solutions = checker(mr)
    answer = mr.sub_questions[0].answer
    assert len(solutions) == 1
    assert solutions[0].answer.correct == answer.correct

    acute = int(mr.params["numbers"]["acute_angle"])
    pool = {"1:1", "1:√2", "√2:1"} if acute == 45 else {
        "1:√3", "1:2", "√3:2", "√3:1", "2:1", "2:√3",
    }
    assert answer.correct in pool
    assert answer.distractors, "妨害選択肢が空"
    assert answer.correct not in answer.distractors
    assert len(set(answer.distractors)) == len(answer.distractors)
    # 比べる2辺は必ず異なる辺（同じ辺どうしの比 1:1 に潰れない形で問う）。
    assert int(mr.params["numbers"]["first_side"]) != int(mr.params["numbers"]["second_side"])


# ---------------------------------------------------------------------------
# C11 g1 度数分布 graph_table（横展開: g1_l54/l55/l56/l58 の「読む」「かく」10セル）
#
# ゲートは「答えが潰れる退化」を素通りするので、分布の形が読めない／答えが一意に
# 決まらない／2つの分布が比較にならない、を property で固定する。
# ---------------------------------------------------------------------------
def _dist_mr(family_name: str, level: int, seed: int):
    ctx = _make_ctx(family_name, level)
    return ctx, REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )


def _svg_text_nodes(svg: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.DOTALL)]


def _assert_chart_labels_cover_svg(mr) -> None:
    """図に出る数値ラベルが visual_plan.labels に収まる（G-Q5v を recipe 側で先取り）。"""
    from engine.packs.math.visuals.distribution_chart import render_frequency_chart_svg

    allowed = set(mr.visual_plan.labels)
    for drawn in (True, False):
        svg = render_frequency_chart_svg(mr.params, draw=drawn)
        assert set(_svg_text_nodes(svg)) <= allowed, f"図内テキストが labels 外: {mr.params}"


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    "family,level,chart_kind",
    [
        ("math.g1_l54.graph_table", 1, "histogram"),
        ("math.g1_l55.graph_table", 1, "polygon"),
    ],
)
def test_read_distribution_chart_property(seed, family, level, chart_kind):
    """「読む」Lv1: 最頻の階級が一意で、問う階級はそれと別（2つの問いが潰れない）。"""
    _ctx, mr = _dist_mr(family, level, seed)
    freqs = [int(f) for f in mr.params["frequencies"]]
    target = int(mr.params["target_index"])

    assert mr.params["chart_kind"] == chart_kind
    assert len(set(freqs)) > 1, "度数が全部同じ（分布の形が読めない）"
    assert freqs.count(max(freqs)) == 1, "度数が最大の階級が一意でない"
    assert freqs[target] != max(freqs), "問う階級が最頻の階級と同じで答えが重複する"
    assert all(f >= 1 for f in freqs)

    # 「読む」ので図には分布が描かれていること（空のグラフ用紙では答えられない）。
    assert {e.kind for e in mr.visual_plan.elements} >= {"distribution"}
    _assert_chart_labels_cover_svg(mr)

    lo, width = int(mr.params["class_lo"]), int(mr.params["class_width"])
    expected = sympy.Tuple(
        sympy.Integer(freqs[target]), sympy.Integer(lo + width * freqs.index(max(freqs)))
    )
    assert mr.sub_questions[0].answer.srepr == sympy.srepr(expected)

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert checker(mr).answer.srepr == mr.sub_questions[0].answer.srepr


@pytest.mark.parametrize("seed", range(40))
def test_tabulate_and_draw_histogram_property(seed):
    """g1_l54.graph_table Lv2: 生データを数え直すと構成した度数に一致し、山が一意。"""
    _ctx, mr = _dist_mr("math.g1_l54.graph_table", 2, seed)
    lo, width = int(mr.params["class_lo"]), int(mr.params["class_width"])
    freqs = [int(f) for f in mr.params["frequencies"]]
    data = [int(v) for v in mr.params["data"]]

    assert len(data) == sum(freqs)
    assert all(lo <= v < lo + width * len(freqs) for v in data), "階級の範囲外のデータ"
    recount = [0] * len(freqs)
    for v in data:
        recount[(v - lo) // width] += 1
    assert recount == freqs
    assert len(set(freqs)) > 1, "度数が全部同じ（ヒストグラムが平ら）"
    assert freqs.count(max(freqs)) == 1, "度数が最大の階級が一意でない"

    # 「かく」ので問題図は空のグラフ用紙（分布を先出ししない）。
    assert "distribution" not in {e.kind for e in mr.visual_plan.elements}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph" and answer.solution_svg_ref.startswith("<svg")
    assert [int(sympy.sympify(f.srepr)[1]) for f in answer.features] == freqs

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert {f.srepr for f in checker(mr).answer.features} == {f.srepr for f in answer.features}


@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize(
    "family,level,chart_kind",
    [
        ("math.g1_l54.graph_table", 3, "histogram"),
        ("math.g1_l58.graph_table", 2, "polygon"),
    ],
)
def test_compare_distribution_shape_property(seed, family, level, chart_kind):
    """2分布の比較: 散らばりも山の位置も必ず相異なる（同点で比較にならない退化を封じる）。"""
    _ctx, mr = _dist_mr(family, level, seed)
    fa = [int(f) for f in mr.params["frequencies"]]
    fb = [int(f) for f in mr.params["frequencies_b"]]

    assert mr.params["chart_kind"] == chart_kind
    assert len(fa) == len(fb)
    assert sum(fa) == sum(fb), "総度数がそろっていないと度数のまま重ねて比べられない"

    def span(fs):
        hits = [i for i, f in enumerate(fs) if f > 0]
        return hits[-1] - hits[0] + 1

    assert span(fa) != span(fb), "散らばりが同じで比較にならない"
    assert fa.count(max(fa)) == 1 and fb.count(max(fb)) == 1, "山が一意でない"
    assert fa.index(max(fa)) != fb.index(max(fb)), "山の位置が同じで偏りを比べられない"

    assert {e.kind for e in mr.visual_plan.elements} >= {"distribution"}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.kind == "choice"
    wider = "A組" if span(fa) > span(fb) else "B組"
    higher = "A組" if fa.index(max(fa)) > fb.index(max(fb)) else "B組"
    assert answer.correct == (
        f"散らばりが大きいのは{wider}、値の大きいほうの階級に偏っているのは{higher}"
    )
    assert len(answer.distractors) == 3
    assert answer.correct not in answer.distractors
    assert len(set(answer.distractors)) == 3

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert checker(mr).answer.correct == answer.correct


@pytest.mark.parametrize("seed", range(40))
def test_relative_frequency_polygon_property(seed):
    """g1_l55.graph_table Lv2: どの階級の相対度数も 0 や 1 に潰れず、分布が平らでない。"""
    _ctx, mr = _dist_mr("math.g1_l55.graph_table", 2, seed)
    freqs = [int(f) for f in mr.params["frequencies"]]
    total = sum(freqs)

    assert len(set(freqs)) > 1, "度数が全部同じ（折れ線が水平に潰れる）"
    for f in freqs:
        assert 0 < sympy.Rational(f, total) < 1, "相対度数が 0 または 1 に潰れている"

    assert "distribution" not in {e.kind for e in mr.visual_plan.elements}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph" and answer.solution_svg_ref.startswith("<svg")
    rel = [f for f in answer.features if f.kind == "relative_frequency"]
    vertices = [f for f in answer.features if f.kind == "polygon_vertex"]
    assert len(rel) == len(freqs) and len(vertices) == len(freqs)
    assert [sympy.sympify(f.srepr)[1] for f in rel] == [
        sympy.Rational(f, total) for f in freqs
    ]

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert {f.srepr for f in checker(mr).answer.features} == {f.srepr for f in answer.features}


@pytest.mark.parametrize("seed", range(40))
def test_compare_relative_frequency_chart_property(seed):
    """g1_l55.graph_table Lv3: 総度数も対象階級の相対度数も相異なる（比較が成立する）。"""
    _ctx, mr = _dist_mr("math.g1_l55.graph_table", 3, seed)
    fa = [int(f) for f in mr.params["frequencies"]]
    fb = [int(f) for f in mr.params["frequencies_b"]]
    idx = int(mr.params["target_index"])
    ta, tb = sum(fa), sum(fb)

    assert ta != tb, "総度数が同じでは「相対度数でそろえて比べる」意味が立たない"
    rel_a, rel_b = sympy.Rational(fa[idx], ta), sympy.Rational(fb[idx], tb)
    assert rel_a != rel_b, "相対度数が同じでどちらが大きいか決まらない"
    assert 0 < rel_a < 1 and 0 < rel_b < 1

    assert {e.kind for e in mr.visual_plan.elements} >= {"distribution"}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.srepr == sympy.srepr(sympy.Tuple(rel_a, rel_b))
    assert ("Aのほうが大きい" if rel_a > rel_b else "Bのほうが大きい") in answer.display

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert checker(mr).answer.srepr == answer.srepr


@pytest.mark.parametrize("seed", range(40))
def test_cumulative_frequency_chart_property(seed):
    """g1_l56.graph_table Lv2: 累積度数が真に増加し、度数が全部同じ（直線）でない。"""
    _ctx, mr = _dist_mr("math.g1_l56.graph_table", 2, seed)
    freqs = [int(f) for f in mr.params["frequencies"]]

    assert mr.params["chart_kind"] == "cumulative"
    assert all(f >= 1 for f in freqs)
    assert len(set(freqs)) > 1, "度数が全部同じで累積の折れ線が直線に潰れる"
    # 導出値（累積度数）を params に置かない＝検証に穴をあけない。
    assert set(mr.params) == {"class_lo", "class_width", "frequencies", "unit", "chart_kind"}

    cums = []
    running = 0
    for f in freqs:
        running += f
        cums.append(running)
    assert all(cums[i] < cums[i + 1] for i in range(len(cums) - 1))

    assert "distribution" not in {e.kind for e in mr.visual_plan.elements}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph" and answer.solution_svg_ref.startswith("<svg")
    assert [int(sympy.sympify(f.srepr)[1]) for f in answer.features] == cums

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert {f.srepr for f in checker(mr).answer.features} == {f.srepr for f in answer.features}


@pytest.mark.parametrize("seed", range(40))
def test_median_class_from_cumulative_property(seed):
    """g1_l56.graph_table Lv3: 総度数が奇数で、中央値の階級は内側（端に寄らない）。"""
    _ctx, mr = _dist_mr("math.g1_l56.graph_table", 3, seed)
    freqs = [int(f) for f in mr.params["frequencies"]]
    lo, width = int(mr.params["class_lo"]), int(mr.params["class_width"])
    total = sum(freqs)

    assert total % 2 == 1, "総度数が偶数だと「ちょうど半分」で階級が一意に決まらない"
    assert len(set(freqs)) > 1

    cums = []
    running = 0
    for f in freqs:
        running += f
        cums.append(running)
    idx = [i for i, c in enumerate(cums) if 2 * c > total][0]
    assert 0 < idx < len(freqs) - 1, "中央値の階級が端に寄っていて読まずに分かる"

    assert {e.kind for e in mr.visual_plan.elements} >= {"distribution"}
    _assert_chart_labels_cover_svg(mr)

    expected = sympy.Tuple(
        sympy.Integer(lo + width * idx), sympy.Integer(lo + width * (idx + 1))
    )
    assert mr.sub_questions[0].answer.srepr == sympy.srepr(expected)

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert checker(mr).answer.srepr == mr.sub_questions[0].answer.srepr


@pytest.mark.parametrize("seed", range(40))
def test_overlay_frequency_polygons_property(seed):
    """g1_l58.graph_table Lv3: 2本が一致せず、総度数がそろい、山の位置がずれている。"""
    _ctx, mr = _dist_mr("math.g1_l58.graph_table", 3, seed)
    fa = [int(f) for f in mr.params["frequencies"]]
    fb = [int(f) for f in mr.params["frequencies_b"]]

    assert fa != fb, "2本が同一で重ねて比べる意味がない"
    assert sum(fa) == sum(fb), "総度数がそろっていないと度数のまま重ねられない"
    assert fa.count(max(fa)) == 1 and fb.count(max(fb)) == 1
    assert fa.index(max(fa)) != fb.index(max(fb)), "山の位置が同じで傾向のちがいが出ない"

    assert "distribution" not in {e.kind for e in mr.visual_plan.elements}
    _assert_chart_labels_cover_svg(mr)

    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph" and answer.solution_svg_ref.startswith("<svg")
    kinds = [f.kind for f in answer.features]
    assert kinds.count("polygon_vertex_a") == len(fa)
    assert kinds.count("polygon_vertex_b") == len(fb)

    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    assert {f.srepr for f in checker(mr).answer.features} == {f.srepr for f in answer.features}


# ---------------------------------------------------------------------------
# C11 箱ひげ図の graph_table（g2_l56 / g2_l57）
#
# ゲートが素通りする退化をここで固定する:
#   - 箱が潰れる（Q1=Q3）・ひげが無い（最小値=Q1／Q3=最大値）
#   - 2本比較で A と B が同じ分布／比べる統計量が一致して「違い」が消える
#   - 「かく」セルの問題図に答え（箱ひげ）が先出しされる
# あわせて G-Q5t 漏洩の設計（「読む」セルの given に算用数字を書かない）も固定する。
# ---------------------------------------------------------------------------
_BOX_PLOT_ASCII_DIGIT_RE = re.compile(r"[0-9]")


def _box_plot_mr(family: str, level: int, seed: int):
    ctx = _make_ctx(family, level)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    return ctx, mr


def _assert_box_plot_axis(mr) -> tuple[int, int]:
    """軸の整合（左端0・右端=間隔×目もり本数）を確かめ、(axis_lo, axis_step) を返す。"""
    from engine.packs.math.visuals.distribution_chart import box_plot_labels

    axis_lo = int(mr.params["axis_lo"])
    axis_hi = int(mr.params["axis_hi"])
    axis_step = int(mr.params["axis_step"])
    assert axis_step > 0
    assert (axis_hi - axis_lo) % axis_step == 0
    # 図に描かれる <text> は軸目盛だけ。labels はヘルパから機械的に作られている（G-Q5v）。
    assert mr.visual_plan is not None
    assert mr.visual_plan.labels == box_plot_labels(mr.params)
    return axis_lo, axis_step


def _assert_non_degenerate_ticks(ticks: list[int]) -> None:
    """箱ひげが潰れていない（狭義単調増加）ことを固定する。"""
    assert len(ticks) == 5
    assert all(ticks[i] < ticks[i + 1] for i in range(4)), f"箱ひげが潰れている: {ticks}"


@pytest.mark.parametrize("seed", range(40))
def test_box_plot_read_values_property(seed):
    """g2_l56.graph_table Lv1: 箱ひげ図から二つの値を読む。"""
    ctx, mr = _box_plot_mr("math.g2_l56.graph_table", 1, seed)
    assert mr.signature == "box_plot_read_values"
    assert set(mr.given) == {"situation_params", "condition"}
    assert [sq.asked for sq in mr.sub_questions] == ["read_box_plot"]

    axis_lo, axis_step = _assert_box_plot_axis(mr)
    ticks = [int(t) for t in mr.params["box_ticks"]]
    _assert_non_degenerate_ticks(ticks)

    # five_number は tick から一意に決まる描画座標（＝図に描かれている位置）。
    five = [int(v) for v in mr.params["five_number"]]
    assert five == [axis_lo + axis_step * t for t in ticks]
    assert min(five) >= axis_lo and max(five) <= int(mr.params["axis_hi"])

    # 「読む」セルの given には算用数字を書かない（whitelist は given から作られるため、
    # ここに数字を混ぜると漏洩検査が甘くなる/誤検出する）。
    for v in mr.given.values():
        assert not _BOX_PLOT_ASCII_DIGIT_RE.search(v), f"given に算用数字: {v!r}"

    # 読む対象そのもの（箱ひげ）は図に描く。値の注記は描かない。
    kinds = [e.kind for e in mr.visual_plan.elements]
    assert "box_plot" in kinds and "number_line" in kinds
    assert "labeled_box_plot_value" not in kinds

    # 答えは5数要約のうちの二つ。
    answer = mr.sub_questions[0].answer
    values = list(sympy.sympify(answer.srepr))
    assert len(values) == 2
    assert all(int(v) in five for v in values)
    assert values[0] < values[1]

    checker = REGISTRY.checker("math.read_box_plot.double_solve")
    assert checker(mr).answer.srepr == answer.srepr


@pytest.mark.parametrize("seed", range(40))
def test_box_plot_draw_from_data_property(seed):
    """g2_l56.graph_table Lv3: データから5数要約を求め箱ひげ図をかく。"""
    from engine.packs.math.visuals.distribution_chart import render_box_plot_svg

    ctx, mr = _box_plot_mr("math.g2_l56.graph_table", 3, seed)
    assert mr.signature == "box_plot_draw_from_data"
    assert set(mr.given) == {"data_table"}
    assert [sq.asked for sq in mr.sub_questions] == ["draw_box_plot"]

    axis_lo, axis_step = _assert_box_plot_axis(mr)
    axis_hi = int(mr.params["axis_hi"])
    data = [int(v) for v in mr.params["data"]]
    assert len(data) >= 8
    assert len(set(data)) == len(data), "データに同値がある（5数要約が潰れうる）"
    assert all(axis_lo < v < axis_hi for v in data), "データが数直線の内側に収まっていない"

    # 5数要約は狭義単調増加（箱もひげも潰れない）。
    five = [sympy.sympify(str(v)) for v in mr.params["five_number"]]
    assert len(five) == 5
    assert all(five[i] < five[i + 1] for i in range(4)), f"5数要約が潰れている: {five}"

    answer = mr.sub_questions[0].answer
    assert answer.kind == "graph"
    assert [f.kind for f in answer.features] == ["min", "q1", "median", "q3", "max"]
    assert [sympy.sympify(f.srepr) for f in answer.features] == five

    # 問題図は数直線と目もりだけ（答えの箱ひげを先出ししない）。模範解答図は箱ひげつき。
    assert [e.kind for e in mr.visual_plan.elements] == ["number_line"]
    problem_svg = render_box_plot_svg(mr.params, draw=False)
    assert problem_svg.count("<rect") == 1  # 背景だけ＝箱が無い
    assert answer.solution_svg_ref.count("<rect") > 1  # 背景＋箱

    checker = REGISTRY.checker("math.draw_box_plot_from_data.double_solve")
    got = checker(mr).answer
    assert {f.srepr for f in got.features} == {f.srepr for f in answer.features}


@pytest.mark.parametrize("seed", range(40))
def test_two_box_plots_compare_property(seed):
    """g2_l57.graph_table Lv1/Lv3: 2本の箱ひげ図を読む／比べる。"""
    specs = [
        (1, "box_plot_compare_center_spread", "math.read_two_box_plots.double_solve", (0, 4)),
        (3, "box_plot_compare_iqr", "math.compare_two_box_plots_iqr.double_solve", (1, 3)),
    ]
    op_seqs = []
    for level, signature, checker_name, (lo_i, hi_i) in specs:
        ctx, mr = _box_plot_mr("math.g2_l57.graph_table", level, seed)
        assert mr.signature == signature
        assert set(mr.given) == {"situation_params"}
        assert [sq.asked for sq in mr.sub_questions] == ["read_box_plot"]

        axis_lo, axis_step = _assert_box_plot_axis(mr)
        ticks_a = [int(t) for t in mr.params["box_ticks_a"]]
        ticks_b = [int(t) for t in mr.params["box_ticks_b"]]
        _assert_non_degenerate_ticks(ticks_a)
        _assert_non_degenerate_ticks(ticks_b)

        # 2本が同じ分布だと「比べる」が成立しない。比べる統計量も相異であること。
        assert ticks_a != ticks_b, "2本の箱ひげ図が同一（比較が成り立たない）"
        stat_a = ticks_a[hi_i] - ticks_a[lo_i]
        stat_b = ticks_b[hi_i] - ticks_b[lo_i]
        assert stat_a != stat_b, f"比べる統計量が一致している: {stat_a}"

        assert [int(v) for v in mr.params["five_number"]] == [
            axis_lo + axis_step * t for t in ticks_a
        ]
        assert [int(v) for v in mr.params["five_number_b"]] == [
            axis_lo + axis_step * t for t in ticks_b
        ]

        for v in mr.given.values():
            assert not _BOX_PLOT_ASCII_DIGIT_RE.search(v), f"given に算用数字: {v!r}"

        kinds = [e.kind for e in mr.visual_plan.elements]
        assert "box_plot" in kinds and "number_line" in kinds

        answer = mr.sub_questions[0].answer
        checker = REGISTRY.checker(checker_name)
        assert checker(mr).answer.srepr == answer.srepr

        # 差（最後の成分）は正＝「違い」が読み取れる（Lv3）。
        values = list(sympy.sympify(answer.srepr))
        if level == 3:
            assert values[-1] > 0
            assert values[-1] == abs(values[0] - values[1])
        op_seqs.append(tuple(s.op for s in mr.sub_questions[0].steps))

    # level_sep: Lv1 と Lv3 で op 列（＝fp の中身）が相異する。
    assert op_seqs[0] != op_seqs[1]


@pytest.mark.parametrize("seed", range(20))
def test_box_plot_level_sep_op_sequences(seed):
    """g2_l56.graph_table: Lv1（読む2手）と Lv3（求めてかく3手）で op 列が相異する。"""
    _, mr1 = _box_plot_mr("math.g2_l56.graph_table", 1, seed)
    _, mr3 = _box_plot_mr("math.g2_l56.graph_table", 3, seed)
    ops1 = tuple(s.op for s in mr1.sub_questions[0].steps)
    ops3 = tuple(s.op for s in mr3.sub_questions[0].steps)
    assert ops1 == ("read_axis_step", "read_box_plot_values")
    assert ops3 == ("sort_data", "compute_five_number", "draw_box_plot")
    assert set(mr1.given) != set(mr3.given)


@pytest.mark.parametrize("seed", range(40))
def test_word_problem_box_plot_compare_property(seed):
    """g2_l57.word_problem Lv2: 誘導あり2小問。どちらの比較も引き分けにならない。"""
    ctx, mr = _box_plot_mr("math.g2_l57.word_problem", 2, seed)
    assert mr.signature == "word_problem_box_plot_compare_guided"
    assert set(mr.given) == {"scenario"}
    assert [sq.label for sq in mr.sub_questions] == ["(1)", "(2)"]
    assert [sq.asked for sq in mr.sub_questions] == ["value", "value"]

    axis_lo, axis_step = _assert_box_plot_axis(mr)
    ticks_a = [int(t) for t in mr.params["box_ticks_a"]]
    ticks_b = [int(t) for t in mr.params["box_ticks_b"]]
    _assert_non_degenerate_ticks(ticks_a)
    _assert_non_degenerate_ticks(ticks_b)
    assert ticks_a != ticks_b
    # (1) 中央値 (2) 範囲 — どちらも引き分けだと「どちらが大きいか」に答えが定まらない。
    assert ticks_a[2] != ticks_b[2]
    assert (ticks_a[4] - ticks_a[0]) != (ticks_b[4] - ticks_b[0])

    for v in mr.given.values():
        assert not _BOX_PLOT_ASCII_DIGIT_RE.search(v), f"given に算用数字: {v!r}"

    answers = [sq.answer for sq in mr.sub_questions]
    assert all(a.kind == "choice" for a in answers)
    assert answers[0].correct == ("A" if ticks_a[2] > ticks_b[2] else "B")
    assert answers[1].correct == (
        "A" if (ticks_a[4] - ticks_a[0]) > (ticks_b[4] - ticks_b[0]) else "B"
    )
    for a in answers:
        assert a.distractors == [("B" if a.correct == "A" else "A")]

    checker = REGISTRY.checker("math.word_problem_box_plot_compare.double_solve")
    got = checker(mr)
    assert len(got) == 2
    assert [s.answer.correct for s in got] == [a.correct for a in answers]


@pytest.mark.parametrize("seed", range(40))
def test_word_problem_box_plot_trend_property(seed):
    """g2_l57.word_problem Lv3: 傾向の主張の当否。中央値は必ずBが上（主張に根拠がある）。"""
    ctx, mr = _box_plot_mr("math.g2_l57.word_problem", 3, seed)
    assert mr.signature == "word_problem_box_plot_judge_trend"
    assert set(mr.given) == {"scenario", "quantities"}
    assert [sq.asked for sq in mr.sub_questions] == ["value"]

    _assert_box_plot_axis(mr)
    ticks_a = [int(t) for t in mr.params["box_ticks_a"]]
    ticks_b = [int(t) for t in mr.params["box_ticks_b"]]
    _assert_non_degenerate_ticks(ticks_a)
    _assert_non_degenerate_ticks(ticks_b)
    assert ticks_a != ticks_b
    # 中央値では必ず B が上＝「Bのほうが大きい傾向がある」に一応の根拠が常にある
    # （常に "いえない" が正解になる退化を防ぐ）。
    assert ticks_b[2] > ticks_a[2]
    # 構成が狙った結論と solver の判定が一致していること。
    expected = "いえる" if (ticks_b[1] > ticks_a[1] and ticks_b[3] > ticks_a[3]) else "いえない"

    for v in mr.given.values():
        assert not _BOX_PLOT_ASCII_DIGIT_RE.search(v), f"given に算用数字: {v!r}"

    answer = mr.sub_questions[0].answer
    assert answer.kind == "choice"
    assert answer.correct == expected
    assert answer.distractors == [("いえない" if expected == "いえる" else "いえる")]
    # 答えが params から直に読めないこと（構成時に狙った結論は params に置かない）。
    assert "supported" not in mr.params and "verdict" not in mr.params

    checker = REGISTRY.checker("math.word_problem_box_plot_trend.double_solve")
    assert checker(mr).answer.correct == answer.correct


@pytest.mark.parametrize("seed", range(40))
def test_word_problem_box_plot_stability_property(seed):
    """g2_l57.word_problem Lv4: 妥当性の批判的判断。支持する根拠は常に1本残す。"""
    ctx, mr = _box_plot_mr("math.g2_l57.word_problem", 4, seed)
    assert mr.signature == "word_problem_box_plot_judge_stability"
    assert set(mr.given) == {"scenario", "quantities"}

    _assert_box_plot_axis(mr)
    ticks_a = [int(t) for t in mr.params["box_ticks_a"]]
    ticks_b = [int(t) for t in mr.params["box_ticks_b"]]
    _assert_non_degenerate_ticks(ticks_a)
    _assert_non_degenerate_ticks(ticks_b)
    assert ticks_a != ticks_b
    # 「多い」＝中央値が大きいは常に成立（支持する根拠が必ず1本ある）。
    assert ticks_a[2] > ticks_b[2]
    iqr_a, iqr_b = ticks_a[3] - ticks_a[1], ticks_b[3] - ticks_b[1]
    # 「安定している」の判定が引き分けにならない。
    assert iqr_a != iqr_b
    expected = "妥当である" if iqr_a < iqr_b else "妥当でない"

    for v in mr.given.values():
        assert not _BOX_PLOT_ASCII_DIGIT_RE.search(v), f"given に算用数字: {v!r}"

    answer = mr.sub_questions[0].answer
    assert answer.kind == "choice"
    assert answer.correct == expected
    assert "valid" not in mr.params and "verdict" not in mr.params

    checker = REGISTRY.checker("math.word_problem_box_plot_stability.double_solve")
    assert checker(mr).answer.correct == answer.correct


def test_word_problem_box_plot_answers_are_not_degenerate():
    """Lv3/Lv4 の結論が片方に潰れていない（ゲートは潰れを素通りする）。"""
    for level, pool in ((3, {"いえる", "いえない"}), (4, {"妥当である", "妥当でない"})):
        seen = set()
        for seed in range(1, 61):
            _, mr = _box_plot_mr("math.g2_l57.word_problem", level, seed)
            seen.add(mr.sub_questions[0].answer.correct)
        assert seen == pool, f"Lv{level} の結論が偏っている: {seen}"


def test_word_problem_box_plot_level_sep_op_sequences():
    """g2_l57.word_problem: Lv2/Lv3/Lv4 で小問数と op 列が相異する（fp 相異の実体）。"""
    shapes = []
    for level in (2, 3, 4):
        _, mr = _box_plot_mr("math.g2_l57.word_problem", level, 7)
        shapes.append(tuple(tuple(s.op for s in sq.steps) for sq in mr.sub_questions))
    assert shapes[0] == (
        ("read_median_both", "compare_median"),
        ("read_range_both", "compare_range"),
    )
    assert shapes[1] == (
        (
            "read_quartiles_both",
            "compare_center",
            "compare_quartile_positions",
            "judge_trend_claim",
        ),
    )
    assert shapes[2] == (
        (
            "read_medians_both",
            "read_iqr_both",
            "weigh_support_and_counter",
            "judge_claim_validity",
        ),
    )
    assert len(set(shapes)) == 3


# ---------------------------------------------------------------------------
# C3 g3_l31.word_problem（2次方程式の利用・動点）
#
# ゲートが素通りする退化をここで固定する:
#   - Lv3: 面積が x の1次式に潰れる（＝2次方程式にならない）／答えの時刻に P・Q が
#          もう辺の上にいない（場面が成立しない）
#   - Lv4: 答えが1つに潰れる（＝場合分けをしなくても正解できる）／求めた時刻が
#          その区間の外にある
# あわせて params 忠実性（numbers は本文に出ている数だけ）も固定する。
# ---------------------------------------------------------------------------
def _motion_wp_mr(level: int, seed: int):
    ctx = _make_ctx("math.g3_l31.word_problem", level)
    return ctx, REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )


@pytest.mark.parametrize("seed", range(40))
def test_word_problem_moving_points_area_property(seed):
    """g3_l31.word_problem Lv3: 面積が x の2次式になり、答えの時刻で場面が成立する。"""
    _ctx, mr = _motion_wp_mr(3, seed)
    assert mr.signature == "word_problem_moving_points_area_guided"
    assert set(mr.given.keys()) == {"scenario", "quantities"}

    n = mr.params["numbers"]
    side, speed, area = int(n["side"]), int(n["speed"]), int(n["area"])
    assert side > 0 and speed > 0 and area > 0
    # params に置くのは本文に出ている数だけ（導出値・答えを置かない）。
    assert set(n) == {"side", "speed", "area"}

    x = sympy.Symbol("x")
    (sq_f, sq_v) = mr.sub_questions
    assert (sq_f.asked, sq_v.asked) == ("formulation", "value")
    assert [s.op for s in sq_f.steps] == ["locate_points_pq", "express_area_in_x"]
    assert [s.op for s in sq_v.steps] == [
        "set_up_quadratic_equation", "solve_quadratic_equation",
    ]

    expr = sympy.sympify(sq_f.answer.srepr)
    # 2次式であること（1次に潰れない＝「2次方程式の利用」として成立する）。
    assert sympy.degree(expr, x) == 2
    assert expr == sympy.Rational(speed**2, 2) * x**2

    t0 = sympy.sympify(sq_v.answer.srepr)
    assert t0.is_positive
    # (1) の式に (2) の時刻を入れると本文の面積に戻る。
    assert sympy.simplify(expr.subs(x, t0) - area) == 0
    # 答えの時刻で P・Q はまだ辺の上にいる（場面が成立している）。
    assert speed * t0 < side
    # 答えが本文の数値と一致しない（図を見ずに当てられない）。
    assert int(t0) not in {side, speed, area}

    checker = REGISTRY.checker("math.word_problem_moving_points_area.double_solve")
    assert [s.answer.srepr for s in checker(mr)] == [
        sq_f.answer.srepr, sq_v.answer.srepr,
    ]


@pytest.mark.parametrize("seed", range(40))
def test_word_problem_moving_point_all_times_property(seed):
    """g3_l31.word_problem Lv4: 答えが必ず2つ＝場合分けが答えに効く。"""
    _ctx, mr = _motion_wp_mr(4, seed)
    assert mr.signature == "word_problem_moving_point_area_all_times"
    assert set(mr.given.keys()) == {"scenario"}

    n = mr.params["numbers"]
    side, speed, area = int(n["side"]), int(n["speed"]), int(n["area"])
    assert set(n) == {"side", "speed", "area"}

    sq = mr.sub_questions[0]
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "identify_intervals",
        "solve_on_increasing_interval",
        "check_constant_interval",
        "solve_on_decreasing_interval",
        "collect_all_times",
    ]

    times = sympy.sympify(sq.answer.srepr)
    # ★退化の封じ: 答えは必ず2つ（1つに潰れると場合分けをしなくても正解できる）。
    assert len(times) == 2
    t1, t3 = times
    assert t1 < t3
    # それぞれが「増えていく区間」「減っていく区間」の内側にある。
    assert 0 < t1 < sympy.Rational(side, speed)
    assert 2 * sympy.Rational(side, speed) < t3 <= 3 * sympy.Rational(side, speed)
    # 一定区間の面積より小さい（＝増減する2区間に必ず解が立つ）。
    assert area < sympy.Rational(side**2, 2)
    # どちらの時刻でも三角形の面積が本文の値に戻る（区間ごとの式で再計算）。
    assert sympy.Rational(side * speed, 2) * t1 == area
    assert sympy.Rational(side, 2) * (3 * side - speed * t3) == area
    # 答えが本文の数値と一致しない。
    assert not {int(t1), int(t3)} & {side, speed, area}

    checker = REGISTRY.checker("math.word_problem_moving_point_all_times.double_solve")
    assert checker(mr).answer.srepr == sq.answer.srepr


def test_word_problem_moving_point_level_sep():
    """Lv3 と Lv4 は given・小問数・op 列がすべて相異する（G6 の構造差）。"""
    shapes = []
    for level in (3, 4):
        _ctx, mr = _motion_wp_mr(level, 1)
        shapes.append(
            (
                tuple(sorted(mr.given)),
                len(mr.sub_questions),
                tuple(s.op for sq in mr.sub_questions for s in sq.steps),
            )
        )
    assert len(set(shapes)) == 2
    assert shapes[0][0] != shapes[1][0]
    assert shapes[0][1] != shapes[1][1]
    assert shapes[0][2] != shapes[1][2]


# ---------------------------------------------------------------------------
# C1 g1_l27.word_problem Lv4（往復の道のりと平均の速さ・作問セルの再定義）
#
# ゲートが素通りする退化をここで固定する:
#   - 行きと帰りの速さが同じ（往復が2区間に分かれず x/a + x/a に潰れる）
#   - 答えが本文の数値と一致する（本文を読むだけで当たる）
#   - 平均の速さが調和平均（＝道のりに依らない）から外れる
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(40))
def test_word_problem_round_trip_average_speed_property(seed):
    ctx = _make_ctx("math.g1_l27.word_problem", 4)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    assert mr.signature == "word_problem_round_trip_average_speed"
    # 誘導なし＝変数の設定を与えない（Lv2 は scenario+quantities の2つ）。
    assert set(mr.given.keys()) == {"scenario"}

    n = mr.params["numbers"]
    a, b, t = (int(n["speed_go"]), int(n["speed_back"]), int(n["total_time"]))
    assert set(n) == {"speed_go", "speed_back", "total_time"}
    # 行きと帰りの速さが相異＝往復が2区間に分かれる（x/a + x/a に潰れない）。
    assert a != b and a > 0 and b > 0 and t > 0

    sq = mr.sub_questions[0]
    assert len(mr.sub_questions) == 1
    assert sq.asked == "value"
    assert [s.op for s in sq.steps] == [
        "set_up_round_trip_equation",
        "clear_denominators",
        "solve_for_one_way_distance",
        "compute_round_trip_distance",
        "compute_average_speed",
    ]

    distance, average = sympy.sympify(sq.answer.srepr)
    assert distance > 0 and average > 0
    # 片道の道のりは x/a + x/b = t の解である。
    assert sympy.simplify(distance / a + distance / b - t) == 0
    # 平均の速さは往復の道のり ÷ 往復の時間 ＝ 調和平均 2ab/(a+b)。
    assert sympy.simplify(average - 2 * distance / t) == 0
    assert sympy.simplify(average - sympy.Rational(2 * a * b, a + b)) == 0
    # 答えが本文の数値と一致しない（本文を読むだけで当たらない）。
    assert not {int(distance), int(average)} & {a, b, t}

    checker = REGISTRY.checker(
        "math.word_problem_round_trip_average_speed.double_solve"
    )
    assert checker(mr).answer.srepr == sq.answer.srepr


def test_word_problem_g1_l27_level_sep():
    """g1_l27 の Lv2/Lv3/Lv4 は given・小問数・op 列が相異する。"""
    shapes = []
    for level in (2, 3, 4):
        ctx = _make_ctx("math.g1_l27.word_problem", level)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(
            ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, 1)
        )
        shapes.append(
            (
                tuple(sorted(mr.given)),
                len(mr.sub_questions),
                tuple(s.op for sq in mr.sub_questions for s in sq.steps),
            )
        )
    assert len(set(shapes)) == 3
    # Lv4 は Lv3 と同じ「誘導なし1小問」だが op 列が違う（平均の速さまで出す）。
    assert shapes[1][0] == shapes[2][0] and shapes[1][1] == shapes[2][1]
    assert shapes[1][2] != shapes[2][2]


# ---------------------------------------------------------------------------
# C6 g3_l38.word_problem Lv4（グラフを構成してから時刻をすべて求める・融合）
#
# ゲートが素通りする退化をここで固定する:
#   - 折れ線が潰れる（増加区間・減少区間が無い＝全区間で一定）
#   - 答えの時刻が1つに潰れる（場合分けをしなくても正解できる）
#   - 答えの時刻が折れ点の外にある
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(40))
def test_word_problem_area_graph_and_times_property(seed):
    ctx = _make_ctx("math.g3_l38.word_problem", 4)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )
    assert mr.signature == "word_problem_area_graph_and_times"
    # 誘導なし＝変数の設定も区間の分割も与えない（Lv3 は区間を小問で与える）。
    assert set(mr.given.keys()) == {"scenario"}

    n = mr.params["numbers"]
    side, speed, area = int(n["side"]), int(n["speed"]), int(n["area"])
    assert set(n) == {"side", "speed", "area"}

    graph_sq, value_sq = mr.sub_questions
    assert (graph_sq.asked, value_sq.asked) == ("draw_graph", "value")
    assert graph_sq.answer.kind == "graph"
    assert [f.kind for f in graph_sq.answer.features] == ["breakpoint"] * 4
    assert [s.op for s in graph_sq.steps] == [
        "identify_intervals",
        "express_area_on_increasing_interval",
        "express_area_on_constant_interval",
        "express_area_on_decreasing_interval",
        "plot_breakpoints",
        "draw_polyline",
    ]

    pts = [sympy.sympify(f.srepr) for f in graph_sq.answer.features]
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    peak = sympy.Rational(side**2, 2)
    # 折れ点は (0,0) → (s/v, s²/2) → (2s/v, s²/2) → (3s/v, 0)。
    assert xs == [0, sympy.Rational(side, speed), 2 * sympy.Rational(side, speed),
                  3 * sympy.Rational(side, speed)]
    assert ys == [0, peak, peak, 0]
    # ★退化の封じ: 増加区間と減少区間が本当にある（全区間一定に潰れない）。
    assert ys[0] < ys[1] and ys[2] > ys[3]

    times = sympy.sympify(value_sq.answer.srepr)
    # ★退化の封じ: 答えは必ず2つ。
    assert len(times) == 2
    t_a, t_b = times
    # それぞれが増加区間・減少区間の内側にある（折れ点の間）。
    assert xs[0] < t_a < xs[1]
    assert xs[2] < t_b < xs[3]
    assert area < peak

    checker = REGISTRY.checker("math.word_problem_area_graph_and_times.double_solve")
    got = checker(mr)
    assert [f.srepr for f in got[0].answer.features] == [
        f.srepr for f in graph_sq.answer.features
    ]
    assert got[1].answer.srepr == value_sq.answer.srepr


def test_word_problem_g3_l38_level_sep():
    """g3_l38 の Lv3（誘導あり・式2つ）と Lv4（誘導なし・グラフ＋時刻）は相異する。"""
    shapes = []
    for level in (3, 4):
        ctx = _make_ctx("math.g3_l38.word_problem", level)
        mr = REGISTRY.recipe(ctx.spec_level.recipe)(
            ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, 1)
        )
        shapes.append(
            (
                tuple(sorted(mr.given)),
                tuple(sq.asked for sq in mr.sub_questions),
                tuple(s.op for sq in mr.sub_questions for s in sq.steps),
            )
        )
    assert len(set(shapes)) == 2
    assert shapes[0][1] == ("formulation", "formulation")
    assert shapes[1][1] == ("draw_graph", "value")


# ---------------------------------------------------------------------------
# Phase A 残り8セル（動点4・放物線2・1次関数の利用2）
#
# ゲートが素通りする退化をここで固定する。共通して見るのは
#   - 答えが本文の数値と一致しない（本文を読むだけで当たらない）
#   - 区間・場面の成立条件（動点が辺の上にいる／出会いが起きる）
#   - 答えが1つ・1:1 などに潰れない
# ---------------------------------------------------------------------------
def _cell_mr(family_name: str, level: int, seed: int):
    ctx = _make_ctx(family_name, level)
    return ctx, REGISTRY.recipe(ctx.spec_level.recipe)(
        ctx, derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    )


@pytest.mark.parametrize("seed", range(30))
def test_g2_l29_single_interval_area_property(seed):
    """g2_l29.word_problem Lv3: 面積が x の1次式で、答えの時刻に動点が辺の上にいる。"""
    _ctx, mr = _cell_mr("math.g2_l29.word_problem", 3, seed)
    n = mr.params["numbers"]
    side, speed, area = int(n["side"]), int(n["speed"]), int(n["area"])
    x = sympy.Symbol("x")
    expr_sq, time_sq = mr.sub_questions
    assert (expr_sq.asked, time_sq.asked) == ("formulation", "value")
    expr = sympy.sympify(expr_sq.answer.srepr)
    assert sympy.degree(expr, x) == 1
    assert expr == sympy.Rational(side * speed, 2) * x
    t0 = sympy.sympify(time_sq.answer.srepr)
    assert sympy.simplify(expr.subs(x, t0) - area) == 0
    # 答えの時刻に動点はまだ辺の上（場面が成立している）。
    assert 0 < speed * t0 <= side
    assert int(t0) not in {side, speed, area}
    checker = REGISTRY.checker("math.word_problem_single_interval_area.double_solve")
    assert [s.answer.srepr for s in checker(mr)] == [
        expr_sq.answer.srepr, time_sq.answer.srepr
    ]


@pytest.mark.parametrize("seed", range(30))
def test_g2_l29_interval_exprs_and_graph_property(seed):
    """g2_l29.word_problem Lv4: 3本の式が折れ点でつながり、増加・一定・減少が揃う。"""
    _ctx, mr = _cell_mr("math.g2_l29.word_problem", 4, seed)
    n = mr.params["numbers"]
    side, speed = int(n["side"]), int(n["speed"])
    exprs_sq, graph_sq = mr.sub_questions
    assert (exprs_sq.asked, graph_sq.asked) == ("formulation", "draw_graph")
    x = sympy.Symbol("x")
    rise, flat, fall = sympy.sympify(exprs_sq.answer.srepr)
    pts = [sympy.sympify(f.srepr) for f in graph_sq.answer.features]
    assert len(pts) == 4
    # 式と折れ線が同じものを指す（境目でつながる）。
    assert sympy.simplify(rise.subs(x, pts[1][0]) - pts[1][1]) == 0
    assert sympy.simplify(flat - pts[2][1]) == 0
    assert sympy.simplify(fall.subs(x, pts[3][0]) - pts[3][1]) == 0
    # ★退化の封じ: 増える区間と減る区間が本当にある（全区間一定に潰れない）。
    assert sympy.degree(rise, x) == 1 and sympy.degree(fall, x) == 1
    assert rise.coeff(x) > 0 > fall.coeff(x)
    assert flat == sympy.Rational(side**2, 2)
    assert speed > 0
    checker = REGISTRY.checker("math.word_problem_interval_exprs_and_graph.double_solve")
    got = checker(mr)
    assert got[0].answer.srepr == exprs_sq.answer.srepr
    assert [f.srepr for f in got[1].answer.features] == [
        f.srepr for f in graph_sq.answer.features
    ]


@pytest.mark.parametrize("seed", range(30))
def test_g2_l29_piecewise_area_graph_property(seed):
    """g2_l29.graph_table Lv3: 折れ点4つ・問題図は空の方眼（答えを先出ししない）。"""
    _ctx, mr = _cell_mr("math.g2_l29.graph_table", 3, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_graph"
    assert [f.kind for f in sq.answer.features] == ["breakpoint"] * 4
    assert mr.params["grid_mode"] == "quantity"
    # 問題図は方眼と軸だけ＝答えの折れ線を宣言しない。
    assert {e.kind for e in mr.visual_plan.elements} == {"grid", "axis"}
    assert sq.answer.solution_svg_ref.startswith("<svg")
    checker = REGISTRY.checker("math.draw_three_interval_area_graph.double_solve")
    assert [f.srepr for f in checker(mr).answer.features] == [
        f.srepr for f in sq.answer.features
    ]


@pytest.mark.parametrize("seed", range(30))
def test_g1_l36_max_area_and_times_property(seed):
    """g1_l36.word_problem Lv4: 最大の区間と、指定の面積になる時刻2つが揃う。"""
    _ctx, mr = _cell_mr("math.g1_l36.word_problem", 4, seed)
    n = mr.params["numbers"]
    side, speed, area = int(n["side"]), int(n["speed"]), int(n["area"])
    sq = mr.sub_questions[0]
    peak, t_lo, t_hi, t_a, t_b = sympy.sympify(sq.answer.srepr)
    assert peak == sympy.Rational(side**2, 2)
    assert t_lo == sympy.Rational(side, speed) and t_hi == 2 * t_lo
    # ★退化の封じ: 最大の区間に幅があり、指定の面積になる時刻が両側に1つずつある。
    assert t_lo < t_hi
    assert 0 < t_a < t_lo < t_hi < t_b
    assert area < peak
    assert not {int(t_a), int(t_b)} & {side, speed, area}
    checker = REGISTRY.checker("math.word_problem_max_area_and_times.double_solve")
    assert checker(mr).answer.srepr == sq.answer.srepr


@pytest.mark.parametrize("seed", range(30))
def test_g3_l37_parabola_line_guided_property(seed):
    """g3_l37.word_problem Lv3: 直線・面積・等積の点が互いに整合する。"""
    _ctx, mr = _cell_mr("math.g3_l37.word_problem", 3, seed)
    n = mr.params["numbers"]
    a, xA, xB = int(n["a"]), int(n["x_a"]), int(n["x_b"])
    # a=±1 だと係数が本文に出ない（params 忠実性契約）。
    assert abs(a) > 1 and xA != xB and xA != 0 and xB != 0
    x = sympy.Symbol("x")
    line_sq, area_sq, point_sq = mr.sub_questions
    assert [s.asked for s in mr.sub_questions] == ["formulation", "value", "value"]
    m, b = a * (xA + xB), -a * xA * xB
    assert sympy.simplify(sympy.sympify(line_sq.answer.srepr) - (m * x + b)) == 0
    # ★退化の封じ: 三角形 OAB がつぶれない（b≠0）。
    assert b != 0
    area = sympy.sympify(area_sq.answer.srepr)
    assert area > 0
    xP = sympy.sympify(point_sq.answer.srepr)
    # 等積の点は原点・A・B と重ならない。
    assert xP not in (0, xA, xB)
    assert xP == sympy.Rational(m, a)
    checker = REGISTRY.checker("math.word_problem_parabola_line_guided.double_solve")
    assert [s.answer.srepr for s in checker(mr)] == [
        line_sq.answer.srepr, area_sq.answer.srepr, point_sq.answer.srepr
    ]


@pytest.mark.parametrize("seed", range(30))
def test_g3_l37_parabola_area_ratio_property(seed):
    """g3_l37.word_problem Lv4: 面積比が 1:1 に潰れず、既約な整数比になる。"""
    _ctx, mr = _cell_mr("math.g3_l37.word_problem", 4, seed)
    sq = mr.sub_questions[0]
    p_, q_ = sympy.sympify(sq.answer.srepr)
    assert p_ > 0 and q_ > 0
    # ★退化の封じ: 比が 1:1 に潰れない（潰れると比を問う意味がない）。
    assert p_ != q_
    assert sympy.gcd(p_, q_) == 1
    checker = REGISTRY.checker("math.word_problem_parabola_area_ratio.double_solve")
    assert checker(mr).answer.srepr == sq.answer.srepr


@pytest.mark.parametrize("seed", range(30))
def test_g2_l28_tank_race_property(seed):
    """g2_l28.word_problem Lv4: 等しくなる時刻が場面の中にあり、量が一致する。"""
    _ctx, mr = _cell_mr("math.g2_l28.word_problem", 4, seed)
    n = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    cap, minutes, rate = n["capacity"], n["empty_minutes"], n["fill_rate"]
    drain = cap // minutes
    # ★退化の封じ: 抜く割合と入れる割合が同じ（ちょうど半分で出会う自明な場面）を排除。
    assert drain != rate
    t, amount = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert 0 < t < minutes
    assert cap - drain * t == amount == rate * t
    assert not {int(t), int(amount)} & {cap, minutes, rate, drain}
    checker = REGISTRY.checker("math.word_problem_linear_function.double_solve")
    assert [s.answer.srepr for s in checker(mr)] == [mr.sub_questions[0].answer.srepr]


@pytest.mark.parametrize("seed", range(30))
def test_g2_l30_second_meeting_property(seed):
    """g2_l30.word_problem Lv4: 1回目が往路・2回目が復路で、相手が着く前に起こる。"""
    _ctx, mr = _cell_mr("math.g2_l30.word_problem", 4, seed)
    n = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    d, va, vb, h = n["distance"], n["speed_a"], n["speed_b"], n["head_start"]
    # 折り返す側が速くないと追いつけない。
    assert va > vb > 0 and d > 0 and h > 0
    t2 = sympy.sympify(mr.sub_questions[0].answer.srepr)
    t_turn = sympy.Rational(d, va)
    t_first = sympy.Rational(d + vb * h, va + vb)
    # ★退化の封じ: 1回目が往路に収まり、2回目が復路で、相手が着く前に起きる。
    assert h <= t_first <= t_turn
    assert t_turn < t2 <= 2 * t_turn
    assert t2 <= h + sympy.Rational(d, vb)
    # その時刻に2人の位置が一致する。
    assert sympy.simplify((2 * d - va * t2) - (d - vb * (t2 - h))) == 0
    assert int(t2) not in {d, va, vb, h}
    checker = REGISTRY.checker("math.word_problem_linear_function.double_solve")
    assert [s.answer.srepr for s in checker(mr)] == [mr.sub_questions[0].answer.srepr]


# ---------------------------------------------------------------------------
# C8 g1_l53.find_value（球の表面積・体積）
#
# ★このセルは「params が半径ひとつだと dup が原理的に通らない」典型。軸を3つに
# したうえで、**与え方を足しても op 列が変わらない**（G-FP が安定する）ことを固定する。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(30))
def test_g1_l53_sphere_direct_property(seed):
    _ctx, mr = _cell_mr("math.g1_l53.find_value", 1, seed)
    p = mr.params
    r = int(p["radius"])
    assert r >= 2
    assert p["given_as"] in ("radius", "diameter")
    assert p["unit"] in ("cm", "m", "mm")
    # 与え方に関わらず op 列は同じ（第1手が variant 中立）。
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "read_radius_from_statement",
        "apply_sphere_surface_formula",
        "apply_sphere_volume_formula",
    ]
    surface, volume = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert surface == 4 * sympy.pi * r**2
    assert volume == sympy.Rational(4, 3) * sympy.pi * r**3
    # 本文の長さは与え方どおり（直径なら半径の2倍）。
    size = 2 * r if p["given_as"] == "diameter" else r
    assert f"{size}{p['unit']}" in mr.given["condition"]


@pytest.mark.parametrize("seed", range(30))
def test_g1_l53_hemisphere_property(seed):
    _ctx, mr = _cell_mr("math.g1_l53.find_value", 2, seed)
    p = mr.params
    r = int(p["radius"])
    # ★1レベル＝1 op 列。逆算 variant（2手）を混ぜていないこと。
    assert p["variant"] == "hemisphere_surface"
    assert [s.op for s in mr.sub_questions[0].steps] == [
        "read_radius_from_statement",
        "identify_hemisphere_faces",
        "compute_curved_and_flat_area",
        "sum_hemisphere_surface_area",
    ]
    # 半球の表面積 = 曲面 2πr² + 切り口の円 πr² = 3πr²
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) == 3 * sympy.pi * r**2


def test_g1_l53_level_sep():
    """Lv1（表面積と体積の組・3手）と Lv2（表面積だけ・4手）は相異する。"""
    shapes = []
    for level in (1, 2):
        _ctx, mr = _cell_mr("math.g1_l53.find_value", level, 1)
        shapes.append(tuple(s.op for s in mr.sub_questions[0].steps))
    assert shapes[0] != shapes[1]
    assert len(shapes[0]) != len(shapes[1])


# ---------------------------------------------------------------------------
# C8 g1_l49.graph_table（回転体）
#
# ゲートが素通りする退化・図の誤りをここで固定する:
#   - 底面の半径と高さが同じ（どちらがどちらから決まるかを問えない）
#   - 断面の横を半径のままにする（軸の両側に現れるので2倍が正しい・この単元の典型誤り）
#   - 問題図に答えの立体を先出しする
#   - 見取図に寸法が書かれていない（設問が「図中に書き入れよ」なのに答えていない）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(30))
def test_g1_l49_revolution_name_property(seed):
    _ctx, mr = _cell_mr("math.g1_l49.graph_table", 1, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "read_solid"
    assert [s.op for s in sq.steps] == [
        "identify_rotation_axis", "name_solid_of_revolution",
    ]
    expected = {"rectangle": "円柱", "right_triangle": "円錐", "semicircle": "球"}
    assert sq.answer.correct == expected[mr.params["shape"]]
    assert sq.answer.correct not in sq.answer.distractors
    # 問題図は回転させる元の平面図形＋軸だけ（答えの立体を先出ししない）。
    assert {e.kind for e in mr.visual_plan.elements} == {"rotation_source"}
    assert mr.params["view"] == "rotation_source"


@pytest.mark.parametrize("seed", range(30))
def test_g1_l49_revolution_sketch_property(seed):
    _ctx, mr = _cell_mr("math.g1_l49.graph_table", 2, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_solid"
    assert [s.op for s in sq.steps] == [
        "identify_rotation_axis", "determine_radius_and_height", "draw_solid_sketch",
    ]
    axis_len, other_len = int(mr.params["axis_len"]), int(mr.params["other_len"])
    # ★退化の封じ: 半径と高さが同じだと、どちらがどちらから決まるかを問えない。
    assert axis_len != other_len
    kinds = [f.kind for f in sq.answer.features]
    assert kinds == ["solid_name", "base_radius", "height"]
    # 底面の半径は軸に垂直な辺・高さは軸の辺。
    assert sq.answer.features[1].display.endswith(str(other_len))
    assert sq.answer.features[2].display.endswith(str(axis_len))
    # 半円（球）は Lv2 に出ない（高さが無く「書き入れよ」が成り立たない）。
    assert mr.params["shape"] in ("rectangle", "right_triangle")
    # 模範解答図に寸法が書かれている（設問が「図中に書き入れよ」）。
    svg = sq.answer.solution_svg_ref
    assert f"{other_len}cm" in svg and f"{axis_len}cm" in svg


@pytest.mark.parametrize("seed", range(30))
def test_g1_l49_revolution_section_property(seed):
    _ctx, mr = _cell_mr("math.g1_l49.graph_table", 3, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_solid"
    assert [s.op for s in sq.steps] == [
        "identify_section_plane", "determine_section_shape", "draw_section",
    ]
    axis_len, other_len = int(mr.params["axis_len"]), int(mr.params["other_len"])
    shape_of = {"rectangle": "長方形", "right_triangle": "二等辺三角形"}
    kinds = [f.kind for f in sq.answer.features]
    assert kinds == ["section_shape", "section_width", "section_height"]
    assert sq.answer.features[0].display == shape_of[mr.params["shape"]]
    # ★この単元の典型誤り: 切り口の横は軸の両側に現れるので半径の2倍。
    assert sq.answer.features[1].display.endswith(str(2 * other_len))
    assert sq.answer.features[2].display.endswith(str(axis_len))
    # 図の形も答えと一致する（円錐なら三角形・円柱なら四角形）。
    svg = sq.answer.solution_svg_ref
    n_pts = len(re.findall(r'<polygon points="([^"]+)"', svg)[0].split(" "))
    assert n_pts == (3 if mr.params["shape"] == "right_triangle" else 4)


def test_g1_l49_level_sep():
    """Lv1/Lv2/Lv3 は問う行為・答えの型・op 列がすべて相異する。"""
    shapes = []
    for level in (1, 2, 3):
        _ctx, mr = _cell_mr("math.g1_l49.graph_table", level, 1)
        sq = mr.sub_questions[0]
        shapes.append((sq.asked, sq.answer.kind, tuple(s.op for s in sq.steps)))
    assert len(set(shapes)) == 3
    assert shapes[0][1] == "choice" and shapes[1][1] == "graph"


# ---------------------------------------------------------------------------
# C8 g1_l50.graph_table（投影図）
#
# この単元の要点は「(立面図, 平面図) の組で立体が一意に決まる」こと。
# 対応表は solver 側が唯一の出典で、描画側はそれを引く（表を2か所に持つと
# 片方だけ直したときに図と答えが食い違う——実装中に一度ずれた）。
# ---------------------------------------------------------------------------
def test_g1_l50_projection_pairs_are_unique_and_shared():
    """★(立面図, 平面図) の組は7種の立体で相異＝立体が一意に決まる。

    かつ、描画側が solver 側と同じ表を引いている。
    """
    from engine.packs.math.solvers.solid_view import _PROJECTION, solid_from_views
    from engine.packs.math.visuals.solid import _projection_shapes

    assert len(set(_PROJECTION.values())) == len(_PROJECTION)
    for kind, (elev, plan) in _PROJECTION.items():
        assert solid_from_views(elev, plan) == kind
        assert _projection_shapes(kind) == (elev, plan)


@pytest.mark.parametrize("seed", range(30))
def test_g1_l50_projection_read_property(seed):
    _ctx, mr = _cell_mr("math.g1_l50.graph_table", 1, seed)
    from engine.packs.math.solvers.solid_view import projection_shapes, solid_name_jp

    sq = mr.sub_questions[0]
    assert sq.asked == "read_solid"
    assert [s.op for s in sq.steps] == [
        "read_elevation_and_plan", "identify_solid_from_projection",
    ]
    assert sq.answer.correct == solid_name_jp(mr.params["solid_kind"])
    # 問題図は投影図の両方（読む対象そのもの）。
    assert mr.params["shown_view"] == "both"
    assert {e.kind for e in mr.visual_plan.elements} == {"projection"}
    projection_shapes(mr.params["solid_kind"])  # 表に載っている立体だけを出す


@pytest.mark.parametrize("seed", range(30))
def test_g1_l50_projection_draw_property(seed):
    _ctx, mr = _cell_mr("math.g1_l50.graph_table", 2, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_solid"
    assert [s.op for s in sq.steps] == [
        "determine_elevation", "determine_plan", "draw_projection",
    ]
    # ★答えの先出し防止: 立体は本文で与え、問題図には投影図を出さない。
    assert mr.params["shown_view"] == "none"
    assert "立面図" not in (mr.given["condition"].split("。")[0])
    base, height = int(mr.params["base_len"]), int(mr.params["solid_height"])
    # ★退化の封じ: 底面と高さが同じだと正四角柱と立方体が図で区別できない。
    # ただし立方体と球は本文が高さを別に言わない（底面が高さを決める）ので、
    # 等しいのが正しい。相異にすると「1辺が14cmの立方体」の高さが3cm になる。
    if mr.params["solid_kind"] in {"cube", "sphere"}:
        assert base == height
    else:
        assert base != height
    # 模範解答図に寸法が書かれている（設問が「長さがわかるようにかけ」）。
    svg = sq.answer.solution_svg_ref
    assert f"{base}cm" in svg and f"{height}cm" in svg
    assert "立面図" in svg and "平面図" in svg


@pytest.mark.parametrize("seed", range(30))
def test_g1_l50_projection_complete_property(seed):
    _ctx, mr = _cell_mr("math.g1_l50.graph_table", 3, seed)
    from engine.packs.math.solvers.solid_view import projection_shapes, solid_name_jp

    sq = mr.sub_questions[0]
    assert sq.asked == "draw_solid"
    assert [s.op for s in sq.steps] == [
        "read_given_view", "identify_solid_from_partial", "draw_missing_view",
    ]
    # 問題図は平面図だけ（立面図は答え）。
    assert mr.params["shown_view"] == "plan"
    kinds = [f.kind for f in sq.answer.features]
    assert kinds == ["solid_name", "elevation_shape"]
    assert sq.answer.features[0].display == solid_name_jp(mr.params["solid_kind"])
    elev, _plan = projection_shapes(mr.params["solid_kind"])
    assert elev in sq.answer.features[1].srepr


def test_g1_l50_level_sep():
    """Lv1/Lv2/Lv3 は問う行為・答えの型・op 列・見せるビューがすべて相異する。"""
    shapes = []
    for level in (1, 2, 3):
        _ctx, mr = _cell_mr("math.g1_l50.graph_table", level, 1)
        sq = mr.sub_questions[0]
        shapes.append(
            (sq.asked, sq.answer.kind, mr.params["shown_view"], tuple(s.op for s in sq.steps))
        )
    assert len(set(shapes)) == 3
    assert len({s[2] for s in shapes}) == 3  # both / none / plan


# ---------------------------------------------------------------------------
# C8 g1_l51.graph_table（展開図）
#
# この単元の典型的な誤りは「側面の長方形の横＝1辺」と取り違えること。
# 正しくは底面の周の長さ（正n角柱なら n×1辺）。
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(30))
def test_g1_l51_prism_net_property(seed):
    _ctx, mr = _cell_mr("math.g1_l51.graph_table", 2, seed)
    sq = mr.sub_questions[0]
    assert sq.asked == "draw_solid"
    assert [s.op for s in sq.steps] == [
        "unfold_lateral_faces", "determine_side_rectangle_size", "draw_net",
    ]
    n = int(mr.params["base_edges"])
    base, height = int(mr.params["base_len"]), int(mr.params["solid_height"])
    assert n in (3, 4, 5, 6)
    # ★典型的な誤りの固定: 側面の長方形の横は底面の周（n×1辺）で、1辺ではない。
    h_f, w_f, _n_f = sq.answer.features
    assert h_f.display.endswith(str(height))
    assert w_f.display.endswith(str(n * base))
    assert n * base != base
    # ★退化の封じ: 縦と横が一致しない（一致すると横を正しく出せたか判別できない）。
    assert n * base != height and base != height
    # 展開図は側面 n 枚＋底面2枚で、底面は正n角形（頂点が n 個）。
    polys = re.findall(r'<polygon points="([^"]+)"', sq.answer.solution_svg_ref)
    assert len(polys) == n + 2
    base_polys = [p for p in polys if len(p.split(" ")) == n]
    assert len(base_polys) >= 2 if n != 4 else len(polys) == n + 2


@pytest.mark.parametrize("seed", range(30))
def test_g1_l51_composite_net_property(seed):
    _ctx, mr = _cell_mr("math.g1_l51.graph_table", 3, seed)
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == [
        "separate_lateral_surfaces", "unfold_cylinder_side",
        "unfold_cone_side", "draw_composite_net",
    ]
    r = int(mr.params["radius_len"])
    cone_h, cyl_h = int(mr.params["cone_height"]), int(mr.params["cylinder_height"])
    # ★母線は整数（無理数を答えさせない）。
    slant = sympy.sqrt(r * r + cone_h * cone_h)
    assert slant.is_Integer
    kinds = [f.kind for f in sq.answer.features]
    assert kinds == [
        "cylinder_side_height", "cylinder_side_width",
        "sector_radius", "sector_arc_length",
    ]
    # 円柱側面の横と、おうぎ形の弧の長さは、どちらも底面の円周 2πr で等しい。
    assert sq.answer.features[1].srepr == sq.answer.features[3].srepr
    assert sympy.sympify(sq.answer.features[1].srepr) == 2 * sympy.pi * r
    assert sympy.sympify(sq.answer.features[2].srepr) == slant
    assert sq.answer.features[0].display.endswith(str(cyl_h))
    # おうぎ形の中心角は 360°×(底面の半径/母線)。図の形が答えと合っている。
    assert abs(float(mr.params["sector_angle_deg"]) - 360.0 * r / int(slant)) < 1e-9


def test_g1_l51_level_sep():
    """Lv2（単一立体・3手）と Lv3（複合立体・4手）は相異する。"""
    shapes = []
    for level in (2, 3):
        _ctx, mr = _cell_mr("math.g1_l51.graph_table", level, 1)
        sq = mr.sub_questions[0]
        shapes.append((len(sq.answer.features), tuple(s.op for s in sq.steps)))
    assert len(set(shapes)) == 2
    assert shapes[0][0] != shapes[1][0]


# ---------------------------------------------------------------------------
# C10 g3_l55 / g3_l56（空間図形への三平方の利用・Phase B の残り4セル）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(25))
def test_g3_l55_box_section_property(seed):
    """g3_l55.graph_table Lv2: 断面の横は底面の対角線・対角線は立体の対角線。"""
    _ctx, mr = _cell_mr("math.g3_l55.graph_table", 2, seed)
    a, b, h = (int(mr.params[k]) for k in ("side_a", "side_b", "box_height"))
    # ★退化の封じ: 3辺が相異（立方体だと断面が正方形になり要点が消える）。
    assert len({a, b, h}) == 3
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == [
        "identify_section_plane", "compute_base_diagonal", "draw_section_with_diagonal",
    ]
    w_f, h_f, d_f = sq.answer.features
    assert sympy.sympify(w_f.srepr) == sympy.sqrt(a**2 + b**2)
    assert sympy.sympify(h_f.srepr) == h
    assert sympy.sympify(d_f.srepr) == sympy.sqrt(a**2 + b**2 + h**2)
    # 与えられた見取図は答えではないので "solid_given" で宣言する。
    assert {e.kind for e in mr.visual_plan.elements} == {"solid_given"}


@pytest.mark.parametrize("seed", range(25))
def test_g3_l56_box_unfold_property(seed):
    """g3_l56.graph_table Lv2: 開いた長方形は横 a+b・縦 h、経路はその対角線。"""
    _ctx, mr = _cell_mr("math.g3_l56.graph_table", 2, seed)
    a, b, h = (int(mr.params[k]) for k in ("side_a", "side_b", "box_height"))
    sq = mr.sub_questions[0]
    assert [s.op for s in sq.steps] == [
        "choose_two_faces", "unfold_to_plane", "draw_straight_path",
    ]
    w_f, h_f, p_f = sq.answer.features
    assert sympy.sympify(w_f.srepr) == a + b
    assert sympy.sympify(h_f.srepr) == h
    assert sympy.sympify(p_f.srepr) == sympy.sqrt((a + b) ** 2 + h**2)


@pytest.mark.parametrize("seed", range(25))
def test_g3_l55_cube_vertex_to_plane_property(seed):
    """g3_l55.word_problem Lv4: 垂線の長さは (√3/3)×1辺。体積が2通りで一致する。"""
    _ctx, mr = _cell_mr("math.g3_l55.word_problem", 4, seed)
    edge = int(sympy.sympify(mr.params["numbers"]["edge"]))
    sq = mr.sub_questions[0]
    assert len(mr.sub_questions) == 1  # 誘導なし
    assert [s.op for s in sq.steps] == [
        "express_volume_two_ways", "compute_equilateral_face_area", "solve_for_perpendicular",
    ]
    h = sympy.sympify(sq.answer.srepr)
    assert sympy.simplify(h - sympy.sqrt(3) * edge / 3) == 0
    # 恒真: 三角錐の体積が2通りの表し方で一致する。
    volume = sympy.Integer(edge) ** 3 / 6
    face = sympy.sqrt(3) / 2 * sympy.Integer(edge) ** 2
    assert sympy.simplify(face * h / 3 - volume) == 0


@pytest.mark.parametrize("seed", range(25))
def test_g3_l56_shortest_path_choose_property(seed):
    """g3_l56.word_problem Lv4: 最短は「小さい2辺を足す」開き方で、一意に決まる。"""
    _ctx, mr = _cell_mr("math.g3_l56.word_problem", 4, seed)
    n = {k: int(sympy.sympify(v)) for k, v in mr.params["numbers"].items()}
    a, b, c = n["edge_a"], n["edge_b"], n["height"]
    # ★退化の封じ: 3辺が相異（立方体だと3通りの開き方が同じ長さになる）。
    assert len({a, b, c}) == 3
    sq = mr.sub_questions[0]
    assert len(mr.sub_questions) == 1
    assert [s.op for s in sq.steps] == [
        "enumerate_unfoldings", "compare_three_paths", "compute_shortest_path",
    ]
    cands = sorted(
        [
            sympy.sqrt((a + b) ** 2 + c**2),
            sympy.sqrt((b + c) ** 2 + a**2),
            sympy.sqrt((c + a) ** 2 + b**2),
        ],
        key=lambda v: float(v.evalf()),
    )
    got = sympy.sympify(sq.answer.srepr)
    assert sympy.simplify(got - cands[0]) == 0
    # 最小は一意（2番目より真に小さい）。
    assert float(cands[0].evalf()) < float(cands[1].evalf())
    # 小さい2辺を足す開き方が最短。
    s1, s2, s3 = sorted([a, b, c])
    assert sympy.simplify(got - sympy.sqrt((s1 + s2) ** 2 + s3**2)) == 0


# ---------------------------------------------------------------------------
# C11 統計的な探究（g1_l58 / g3_l57 / g3_l58 の word_problem・Phase C）
#
# ゲートが素通りする退化をここで固定する:
#   - Lv2: 平均が等しく範囲が相異（「平均は同じなのに散らばりが違う」が見せ場）
#   - Lv3: 平均値・中央値・最頻値のすべてが同じ側を指す（＝指標を自分で選んでよい）
#   - 判断セル: 正解の選択肢がちょうど1つ／答えが片方に固定されない
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(25))
def test_g1_l58_compare_mean_range_property(seed):
    _ctx, mr = _cell_mr("math.g1_l58.word_problem", 2, seed)
    from engine.packs.math.recipes.statistics_inquiry import lists_from_numbers

    # データ列は numbers（本文に出ている数）から組み直す＝二重管理にしない。
    a, b = lists_from_numbers(mr.params["numbers"])
    assert len(a) == len(b) >= 8
    mean_sq, range_sq, judge_sq = mr.sub_questions
    ma, mb = sympy.sympify(mean_sq.answer.srepr)
    ra, rb = sympy.sympify(range_sq.answer.srepr)
    # ★見せ場: 平均は等しく、範囲は相異（範囲が等しいと安定なほうを決められない）。
    assert ma == mb
    assert ra != rb
    assert ma == sympy.Rational(sum(a), len(a))
    assert ra == max(a) - min(a) and rb == max(b) - min(b)
    # 安定しているのは範囲が小さいほう。
    assert judge_sq.answer.correct == ("A" if ra < rb else "B")
    checker = REGISTRY.checker("math.statistics_inquiry.double_solve")
    got = checker(mr)
    assert len(got) == 3


@pytest.mark.parametrize("seed", range(25))
def test_g1_l58_choose_statistic_property(seed):
    """★どの代表値で比べても同じ側＝「指標を自分で選んでよい」が成り立つ。"""
    _ctx, mr = _cell_mr("math.g1_l58.word_problem", 3, seed)
    from engine.packs.math.recipes.statistics_inquiry import lists_from_numbers

    a, b = lists_from_numbers(mr.params["numbers"])

    def mean(v):
        return sympy.Rational(sum(v), len(v))

    def median(v):
        o = sorted(v)
        n = len(o)
        return sympy.Integer(o[n // 2]) if n % 2 else sympy.Rational(o[n // 2 - 1] + o[n // 2], 2)

    def mode(v):
        c = {}
        for x in v:
            c[x] = c.get(x, 0) + 1
        top = max(c.values())
        winners = [k for k, n in c.items() if n == top]
        assert len(winners) == 1, winners  # 最頻値が一意
        return winners[0]

    smaller = bool(mr.params["smaller_is_better"])
    sides = set()
    for fa, fb in ((mean(a), mean(b)), (median(a), median(b)), (mode(a), mode(b))):
        assert fa != fb
        sides.add("A" if ((fa < fb) if smaller else (fa > fb)) else "B")
    assert len(sides) == 1
    assert mr.sub_questions[0].answer.correct == sides.pop()


@pytest.mark.parametrize("seed", range(25))
def test_g3_l57_judge_survey_method_property(seed):
    _ctx, mr = _cell_mr("math.g3_l57.word_problem", 2, seed)
    sq = mr.sub_questions[0]
    needs_sample = str(mr.params["needs_sample"]).lower() in ("true", "1")
    expected = "標本調査で行うのが適切" if needs_sample else "全数調査で行うのが適切"
    assert sq.answer.correct == expected
    assert sq.answer.correct not in sq.answer.distractors
    # 母集団の大きさは本文に出る数なので numbers に載っている（params 忠実性契約）。
    assert set(mr.params["numbers"]) == {"population"}
    assert mr.params["numbers"]["population"] in mr.given["scenario"]


def test_g3_l57_both_answers_occur():
    """★答えが片方に固定されない（場面を読まずに当てられない）。"""
    answers = set()
    for seed in range(40):
        _ctx, mr = _cell_mr("math.g3_l57.word_problem", 2, seed)
        answers.add(mr.sub_questions[0].answer.correct)
    assert len(answers) == 2, answers


@pytest.mark.parametrize("seed", range(25))
def test_choice_cells_have_exactly_one_correct(seed):
    """g3_l58 Lv2 と g1_l58 Lv4: 条件を満たす選択肢がちょうど1つ。"""
    for family, level in (("math.g3_l58.word_problem", 2), ("math.g1_l58.word_problem", 4)):
        _ctx, mr = _cell_mr(family, level, seed)
        flags = [int(v) for v in mr.params["flags"]]
        labels = [str(v) for v in mr.params["labels"]]
        assert sum(flags) == 1, (family, flags)
        assert len(labels) == 3
        sq = mr.sub_questions[0]
        assert sq.answer.correct == labels[flags.index(1)]
        assert sorted(sq.answer.distractors) == sorted(
            l for i, l in enumerate(labels) if not flags[i]
        )
        # 選択肢はすべて本文に出ている。
        for lab in labels:
            assert lab in mr.given["scenario"] or lab in "".join(mr.context_slots.values())


# ---------------------------------------------------------------------------
# C13 exam_l3（動点と面積変化）・exam_l1（一次関数と図形の融合）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(25))
def test_exam_l3_interval_area_uses_decreasing_interval(seed):
    """指定区間の式が x を含む（辺BC上＝一定になる退化に落ちていない）。"""
    _ctx, mr = _cell_mr("math.exam_l3.find_value", 3, seed)
    x = sympy.Symbol("x")
    expr, value = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert expr.has(x), expr
    n = mr.params["numbers"]
    s, v, x0 = int(n["side"]), int(n["speed"]), int(n["time"])
    # 指定の時刻は第3区間（面積が減っていく区間）の内側にある。
    assert 2 * s / v < x0 < 3 * s / v
    assert (expr.subs(x, x0) - value).equals(0)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l3_all_times_has_two_answers(seed):
    """場合分けが答えに効く（時刻が2つ立つ）。区間を1つ見落とすと落とす構成。"""
    for family, level in (("math.exam_l3.find_value", 4), ("math.exam_l3.word_problem", 4)):
        _ctx, mr = _cell_mr(family, level, seed)
        times = sympy.sympify(mr.sub_questions[-1].answer.srepr)
        assert len(times) == 2 and times[0] < times[1], (family, times)
        n = mr.params["numbers"]
        s, v = int(n["side"]), int(n["speed"])
        assert 0 < times[0] < s / v, times      # 増えていく区間
        assert 2 * s / v < times[1] <= 3 * s / v  # 減っていく区間


@pytest.mark.parametrize("seed", range(25))
def test_exam_l3_read_graph_values_are_on_grid(seed):
    """読み取らせる値が方眼の目盛にのっている（目盛の間だと図から読めない）。"""
    from engine.packs.math.recipes.motion import _quantity_grid_steps

    _ctx, mr = _cell_mr("math.exam_l3.graph_table", 2, seed)
    s, v, x0 = int(mr.params["side"]), int(mr.params["speed"]), int(mr.params["read_time"])
    x_step, y_step = _quantity_grid_steps(s, v)
    y0, t_lo, t_hi = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert x0 % x_step == 0 and y0 % y_step == 0, (x0, y0, x_step, y_step)
    assert t_lo % x_step == 0 and t_hi % x_step == 0, (t_lo, t_hi, x_step)
    assert t_lo == sympy.Rational(s, v) and t_hi == sympy.Rational(2 * s, v)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l3_guided_middle_interval_is_constant(seed):
    """(2) の答えは x を含まない定数（辺BC上では面積が変わらない）。"""
    _ctx, mr = _cell_mr("math.exam_l3.word_problem", 3, seed)
    x = sympy.Symbol("x")
    first = sympy.sympify(mr.sub_questions[0].answer.srepr)
    flat = sympy.sympify(mr.sub_questions[1].answer.srepr)
    assert first.has(x) and not flat.has(x), (first, flat)
    s = int(mr.params["numbers"]["side"])
    assert flat == sympy.Rational(s * s, 2)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l1_intersection_area_is_consistent(seed):
    """交点は2直線の両方の式を満たし、面積は底辺×高さ÷2 と一致する。"""
    _ctx, mr = _cell_mr("math.exam_l1.find_value", 3, seed)
    p = mr.params
    m1, b1, m2, b2 = p["m1"], p["b1"], p["m2"], p["b2"]
    pt, area = sympy.sympify(mr.sub_questions[0].answer.srepr)
    px, py = pt
    assert py == m1 * px + b1 and py == m2 * px + b2
    qx = sympy.Rational(-b2, m2)
    assert (area - sympy.Rational(1, 2) * abs(qx) * abs(py)).equals(0)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l1_coefficient_returns_to_given_area(seed):
    """逆算した傾きで三角形を組み直すと、問いで与えた面積に戻る。"""
    _ctx, mr = _cell_mr("math.exam_l1.find_value", 4, seed)
    b, area = sympy.Integer(mr.params["intercept"]), sympy.Integer(mr.params["area"])
    a = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert a > 0
    assert (sympy.Rational(1, 2) * abs(sympy.Rational(-b, a)) * b - area).equals(0)


def test_exam_l1_line_through_triangle_both_answers_occur():
    """★答えが片方に固定されない（図を見ずに当てられない）。"""
    answers = set()
    for seed in range(40):
        _ctx, mr = _cell_mr("math.exam_l1.graph_table", 2, seed)
        answers.add(mr.sub_questions[0].answer.correct)
    assert len(answers) == 2, answers


@pytest.mark.parametrize("seed", range(25))
def test_exam_l1_guided_three_subquestions_agree(seed):
    """(3) の面積が、(1) の交点と (2) の切片から底辺×高さ÷2 でも出る。"""
    _ctx, mr = _cell_mr("math.exam_l1.word_problem", 3, seed)
    assert len(mr.sub_questions) == 3
    pt = sympy.sympify(mr.sub_questions[0].answer.srepr)
    q1, q2 = sympy.sympify(mr.sub_questions[1].answer.srepr)
    area = sympy.sympify(mr.sub_questions[2].answer.srepr)
    assert q1[1] == 0 and q2[1] == 0
    assert (area - sympy.Rational(1, 2) * abs(q1[0] - q2[0]) * abs(pt[1])).equals(0)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l1_area_multiple_point_is_on_positive_x_axis(seed):
    """求めた点は x 軸の正の部分にあり、面積が指定の倍になる。"""
    _ctx, mr = _cell_mr("math.exam_l1.word_problem", 4, seed)
    numbers = mr.params["numbers"]
    m, b, k = (sympy.Integer(numbers[key]) for key in ("slope", "intercept", "multiple"))
    cx, cy = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert cx > 0 and cy == 0
    ax = sympy.Rational(-b, m)
    area_oab = sympy.Rational(1, 2) * abs(ax) * b
    area_abc = sympy.Rational(1, 2) * abs(cx - ax) * b
    assert (area_abc - k * area_oab).equals(0)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l2_coefficient_from_intersection(seed):
    """逆算した a のもとで A は本当に交点になり、面積は shoelace と一致する。"""
    _ctx, mr = _cell_mr("math.exam_l2.find_value", 4, seed)
    m, b, xa = (sympy.Integer(mr.params[k]) for k in ("m", "b", "x_a"))
    a, area = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert a != 0 and area > 0
    assert a * xa**2 == m * xa + b          # A は放物線と直線の両方の上にある
    roots = sympy.solve(sympy.Eq(a * sympy.Symbol("x") ** 2, m * sympy.Symbol("x") + b))
    assert len(roots) == 2 and xa in roots
    xb = roots[0] if roots[1] == xa else roots[1]
    expected = sympy.Rational(1, 2) * abs(xa * (a * xb**2) - xb * (a * xa**2))
    assert (area - expected).equals(0)


@pytest.mark.parametrize("seed", range(25))
def test_exam_l2_equal_area_point_is_valid(seed):
    """求めた P で三角形 PAB の面積が三角形 OAB と等しく、P は O・A・B と重ならない。"""
    _ctx, mr = _cell_mr("math.exam_l2.word_problem", 4, seed)
    n = mr.params["numbers"]
    a, xa, xb = (sympy.Integer(int(n[k])) for k in ("a", "x_a", "x_b"))
    xp = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert xp not in (0, xa, xb)

    def area(p, q, r):
        return sympy.Rational(1, 2) * abs(
            p[0] * (q[1] - r[1]) + q[0] * (r[1] - p[1]) + r[0] * (p[1] - q[1])
        )

    ptA, ptB = (xa, a * xa**2), (xb, a * xb**2)
    ptO, ptP = (sympy.Integer(0), sympy.Integer(0)), (xp, a * xp**2)
    assert (area(ptO, ptA, ptB) - area(ptP, ptA, ptB)).equals(0)


# ---------------------------------------------------------------------------
# C13 exam_l5（確率・複合事象／余事象）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(25))
def test_exam_l5_dice_guided_three_non_degenerate(seed):
    """Lv3: (1)は総数36通り、(2)(3)は 0 にも 1 にも潰れない（0/1 はゲートが弾かない）。"""
    _ctx, mr = _cell_mr("math.exam_l5.word_problem", 3, seed)
    faces = int(sympy.sympify(mr.params["numbers"]["faces"]))
    total = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert total == faces**2
    for sq in mr.sub_questions[1:]:
        p = sympy.sympify(sq.answer.srepr)
        assert 0 < p < 1, (sq.label, p)
    # (2) が和なら (3) は積、(2) が積なら (3) は和（同じ量を2回問わない）。
    numbers = mr.params["numbers"]
    assert {str(numbers["target_quantity"]), str(numbers["parity_quantity"])} == {"和", "積"}
    assert str(numbers["parity_word"]) in ("偶数", "奇数")


@pytest.mark.parametrize("seed", range(25))
def test_exam_l5_at_least_one_complement_is_consistent(seed):
    """Lv4: 答えは 1 −(対象が1個も入らない確率) と一致し、1 に潰れていない。"""
    _ctx, mr = _cell_mr("math.exam_l5.word_problem", 4, seed)
    numbers = mr.params["numbers"]
    a = int(sympy.sympify(numbers["count_target"]))
    b = int(sympy.sympify(numbers["count_other"]))
    k = int(sympy.sympify(numbers["draws"]))
    # 取り出す個数が対象でない色の個数以下＝余事象が起こりうる（1 への退化を防ぐ）。
    assert 1 <= k <= b
    expected = 1 - sympy.Rational(math.comb(b, k), math.comb(a + b, k))
    assert sympy.sympify(mr.sub_questions[0].answer.srepr) == expected
    assert 0 < expected < 1


# ---------------------------------------------------------------------------
# C13 exam_l6（相似と面積比・体積比の融合）
# ---------------------------------------------------------------------------
_EXAM_L6_CELLS = [
    ("math.exam_l6.find_value", 3, "exam_similar_solid_volume", 1),
    ("math.exam_l6.find_value", 4, "exam_cone_split_volume_ratio", 1),
    ("math.exam_l6.word_problem", 3, "exam_parallel_line_area_guided", 3),
    ("math.exam_l6.word_problem", 4, "exam_trapezoid_diagonal_ratios", 1),
]


@pytest.mark.parametrize(("family", "level", "signature", "n_subs"), _EXAM_L6_CELLS)
@pytest.mark.parametrize("seed", range(20))
def test_exam_l6_double_solve_property(seed, family, level, signature, n_subs):
    """全小問が checker の独立再計算と一致し、答えは params に入っていない。"""
    _ctx, mr = _cell_mr(family, level, seed)
    assert mr.signature == signature
    assert len(mr.sub_questions) == n_subs
    checker = REGISTRY.checker(f"{mr.provenance.recipe}.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr
    assert "answer" not in mr.params
    # params の数値はすべて場面文（given）に現れる。
    given_text = "".join(mr.given.values()) + "".join(mr.context_slots.values())
    for value in mr.params["numbers"].values():
        assert str(value) in given_text, (family, level, value)


@pytest.mark.parametrize("seed", range(20))
def test_exam_l6_similar_solid_volume_is_integer_multiple(seed):
    """Lv3: 体積比は相似比の三乗で、大きいほうの体積は整数になる。"""
    _ctx, mr = _cell_mr("math.exam_l6.find_value", 3, seed)
    n = mr.params["numbers"]
    m, k, known = int(n["ratio_num"]), int(n["ratio_den"]), int(n["known_volume"])
    assert m < k and math.gcd(m, k) == 1
    other = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert other == sympy.Integer(known) * k**3 / m**3
    assert other.is_Integer


@pytest.mark.parametrize("seed", range(20))
def test_exam_l6_cone_split_is_frustum_remainder(seed):
    """Lv4: 小円錐:円錐台 = k³:((k+l)³−k³)（引き算の合成が効いている）。"""
    _ctx, mr = _cell_mr("math.exam_l6.find_value", 4, seed)
    n = mr.params["numbers"]
    upper, lower = int(n["upper_part"]), int(n["lower_part"])
    small, frustum = sympy.sympify(mr.sub_questions[0].answer.srepr)
    expected_small = sympy.Integer(upper**3)
    expected_frustum = sympy.Integer((upper + lower) ** 3 - upper**3)
    g = sympy.gcd(expected_small, expected_frustum)
    assert (small, frustum) == (expected_small // g, expected_frustum // g)
    # 高さは分けた比で割り切れる（切り口の高さが整数になる場面にしてある）。
    assert int(n["height"]) % (upper + lower) == 0


@pytest.mark.parametrize("seed", range(20))
def test_exam_l6_parallel_line_area_guided_is_consistent(seed):
    """word_problem Lv3: 相似比 →面積比 →四角形の面積、が同じ比で貫かれている。"""
    _ctx, mr = _cell_mr("math.exam_l6.word_problem", 3, seed)
    n = mr.params["numbers"]
    ad, db, area_ade = int(n["ad"]), int(n["db"]), int(n["area_ade"])
    whole = ad + db
    r_num, r_den = sympy.sympify(mr.sub_questions[0].answer.srepr)
    a_num, a_den = sympy.sympify(mr.sub_questions[1].answer.srepr)
    quad = sympy.sympify(mr.sub_questions[2].answer.srepr)
    assert (r_num, r_den) == (sympy.Rational(ad, whole).p, sympy.Rational(ad, whole).q)
    assert (a_num, a_den) == (ad**2, whole**2)
    # 四角形DBCE = 三角形ABC − 三角形ADE（整数になるよう構成されている）。
    assert quad == sympy.Integer(area_ade) * (whole**2 - ad**2) / ad**2
    assert quad.is_Integer and quad > 0


@pytest.mark.parametrize("seed", range(20))
def test_exam_l6_trapezoid_uses_ratio_twice(seed):
    """word_problem Lv4: 面積比は相似比の二乗、倍率は相似比そのもの（使い分けが眼目）。"""
    _ctx, mr = _cell_mr("math.exam_l6.word_problem", 4, seed)
    n = mr.params["numbers"]
    ad, bc = int(n["ad"]), int(n["bc"])
    ratio_num, ratio_den, times = sympy.sympify(mr.sub_questions[0].answer.srepr)
    g = math.gcd(ad**2, bc**2)
    assert (ratio_num, ratio_den) == (ad**2 // g, bc**2 // g)
    assert times == sympy.Rational(ad, bc)
    assert ad != bc, "AD=BC だと平行四辺形になり、相似比が 1 に潰れる"


# ---------------------------------------------------------------------------
# C13 exam_l4（三平方の定理と空間図形）
# ---------------------------------------------------------------------------
_EXAM_L4_CELLS = [
    ("math.exam_l4.find_value", 3, "exam_box_space_diagonal", 1),
    ("math.exam_l4.find_value", 4, "exam_box_shortest_path_choose", 1),
    ("math.exam_l4.word_problem", 3, "exam_cube_guided", 3),
    ("math.exam_l4.word_problem", 4, "exam_regular_tetrahedron", 1),
]


@pytest.mark.parametrize(("family", "level", "signature", "n_subs"), _EXAM_L4_CELLS)
@pytest.mark.parametrize("seed", range(20))
def test_exam_l4_double_solve_property(seed, family, level, signature, n_subs):
    """全小問が checker の独立再計算と一致し、params の数値は本文に現れる。"""
    _ctx, mr = _cell_mr(family, level, seed)
    assert mr.signature == signature
    assert len(mr.sub_questions) == n_subs
    checker = REGISTRY.checker("math.word_problem_pythagorean.double_solve")
    solutions = checker(mr)
    assert len(solutions) == len(mr.sub_questions)
    for sol, sq in zip(solutions, mr.sub_questions, strict=True):
        assert sol.answer.srepr == sq.answer.srepr
    given_text = "".join(mr.given.values())
    for value in mr.params["numbers"].values():
        assert str(value) in given_text, (family, level, value)


@pytest.mark.parametrize("seed", range(20))
def test_exam_l4_box_space_diagonal_is_integer(seed):
    """find_value Lv3: 3辺は相異で、対角線は整数（読みやすさのために構成で保証）。"""
    _ctx, mr = _cell_mr("math.exam_l4.find_value", 3, seed)
    n = mr.params["numbers"]
    a, b, h = (int(n[k]) for k in ("edge_a", "edge_b", "height"))
    assert a != b and b != h and a != h
    diagonal = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert diagonal.is_Integer
    assert diagonal**2 == a**2 + b**2 + h**2


@pytest.mark.parametrize("seed", range(20))
def test_exam_l4_cube_guided_three_planes(seed):
    """word_problem Lv3: 3小問の答えは 1辺の √3 倍・(√3/2)倍の面積・√5 倍。

    同じ立方体を3通りの平面に落とすセルなので、3つの答えが**別々の無理数**に
    なることが要点（どれか2つが同じ形なら「落とし方が違う」ことが見えていない）。
    """
    _ctx, mr = _cell_mr("math.exam_l4.word_problem", 3, seed)
    a = sympy.Integer(int(mr.params["numbers"]["edge"]))
    diagonal, area, path = (sympy.sympify(sq.answer.srepr) for sq in mr.sub_questions)
    assert sympy.simplify(diagonal - a * sympy.sqrt(3)) == 0
    assert sympy.simplify(area - sympy.sqrt(3) / 2 * a**2) == 0
    assert sympy.simplify(path - a * sympy.sqrt(5)) == 0


@pytest.mark.parametrize("seed", range(20))
def test_exam_l4_regular_tetrahedron_height_volume(seed):
    """word_problem Lv4: 高さは 1辺の √6/3 倍、体積は 1辺³の √2/12 倍。"""
    _ctx, mr = _cell_mr("math.exam_l4.word_problem", 4, seed)
    a = sympy.Integer(int(mr.params["numbers"]["edge"]))
    height, volume = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert sympy.simplify(height - sympy.sqrt(6) / 3 * a) == 0
    assert sympy.simplify(volume - sympy.sqrt(2) / 12 * a**3) == 0
    # 体積 = 底面の正三角形の面積 × 高さ ÷ 3（別経路の確かめ）。
    base_area = sympy.sqrt(3) / 4 * a**2
    assert sympy.simplify(volume - base_area * height / 3) == 0


@pytest.mark.parametrize("seed", range(20))
def test_exam_l4_cube_section_figure_matches_labels(seed):
    """graph_table Lv2: 断面の長方形は、横＝1辺の√2倍・縦＝1辺（正方形に潰れない）。

    描画側の頂点の並びも合わせて固定する。横に並ぶ2点が縦の辺（高さ）になっていると、
    描かれた長方形の縦横と頂点名が食い違う（g3_l55 で実際に起きていた）。
    """
    _ctx, mr = _cell_mr("math.exam_l4.graph_table", 2, seed)
    a = sympy.Integer(int(mr.params["side_a"]))
    assert mr.params["side_a"] == mr.params["side_b"] == mr.params["box_height"]
    features = {f.kind: sympy.sympify(f.srepr) for f in mr.sub_questions[0].answer.features}
    width, height, diagonal = (
        features["section_width"], features["section_height"], features["body_diagonal"]
    )
    assert sympy.simplify(width - a * sympy.sqrt(2)) == 0
    assert height == a
    assert sympy.simplify(diagonal - a * sympy.sqrt(3)) == 0
    assert width != height, "断面が正方形に潰れていない"


# ---------------------------------------------------------------------------
# Phase E 端物: g3_l53.word_problem Lv4（補助線）・g2_l33.find_value Lv2（ブーメラン型）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(20))
def test_g3_l53_lv4_height_and_area_are_consistent(seed):
    """垂線の足は底辺の内側にあり、高さは2つの直角三角形の両方から同じ値になる。"""
    _ctx, mr = _cell_mr("math.g3_l53.word_problem", 4, seed)
    n = mr.params["numbers"]
    a, b, c = (int(n[k]) for k in ("base", "side_b", "side_c"))
    assert b != c, "二等辺だと垂線の足が中点に来て「未知数を置く」段が消える"
    height, area = sympy.sympify(mr.sub_questions[0].answer.srepr)
    x = sympy.Rational(c**2 - b**2 + a**2, 2 * a)
    assert 0 < x < a
    assert sympy.simplify(height**2 - (c**2 - x**2)) == 0
    assert sympy.simplify(height**2 - (b**2 - (a - x) ** 2)) == 0
    assert height.is_Integer, "高さが整数に落ちる組だけを候補にしている"
    assert sympy.simplify(area - sympy.Rational(1, 2) * a * height) == 0


@pytest.mark.parametrize("seed", range(20))
def test_g2_l33_lv2_arrowhead_is_sum_of_three_angles(seed):
    """内部の点がつくる角は3つの角の和で、平角未満（図が成立する）。"""
    _ctx, mr = _cell_mr("math.g2_l33.find_value", 2, seed)
    a, b, c = (int(mr.params[k]) for k in ("angle_a", "angle_b", "angle_c"))
    answer = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert answer == a + b + c
    assert 0 < answer < 180, "平角以上だと内部に点をとった図として成立しない"
    checker = REGISTRY.checker("math.arrowhead_angle.double_solve")
    assert checker(mr).answer.srepr == mr.sub_questions[0].answer.srepr


def test_g2_l33_levels_have_distinct_op_columns():
    """Lv1（2手）と Lv2（補助線を含む4手）で op 列が相異する（level_sep の骨）。"""
    _ctx1, mr1 = _cell_mr("math.g2_l33.find_value", 1, 1)
    _ctx2, mr2 = _cell_mr("math.g2_l33.find_value", 2, 1)
    ops1 = [s.op for s in mr1.sub_questions[0].steps]
    ops2 = [s.op for s in mr2.sub_questions[0].steps]
    assert ops1 != ops2
    assert "draw_auxiliary_line" in ops2


@pytest.mark.parametrize("seed", range(20))
def test_g3_l54_graph_table_right_triangle(seed):
    """g3_l54.graph_table Lv2: 直角の頂点は (x2, y1)、2辺は座標の差の絶対値。

    軸に平行に並ぶ2点（差の一方が 0）は三角形にならないので構成で除いてある。
    """
    _ctx, mr = _cell_mr("math.g3_l54.graph_table", 2, seed)
    x1, y1, x2, y2 = (int(mr.params[k]) for k in ("x1", "y1", "x2", "y2"))
    assert x1 != x2 and y1 != y2
    feats = {f.kind: sympy.sympify(f.srepr) for f in mr.sub_questions[0].answer.features}
    assert feats["right_angle_vertex"] == sympy.Tuple(x2, y1)
    assert feats["horizontal_leg"] == abs(x2 - x1)
    assert feats["vertical_leg"] == abs(y2 - y1)
    # 直角の頂点は描画側でも同じ点を使う（対応表を2か所に持たない）。
    assert mr.params["right_angle_pt"] == f"({x2}, {y1})"
    checker = REGISTRY.checker("math.coordinate_right_triangle.double_solve")
    recomputed = {f.kind: sympy.sympify(f.srepr) for f in checker(mr).answer.features}
    assert recomputed == feats


# ---------------------------------------------------------------------------
# Phase E 端物: 図の要素を記号で答える3セル（g1_l37 / g2_l32 / g2_l44 の graph_table Lv1）
# ---------------------------------------------------------------------------
_FIGURE_READING_CELLS = [
    ("math.g1_l37.graph_table", "identify_distance_segment", "math.identify_distance_segment"),
    ("math.g2_l32.graph_table", "identify_parallel_line", "math.identify_parallel_line"),
    ("math.g2_l44.graph_table", "identify_right_triangle_sides",
     "math.identify_right_triangle_sides"),
]


@pytest.mark.parametrize(("family", "signature", "recipe"), _FIGURE_READING_CELLS)
@pytest.mark.parametrize("seed", range(20))
def test_figure_reading_cells_shape(seed, family, signature, recipe):
    """3セル共通の骨格: read_figure_element の選択肢1問・図つき・答えは params に無い。"""
    _ctx, mr = _cell_mr(family, 1, seed)
    assert mr.signature == signature
    assert [(sq.label, sq.asked) for sq in mr.sub_questions] == [("(1)", "read_figure_element")]
    answer = mr.sub_questions[0].answer
    assert answer.kind == "choice"
    # 選択肢は相異で、正解が妨害に混ざっていない。
    assert answer.correct not in answer.distractors
    assert len(set(answer.distractors)) == len(answer.distractors)
    assert mr.visual_plan is not None and mr.visual_plan.elements
    assert set(mr.given) == {"condition"}
    checker = REGISTRY.checker(f"{recipe}.double_solve")
    assert checker(mr).answer.correct == answer.correct


@pytest.mark.parametrize("seed", range(20))
def test_g1_l37_distance_segment_options_are_all_in_figure(seed):
    """選択肢はすべて図に描かれている線分（図に無いものを混ぜると消去法で解ける）。"""
    _ctx, mr = _cell_mr("math.g1_l37.graph_table", 1, seed)
    p, h = mr.params["point_p"], mr.params["point_foot"]
    a, b = mr.params["point_left"], mr.params["point_right"]
    assert len({p, h, a, b}) == 4
    answer = mr.sub_questions[0].answer
    assert answer.correct == f"線分{p}{h}", "距離は垂線の長さ＝点と垂線の足を結ぶ線分"
    assert set(answer.distractors) == {f"線分{p}{a}", f"線分{p}{b}", f"線分{a}{b}"}


@pytest.mark.parametrize("seed", range(20))
def test_g2_l32_exactly_one_line_matches_base_angle(seed):
    """基準と同じ角の直線がちょうど1本（複数あると答えが定まらない）。"""
    _ctx, mr = _cell_mr("math.g2_l32.graph_table", 1, seed)
    base = int(mr.params["base_angle"])
    angles = [int(a) for a in mr.params["angles"]]
    names = [str(n) for n in mr.params["names"]]
    assert len(angles) == len(names)
    matched = [n for n, a in zip(names, angles, strict=True) if a == base]
    assert len(matched) == 1
    assert mr.sub_questions[0].answer.correct == f"直線{matched[0]}"
    # 角はすべて相異（同じ角が2本あると平行な組が2つできる）。
    assert len(set(angles)) == len(angles)


@pytest.mark.parametrize("seed", range(20))
def test_g2_l44_hypotenuse_is_opposite_the_right_angle(seed):
    """斜辺は直角の頂点をふくまない辺。妨害は斜辺の取り違え2通り。"""
    _ctx, mr = _cell_mr("math.g2_l44.graph_table", 1, seed)
    labels = [str(v) for v in mr.params["vertex_labels"]]
    idx = int(mr.params["right_angle_index"])
    right = labels[idx]
    others = [n for i, n in enumerate(labels) if i != idx]
    answer = mr.sub_questions[0].answer
    assert answer.correct == (
        f"斜辺は辺{others[0]}{others[1]}、"
        f"直角をはさむ2辺は辺{right}{others[0]}と辺{right}{others[1]}"
    )
    assert right not in f"{others[0]}{others[1]}"
    assert len(answer.distractors) == 2


# ---------------------------------------------------------------------------
# Phase E 端物: 樹形図に整理する2セル（g2_l52 / g2_l53 の graph_table Lv1）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("family", "signature", "with_replacement", "n_paths"),
    [
        ("math.g2_l52.graph_table", "tree_diagram_coins", True, 4),
        ("math.g2_l53.graph_table", "tree_diagram_draws", False, 6),
    ],
)
@pytest.mark.parametrize("seed", range(20))
def test_tree_diagram_cells(seed, family, signature, with_replacement, n_paths):
    """場合の列は itertools の列挙と一致し、重複が無い。総数の feature も一致する。"""
    import itertools

    _ctx, mr = _cell_mr(family, 1, seed)
    assert mr.signature == signature
    assert mr.params["with_replacement"] is with_replacement
    items = [str(v) for v in mr.params["items"]]
    draws = int(mr.params["draws"])
    expected = (
        list(itertools.product(items, repeat=draws))
        if with_replacement
        else list(itertools.permutations(items, draws))
    )
    assert len(expected) == n_paths
    features = mr.sub_questions[0].answer.features
    outcomes = [f.display for f in features if f.kind == "outcome"]
    assert outcomes == ["、".join(t) for t in expected]
    assert len(set(outcomes)) == len(outcomes), "同じ場合が2回出てはいけない"
    total = [f for f in features if f.kind == "total_count"]
    assert len(total) == 1 and sympy.sympify(total[0].srepr) == n_paths
    # 答え（場合の列）は checker が params から独立に列挙し直せる。
    checker = REGISTRY.checker("math.tree_diagram.double_solve")
    assert [f.display for f in checker(mr).answer.features] == [f.display for f in features]
    # 問題図には樹形図を描かない（描く対象は題材の絵だけ）。
    assert [e.kind for e in mr.visual_plan.elements] == ["subject_given"]


@pytest.mark.parametrize("seed", range(20))
def test_g2_l53_draws_do_not_repeat_the_same_item(seed):
    """もとに戻さないので、同じものが2回出る場合は樹形図に現れない。"""
    _ctx, mr = _cell_mr("math.g2_l53.graph_table", 1, seed)
    for f in mr.sub_questions[0].answer.features:
        if f.kind != "outcome":
            continue
        first, second = f.display.split("、")
        assert first != second


# ---------------------------------------------------------------------------
# Phase E 端物の締め: g2_l50 Lv3（面積2等分）・g2_l38 Lv2（逆と反例）・g1_l39 Lv3（回転の中心）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(20))
def test_g2_l50_lv3_bisects_the_quadrilateral(seed):
    """点Pは辺BC上にあり、三角形ABPの面積が四角形全体のちょうど半分になる。"""
    _ctx, mr = _cell_mr("math.g2_l50.find_value", 3, seed)
    p = mr.params
    quad = [(int(p["ax"]), int(p["ay"])), (int(p["bx"]), int(p["by"])),
            (int(p["cx"]), int(p["cy"])), (int(p["dx"]), int(p["dy"]))]

    def area(pts):
        total = sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                    - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
        return sympy.Rational(abs(total), 2)

    px, py = sympy.sympify(mr.sub_questions[0].answer.srepr)
    assert py == 0 and 0 < px < quad[2][0], "Pは辺BCの内側にある"
    assert area([quad[0], quad[1], (px, py)]) == area(quad) / 2
    checker = REGISTRY.checker("math.area_bisecting_point.double_solve")
    assert checker(mr).answer.srepr == mr.sub_questions[0].answer.srepr


@pytest.mark.parametrize("seed", range(25))
def test_g2_l38_lv2_converse_and_counterexample(seed):
    """(1)は逆（仮定と結論の入れかえ）、(2)は逆の仮定を満たし逆の結論を満たさない例。"""
    _ctx, mr = _cell_mr("math.g2_l38.knowledge", 2, seed)
    assert [sq.asked for sq in mr.sub_questions] == ["choice", "choice"]
    converse, counter = (sq.answer for sq in mr.sub_questions)
    # 否定形が「…であるない」のような壊れた日本語になっていない。
    for text in [converse.correct, *converse.distractors]:
        assert "であるない" not in text
    assert converse.correct not in converse.distractors
    assert counter.correct not in counter.distractors
    kind, a, b = str(mr.params["kind"]), int(mr.params["a"]), int(mr.params["b"])
    if kind == "multiple":
        # 反例は b の倍数だが a の倍数でない数（逆「bの倍数ならaの倍数」が偽である証拠）。
        n = int(counter.correct.split("=")[1])
        assert n % b == 0 and n % a != 0
        assert a % b == 0, "もとの命題（aの倍数ならbの倍数）が正しい構成になっている"
    elif kind == "greater":
        n = int(counter.correct.split("=")[1])
        assert n > b and not n > a
        assert a > b


@pytest.mark.parametrize("seed", range(20))
def test_g1_l39_lv3_center_is_equidistant_from_corresponding_points(seed):
    """回転の中心は、対応するすべての点の組から等距離にある。"""
    _ctx, mr = _cell_mr("math.g1_l39.graph_table", 3, seed)

    def parse(s):
        x, y = str(s).strip("() ").split(",")
        return sympy.Integer(int(x)), sympy.Integer(int(y))

    src = [parse(s) for s in mr.params["pts"]]
    dst = [parse(s) for s in mr.params["new_pts"]]
    feats = {f.kind: sympy.sympify(f.srepr) for f in mr.sub_questions[0].answer.features}
    ox, oy = feats["rotation_center"]
    for (px, py), (qx, qy) in zip(src, dst, strict=True):
        assert (ox - px) ** 2 + (oy - py) ** 2 == (ox - qx) ** 2 + (oy - qy) ** 2
    # 問題図に中心は描かない（描く要素の宣言に "point" が無い）。
    assert [e.kind for e in mr.visual_plan.elements] == ["grid", "axis", "polygon", "polygon"]
    checker = REGISTRY.checker("math.find_rotation_center.double_solve")
    assert checker(mr).answer.features[0].srepr == mr.sub_questions[0].answer.features[0].srepr
