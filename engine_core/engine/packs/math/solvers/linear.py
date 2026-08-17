"""一次関数まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論・SymPy 恒真であること。乱数は引かない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import (
    ChoiceAnswer,
    Feature,
    GraphAnswer,
    Solution,
    Step,
    SymbolicAnswer,
)
from engine.core.registry import register_solver

X = sympy.Symbol("x")
Y = sympy.Symbol("y")


def _format_number(v: sympy.Expr) -> str:
    """数値の表示形（負数括弧なし・帯分数禁止・既約分数はそのまま）。"""
    return str(sympy.sstr(v))


def _paren_number(v: sympy.Expr) -> str:
    """負の数はかっこで囲む（解説の途中式で `× -1` と書かないため）。"""
    text = _format_number(v)
    return f"({text})" if v < 0 else text


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
    elif a_s.is_Rational and a_s.q != 1:
        # **分数の係数はかっこでくくる。** `-5/4x` と書くと -5/(4x) と読めてしまう。
        # 問題文の側は「y = -(5/4)x + 4」と書いているので、そちらに合わせる。
        a_part = (
            f"-({_format_number(-a_s)})x" if a_s < 0 else f"({_format_number(a_s)})x"
        )
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
                result_display=f"{_format_equation_display(eq1)}, {_format_equation_display(eq2)}",
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

    # nsimplify の前に必ず sympify する: 文字列を直接渡すと近似値として扱われ、
    # "1615" が 50*2**(314/427)*… という偽の閉形式になることがある（黙って解が
    # 無理数になる）。sympify を通せば整数・分数は厳密なまま、Float だけが
    # nsimplify の有理化対象として残る。
    A1, B1, C1 = (sympy.nsimplify(sympy.sympify(v)) for v in line_a)
    A2, B2, C2 = (sympy.nsimplify(sympy.sympify(v)) for v in line_b)
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
                # **立てた方程式そのものを見せる。** ここが `x = 2`（＝解）だったので、
                # 1手目で答えが出てしまい、次の手「x の値を求める」が
                # **同じ値をもう一度書くだけの空手**になっていた。
                result_display=_format_equation_display(
                    sympy.Eq((C1 - A1 * x_sym) / B1, (C2 - A2 * x_sym) / B2)
                ),
                # 「2つの直線」: 助数詞「つ」除外により先頭 "2" が答えと衝突する偽陽性を避ける。
                narration="2つの直線の y を等しいとおき、x についての方程式をつくる。",
            ),
            Step(
                op="solve_for_x",
                args=[_format_number(x0)],
                result_srepr=sympy.srepr(x0),
                result_display=f"x = {_format_number(x0)}",
                narration="その方程式を解いて、x の値を求める。",
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
                result_display=f"{_format_equation_display(eq1)}, {_format_equation_display(eq2)}",
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


def _evaluate_linear_at_x_core(a: object, b: object, x0: object) -> Solution:
    """`evaluate_linear_at_x` の本体（型付き素関数）。

    solver 間で再利用する（`point_on_line_at_x` が呼ぶ）。`@register_solver` の戻り型は
    `Callable[..., object]` で型が消えるため、solver 同士は登録名でなくこの素関数を呼ぶ。
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


@register_solver("math.evaluate_linear_at_x")
def evaluate_linear_at_x(a: object, b: object, x0: object) -> Solution:
    """1次関数 y = a x + b の x = x0 における y の値を求める（g2_l19.calculation Lv1）。

    代入して計算するだけ。答えは1つの数値 y。asked=value。
    """
    return _evaluate_linear_at_x_core(a, b, x0)


@register_solver("math.point_on_line_at_x")
def point_on_line_at_x(a: object, b: object, x0: object) -> Solution:
    """1次関数 y=ax+b のグラフ上で x=x0 における通過点 (x0, y0) を求める（g2_l22.calculation Lv1）。

    値の計算は `evaluate_linear_at_x`（同モジュール・g2_l19 と共有）を再利用し、その
    substitute/evaluate ステップに座標を組み立てる1手を足す。答えは座標 (x0, y0)。
    asked=coordinate で、g2_l19（asked=value）とは答えの形も steps も異なる別構造。
    """
    a_s, b_s, x_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(x0)
    inner = _evaluate_linear_at_x_core(a_s, b_s, x_s)  # 代入計算を再利用（g2_l19 と同一ロジック）
    y0 = a_s * x_s + b_s
    assert isinstance(inner.answer, SymbolicAnswer)
    assert inner.answer.srepr == sympy.srepr(y0)  # 再利用元の値と一致を確認

    point = sympy.Tuple(x_s, y0)
    steps = list(inner.steps) + [
        Step(
            op="form_coordinate",
            args=[_format_number(x_s), _format_number(y0)],
            result_srepr=sympy.srepr(point),
            result_display=f"({_format_number(x_s)}, {_format_number(y0)})",
            narration="与えられた x の値と求めた y の値を組にして、通過点の座標とする。",
        ),
    ]
    answer = SymbolicAnswer(
        srepr=sympy.srepr(point),
        display=f"({_format_number(x_s)}, {_format_number(y0)})",
    )
    return Solution(answer=answer, steps=steps)


def _draw_linear_features_core(a: object, b: object) -> Solution:
    """`draw_linear_features` の本体（型付き素関数）。

    solver 間で再利用する（`draw_from_equation` が変形後の直線を描くのに呼ぶ）。
    `@register_solver` の戻り型は `Callable[..., object]` で型が消えるため、solver 同士は
    登録名でなくこの素関数を呼ぶ。
    """
    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    intercept_pt = sympy.Tuple(sympy.Integer(0), b_s)
    features = [
        Feature(kind="slope", srepr=sympy.srepr(a_s), display=f"傾き {_format_number(a_s)}"),
        Feature(
            kind="intercept",
            srepr=sympy.srepr(intercept_pt),
            display=f"切片の点 (0, {_format_number(b_s)})",
        ),
    ]
    line_expr = _build_expr(a_s, b_s)
    steps = [
        Step(
            op="plot_intercept",
            args=[_format_number(b_s)],
            result_srepr=sympy.srepr(intercept_pt),
            result_display=f"(0, {_format_number(b_s)})",
            narration="y 軸との交点（切片）に点をとる。",
        ),
        Step(
            op="apply_slope",
            args=[_format_number(a_s)],
            result_srepr=sympy.srepr(a_s),
            result_display=f"傾き {_format_number(a_s)}",
            narration="傾きにしたがって、右へ進んだときの上下の変化の分だけ動いた点をとる。",
        ),
        Step(
            op="draw_line",
            args=[],
            result_srepr=sympy.srepr(line_expr),
            result_display=_format_expr_display(a_s, b_s),
            narration="とった2点を通る直線をひく。",
        ),
    ]
    answer = GraphAnswer(features=features, solution_svg_ref="")
    return Solution(answer=answer, steps=steps)


@register_solver("math.draw_linear_features")
def draw_linear_features(a: object, b: object) -> Solution:
    """1次関数 y=ax+b のグラフをかくための検証可能な特徴を求める（g2_l22.graph_table Lv1）。

    答えは GraphAnswer（傾き a・y切片の点 (0,b) の2特徴の集合で採点＝§6.2 V1'）。solver は
    SVG を描かない（特徴のみ）。模範解答図の描画は recipe が visual 層のヘルパで行う。
    「読む」（SymbolicAnswer）と違い answer.kind="graph" になる別構造。
    """
    return _draw_linear_features_core(a, b)


def _format_equation_display(eq: sympy.Eq) -> str:
    """方程式を教材の書き方で表示する（`Eq(5*x + y, 45)` → `5x + y = 45`）。

    `sympy.sstr` をそのまま解説に出していたので、生徒に
    「Eq(5*x + y, 45), Eq(-10*x + y, 0) の連立方程式を立てる」と見せていた。
    """
    def side(expr: sympy.Expr) -> str:
        s = sympy.sstr(sympy.expand(expr))
        return s.replace("*", "")

    return f"{side(eq.lhs)} = {side(eq.rhs)}"


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


def _solve_equation_for_y_core(a: object, b: object, c: object) -> Solution:
    """`solve_equation_for_y` の本体（型付き素関数）。

    solver 間で再利用する（`draw_from_equation` が変形手順の取得に呼ぶ）。
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


@register_solver("math.solve_equation_for_y")
def solve_equation_for_y(a: object, b: object, c: object) -> Solution:
    """2元1次方程式 a x + b y = c を y について解く（g2_l26.calculation Lv1）。

    b y = c - a x → y = (c - a x)/b = (-a/b) x + c/b。答えは y = m x + k の式。
    """
    return _solve_equation_for_y_core(a, b, c)


@register_solver("math.draw_from_equation")
def draw_from_equation(a: object, b: object, c: object) -> Solution:
    """2元1次方程式 a x + b y = c を y=… に変形してからグラフをかく（g2_l26.graph_table Lv1）。

    **合成ソルバ**: 変形手順は `_solve_equation_for_y_core`（#5 の資産）、作図の特徴・手順は
    `_draw_linear_features_core`（#8「かく」capability）を再利用するだけで、新しい数学ロジックは
    書かない。答えは GraphAnswer（変形後の直線 y=mx+k の傾き・切片の特徴集合）。
    """
    a_s, b_s, c_s = sympy.nsimplify(a), sympy.nsimplify(b), sympy.nsimplify(c)
    if b_s == 0:
        raise ValueError("y の係数 b が 0 でグラフ（1次関数）にならない")
    transform = _solve_equation_for_y_core(a_s, b_s, c_s)  # 変形手順（#5 再利用）
    m = -a_s / b_s
    k = c_s / b_s
    draw = _draw_linear_features_core(m, k)  # 作図の特徴・手順（#8 再利用）
    steps = list(transform.steps) + list(draw.steps)
    return Solution(answer=draw.answer, steps=steps)


@register_solver("math.draw_special_lines")
def draw_special_lines(xi: object, yi: object, axis: object, k: object) -> Solution:
    """切片法で 2元1次方程式の直線をかき、さらに特殊直線 x=k / y=k もかく（g2_l26.graph_table Lv2）。

    主直線は x 軸との交点 (xi,0)・y 軸との交点 (0,yi) を通る直線（切片法）。特殊直線は
    axis="vertical"→x=k（y 軸に平行）／axis="horizontal"→y=k（x 軸に平行）。答えは GraphAnswer
    ＝2交点＋特殊直線の特徴集合（srepr 集合一致で採点）。steps は切片法の手順（Lv1 の y= 変形とは
    op 列が異なる＝level_sep）。narration には数字を書かない（切片の 0 が答え値＝漏洩回避）。
    """
    xi_s, yi_s, k_s = sympy.nsimplify(xi), sympy.nsimplify(yi), sympy.nsimplify(k)
    if xi_s == 0 or yi_s == 0:
        raise ValueError("切片法には x/y 軸との交点が原点以外である必要がある（xi≠0, yi≠0）")

    x_int_pt = sympy.Tuple(xi_s, sympy.Integer(0))
    y_int_pt = sympy.Tuple(sympy.Integer(0), yi_s)

    if axis == "vertical":
        special = Feature(
            kind="vertical_line",
            srepr=sympy.srepr(sympy.Eq(X, k_s)),
            display=f"x = {_format_number(k_s)}",
        )
        special_narr = "「x = 定数」のグラフは、y 軸に平行な縦の直線としてかく。"
    elif axis == "horizontal":
        special = Feature(
            kind="horizontal_line",
            srepr=sympy.srepr(sympy.Eq(Y, k_s)),
            display=f"y = {_format_number(k_s)}",
        )
        special_narr = "「y = 定数」のグラフは、x 軸に平行な横の直線としてかく。"
    else:
        raise ValueError(f"axis は vertical/horizontal のいずれか: {axis!r}")

    features = [
        Feature(
            kind="x_intercept",
            srepr=sympy.srepr(x_int_pt),
            display=f"x 軸との交点 ({_format_number(xi_s)}, 0)",
        ),
        Feature(
            kind="y_intercept",
            srepr=sympy.srepr(y_int_pt),
            display=f"y 軸との交点 (0, {_format_number(yi_s)})",
        ),
        special,
    ]
    steps = [
        Step(
            op="find_x_intercept",
            args=[],
            result_srepr=sympy.srepr(x_int_pt),
            result_display=f"({_format_number(xi_s)}, 0)",
            narration="グラフが x 軸と交わる点（x 軸との交点）を求める。",
        ),
        Step(
            op="find_y_intercept",
            args=[],
            result_srepr=sympy.srepr(y_int_pt),
            result_display=f"(0, {_format_number(yi_s)})",
            narration="グラフが y 軸と交わる点（y 軸との交点）を求める。",
        ),
        Step(
            op="draw_line",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(x_int_pt, y_int_pt)),
            result_display="2つの交点を通る直線",
            narration="求めた2つの交点を通る直線をひく。",
        ),
        Step(
            op="draw_special_line",
            args=[special.display],
            result_srepr=special.srepr,
            result_display=special.display,
            narration=special_narr,
        ),
    ]
    answer = GraphAnswer(features=features, solution_svg_ref="")
    return Solution(answer=answer, steps=steps)


@register_solver("math.draw_linear_features_fraction")
def draw_linear_features_fraction(p: object, q: object, b: object) -> Solution:
    """分数の傾き p/q の直線 y=(p/q)x+b を、格子点を通るようにかく（g2_l22.graph_table Lv3）。

    傾き p/q（q>0・既約・非整数）と切片 b から、y 軸との交点 (0,b) と、そこから x を +q・
    y を +p 進んだ格子点 (q, p+b) を採る（分数傾きでも整数座標で正確にかける）。答えは GraphAnswer
    ＝傾き・切片・通る格子点の3特徴。steps は分母/分子ぶんの移動→格子点印づけ（Lv1 の整数傾きとは
    op 列が異なる＝level_sep）。narration には数字を書かない。
    """
    p_s, q_s, b_s = sympy.nsimplify(p), sympy.nsimplify(q), sympy.nsimplify(b)
    if q_s <= 1:
        raise ValueError("分数傾きの分母 q は 2 以上（非整数の傾き）である必要がある")
    slope = p_s / q_s  # sympy Rational（q≥2・既約）
    intercept_pt = sympy.Tuple(sympy.Integer(0), b_s)
    lattice_pt = sympy.Tuple(q_s, p_s + b_s)  # x=q で y=(p/q)*q+b=p+b（整数）
    features = [
        Feature(kind="slope", srepr=sympy.srepr(slope), display=f"傾き {_format_number(slope)}"),
        Feature(
            kind="intercept",
            srepr=sympy.srepr(intercept_pt),
            display=f"切片の点 (0, {_format_number(b_s)})",
        ),
        Feature(
            kind="lattice_point",
            srepr=sympy.srepr(lattice_pt),
            display=f"通る格子点 ({_format_number(q_s)}, {_format_number(p_s + b_s)})",
        ),
    ]
    steps = [
        Step(
            op="plot_intercept",
            args=[],
            result_srepr=sympy.srepr(intercept_pt),
            result_display=f"(0, {_format_number(b_s)})",
            narration="y 軸との交点（切片）に点をとる。",
        ),
        Step(
            op="apply_slope_denominator",
            args=[],
            result_srepr=sympy.srepr(q_s),
            result_display=f"x 方向に {_format_number(q_s)}",
            narration="切片から、傾きの分母のぶんだけ x 軸の正の向きに進む。",
        ),
        Step(
            op="apply_slope_numerator",
            args=[],
            result_srepr=sympy.srepr(p_s),
            result_display=f"y 方向に {_format_number(p_s)}",
            narration="そこから、傾きの分子のぶんだけ y 軸方向に進む（分子の符号にしたがう）。",
        ),
        Step(
            op="mark_lattice_point",
            args=[],
            result_srepr=sympy.srepr(lattice_pt),
            result_display=f"({_format_number(q_s)}, {_format_number(p_s + b_s)})",
            narration="進んだ先の格子点に印をつける。",
        ),
        Step(
            op="draw_line",
            args=[],
            result_srepr=sympy.srepr(slope * X + b_s),
            # 兄弟の Lv1 は「（y = 3x + 9）」と y = をつけていて、ここだけ
            # 右辺だけを出していた。
            result_display=_format_expr_display(slope, b_s),
            narration="切片と格子点の2点を通る直線をひく。",
        ),
    ]
    answer = GraphAnswer(features=features, solution_svg_ref="")
    return Solution(answer=answer, steps=steps)


def _endpoint_feature(x: sympy.Expr, y: sympy.Expr, closed: bool) -> Feature:
    """線分の端点の特徴（開閉を srepr の flag に埋め込むので double-solve で開閉を区別できる）。"""
    flag = sympy.Integer(1) if closed else sympy.Integer(0)
    kind = "endpoint_closed" if closed else "endpoint_open"
    status = "ふくむ" if closed else "ふくまない"
    return Feature(
        kind=kind,
        srepr=sympy.srepr(sympy.Tuple(x, y, flag)),  # 座標＋開閉フラグ＝開/閉で srepr が相異
        display=f"端点 ({_format_number(x)}, {_format_number(y)}) を{status}（{'●' if closed else '○'}）",
    )


@register_solver("math.draw_segment_features")
def draw_segment_features(
    a: object, b: object, x_lo: object, x_hi: object, closed_lo: object, closed_hi: object
) -> Solution:
    """変域つき1次関数 y=ax+b（x_lo≦/<x≦/<x_hi）を線分としてかく（g2_l23.graph_table Lv2）。

    両端の点 (x_lo, a·x_lo+b)・(x_hi, a·x_hi+b) を、変域の不等号（等号の有無）にしたがって
    閉端（ふくむ＝●）/開端（ふくまない＝○）で表す。答えは GraphAnswer＝両端点の特徴集合
    （開閉は srepr の flag に埋め込むので集合一致で開閉まで検証できる）。narration に数字を書かない。
    """
    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    x_lo_s, x_hi_s = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    if x_lo_s >= x_hi_s:
        raise ValueError("変域は x_lo < x_hi である必要がある")
    cl, ch = bool(closed_lo), bool(closed_hi)
    y_lo = a_s * x_lo_s + b_s
    y_hi = a_s * x_hi_s + b_s
    features = [
        _endpoint_feature(x_lo_s, y_lo, cl),
        _endpoint_feature(x_hi_s, y_hi, ch),
    ]
    steps = [
        Step(
            op="plot_endpoint_lo",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(x_lo_s, y_lo)),
            result_display=f"({_format_number(x_lo_s)}, {_format_number(y_lo)})",
            narration="変域の左端の x に対応する点をとり、端をふくむなら●、ふくまないなら○で表す。",
        ),
        Step(
            op="plot_endpoint_hi",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(x_hi_s, y_hi)),
            result_display=f"({_format_number(x_hi_s)}, {_format_number(y_hi)})",
            narration="変域の右端の x に対応する点をとり、端をふくむなら●、ふくまないなら○で表す。",
        ),
        Step(
            op="draw_segment",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(sympy.Tuple(x_lo_s, y_lo), sympy.Tuple(x_hi_s, y_hi))),
            result_display="両端点を結ぶ線分",
            narration="とった2つの端点を結ぶ線分をひく。",
        ),
    ]
    answer = GraphAnswer(features=features, solution_svg_ref="")
    return Solution(answer=answer, steps=steps)


@register_solver("math.linear_direction_from_slope")
def linear_direction_from_slope(a: object) -> Solution:
    """1次関数 y=ax+b のグラフの向き（右上がり/右下がり）を傾き a の符号から判定する
    （knowledge・g2_l21）。a>0 → 右上がり／a<0 → 右下がり。答えは ChoiceAnswer（単一選択）、
    fact_id で根拠（傾きの符号と向きの対応規則）を刻む＝Q1 は V2（規則ベース照合・§6.2）。

    b（切片）は向きに無関係なので solver は a のみで判定する（recipe の構成値は見ない・double-solve）。
    """
    a_s = sympy.nsimplify(a)
    if a_s == 0:
        raise ValueError("傾き a=0 は1次関数でない（a≠0）")
    positive = a_s > 0
    direction = "右上がり" if positive else "右下がり"
    other = "右下がり" if positive else "右上がり"
    steps = [
        Step(
            op="identify_slope_sign",
            args=[_format_number(a_s)],
            result_srepr=sympy.srepr(sympy.sign(a_s)),
            result_display="傾きは正" if positive else "傾きは負",
            # 数字を出さない（答えの向きは a の符号で決まるが、ヒントでは向きを言わない）
            narration="傾き a の符号に注目する。",
        ),
        Step(
            op="determine_direction",
            args=[],
            result_srepr=direction,
            result_display=direction,
            narration="傾きが正なら右上がり、傾きが負なら右下がりになる。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=direction, distractors=[other], fact_id="lf.slope_sign_to_direction"
    )
    return Solution(answer=answer, steps=steps)


def _line_sign_description(a_positive: bool, b_positive: bool) -> str:
    """傾き・切片の符号からグラフのようすの説明文を作る（4分類の各文言）。"""
    direction = "右上がり" if a_positive else "右下がり"
    inter = "y 軸の正の部分" if b_positive else "y 軸の負の部分"
    return f"{direction}で、{inter}で y 軸と交わる"


@register_solver("math.classify_line_by_signs")
def classify_line_by_signs(a: object, b: object) -> Solution:
    """1次関数 y=ax+b のグラフのようすを、傾き a と切片 b の符号から判別する（knowledge・g2_l21 Lv2）。

    傾きの符号→向き（右上がり/右下がり）と、切片の符号→y 軸の正/負のどちらで交わるか、の
    2つを合わせた4分類の単一選択。傾き・切片の両方の意味を判別・適用する（Lv1 の向き単独＝
    傾きの符号のみ、とは op 列も答えの構造も異なる）。b（切片）は本セルでは判別対象なので b≠0 必須。
    Q1 は fact_id 照合の V2（規則ベース）。答えは ChoiceAnswer（テキスト＝数字なしで G-Q5t 素通り）。
    """
    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    if a_s == 0:
        raise ValueError("傾き a=0 は1次関数でない（a≠0）")
    if b_s == 0:
        raise ValueError("切片 b=0（原点を通る）は本セルの4分類の対象外（b≠0）")
    ap, bp = a_s > 0, b_s > 0
    correct = _line_sign_description(ap, bp)
    # 決定論的な順序で4分類を並べ、correct を除いたものを妨害選択肢にする。
    all_four = [
        _line_sign_description(True, True),
        _line_sign_description(True, False),
        _line_sign_description(False, True),
        _line_sign_description(False, False),
    ]
    distractors = [d for d in all_four if d != correct]
    steps = [
        Step(
            op="identify_slope_sign",
            args=[],
            result_srepr=sympy.srepr(sympy.sign(a_s)),
            result_display="傾きは正" if a_s > 0 else "傾きは負",
            narration="傾き a の符号から、グラフが右上がりか右下がりかを判断する。",
        ),
        Step(
            op="identify_intercept_sign",
            args=[],
            result_srepr=sympy.srepr(sympy.sign(b_s)),
            result_display="切片は正" if b_s > 0 else "切片は負",
            narration="切片 b の符号から、y 軸の正の部分・負の部分のどちらで交わるかを判断する。",
        ),
        Step(
            op="combine_signs",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="傾きと切片の符号を合わせて、グラフのようすを選ぶ。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="lf.slope_and_intercept_signs"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.solve_time_from_area")
def solve_time_from_area(a: object, y_target: object) -> Solution:
    """面積の式 y=ax（比例・a>0）で、面積が y_target となる時刻 x を逆算する（g2_l29.find_value Lv3）。

    a·x = y_target を x について解く（x = y_target / a）。answer=value（時刻 x）。動点の面積の式は
    既知として与え、目標の面積から時刻を逆算する技能のみを問う（面積の式の立式は word_problem g2_l29）。
    narration には数字を書かない。
    """
    a_s, y_s = sympy.nsimplify(a), sympy.nsimplify(y_target)
    if a_s <= 0:
        raise ValueError("面積の比例定数 a は正である必要がある（a>0）")
    x = y_s / a_s
    steps = [
        Step(
            op="set_up_equation",
            args=[],
            result_srepr=sympy.srepr(sympy.Eq(a_s * X, y_s)),
            result_display=f"{_format_linear_rhs(a_s, sympy.Integer(0))} = {_format_number(y_s)}",
            narration="面積の式に、求める面積の値を代入して、時刻 x についての方程式をつくる。",
        ),
        Step(
            op="solve_for_x",
            args=[],
            result_srepr=sympy.srepr(x),
            result_display=f"x = {_format_number(x)}",
            narration="両辺を x の係数で割って、時刻 x を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(x), display=_format_number(x))
    return Solution(answer=answer, steps=steps)


@register_solver("math.evaluate_two_var_lhs")
def evaluate_two_var_lhs(a: object, b: object, x_cand: object, y_cand: object) -> Solution:
    """2元1次方程式 ax+by=c の左辺 ax+by に (x,y) の値を代入して左辺の値を求める
    （g2_l10.calculation Lv1）。答えは左辺の値（数値・SymbolicAnswer）。右辺 c と比べれば等式が
    成り立つか確かめられるが、本セルは「左辺の値を求める」代入計算を問う（○×判定は knowledge Lv2）。
    narration には数字を書かない。
    """
    a_s, b_s = sympy.nsimplify(a), sympy.nsimplify(b)
    x_s, y_s = sympy.nsimplify(x_cand), sympy.nsimplify(y_cand)
    lhs = a_s * x_s + b_s * y_s
    steps = [
        Step(
            op="substitute_candidate",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(x_s, y_s)),
            # 代入したままの左辺（`3 × 2 + 4 × (-1)`）。指示の言い直しは置かない（面③）。
            result_display=(
                f"{_format_number(a_s)} × {_paren_number(x_s)}"
                f" + {_format_number(b_s)} × {_paren_number(y_s)}"
            ),
            # **この問題は等式ではなく「式の値」**（2x + 4y に代入する）。
            # 「左辺」と呼ぶと、ありもしない右辺があるように読める。
            narration="式の x と y に、与えられた値をそれぞれ代入する。",
        ),
        Step(
            op="compute_lhs",
            args=[],
            result_srepr=sympy.srepr(lhs),
            result_display=_format_number(lhs),
            narration="代入した式を計算して、その値を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(lhs), display=_format_number(lhs))
    return Solution(answer=answer, steps=steps)


@register_solver("math.verify_system_solution")
def verify_system_solution(
    line_a: tuple[object, object, object],
    line_b: tuple[object, object, object],
    candidate: tuple[object, object],
) -> Solution:
    """与えられた組 (x,y) が連立方程式 A1x+B1y=C1, A2x+B2y=C2 の解かを判定する
    （knowledge・g2_l10）。両式に代入して**両方**成り立てば「解である」、片方でも
    成り立たなければ「解でない」。答えは ChoiceAnswer。Q1 は代入検証＝実質 V1（決定論恒真）。
    solver は与えられた候補と係数だけから判定する（recipe の真偽ビットは見ない・double-solve）。
    """
    # nsimplify の前に必ず sympify する: 文字列を直接渡すと近似値として扱われ、
    # "1615" が 50*2**(314/427)*… という偽の閉形式になることがある（黙って解が
    # 無理数になる）。sympify を通せば整数・分数は厳密なまま、Float だけが
    # nsimplify の有理化対象として残る。
    A1, B1, C1 = (sympy.nsimplify(sympy.sympify(v)) for v in line_a)
    A2, B2, C2 = (sympy.nsimplify(sympy.sympify(v)) for v in line_b)
    xc, yc = (sympy.nsimplify(sympy.sympify(v)) for v in candidate)
    ok1 = sympy.simplify(A1 * xc + B1 * yc - C1) == 0
    ok2 = sympy.simplify(A2 * xc + B2 * yc - C2) == 0
    is_sol = bool(ok1 and ok2)
    correct = "解である" if is_sol else "解でない"
    other = "解でない" if is_sol else "解である"
    steps = [
        Step(
            op="substitute_candidate",
            args=[_format_number(xc), _format_number(yc)],
            result_srepr=sympy.srepr(sympy.Tuple(A1 * xc + B1 * yc, A2 * xc + B2 * yc)),
            result_display=(
                f"{_format_number(A1 * xc + B1 * yc)} と {_format_number(A2 * xc + B2 * yc)}"
            ),
            narration="組の x, y の値を2つの式の左辺にそれぞれ代入する。",
        ),
        Step(
            op="judge_solution",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="両方の式が成り立てば解、片方でも成り立たなければ解でない。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="simultaneous.solution_verification"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.range_endpoint_inclusion")
def range_endpoint_inclusion(inclusive: object) -> Solution:
    """変域の端点がグラフにふくまれるかを不等号の種類から判定する（knowledge・g2_l23）。

    等号つきの不等号（≦・≧＝以上・以下）→ 端点はふくまれる／等号なし（<・>＝より大きい・
    未満）→ ふくまれない。答えは ChoiceAnswer（単一選択）、fact_id で根拠（等号の有無と端点の
    包含の対応規則）を刻む＝Q1 は V2（規則ベース・§6.2）。端点の値・関数は包含に無関係（規則は
    不等号の種類だけで決まる）ので solver は inclusive の真偽だけで判定する（double-solve）。
    """
    inc = bool(inclusive)
    correct = "ふくまれる" if inc else "ふくまれない"
    other = "ふくまれない" if inc else "ふくまれる"
    steps = [
        Step(
            op="identify_inequality_type",
            args=[],
            result_srepr="closed" if inc else "open",
            result_display="等号あり（≦・≧）" if inc else "等号なし（<・>）",
            narration="変域の不等号に等号がついているか（≦・≧か、<・>か）に注目する。",
        ),
        Step(
            op="determine_inclusion",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="等号つきの不等号なら端の点はふくまれ、等号がなければふくまれない。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="range.endpoint_inclusion"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.linear_slope_as_rate")
def linear_slope_as_rate(a: object) -> Solution:
    """1次関数 y=ax+b で x が1増加したときの y の増加量（＝変化の割合＝傾き a）を求める
    （calculation・g2_l21）。増加量 = a(x+1)+b − (ax+b) = a で、切片 b にも x にも依らない。
    solver は傾き a だけから答えを出す（recipe の切片は見ない・double-solve）。答えは数値。
    """
    a_s = sympy.nsimplify(a)
    steps = [
        Step(
            op="compute_increment",
            args=[],
            result_srepr=sympy.srepr(a_s),
            # `×` は数とかっこの間には書かない（教科書の書き方）。
            result_display=(
                f"({_format_number(a_s)}(x + 1) + b) - ({_format_number(a_s)}x + b)"
            ),
            # 数字を出さない（§5-#9: narration/ヒントに数値を書かない）。
            narration="x が1増えると y がいくつ増えるかを、式の変化から調べる。",
            # **b が何なのかを言う。** 断りなく `b` が現れていたので、
            # 問題文（y = -9x - 1）に無い文字が突然出てくるように読めた。
            detail=(
                f"切片を b とおくと、x を 1 増やしたときの y の変化は "
                f"({_format_number(a_s)}(x + 1) + b) - ({_format_number(a_s)}x + b) になる。"
            ),
        ),
        Step(
            op="state_rate_of_change",
            args=[],
            result_srepr=sympy.srepr(a_s),
            result_display=_format_number(a_s),
            narration="1次関数では、x が1増えるときの y の増加量は傾きに等しい。",
            # **計算せずに結論だけ言っていた。** b どうし・x の項どうしが消えることを見せる。
            detail=(
                f"b どうしも {_format_number(a_s)}x どうしも消えるので、"
                f"残るのは {_format_number(a_s)} になる。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(a_s), display=_format_number(a_s))
    return Solution(answer=answer, steps=steps)


@register_solver("math.classify_linear_function")
def classify_linear_function(rhs: object) -> Solution:
    """与えられた式 y=<rhs> が x の1次関数かを判定する（knowledge・g2_l19）。

    x で微分した「変化の割合（導関数）」が **x を含まない 0 でない定数** であれば
    1次関数（y=ax+b, a≠0）、そうでなければ1次関数でない（定数関数=導関数0／2次=導関数が
    x を含む／反比例 y=a/x=導関数が x を含む）。答えは ChoiceAnswer。Q1 は導関数による
    恒真判定＝実質 V1（決定論恒真・§6.2）。solver は式そのものだけから判定する
    （recipe が仕込んだ category ビットは見ない・double-solve）。
    """
    x = sympy.symbols("x")
    expr = rhs if isinstance(rhs, sympy.Basic) else sympy.sympify(rhs)
    deriv = sympy.diff(expr, x)
    is_linear = (not deriv.is_zero) and (x not in deriv.free_symbols)
    correct = "1次関数である" if is_linear else "1次関数ではない"
    other = "1次関数ではない" if is_linear else "1次関数である"
    steps = [
        Step(
            op="inspect_rate_of_change",
            args=[],
            result_srepr=sympy.srepr(deriv),
            # 変化の割合そのもの。x が残る式（2乗の式など）は一定にならない。
            result_display=(
                "変化の割合が一定でない"
                if x in deriv.free_symbols
                else f"変化の割合は {_format_number(deriv)}"
            ),
            # 数字を出さない（§5-#9: narration/ヒントに数値を書かない）。
            narration="式の形から、x が増えるときに y がどのように変わるかを調べる。",
        ),
        Step(
            op="judge_linear",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="変化の割合がつねに一定なら1次関数、一定でなければ1次関数でない。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="lf.classify_linear_function"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.rate_of_change_is_constant")
def rate_of_change_is_constant(_marker: object = None) -> Solution:
    """1次関数の変化の割合はつねに一定で傾きに等しい、という性質の想起（knowledge・g2_l20 Lv1）。
    正しい説明（一定・傾きに等しい）を選ぶ規則。答えは常に同じ命題（命題の正誤想起・V2 規則）。
    solver は引数を取らない（性質は式によらず不変）。無限性は recipe 側の surface param で確保する。
    """
    correct = "変化の割合はつねに一定で、傾きに等しい"
    distractors = [
        "変化の割合は x の値によって変わる",
        "変化の割合は切片に等しい",
    ]
    steps = [
        Step(
            op="recall_property",
            args=[],
            result_srepr="rate_is_constant",
            result_display="変化の割合の性質を思い出す",
            narration="1次関数では、x がどこで増えても y の増え方が同じであることを思い出す。",
        ),
        Step(
            op="select_correct",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="変化の割合はつねに一定で、x の係数（傾き）に等しい。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="lf.rate_of_change_is_constant"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.equation_solution_set_shape")
def equation_solution_set_shape(_marker: object = None) -> Solution:
    """2元1次方程式 ax+by=c の解を座標とする点をすべて集めると直線になる、という性質の想起
    （knowledge・g2_l26 Lv1）。答えは常に「直線」（命題の正誤想起・V2 規則）。solver は引数を
    取らない（性質は係数によらず不変）。無限性は recipe 側の surface param（係数）で確保する。
    """
    correct = "直線"
    distractors = ["放物線", "1つの点"]
    steps = [
        Step(
            op="recall_property",
            args=[],
            result_srepr="solution_set_is_line",
            result_display="解は1組に決まらず、いくつもある",
            narration="2元1次方程式の解を座標とする点をすべて集めると、どんな形になるかを思い出す。",
        ),
        Step(
            op="select_correct",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="2元1次方程式の解の集合は直線になる。",
            detail=(
                "2元1次方程式は、片方の文字にどんな値を入れても、"
                "もう片方の値がそれに応じて1つ決まる。その組を座標とみて"
                "点をとっていくと、点はまっすぐに並ぶので、集めた形は直線になる。"
            ),
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="lf.equation_solution_set_is_line"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.system_solution_is_intersection")
def system_solution_is_intersection(_marker: object = None) -> Solution:
    """連立方程式の解は、2つの式が表す2直線の交点である、という性質の想起
    （knowledge・g2_l27 Lv1）。答えは常に「2直線の交点」（命題の正誤想起・V2 規則）。solver は
    引数を取らない（性質は係数によらず不変）。無限性は recipe 側の surface param（係数）で確保する。
    """
    # 「2つの直線」形（助数詞「つ」は G-Q5t スキャンの除外対象）。「2直線」だと "2" が本文と
    # 衝突し漏洩誤検出になる（直 は助数詞でない）。
    correct = "2つの直線の交点"
    distractors = ["2つの直線の傾き", "2つの直線とy軸との交点"]
    steps = [
        Step(
            op="recall_property",
            args=[],
            result_srepr="solution_is_intersection",
            result_display="どちらの式も成り立たせる値の組",
            narration="連立方程式の解が、2つの式のグラフのどこにあたるかを思い出す。",
        ),
        Step(
            op="select_correct",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="連立方程式の解は、2つの直線の交点の座標である。",
            detail=(
                "それぞれの式のグラフは、その式を成り立たせる点だけを集めた直線である。"
                "どちらの式も成り立たせる点は、両方の直線にのっている点だから、"
                "2つの直線が交わる点にあたる。"
            ),
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=distractors, fact_id="lf.system_solution_is_intersection"
    )
    return Solution(answer=answer, steps=steps)


@register_solver("math.linear_coefficient_role")
def linear_coefficient_role(which: object) -> Solution:
    """1次関数 y=ax+b で x の係数 a・定数項 b がグラフの何を表すかを答える
    （knowledge・g2_l19 Lv1）。which="slope"→a は傾き／which="intercept"→b は切片。
    用語想起の規則で判定＝Q1 は V2（規則ベース）。solver は which だけで決める（式の値は無関係）。
    """
    w = str(which)
    if w == "slope":
        correct, other = "傾き", "切片"
    elif w == "intercept":
        correct, other = "切片", "傾き"
    else:
        raise ValueError(f"which は 'slope' か 'intercept' のいずれか（受領: {which!r}）")
    steps = [
        Step(
            op="locate_part",
            args=[],
            result_srepr=w,
            result_display="x の係数の部分" if w == "slope" else "定数項の部分",
            narration="1次関数の式の、x の係数の部分か、定数項の部分かを確かめる。",
        ),
        Step(
            op="recall_term",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="x の係数は傾き、定数項は切片を表すことを思い出す。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="lf.coefficient_role")
    return Solution(answer=answer, steps=steps)


@register_solver("math.solve_meeting_time_two_segment")
def solve_meeting_time_two_segment(
    va: object, d: object, delay: object, v1: object, p1: object, v2: object,
) -> Solution:
    """速さが変化する2区間を含む2人の出会いの時刻を求める（g2_l30.find_value Lv3）。

    A は原点（地点P）から一定の速さ va で出発する（y_A=va·x）。B は距離 d 離れた
    地点Qから、A の出発より delay 分おくれて出発し、最初の p1 分は速さ v1、その後は
    速さ v2 で地点Pへ向かう（B は地点Pからの道のり y で測ると
    y_B = d - v1·(x-delay) （最初の区間）／d - v1·p1 - v2·(x-delay-p1) （2区間目）
    と表せる）。パラメータだけから2区間目の式 va·x = d-v1·p1-v2·(x-delay-p1) を x
    について解く（構成側が2区間目で出会うことを保証している前提・recipe の構成内訳は
    見ない・double-solve）。答えは出会う時刻 x（SymbolicAnswer）。narration に数字は
    書かない。
    """
    # sympy.nsimplify は数値文字列に対し稀に無関係な無理数近似を返す既知の落とし穴が
    # あるため（例: nsimplify("1455") が 2**(18/175)*... のような式になる）、厳密な
    # 整数/分数値の解析には sympy.sympify を使う（鉄則④相当の実バグ回避）。
    va_s, d_s = sympy.sympify(str(va)), sympy.sympify(str(d))
    delay_s, v1_s, p1_s, v2_s = (
        sympy.sympify(str(delay)), sympy.sympify(str(v1)),
        sympy.sympify(str(p1)), sympy.sympify(str(v2)),
    )
    # va·x + v2·x = d - v1·p1 + v2·(delay+p1)
    rhs = d_s - v1_s * p1_s + v2_s * (delay_s + p1_s)
    x = rhs / (va_s + v2_s)
    steps = [
        Step(
            op="set_up_second_segment_equation",
            args=[],
            result_srepr=sympy.srepr(x),
            result_display="2区間目の式どうしを等号でつなぐ",
            narration="Bが速さを変えた後の式と、Aの式が等しくなる方程式をつくる。",
        ),
        Step(
            op="solve_for_x",
            args=[],
            result_srepr=sympy.srepr(x),
            result_display=f"x = {_format_number(x)}",
            narration="方程式を整理して、出会う時刻 x を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(x), display=f"{_format_number(x)}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g2_l30.word_problem Lv4: 往復する人と向かってくる人が2回目に出会う時刻
#
# P地点とQ地点が distance だけ離れている。A は P を出発して Q へ speed_a で進み、
# Q に着くとすぐ折り返して同じ速さで P へもどる。B は A の head_start 分後に Q を
# 出発して speed_b で P へ進む。
#   A の位置（P からの距離）: 往路 speed_a·t ／ 復路 2·distance − speed_a·t
#   B の位置: distance − speed_b·(t − head_start)
# 1回目は A の往路と B が向かい合って出会う。2回目は折り返した A が B に追いつく。
# 「2回目」が実際に起こるには、その時刻に A がまだ復路にいて、B もまだ P に
# 着いていないことが要る（recipe が構成の段階で保証し、ここでも検算する）。
# ---------------------------------------------------------------------------
_SECOND_MEETING_OPS = [
    "express_positions_in_time",
    "find_first_meeting",
    "express_position_after_turn",
    "solve_for_second_meeting",
]

_SECOND_MEETING_NARRATION: dict[str, str] = {
    "express_positions_in_time": "二人の位置を、出発してからの時間を使ってそれぞれ式で表す。",
    "find_first_meeting": "向かい合って進む間に位置が等しくなる時刻を求め、これが一回目の出会いであることを確かめる。",
    "express_position_after_turn": "折り返したあとの位置は、折り返す地点までの道のりから、折り返してから進んだ道のりを引いて表す。",
    "solve_for_second_meeting": "折り返したあとの位置と、向かってくる相手の位置が等しいとおいて方程式を解く。",
}

def _second_meeting_phrase(d, va, vb, h, t_first) -> dict[str, str]:
    """2回目の出会いの手の括弧（この手で得た式・時刻）。"""
    return {
        # **人の名前・記号は書かない**（問題文の記号は recipe が引くので、
        # solver が A・B と書くと text_quality の「記号の食い違い」に当たる）。
        "express_positions_in_time": (
            f"先に出た人は {_format_number(va)}x、あとの人は {_format_number(d)} - "
            f"{_format_number(vb)}(x - {_format_number(h)})"
        ),
        "find_first_meeting": f"{_format_number(t_first)}分後",
        "express_position_after_turn": (
            f"折り返した人は {_format_number(2 * d)} - {_format_number(va)}x"
        ),
    }


@register_solver("math.solve_second_meeting_time")
def solve_second_meeting_time(
    distance: object, speed_a: object, speed_b: object, head_start: object
) -> Solution:
    """2人が2回目に出会う時刻を求める（g2_l30.word_problem Lv4）。

    問題パラメータ（2地点の距離・2人の速さ・出発の差）だけから導く。
    """
    d = sympy.nsimplify(sympy.sympify(distance))
    va = sympy.nsimplify(sympy.sympify(speed_a))
    vb = sympy.nsimplify(sympy.sympify(speed_b))
    h = sympy.nsimplify(sympy.sympify(head_start))
    if d <= 0 or va <= 0 or vb <= 0 or h < 0:
        raise ValueError("距離・速さは正、出発の差は非負であること")
    if va <= vb:
        raise ValueError("折り返した側が速くないと追いつけない")

    t_turn = d / va  # A が Q に着いて折り返す時刻
    t_first = (d + vb * h) / (va + vb)
    t_second = (d - vb * h) / (va - vb)
    if not (h <= t_first <= t_turn):
        raise ValueError(f"1回目の出会いが往路に収まらない: {t_first}")
    if not (t_turn < t_second <= 2 * t_turn):
        raise ValueError(f"2回目の出会いが復路に収まらない: {t_second}")
    if not (t_second <= h + d / vb):
        raise ValueError(f"2回目の出会いの前に相手が着いてしまう: {t_second}")
    # 恒真: その時刻で2人の位置が一致する。
    pos_a = 2 * d - va * t_second
    pos_b = d - vb * (t_second - h)
    if not sympy.simplify(pos_a - pos_b) == 0:
        raise ValueError(f"2回目の位置が一致しない: {pos_a} != {pos_b}")

    srepr = sympy.srepr(sympy.nsimplify(t_second))
    disp = f"{_format_number(t_second)}分後"
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_SECOND_MEETING_OPS) - 1 else "",
            result_display=disp if i == len(_SECOND_MEETING_OPS) - 1
            else _second_meeting_phrase(d, va, vb, h, t_first)[op],
            narration=_SECOND_MEETING_NARRATION[op],
        )
        for i, op in enumerate(_SECOND_MEETING_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


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
    "point_on_line_at_x",
    "draw_linear_features",
    "draw_from_equation",
    "linear_direction_from_slope",
    "range_endpoint_inclusion",
    "verify_system_solution",
    "classify_linear_function",
    "linear_slope_as_rate",
    "linear_coefficient_role",
    "rate_of_change_is_constant",
    "equation_solution_set_shape",
    "system_solution_is_intersection",
    "solve_meeting_time_two_segment",
    "solve_second_meeting_time",
]
