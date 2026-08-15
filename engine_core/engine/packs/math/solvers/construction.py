"""基本作図（form: construction）の独立再計算ソルバ（実装設計 §6.2 double-solve）。

C7（g1 平面図形）の作図セル（g1_l41 / l42 / l43 / l44）。solver は**問題パラメータ
だけ**から「作図で得られるもの」と手順を導く（recipe の構成値は見ない）。純粋・決定論・
SymPy 恒真。乱数は引かない。図は描かない（描画は visual 層の責務）。

作図の答えを何で検証するか（この form の設計の要）:
  作図は「線を引く操作」だが、引けたかどうかは**得られた図形の位置**で決まる。そこで
  `GraphAnswer.features` に、直線なら正規化した係数 (a, b, c)（ax+by+c=0）、点なら
  座標を入れる。座標は有理数に閉じるように問題側を構成してあるので、一致は厳密に
  判定できる（浮動小数の近似一致に頼らない）。

  **座標と直線の式は `srepr`（機械の照合用）にだけ置き、`display` には出さない。**
  作図の図には座標軸が無い（線分と点の名前しか描かれていない）ので、
  「中点(2, -5)」「線分CDの垂直二等分線＝直線 2x - 5y - 29 = 0」と答えても、
  生徒は自分の作図と照合できない。しかも直線の一般形 ax+by+c=0 は中学の範囲外
  （一次関数は中2、一般形は高校数II）。**生徒に見せる答えは「何をかいたか」**——
  「線分CDの垂直二等分線」——であって、その式ではない。手順そのものは教科書どおり
  なので、直しはこの表示層で閉じている。

  角の二等分線だけは、方向が u/|u| + v/|v| になるため一般には無理数になる。そこで
  **2辺の方向ベクトルは長さが整数のもの（(3,4) など）から引く**——こうすると
  二等分線の方向は u*|v| + v*|u| という整数ベクトルになり、厳密に扱える。

steps の op が Lv 間の差（level_sep）を作る:
  基本作図1つ = 弧2〜3手 + 直線1手。応用はそこへ「交点をとる」「足を示す」「方針を
  選ぶ」が積み増される。narration には**数字を書かない**（鉄則⑦・hints へ流れる）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Feature, GraphAnswer, Solution, Step
from engine.core.registry import register_solver

_V = tuple[sympy.Expr, sympy.Expr]


# ---------------------------------------------------------------------------
# 幾何の道具（すべて有理数で閉じる）
# ---------------------------------------------------------------------------
def _pt(x: object, y: object) -> _V:
    return (sympy.nsimplify(x), sympy.nsimplify(y))


def _srepr_pt(p: _V) -> str:
    return sympy.srepr(sympy.Tuple(p[0], p[1]))


def _midpoint(a: _V, b: _V) -> _V:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _line_coeffs(p: _V, d: _V) -> sympy.Tuple:
    """点 p を通り向き d の直線を ax+by+c=0 の正規形（整数・既約・先頭正）で返す。

    直線の「表し方」は無数にあるので、答えの一致判定ができるように一意化する。
    """
    a, b = -d[1], d[0]
    c = -(a * p[0] + b * p[1])
    coeffs = [sympy.nsimplify(v) for v in (a, b, c)]
    den = sympy.ilcm(*[sympy.Rational(v).q for v in coeffs])
    ints = [int(sympy.Rational(v) * den) for v in coeffs]
    g = sympy.igcd(*[abs(v) for v in ints]) or 1
    ints = [v // g for v in ints]
    for v in ints:
        if v != 0:
            if v < 0:
                ints = [-w for w in ints]
            break
    return sympy.Tuple(*[sympy.Integer(v) for v in ints])


def _line_from_normal(p: _V, n: _V) -> sympy.Tuple:
    """点 p を通り、法線が n の直線（＝n に垂直な向きの直線）。

    垂直二等分線は「線分ABの向きを**法線**にもつ」直線である。向きとして渡すと
    ABに平行な直線ができてしまうので、法線から作る入口を分けておく。
    """
    return _line_coeffs(p, (-n[1], n[0]))


def _intersect(l1: sympy.Tuple, l2: sympy.Tuple) -> _V:
    a1, b1, c1 = l1
    a2, b2, c2 = l2
    det = a1 * b2 - a2 * b1
    if det == 0:
        raise ValueError("交わらない2直線の交点を求めようとした")
    return ((b1 * c2 - b2 * c1) / det, (c1 * a2 - c2 * a1) / det)


def _foot(p: _V, q: _V, d: _V) -> _V:
    """点 p から、点 q を通り向き d の直線へ下ろした垂線の足。"""
    t = ((p[0] - q[0]) * d[0] + (p[1] - q[1]) * d[1]) / (d[0] ** 2 + d[1] ** 2)
    return (q[0] + t * d[0], q[1] + t * d[1])


def _int_len(d: _V) -> sympy.Expr:
    """方向ベクトルの長さ。整数長のベクトルだけを渡す約束（無理数を持ち込まない）。"""
    n2 = d[0] ** 2 + d[1] ** 2
    n = sympy.sqrt(n2)
    if not n.is_Integer:
        raise ValueError(f"長さが整数でない方向ベクトル: {d}")
    return n


def _bisector_dir(u: _V, v: _V) -> _V:
    """2辺 u, v がなす角の二等分線の向き（u/|u| + v/|v| を整数倍したもの）。"""
    lu, lv = _int_len(u), _int_len(v)
    w = (u[0] * lv + v[0] * lu, u[1] * lv + v[1] * lu)
    g = sympy.igcd(int(w[0]), int(w[1])) or 1
    return (sympy.Integer(int(w[0]) // g), sympy.Integer(int(w[1]) // g))


# ---------------------------------------------------------------------------
# 基本作図の手順（steps）。op がレベル分離の材料になる。
# ---------------------------------------------------------------------------
def _perp_bisector_steps(a: _V, b: _V, na: str, nb: str, coeffs: sympy.Tuple) -> list[Step]:
    return [
        Step(
            op="arc_from_first_endpoint",
            args=[na],
            result_srepr=_srepr_pt(a),
            result_display=f"点{na}を中心とする弧",
            narration=f"点{na}を中心に、線分の長さの半分より大きい半径で弧をかく。",
        ),
        Step(
            op="arc_from_second_endpoint",
            args=[nb],
            result_srepr=_srepr_pt(b),
            result_display=f"点{nb}を中心とする同じ半径の弧（先の弧との交点2つ）",
            narration=f"点{nb}を中心に、同じ半径で弧をかき、先の弧との交点を二つ得る。",
        ),
        Step(
            op="draw_perpendicular_bisector",
            args=[na, nb],
            result_srepr=sympy.srepr(coeffs),
            result_display=f"線分{na}{nb}の垂直二等分線",
            narration="二つの交点を通る直線をひく。これが線分の垂直二等分線になる。",
        ),
    ]


def _angle_bisector_steps(o: _V, no: str, n1: str, n2: str, coeffs: sympy.Tuple) -> list[Step]:
    return [
        Step(
            op="arc_from_vertex",
            args=[no],
            result_srepr=_srepr_pt(o),
            result_display=f"頂点{no}を中心とする弧（二辺との交点2つ）",
            narration=f"頂点{no}を中心に弧をかき、角の二辺との交点をとる。",
        ),
        Step(
            op="arcs_from_side_points",
            args=[n1, n2],
            result_srepr=sympy.srepr(sympy.Tuple()),
            result_display=f"二辺{no}{n1}、{no}{n2}上の点を中心とする弧",
            narration="二辺上にとった点それぞれを中心に、等しい半径の弧をかいて交点を得る。",
        ),
        Step(
            op="draw_angle_bisector",
            args=[no],
            result_srepr=sympy.srepr(coeffs),
            result_display=f"∠{n1}{no}{n2}の二等分線",
            narration="頂点とその交点を通る半直線をひく。これが角の二等分線になる。",
        ),
    ]


def _perpendicular_steps(p: _V, np_: str, coeffs: sympy.Tuple) -> list[Step]:
    return [
        Step(
            op="arc_from_point_cross_line",
            args=[np_],
            result_srepr=_srepr_pt(p),
            result_display=f"点{np_}を中心とする円（直線との交点2つ）",
            narration=f"点{np_}を中心に、直線と二つの点で交わる円をかく。",
        ),
        Step(
            op="arcs_from_line_points",
            args=[np_],
            result_srepr=sympy.srepr(sympy.Tuple()),
            result_display="直線上の二点を中心とする弧",
            narration="直線上にできた二点それぞれを中心に、等しい半径の弧をかいて交点を得る。",
        ),
        Step(
            op="draw_perpendicular",
            args=[np_],
            result_srepr=sympy.srepr(coeffs),
            result_display=f"点{np_}を通り、与えられた直線に垂直な直線",
            narration="もとの点とその交点を通る直線をひく。これが直線への垂線になる。",
        ),
    ]


def _graph(features: list[Feature]) -> GraphAnswer:
    return GraphAnswer(features=features)


# ---------------------------------------------------------------------------
# math.perpendicular_bisector_of_segment（g1_l41.construction Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.perpendicular_bisector_of_segment")
def perpendicular_bisector_of_segment(
    ax: object, ay: object, bx: object, by: object, na: object, nb: object
) -> Solution:
    """線分の垂直二等分線を作図する（g1_l41.construction Lv1）。"""
    a, b = _pt(ax, ay), _pt(bx, by)
    na_s, nb_s = str(na), str(nb)
    mid = _midpoint(a, b)
    coeffs = _line_from_normal(mid, (b[0] - a[0], b[1] - a[1]))
    features = [
        Feature(kind="midpoint", srepr=_srepr_pt(mid), display=f"線分{na_s}{nb_s}の中点"),
        Feature(
            kind="perpendicular_bisector",
            srepr=sympy.srepr(coeffs),
            display=f"線分{na_s}{nb_s}の垂直二等分線（かいた直線）",
        ),
    ]
    return Solution(answer=_graph(features), steps=_perp_bisector_steps(a, b, na_s, nb_s, coeffs))


# ---------------------------------------------------------------------------
# math.equidistant_point_on_line（g1_l41.construction Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.equidistant_point_on_line")
def equidistant_point_on_line(
    ax: object, ay: object, bx: object, by: object,
    lx: object, ly: object, ldx: object, ldy: object,
    na: object, nb: object,
) -> Solution:
    """2点から等距離で、かつ与えられた直線上にある点を作図で求める（g1_l41 Lv2）。"""
    a, b = _pt(ax, ay), _pt(bx, by)
    na_s, nb_s = str(na), str(nb)
    lp, ld = _pt(lx, ly), _pt(ldx, ldy)
    mid = _midpoint(a, b)
    bis = _line_from_normal(mid, (b[0] - a[0], b[1] - a[1]))
    ell = _line_coeffs(lp, ld)
    p = _intersect(bis, ell)
    features = [
        Feature(
            kind="perpendicular_bisector",
            srepr=sympy.srepr(bis),
            display=f"線分{na_s}{nb_s}の垂直二等分線（かいた直線）",
        ),
        Feature(
            kind="point",
            srepr=_srepr_pt(p),
            display=f"点P（線分{na_s}{nb_s}の垂直二等分線と、与えられた直線との交点）",
        ),
    ]
    steps = _perp_bisector_steps(a, b, na_s, nb_s, bis) + [
        Step(
            op="intersect_with_given_line",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="垂直二等分線と与えられた直線との交点",
            narration="ひいた垂直二等分線と、与えられた直線との交点をとる。",
        ),
        Step(
            op="mark_result_point",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="点P",
            narration=(
                f"その交点は{na_s}からの距離と{nb_s}からの距離が等しく、"
                "直線上にもあるので、求める点である。"
            ),
        ),
    ]
    return Solution(answer=_graph(features), steps=steps)


# ---------------------------------------------------------------------------
# math.angle_bisector_of_angle（g1_l42.construction Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.angle_bisector_of_angle")
def angle_bisector_of_angle(
    ox: object, oy: object, ux: object, uy: object, vx: object, vy: object,
    no: object, n1: object, n2: object,
) -> Solution:
    """角の二等分線を作図する（g1_l42.construction Lv1）。"""
    o = _pt(ox, oy)
    u, v = _pt(ux, uy), _pt(vx, vy)
    no_s, n1_s, n2_s = str(no), str(n1), str(n2)
    w = _bisector_dir(u, v)
    coeffs = _line_coeffs(o, w)
    features = [
        Feature(kind="vertex", srepr=_srepr_pt(o), display=f"頂点{no_s}"),
        Feature(
            kind="angle_bisector",
            srepr=sympy.srepr(coeffs),
            display=f"∠{n1_s}{no_s}{n2_s}の二等分線（かいた半直線）",
        ),
    ]
    return Solution(
        answer=_graph(features), steps=_angle_bisector_steps(o, no_s, n1_s, n2_s, coeffs)
    )


# ---------------------------------------------------------------------------
# math.equidistant_point_from_two_sides（g1_l42.construction Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.equidistant_point_from_two_sides")
def equidistant_point_from_two_sides(
    ox: object, oy: object, ux: object, uy: object, vx: object, vy: object,
    no: object, n1: object, n2: object,
) -> Solution:
    """角の2辺から等距離で、2辺の端を結ぶ線分上にある点を作図で求める（g1_l42 Lv2）。"""
    o = _pt(ox, oy)
    u, v = _pt(ux, uy), _pt(vx, vy)
    no_s, n1_s, n2_s = str(no), str(n1), str(n2)
    x_pt = (o[0] + u[0], o[1] + u[1])
    y_pt = (o[0] + v[0], o[1] + v[1])
    w = _bisector_dir(u, v)
    bis = _line_coeffs(o, w)
    chord = _line_coeffs(x_pt, (y_pt[0] - x_pt[0], y_pt[1] - x_pt[1]))
    p = _intersect(bis, chord)
    features = [
        Feature(
            kind="angle_bisector",
            srepr=sympy.srepr(bis),
            display=f"∠{n1_s}{no_s}{n2_s}の二等分線（かいた半直線）",
        ),
        Feature(
            kind="point",
            srepr=_srepr_pt(p),
            display=f"点P（∠{n1_s}{no_s}{n2_s}の二等分線と線分{n1_s}{n2_s}との交点）",
        ),
    ]
    steps = _angle_bisector_steps(o, no_s, n1_s, n2_s, bis) + [
        Step(
            op="intersect_with_given_segment",
            args=[n1_s, n2_s],
            result_srepr=_srepr_pt(p),
            result_display=f"二等分線と線分{n1_s}{n2_s}との交点",
            narration="ひいた二等分線と、与えられた線分との交点をとる。",
        ),
        Step(
            op="mark_result_point",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="点P",
            narration=(
                "角の二等分線上の点は角の二辺までの距離が等しいので、その交点が求める点である。"
            ),
        ),
    ]
    return Solution(answer=_graph(features), steps=steps)


# ---------------------------------------------------------------------------
# math.perpendicular_through_point（g1_l43.construction Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.perpendicular_through_point")
def perpendicular_through_point(
    px: object, py: object, lx: object, ly: object, ldx: object, ldy: object, np_: object
) -> Solution:
    """与えられた点を通り、直線に垂直な直線を作図する（g1_l43.construction Lv1）。"""
    p = _pt(px, py)
    lp, ld = _pt(lx, ly), _pt(ldx, ldy)
    name = str(np_)
    coeffs = _line_coeffs(p, (-ld[1], ld[0]))
    features = [
        Feature(kind="through_point", srepr=_srepr_pt(p), display=f"点{name}"),
        Feature(
            kind="perpendicular_line",
            srepr=sympy.srepr(coeffs),
            display=f"点{name}を通る垂線（かいた直線）",
        ),
    ]
    return Solution(answer=_graph(features), steps=_perpendicular_steps(p, name, coeffs))


# ---------------------------------------------------------------------------
# math.foot_and_point_line_distance（g1_l43.construction Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.foot_and_point_line_distance")
def foot_and_point_line_distance(
    px: object, py: object, lx: object, ly: object, ldx: object, ldy: object,
    np_: object, nh: object,
) -> Solution:
    """垂線の足と、点と直線の距離を表す線分を作図で求める（g1_l43.construction Lv2）。"""
    p = _pt(px, py)
    lp, ld = _pt(lx, ly), _pt(ldx, ldy)
    name, hname = str(np_), str(nh)
    coeffs = _line_coeffs(p, (-ld[1], ld[0]))
    h = _foot(p, lp, ld)
    features = [
        Feature(
            kind="perpendicular_line",
            srepr=sympy.srepr(coeffs),
            display=f"点{name}を通る垂線（かいた直線）",
        ),
        Feature(kind="foot", srepr=_srepr_pt(h), display=f"垂線の足{hname}"),
    ]
    steps = _perpendicular_steps(p, name, coeffs) + [
        Step(
            op="mark_foot_of_perpendicular",
            args=[hname],
            result_srepr=_srepr_pt(h),
            result_display=f"垂線の足{hname}",
            narration="ひいた垂線ともとの直線との交点に印をつける。これが垂線の足である。",
        ),
        Step(
            op="draw_distance_segment",
            args=[name, hname],
            result_srepr=_srepr_pt(h),
            result_display=f"線分{name}{hname}",
            narration="もとの点と垂線の足を結ぶ線分が、点と直線との距離を表す線分である。",
        ),
    ]
    return Solution(answer=_graph(features), steps=steps)


# ---------------------------------------------------------------------------
# math.locus_equidistant_two_points（g1_l44.construction Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.locus_equidistant_two_points")
def locus_equidistant_two_points(
    ax: object, ay: object, bx: object, by: object, na: object, nb: object
) -> Solution:
    """2点から等距離にある点の集まりを、基本作図1つで求める（g1_l44.construction Lv2）。"""
    a, b = _pt(ax, ay), _pt(bx, by)
    na_s, nb_s = str(na), str(nb)
    mid = _midpoint(a, b)
    coeffs = _line_from_normal(mid, (b[0] - a[0], b[1] - a[1]))
    features = [
        Feature(kind="midpoint", srepr=_srepr_pt(mid), display=f"線分{na_s}{nb_s}の中点"),
        Feature(
            kind="perpendicular_bisector",
            srepr=sympy.srepr(coeffs),
            display=f"{na_s}、{nb_s}から等距離の点の集まり＝線分{na_s}{nb_s}の垂直二等分線",
        ),
    ]
    steps = [
        Step(
            op="choose_basic_construction",
            args=[na_s, nb_s],
            result_srepr=sympy.srepr(sympy.Tuple()),
            result_display="垂直二等分線の作図",
            narration=(
                "二つの点から等しい距離にある点の集まりは、その二点を結ぶ線分の"
                "垂直二等分線だから、使う基本作図を垂直二等分線に決める。"
            ),
        ),
        *_perp_bisector_steps(a, b, na_s, nb_s, coeffs),
    ]
    return Solution(answer=_graph(features), steps=steps)


# ---------------------------------------------------------------------------
# math.circumcenter_of_three_points（g1_l44.construction Lv3）
# ---------------------------------------------------------------------------
@register_solver("math.circumcenter_of_three_points")
def circumcenter_of_three_points(
    ax: object, ay: object, bx: object, by: object, cx: object, cy: object,
    na: object, nb: object, nc: object,
) -> Solution:
    """3点から等距離にある点を、垂直二等分線2本の交点として求める（g1_l44 Lv3）。"""
    a, b, c = _pt(ax, ay), _pt(bx, by), _pt(cx, cy)
    na_s, nb_s, nc_s = str(na), str(nb), str(nc)
    mid_ab = _midpoint(a, b)
    mid_bc = _midpoint(b, c)
    bis_ab = _line_from_normal(mid_ab, (b[0] - a[0], b[1] - a[1]))
    bis_bc = _line_from_normal(mid_bc, (c[0] - b[0], c[1] - b[1]))
    p = _intersect(bis_ab, bis_bc)
    features = [
        Feature(
            kind="perpendicular_bisector_first",
            srepr=sympy.srepr(bis_ab),
            display=f"線分{na_s}{nb_s}の垂直二等分線（かいた1本目）",
        ),
        Feature(
            kind="perpendicular_bisector_second",
            srepr=sympy.srepr(bis_bc),
            display=f"線分{nb_s}{nc_s}の垂直二等分線（かいた2本目）",
        ),
        Feature(
            kind="point",
            srepr=_srepr_pt(p),
            display="点P（2本の垂直二等分線の交点）",
        ),
    ]
    first = _perp_bisector_steps(a, b, na_s, nb_s, bis_ab)
    second = _perp_bisector_steps(b, c, nb_s, nc_s, bis_bc)
    steps = [
        first[0],
        first[1],
        first[2],
        Step(
            op="arc_from_third_point",
            args=[nc_s],
            result_srepr=_srepr_pt(c),
            result_display=f"点{nc_s}を中心とする弧",
            narration=f"次の組についても、点{nc_s}を中心に同じ要領で弧をかく。",
        ),
        Step(
            op="arc_from_shared_point",
            args=[nb_s],
            result_srepr=_srepr_pt(b),
            result_display=f"点{nb_s}を中心とする同じ半径の弧（先の弧との交点2つ）",
            narration="組のもう一方の点を中心に、同じ半径で弧をかいて交点を得る。",
        ),
        Step(
            op="draw_second_perpendicular_bisector",
            args=[nb_s, nc_s],
            result_srepr=sympy.srepr(bis_bc),
            result_display=second[2].result_display,
            narration="その二つの交点を通る直線をひき、二本目の垂直二等分線とする。",
        ),
        Step(
            op="intersect_two_bisectors",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="2本の垂直二等分線の交点",
            narration="二本の垂直二等分線の交点をとる。",
        ),
        Step(
            op="mark_result_point",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="点P",
            narration="その交点はどの点からの距離も等しいので、求める点である。",
        ),
    ]
    return Solution(answer=_graph(features), steps=steps)


# ---------------------------------------------------------------------------
# math.point_on_side_equidistant_from_two_sides（g1_l44.construction Lv4）
# ---------------------------------------------------------------------------
@register_solver("math.point_on_side_equidistant_from_two_sides")
def point_on_side_equidistant_from_two_sides(
    ax: object, ay: object, ux: object, uy: object, vx: object, vy: object,
    na: object, nb: object, nc: object,
) -> Solution:
    """三角形の1辺上にあり、他の2辺から等距離にある点を求める（g1_l44 Lv4・誘導なし）。"""
    a = _pt(ax, ay)
    u, v = _pt(ux, uy), _pt(vx, vy)
    na_s, nb_s, nc_s = str(na), str(nb), str(nc)
    b = (a[0] + u[0], a[1] + u[1])
    c = (a[0] + v[0], a[1] + v[1])
    w = _bisector_dir(u, v)
    bis = _line_coeffs(a, w)
    side = _line_coeffs(b, (c[0] - b[0], c[1] - b[1]))
    p = _intersect(bis, side)
    features = [
        Feature(
            kind="angle_bisector",
            srepr=sympy.srepr(bis),
            display=f"∠{nb_s}{na_s}{nc_s}の二等分線（かいた半直線）",
        ),
        Feature(
            kind="point",
            srepr=_srepr_pt(p),
            display=f"点P（∠{nb_s}{na_s}{nc_s}の二等分線と辺{nb_s}{nc_s}との交点）",
        ),
    ]
    steps = [
        Step(
            op="plan_choose_construction",
            args=[na_s],
            result_srepr=sympy.srepr(sympy.Tuple()),
            result_display="角の二等分線の作図",
            narration=(
                "二辺から等しい距離にある点の集まりは、その二辺がつくる角の二等分線"
                "だから、頂点の角の二等分線をひく方針を立てる。"
            ),
        ),
        *_angle_bisector_steps(a, na_s, nb_s, nc_s, bis),
        Step(
            op="intersect_with_opposite_side",
            args=[nb_s, nc_s],
            result_srepr=_srepr_pt(p),
            result_display=f"二等分線と辺{nb_s}{nc_s}との交点",
            narration="ひいた二等分線と、向かい合う辺との交点をとる。",
        ),
        Step(
            op="mark_result_point",
            args=[],
            result_srepr=_srepr_pt(p),
            result_display="点P",
            narration="その交点は辺の上にあり、二辺までの距離も等しいので、求める点である。",
        ),
    ]
    return Solution(answer=_graph(features), steps=steps)


__all__ = [
    "perpendicular_bisector_of_segment",
    "equidistant_point_on_line",
    "angle_bisector_of_angle",
    "equidistant_point_from_two_sides",
    "perpendicular_through_point",
    "foot_and_point_line_distance",
    "locus_equidistant_two_points",
    "circumcenter_of_three_points",
    "point_on_side_equidistant_from_two_sides",
]
