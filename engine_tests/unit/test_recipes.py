"""Task5b: 数学パック recipe（構成的生成・answer-first）の unit テスト。

各 recipe を実 FamilySpec YAML（engine/curriculum/math/families）から読んだ
CellContext で construct し、MR が正しく組み立てられること・signature が spec と
一致すること・double-solve（独立ソルバでの再確認）が全 seed で一致することを
検証する（H4/H5）。200 seed の property テストで例外なし・答え一致を確認する。
"""
from __future__ import annotations

import math
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
]


@pytest.mark.parametrize("family,level", _RULE_RECALL_CELLS)
@pytest.mark.parametrize("seed", range(100))
def test_recall_rule_double_solve_property(family, level, seed):
    ctx = _make_ctx(family, level)
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    mr = REGISTRY.recipe(ctx.spec_level.recipe)(ctx, rng)
    solver = REGISTRY.solver("math.recall_rule_statement")
    sol = solver(mr.params["topic"], mr.params["concept"])
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
    assert mr.signature == "quadratic_intersection_bisecting_point"
    sq = mr.sub_questions[0]
    assert sq.asked == "coordinate"
    assert [s.op for s in sq.steps] == [
        "set_up_equation", "solve_for_x", "compute_y",
        "compute_triangle_area", "solve_for_bisecting_point",
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

    # 場面文に、立式に使う数値がすべて現れている（G-GND の材料が本文にある）
    for value in numbers.values():
        assert str(value) in mr.given["scenario"]


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
