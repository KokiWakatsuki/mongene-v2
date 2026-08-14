"""一次関数と図形の融合（exam_l1）の独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（直線の傾き・切片・面積の条件）から答えと steps を
導く。純粋・決定論・厳密（sympy.Rational）演算であること。乱数は引かない。

C13（exam_l1・一次関数と図形の融合）クラスタ。三角形の面積はすべて shoelace 公式
（3頂点の座標だけから面積を求める公式）で計算する——動点（solvers/motion.py）・
放物線（solvers/quadratic_function.py）と同じ道具立てにそろえ、面積の求め方を
題材ごとにばらけさせない。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _shoelace(pts: list[tuple[sympy.Expr, sympy.Expr]]) -> sympy.Expr:
    """3点の shoelace 公式による三角形の面積（符号なし・厳密値）。"""
    (x1, y1), (x2, y2), (x3, y3) = pts
    return sympy.Rational(1, 2) * sympy.Abs(
        x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    )


def _fmt(v: sympy.Expr) -> str:
    return sympy.sstr(sympy.nsimplify(v))


def _fmt_pt(pt: tuple[sympy.Expr, sympy.Expr]) -> str:
    return f"({_fmt(pt[0])}, {_fmt(pt[1])})"


def _steps(rows: list[tuple[str, str, str, str]]) -> list[Step]:
    return [
        Step(op=op, args=[], result_srepr=srepr, result_display=disp, narration=narr)
        for op, srepr, disp, narr in rows
    ]


def _intersection(
    m1: sympy.Rational, b1: sympy.Rational, m2: sympy.Rational, b2: sympy.Rational
) -> tuple[sympy.Rational, sympy.Rational]:
    """2直線 y=m1x+b1, y=m2x+b2 の交点。平行なら例外。"""
    if m1 == m2:
        raise ValueError("2直線が平行で交点が定まらない")
    x0 = sympy.nsimplify((b2 - b1) / (m1 - m2))
    return x0, sympy.nsimplify(m1 * x0 + b1)


def _x_intercept(m: sympy.Rational, b: sympy.Rational) -> sympy.Rational:
    if m == 0:
        raise ValueError("傾きが 0 の直線は x 軸と交わらない")
    return sympy.nsimplify(-b / m)


# ---------------------------------------------------------------------------
# exam_l1.find_value Lv3: 交点 → x 切片 → 三角形の面積、と多段で求める
# ---------------------------------------------------------------------------
@register_solver("math.lines_intersection_and_triangle_area")
def lines_intersection_and_triangle_area(
    m1: object, b1: object, m2: object, b2: object, labels: object = None
) -> Solution:
    """2直線の交点と、2本目の x 切片・原点がつくる三角形の面積を求める。

    答えは (交点の座標, 三角形の面積) の組。面積は shoelace 公式で求める。

    **点の名前は recipe から受け取る。** 問題文は「交点をG、x軸との交点をH」と
    名づけるのに、ここを P・Q に固定していたため、答えが `P(5, 12)、△OPQ = 12` と
    問題文に無い記号で出ていた。
    """
    lab = str(labels or "PQ")
    lp, lq = (lab[0], lab[1]) if len(lab) >= 2 else ("P", "Q")
    m1_s, b1_s = sympy.nsimplify(sympy.sympify(m1)), sympy.nsimplify(sympy.sympify(b1))
    m2_s, b2_s = sympy.nsimplify(sympy.sympify(m2)), sympy.nsimplify(sympy.sympify(b2))
    px, py = _intersection(m1_s, b1_s, m2_s, b2_s)
    qx = _x_intercept(m2_s, b2_s)
    origin = (sympy.Integer(0), sympy.Integer(0))
    area = sympy.nsimplify(_shoelace([origin, (px, py), (qx, sympy.Integer(0))]))
    if area == 0:
        raise ValueError("3点が一直線上にあり三角形にならない")
    # 恒真: 底辺 OQ・高さ |py| でも同じ面積になる（別経路での裏取り）。
    if not (area - sympy.Rational(1, 2) * sympy.Abs(qx) * sympy.Abs(py)).equals(0):
        raise ValueError("shoelace と底辺×高さの再計算が一致しない")

    answer = sympy.Tuple(sympy.Tuple(px, py), area)
    srepr = sympy.srepr(answer)
    disp = f"{lp}{_fmt_pt((px, py))}、△O{lp}{lq} = {_fmt(area)}"
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("set_up_equation", "",
             f"{_fmt(m1_s)}x + {_fmt(b1_s)} = {_fmt(m2_s)}x + {_fmt(b2_s)}",
             "2つの直線の式の右辺どうしを等しいとおいて、方程式を立てる。"),
            ("solve_for_x", "", f"x = {_fmt(px)}",
             "その方程式を解いて、交点の x 座標を求める。"),
            ("compute_y", "", f"{lp}{_fmt_pt((px, py))}",
             "求めた x の値をどちらかの式に代入して、交点の y 座標を求める。"),
            ("find_x_intercept", "", f"{lq}{_fmt_pt((qx, sympy.Integer(0)))}",
             "x 軸上の点は y 座標がゼロなので、y にゼロを代入して交わる点の座標を求める。"),
            ("compute_triangle_area", srepr, disp,
             "3つの頂点の座標がそろったので、三角形の面積を求める公式で面積を計算する。"),
        ]),
    )


# ---------------------------------------------------------------------------
# exam_l1.find_value Lv4: 面積の条件から係数を逆算する
# ---------------------------------------------------------------------------
@register_solver("math.slope_from_triangle_area")
def slope_from_triangle_area(b: object, area: object) -> Solution:
    """直線 y=ax+b が両軸と切り取る三角形 OAB の面積から、正の傾き a を逆算する。

    A=(−b/a, 0)、B=(0, b) なので面積は b²/(2|a|)。a>0 のとき A は x 軸の負の側に
    あるが、面積は絶対値で決まるので a = b²/(2·面積)。
    """
    b_s = sympy.nsimplify(sympy.sympify(b))
    area_s = sympy.nsimplify(sympy.sympify(area))
    if b_s <= 0 or area_s <= 0:
        raise ValueError("切片・面積は正であること")
    a_val = sympy.nsimplify(b_s**2 / (2 * area_s))
    if a_val <= 0:
        raise ValueError("正の傾きが求まらない")
    # 恒真: 求めた a で切片を組み直し、shoelace 公式で面積に戻る。
    ax = _x_intercept(a_val, b_s)
    check = _shoelace([
        (sympy.Integer(0), sympy.Integer(0)), (ax, sympy.Integer(0)), (sympy.Integer(0), b_s)
    ])
    if not (check - area_s).equals(0):
        raise ValueError(f"逆算した傾きが面積に戻らない: {check} != {area_s}")

    srepr = sympy.srepr(a_val)
    disp = f"a = {_fmt(a_val)}"
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("express_intercepts", "", "両軸との交点を a で表す",
             "x 軸との交点は y がゼロ、y 軸との交点は x がゼロになるところなので、"
             "それぞれの座標を a を使って表す。"),
            ("set_up_area_equation", "", f"{_fmt(b_s)} × x切片 ÷ 2 = {_fmt(area_s)}",
             "2つの交点と原点を頂点とする三角形の面積を a の式で表し、"
             "与えられた面積に等しいとおく。"),
            ("solve_for_coefficient", srepr, disp,
             "その方程式を解いて a の値を求め、正の数という条件に合うものを選ぶ。"),
        ]),
    )


# ---------------------------------------------------------------------------
# exam_l1.graph_table Lv2: 直線と三角形の位置関係を読む
# ---------------------------------------------------------------------------
@register_solver("math.judge_line_through_triangle")
def judge_line_through_triangle(m: object, b: object, verts: object) -> Solution:
    """直線 y=mx+b が三角形の内部を通るかどうかを判定する。

    各頂点を直線の式に入れた差 y−(mx+b) の**符号がそろっていれば**3頂点は直線の
    同じ側にあり、直線は三角形を通らない。符号が割れていれば通る。
    頂点が直線上にある（差が 0）構成は判定が曖昧になるので例外にする。
    """
    m_s, b_s = sympy.nsimplify(sympy.sympify(m)), sympy.nsimplify(sympy.sympify(b))
    pts = [
        (sympy.nsimplify(sympy.sympify(x)), sympy.nsimplify(sympy.sympify(y)))
        for x, y in list(verts)  # type: ignore[arg-type]
    ]
    if len(pts) != 3:
        raise ValueError("三角形の頂点は3つであること")
    diffs = [y - (m_s * x + b_s) for x, y in pts]
    if any(d == 0 for d in diffs):
        raise ValueError("頂点が直線上にあり、内部を通るかどうかが決まらない")
    signs = {1 if d > 0 else -1 for d in diffs}
    passes = len(signs) == 2
    correct = "通る" if passes else "通らない"
    other = "通らない" if passes else "通る"
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=[other], fact_id="linear_figure.line_through_triangle"
        ),
        steps=_steps([
            ("plot_line_and_triangle", "", "直線と三角形をかき入れる",
             "直線が両軸と交わる点をとって直線をかき、与えられた3つの頂点を結んで三角形をかく。"),
            ("compare_vertices_to_line", "", ("同じ側" if correct == "通らない" else "分かれている"),
             "それぞれの頂点について、直線より上にあるか下にあるかを調べる。"),
            ("conclude_position", correct, correct,
             "3つの頂点が直線の同じ側にそろえば直線は三角形を通らず、"
             "割れていれば三角形の内部を通る。"),
        ]),
    )


# ---------------------------------------------------------------------------
# exam_l1.word_problem Lv3: 誘導あり（交点 → x 切片2つ → 三角形の面積）
# ---------------------------------------------------------------------------
@register_solver("math.intersection_point_of_two_lines")
def intersection_point_of_two_lines(
    m1: object, b1: object, m2: object, b2: object
) -> Solution:
    """2直線の交点の座標だけを求める（誘導ありの (1)）。"""
    m1_s, b1_s = sympy.nsimplify(sympy.sympify(m1)), sympy.nsimplify(sympy.sympify(b1))
    m2_s, b2_s = sympy.nsimplify(sympy.sympify(m2)), sympy.nsimplify(sympy.sympify(b2))
    px, py = _intersection(m1_s, b1_s, m2_s, b2_s)
    pt = sympy.Tuple(px, py)
    srepr = sympy.srepr(pt)
    disp = _fmt_pt((px, py))
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("set_up_equation", "",
             f"{_fmt(m1_s)}x + {_fmt(b1_s)} = {_fmt(m2_s)}x + {_fmt(b2_s)}",
             "2つの直線の式の右辺どうしを等しいとおいて、方程式を立てる。"),
            ("solve_for_x", "", f"x = {_fmt(px)}",
             "その方程式を解いて、交点の x 座標を求める。"),
            ("compute_y", srepr, disp,
             "求めた x の値をどちらかの式に代入して、交点の y 座標を求める。"),
        ]),
    )


@register_solver("math.x_intercepts_of_two_lines")
def x_intercepts_of_two_lines(
    m1: object, b1: object, m2: object, b2: object
) -> Solution:
    """2直線それぞれが x 軸と交わる点の座標を求める（誘導ありの (2)）。"""
    m1_s, b1_s = sympy.nsimplify(sympy.sympify(m1)), sympy.nsimplify(sympy.sympify(b1))
    m2_s, b2_s = sympy.nsimplify(sympy.sympify(m2)), sympy.nsimplify(sympy.sympify(b2))
    q1, q2 = _x_intercept(m1_s, b1_s), _x_intercept(m2_s, b2_s)
    if q1 == q2:
        raise ValueError("2直線の x 切片が同じで三角形にならない")
    zero = sympy.Integer(0)
    pts = sympy.Tuple(sympy.Tuple(q1, zero), sympy.Tuple(q2, zero))
    srepr = sympy.srepr(pts)
    disp = f"{_fmt_pt((q1, zero))}、{_fmt_pt((q2, zero))}"
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("substitute_zero_for_y", "",
             f"{_fmt(m1_s)}x + {_fmt(b1_s)} = 0、{_fmt(m2_s)}x + {_fmt(b2_s)} = 0",
             "x 軸上の点は y 座標がゼロなので、それぞれの式の y にゼロを代入する。"),
            ("solve_for_x_intercepts", srepr, disp,
             "できた方程式をそれぞれ解いて、x 軸と交わる点の座標を求める。"),
        ]),
    )


@register_solver("math.triangle_area_from_two_lines")
def triangle_area_from_two_lines(
    m1: object, b1: object, m2: object, b2: object
) -> Solution:
    """2直線の交点と、それぞれの x 切片がつくる三角形の面積を求める（誘導ありの (3)）。"""
    m1_s, b1_s = sympy.nsimplify(sympy.sympify(m1)), sympy.nsimplify(sympy.sympify(b1))
    m2_s, b2_s = sympy.nsimplify(sympy.sympify(m2)), sympy.nsimplify(sympy.sympify(b2))
    px, py = _intersection(m1_s, b1_s, m2_s, b2_s)
    q1, q2 = _x_intercept(m1_s, b1_s), _x_intercept(m2_s, b2_s)
    zero = sympy.Integer(0)
    area = sympy.nsimplify(_shoelace([(px, py), (q1, zero), (q2, zero)]))
    if area == 0:
        raise ValueError("3点が一直線上にあり三角形にならない")
    # 恒真: 底辺は x 軸上の2点の距離、高さは交点の y 座標の絶対値。
    if not (area - sympy.Rational(1, 2) * sympy.Abs(q1 - q2) * sympy.Abs(py)).equals(0):
        raise ValueError("shoelace と底辺×高さの再計算が一致しない")

    srepr = sympy.srepr(area)
    disp = _fmt(area)
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("identify_base_on_x_axis", "", f"底辺 {_fmt(sympy.Abs(q1 - q2))}",
             "x 軸上にある2つの頂点を結んだ辺を底辺とみて、その長さを2点の x 座標の差から求める。"),
            ("read_height_from_vertex", "", f"高さ {_fmt(sympy.Abs(py))}",
             "残りの頂点の y 座標の絶対値が、その底辺に対する高さになる。"),
            ("compute_triangle_area", srepr, disp,
             "底辺と高さがそろったので、三角形の面積を求める。"),
        ]),
    )


# ---------------------------------------------------------------------------
# exam_l1.word_problem Lv4: 面積が k 倍になる x 軸上の点を構成する
# ---------------------------------------------------------------------------
@register_solver("math.point_on_x_axis_for_area_multiple")
def point_on_x_axis_for_area_multiple(m: object, b: object, k: object) -> Solution:
    """三角形 ABC の面積が三角形 OAB の k 倍になる、x 軸上の点 C を求める。

    A は直線 y=mx+b の x 切片、B は y 切片。底辺をどちらも x 軸上にとると高さは
    共通（B の y 座標）なので、面積の比は底辺の長さの比に等しい——この見方が
    「等積変形・面積比」の眼目で、二次方程式を解く必要はない。
    """
    m_s, b_s = sympy.nsimplify(sympy.sympify(m)), sympy.nsimplify(sympy.sympify(b))
    k_s = sympy.nsimplify(sympy.sympify(k))
    if m_s <= 0 or b_s <= 0 or k_s <= 1:
        raise ValueError("傾き・切片は正、倍率は 1 より大きいこと")
    ax = _x_intercept(m_s, b_s)  # 負の側
    zero = sympy.Integer(0)
    # AC = k·AO（高さが共通なので面積の比＝底辺の比）。C は x 軸の正の側。
    cx = sympy.nsimplify(ax + k_s * (zero - ax))
    if cx <= 0:
        raise ValueError("求める点が x 軸の正の側にならない")
    area_oab = _shoelace([(zero, zero), (ax, zero), (zero, b_s)])
    area_abc = _shoelace([(ax, zero), (zero, b_s), (cx, zero)])
    if not (area_abc - k_s * area_oab).equals(0):
        raise ValueError(f"面積が {k_s} 倍にならない: {area_abc} != {k_s}·{area_oab}")

    pt = sympy.Tuple(cx, zero)
    srepr = sympy.srepr(pt)
    disp = _fmt_pt((cx, zero))
    return Solution(
        answer=SymbolicAnswer(srepr=srepr, display=disp),
        steps=_steps([
            ("find_intercepts", "", f"{_fmt_pt((ax, zero))}、{_fmt_pt((zero, b_s))}",
             "x 軸との交点は y がゼロ、y 軸との交点は x がゼロになるところなので、"
             "それぞれの座標を求める。"),
            ("note_common_height", "", "高さが共通であることに気づく",
             "底辺をどちらも x 軸上にとると、2つの三角形の高さはどちらも同じ点の"
             "y 座標になるので、面積の比は底辺の長さの比に等しい。"),
            ("set_up_ratio_equation", "", f"底辺の比が {_fmt(k_s)} になる位置",
             "面積が指定された倍率になる条件を、底辺の長さの比に置きかえて式にする。"),
            ("solve_for_point", srepr, disp,
             "その方程式を解き、x 軸の正の部分にあるという条件に合う点の座標を求める。"),
        ]),
    )


__all__ = [
    "lines_intersection_and_triangle_area",
    "slope_from_triangle_area",
    "judge_line_through_triangle",
    "intersection_point_of_two_lines",
    "x_intercepts_of_two_lines",
    "triangle_area_from_two_lines",
    "point_on_x_axis_for_area_multiple",
]
