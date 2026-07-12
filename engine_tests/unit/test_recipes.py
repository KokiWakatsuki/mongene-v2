"""Task5b: 数学パック recipe（構成的生成・answer-first）の unit テスト。

各 recipe を実 FamilySpec YAML（engine/curriculum/math/families）から読んだ
CellContext で construct し、MR が正しく組み立てられること・signature が spec と
一致すること・double-solve（独立ソルバでの再確認）が全 seed で一致することを
検証する（H4/H5）。200 seed の property テストで例外なし・答え一致を確認する。
"""
from __future__ import annotations

import math
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


def _families():
    return load_family_dir(FAMILIES_DIR)


def _make_ctx(family_name: str, level: int) -> CellContext:
    families = _families()
    spec_family = families[family_name]
    spec_level = spec_family.levels[str(level)]
    curriculum = load_curriculum()
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
