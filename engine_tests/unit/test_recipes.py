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


_SIGNED_ARITHMETIC_CELLS = [
    ("math.g1_l3.calculation", 1), ("math.g1_l3.calculation", 2),
    ("math.g1_l4.calculation", 1), ("math.g1_l4.calculation", 2),
    ("math.g1_l5.calculation", 1), ("math.g1_l5.calculation", 2),
    ("math.g1_l6.calculation", 1), ("math.g1_l6.calculation", 2),
    ("math.g1_l8.calculation", 1), ("math.g1_l8.calculation", 2),
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
