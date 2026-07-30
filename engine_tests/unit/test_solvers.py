"""Task5a: 数学パック solvers（独立再計算）の unit テスト。

各 solver について、既知の入力から期待する answer 式（srepr 一致）と op 列一致を
確認する。分数傾き・負の傾きも含める。two_points は両 method で
「同じ答え・異なる op 列」になることを明示的にテストする（Q3 の核）。
"""
from __future__ import annotations

import pytest
import sympy

import engine.packs.math  # noqa: F401  (register_solver の副作用のため import)
from engine.core.registry import REGISTRY

X = sympy.Symbol("x")


def _ops(steps):
    return [s.op for s in steps]


# ---------------------------------------------------------------------------
# math.linear_expr_from_two_points
# ---------------------------------------------------------------------------
def test_two_points_slope_then_intercept_integer_slope():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol = solver((1, 3), (4, 12), "slope_then_intercept")

    expected_expr = 3 * X  # a=3, b=0
    assert sol.answer.kind == "symbolic"
    assert sol.answer.srepr == sympy.srepr(expected_expr)
    assert _ops(sol.steps) == ["compute_slope", "compute_intercept", "form_expression"]
    # 数学的に正しいことも独立に確認（両点を通る）
    a, b = sympy.Rational(3), sympy.Rational(0)
    assert (a * 1 + b) == 3
    assert (a * 4 + b) == 12


def test_two_points_simultaneous_same_answer_different_ops():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    sol_a = solver((1, 3), (4, 12), "slope_then_intercept")
    sol_b = solver((1, 3), (4, 12), "simultaneous")

    # Q3 の核: 同じ答え
    assert sol_a.answer.srepr == sol_b.answer.srepr
    assert sol_a.answer.display == sol_b.answer.display
    # だが op 列は method ごとに異なる
    assert _ops(sol_a.steps) == ["compute_slope", "compute_intercept", "form_expression"]
    assert _ops(sol_b.steps) == ["setup_simultaneous", "solve_simultaneous", "form_expression"]
    assert _ops(sol_a.steps) != _ops(sol_b.steps)


def test_two_points_fractional_slope():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    # (1,2) -> (4,3): slope = 1/3, intercept = 2 - 1/3 = 5/3
    sol = solver((1, 2), (4, 3), "slope_then_intercept")
    expected = sympy.Rational(1, 3) * X + sympy.Rational(5, 3)
    assert sol.answer.srepr == sympy.srepr(expected)

    sol2 = solver((1, 2), (4, 3), "simultaneous")
    assert sol2.answer.srepr == sol.answer.srepr
    # 両点を通ることを直接検算
    expr = sympy.sympify(sol.answer.srepr, locals={"x": X})
    assert expr.subs(X, 1) == 2
    assert expr.subs(X, 4) == 3


def test_two_points_negative_slope():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    # (0,5) -> (2,1): slope = -2, intercept = 5
    sol = solver((0, 5), (2, 1), "slope_then_intercept")
    expected = -2 * X + 5
    assert sympy.expand(sympy.sympify(sol.answer.srepr, locals={"x": X}) - expected) == 0


def test_two_points_invalid_method_raises():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    try:
        solver((0, 0), (1, 1), "bogus_method")
        assert False, "ValueError が発生するはず"
    except ValueError:
        pass


def test_two_points_vertical_line_raises():
    solver = REGISTRY.solver("math.linear_expr_from_two_points")
    try:
        solver((2, 0), (2, 5), "slope_then_intercept")
        assert False, "x1 == x2 は ValueError となるはず"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# math.linear_expr_from_slope_point
# ---------------------------------------------------------------------------
def test_slope_point_integer():
    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol = solver(2, (1, 5))
    expected = 2 * X + 3
    assert sol.answer.srepr == sympy.srepr(expected)
    assert _ops(sol.steps) == ["substitute_point", "compute_intercept", "form_expression"]
    # 通る点の検算
    expr = sympy.sympify(sol.answer.srepr, locals={"x": X})
    assert expr.subs(X, 1) == 5


def test_slope_point_fractional_slope():
    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol = solver(sympy.Rational(1, 2), (2, 1))
    expected = sympy.Rational(1, 2) * X + 0
    assert sol.answer.srepr == sympy.srepr(expected)


def test_slope_point_negative_slope():
    solver = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol = solver(-1, (3, 2))
    expr = sympy.sympify(sol.answer.srepr, locals={"x": X})
    assert expr.subs(X, 3) == 2
    assert sympy.expand(expr - (-1 * X + 5)) == 0


# ---------------------------------------------------------------------------
# math.linear_expr_parallel_through_point
# ---------------------------------------------------------------------------
def test_parallel_through_point():
    solver = REGISTRY.solver("math.linear_expr_parallel_through_point")
    sol = solver(-3, (2, 1))
    expected = -3 * X + 7
    assert sympy.expand(sympy.sympify(sol.answer.srepr, locals={"x": X}) - expected) == 0
    assert _ops(sol.steps) == ["read_parallel_slope", "compute_intercept", "form_expression"]


def test_parallel_through_point_fractional_slope():
    solver = REGISTRY.solver("math.linear_expr_parallel_through_point")
    sol = solver(sympy.Rational(2, 3), (3, 1))
    expr = sympy.sympify(sol.answer.srepr, locals={"x": X})
    assert expr.subs(X, 3) == 1
    # 傾きが 2/3 であることを検算
    assert sympy.simplify(expr - sympy.Rational(2, 3) * X).is_constant()


# ---------------------------------------------------------------------------
# math.read_two_lattice_points
# ---------------------------------------------------------------------------
def test_read_two_lattice_points():
    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = solver((1, 3), (4, 12))
    expected = sympy.Tuple(sympy.Tuple(1, 3), sympy.Tuple(4, 12))
    assert sol.answer.kind == "symbolic"
    assert sol.answer.srepr == sympy.srepr(expected)
    assert sol.answer.display == "(1, 3), (4, 12)"
    assert _ops(sol.steps) == ["read_point", "read_point"]
    assert len(sol.steps) == 2


def test_read_two_lattice_points_negative_coords():
    solver = REGISTRY.solver("math.read_two_lattice_points")
    sol = solver((-2, -1), (3, 4))
    assert sol.answer.display == "(-2, -1), (3, 4)"


# ---------------------------------------------------------------------------
# math.intersection_of_two_lines / math.verify_system_solution:
# 係数を文字列で渡しても厳密に解ける（nsimplify の近似探索に落ちない）
# ---------------------------------------------------------------------------
def test_nsimplify_of_bare_string_is_a_trap():
    """前提の記録: 文字列を nsimplify に直接渡すと偽の閉形式になる整数がある。

    solver がこの罠を踏まないよう sympify を挟んでいる（下のテストがそれを守る）。
    """
    assert sympy.nsimplify("1615") != 1615
    assert sympy.nsimplify(sympy.sympify("1615")) == 1615


@pytest.mark.parametrize("c", ["1615", "1093", "2071", "17"])
def test_intersection_of_two_lines_accepts_string_coefficients(c):
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    # x + y = 17, 75x + 160y = c 形（c=1615 のとき解は (13, 4)）
    sol = solver(("1", "1", "17"), ("75", "160", c), "elimination")
    x0, y0 = sympy.sympify(sol.answer.srepr)
    assert x0.is_rational and y0.is_rational, "無理数が出たら nsimplify の罠を踏んでいる"
    assert 75 * x0 + 160 * y0 == int(c)
    assert x0 + y0 == 17


def test_intersection_of_two_lines_accepts_fraction_strings():
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    # x + y = 44, x/4 + y/12 = 5 → (8, 36)
    sol = solver((1, 1, 44), ("1/4", "1/12", 5), "elimination")
    assert sol.answer.srepr == sympy.srepr(sympy.Tuple(sympy.Integer(8), sympy.Integer(36)))


def test_verify_system_solution_accepts_string_coefficients():
    solver = REGISTRY.solver("math.verify_system_solution")
    sol = solver(("1", "1", "17"), ("75", "160", "1615"), ("13", "4"))
    assert sol.answer.correct == "解である"
