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

def _motion_step_display(op: str, lp: str, px, py, on_ab: bool) -> str:
    """動点の手の括弧（この手で得た位置）。指示の言い直しは置かない（面③）。"""
    if op == "locate_point_p":
        return f"{lp}({sympy.sstr(px)}, {sympy.sstr(py)})"
    if op == "determine_which_segment":
        return "はじめの辺の上" if on_ab else "次の辺の上"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


def _label(labels: object, index: int, default: str) -> str:
    """点名の1文字（`labels` は recipe が引いた頂点名を並べた文字列）。

    **問題文の点名は recipe が引く**ので、solver がここを固定にすると
    「点Jが動く」と問うて「点 P がどの辺の上にあるか」と解説することになる
    （実際そうなっていた）。recipe から受け取り、無ければ既定を使う。
    """
    s = str(labels or "")
    return s[index] if len(s) > index else default


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
            result_display=disp if i == len(ops) - 1
            else _motion_step_display(op, _label(None, 4, "P"), px, py, mode_s == "single_segment"),
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
    # 括弧には**その手で得た区間・式・点**を入れる（面③）。
    phrase = {
        "identify_intervals": f"0〜{sympy.sstr(t1)}秒、{sympy.sstr(t1)}〜{sympy.sstr(t2)}秒",
        "express_area_on_first_interval": _linear_area_display(s_v * v_v / 2),
        "express_area_on_second_interval": _linear_area_display(
            sympy.Integer(0), s_v**2 / 2
        ),
        "plot_breakpoints": "、".join(f"({x}, {y})" for x, y in breakpoints),
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
def express_moving_points_area(v: object, labels: object = None) -> Solution:
    """点 P・Q が直交2辺を速さ v で動くときの三角形 APQ の面積を x の式で表す。

    問題パラメータ（速さ v）だけから導く。正方形の1辺 s は**式に現れない**
    （P・Q が辺の上にある間の話なので、面積は s に依存しない）ため受け取らない。
    `labels` は問題文の点名（A,B,C,D,P,Q の順）で、解説の点名を問題文に合わせる
    ためだけに使う（計算には効かない）。
    """
    lp = _label(labels, 4, "P")
    lq = _label(labels, 5, "Q")
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
        "locate_points_pq": f"経過した時間と速さから、点{lp}と点{lq}が動いた道のりを、それぞれ x を使って表す。",
        "express_area_in_x": "直角をはさむ二辺の長さがわかったので、三角形の面積を x の式で表す。",
    }
    srepr = sympy.srepr(expr)
    disp = "y = x²" if a == 1 else f"y = {a_disp}x²"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else f"点{lp}と点{lq}の位置を x で表す",
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
            result_display=disp if i == len(ops) - 1
            else f"{_linear_area_display(sympy.Rational(v_v**2, 2))[4:]} = {sympy.sstr(area_v)}",
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

def _all_times_narration(lp: str) -> dict[str, str]:
    """解く筋道の言葉。動く点の名前だけ問題文に合わせる（それ以外は固定）。"""
    return {
        "identify_intervals": f"点{lp}がどの辺の上にあるかで時間を区間に分け、区間ごとに面積の式が変わることを確かめる。",
        "solve_on_increasing_interval": "はじめの辺の上では高さが時間に比例するので、面積の式を方程式とみて解く。",
        "check_constant_interval": "次の辺の上では底辺も高さも変わらず面積が一定なので、その値と比べて解があるかを調べる。",
        "solve_on_decreasing_interval": "最後の辺の上では高さが減っていくので、その区間の式を方程式とみて解く。",
        "collect_all_times": "求めた時刻がそれぞれの区間の中にあることを確かめ、答えをすべて並べる。",
    }


def _all_times_display(op: str, t1, t2, t3, const_area, t_first, t_third) -> str:
    """時刻をすべて求める手の括弧（この手で得た区切り・値）。"""
    if op == "identify_intervals":
        return (f"0〜{sympy.sstr(t1)}秒、{sympy.sstr(t1)}〜{sympy.sstr(t2)}秒、"
                f"{sympy.sstr(t2)}〜{sympy.sstr(t3)}秒")
    if op == "solve_on_increasing_interval":
        return f"{sympy.sstr(t_first)}秒後"
    if op == "check_constant_interval":
        return f"面積は {sympy.sstr(const_area)} のままなので解なし"
    if op == "solve_on_decreasing_interval":
        return f"{sympy.sstr(t_third)}秒後"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.solve_moving_point_area_all_times")
def solve_moving_point_area_all_times(
    s: object, v: object, area: object, labels: object = None
) -> Solution:
    """三角形 APD の面積が与えられた値になる時刻をすべて求める（g3_l31.word_problem Lv4）。

    正方形 A=(0,0), B=(s,0), C=(s,s), D=(0,s) の周上を、点 P が A を出発して
    A→B→C→D の順に速さ v で動く。区間ごとに P の座標を決め、面積は既存の
    shoelace 公式（`_shoelace_triangle_area`）で求める＝新しい幾何ロジックは足さない。
    問題パラメータ（s・v・面積）だけから独立に再計算する（double-solve）。
    `labels` は問題文の点名（A,B,C,D,P の順）で、解説の点名を問題文に合わせる
    ためだけに使う（計算には効かない）。
    """
    narration = _all_times_narration(_label(labels, 4, "P"))
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
            result_display=disp if i == len(_ALL_TIMES_OPS) - 1
            else _all_times_display(
                op, s_v / v_v, 2 * s_v / v_v, 3 * s_v / v_v,
                s_v**2 / 2, sympy.nsimplify(t_first), sympy.nsimplify(t_third),
            ),
            narration=narration[op],
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
    # 括弧には**その手で得た区間・式・点**を入れる（面③）。
    phrase = {
        "identify_intervals": (
            f"0〜{sympy.sstr(t1)}秒、{sympy.sstr(t1)}〜{sympy.sstr(2 * t1)}秒、"
            f"{sympy.sstr(2 * t1)}〜{sympy.sstr(3 * t1)}秒"
        ),
        "express_area_on_increasing_interval": _linear_area_display(s_v * v_v / 2),
        "express_area_on_constant_interval": _linear_area_display(
            sympy.Integer(0), s_v**2 / 2
        ),
        "express_area_on_decreasing_interval": _linear_area_display(
            -s_v * v_v / 2, 3 * s_v**2 / 2
        ),
        "plot_breakpoints": "、".join(f"({x}, {y})" for x, y in breakpoints),
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
# 面積を時間の式で表す（g2_l29.word_problem Lv3/Lv4・g1_l36.word_problem Lv4）
#
# 底辺が正方形の1辺で固定・高さが v·x で伸びる区間では、面積は x の1次式 y=(s·v/2)x。
# 3辺を渡る場合は 増加 → 一定 → 減少 の3本に分かれる。値はいずれも既存の
# shoelace 公式（`_shoelace_triangle_area`）で裏取りする＝新しい幾何ロジックは足さない。
# ---------------------------------------------------------------------------
def _coeff_display(coeff: sympy.Rational) -> str:
    """x の係数の表示（分数はかっこでくくって係数の範囲を確定させる）。"""
    if coeff == 1:
        return ""
    if coeff == -1:
        return "-"
    return f"{coeff}" if coeff.q == 1 else f"({coeff})"


def _linear_area_display(coeff: sympy.Rational, const: sympy.Rational | None = None) -> str:
    """y = ax + b の表示（`*` を書かない教科書表記に揃える）。"""
    term = f"{_coeff_display(coeff)}x" if coeff != 0 else ""
    c = sympy.Integer(0) if const is None else const
    if coeff == 0:
        return f"y = {c}"
    if c == 0:
        return f"y = {term}"
    sign = "+" if c > 0 else "-"
    return f"y = {term} {sign} {abs(c)}"


@register_solver("math.express_single_interval_area")
def express_single_interval_area(s: object, v: object) -> Solution:
    """動点がつくる三角形の面積を、1区間ぶんの x の式で表す（g2_l29.word_problem Lv3）。

    底辺は正方形の1辺 s で固定、高さは v·x なので y=(s·v/2)x。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    if s_v <= 0 or v_v <= 0:
        raise ValueError("1辺・速さは正であること")
    coeff = sympy.Rational(s_v * v_v, 2)
    expr = coeff * _X
    # 恒真: 区間の右端（P が向かいの頂点に着く時刻）で shoelace 再計算と一致する。
    t_end = s_v / v_v
    geom = _shoelace_triangle_area(
        sympy.Integer(0), sympy.Integer(0), v_v * t_end, sympy.Integer(0),
        sympy.Integer(0), s_v,
    )
    if not (expr.subs(_X, t_end) - geom).equals(0):
        raise ValueError("面積の式と shoelace 再計算が一致しない")

    ops = ["locate_point_p", "express_area_in_x"]
    narration = {
        "locate_point_p": "経過した時間と速さから、動く点が進んだ道のりを x を使って表す。",
        "express_area_in_x": "底辺は正方形の一辺で変わらず、高さが進んだ道のりなので、面積を x の式で表す。",
    }
    srepr = sympy.srepr(expr)
    disp = _linear_area_display(coeff)
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else "動く点の位置を x で表す",
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.express_three_interval_area_exprs")
def express_three_interval_area_exprs(s: object, v: object) -> Solution:
    """3辺を渡る動点の面積を、区間ごとの式で表す（g2_l29.word_problem Lv4）。

    A→B→C→D の経路で、面積は
      0≦x≦s/v   … y=(s·v/2)x（増加）
      s/v≦x≦2s/v … y=s²/2（一定）
      2s/v≦x≦3s/v … y=(s/2)(3s−v·x)（減少）
    の3本。答えは3本の式の組で、区間の境目も含めて再計算で裏取りする。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    if s_v <= 0 or v_v <= 0:
        raise ValueError("1辺・速さは正であること")
    t1 = s_v / v_v
    rise = sympy.Rational(s_v * v_v, 2) * _X
    flat = sympy.Rational(s_v**2, 2)
    fall = sympy.expand(sympy.Rational(s_v, 2) * (3 * s_v - v_v * _X))
    # 恒真: 区間の境目で隣り合う式の値が一致する（折れ線がつながる）。
    if not (rise.subs(_X, t1) - flat).equals(0) or not (fall.subs(_X, 2 * t1) - flat).equals(0):
        raise ValueError("区間の境目で式の値がつながらない")
    if not (fall.subs(_X, 3 * t1)).equals(0):
        raise ValueError("最後の区間の終わりで面積がゼロにならない")

    exprs = sympy.Tuple(rise, flat, fall)
    ops = [
        "identify_intervals",
        "express_area_on_increasing_interval",
        "express_area_on_constant_interval",
        "express_area_on_decreasing_interval",
    ]
    narration = {
        "identify_intervals": "動く点がどの辺の上にあるかで、時間を区間に分ける。",
        "express_area_on_increasing_interval": "はじめの区間では高さが時間に比例するので、面積を x の1次式で表す。",
        "express_area_on_constant_interval": "次の区間では底辺も高さも変わらないので、面積が一定になることを確かめる。",
        "express_area_on_decreasing_interval": "最後の区間では高さが減っていくので、面積を x の1次式で表す。",
    }
    # 括弧には**その手で得た区間・式**を入れる（面③）。
    phrase = {
        "identify_intervals": (
            f"0〜{sympy.sstr(t1)}秒、{sympy.sstr(t1)}〜{sympy.sstr(2 * t1)}秒、"
            f"{sympy.sstr(2 * t1)}〜{sympy.sstr(3 * t1)}秒"
        ),
        "express_area_on_increasing_interval": _linear_area_display(
            sympy.Rational(s_v * v_v, 2)
        ),
        "express_area_on_constant_interval": f"y = {sympy.sstr(flat)}",
    }
    srepr = sympy.srepr(exprs)
    disp = "、".join(
        [
            f"0≦x≦{sympy.sstr(t1)} のとき {_linear_area_display(sympy.Rational(s_v * v_v, 2))}",
            f"{sympy.sstr(t1)}≦x≦{sympy.sstr(2 * t1)} のとき y = {sympy.sstr(flat)}",
            f"{sympy.sstr(2 * t1)}≦x≦{sympy.sstr(3 * t1)} のとき "
            f"{_linear_area_display(-sympy.Rational(s_v * v_v, 2), sympy.Rational(3 * s_v**2, 2))}",
        ]
    )
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.max_area_and_times")
def max_area_and_times(s: object, v: object, area: object) -> Solution:
    """面積が最大になる時間の範囲と、指定の面積になる時刻を求める（g1_l36.word_problem Lv4）。

    A→B→C→D の経路では面積は 増加 → 一定 → 減少 と変わるので、最大になるのは
    一定の区間（x が s/v から 2s/v まで）で、そのときの面積は s²/2。
    指定の面積になる時刻は増加区間と減少区間に1つずつある。
    答えは (最大の面積, 最大になる区間の始まり, 終わり, 指定の面積になる時刻2つ)。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    area_v = sympy.Rational(str(area))
    if s_v <= 0 or v_v <= 0 or area_v <= 0:
        raise ValueError("1辺・速さ・面積は正であること")
    peak = sympy.Rational(s_v**2, 2)
    if area_v >= peak:
        raise ValueError("指定の面積が最大の面積以上だと、増減する区間に解が立たない")
    t1 = s_v / v_v
    t_a = 2 * area_v / (s_v * v_v)
    t_b = 3 * t1 - t_a
    if not (0 < t_a < t1 and 2 * t1 < t_b < 3 * t1):
        raise ValueError(f"解が増加区間・減少区間の内側にない: {t_a}, {t_b}")

    vals = sympy.Tuple(peak, t1, 2 * t1, sympy.nsimplify(t_a), sympy.nsimplify(t_b))
    ops = [
        "identify_intervals",
        "find_maximum_area",
        "solve_on_increasing_interval",
        "solve_on_decreasing_interval",
        "collect_answers",
    ]
    narration = {
        "identify_intervals": "動く点がどの辺の上にあるかで時間を区間に分け、面積が増える区間・変わらない区間・減る区間を見つける。",
        "find_maximum_area": "面積が変わらない区間で最大になるので、その面積の値と、区間の始まりと終わりの時刻を求める。",
        "solve_on_increasing_interval": "増えていく区間の式を方程式とみて、指定された面積になる時刻を求める。",
        "solve_on_decreasing_interval": "減っていく区間の式を方程式とみて、指定された面積になる時刻を求める。",
        "collect_answers": "求めた時刻がそれぞれの区間の中にあることを確かめ、答えを並べる。",
    }
    phrase = {
        "identify_intervals": (
            f"0〜{sympy.sstr(t1)}秒、{sympy.sstr(t1)}〜{sympy.sstr(2 * t1)}秒、"
            f"{sympy.sstr(2 * t1)}〜{sympy.sstr(3 * t1)}秒"
        ),
        "find_maximum_area": f"{sympy.sstr(peak)}cm²",
        "solve_on_increasing_interval": f"{sympy.sstr(t_a)}秒後",
        "solve_on_decreasing_interval": f"{sympy.sstr(t_b)}秒後",
    }
    srepr = sympy.srepr(vals)
    disp = (
        f"面積が最大になるのは x が {sympy.sstr(t1)} から {sympy.sstr(2 * t1)} までのときで、"
        f"そのときの面積は {sympy.sstr(peak)}cm²。"
        f"指定された面積になるのは {sympy.sstr(t_a)}秒後と{sympy.sstr(t_b)}秒後"
    )
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# exam_l3（入試融合・動点と面積変化）で足りなかった3つ
#
# 既存 solver は「はじめの区間の式」「区間3本の式」「時刻をすべて求める」までは
# そろっていたが、入試融合の台帳が要求する
#   ・指定された区間の式と、その区間の1点での値（find_value Lv3）
#   ・一定になる区間の式そのもの（word_problem Lv3 の (2)）
#   ・与えられたグラフから値を読む（graph_table Lv2）
# の3つが無かった。いずれも面積は既存の shoelace 公式で裏取りする
# ＝新しい幾何ロジックは足さない。
# ---------------------------------------------------------------------------
def _area_at_time(s_v: sympy.Rational, v_v: sympy.Rational, t: sympy.Rational) -> sympy.Rational:
    """A→B→C→D の経路上、時刻 t における三角形 APD の面積（shoelace 公式）。"""
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


def _interval_expr(
    s_v: sympy.Rational, v_v: sympy.Rational, index: int
) -> tuple[sympy.Expr, sympy.Rational, sympy.Rational]:
    """区間 index（0=増加 / 1=一定 / 2=減少）の面積の式と、その区間の両端の時刻。"""
    t1 = s_v / v_v
    if index == 0:
        return sympy.Rational(s_v * v_v, 2) * _X, sympy.Integer(0), t1
    if index == 1:
        return sympy.Rational(s_v**2, 2) + 0 * _X, t1, 2 * t1
    return sympy.expand(sympy.Rational(s_v, 2) * (3 * s_v - v_v * _X)), 2 * t1, 3 * t1


@register_solver("math.express_interval_area_and_value")
def express_interval_area_and_value(s: object, v: object, x0: object) -> Solution:
    """指定された時刻をふくむ区間の面積の式と、その時刻での面積を求める（exam_l3.find_value Lv3）。

    どの区間かは時刻 x0 から決まる（＝「動点がどの辺の上にいるか」の判断が答えの一部）。
    式に x0 を代入した値が shoelace 公式による再計算と一致することを確かめる。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    x_v = sympy.Rational(str(x0))
    if s_v <= 0 or v_v <= 0 or x_v <= 0:
        raise ValueError("1辺・速さ・時刻は正であること")
    t1 = s_v / v_v
    if x_v > 3 * t1:
        raise ValueError("点がすでに終点に着いている時刻")
    index = 0 if x_v <= t1 else (1 if x_v <= 2 * t1 else 2)
    expr, lo, hi = _interval_expr(s_v, v_v, index)
    value = sympy.nsimplify(expr.subs(_X, x_v))
    geom = _area_at_time(s_v, v_v, x_v)
    if not (value - geom).equals(0):
        raise ValueError(f"区間の式と shoelace 再計算が一致しない: {value} != {geom}")

    coeff = sympy.Poly(expr, _X).coeff_monomial(_X) if index != 1 else sympy.Integer(0)
    const = sympy.Poly(expr, _X).coeff_monomial(1)
    expr_disp = _linear_area_display(sympy.Rational(coeff), sympy.Rational(const))
    ops = ["determine_which_segment", "express_area_in_x", "substitute_time"]
    narration = {
        "determine_which_segment": "与えられた時刻に動く点がどの辺の上にいるかを、進んだ道のりから判断する。",
        "express_area_in_x": "その辺の上にいる間の底辺と高さを x で表し、面積を x の式で表す。",
        "substitute_time": "求めた式に与えられた時刻を代入して、そのときの面積を求める。",
    }
    phrase = {
        # 判断した結果（何番目の辺の上か）を書く。指示の言い直しは置かない（面③）。
        "determine_which_segment": ("はじめの辺の上", "次の辺の上", "最後の辺の上")[index],
        "express_area_in_x": expr_disp,
    }
    answer = sympy.Tuple(expr, value)
    srepr = sympy.srepr(answer)
    disp = (
        f"{sympy.sstr(lo)}≦x≦{sympy.sstr(hi)} のとき {expr_disp}、"
        f"x = {sympy.sstr(x_v)} のときの面積は {sympy.sstr(value)}cm²"
    )
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.express_constant_interval_area")
def express_constant_interval_area(s: object, v: object) -> Solution:
    """面積が一定になる区間の式を求める（exam_l3.word_problem Lv3 の (2)）。

    底辺も高さも変わらないので y は定数 s²/2。「x の式で表せ」に対して
    **x を含まない式**になることを見抜けるかどうかが、この小問の眼目。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    if s_v <= 0 or v_v <= 0:
        raise ValueError("1辺・速さは正であること")
    expr, lo, hi = _interval_expr(s_v, v_v, 1)
    value = sympy.Rational(s_v**2, 2)
    # 恒真: 区間の内側のどこで測っても shoelace 再計算が同じ値になる（＝一定）。
    for t in (lo, (lo + hi) / 2, hi):
        if not (_area_at_time(s_v, v_v, t) - value).equals(0):
            raise ValueError(f"一定であるはずの区間で面積が変わる: t={t}")

    ops = ["locate_point_on_far_side", "express_constant_area"]
    narration = {
        "locate_point_on_far_side": "この区間では動く点が向かい合う辺の上にあり、底辺からの距離が変わらないことを確かめる。",
        "express_constant_area": "底辺も高さも変わらないので、面積は時間によらず一定になる。",
    }
    srepr = sympy.srepr(expr)
    disp = _linear_area_display(sympy.Integer(0), value)
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else f"高さは {sympy.sstr(s_v)} のまま",
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


@register_solver("math.read_area_graph_values")
def read_area_graph_values(s: object, v: object, x0: object) -> Solution:
    """面積のグラフから、指定の時刻での面積と、面積が最大になる時間の範囲を読む（exam_l3.graph_table Lv2）。

    読み取りの正解も、グラフの形ではなく場面のパラメータ（s・v）から shoelace 公式で
    独立に再計算する＝図が間違っていれば一致しない。
    """
    s_v = sympy.Rational(str(s))
    v_v = sympy.Rational(str(v))
    x_v = sympy.Rational(str(x0))
    if s_v <= 0 or v_v <= 0 or x_v <= 0:
        raise ValueError("1辺・速さ・時刻は正であること")
    t1 = s_v / v_v
    if not (0 < x_v < t1):
        raise ValueError("読み取る時刻は、面積が増えていく区間の内側であること")
    y0 = _area_at_time(s_v, v_v, x_v)
    peak = sympy.Rational(s_v**2, 2)
    if not (_area_at_time(s_v, v_v, (t1 + 2 * t1) / 2) - peak).equals(0):
        raise ValueError("最大の区間で面積が s²/2 にならない")

    vals = sympy.Tuple(sympy.nsimplify(y0), sympy.nsimplify(t1), sympy.nsimplify(2 * t1))
    ops = ["read_value_at_time", "find_flat_part", "read_range_of_maximum"]
    narration = {
        "read_value_at_time": "横軸の与えられた時刻のところで縦軸の目もりを読み、そのときの面積を求める。",
        "find_flat_part": "グラフのうち高さが変わらない平らな部分を見つけ、そこが面積の最大であることを確かめる。",
        "read_range_of_maximum": "平らな部分の左端と右端の横軸の値を読み、面積が最大になる時間の範囲を答える。",
    }
    phrase = {
        "read_value_at_time": f"{sympy.sstr(y0)}cm²",
        "find_flat_part": f"x が {sympy.sstr(t1)} から {sympy.sstr(2 * t1)} までの平らな部分",
    }
    srepr = sympy.srepr(vals)
    disp = (
        f"x = {sympy.sstr(x_v)} のときの面積は {sympy.sstr(y0)}cm²、"
        f"面積が最大になるのは x が {sympy.sstr(t1)} から {sympy.sstr(2 * t1)} までのとき"
    )
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


__all__ = [
    "solve_moving_point_area",
    "draw_piecewise_area_graph_features",
    "draw_three_interval_area_graph_features",
    "express_moving_points_area",
    "solve_moving_points_area_time",
    "solve_moving_point_area_all_times",
    "express_single_interval_area",
    "express_three_interval_area_exprs",
    "max_area_and_times",
    "express_interval_area_and_value",
    "express_constant_interval_area",
    "read_area_graph_values",
]
