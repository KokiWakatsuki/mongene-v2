"""動点（正方形の辺上を動く点）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（正方形の1辺 s・速さ v・経過時間 t・mode）から答えと
steps を導く。純粋・決定論・厳密（sympy.Rational）演算であること。乱数は引かない。

C3（g3_l31.find_value・2次方程式の利用「動点」）クラスタ。visual は不要（座標幾何の
数式のみで完結・図なしで解ける設計）。正方形を A=(0,0), B=(s,0), C=(s,s), D=(0,s) に
固定し、点 P の位置を経過距離 d=v·t の区分（どの辺上にあるか）で決める。三角形 APD の
面積は shoelace 公式（三角形の面積を頂点座標だけから求める公式）で計算する。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_MOTION_STEPS: dict[str, list[str]] = {
    # g3_l31.find_value Lv2: 点 P が辺 AB 上（1区間）にあるときの面積
    "single_segment": ["locate_point_p", "compute_triangle_area"],
    # g3_l31.find_value Lv3: 点 P が A→B→C の2区間目（辺 BC 上）にあるときの面積
    "two_segment": ["determine_which_segment", "locate_point_p", "compute_triangle_area"],
}

_MOTION_OP_NARRATION: dict[str, str] = {
    "locate_point_p": "経過した時間と速さから、点 P が動いた道のりを求め、その位置の座標を決める。",
    "compute_triangle_area": "3点の座標から、三角形の面積を求める公式で面積を計算する。",
    "determine_which_segment": "点 P が動いた道のりから、今どの辺の上にいるかを判断する。",
}

_MOTION_OP_PHRASE: dict[str, str] = {
    "locate_point_p": "点 P の座標を決める",
    "determine_which_segment": "どの辺の上にいるかを判断する",
}


def _shoelace_triangle_area(
    ax: sympy.Rational, ay: sympy.Rational,
    px: sympy.Rational, py: sympy.Rational,
    dx: sympy.Rational, dy: sympy.Rational,
) -> sympy.Rational:
    """3点 A,P,D の座標から三角形の面積を shoelace 公式で求める（符号なし・厳密値）。"""
    return sympy.Rational(1, 2) * sympy.Abs(
        ax * (py - dy) + px * (dy - ay) + dx * (ay - py)
    )


@register_solver("math.solve_moving_point_area")
def solve_moving_point_area(s: object, v: object, t: object, mode: object) -> Solution:
    """正方形の辺上を動く点 P による三角形 APD の面積を求める（C3 g3_l31.find_value）。

    正方形の1辺 s・速さ v・経過時間 t・mode だけから答えを導く（recipe の構成内訳は
    見ない・double-solve）。A=(0,0), B=(s,0), C=(s,s), D=(0,s) に固定し、
    d=v·t（点 P が動いた道のり）の区間（mode）に応じて P の座標を決め、shoelace 公式で
    三角形 APD の面積を計算する。mode ごとに steps の op 列を変える＝level_sep。
    """
    mode_s = str(mode)
    if mode_s not in _MOTION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    t_v = sympy.Rational(str(t))
    d = v_v * t_v

    if mode_s == "single_segment":
        px, py = d, sympy.Integer(0)
    else:  # two_segment: 辺 BC 上（B=(s,0) から C=(s,s) 方向）
        px, py = s_v, d - s_v

    area = _shoelace_triangle_area(sympy.Integer(0), sympy.Integer(0), px, py, sympy.Integer(0), s_v)
    disp = str(area)
    srepr = sympy.srepr(area)

    ops = _MOTION_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _MOTION_OP_PHRASE.get(op, ""),
            narration=_MOTION_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = ["solve_moving_point_area"]
