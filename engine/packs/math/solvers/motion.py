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

from engine.core.contracts import Feature, GraphAnswer, Solution, Step, SymbolicAnswer
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


@register_solver("math.draw_piecewise_area_graph_features")
def draw_piecewise_area_graph_features(s: object, v: object) -> Solution:
    """区間ごとに式が変わる面積のグラフ（折れ線）をかく（g3_l38.graph_table Lv3）。

    正方形 A=(0,0), B=(s,0), C=(s,s), D=(0,s) の周上を、点 P が A を出発して A→B→C の
    順に速さ v で動く。三角形 APD の面積 y は
      ・0≦x≦s/v（P は辺 AB 上）: 底辺 AD=s・高さ AP=v·x で y=(s·v/2)x（1次関数）
      ・s/v≦x≦2s/v（P は辺 BC 上）: 底辺 AD=s・高さ AB=s のまま y=s²/2（一定）
    となり、グラフは折れ点 (s/v, s²/2) をもつ折れ線になる。答えは折れ点3つ
    （出発点・折れ点・終点）の特徴集合で、面積の値は既存の `solve_moving_point_area`
    と同じ shoelace 公式（`_shoelace_triangle_area`）で求める＝新しい数学ロジックはゼロ。
    問題パラメータ（s・v）だけから独立に再計算する（double-solve）。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    if s_v <= 0 or v_v <= 0:
        raise ValueError("1辺・速さは正であること")
    t1 = s_v / v_v  # P が B に到達する時刻（辺 AB を渡りきる）
    t2 = 2 * t1  # P が C に到達する時刻

    # 各時刻の面積を shoelace 公式で求める（辺 AB 上 / 辺 BC 上の位置から）。
    def area_at(t: sympy.Rational, on_bc: bool) -> sympy.Rational:
        d = v_v * t
        px, py = (s_v, d - s_v) if on_bc else (d, sympy.Integer(0))
        return _shoelace_triangle_area(
            sympy.Integer(0), sympy.Integer(0), px, py, sympy.Integer(0), s_v
        )

    breakpoints = [
        (sympy.Integer(0), area_at(sympy.Integer(0), False)),
        (t1, area_at(t1, False)),
        (t2, area_at(t2, True)),
    ]
    # 折れ点の面積が、区間ごとの式（1次関数 → 一定）と一致することを確かめる。
    if breakpoints[1][1] != s_v * v_v / 2 * t1 or breakpoints[2][1] != breakpoints[1][1]:
        raise ValueError("区間ごとの式と shoelace 再計算が一致しない")

    features = [
        Feature(
            kind="breakpoint",
            srepr=sympy.srepr(sympy.Tuple(x, y)),
            display=f"({x}, {y})",
        )
        for x, y in breakpoints
    ]

    ops = [
        "identify_intervals",
        "express_area_on_first_interval",
        "express_area_on_second_interval",
        "plot_breakpoints",
        "draw_polyline",
    ]
    narration = {
        "identify_intervals": "動く点がどの辺の上にあるかで、時間を区間に分ける。",
        "express_area_on_first_interval": "はじめの区間では高さが時間に比例するので、面積を時間の1次式で表す。",
        "express_area_on_second_interval": "次の区間では底辺も高さも変わらないので、面積が一定になることを確かめる。",
        "plot_breakpoints": "区間の境目と両端で面積を求め、その組を座標とみて点をとる。",
        "draw_polyline": "とった点を順に線分で結び、区間ごとに式が変わるグラフをかく。",
    }
    phrase = {
        "identify_intervals": "時間を区間に分ける",
        "express_area_on_first_interval": "はじめの区間の式をつくる",
        "express_area_on_second_interval": "次の区間の式をつくる",
        "plot_breakpoints": "区間の境目の点をとる",
    }
    srepr = sympy.srepr(sympy.Tuple(*(sympy.Tuple(x, y) for x, y in breakpoints)))
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display="区間の境目を折れ点とする折れ線" if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


__all__ = ["solve_moving_point_area", "draw_piecewise_area_graph_features"]
