"""一次関数まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論・SymPy 恒真であること。乱数は引かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

X = sympy.Symbol("x")
Y = sympy.Symbol("y")


def _format_number(v: sympy.Expr) -> str:
    """数値の表示形（負数括弧なし・帯分数禁止・既約分数はそのまま）。"""
    return str(sympy.sstr(v))


def _format_expr_display(a: sympy.Expr, b: sympy.Expr) -> str:
    """y = a*x + b を日本語的な標準表示形にする（例: "y = 3x - 1"）。"""
    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    if a_s == 0:
        rhs = _format_number(b_s)
    else:
        if a_s == 1:
            a_part = "x"
        elif a_s == -1:
            a_part = "-x"
        else:
            a_part = f"{_format_number(a_s)}x"
        if b_s == 0:
            rhs = a_part
        elif b_s > 0:
            rhs = f"{a_part} + {_format_number(b_s)}"
        else:
            rhs = f"{a_part} - {_format_number(-b_s)}"
    return f"y = {rhs}"


def _build_expr(a: sympy.Expr, b: sympy.Expr) -> sympy.Expr:
    return a * X + b


@register_solver("math.linear_expr_from_two_points")
def linear_expr_from_two_points(
    p1: tuple[object, object], p2: tuple[object, object], method: str
) -> Solution:
    """2点を通る直線 y = ax + b を導出する。

    method="slope_then_intercept": 傾き→切片→式の順で計算。
    method="simultaneous": 連立方程式を立てて a, b を同時に解く。
    どちらも答え（式）は同一だが steps の op 列は異なる（Q3 の核）。
    """
    if method not in ("slope_then_intercept", "simultaneous"):
        raise ValueError(f"未知の method: {method!r}")

    x1, y1 = sympy.nsimplify(p1[0]), sympy.nsimplify(p1[1])
    x2, y2 = sympy.nsimplify(p2[0]), sympy.nsimplify(p2[1])
    if x1 == x2:
        raise ValueError("p1, p2 の x 座標が一致しており直線が定まらない")

    if method == "slope_then_intercept":
        a = (y2 - y1) / (x2 - x1)
        b = y1 - a * x1
        expr = _build_expr(a, b)
        steps = [
            Step(
                op="compute_slope",
                args=[str(p1), str(p2)],
                result_srepr=sympy.srepr(a),
                result_display=f"傾き a = {_format_number(a)}",
                narration="2点の y 座標の差を x 座標の差で割り、傾きを求める。",
            ),
            Step(
                op="compute_intercept",
                args=[_format_number(a), str(p1)],
                result_srepr=sympy.srepr(b),
                result_display=f"切片 b = {_format_number(b)}",
                narration="傾きと通る1点を y = ax + b に代入し、切片を求める。",
            ),
            Step(
                op="form_expression",
                args=[_format_number(a), _format_number(b)],
                result_srepr=sympy.srepr(expr),
                result_display=_format_expr_display(a, b),
                narration="傾きと切片から一次関数の式を組み立てる。",
            ),
        ]
    else:  # simultaneous
        a_sym, b_sym = sympy.symbols("a b")
        eq1 = sympy.Eq(a_sym * x1 + b_sym, y1)
        eq2 = sympy.Eq(a_sym * x2 + b_sym, y2)
        sol = sympy.solve([eq1, eq2], [a_sym, b_sym])
        a, b = sol[a_sym], sol[b_sym]
        expr = _build_expr(a, b)
        steps = [
            Step(
                op="setup_simultaneous",
                args=[str(p1), str(p2)],
                result_srepr=sympy.srepr([eq1, eq2]),
                result_display=f"{sympy.sstr(eq1)}, {sympy.sstr(eq2)}",
                narration="2点をそれぞれ y = ax + b に代入し、a, b の連立方程式を立てる。",
            ),
            Step(
                op="solve_simultaneous",
                args=[sympy.sstr(eq1), sympy.sstr(eq2)],
                result_srepr=sympy.srepr({str(a_sym): a, str(b_sym): b}),
                result_display=f"a = {_format_number(a)}, b = {_format_number(b)}",
                narration="連立方程式を解いて a, b を同時に求める。",
            ),
            Step(
                op="form_expression",
                args=[_format_number(a), _format_number(b)],
                result_srepr=sympy.srepr(expr),
                result_display=_format_expr_display(a, b),
                narration="求めた a, b から一次関数の式を組み立てる。",
            ),
        ]

    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=_format_expr_display(a, b))
    return Solution(answer=answer, steps=steps)


@register_solver("math.linear_expr_from_slope_point")
def linear_expr_from_slope_point(slope: object, point: tuple[object, object]) -> Solution:
    """傾きと1点から一次関数の式 y = ax + b を決定する。"""
    a = sympy.nsimplify(slope)
    px, py = sympy.nsimplify(point[0]), sympy.nsimplify(point[1])
    b = py - a * px
    expr = _build_expr(a, b)

    steps = [
        Step(
            op="substitute_point",
            args=[_format_number(a), str(point)],
            result_srepr=sympy.srepr(sympy.Eq(a * px + sympy.Symbol("b"), py)),
            result_display=f"{_format_number(a)} × {_format_number(px)} + b = {_format_number(py)}",
            narration="傾きと通る点の座標を y = ax + b に代入する。",
        ),
        Step(
            op="compute_intercept",
            args=[_format_number(a), str(point)],
            result_srepr=sympy.srepr(b),
            result_display=f"切片 b = {_format_number(b)}",
            narration="代入した式を b について解き、切片を求める。",
        ),
        Step(
            op="form_expression",
            args=[_format_number(a), _format_number(b)],
            result_srepr=sympy.srepr(expr),
            result_display=_format_expr_display(a, b),
            narration="傾きと切片から一次関数の式を組み立てる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=_format_expr_display(a, b))
    return Solution(answer=answer, steps=steps)


@register_solver("math.linear_expr_parallel_through_point")
def linear_expr_parallel_through_point(
    parallel_slope: object, point: tuple[object, object]
) -> Solution:
    """与えられた直線に平行（同じ傾き）で1点を通る一次関数の式を決定する。"""
    a = sympy.nsimplify(parallel_slope)
    px, py = sympy.nsimplify(point[0]), sympy.nsimplify(point[1])
    b = py - a * px
    expr = _build_expr(a, b)

    steps = [
        Step(
            op="read_parallel_slope",
            args=[_format_number(a)],
            result_srepr=sympy.srepr(a),
            result_display=f"傾き a = {_format_number(a)}",
            narration="平行な直線は傾きが等しいので、与えられた直線の傾きをそのまま用いる。",
        ),
        Step(
            op="compute_intercept",
            args=[_format_number(a), str(point)],
            result_srepr=sympy.srepr(b),
            result_display=f"切片 b = {_format_number(b)}",
            narration="傾きと通る1点を y = ax + b に代入し、切片を求める。",
        ),
        Step(
            op="form_expression",
            args=[_format_number(a), _format_number(b)],
            result_srepr=sympy.srepr(expr),
            result_display=_format_expr_display(a, b),
            narration="傾きと切片から一次関数の式を組み立てる。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=_format_expr_display(a, b))
    return Solution(answer=answer, steps=steps)


@register_solver("math.read_two_lattice_points")
def read_two_lattice_points(p1: tuple[object, object], p2: tuple[object, object]) -> Solution:
    """グラフ上の2格子点座標を読み取る（graph_table Lv2「読む」）。"""
    x1, y1 = sympy.nsimplify(p1[0]), sympy.nsimplify(p1[1])
    x2, y2 = sympy.nsimplify(p2[0]), sympy.nsimplify(p2[1])
    pt1 = sympy.Tuple(x1, y1)
    pt2 = sympy.Tuple(x2, y2)
    pts = sympy.Tuple(pt1, pt2)

    steps = [
        Step(
            op="read_point",
            args=[],
            result_srepr=sympy.srepr(pt1),
            result_display=f"({_format_number(x1)}, {_format_number(y1)})",
            narration="グラフ上の格子点の座標を1つ読み取る。",
        ),
        Step(
            op="read_point",
            args=[],
            result_srepr=sympy.srepr(pt2),
            result_display=f"({_format_number(x2)}, {_format_number(y2)})",
            narration="グラフ上のもう1つの格子点の座標を読み取る。",
        ),
    ]
    display = f"({_format_number(x1)}, {_format_number(y1)}), ({_format_number(x2)}, {_format_number(y2)})"
    answer = SymbolicAnswer(srepr=sympy.srepr(pts), display=display)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "linear_expr_from_two_points",
    "linear_expr_from_slope_point",
    "linear_expr_parallel_through_point",
    "read_two_lattice_points",
]
