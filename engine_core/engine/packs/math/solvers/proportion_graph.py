"""比例・反比例の **グラフ**（graph_table）独立再計算ソルバ（実装設計 §6.2 double-solve）。

C4（g1 関数・比例と反比例）クラスタの visual セル群（g1_l30 / l31 / l32 / l34 / l35 / l36）。
solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。純粋・
決定論・SymPy 恒真。乱数は引かない。図は描かない（描画は visual 層のヘルパの責務）。

- `math.read_coordinate_components(x0, y0)`: x座標・y座標の値から点の座標を書く（g1_l30 Lv1）
- `math.reflect_point_pair(x0, y0)`: 原点対称・x軸対称の点の座標を求める（g1_l30 Lv2）
- `math.read_value_on_proportion_graph(a, x0)`: 比例のグラフから対応する y を読む（g1_l31 Lv1）
- `math.draw_proportion_graph_features(a, p, q)`: 比例のグラフをかく特徴（g1_l31 Lv2）
- `math.compare_proportion_graphs(a1, a2, a3)`: 3本の比例グラフを比べる（g1_l31 Lv3）
- `math.read_lattice_point_on_proportion(a, p)`: 比例のグラフ上の格子点を読む（g1_l32 Lv1）
- `math.read_value_on_hyperbola_graph(a, x0)`: 双曲線から対応する y を読む（g1_l34 Lv1）
- `math.draw_hyperbola_features(a, xs)`: 双曲線を2つの枝でかく特徴（g1_l34 Lv2）
- `math.compare_hyperbolas(a1, a2, a3)`: 3本の双曲線を比べる（g1_l34 Lv3）
- `math.read_lattice_point_on_hyperbola(a, x0)`: 双曲線上の格子点を読む（g1_l35 Lv1）
- `math.read_situation_value_from_graph(a, x_q)`: 場面の対応をグラフにして読む（g1_l36 Lv2）
- `math.read_plan_crossover_from_graph(pa, pb, fixed)`: 2つの料金プランの交点（g1_l36 Lv3）

narration には**数字を書かない**（鉄則⑦・G-Q5t 偽陽性の元。hints は narration がそのまま
流れる）。数える語は漢数字（「二つ」）で書く。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Feature, GraphAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_number


def _pt(x: sympy.Expr, y: sympy.Expr) -> sympy.Tuple:
    return sympy.Tuple(sympy.nsimplify(x), sympy.nsimplify(y))


def _pt_display(p: sympy.Tuple) -> str:
    return f"({fmt_number(p[0])}, {fmt_number(p[1])})"


def _int(v: object) -> sympy.Integer:
    return sympy.Integer(int(sympy.nsimplify(v)))


def _rat(v: object) -> sympy.Expr:
    """文字列/数値を sympy の有理数に正規化する（分数の比例定数を受けるため）。

    `sympy.nsimplify(文字列)` は「偽の閉形式」を返すことがあるため、いったん
    `sympy.sympify` で式にしてから `sympy.Rational` 相当に落とす。
    """
    e = sympy.sympify(v)
    return sympy.Rational(e) if e.is_rational else e


def _fmt_direct(a: sympy.Expr) -> str:
    if a == 1:
        return "y = x"
    if a == -1:
        return "y = -x"
    return f"y = {fmt_number(a)}x"


def _fmt_inverse(a: sympy.Expr) -> str:
    return f"y = {fmt_number(a)}/x"


# ---------------------------------------------------------------------------
# math.read_coordinate_components（g1_l30.graph_table Lv1）
# x座標・y座標の値から、点の座標 (x, y) を書く（座標の読み方・1動作）。
# ---------------------------------------------------------------------------
@register_solver("math.read_coordinate_components")
def read_coordinate_components(x0: object, y0: object) -> Solution:
    """x座標・y座標の値から点の座標を組み立てる（g1_l30.graph_table Lv1）。

    **このセルは「図から読む」問題ではない。** 座標は本文が与え、図は空の方眼で、
    生徒はそこに点をとる。それなのに解説が「どれだけ進んだ位置かを読み」と
    言っていたので、読む対象が無いのに読めと指示していた（EVALUATION D-8）。
    実際にやることは「与えられた2つの数を、横・縦の位置として受け取り、
    (x座標, y座標) の形に並べて、方眼の上でその位置に点をとる」こと。
    """
    x_s, y_s = _int(x0), _int(y0)
    pt = _pt(x_s, y_s)
    steps = [
        Step(
            op="read_x_coordinate",
            args=[fmt_number(x_s)],
            result_srepr=sympy.srepr(x_s),
            result_display=f"x座標 = {fmt_number(x_s)}",
            narration="与えられたx座標を、原点から横の向き（x軸の向き）に進む量として受け取る。",
        ),
        Step(
            op="read_y_coordinate",
            args=[fmt_number(y_s)],
            result_srepr=sympy.srepr(y_s),
            result_display=f"y座標 = {fmt_number(y_s)}",
            narration="与えられたy座標を、原点から縦の向き（y軸の向き）に進む量として受け取る。",
        ),
        Step(
            op="write_coordinate",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="x座標、y座標の順にかっこの中へ並べて、点の座標の形に書く。"
            "その位置を方眼の上でたどって、点をとる。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pt), display=_pt_display(pt)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.reflect_point_pair（g1_l30.graph_table Lv2）
# 点 A(x0,y0) に対し、原点対称の点 B と x 軸対称の点 C の座標を求める。
# ---------------------------------------------------------------------------
@register_solver("math.reflect_point_pair")
def reflect_point_pair(x0: object, y0: object) -> Solution:
    """原点について対称な点・x軸について対称な点の座標を求める（g1_l30.graph_table Lv2）。"""
    x_s, y_s = _int(x0), _int(y0)
    b_pt = _pt(-x_s, -y_s)
    c_pt = _pt(x_s, -y_s)
    both = sympy.Tuple(b_pt, c_pt)
    display = f"B{_pt_display(b_pt)}, C{_pt_display(c_pt)}"
    steps = [
        Step(
            op="reflect_about_origin",
            args=[_pt_display(_pt(x_s, y_s))],
            result_srepr=sympy.srepr(b_pt),
            result_display=_pt_display(b_pt),
            narration="原点について対称な点は、x座標とy座標のどちらの符号も入れかえた点になる。",
        ),
        Step(
            op="reflect_about_x_axis",
            args=[_pt_display(_pt(x_s, y_s))],
            result_srepr=sympy.srepr(c_pt),
            result_display=_pt_display(c_pt),
            narration="x軸について対称な点は、x座標はそのままで、y座標の符号だけを入れかえた点になる。",
        ),
        Step(
            op="write_reflected_coordinates",
            args=[],
            result_srepr=sympy.srepr(both),
            result_display=display,
            narration="求めた二つの点を、それぞれ座標の形に書き、座標平面上の位置を確かめる。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(both), display=display), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_value_on_proportion_graph（g1_l31.graph_table Lv1）
# 比例のグラフ（原点を通る直線）から x=x0 に対応する y の値を読む。
# ---------------------------------------------------------------------------
@register_solver("math.read_value_on_proportion_graph")
def read_value_on_proportion_graph(a: object, x0: object) -> Solution:
    """比例のグラフから対応する y の値を読み取る（g1_l31.graph_table Lv1）。"""
    a_s, x_s = _rat(a), _int(x0)
    y_s = sympy.nsimplify(a_s * x_s)
    steps = [
        Step(
            op="locate_x_on_graph",
            args=[fmt_number(x_s)],
            result_srepr=sympy.srepr(x_s),
            result_display=f"x = {fmt_number(x_s)}",
            narration="読み取りたいx座標の目もりを、横軸の上で見つける。",
        ),
        Step(
            op="read_y_on_graph",
            args=[fmt_number(x_s)],
            result_srepr=sympy.srepr(y_s),
            result_display=f"y = {fmt_number(y_s)}",
            narration="その目もりから縦にたどってグラフと交わる位置を見つけ、そこから横にたどってy座標を読む。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(y_s), display=fmt_number(y_s)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.draw_proportion_graph_features（g1_l31.graph_table Lv2）
# 比例 y=ax のグラフ（原点を通る直線）を、原点と指定された2つの格子点でかく。
# ---------------------------------------------------------------------------
@register_solver("math.draw_proportion_graph_features")
def draw_proportion_graph_features(a: object, p: object, q: object) -> Solution:
    """比例 y=ax のグラフをかくための検証可能な特徴を求める（g1_l31.graph_table Lv2）。

    答えは GraphAnswer（比例定数 a・通る2点の集合で採点＝§6.2 V1'）。SVG は描かない。
    """
    a_s, p_s, q_s = _rat(a), _int(p), _int(q)
    pt_p = _pt(p_s, a_s * p_s)
    pt_q = _pt(q_s, a_s * q_s)
    features = [
        Feature(kind="slope", srepr=sympy.srepr(a_s), display=f"比例定数 {fmt_number(a_s)}"),
        Feature(kind="point", srepr=sympy.srepr(pt_p), display=f"通る点 {_pt_display(pt_p)}"),
        Feature(kind="point", srepr=sympy.srepr(pt_q), display=f"通る点 {_pt_display(pt_q)}"),
    ]
    steps = [
        Step(
            op="plot_origin",
            args=[],
            result_srepr=sympy.srepr(_pt(sympy.Integer(0), sympy.Integer(0))),
            result_display="(0, 0)",
            narration="比例のグラフは必ず原点を通るので、はじめに原点に点をとる。",
        ),
        Step(
            op="plot_point_from_constant",
            args=[fmt_number(p_s)],
            result_srepr=sympy.srepr(pt_p),
            result_display=_pt_display(pt_p),
            narration="指定されたx座標を式にあてはめて対応するy座標を求め、その点をとる。",
        ),
        Step(
            op="plot_second_point_from_constant",
            args=[fmt_number(q_s)],
            result_srepr=sympy.srepr(pt_q),
            result_display=_pt_display(pt_q),
            narration="もう一方の指定されたx座標についても同じように対応するy座標を求め、その点をとる。",
        ),
        Step(
            op="draw_proportion_line",
            args=[],
            result_srepr=sympy.srepr(a_s * sympy.Symbol("x")),
            result_display=_fmt_direct(a_s),
            narration="とった点と原点を通るように、まっすぐな直線をひく。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


# ---------------------------------------------------------------------------
# math.compare_proportion_graphs（g1_l31.graph_table Lv3）
# 3本の比例のグラフを比べ、最も傾きが急なものと右下がりのものの比例定数を答える。
# ---------------------------------------------------------------------------
@register_solver("math.compare_proportion_graphs")
def compare_proportion_graphs(a1: object, a2: object, a3: object) -> Solution:
    """3本の比例のグラフを比べる（g1_l31.graph_table Lv3）。

    最も傾きが急なグラフ（|a| 最大）と、右下がりのグラフ（a<0）の比例定数を組で答える。
    recipe 側が「負は1本だけ・|a| 最大は正の1本だけ」を構成で保証する（退化の排除）。
    """
    values = [_rat(a1), _rat(a2), _rat(a3)]
    negatives = [v for v in values if v < 0]
    if len(negatives) != 1:
        raise ValueError(f"右下がりのグラフがただ一つに定まらない: {values}")
    steepest = max(values, key=lambda v: abs(v))
    if [abs(v) for v in values].count(abs(steepest)) != 1:
        raise ValueError(f"最も傾きが急なグラフがただ一つに定まらない: {values}")
    negative = negatives[0]
    pair = sympy.Tuple(steepest, negative)
    # display に説明語（「第2象限」等）を混ぜない: G-Q5t は answer.display からも数値
    # トークンを取るため、説明語の中の数字が本文の数字と衝突して偽陽性になる。
    display = f"{fmt_number(steepest)}, {fmt_number(negative)}"
    steps = [
        Step(
            op="sketch_proportion_graphs",
            args=[_fmt_direct(v) for v in values],
            result_srepr=sympy.srepr(sympy.Tuple(*values)),
            result_display="、".join(_fmt_direct(v) for v in values),
            narration="どのグラフも原点を通る直線なので、原点ともう一つの点をとって三本のグラフをかく。",
        ),
        Step(
            op="compare_steepness",
            args=[fmt_number(steepest)],
            result_srepr=sympy.srepr(steepest),
            result_display=fmt_number(steepest),
            narration="比例定数の絶対値が大きいほどグラフの傾きは急になるので、絶対値を比べて最も急なものを選ぶ。",
        ),
        Step(
            op="identify_decreasing_graph",
            args=[fmt_number(negative)],
            result_srepr=sympy.srepr(negative),
            result_display=fmt_number(negative),
            narration="比例定数が負のとき、グラフは右下がりの直線になるので、符号を見て選ぶ。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pair), display=display), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_lattice_point_on_proportion（g1_l32.graph_table Lv1）
# 比例のグラフ上の（原点でない）格子点の座標を読む。式決定の材料。
# ---------------------------------------------------------------------------
@register_solver("math.read_lattice_point_on_proportion")
def read_lattice_point_on_proportion(a: object, p: object) -> Solution:
    """比例のグラフ上の格子点を読み取る（g1_l32.graph_table Lv1）。"""
    a_s, p_s = _rat(a), _int(p)
    pt = _pt(p_s, a_s * p_s)
    steps = [
        Step(
            op="find_lattice_point",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="直線と方眼の交点のうち、たて・よこの目もりがどちらもちょうど整数になる点をさがす。",
        ),
        Step(
            op="write_lattice_coordinate",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="見つけた点のx座標とy座標を目もりから読み、座標の形に書く。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pt), display=_pt_display(pt)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_value_on_hyperbola_graph（g1_l34.graph_table Lv1）
# 反比例 y=a/x のグラフ（双曲線）から x=x0 に対応する y を読む。
# ---------------------------------------------------------------------------
@register_solver("math.read_value_on_hyperbola_graph")
def read_value_on_hyperbola_graph(a: object, x0: object) -> Solution:
    """双曲線から対応する y の値を読み取る（g1_l34.graph_table Lv1）。"""
    a_s, x_s = _int(a), _int(x0)
    if x_s == 0:
        raise ValueError("反比例のグラフで x=0 に対応する点は無い")
    y_s = sympy.nsimplify(sympy.Rational(a_s, x_s))
    steps = [
        Step(
            op="locate_x_on_hyperbola",
            args=[fmt_number(x_s)],
            result_srepr=sympy.srepr(x_s),
            result_display=f"x = {fmt_number(x_s)}",
            narration="読み取りたいx座標の目もりを横軸の上で見つけ、どちらの枝の上にある点かを確かめる。",
        ),
        Step(
            op="read_y_on_hyperbola",
            args=[fmt_number(x_s)],
            result_srepr=sympy.srepr(y_s),
            result_display=f"y = {fmt_number(y_s)}",
            narration="その目もりから縦にたどって曲線と交わる位置を見つけ、そこから横にたどってy座標を読む。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(y_s), display=fmt_number(y_s)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.draw_hyperbola_features（g1_l34.graph_table Lv2）
# 表で対応値を求め、点をとって双曲線を2つの枝でかく。
# ---------------------------------------------------------------------------
@register_solver("math.draw_hyperbola_features")
def draw_hyperbola_features(a: object, xs: object) -> Solution:
    """双曲線を2つの枝でかくための検証可能な特徴を求める（g1_l34.graph_table Lv2）。

    答えは GraphAnswer（比例定数 a・正の枝の代表点・負の枝の代表点で採点＝§6.2 V1'）。
    `xs` は表に並べる正のx座標（a の約数）。代表点は最小の |x| に対応する点をとる。
    """
    a_s = _int(a)
    x_list = [_int(v) for v in list(xs)]  # type: ignore[call-overload]
    if not x_list or any(v <= 0 for v in x_list):
        raise ValueError(f"表のx座標は正の整数の並びであること: {xs!r}")
    if any(sympy.Rational(a_s, v).q != 1 for v in x_list):
        raise ValueError(f"表のx座標は比例定数の約数であること: a={a_s} xs={x_list}")
    x1 = min(x_list)
    y1 = sympy.nsimplify(sympy.Rational(a_s, x1))
    pt_pos = _pt(x1, y1)
    pt_neg = _pt(-x1, -y1)
    features = [
        Feature(kind="slope", srepr=sympy.srepr(a_s), display=f"比例定数 {fmt_number(a_s)}"),
        Feature(kind="point", srepr=sympy.srepr(pt_pos), display=f"通る点 {_pt_display(pt_pos)}"),
        Feature(kind="point", srepr=sympy.srepr(pt_neg), display=f"通る点 {_pt_display(pt_neg)}"),
    ]
    table_display = "、".join(
        f"{_pt_display(_pt(v, sympy.Rational(a_s, v)))}" for v in sorted(x_list)
    )
    steps = [
        Step(
            op="make_correspondence_table",
            args=[fmt_number(v) for v in sorted(x_list)],
            result_srepr=sympy.srepr(sympy.Tuple(*[_int(v) for v in sorted(x_list)])),
            result_display=table_display,
            narration="表のそれぞれの x の値を式にあてはめ、対応する y の値を求めて表にまとめる。",
        ),
        Step(
            op="plot_table_points",
            args=[],
            result_srepr=sympy.srepr(pt_pos),
            result_display=_pt_display(pt_pos),
            narration="表で求めた組を座標とみて、座標平面上に点をとる。",
        ),
        Step(
            op="draw_positive_branch",
            args=[],
            result_srepr=sympy.srepr(pt_pos),
            result_display=_pt_display(pt_pos),
            narration="xが正の側の点を、軸に近づきながら軸とは交わらないなめらかな曲線で結ぶ。",
        ),
        Step(
            op="draw_negative_branch",
            args=[],
            result_srepr=sympy.srepr(pt_neg),
            result_display=_pt_display(pt_neg),
            narration="xが負の側にも同じ形の枝があるので、そちらの点もなめらかな曲線で結ぶ。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


# ---------------------------------------------------------------------------
# math.compare_hyperbolas（g1_l34.graph_table Lv3）
# 3本の双曲線を比べ、第2・第4象限にあるものと、原点から最も離れたものを答える。
# ---------------------------------------------------------------------------
@register_solver("math.compare_hyperbolas")
def compare_hyperbolas(a1: object, a2: object, a3: object) -> Solution:
    """3本の双曲線を比べる（g1_l34.graph_table Lv3）。

    第2・第4象限にある双曲線（a<0）と、原点から最も離れた双曲線（|a| 最大）の比例定数を
    組で答える。recipe が「負は1本だけ・|a| 最大は正の1本だけ」を構成で保証する。
    """
    values = [_int(a1), _int(a2), _int(a3)]
    negatives = [v for v in values if v < 0]
    if len(negatives) != 1:
        raise ValueError(f"第2・第4象限にある双曲線がただ一つに定まらない: {values}")
    farthest = max(values, key=lambda v: abs(v))
    if [abs(v) for v in values].count(abs(farthest)) != 1:
        raise ValueError(f"原点から最も離れた双曲線がただ一つに定まらない: {values}")
    negative = negatives[0]
    pair = sympy.Tuple(negative, farthest)
    # display に説明語（「第2象限」等）を混ぜない（G-Q5t は display からも数値を取る）。
    display = f"{fmt_number(negative)}, {fmt_number(farthest)}"
    steps = [
        Step(
            op="sketch_hyperbolas",
            args=[_fmt_inverse(v) for v in values],
            result_srepr=sympy.srepr(sympy.Tuple(*values)),
            result_display="、".join(_fmt_inverse(v) for v in values),
            narration="それぞれの式で対応する点をいくつかとり、三本の双曲線を同じ座標平面にかく。",
        ),
        Step(
            op="identify_quadrant_pair",
            args=[fmt_number(negative)],
            result_srepr=sympy.srepr(negative),
            result_display=fmt_number(negative),
            # 「象限」は中学の教科書に無い用語（高校で扱う）。中1の反比例のグラフでは
            # 「左上と右下の部分」と書く（`judge_hyperbola_quadrants` と同じ扱い）。
            narration="比例定数が負のとき、双曲線は左上と右下の部分にあらわれるので、符号を見て選ぶ。",
        ),
        Step(
            op="compare_distance_from_origin",
            args=[fmt_number(farthest)],
            result_srepr=sympy.srepr(farthest),
            result_display=fmt_number(farthest),
            narration="比例定数の絶対値が大きいほど双曲線は原点から遠ざかるので、絶対値を比べて選ぶ。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pair), display=display), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_lattice_point_on_hyperbola（g1_l35.graph_table Lv1）
# 双曲線上の格子点の座標を読む。式決定の材料。
# ---------------------------------------------------------------------------
@register_solver("math.read_lattice_point_on_hyperbola")
def read_lattice_point_on_hyperbola(a: object, x0: object) -> Solution:
    """双曲線上の格子点を読み取る（g1_l35.graph_table Lv1）。"""
    a_s, x_s = _int(a), _int(x0)
    if x_s == 0 or sympy.Rational(a_s, x_s).q != 1:
        raise ValueError(f"格子点にならない x 座標: a={a_s} x0={x_s}")
    pt = _pt(x_s, sympy.Rational(a_s, x_s))
    steps = [
        Step(
            op="find_lattice_point_on_curve",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="曲線と方眼の交点のうち、たて・よこの目もりがどちらもちょうど整数になる点をさがす。",
        ),
        Step(
            op="write_lattice_coordinate_on_curve",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="見つけた点のx座標とy座標を目もりから読み、座標の形に書く。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pt), display=_pt_display(pt)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_situation_value_from_graph（g1_l36.graph_table Lv2）
# 場面の対応を表とグラフに表し、別の x に対応する値をグラフから読む。
# ---------------------------------------------------------------------------
@register_solver("math.read_situation_value_from_graph")
def read_situation_value_from_graph(a: object, x_q: object) -> Solution:
    """場面の対応をグラフに表し、指定された x に対応する値を読む（g1_l36.graph_table Lv2）。"""
    a_s, xq_s = _int(a), _int(x_q)
    y_s = sympy.nsimplify(a_s * xq_s)
    steps = [
        Step(
            op="make_situation_table",
            args=[],
            result_srepr=sympy.srepr(a_s),
            result_display=_fmt_direct(a_s),
            narration="測った組を表にまとめ、対応する y の値を x の値で割った商がいつも同じかどうかを確かめる。",
        ),
        Step(
            op="plot_situation_points",
            args=[],
            result_srepr=sympy.srepr(a_s),
            result_display=_fmt_direct(a_s),
            narration="表にまとめた組を座標とみて、座標平面上に点をとる。",
        ),
        Step(
            op="draw_situation_line",
            args=[],
            result_srepr=sympy.srepr(a_s * sympy.Symbol("x")),
            result_display=_fmt_direct(a_s),
            narration="とった点が一直線に並ぶので、原点を通る直線をひいてグラフに表す。",
        ),
        Step(
            op="read_situation_value",
            args=[fmt_number(xq_s)],
            result_srepr=sympy.srepr(y_s),
            result_display=fmt_number(y_s),
            narration="たずねられたxの目もりから縦にたどって直線と交わる位置を見つけ、対応する値を読む。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(y_s), display=fmt_number(y_s)), steps=steps
    )


# ---------------------------------------------------------------------------
# math.read_plan_crossover_from_graph（g1_l36.graph_table Lv3）
# 2つの料金プラン（比例／固定費つき）のグラフを同じ座標平面にかき、交点を読む。
# ---------------------------------------------------------------------------
@register_solver("math.read_plan_crossover_from_graph")
def read_plan_crossover_from_graph(pa: object, pb: object, fixed: object) -> Solution:
    """2つの料金プランのグラフの交点をグラフから読む（g1_l36.graph_table Lv3）。

    A は 1 個あたり pa 円の比例、B は 1 個あたり pb 円＋固定費 fixed 円。
    交点の x は fixed/(pa-pb)（recipe が整数になるよう構成する）。
    """
    pa_s, pb_s, f_s = _int(pa), _int(pb), _int(fixed)
    if pa_s <= pb_s:
        raise ValueError(f"1個あたりの値段は A のほうが高いこと: pa={pa_s} pb={pb_s}")
    x0 = sympy.Rational(f_s, pa_s - pb_s)
    if x0.q != 1:
        raise ValueError(f"交点のx座標が格子点にならない: pa={pa_s} pb={pb_s} fixed={f_s}")
    x0 = sympy.Integer(x0)
    y0 = sympy.nsimplify(pa_s * x0)
    pt = _pt(x0, y0)
    steps = [
        Step(
            op="express_plan_a",
            args=[fmt_number(pa_s)],
            result_srepr=sympy.srepr(pa_s * sympy.Symbol("x")),
            result_display=_fmt_direct(pa_s),
            narration="Aの料金は個数に比例するので、一個あたりの値段を比例定数として式に表す。",
        ),
        Step(
            op="express_plan_b",
            args=[fmt_number(pb_s), fmt_number(f_s)],
            result_srepr=sympy.srepr(pb_s * sympy.Symbol("x") + f_s),
            result_display=f"y = {fmt_number(pb_s)}x + {fmt_number(f_s)}",
            narration="Bの料金は個数に比例する分に、個数によらずかかる分をたした式になる。",
        ),
        Step(
            op="draw_both_plan_graphs",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="二つの式のグラフを同じ座標平面にかき、どこで交わるかを見る。",
        ),
        Step(
            op="read_plan_crossover",
            args=[],
            result_srepr=sympy.srepr(pt),
            result_display=_pt_display(pt),
            narration="二本のグラフが交わる点の目もりを読むと、どちらの料金も等しくなる個数と、そのときの料金がわかる。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(pt), display=_pt_display(pt)), steps=steps
    )


__all__ = [
    "read_coordinate_components",
    "reflect_point_pair",
    "read_value_on_proportion_graph",
    "draw_proportion_graph_features",
    "compare_proportion_graphs",
    "read_lattice_point_on_proportion",
    "read_value_on_hyperbola_graph",
    "draw_hyperbola_features",
    "compare_hyperbolas",
    "read_lattice_point_on_hyperbola",
    "read_situation_value_from_graph",
    "read_plan_crossover_from_graph",
]
