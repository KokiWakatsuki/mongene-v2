"""Task5b: 数学パック recipe（構成的生成・answer-first）の unit テスト。

各 recipe を実 FamilySpec YAML（engine/curriculum/math/families）から読んだ
CellContext で construct し、MR が正しく組み立てられること・signature が spec と
一致すること・double-solve（独立ソルバでの再確認）が全 seed で一致することを
検証する（H4/H5）。200 seed の property テストで例外なし・答え一致を確認する。
"""
from __future__ import annotations

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
    assert set(mr.given.keys()) == {"expression"}
    sq = mr.sub_questions[0]
    assert sq.asked == "read_point"
    assert [s.op for s in sq.steps] == ["read_point", "read_point"]
    # visual_plan は非 None（frame.visual="required" を満たす）
    assert mr.visual_plan is not None
    assert mr.visual_plan.style == "grid"
    # 答え（読み取るべき座標そのもの）を labels に載せない
    for label in mr.visual_plan.labels:
        assert "," not in label or "y = " in label  # 座標値そのものの文字列は含めない


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
