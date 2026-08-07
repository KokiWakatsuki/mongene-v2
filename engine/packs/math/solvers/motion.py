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


# ---------------------------------------------------------------------------
# g3_l31.word_problem Lv3: 2点 P・Q が直交する2辺を同時に動く（面積が x の2次式）
#
# 三角形 APD（P だけが動く）は面積が時間の**1次式**にしかならない。2次方程式の利用
# として成立させるには、底辺と高さの**両方**が時間とともに伸びる形が要る。そこで
# 台帳 example どおり P は辺 AB 上、Q は辺 AD 上を同時に動かし、直角をはさむ2辺が
# ともに v·x になる三角形 APQ を使う（面積 = (v²/2)x²）。
# ---------------------------------------------------------------------------
_X = sympy.Symbol("x")


def _pq_area_expr(v: sympy.Rational) -> sympy.Expr:
    """三角形 APQ の面積を x の式で表す。AP=AQ=v·x・その間の角が直角。"""
    return sympy.Rational(1, 2) * (v * _X) * (v * _X)


@register_solver("math.express_moving_points_area")
def express_moving_points_area(v: object) -> Solution:
    """点 P・Q が直交2辺を速さ v で動くときの三角形 APQ の面積を x の式で表す。

    問題パラメータ（速さ v）だけから導く。正方形の1辺 s は**式に現れない**
    （P・Q が辺の上にある間の話なので、面積は s に依存しない）ため受け取らない。
    """
    v_v = sympy.Rational(str(v))
    if v_v <= 0:
        raise ValueError("速さは正であること")
    expr = sympy.expand(_pq_area_expr(v_v))
    # 表示は既存の y=ax² セル（word_problem_quadratic_function._quadratic_display）と
    # 同じ規約: 分数の係数はかっこでくくって係数の範囲を確定させる。
    a = sympy.Rational(v_v**2, 2)
    a_disp = f"{a}" if a.q == 1 else f"({a})"

    ops = ["locate_points_pq", "express_area_in_x"]
    narration = {
        "locate_points_pq": "経過した時間と速さから、点 P と点 Q が動いた道のりを、それぞれ x を使って表す。",
        "express_area_in_x": "直角をはさむ二辺の長さがわかったので、三角形の面積を x の式で表す。",
    }
    srepr = sympy.srepr(expr)
    disp = "y = x²" if a == 1 else f"y = {a_disp}x²"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else "点 P と点 Q の位置を x で表す",
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.solve_moving_points_area_time")
def solve_moving_points_area_time(v: object, area: object) -> Solution:
    """三角形 APQ の面積が与えられた値になる時刻を、2次方程式を解いて求める。

    (v²/2)x² = area を解く。負の解は時間として意味を持たないので捨てる
    ＝「解いてから場面に照らして吟味する」ところまでが答え。
    """
    v_v = sympy.Rational(str(v))
    area_v = sympy.Rational(str(area))
    if v_v <= 0 or area_v <= 0:
        raise ValueError("速さ・面積は正であること")
    roots = sympy.solve(sympy.Eq(_pq_area_expr(v_v), area_v), _X)
    positive = [r for r in roots if r.is_positive]
    if len(positive) != 1:
        raise ValueError(f"正の解がちょうど1つにならない: {roots}")
    t = sympy.nsimplify(positive[0])

    ops = ["set_up_quadratic_equation", "solve_quadratic_equation"]
    narration = {
        "set_up_quadratic_equation": "面積を x で表した式が、与えられた面積に等しいとおいて方程式をつくる。",
        "solve_quadratic_equation": "方程式を解き、負の解は時間として意味を持たないので捨てる。",
    }
    srepr = sympy.srepr(t)
    disp = f"{sympy.sstr(t)}秒後"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else "面積についての方程式をつくる",
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# g3_l31.word_problem Lv4: 3辺を渡る動点・面積が与えられた値になる時刻をすべて求める
#
# 【台帳 example との差と、その判断】example は「A→B→C の順に動く」だが、この経路だと
# 三角形 APD の面積は 辺AB上で増加 → 辺BC上で一定 の2区間しかなく、与えられた面積に
# なる時刻は**必ず1つ**になる。つまり「場合分けをしてもしなくても答えが変わらない」＝
# ゲートが素通りする退化そのもの（BRIEF「ゲートは答えが潰れる退化を素通りする」）。
# そこで経路を A→B→C→D に延ばす。辺CD上では面積が減少に転じるので、同じ面積になる
# 時刻が**2つ**あり、「すべて求めよ」が意味を持ち、第3区間を見落とすと答えを落とす。
# desc の「場合分け(位置による式変化)を含め方針を構成」はこの形で満たす。
# なお g2_l29.word_problem Lv4 の台帳 example も A→B→C→D の経路である。
# ---------------------------------------------------------------------------
_ALL_TIMES_OPS = [
    "identify_intervals",
    "solve_on_increasing_interval",
    "check_constant_interval",
    "solve_on_decreasing_interval",
    "collect_all_times",
]

_ALL_TIMES_NARRATION: dict[str, str] = {
    "identify_intervals": "点 P がどの辺の上にあるかで時間を区間に分け、区間ごとに面積の式が変わることを確かめる。",
    "solve_on_increasing_interval": "はじめの辺の上では高さが時間に比例するので、面積の式を方程式とみて解く。",
    "check_constant_interval": "次の辺の上では底辺も高さも変わらず面積が一定なので、その値と比べて解があるかを調べる。",
    "solve_on_decreasing_interval": "最後の辺の上では高さが減っていくので、その区間の式を方程式とみて解く。",
    "collect_all_times": "求めた時刻がそれぞれの区間の中にあることを確かめ、答えをすべて並べる。",
}

_ALL_TIMES_PHRASE: dict[str, str] = {
    "identify_intervals": "時間を区間に分ける",
    "solve_on_increasing_interval": "増えていく区間で解く",
    "check_constant_interval": "一定の区間に解が無いことを確かめる",
    "solve_on_decreasing_interval": "減っていく区間で解く",
}


@register_solver("math.solve_moving_point_area_all_times")
def solve_moving_point_area_all_times(s: object, v: object, area: object) -> Solution:
    """三角形 APD の面積が与えられた値になる時刻をすべて求める（g3_l31.word_problem Lv4）。

    正方形 A=(0,0), B=(s,0), C=(s,s), D=(0,s) の周上を、点 P が A を出発して
    A→B→C→D の順に速さ v で動く。区間ごとに P の座標を決め、面積は既存の
    shoelace 公式（`_shoelace_triangle_area`）で求める＝新しい幾何ロジックは足さない。
    問題パラメータ（s・v・面積）だけから独立に再計算する（double-solve）。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    area_v = sympy.Rational(str(area))
    if s_v <= 0 or v_v <= 0 or area_v <= 0:
        raise ValueError("1辺・速さ・面積は正であること")

    def _p_at(t: sympy.Rational) -> tuple[sympy.Rational, sympy.Rational]:
        """時刻 t における点 P の座標（辺 AB → BC → CD の順に渡る）。"""
        d = v_v * t
        if d <= s_v:
            return d, sympy.Integer(0)
        if d <= 2 * s_v:
            return s_v, d - s_v
        return 3 * s_v - d, s_v

    def _area_at(t: sympy.Rational) -> sympy.Rational:
        px, py = _p_at(t)
        return _shoelace_triangle_area(
            sympy.Integer(0), sympy.Integer(0), px, py, sympy.Integer(0), s_v
        )

    # 辺AB上: y = (s·v/2)t（増加）／辺BC上: y = s²/2（一定）／辺CD上: y = (s/2)(3s - v·t)（減少）
    t_first = 2 * area_v / (s_v * v_v)
    t_third = (3 * s_v - 2 * area_v / s_v) / v_v
    if not (0 < t_first < s_v / v_v):
        raise ValueError(f"はじめの区間に解が無い: t={t_first}")
    if not (2 * s_v / v_v < t_third <= 3 * s_v / v_v):
        raise ValueError(f"最後の区間に解が無い: t={t_third}")
    if area_v >= s_v**2 / 2:
        raise ValueError("一定区間の面積以上なので、増減する区間に解が立たない")
    # 恒真: 求めた時刻を shoelace 公式に戻すと与えられた面積に一致する。
    for t in (t_first, t_third):
        if not (_area_at(t) - area_v).equals(0):
            raise ValueError(f"再計算が一致しない: t={t}")

    times = sympy.Tuple(sympy.nsimplify(t_first), sympy.nsimplify(t_third))
    srepr = sympy.srepr(times)
    disp = "、".join(f"{sympy.sstr(t)}秒後" for t in times)
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(_ALL_TIMES_OPS) - 1 else "",
            result_display=disp if i == len(_ALL_TIMES_OPS) - 1 else _ALL_TIMES_PHRASE[op],
            narration=_ALL_TIMES_NARRATION[op],
        )
        for i, op in enumerate(_ALL_TIMES_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.draw_three_interval_area_graph_features")
def draw_three_interval_area_graph_features(s: object, v: object) -> Solution:
    """3辺を渡る動点の面積グラフ（増加→一定→減少の折れ線）をかく（g3_l38.word_problem Lv4）。

    A→B→C→D の経路なので折れ点は4つ:
      (0, 0) → (s/v, s²/2) → (2s/v, s²/2) → (3s/v, 0)
    既存の 2 区間版（`draw_piecewise_area_graph_features`・A→B→C）の素直な延長で、
    面積はいずれも同じ shoelace 公式（`_shoelace_triangle_area`）で求める
    ＝新しい幾何ロジックは足さない。問題パラメータ（s・v）だけから再計算する。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    if s_v <= 0 or v_v <= 0:
        raise ValueError("1辺・速さは正であること")
    t1 = s_v / v_v
    times = [sympy.Integer(0), t1, 2 * t1, 3 * t1]

    def _area_at(t: sympy.Rational) -> sympy.Rational:
        d = v_v * t
        if d <= s_v:
            px, py = d, sympy.Integer(0)
        elif d <= 2 * s_v:
            px, py = s_v, d - s_v
        else:
            px, py = 3 * s_v - d, s_v
        return _shoelace_triangle_area(
            sympy.Integer(0), sympy.Integer(0), px, py, sympy.Integer(0), s_v
        )

    breakpoints = [(t, _area_at(t)) for t in times]
    peak = s_v**2 / 2
    # 区間ごとの式（増加 → 一定 → 減少）と shoelace 再計算が一致することを確かめる。
    expected = [sympy.Integer(0), peak, peak, sympy.Integer(0)]
    if any(not (b - e).equals(0) for (_t, b), e in zip(breakpoints, expected, strict=True)):
        raise ValueError("区間ごとの式と shoelace 再計算が一致しない")

    features = [
        Feature(kind="breakpoint", srepr=sympy.srepr(sympy.Tuple(x, y)), display=f"({x}, {y})")
        for x, y in breakpoints
    ]
    ops = [
        "identify_intervals",
        "express_area_on_increasing_interval",
        "express_area_on_constant_interval",
        "express_area_on_decreasing_interval",
        "plot_breakpoints",
        "draw_polyline",
    ]
    narration = {
        "identify_intervals": "動く点がどの辺の上にあるかで、時間を区間に分ける。",
        "express_area_on_increasing_interval": "はじめの区間では高さが時間に比例するので、面積を時間の1次式で表す。",
        "express_area_on_constant_interval": "次の区間では底辺も高さも変わらないので、面積が一定になることを確かめる。",
        "express_area_on_decreasing_interval": "最後の区間では高さが減っていくので、面積を時間の1次式で表す。",
        "plot_breakpoints": "区間の境目と両端で面積を求め、その組を座標とみて点をとる。",
        "draw_polyline": "とった点を順に線分で結び、区間ごとに式が変わるグラフをかく。",
    }
    phrase = {
        "identify_intervals": "時間を区間に分ける",
        "express_area_on_increasing_interval": "増えていく区間の式をつくる",
        "express_area_on_constant_interval": "一定の区間であることを確かめる",
        "express_area_on_decreasing_interval": "減っていく区間の式をつくる",
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


__all__ = [
    "solve_moving_point_area",
    "draw_piecewise_area_graph_features",
    "draw_three_interval_area_graph_features",
    "express_moving_points_area",
    "solve_moving_points_area_time",
    "solve_moving_point_area_all_times",
]
