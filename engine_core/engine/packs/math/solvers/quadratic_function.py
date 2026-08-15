"""関数 y=ax² まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（a・x の値／区間の端点／mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C6（g3 二次関数 y=ax²）クラスタのうち、放物線の描画を必要としない 13 セルを対象にする
（g3_l32/l34/l35/l37/l38）。各関数を1つのモジュールに集約する:
  - `math.evaluate_quadratic_function`: g3_l32.calculation Lv1（代入して y を求める）
  - `math.y_range_over_quadratic_domain`: g3_l34.find_value Lv2/Lv3（変域→変域）
  - `math.rate_of_change_quadratic`: g3_l35.find_value Lv2/Lv3（変化の割合の順算/逆算）
  - `math.intersection_parabola_line`: g3_l37.find_value Lv2/Lv3/Lv4（放物線と直線の交点・
    線分長・面積・逆算）
  - `math.solve_quadratic_motion_area`: g3_l38.find_value Lv2/Lv3（動点の面積・区間の場合分け）

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。sympy の恒真判定は
`.equals(0)` を使い `.evalf()` に頼らない（ハング回避）。
"""
from __future__ import annotations

import re
from typing import cast

import sympy

from engine.core.contracts import Feature, GraphAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers._step_text import fmt_expr
from engine.packs.math.solvers.arithmetic import fmt_measure

_X = sympy.Symbol("x")
_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


def _fmt_scalar(v: sympy.Expr) -> str:
    """数（整数・分数・根号を含む式）の教材表記。"""
    s = _SQRT_RE.sub(r"√\1", str(sympy.sstr(sympy.together(v))))
    return s.replace("*", "")


def _fmt_point(pt: tuple[sympy.Expr, sympy.Expr]) -> str:
    return f"({_fmt_scalar(pt[0])}, {_fmt_scalar(pt[1])})"


# ---------------------------------------------------------------------------
# g3_l32.calculation Lv1: y=ax² に x を代入して y を求める
# ---------------------------------------------------------------------------
@register_solver("math.evaluate_quadratic_function")
def evaluate_quadratic_function(a: object, x: object) -> Solution:
    """y=ax² に x の値を代入して y の値を求める（g3_l32.calculation Lv1）。

    比例定数 a と代入する x の値だけから y=a·x² を計算する（double-solve）。
    narration には数字を書かない。
    """
    a_s = sympy.nsimplify(a)
    x_s = sympy.nsimplify(x)
    y = a_s * x_s**2
    disp = _fmt_scalar(y)
    srepr = sympy.srepr(y)
    steps = [
        Step(
            op="substitute_x",
            args=[],
            result_srepr="",
            # 代入したままの式（`3 × (-4)²`）。指示の言い直しを括弧に置かない（面③）。
            result_display=f"{_fmt_scalar(a_s)} × ({_fmt_scalar(x_s)})²",
            narration="式の x に、与えられた値をあてはめる。",
        ),
        Step(
            op="compute_y",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="2乗を計算してから比例定数をかけ、y の値を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l34.find_value Lv2/Lv3: x の変域から y の変域を求める
# ---------------------------------------------------------------------------
_RANGE_STEPS: dict[str, list[str]] = {
    # Lv2: x の変域が0の片側（単調区間）— 端点の値をそのまま比較するだけでよい
    "one_sided": ["evaluate_endpoints", "order_by_magnitude"],
    # Lv3: x の変域が0をまたぐ — 頂点(0,0)を含むかどうかの吟味が追加で要る
    "straddles_zero": ["check_domain_contains_vertex", "evaluate_endpoints", "combine_with_vertex"],
}

_RANGE_NARRATION: dict[str, str] = {
    "evaluate_endpoints": "x の変域の両端の値を、それぞれ式に代入して y の値を求める。",
    "order_by_magnitude": "a の符号に注意して、2つの端点の y の値を大小の順に並べる。",
    "check_domain_contains_vertex": "x の変域が、頂点である原点をまたいでいるかどうかを確かめる。",
    "combine_with_vertex": "頂点の y の値と両端の y の値を合わせて、変域の両端を決める。",
}

def _range_step_display(op: str, x1, x2, y1, y2, straddles: bool) -> str:
    """変域の手の括弧（この手で得た値）。"""
    if op == "evaluate_endpoints":
        return f"x = {_fmt_scalar(x1)} のとき y = {_fmt_scalar(y1)}、" \
               f"x = {_fmt_scalar(x2)} のとき y = {_fmt_scalar(y2)}"
    if op == "check_domain_contains_vertex":
        # またぐかどうか＝この手で分かること。またぐなら頂点の y=0 も候補に入る。
        return "またぐので y = 0 も候補" if straddles else "またがない"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.y_range_over_quadratic_domain")
def y_range_over_quadratic_domain(a: object, x_lo: object, x_hi: object, mode: object) -> Solution:
    """y=ax² の x の変域 [x_lo, x_hi] に対する y の変域を求める（g3_l34.find_value）。

    mode="one_sided"（Lv2・0の片側の単調区間）／"straddles_zero"（Lv3・0をまたぐ・
    頂点(0,0)を含むかどうかを吟味する）。mode ごとに steps の op 列を変える＝level_sep。
    問題パラメータ（a・x_lo・x_hi・mode）だけから独立に再計算する（double-solve）。
    """
    mode_s = str(mode)
    if mode_s not in _RANGE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    a_s = sympy.nsimplify(a)
    x1, x2 = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    if x1 >= x2:
        raise ValueError("x の変域は x_lo < x_hi であること")
    if mode_s == "one_sided" and x1 * x2 < 0:
        raise ValueError("one_sided は 0 をまたがない変域であること")
    if mode_s == "straddles_zero" and not (x1 < 0 < x2):
        raise ValueError("straddles_zero は 0 を内部に含む変域であること")

    y1, y2 = a_s * x1**2, a_s * x2**2
    candidates = [y1, y2]
    if mode_s == "straddles_zero":
        candidates.append(sympy.Integer(0))  # 頂点 (0,0) の y 値
    y_lo, y_hi = sympy.Min(*candidates), sympy.Max(*candidates)

    disp = f"{_fmt_scalar(y_lo)} ≦ y ≦ {_fmt_scalar(y_hi)}"
    srepr = sympy.srepr(sympy.Tuple(y_lo, y_hi))

    ops = _RANGE_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _range_step_display(op, x1, x2, y1, y2, mode_s == "straddles_zero"),
            narration=_RANGE_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l35.find_value Lv2/Lv3: 変化の割合の順算・逆算
# ---------------------------------------------------------------------------
_ROC_STEPS: dict[str, list[str]] = {
    # Lv2: 2点/区間から変化の割合を求める（順算）
    "forward": ["evaluate_endpoints_roc", "compute_rate_of_change"],
    # Lv3: 変化の割合から係数 a を逆算する
    "solve_for_a": ["set_up_rate_equation", "solve_for_coefficient"],
}

_ROC_NARRATION: dict[str, str] = {
    "evaluate_endpoints_roc": "x の変域の両端の値を、それぞれ式に代入して y の値を求める。",
    "compute_rate_of_change": "y の増加量を x の増加量で割り、変化の割合を求める。",
    "set_up_rate_equation": "y=ax² の変化の割合を a を使った式で表し、与えられた値と等しいとおく。",
    "solve_for_coefficient": "その方程式を解いて、比例定数 a の値を求める。",
}

def _roc_step_display(op: str, x1, x2, y1, y2, rate) -> str:
    """変化の割合の手の括弧（この手で得た値・式）。"""
    if op == "evaluate_endpoints_roc":
        return (f"x = {_fmt_scalar(x1)} のとき y = {_fmt_scalar(y1)}、"
                f"x = {_fmt_scalar(x2)} のとき y = {_fmt_scalar(y2)}")
    if op == "set_up_rate_equation":
        # 変化の割合は a(x1+x2)。与えられた値と等しいとおいた式。
        return f"a × ({_fmt_scalar(x1)} + {_fmt_scalar(x2)}) = {_fmt_scalar(rate)}"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.rate_of_change_quadratic")
def rate_of_change_quadratic(a: object, x1: object, x2: object, mode: object) -> Solution:
    """y=ax² の変化の割合の順算・逆算を行う（g3_l35.find_value）。

    mode="forward"（Lv2・a と区間 [x1,x2] から変化の割合そのものを求める）／
    "solve_for_a"（Lv3・区間 [x1,x2] と変化の割合の値が既知のとき a を逆算。このとき
    引数 a は「変化の割合の値」を意味する＝rate=a·(x1+x2) を a について解く）。
    mode ごとに steps の op 列を変える＝level_sep。
    """
    mode_s = str(mode)
    if mode_s not in _ROC_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    x1_s, x2_s = sympy.nsimplify(x1), sympy.nsimplify(x2)
    if x1_s == x2_s:
        raise ValueError("x1 と x2 が等しく変化の割合が定まらない")

    if mode_s == "forward":
        a_s = sympy.nsimplify(a)
        y1, y2 = a_s * x1_s**2, a_s * x2_s**2
        rate = (y2 - y1) / (x2_s - x1_s)
        disp = _fmt_scalar(rate)
        srepr = sympy.srepr(rate)
    else:  # solve_for_a
        rate_s = sympy.nsimplify(a)  # 「変化の割合の値」として渡される
        # rate = a(x1+x2) より a = rate/(x1+x2)
        denom = x1_s + x2_s
        if denom == 0:
            raise ValueError("x1+x2=0 では a が一意に定まらない")
        a_val = rate_s / denom
        disp = _fmt_scalar(a_val)
        srepr = sympy.srepr(a_val)

    ops = _ROC_STEPS[mode_s]
    if mode_s == "forward":
        step_y1, step_y2, step_rate = y1, y2, rate
    else:
        step_y1 = step_y2 = None
        step_rate = rate_s
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _roc_step_display(op, x1_s, x2_s, step_y1, step_y2, step_rate),
            narration=_ROC_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l37.find_value Lv2/Lv3/Lv4: 放物線と直線の交点・線分長・面積・逆算
# ---------------------------------------------------------------------------
def _parabola_line_intersections(a: sympy.Expr, m: sympy.Expr, b: sympy.Expr) -> list[sympy.Expr]:
    """y=ax² と y=mx+b の交点の x 座標（昇順）を求める。ax²-mx-b=0 を解く。"""
    roots = sympy.solve(sympy.Eq(a * _X**2, m * _X + b), _X)
    return sorted(roots, key=lambda r: float(r.evalf()))


def _shoelace_area(pts: list[tuple[sympy.Expr, sympy.Expr]]) -> sympy.Expr:
    """3点の shoelace 公式による三角形面積（符号なし・厳密値）。"""
    (x1, y1), (x2, y2), (x3, y3) = pts
    return sympy.Rational(1, 2) * sympy.Abs(
        x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    )


_INTERSECTION_STEPS: dict[str, list[str]] = {
    # Lv2: 放物線と直線を連立して交点を求める
    "find_intersection": ["set_up_equation", "solve_for_x", "compute_y"],
    # Lv3: 交点から線分長・三角形の面積を多段で求める
    "segment_and_area": [
        "set_up_equation", "solve_for_x", "compute_y",
        "compute_segment_length", "compute_triangle_area",
    ],
    # Lv4: 面積を等分する点を逆算する
    "equal_area_point": [
        "set_up_equation", "solve_for_x", "compute_y",
        "compute_triangle_area", "solve_for_equal_area_point",
    ],
    # g3_l37.word_problem Lv3 の小問: 三角形 OAB の面積だけを答える
    # （segment_and_area は線分長も一緒に答えるので、面積だけを問う小問には使えない）
    "triangle_area": [
        "set_up_equation", "solve_for_x", "compute_y", "compute_triangle_area",
    ],
}

_INTERSECTION_NARRATION: dict[str, str] = {
    "set_up_equation": "放物線の式と直線の式の右辺どうしを等しいとおき、方程式を立てる。",
    "solve_for_x": "その方程式を解いて、交点の x 座標を求める。",
    "compute_y": "求めた x の値を式に代入して、交点の y 座標を求める。",
    "compute_segment_length": "2点の座標の差から、線分の長さを求める。",
    "compute_triangle_area": "頂点の座標から、三角形の面積を求める公式で面積を計算する。",
    "solve_for_equal_area_point": "三角形 PAB の面積が三角形 OAB の面積と等しくなる条件から方程式を立て、点 P の座標を決める。",
}

def _intersection_step_display(
    op: str, a, m, b, xA, xB, yA, yB
) -> str:
    """交点まわりの手の括弧（この手で得た式・値）。"""
    if op == "set_up_equation":
        return f"{fmt_expr(a * _X**2)} = {fmt_expr(m * _X + b)}"
    if op == "solve_for_x":
        return f"x = {_fmt_scalar(xA)}, x = {_fmt_scalar(xB)}"
    if op == "compute_y":
        return f"A({_fmt_scalar(xA)}, {_fmt_scalar(yA)}), B({_fmt_scalar(xB)}, {_fmt_scalar(yB)})"
    if op == "compute_segment_length":
        seg = sympy.sqrt((xB - xA) ** 2 + (yB - yA) ** 2)
        return f"AB = {_fmt_scalar(seg)}"
    if op == "compute_triangle_area":
        area = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), (xA, yA), (xB, yB)])
        return f"△OAB = {_fmt_scalar(area)}"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.intersection_parabola_line")
def intersection_parabola_line(
    a: object, m: object, b: object, mode: object,
) -> Solution:
    """放物線 y=ax² と直線 y=mx+b の交点・線分長・面積を求める（g3_l37.find_value）。

    mode="find_intersection"（Lv2・交点座標のみ）／"segment_and_area"（Lv3・線分 AB の
    長さと三角形 OAB の面積）／"equal_area_point"（Lv4・y 軸上の点 P で三角形 PAB の面積が
    三角形 OAB の面積と**等しくなる**ときの P の座標。O 以外の解を採用する）。mode ごとに
    steps の op 列を変える＝level_sep。問題パラメータ（a・m・b・mode）だけから
    独立に再計算する（double-solve）。
    """
    mode_s = str(mode)
    if mode_s not in _INTERSECTION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    a_s, m_s, b_s = sympy.nsimplify(a), sympy.nsimplify(m), sympy.nsimplify(b)
    roots = _parabola_line_intersections(a_s, m_s, b_s)
    if len(roots) != 2:
        raise ValueError(f"交点がちょうど2つでない: {roots}")
    xA, xB = roots[0], roots[1]
    yA, yB = a_s * xA**2, a_s * xB**2
    ptA, ptB = (xA, yA), (xB, yB)

    if mode_s == "find_intersection":
        disp = f"A{_fmt_point(ptA)}, B{_fmt_point(ptB)}"
        srepr = sympy.srepr(sympy.Tuple(sympy.Tuple(*ptA), sympy.Tuple(*ptB)))
    elif mode_s == "triangle_area":
        area = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), ptA, ptB])
        disp = f"△OAB = {_fmt_scalar(area)}"
        srepr = sympy.srepr(area)
    elif mode_s == "segment_and_area":
        seg_len = sympy.sqrt((xB - xA) ** 2 + (yB - yA) ** 2)
        area = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), ptA, ptB])
        disp = f"AB = {_fmt_scalar(seg_len)}, △OAB = {_fmt_scalar(area)}"
        srepr = sympy.srepr(sympy.Tuple(seg_len, area))
    else:  # equal_area_point
        area_oab = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), ptA, ptB])
        # P=(0,p) は y 軸上。△PAB の面積が △OAB と等しくなる p を解く（p=0 以外の解）。
        p_sym = sympy.Symbol("p", real=True)
        area_pab = _shoelace_area([(sympy.Integer(0), p_sym), ptA, ptB])
        p_solutions = sympy.solve(sympy.Eq(area_pab, area_oab), p_sym)
        p_candidates = sorted(
            {sympy.simplify(s) for s in p_solutions if sympy.simplify(s) != 0},
            key=lambda v: float(v.evalf()),
        )
        if not p_candidates:
            raise ValueError("O 以外に等積になる y 軸上の点が求まらない")
        p_val = p_candidates[0]
        disp = f"P(0, {_fmt_scalar(p_val)})"
        srepr = sympy.srepr(sympy.Tuple(sympy.Integer(0), p_val))

    ops = _INTERSECTION_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _intersection_step_display(op, a_s, m_s, b_s, xA, xB, yA, yB),
            narration=_INTERSECTION_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l37.word_problem Lv3/Lv4: 放物線と直線が交わる図形の融合
#
# いずれも既存の交点計算（`_parabola_line_intersections`）と shoelace 公式
# （`_shoelace_area`）の上に乗せる＝新しい幾何ロジックは足さない。
# ---------------------------------------------------------------------------
_EQUAL_AREA_OPS = [
    "set_up_equation",
    "solve_for_x",
    "find_parallel_line_through_origin",
    "solve_for_equal_area_point",
]

_EQUAL_AREA_NARRATION: dict[str, str] = {
    "set_up_equation": "放物線の式と直線の式の右辺どうしを等しいとおき、方程式を立てる。",
    "solve_for_x": "その方程式を解いて、二つの交点の x 座標を求める。",
    "find_parallel_line_through_origin": "底辺を共通の線分とみると、高さが等しければ面積も等しい。原点を通り、その線分に平行な直線を考える。",
    "solve_for_equal_area_point": "その平行な直線と放物線が交わる点のうち、原点でないほうを求める。",
}

def _equal_area_display(op: str, a, m, b, xA, xB) -> str:
    """面積が等しい点の手の括弧（この手で得た式・値）。"""
    if op == "set_up_equation":
        return f"{fmt_expr(a * _X**2)} = {fmt_expr(m * _X + b)}"
    if op == "solve_for_x":
        return f"x = {_fmt_scalar(xA)}, x = {_fmt_scalar(xB)}"
    if op == "find_parallel_line_through_origin":
        return f"y = {fmt_expr(m * _X)}"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


# ---------------------------------------------------------------------------
# exam_l2.find_value Lv4: 交点の x 座標から放物線の係数を逆算し、面積まで進む
# ---------------------------------------------------------------------------
_COEFF_FROM_INTERSECTION_OPS = [
    "compute_point_on_line",
    "solve_for_coefficient",
    "find_other_intersection",
    "compute_triangle_area",
]

_COEFF_FROM_INTERSECTION_NARRATION: dict[str, str] = {
    "compute_point_on_line": "交点は直線の上にもあるので、与えられた x 座標を直線の式に代入して y 座標を求める。",
    "solve_for_coefficient": "その点が放物線 y=ax² の上にもあることから、a についての方程式を立てて解く。",
    "find_other_intersection": "a が決まったので、放物線の式と直線の式を連立して、もう一方の交点を求める。",
    "compute_triangle_area": "2つの交点と原点の座標がそろったので、三角形の面積を求める公式で面積を計算する。",
}

def _coeff_from_intersection_display(op: str, la, lb, xa, ya, a_val, ptB) -> str:
    """係数の逆算の手の括弧（この手で得た値）。"""
    if op == "compute_point_on_line":
        return f"{la}({_fmt_scalar(xa)}, {_fmt_scalar(ya)})"
    if op == "solve_for_coefficient":
        return f"a = {_fmt_scalar(a_val)}"
    if op == "find_other_intersection":
        return f"{lb}({_fmt_scalar(ptB[0])}, {_fmt_scalar(ptB[1])})"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.parabola_coefficient_from_intersection")
def parabola_coefficient_from_intersection(
    m: object, b: object, x_a: object, labels: object = None
) -> Solution:
    """交点の x 座標から放物線 y=ax² の係数 a を逆算し、三角形の面積も求める。

    一方の交点は直線 y=mx+b の上にあるので y=m·x+b、放物線の上にもあるので a=y/x²。
    もう一方は残りの交点。面積は既存の shoelace 公式（`_shoelace_area`）で求める
    ＝新しい幾何ロジックは足さない。答えは (a, 三角形の面積) の組。

    **点の名前は recipe から受け取る。** 問題文が「2点F、Dで交わり」と名づけるのに
    ここを A・B に固定していたため、答えが `a = 4、△OAB = 60` と問題文に無い記号で
    出ていた。
    """
    lab = str(labels or "AB")
    la, lb = (lab[0], lab[1]) if len(lab) >= 2 else ("A", "B")
    m_s, b_s = sympy.nsimplify(sympy.sympify(m)), sympy.nsimplify(sympy.sympify(b))
    xa_s = sympy.nsimplify(sympy.sympify(x_a))
    if xa_s == 0:
        raise ValueError("交点の x 座標が 0 だと a が決まらない")
    ya = m_s * xa_s + b_s
    a_val = sympy.nsimplify(ya / xa_s**2)
    if a_val == 0:
        raise ValueError("a が 0 になり放物線にならない")
    roots = _parabola_line_intersections(a_val, m_s, b_s)
    if len(roots) != 2:
        raise ValueError(f"交点がちょうど2つでない: {roots}")
    if xa_s not in roots:
        raise ValueError(f"逆算した a のもとで A が交点にならない: {roots}")
    xb_s = roots[0] if roots[1] == xa_s else roots[1]
    ptA, ptB = (xa_s, a_val * xa_s**2), (xb_s, a_val * xb_s**2)
    area = sympy.nsimplify(
        _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), ptA, ptB])
    )
    if area == 0:
        raise ValueError("原点と2交点が一直線上にあり三角形にならない")

    answer = sympy.Tuple(a_val, area)
    srepr = sympy.srepr(answer)
    disp = f"a = {_fmt_scalar(a_val)}、△O{la}{lb} = {_fmt_scalar(area)}"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(_COEFF_FROM_INTERSECTION_OPS) - 1 else "",
            result_display=(
                disp if i == len(_COEFF_FROM_INTERSECTION_OPS) - 1
                else _coeff_from_intersection_display(op, la, lb, xa_s, ya, a_val, ptB)
            ),
            narration=_COEFF_FROM_INTERSECTION_NARRATION[op],
        )
        for i, op in enumerate(_COEFF_FROM_INTERSECTION_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.parabola_equal_area_point")
def parabola_equal_area_point(a: object, m: object, b: object) -> Solution:
    """三角形 PAB の面積が三角形 OAB と等しくなる放物線上の点 P の x 座標。

    A・B は放物線 y=ax² と直線 y=mx+b の交点。線分 AB を共通の底辺とみると、
    面積が等しい ⇔ AB からの距離が等しい。原点 O と同じ側でその条件を満たすのは
    「O を通り AB に平行な直線」の上の点なので、その直線 y=mx と放物線の交点のうち
    原点でないほう＝ x = m/a が答え（＝2交点の x 座標の和）。
    P が A・B と一致すると三角形がつぶれるので、その場合は例外にする。
    """
    a_s, m_s, b_s = sympy.nsimplify(a), sympy.nsimplify(m), sympy.nsimplify(b)
    roots = _parabola_line_intersections(a_s, m_s, b_s)
    if len(roots) != 2:
        raise ValueError(f"交点がちょうど2つでない: {roots}")
    xA, xB = roots
    xP = sympy.simplify(m_s / a_s)
    if xP == 0 or xP in (xA, xB):
        raise ValueError(f"P が原点または A・B と一致する: {xP}")
    # 恒真: 求めた P で三角形の面積が実際に一致する。
    ptA, ptB = (xA, a_s * xA**2), (xB, a_s * xB**2)
    ptP = (xP, a_s * xP**2)
    area_oab = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), ptA, ptB])
    area_pab = _shoelace_area([ptP, ptA, ptB])
    if not sympy.simplify(area_pab - area_oab) == 0:
        raise ValueError(f"面積が一致しない: {area_pab} != {area_oab}")
    if area_oab == 0:
        raise ValueError("三角形 OAB がつぶれている")

    srepr = sympy.srepr(xP)
    disp = f"x = {_fmt_scalar(xP)}"
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_EQUAL_AREA_OPS) - 1 else "",
            result_display=disp if i == len(_EQUAL_AREA_OPS) - 1
            else _equal_area_display(op, a_s, m_s, b_s, xA, xB),
            narration=_EQUAL_AREA_NARRATION[op],
        )
        for i, op in enumerate(_EQUAL_AREA_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


_AREA_RATIO_OPS = [
    "set_up_equation",
    "solve_for_x",
    "find_x_axis_intersection",
    "compute_two_triangle_areas",
    "reduce_area_ratio",
]

_AREA_RATIO_NARRATION: dict[str, str] = {
    "set_up_equation": "放物線の式と直線の式の右辺どうしを等しいとおき、方程式を立てる。",
    "solve_for_x": "その方程式を解いて、二つの交点の x 座標を求め、y 座標も出す。",
    "find_x_axis_intersection": "直線の式で y を零とおいて、x 軸との交点の座標を求める。",
    "compute_two_triangle_areas": "頂点の座標から、二つの三角形の面積をそれぞれ求める。",
    "reduce_area_ratio": "求めた二つの面積の比を、できるだけ簡単な整数の比に直す。",
}

def _area_ratio_display(op: str, a, m, b, ptA, ptB, ptC, area_oab, area_obc) -> str:
    """面積の比の手の括弧（この手で得た式・値）。"""
    if op == "set_up_equation":
        return f"{fmt_expr(a * _X**2)} = {fmt_expr(m * _X + b)}"
    if op == "solve_for_x":
        return (f"A({_fmt_scalar(ptA[0])}, {_fmt_scalar(ptA[1])}), "
                f"B({_fmt_scalar(ptB[0])}, {_fmt_scalar(ptB[1])})")
    if op == "find_x_axis_intersection":
        return f"C({_fmt_scalar(ptC[0])}, 0)"
    if op == "compute_two_triangle_areas":
        return f"△OAB = {_fmt_scalar(area_oab)}、△OBC = {_fmt_scalar(area_obc)}"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.parabola_line_area_ratio")
def parabola_line_area_ratio(a: object, m: object, b: object) -> Solution:
    """三角形 OAB と三角形 OBC の面積の比（C は直線 AB と x 軸の交点・g3_l37 Lv4）。"""
    a_s, m_s, b_s = sympy.nsimplify(a), sympy.nsimplify(m), sympy.nsimplify(b)
    if m_s == 0:
        raise ValueError("直線が x 軸と交わらない（傾きが零）")
    roots = _parabola_line_intersections(a_s, m_s, b_s)
    if len(roots) != 2:
        raise ValueError(f"交点がちょうど2つでない: {roots}")
    xA, xB = roots
    ptA, ptB = (xA, a_s * xA**2), (xB, a_s * xB**2)
    xC = sympy.simplify(-b_s / m_s)
    ptC = (xC, sympy.Integer(0))
    origin = (sympy.Integer(0), sympy.Integer(0))
    area_oab = _shoelace_area([origin, ptA, ptB])
    area_obc = _shoelace_area([origin, ptB, ptC])
    if area_oab == 0 or area_obc == 0:
        raise ValueError("三角形がつぶれている")
    ratio = sympy.Rational(area_oab, area_obc)
    if area_oab == area_obc:
        raise ValueError("比が 1:1 に潰れている（比を問う意味がない）")

    pair = sympy.Tuple(ratio.p, ratio.q)
    srepr = sympy.srepr(pair)
    disp = f"△OAB : △OBC = {ratio.p} : {ratio.q}"
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_AREA_RATIO_OPS) - 1 else "",
            result_display=disp if i == len(_AREA_RATIO_OPS) - 1
            else _area_ratio_display(op, a_s, m_s, b_s, ptA, ptB, ptC, area_oab, area_obc),
            narration=_AREA_RATIO_NARRATION[op],
        )
        for i, op in enumerate(_AREA_RATIO_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# g3_l38.find_value Lv2/Lv3: 動点の面積（区間ごとの立式・場合分け）
# 正方形 ABCD（A=(0,0), B=(s,0), C=(s,s), D=(0,s)）の周上を、点 P が B を出発して
# B→C→D の順に動く。三角形 ABP の面積を shoelace 公式で求める（units.generated.yaml
# の例に一致：「BP=4cmのときの三角形ABPの面積」「BからB→C→Dの順に...三角形ABPの面積」）。
# ---------------------------------------------------------------------------
_QMOTION_STEPS: dict[str, list[str]] = {
    # Lv2: 指定区間で動点位置から面積を立式して求める（1区間のみ・辺BC上）
    "single_segment": ["locate_point_p", "compute_triangle_area"],
    # Lv3: 区間の境界での場合分けを要する面積を構成して求める（B→C→D）
    "case_split": ["determine_which_segment", "locate_point_p", "compute_triangle_area"],
}

_QMOTION_NARRATION: dict[str, str] = {
    "locate_point_p": "動いた道のりから、点 P の位置の座標を決める。",
    "compute_triangle_area": "3点の座標から、三角形の面積を求める公式で面積を計算する。",
    "determine_which_segment": "点 P が動いた道のりから、周上のどの辺の上にいるかを判断する。",
}

def _qmotion_display(op: str, px, py, on_bc: bool) -> str:
    """動点の手の括弧（この手で得た位置）。"""
    if op == "locate_point_p":
        return f"P({_fmt_scalar(px)}, {_fmt_scalar(py)})"
    if op == "determine_which_segment":
        return "辺BC上" if on_bc else "辺CD上"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.solve_quadratic_motion_area")
def solve_quadratic_motion_area(s: object, d: object, mode: object) -> Solution:
    """正方形の周上を動く点 P による三角形 ABP の面積を求める（g3_l38.find_value）。

    正方形を A=(0,0), B=(s,0), C=(s,s), D=(0,s) に固定し、点 P が B を出発して
    B→C→D の順に動いた道のり d だけから位置を決める（Lv2 は BP=d をそのまま距離として
    与えられる想定・Lv3 は速さ×時間で d を求めた上で渡す想定。solver 自身は道のり d
    のみを受け取り速さ・時間の区別はしない）。mode="single_segment"（Lv2・P が辺 BC 上・
    1区間のみ）／"case_split"（Lv3・P が B→C→D で区間をまたぎうる・d の区間で場合分け）。
    三角形 ABP の面積を shoelace 公式で求める。mode ごとに steps の op 列を変える＝
    level_sep。問題パラメータ（s・d・mode）だけから独立に再計算する（double-solve）。
    """
    mode_s = str(mode)
    if mode_s not in _QMOTION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    s_v = sympy.nsimplify(s)
    d_v = sympy.nsimplify(d)

    if mode_s == "single_segment":
        if not (0 < d_v < s_v):
            raise ValueError("single_segment は P が辺 BC 上（0<d<s）にあること")
        px, py = s_v, d_v  # 辺 BC 上（B=(s,0)→C=(s,s)）
    else:  # case_split: B→C→D。0<d<s: BC上。s<d<2s: CD上。
        if not (0 < d_v < 2 * s_v):
            raise ValueError("case_split は 0<d<2s の範囲であること")
        if d_v < s_v:
            px, py = s_v, d_v
        else:  # CD 上（C=(s,s)→D=(0,s)）
            px, py = s_v - (d_v - s_v), s_v

    area = _shoelace_area([(sympy.Integer(0), sympy.Integer(0)), (s_v, sympy.Integer(0)), (px, py)])
    # 面積は量なので、割り切れるなら小数で書く（`2065/2` ではなく `1032.5`）。
    # 座標の表示（`_fmt_scalar`）は分数のままにしておく——放物線上の点は分数で書く。
    disp = fmt_measure(area) if isinstance(area, sympy.Rational) else _fmt_scalar(area)
    srepr = sympy.srepr(area)

    ops = _QMOTION_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _qmotion_display(op, px, py, d_v < s_v),
            narration=_QMOTION_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# graph_table「かく」系（答えは GraphAnswer＝特徴集合。§6.2 V1'）
#
# 直線の「かく」（math.draw_linear_features ほか）と同じ規約:
#   - solver は SVG を描かない（検証可能な特徴と手順だけを返す）
#   - 模範解答図の描画は recipe が visual 層の純ヘルパで行う
# 特徴の srepr には役割を表す記号（Symbol）を先頭に置き、座標が偶然一致しても
# 別の特徴として区別できるようにする（_answers_match は srepr 集合で比較するため）。
# ---------------------------------------------------------------------------
_ROLE_VERTEX = sympy.Symbol("vertex")
_ROLE_ON_CURVE = sympy.Symbol("on_curve")
_ROLE_NARROWER = sympy.Symbol("narrower")
_ROLE_ENDPOINT = sympy.Symbol("endpoint")
_ROLE_Y_RANGE = sympy.Symbol("y_range")
_ROLE_INTERSECTION = sympy.Symbol("intersection")


def _vertex_feature() -> "Feature":
    return Feature(
        kind="vertex",
        srepr=sympy.srepr(sympy.Tuple(_ROLE_VERTEX, sympy.Integer(0), sympy.Integer(0))),
        display="頂点は原点",
    )


def _curve_point_feature(a: sympy.Expr, x: sympy.Expr) -> "Feature":
    """曲線 y=ax² 上の点（比例定数も srepr に含めるので、どの曲線の点かまで検証できる）。"""
    y = a * x**2
    return Feature(
        kind="curve_point",
        srepr=sympy.srepr(sympy.Tuple(_ROLE_ON_CURVE, a, x, y)),
        display=f"({_fmt_scalar(x)}, {_fmt_scalar(y)})",
    )


def _int_range(x_lo: sympy.Expr, x_hi: sympy.Expr) -> list[sympy.Integer]:
    if x_lo >= x_hi:
        raise ValueError("表の x の範囲は x_lo < x_hi であること")
    return [sympy.Integer(v) for v in range(int(x_lo), int(x_hi) + 1)]


@register_solver("math.draw_two_parabolas_features")
def draw_two_parabolas_features(a1: object, a2: object, x_lo: object, x_hi: object) -> Solution:
    """対応表の点をとって放物線を2本かき、開き方を比べる（g3_l33.graph_table Lv2）。

    比例定数 a1・a2（相異・非0）と対応表の x の範囲 [x_lo, x_hi]（整数）だけから、
    採点用の特徴（頂点・各曲線の通過点・開き方がせまいほうの比例定数）を導く。
    「開き方」は |a| が大きいほどせまい（y 軸に近づく）。narration には数字を書かない。
    """
    a1_s, a2_s = sympy.nsimplify(a1), sympy.nsimplify(a2)
    lo, hi = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    if a1_s == 0 or a2_s == 0:
        raise ValueError("比例定数は 0 でないこと")
    if abs(a1_s) == abs(a2_s):
        # a1=a2 は2本が重なる。a1=-a2 は開く向きが逆なだけで開き方の広さが等しく、
        # 「どちらの開き方がせまいか」が一意に決まらない（答えが黙って片方に倒れる退化）。
        raise ValueError("2つの比例定数は絶対値が相異なること（開き方を比べられない）")
    xs = _int_range(lo, hi)

    narrower = a1_s if abs(a1_s) > abs(a2_s) else a2_s
    features = [_vertex_feature()]
    for a in (a1_s, a2_s):
        features.extend(_curve_point_feature(a, x) for x in xs)
    features.append(
        Feature(
            kind="narrower_curve",
            srepr=sympy.srepr(sympy.Tuple(_ROLE_NARROWER, narrower)),
            display=f"開き方がせまいのは比例定数が {_fmt_scalar(narrower)} のほう",
        )
    )

    ops = [
        "build_correspondence_table",
        "plot_table_points",
        "draw_first_parabola",
        "draw_second_parabola",
        "compare_opening",
    ]
    narration = {
        "build_correspondence_table": "表の x の値を式に代入して、対応する y の値を求める。",
        "plot_table_points": "求めた x と y の組を座標とみて、方眼上に点をとる。",
        "draw_first_parabola": "とった点をなめらかな曲線で結び、放物線をかく。",
        "draw_second_parabola": "もう一方の式についても同じように点をとり、放物線をかく。",
        "compare_opening": "比例定数の絶対値が大きいほど開き方はせまいことから、2本を比べる。",
    }
    # 括弧には**求めた組・かいた曲線の式**を入れる（面③）。
    phrase = {
        "build_correspondence_table": "、".join(
            f"({_fmt_scalar(x)}, {_fmt_scalar(a1_s * x**2)})" for x in xs
        ),
        "plot_table_points": f"{len(xs)}個の点",
        "draw_first_parabola": f"y = {fmt_expr(a1_s * _X**2)}",
        "draw_second_parabola": f"y = {fmt_expr(a2_s * _X**2)}",
    }
    disp = f"開き方がせまいのは比例定数が {_fmt_scalar(narrower)} のほう"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(_ROLE_NARROWER, narrower)) if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


@register_solver("math.draw_parabola_domain_features")
def draw_parabola_domain_features(a: object, x_lo: object, x_hi: object) -> Solution:
    """放物線をかき、x の変域に対応する部分と y の変域を示す（g3_l34.graph_table Lv2）。

    比例定数 a（非0）と x の変域 [x_lo, x_hi] だけから、変域の両端に対応する曲線上の点と
    y の変域を導く。y の変域は、変域が頂点（原点）をまたぐときだけ頂点の y 値 0 を
    候補に加えて決める（find_value 側 math.y_range_over_quadratic_domain と同じ規則）。
    """
    a_s = sympy.nsimplify(a)
    lo, hi = sympy.nsimplify(x_lo), sympy.nsimplify(x_hi)
    if a_s == 0:
        raise ValueError("比例定数は 0 でないこと")
    if lo >= hi:
        raise ValueError("x の変域は x_lo < x_hi であること")

    y1, y2 = a_s * lo**2, a_s * hi**2
    candidates = [y1, y2]
    if lo < 0 < hi:
        candidates.append(sympy.Integer(0))  # 頂点 (0,0) の y 値
    y_min, y_max = sympy.Min(*candidates), sympy.Max(*candidates)

    features = [
        Feature(
            kind="arc_endpoint",
            srepr=sympy.srepr(sympy.Tuple(_ROLE_ENDPOINT, lo, y1)),
            display=f"変域の左端に対応する点 ({_fmt_scalar(lo)}, {_fmt_scalar(y1)})",
        ),
        Feature(
            kind="arc_endpoint",
            srepr=sympy.srepr(sympy.Tuple(_ROLE_ENDPOINT, hi, y2)),
            display=f"変域の右端に対応する点 ({_fmt_scalar(hi)}, {_fmt_scalar(y2)})",
        ),
        Feature(
            kind="y_range",
            srepr=sympy.srepr(sympy.Tuple(_ROLE_Y_RANGE, y_min, y_max)),
            display=f"{_fmt_scalar(y_min)} ≦ y ≦ {_fmt_scalar(y_max)}",
        ),
    ]

    ops = ["draw_parabola", "mark_domain_endpoints", "trace_domain_part", "read_y_range"]
    narration = {
        "draw_parabola": "式にしたがって、放物線を座標平面にかく。",
        "mark_domain_endpoints": "x の変域の両端に対応する曲線上の点をとる。",
        "trace_domain_part": "その両端にはさまれた部分の曲線を、太くなぞって示す。",
        "read_y_range": "なぞった部分の最も低いところと最も高いところから、y の変域を読み取る。",
    }
    phrase = {
        "draw_parabola": f"y = {fmt_expr(a_s * _X**2)}",
        "mark_domain_endpoints": (
            f"({_fmt_scalar(lo)}, {_fmt_scalar(y1)})、({_fmt_scalar(hi)}, {_fmt_scalar(y2)})"
        ),
        "trace_domain_part": f"{_fmt_scalar(lo)} ≦ x ≦ {_fmt_scalar(hi)} の部分",
    }
    disp = f"{_fmt_scalar(y_min)} ≦ y ≦ {_fmt_scalar(y_max)}"
    srepr = sympy.srepr(sympy.Tuple(_ROLE_Y_RANGE, y_min, y_max))
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


@register_solver("math.draw_parabola_line_features")
def draw_parabola_line_features(a: object, m: object, b: object) -> Solution:
    """放物線と直線を同じ座標軸にかき、囲まれた部分を示す（g3_l37.graph_table Lv2）。

    囲まれた部分の境界は2つの交点で定まるので、答えは交点2つの特徴集合とする。
    交点そのものは find_value 側と共有の `_parabola_line_intersections`（連立方程式を
    解く）で求める＝新しい数学ロジックは足していない。
    """
    a_s, m_s, b_s = sympy.nsimplify(a), sympy.nsimplify(m), sympy.nsimplify(b)
    roots = _parabola_line_intersections(a_s, m_s, b_s)
    if len(roots) != 2:
        raise ValueError(f"交点がちょうど2つでない: {roots}")
    features = [
        Feature(
            kind="intersection",
            srepr=sympy.srepr(sympy.Tuple(_ROLE_INTERSECTION, r, a_s * r**2)),
            display=f"交点 ({_fmt_scalar(r)}, {_fmt_scalar(a_s * r**2)})",
        )
        for r in roots
    ]

    ops = ["draw_parabola", "draw_line", "mark_intersections", "shade_enclosed_region"]
    narration = {
        "draw_parabola": "放物線の式にしたがって、曲線を座標平面にかく。",
        "draw_line": "直線の式にしたがって、同じ座標軸に直線をかく。",
        "mark_intersections": "放物線と直線の式を連立させて解き、交点をとる。",
        "shade_enclosed_region": "2つの交点にはさまれた、曲線と直線で囲まれた部分に斜線をひく。",
    }
    # 括弧には**かいたもの・とった点**を入れる（面③）。
    phrase = {
        "draw_parabola": f"y = {fmt_expr(a_s * _X**2)}",
        "draw_line": f"y = {fmt_expr(m_s * _X + b_s)}",
        "mark_intersections": "、".join(
            f"({_fmt_scalar(r)}, {_fmt_scalar(a_s * r**2)})" for r in roots
        ),
    }
    disp = "、".join(f"({_fmt_scalar(r)}, {_fmt_scalar(a_s * r**2)})" for r in roots)
    srepr = sympy.srepr(sympy.Tuple(*(sympy.Tuple(r, a_s * r**2) for r in roots)))
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=f"囲まれた部分の境界は2つの交点 {disp}" if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


@register_solver("math.draw_quantity_curve_features")
def draw_quantity_curve_features(a: object, x_values: object) -> Solution:
    """表の値を座標にとって、2乗に比例する現象のグラフをかく（g3_l36.graph_table Lv2）。

    比例定数 a（正）と表に載っている x の値の並びだけから、とるべき点を導く。
    x も y も 0 以上の量（第1象限の量-量グラフ）なので、点は表の各行に対応する。
    """
    a_s = sympy.nsimplify(a)
    if a_s <= 0:
        raise ValueError("現象の比例定数は正であること（第1象限の量-量グラフ）")
    xs = [sympy.nsimplify(v) for v in cast("list[object]", x_values)]
    if len(xs) < 2:
        raise ValueError("表には 2 行以上の値が必要")
    if any(v < 0 for v in xs):
        raise ValueError("x の値は 0 以上であること")
    if len(set(xs)) != len(xs):
        raise ValueError("表の x の値は相異なること")

    features = [_curve_point_feature(a_s, x) for x in xs]

    ops = ["read_table_values", "plot_table_points", "draw_smooth_curve"]
    narration = {
        "read_table_values": "表に並んだ x の値と、それに対応する y の値の組を読み取る。",
        "plot_table_points": "読み取った組を座標とみて、方眼上に点をとる。",
        "draw_smooth_curve": "とった点をなめらかな曲線で結び、変化のようすを表す。",
    }
    phrase = {
        "read_table_values": "、".join(
            f"({_fmt_scalar(x)}, {_fmt_scalar(a_s * x**2)})" for x in xs
        ),
        "plot_table_points": f"{len(xs)}個の点",
    }
    last = features[-1]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=last.srepr if i == len(ops) - 1 else "",
            result_display="とった点をなめらかに結んだ曲線" if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


__all__ = [
    "evaluate_quadratic_function",
    "y_range_over_quadratic_domain",
    "rate_of_change_quadratic",
    "intersection_parabola_line",
    "parabola_coefficient_from_intersection",
    "parabola_equal_area_point",
    "parabola_line_area_ratio",
    "solve_quadratic_motion_area",
    "draw_two_parabolas_features",
    "draw_parabola_domain_features",
    "draw_parabola_line_features",
    "draw_quantity_curve_features",
]
