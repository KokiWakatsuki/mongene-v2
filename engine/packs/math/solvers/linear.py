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


def _format_linear_rhs(a: sympy.Expr, b: sympy.Expr) -> str:
    """a*x + b の右辺表示（例: "3x - 1", "-x", "5"）。"""
    a_s = sympy.nsimplify(a)
    b_s = sympy.nsimplify(b)
    if a_s == 0:
        return _format_number(b_s)
    if a_s == 1:
        a_part = "x"
    elif a_s == -1:
        a_part = "-x"
    else:
        a_part = f"{_format_number(a_s)}x"
    if b_s == 0:
        return a_part
    if b_s > 0:
        return f"{a_part} + {_format_number(b_s)}"
    return f"{a_part} - {_format_number(-b_s)}"


def _format_expr_display(a: sympy.Expr, b: sympy.Expr) -> str:
    """y = a*x + b を日本語的な標準表示形にする（例: "y = 3x - 1"）。"""
    return f"y = {_format_linear_rhs(a, b)}"


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


@register_solver("math.rate_of_change_from_two_points")
def rate_of_change_from_two_points(p1: tuple[object, object], p2: tuple[object, object]) -> Solution:
    """2点から一次関数の変化の割合（＝傾き）を求める（g2_l20.find_value Lv1）。

    変化の割合 = (y の増加量)/(x の増加量) = (y2 - y1)/(x2 - x1)。答えは式ではなく
    数値（傾きそのもの）で、g2_l25 の「2点→式」とは asked も steps も異なる別構造。
    """
    x1, y1 = sympy.nsimplify(p1[0]), sympy.nsimplify(p1[1])
    x2, y2 = sympy.nsimplify(p2[0]), sympy.nsimplify(p2[1])
    if x1 == x2:
        raise ValueError("p1, p2 の x 座標が一致しており変化の割合が定まらない")

    dy = y2 - y1
    dx = x2 - x1
    rate = dy / dx

    steps = [
        Step(
            op="compute_differences",
            args=[str(p1), str(p2)],
            result_srepr=sympy.srepr(sympy.Tuple(dy, dx)),
            result_display=f"y の増加量 = {_format_number(dy)}, x の増加量 = {_format_number(dx)}",
            narration="2点から y の増加量と x の増加量をそれぞれ求める。",
        ),
        Step(
            op="compute_rate_of_change",
            args=[_format_number(dy), _format_number(dx)],
            result_srepr=sympy.srepr(rate),
            result_display=f"変化の割合 = {_format_number(rate)}",
            narration="y の増加量を x の増加量で割り、変化の割合を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(rate), display=_format_number(rate))
    return Solution(answer=answer, steps=steps)


@register_solver("math.intersection_of_two_lines")
def intersection_of_two_lines(
    line_a: tuple[object, object, object],
    line_b: tuple[object, object, object],
    method: str,
) -> Solution:
    """2直線 A1 x + B1 y = C1, A2 x + B2 y = C2 の交点座標を求める（g2_l27.find_value）。

    method="substitute"（Lv2・傾き切片形を等値して代入）／"elimination"（Lv3・
    一般形を連立して1文字消去）。答え（交点）は同一だが steps の op 列が異なる（Q3 の核）。
    """
    if method not in ("substitute", "elimination"):
        raise ValueError(f"未知の method: {method!r}")

    A1, B1, C1 = (sympy.nsimplify(v) for v in line_a)
    A2, B2, C2 = (sympy.nsimplify(v) for v in line_b)
    det = A1 * B2 - A2 * B1
    if det == 0:
        raise ValueError("2直線が平行または一致で交点が定まらない")

    x0 = (C1 * B2 - C2 * B1) / det
    y0 = (A1 * C2 - A2 * C1) / det
    pt = sympy.Tuple(x0, y0)
    x_sym, y_sym = sympy.symbols("x y")
    eq1 = sympy.Eq(A1 * x_sym + B1 * y_sym, C1)
    eq2 = sympy.Eq(A2 * x_sym + B2 * y_sym, C2)

    if method == "substitute":
        steps = [
            Step(
                op="equate_expressions",
                args=[sympy.sstr(eq1), sympy.sstr(eq2)],
                result_srepr=sympy.srepr(sympy.Eq(x_sym, x0)),
                result_display=f"x = {_format_number(x0)}",
                # 「2つの直線」: 助数詞「つ」除外により先頭 "2" が答えと衝突する偽陽性を避ける。
                narration="2つの直線の y を等しいとおき、x についての方程式を解く。",
            ),
            Step(
                op="solve_for_x",
                args=[_format_number(x0)],
                result_srepr=sympy.srepr(x0),
                result_display=f"x = {_format_number(x0)}",
                narration="x の値を求める。",
            ),
            Step(
                op="compute_y",
                args=[_format_number(x0)],
                result_srepr=sympy.srepr(y0),
                result_display=f"y = {_format_number(y0)}",
                narration="求めた x をどちらかの式に代入し、y を求める。",
            ),
        ]
    else:  # elimination
        steps = [
            Step(
                op="setup_system",
                args=[sympy.sstr(eq1), sympy.sstr(eq2)],
                result_srepr=sympy.srepr([eq1, eq2]),
                result_display=f"{sympy.sstr(eq1)}, {sympy.sstr(eq2)}",
                narration="2つの直線を ax + by = c の形にそろえて連立方程式を立てる。",
            ),
            Step(
                op="eliminate_variable",
                args=[sympy.sstr(eq1), sympy.sstr(eq2)],
                result_srepr=sympy.srepr(sympy.Eq(x_sym, x0)),
                result_display=f"x = {_format_number(x0)}",
                narration="係数をそろえて一方の文字を消去し、残った文字を求める。",
            ),
            Step(
                op="back_substitute",
                args=[_format_number(x0)],
                result_srepr=sympy.srepr(y0),
                result_display=f"y = {_format_number(y0)}",
                narration="求めた値をもとの式に代入し、もう一方の文字を求める。",
            ),
        ]

    answer = SymbolicAnswer(
        srepr=sympy.srepr(pt),
        display=f"({_format_number(x0)}, {_format_number(y0)})",
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.read_slope_intercept_from_graph")
def read_slope_intercept_from_graph(
    p1: tuple[object, object], p2: tuple[object, object]
) -> Solution:
    """グラフ上の直線から傾きと切片を読み取る（graph_table Lv1「読む」・g2_l21）。

    グラフ上の2格子点から傾き a = (y2-y1)/(x2-x1) を（変化の割合として）読み、
    y 軸との交点の y 座標として切片 b を読む。答えは (傾き, 切片) の組。式は与えられず
    図から読むため、g2_l20 の「変化の割合（数値）」・g2_l25 の「2点→式」とは asked も
    steps も異なる別構造。
    """
    x1, y1 = sympy.nsimplify(p1[0]), sympy.nsimplify(p1[1])
    x2, y2 = sympy.nsimplify(p2[0]), sympy.nsimplify(p2[1])
    if x1 == x2:
        raise ValueError("p1, p2 の x 座標が一致しており傾きが定まらない")

    a = (y2 - y1) / (x2 - x1)
    b = y1 - a * x1
    pair = sympy.Tuple(a, b)

    steps = [
        Step(
            op="read_slope",
            args=[str(p1), str(p2)],
            result_srepr=sympy.srepr(a),
            result_display=f"傾き a = {_format_number(a)}",
            narration="グラフ上の格子点で、右へ進む量に対する上下の変化の割合を読み取り、傾きとする。",
        ),
        Step(
            op="read_intercept",
            args=[_format_number(a), str(p1)],
            result_srepr=sympy.srepr(b),
            result_display=f"切片 b = {_format_number(b)}",
            narration="グラフが y 軸と交わる点の y 座標を読み取り、切片とする。",
        ),
    ]
    display = f"傾き {_format_number(a)}, 切片 {_format_number(b)}"
    answer = SymbolicAnswer(srepr=sympy.srepr(pair), display=display)
    return Solution(answer=answer, steps=steps)


def _format_y_range(y_lo: sympy.Expr, y_hi: sympy.Expr) -> str:
    """y の変域表示（例: "-1 ≦ y ≦ 5"）。全角 ≦ を使う（教科書表記）。"""
    return f"{_format_number(y_lo)} ≦ y ≦ {_format_number(y_hi)}"


@register_solver("math.y_range_over_domain")
def y_range_over_domain(
    a: object, b: object, x_lo: object, x_hi: object
) -> Solution:
    """1次関数 y=ax+b の x の変域 [x_lo, x_hi] に対する y の変域を求める（g2_l23 Lv2）。

    傾きの正負で端点の対応が入れかわる（a>0 なら x_lo→y_lo・x_hi→y_hi、a<0 で逆）。
    """
    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    x1, x2 = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    if x1 >= x2:
        raise ValueError("x の変域は x_lo < x_hi であること")
    y_at_x1 = a_s * x1 + b_s
    y_at_x2 = a_s * x2 + b_s
    y_lo = sympy.Min(y_at_x1, y_at_x2)
    y_hi = sympy.Max(y_at_x1, y_at_x2)

    sign_word = "正" if a_s > 0 else "負"
    steps = [
        Step(
            op="determine_sign",
            args=[_format_number(a_s)],
            result_srepr=sympy.srepr(a_s),
            result_display=f"傾きは {sign_word}",
            narration="傾きの正負を調べ、端点の対応（どちらの端が最大・最小か）を決める。",
        ),
        Step(
            op="eval_endpoints",
            args=[_format_number(x1), _format_number(x2)],
            result_srepr=sympy.srepr(sympy.Tuple(y_at_x1, y_at_x2)),
            result_display=(
                f"x = {_format_number(x1)} のとき y = {_format_number(y_at_x1)}, "
                f"x = {_format_number(x2)} のとき y = {_format_number(y_at_x2)}"
            ),
            narration="変域の両端の x を式に代入し、対応する y の値を求める。",
        ),
        Step(
            op="form_range",
            args=[_format_number(y_lo), _format_number(y_hi)],
            result_srepr=sympy.srepr(sympy.Tuple(y_lo, y_hi)),
            result_display=_format_y_range(y_lo, y_hi),
            narration="小さい方を下限、大きい方を上限として y の変域を書く。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(sympy.Tuple(y_lo, y_hi)), display=_format_y_range(y_lo, y_hi))
    return Solution(answer=answer, steps=steps)


def _paren_neg(v: sympy.Expr) -> str:
    """負数は括弧で囲む（代入表示の可読性。例: -4 → "(-4)"）。"""
    s = _format_number(v)
    return f"({s})" if v < 0 else s


@register_solver("math.evaluate_linear_at_x")
def evaluate_linear_at_x(a: object, b: object, x0: object) -> Solution:
    """1次関数 y = a x + b の x = x0 における y の値を求める（g2_l19.calculation Lv1）。

    代入して計算するだけ。答えは1つの数値 y。asked=value。
    """
    a_s, b_s, x_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(x0)
    y = a_s * x_s + b_s

    prod = f"{_paren_neg(a_s)} × {_paren_neg(x_s)}"
    if b_s == 0:
        rhs = prod
    elif b_s > 0:
        rhs = f"{prod} + {_format_number(b_s)}"
    else:
        rhs = f"{prod} - {_format_number(-b_s)}"

    steps = [
        Step(
            op="substitute_x",
            args=[_format_number(a_s), _format_number(b_s), _format_number(x_s)],
            result_srepr=sympy.srepr(a_s * x_s + b_s),
            result_display=f"y = {rhs}",
            narration="x の値を式に代入する。",
        ),
        Step(
            op="evaluate",
            args=[f"y = {rhs}"],
            result_srepr=sympy.srepr(y),
            result_display=f"y = {_format_number(y)}",
            narration="計算して y の値を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(y), display=_format_number(y))
    return Solution(answer=answer, steps=steps)


def _format_two_var_equation(a: sympy.Expr, b: sympy.Expr, c: sympy.Expr) -> str:
    """2元1次方程式 a x + b y = c の表示形（例: "4x + 2y = 10", "-3x + 2y = 6"）。

    b > 0 を前提とする（recipe が保証）。a は任意符号、a≠0・b≠0。
    """

    def coeff_term(coeff: sympy.Expr, var: str) -> str:
        mag = abs(coeff)
        mag_part = "" if mag == 1 else _format_number(mag)
        return f"{mag_part}{var}"

    ax = ("-" if a < 0 else "") + coeff_term(a, "x")
    by = coeff_term(b, "y")  # b > 0
    return f"{ax} + {by} = {_format_number(c)}"


@register_solver("math.solve_equation_for_y")
def solve_equation_for_y(a: object, b: object, c: object) -> Solution:
    """2元1次方程式 a x + b y = c を y について解く（g2_l26.calculation Lv1）。

    b y = c - a x → y = (c - a x)/b = (-a/b) x + c/b。答えは y = m x + k の式。
    """
    a_s, b_s, c_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(c)
    if b_s == 0:
        raise ValueError("y の係数 b が 0 で y について解けない")

    m = -a_s / b_s
    k = c_s / b_s
    expr = _build_expr(m, k)

    steps = [
        Step(
            op="isolate_y_term",
            args=[_format_two_var_equation(a_s, b_s, c_s)],
            result_srepr=sympy.srepr(sympy.Eq(b_s * Y, c_s - a_s * X)),
            result_display=f"{_format_number(b_s)}y = {_format_linear_rhs(-a_s, c_s)}",
            narration="x の項を右辺に移項し、y の項だけを左辺に残す。",
        ),
        Step(
            op="divide_by_coefficient",
            args=[_format_number(b_s)],
            result_srepr=sympy.srepr(expr),
            result_display=_format_expr_display(m, k),
            narration="両辺を y の係数で割り、y = の形にする。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=_format_expr_display(m, k))
    return Solution(answer=answer, steps=steps)


__all__ = [
    "linear_expr_from_two_points",
    "linear_expr_from_slope_point",
    "linear_expr_parallel_through_point",
    "read_two_lattice_points",
    "read_slope_intercept_from_graph",
    "rate_of_change_from_two_points",
    "intersection_of_two_lines",
    "y_range_over_domain",
    "solve_equation_for_y",
    "evaluate_linear_at_x",
]
