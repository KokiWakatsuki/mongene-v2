"""三平方の定理の利用（form=find_value / knowledge・C10 の g3_l53〜l56）。

g3_l53（平面図形）・g3_l54（座標平面）・g3_l55（空間図形）・g3_l56（表面上の最短距離）の
find_value と、g3_l53.knowledge Lv1（特別な直角三角形の辺の比）を1つのモジュールに集約する。

## 新 solver ゼロ

三平方の利用で必要な計算は2種類しかないので、既存 solver をそのまま呼ぶ
（`word_problem_pythagorean.py` と同じ方針・同じ2経路）。

  - **斜辺を求める**（直角をはさむ2辺 → 斜辺）: `math.pythagorean_hypotenuse`
  - **直角をはさむ辺を求める**（斜辺と一方の辺 → 他方の辺）: 中学生が書く立式
    「x² + (既知の辺)² = (斜辺)²」を `math.solve_quadratic`
    （mode=`solve_product_form_positive_root`＝正の解を1つ選ぶ）に渡す。
    長さは正の数だから正の解がちょうど1つ選ばれる。
  - **x 軸上の等距離点**（g3_l54 Lv3）: 「(x−a)²+b² = (x−c)²+d²」を
    `math.solve_linear_equation`（mode=`pythagorean_equidistant_point_x_axis`）に渡す。
    両辺を展開すると x² が消えて一次方程式になるので、既存の一次方程式ソルバで解ける。

面積・体積・中心角は solver の出力を sympy でそのまま合成する。
`sympy.nsimplify(文字列)` は偽の閉形式を返す既知の罠なので使わない。

## level_sep（fp は steps の op 列なので、同一 family 内で必ず段数・op 名を変える）

  - g3_l53.find_value: Lv2=2手（読み取る→三平方1回）／Lv3=3手（垂線→三平方→面積）／
    Lv4=4手（角を読む→特別な直角三角形の比で表す→和の方程式→解く）
  - g3_l54.find_value: Lv2=2手（座標の差→距離）／Lv3=3手（文字でおく→方程式→解く）
  - g3_l55.find_value: Lv2=2手（底面の対角線→立体の対角線）／Lv3=3手（対角線の半分→
    高さ→体積）／Lv4=4手（垂線の足→重心までの距離→高さ→体積）
  - g3_l56.find_value: Lv2=2手（2面を開く→三平方）／Lv4=3手（側面を展開→二等辺三角形→
    三平方）

## params は「本文に出ている値」だけ

`numbers` は場面文が読者に見せている長さ・角・座標と、問いの型（どの辺を求めるか）だけ。
答え（斜辺・高さ・面積・体積・最短距離・座標）は入っていない。頂点名は `slots` に置く。
checker は同じ `SOLVE_BUILDERS` を通して solver を呼び直す。

## narration に数字を書かない

hints は steps の narration そのものなので、narration に数字があると G-Q5t が
「解答由来の値が漏洩」と誤検出する（数え上げの語は漢数字で書く）。値は
`result_display` にだけ置く（result_display は explanation 専用で漏洩検査の対象外）。
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    GraphAnswer,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.core.verify.answer_size import answer_is_too_big, limits_for
from engine.packs.math.recipes.pythagorean import (
    usable_hypotenuse_leg_pairs,
    usable_leg_pairs,
)
from engine.packs.math.visuals.graph import (
    render_coordinate_triangle_solution_svg,
    tick_labels_from_params,
)

RECIPE_NAME = "math.pythagorean_find_value"
KNOWLEDGE_RECIPE_NAME = "math.special_right_triangle_ratio"

_FIND_VALUE_CONCEPTS = [
    "pythagorean.missing_side_in_right_triangle",
    "pythagorean.isosceles_height_and_area",
    "pythagorean.height_from_special_angles",
    "pythagorean.coordinate_distance",
    "pythagorean.equidistant_point_on_x_axis",
    "pythagorean.box_diagonal",
    "pythagorean.square_pyramid_height_volume",
    "pythagorean.regular_tetrahedron_height_volume",
    "pythagorean.box_surface_shortest_path",
    "pythagorean.cone_surface_shortest_path",
]
_KNOWLEDGE_CONCEPTS = ["pythagorean.special_right_triangle_ratio"]

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 垂線の足に使う点名（三角形の頂点名と重ならないものを引く）。
_FOOT_LETTERS = ["H", "K", "L", "M", "N", "P", "Q", "R"]
# 正の解をちょうど1つ選ぶ mode（長さは正の数）。g3_l29/l30 の図形立式と同じ経路。
_POSITIVE_ROOT_MODE = "solve_product_form_positive_root"
_EQUIDISTANT_MODE = "pythagorean_equidistant_point_x_axis"
_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


# ---------------------------------------------------------------------------
# 表示（√ 表記・`*` 除去）。nsimplify は使わない（偽の閉形式を返す罠）。
# ---------------------------------------------------------------------------
def _fmt(value: sympy.Expr, unit: str = "") -> str:
    body = _SQRT_RE.sub(r"√\1", sympy.sstr(sympy.together(value))).replace("*", "")
    return f"{body} {unit}" if unit else body


def _symbolic(value: sympy.Expr, display: str) -> SymbolicAnswer:
    return SymbolicAnswer(srepr=sympy.srepr(value), display=display)


def _step(op: str, narration: str, value: sympy.Expr | None = None, unit: str = "", phrase: str = "") -> Step:
    """1手＝1 Step。値は result_display にだけ置く（narration に数字を書かない）。"""
    if value is None:
        return Step(op=op, args=[], result_srepr="", result_display=phrase, narration=narration)
    return Step(
        op=op, args=[], result_srepr=sympy.srepr(value),
        result_display=_fmt(value, unit), narration=narration,
    )


# ---------------------------------------------------------------------------
# 既存 solver の薄いラッパ（答えの値だけを取り出す）
# ---------------------------------------------------------------------------
def _hypotenuse(leg_a: sympy.Expr | int, leg_b: sympy.Expr | int) -> sympy.Expr:
    """直角をはさむ2辺 → 斜辺（`math.pythagorean_hypotenuse` に委ねる）。"""
    solver = REGISTRY.solver("math.pythagorean_hypotenuse")
    sol = cast(Solution, solver(leg_a, leg_b))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Expr, sympy.sympify(sol.answer.srepr))


def _leg(hypotenuse: sympy.Expr | int, known_leg_squared: sympy.Expr | int) -> sympy.Expr:
    """斜辺と一方の辺の二乗 → 他方の辺（`math.solve_quadratic` の正の解に委ねる）。

    中学生が実際に書く立式「x² + (既知の辺)² = (斜辺)²」をそのまま渡す。専用の
    「leg solver」を新設しないための経路（`word_problem_pythagorean` と同じ）。
    """
    hyp_squared = sympy.expand(sympy.sympify(hypotenuse) ** 2)
    known = sympy.sympify(known_leg_squared)
    solver = REGISTRY.solver("math.solve_quadratic")
    eq = f"x**2 + {sympy.sstr(known)} = {sympy.sstr(hyp_squared)}"
    sol = cast(Solution, solver(eq, _POSITIVE_ROOT_MODE))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Expr, sympy.sympify(sol.answer.srepr))


def _equidistant_x(x1: int, y1: int, x2: int, y2: int) -> sympy.Expr:
    """PA=PB となる x 軸上の点の x 座標（`math.solve_linear_equation` に委ねる）。"""
    solver = REGISTRY.solver("math.solve_linear_equation")
    eq = f"(x - ({x1}))**2 + ({y1})**2 = (x - ({x2}))**2 + ({y2})**2"
    sol = cast(Solution, solver(eq, _EQUIDISTANT_MODE))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Expr, sympy.sympify(sol.answer.srepr))


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「本文の値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_right_triangle_missing_side(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53.find_value Lv2: 直角三角形の2辺から残り1辺を三平方1回で求める。"""
    role = str(numbers["role"])
    known_a = int(numbers["known_a"])
    known_b = int(numbers["known_b"])
    if role == "hypotenuse":
        result = _hypotenuse(known_a, known_b)
        find_narration = (
            "直角をはさむ二辺の長さの二乗の和が斜辺の長さの二乗に等しいという"
            "三平方の定理を使って、斜辺の長さを求める。"
        )
    else:  # role == "leg": known_a が斜辺、known_b が直角をはさむ一方の辺
        result = _leg(known_a, known_b * known_b)
        find_narration = (
            "直角をはさむ二辺の長さの二乗の和が斜辺の長さの二乗に等しいという"
            "三平方の定理から方程式をつくり、直角をはさむもう一方の辺の長さを求める。"
        )
    return [
        Solution(
            answer=_symbolic(result, _fmt(result, "cm")),
            steps=[
                _step(
                    "identify_right_triangle_sides",
                    "直角三角形の三つの辺のうち、どれが斜辺で、どの辺の長さがわかっていて、"
                    "どの辺の長さを求めるのかを読み取る。",
                    phrase=(
                        f"わかっている辺 {known_a}cm と {known_b}cm"
                        if role == "hypotenuse"
                        else f"斜辺 {known_a}cm、わかっている辺 {known_b}cm"
                    ),
                ),
                _step("apply_pythagorean_theorem", find_narration, result, "cm"),
            ],
        )
    ]


def solve_isosceles_height_area(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53.find_value Lv3: 頂点から底辺に垂線を引き、高さと面積を多段で求める。"""
    equal_side = int(numbers["equal_side"])
    base = int(numbers["base"])
    half_base = sympy.Integer(base // 2)
    height = _leg(equal_side, half_base**2)
    area = cast(sympy.Expr, sympy.Rational(1, 2) * base * height)
    result = sympy.Tuple(height, area)
    display = f"高さ {_fmt(height, 'cm')}、面積 {_fmt(area, 'cm²')}"
    return [
        Solution(
            answer=_symbolic(result, display),
            steps=[
                _step(
                    "split_base_at_foot_of_perpendicular",
                    "頂点から底辺に垂線を引くと、二つの合同な直角三角形に分けられるから、"
                    "垂線の足は底辺の中点になり、直角をはさむ一方の辺の長さは底辺の長さの半分になる。",
                    half_base, "cm",
                ),
                _step(
                    "apply_pythagorean_theorem",
                    "等しい長さの辺を斜辺、いま求めた長さを直角をはさむ一方の辺とする直角三角形で、"
                    "三平方の定理から垂線の長さ、すなわち高さを求める。",
                    height, "cm",
                ),
                _step(
                    "compute_triangle_area",
                    "底辺の長さと、いま求めた高さの積の半分をとって、三角形の面積を求める。",
                    area, "cm²",
                ),
            ],
        )
    ]


# 特別な直角三角形の、角の大きさ → その角に対する「底辺方向の長さ／高さ」の比（コタンジェント）。
# 30-60-90 と 45-45-90 の辺の比そのもの（無理数を sympy で厳密に持つ）。
def _cotangent(angle_deg: int) -> sympy.Expr:
    return cast(sympy.Expr, sympy.cot(sympy.pi * sympy.Integer(angle_deg) / 180))


def solve_height_from_special_angles(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53.find_value Lv4: 底辺の両端の角が特別な角のとき、垂線の長さを逆算する。

    垂線の足で分けられた底辺の二つの部分は、それぞれ特別な直角三角形の辺の比から
    高さの定数倍で表せる。その和が底辺に等しいという方程式を解いて高さを求める。
    """
    base = int(numbers["base"])
    angle_b = int(numbers["angle_b"])
    angle_c = int(numbers["angle_c"])
    ratio_sum = cast(sympy.Expr, sympy.simplify(_cotangent(angle_b) + _cotangent(angle_c)))
    height = cast(sympy.Expr, sympy.radsimp(sympy.simplify(sympy.Integer(base) / ratio_sum)))
    return [
        Solution(
            answer=_symbolic(height, _fmt(height, "cm")),
            steps=[
                _step(
                    "read_base_angles",
                    "頂点から底辺に垂線を引くと二つの直角三角形ができるから、底辺の両端の角の"
                    "大きさから、それぞれがどの特別な直角三角形にあたるかを読み取る。",
                    phrase=f"{angle_b}° と {angle_c}° の直角三角形",
                ),
                _step(
                    "express_segments_by_special_ratio",
                    "それぞれの特別な直角三角形の辺の比を使って、垂線の足で分けられた底辺の"
                    "二つの部分の長さを、垂線の長さを表す文字の定数倍として表す。",
                    phrase=(
                        f"それぞれ {_fmt(_cotangent(angle_b))}h と "
                        f"{_fmt(_cotangent(angle_c))}h"
                    ),
                ),
                _step(
                    "set_up_equation_for_base",
                    "分けられた二つの部分の長さの和が底辺の長さに等しいことから、"
                    "垂線の長さを表す文字についての方程式をつくる。",
                    phrase=f"{_fmt(ratio_sum)}h = {base}",
                ),
                _step(
                    "solve_for_height",
                    "その方程式を解いて、分母に根号が残らないように直し、垂線の長さを求める。",
                    height, "cm",
                ),
            ],
        )
    ]


def solve_coordinate_distance(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l54.find_value Lv2: 2点の座標差を辺として三平方で距離を求める。"""
    x1, y1 = int(numbers["x1"]), int(numbers["y1"])
    x2, y2 = int(numbers["x2"]), int(numbers["y2"])
    dx, dy = abs(x2 - x1), abs(y2 - y1)
    distance = _hypotenuse(dx, dy)
    return [
        Solution(
            answer=_symbolic(distance, _fmt(distance)),
            steps=[
                _step(
                    "compute_coordinate_differences",
                    "二つの点の x 座標の差と y 座標の差を求め、座標軸に平行な二辺を"
                    "直角をはさむ二辺とする直角三角形をとらえる。",
                    phrase=f"x の差 {dx}、y の差 {dy}",
                ),
                _step(
                    "apply_pythagorean_theorem_for_distance",
                    "その直角三角形で、線分は斜辺にあたるから、三平方の定理から"
                    "二点間の距離を求める。",
                    distance,
                ),
            ],
        )
    ]


def solve_equidistant_point_on_x_axis(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l54.find_value Lv3: 2点から等しい距離にある x 軸上の点の座標を逆算する。"""
    x1, y1 = int(numbers["x1"]), int(numbers["y1"])
    x2, y2 = int(numbers["x2"]), int(numbers["y2"])
    t = _equidistant_x(x1, y1, x2, y2)
    point = sympy.Tuple(t, sympy.Integer(0))
    display = f"({_fmt(t)}, 0)"
    return [
        Solution(
            answer=_symbolic(point, display),
            steps=[
                _step(
                    "express_distances_with_unknown",
                    "求める点は x 軸上にあるから、その x 座標を文字でおき、二つの点までの"
                    "距離の二乗を、三平方の定理を使ってその文字の式で表す。",
                    phrase="（x の差）² ＋（y の差）² の形で表す",
                ),
                _step(
                    "set_up_equation_from_equal_distances",
                    "二つの距離が等しいことは、距離の二乗どうしが等しいことと同じだから、"
                    "その等式を方程式とみる。",
                    phrase="（一方の距離）² =（もう一方の距離）²",
                ),
                _step(
                    "solve_linear_equation_for_x",
                    "両辺のかっこを展開すると二乗の項が消えて一次方程式になるから、"
                    "これを解いて点の座標を求める。",
                    point,
                ),
            ],
        )
    ]


def solve_box_diagonal(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l55.find_value Lv2: 直方体の対角線の長さを求める。"""
    depth = int(numbers["depth"])
    width = int(numbers["width"])
    height = int(numbers["height"])
    base_diagonal = _hypotenuse(depth, width)
    diagonal = _hypotenuse(base_diagonal, height)
    return [
        Solution(
            answer=_symbolic(diagonal, _fmt(diagonal, "cm")),
            steps=[
                _step(
                    "compute_base_diagonal",
                    "底面の長方形で、となり合う二辺を直角をはさむ二辺とみて、"
                    "三平方の定理から底面の対角線の長さを求める。",
                    base_diagonal, "cm",
                ),
                _step(
                    "apply_pythagorean_theorem_for_solid_diagonal",
                    "底面の対角線と高さを直角をはさむ二辺とする直角三角形をとらえ、"
                    "三平方の定理から直方体の対角線の長さを求める。",
                    diagonal, "cm",
                ),
            ],
        )
    ]


def solve_square_pyramid_height_volume(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l55.find_value Lv3: 正四角錐の高さと体積を多段で求める。"""
    base_edge = int(numbers["base_edge"])
    lateral_edge = int(numbers["lateral_edge"])
    half_diagonal = cast(sympy.Expr, sympy.Rational(1, 2) * _hypotenuse(base_edge, base_edge))
    height = _leg(lateral_edge, sympy.expand(half_diagonal**2))
    volume = cast(sympy.Expr, sympy.Rational(1, 3) * base_edge * base_edge * height)
    result = sympy.Tuple(height, volume)
    display = f"高さ {_fmt(height, 'cm')}、体積 {_fmt(volume, 'cm³')}"
    return [
        Solution(
            answer=_symbolic(result, display),
            steps=[
                _step(
                    "compute_half_base_diagonal",
                    "底面は正方形だから、となり合う二辺を直角をはさむ二辺とみて三平方の定理で"
                    "対角線の長さを求める。頂点から底面に下ろした垂線の足は対角線の交点だから、"
                    "その半分が直角をはさむ一方の辺になる。",
                    half_diagonal, "cm",
                ),
                _step(
                    "apply_pythagorean_theorem_for_apex_height",
                    "側辺を斜辺、いま求めた長さを直角をはさむ一方の辺とする直角三角形で、"
                    "三平方の定理から角錐の高さを求める。",
                    height, "cm",
                ),
                _step(
                    "compute_pyramid_volume",
                    "底面の正方形の面積を求め、角錐の体積は底面積と高さの積の三分の一で"
                    "求められることを使って体積を求める。",
                    volume, "cm³",
                ),
            ],
        )
    ]


def solve_regular_tetrahedron_height_volume(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l55.find_value Lv4: 正四面体の高さと体積を、垂線の足の位置から構想して求める。"""
    edge = int(numbers["edge"])
    # 底面の正三角形の中線（＝高さ）。斜辺が1辺、直角をはさむ一方が1辺の半分。
    median = _leg(edge, sympy.Rational(edge, 2) ** 2)
    # 垂線の足は底面の重心。重心は中線を頂点側から2:1に分けるので、頂点までの距離は中線の2/3。
    center_to_vertex = cast(sympy.Expr, sympy.Rational(2, 3) * median)
    height = _leg(edge, sympy.expand(center_to_vertex**2))
    base_area = cast(sympy.Expr, sympy.Rational(1, 2) * edge * median)
    volume = cast(sympy.Expr, sympy.Rational(1, 3) * base_area * height)
    result = sympy.Tuple(height, volume)
    display = f"高さ {_fmt(height, 'cm')}、体積 {_fmt(volume, 'cm³')}"
    return [
        Solution(
            answer=_symbolic(result, display),
            steps=[
                _step(
                    "locate_foot_of_perpendicular_at_centroid",
                    "頂点から底面に下ろした垂線の足は、底面の正三角形の三つの頂点から等しい距離に"
                    "ある点、すなわち中線が交わる点になることをとらえる。",
                    phrase="垂線の足は底面の中線の交点",
                ),
                _step(
                    "compute_distance_from_centroid_to_vertex",
                    "底面の正三角形の中線の長さを三平方の定理で求め、中線が交わる点は中線を"
                    "頂点の側から二対一に分けることから、その点と底面の頂点との距離を求める。",
                    center_to_vertex, "cm",
                ),
                _step(
                    "apply_pythagorean_theorem_for_tetrahedron_height",
                    "正四面体の辺を斜辺、いま求めた距離を直角をはさむ一方の辺とする直角三角形で、"
                    "三平方の定理から高さを求める。",
                    height, "cm",
                ),
                _step(
                    "compute_pyramid_volume",
                    "底面の正三角形の面積を、底辺と中線の長さから求め、角錐の体積は底面積と"
                    "高さの積の三分の一で求められることを使って体積を求める。",
                    volume, "cm³",
                ),
            ],
        )
    ]


def solve_box_surface_shortest_path(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l56.find_value Lv2: 直方体の底面と側面を1面ずつ開いて最短の道のりを求める。"""
    depth = int(numbers["depth"])
    width = int(numbers["width"])
    height = int(numbers["height"])
    # 底面（縦 depth・横 width）と、横 width・高さ height の側面を、長さ width の辺で開く。
    # 開いた図は横 width・縦 (depth + height) の長方形になり、求める道のりはその対角線。
    unfolded_height = sympy.Integer(depth + height)
    shortest = _hypotenuse(width, depth + height)
    return [
        Solution(
            answer=_symbolic(shortest, _fmt(shortest, "cm")),
            steps=[
                _step(
                    "unfold_two_faces_into_one_plane",
                    "表面上の道のりを平面で考えるために、通る二つの面を共有する辺で一つの平面に"
                    "開く。開いた図は、二つの長方形が縦に並んだ一つの長方形になる。",
                    unfolded_height, "cm",
                ),
                _step(
                    "apply_pythagorean_theorem_for_shortest_path",
                    "開いた図で道のりが最も短くなるのは出発点と到着点を結ぶ線分のときだから、"
                    "その線分を斜辺とする直角三角形で三平方の定理を使って長さを求める。",
                    shortest, "cm",
                ),
            ],
        )
    ]


def solve_cone_surface_shortest_path(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l56.find_value Lv4: 円錐の側面をひとまわりして戻る最短の道のりを求める。

    側面を展開したおうぎ形の中心角は、弧の長さが底面の円周に等しいことから
    360×(底面の半径)÷(母線) で決まる。求める道のりは弧の両端を結ぶ線分（弦）で、
    二本の母線とその弦でできる二等辺三角形に垂線を下ろして三平方の定理で求める。
    """
    radius = int(numbers["radius"])
    slant = int(numbers["slant"])
    unit = str(numbers["unit"])
    central_angle = sympy.Rational(360 * radius, slant)
    assert central_angle < 180, f"中心角が 180°以上（弦が最短にならない）: {central_angle}"
    half_angle_rad = sympy.pi * central_angle / 360
    # 二等辺三角形の頂点から弦に下ろした垂線の足までの距離（母線×cos(中心角の半分)）。
    adjacent = cast(sympy.Expr, sympy.simplify(slant * sympy.cos(half_angle_rad)))
    half_chord = _leg(slant, sympy.expand(adjacent**2))
    chord = cast(sympy.Expr, sympy.expand(2 * half_chord))
    return [
        Solution(
            answer=_symbolic(chord, _fmt(chord, unit)),
            steps=[
                _step(
                    "unfold_cone_lateral_surface",
                    "円錐の側面を展開すると、母線を半径とするおうぎ形になる。その弧の長さが"
                    "底面の円周の長さに等しいことから、おうぎ形の中心角の大きさを求める。",
                    cast(sympy.Expr, central_angle), "度",
                ),
                _step(
                    "identify_isosceles_triangle_in_sector",
                    "ひとまわりして戻る最短の道のりは、展開したおうぎ形で弧の両端を結ぶ線分に"
                    "なる。二本の母線とその線分でできる二等辺三角形の頂点から線分に垂線を下ろすと、"
                    "特別な直角三角形ができるので、垂線の足までの長さを求める。",
                    adjacent, unit,
                ),
                _step(
                    "apply_pythagorean_theorem_for_chord",
                    "その直角三角形で三平方の定理を使って線分の長さの半分を求め、"
                    "二倍して最短の道のりを求める。",
                    chord, unit,
                ),
            ],
        )
    ]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "right_triangle_missing_side": solve_right_triangle_missing_side,
    "isosceles_height_area": solve_isosceles_height_area,
    "height_from_special_angles": solve_height_from_special_angles,
    "coordinate_distance": solve_coordinate_distance,
    "equidistant_point_on_x_axis": solve_equidistant_point_on_x_axis,
    "box_diagonal": solve_box_diagonal,
    "square_pyramid_height_volume": solve_square_pyramid_height_volume,
    "regular_tetrahedron_height_volume": solve_regular_tetrahedron_height_volume,
    "box_surface_shortest_path": solve_box_surface_shortest_path,
    "cone_surface_shortest_path": solve_cone_surface_shortest_path,
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FindValueScene:
    """本文と、そこから solve に渡す値。

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す「本文に出ている値」だけの辞書
    （params にそのまま載り、checker が同じ関数へ渡す）。頂点名は `slots` に置く。
    """

    numbers: dict[str, Any]
    statement: str
    slots: dict[str, str] = field(default_factory=dict)


def _draw_from(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _draw_consecutive_labels(count: int, rng: Rng) -> str:
    """連続する count 文字の大文字（"ABC" / "EFGH" …）を引く（多角形・立体の慣例）。"""
    start = int(draw({"int_range": [0, len(_ALPHABET) - count]}, rng))
    return _ALPHABET[start : start + count]


def _draw_foot_label(used: str, rng: Rng) -> str:
    return str(_draw_from([c for c in _FOOT_LETTERS if c not in used], rng))


def _int_range(p: Mapping[str, Any], key: str) -> tuple[int, int]:
    lo, hi = (int(v) for v in p[key]["int_range"])
    return lo, hi


# --- g3_l53 Lv2 -------------------------------------------------------------
def _scene_right_triangle_missing_side(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    """求める辺が教材で扱える形（整数か、根号の中が小さい a√b）になる組だけを引く。

    前は 1〜60 を独立に引いていたので「24cm, 41cm → √2257」のような、
    素因数分解もできない答えが出ていた。
    """
    side_max, radicand_max = int(p["side_max"]), int(p["radicand_max"])
    role = str(draw(["hypotenuse", "leg"], rng))
    if role == "hypotenuse":
        pairs = usable_leg_pairs(side_max, radicand_max)
        known_a, known_b = pairs[int(draw({"int_set": list(range(len(pairs)))}, rng))]
        statement = (
            f"直角をはさむ2辺の長さが {known_a}cm, {known_b}cm である直角三角形の"
            "斜辺の長さを求めよ"
        )
    else:
        pairs = usable_hypotenuse_leg_pairs(side_max, radicand_max)
        known_a, known_b = pairs[int(draw({"int_set": list(range(len(pairs)))}, rng))]
        statement = (
            f"斜辺の長さが {known_a}cm、直角をはさむ1辺の長さが {known_b}cm である"
            "直角三角形の、直角をはさむもう1辺の長さを求めよ"
        )
    return FindValueScene(
        numbers={"role": role, "known_a": known_a, "known_b": known_b},
        statement=statement,
    )


# --- g3_l53 Lv3 -------------------------------------------------------------
@lru_cache(maxsize=8)
def _isosceles_candidates(
    side_lo: int, side_hi: int, base_lo: int, base_hi: int
) -> tuple[tuple[int, int], ...]:
    """(等しい辺, 底辺) の候補列挙。

    底辺は偶数（半分が整数になる）。底辺 < 等辺の二倍（三角形が成り立つ）。
    底辺の二倍 >= 等辺（針のように細い三角形にしない）。等辺 == 底辺 は正三角形として含む。
    """
    out: list[tuple[int, int]] = []
    for equal_side in range(side_lo, side_hi + 1):
        for base in range(base_lo + base_lo % 2, base_hi + 1, 2):
            if base < 2 * equal_side and 2 * base >= equal_side:
                out.append((equal_side, base))
    return tuple(out)


def _scene_isosceles_height_area(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    side_lo, side_hi = _int_range(p, "equal_side_domain")
    base_lo, base_hi = _int_range(p, "base_domain")
    equal_side, base = _draw_from(
        list(_isosceles_candidates(side_lo, side_hi, base_lo, base_hi)), rng
    )
    tri = _draw_consecutive_labels(3, rng)
    foot = _draw_foot_label(tri, rng)
    a, b, c = tri[0], tri[1], tri[2]
    if equal_side == base:
        head = f"1辺の長さが {equal_side}cm の正三角形{tri}"
    else:
        head = (
            f"{a}{b}={a}{c}={equal_side}cm、{b}{c}={base}cm の二等辺三角形{tri}"
        )
    statement = (
        f"{head}について、頂点{a}から辺{b}{c}に垂線{a}{foot}を引く。"
        f"線分{a}{foot}の長さと、三角形{tri}の面積を求めよ"
    )
    return FindValueScene(
        numbers={"equal_side": equal_side, "base": base},
        statement=statement,
        slots={"triangle": tri, "foot": foot},
    )


# --- g3_l53 Lv4 -------------------------------------------------------------
def _scene_height_from_special_angles(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    base = int(draw(p["base_domain"], rng))
    angle_b = int(draw(p["angle_domain"], rng))
    angle_c = int(draw(p["angle_domain"], rng))
    tri = _draw_consecutive_labels(3, rng)
    foot = _draw_foot_label(tri, rng)
    a, b, c = tri[0], tri[1], tri[2]
    statement = (
        f"三角形{tri}で、∠{b}={angle_b}°、∠{c}={angle_c}°、辺{b}{c}={base}cm である。"
        f"頂点{a}から辺{b}{c}に垂線{a}{foot}を引くとき、線分{a}{foot}の長さを求めよ"
    )
    return FindValueScene(
        numbers={"base": base, "angle_b": angle_b, "angle_c": angle_c},
        statement=statement,
        slots={"triangle": tri, "foot": foot},
    )


# --- g3_l54 Lv2 -------------------------------------------------------------
def _scene_coordinate_distance(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    for _ in range(200):
        x1 = int(draw(p["coord_domain"], rng))
        y1 = int(draw(p["coord_domain"], rng))
        x2 = int(draw(p["coord_domain"], rng))
        y2 = int(draw(p["coord_domain"], rng))
        # 座標軸に平行な線分（差の一方が 0）は直角三角形ができず題材が退化する。
        if x1 != x2 and y1 != y2:
            break
    else:  # pragma: no cover - 200回すべて退化することは実質ない
        raise ValueError("_scene_coordinate_distance: 有効な2点を構成できず")
    labels = _draw_consecutive_labels(2, rng)
    pa, pb = labels[0], labels[1]
    statement = (
        f"座標平面上の2点{pa}({x1}, {y1}), {pb}({x2}, {y2})の間の距離{pa}{pb}を求めよ"
    )
    return FindValueScene(
        numbers={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        statement=statement,
        slots={"points": labels},
    )


# --- g3_l54 Lv3 -------------------------------------------------------------
@lru_cache(maxsize=8)
def _equidistant_candidates(lo: int, hi: int) -> tuple[tuple[int, int, int, int], ...]:
    """PA=PB となる x 軸上の点の x 座標が整数になる (x1, y1, x2, y2) の候補列挙。

    - x1 == x2 だと条件を満たす点が無い（または無数にある）ので除く。
    - y1² == y2² だと二乗の項が両辺で打ち消し合って答えが2点の x 座標の中点に潰れ、
      三平方の定理を使わずに解けてしまうので除く（Lv3＝応用の狙いから外れる）。
    """
    out: list[tuple[int, int, int, int]] = []
    for x1 in range(lo, hi + 1):
        for x2 in range(lo, hi + 1):
            if x1 == x2:
                continue
            denominator = 2 * (x2 - x1)
            for y1 in range(lo, hi + 1):
                for y2 in range(lo, hi + 1):
                    if y1 * y1 == y2 * y2:
                        continue
                    numerator = x2 * x2 + y2 * y2 - x1 * x1 - y1 * y1
                    if numerator % denominator == 0:
                        out.append((x1, y1, x2, y2))
    return tuple(out)


def _scene_equidistant_point_on_x_axis(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    lo, hi = _int_range(p, "coord_domain")
    x1, y1, x2, y2 = _draw_from(list(_equidistant_candidates(lo, hi)), rng)
    labels = _draw_consecutive_labels(2, rng)
    pa, pb = labels[0], labels[1]
    pp = _draw_foot_label(labels, rng)
    statement = (
        f"座標平面上に2点{pa}({x1}, {y1}), {pb}({x2}, {y2})がある。x軸上に点{pp}をとり、"
        f"{pp}{pa}={pp}{pb} となるようにするとき、点{pp}の座標を求めよ"
    )
    return FindValueScene(
        numbers={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        statement=statement,
        slots={"points": labels, "unknown_point": pp},
    )


# --- g3_l55 Lv2 -------------------------------------------------------------
def _scene_box_diagonal(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    depth = int(draw(p["edge_domain"], rng))
    width = int(draw(p["edge_domain"], rng))
    height = int(draw(p["edge_domain"], rng))
    statement = (
        f"縦 {depth}cm、横 {width}cm、高さ {height}cm の直方体の対角線の長さを求めよ"
    )
    return FindValueScene(
        numbers={"depth": depth, "width": width, "height": height},
        statement=statement,
    )


# --- g3_l55 Lv3 -------------------------------------------------------------
@lru_cache(maxsize=8)
def _square_pyramid_candidates(
    base_lo: int, base_hi: int, lat_lo: int, lat_hi: int, min_height_squared: int
) -> tuple[tuple[int, int], ...]:
    """(底面の1辺, 側辺) の候補列挙。

    底面の1辺は偶数（対角線の半分の二乗が整数になる）・高さの二乗
    (側辺² − 1辺²/2) が正で小さすぎない（つぶれた錐にしない）。
    """
    out: list[tuple[int, int]] = []
    for base_edge in range(base_lo + base_lo % 2, base_hi + 1, 2):
        for lateral_edge in range(lat_lo, lat_hi + 1):
            if lateral_edge**2 - base_edge**2 // 2 >= min_height_squared:
                out.append((base_edge, lateral_edge))
    return tuple(out)


def _scene_square_pyramid_height_volume(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    base_lo, base_hi = _int_range(p, "base_edge_domain")
    lat_lo, lat_hi = _int_range(p, "lateral_edge_domain")
    base_edge, lateral_edge = _draw_from(
        list(
            _square_pyramid_candidates(
                base_lo, base_hi, lat_lo, lat_hi, int(p["min_height_squared"])
            )
        ),
        rng,
    )
    labels = _draw_consecutive_labels(5, rng)
    apex, base_square = labels[0], labels[1:]
    statement = (
        f"底面が1辺 {base_edge}cm の正方形{base_square}で、他の辺の長さがすべて"
        f" {lateral_edge}cm である正四角錐{apex}-{base_square}がある。"
        "この正四角錐の高さと体積を求めよ"
    )
    return FindValueScene(
        numbers={"base_edge": base_edge, "lateral_edge": lateral_edge},
        statement=statement,
        slots={"labels": labels},
    )


# --- g3_l55 Lv4 -------------------------------------------------------------
def _scene_regular_tetrahedron_height_volume(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    edge = int(draw(p["edge_domain"], rng))
    labels = _draw_consecutive_labels(4, rng)
    statement = (
        f"1辺 {edge}cm の正四面体{labels}について、頂点{labels[0]}から底面{labels[1:]}に"
        "下ろした垂線の足の位置を考え、この正四面体の高さと体積を求めよ"
    )
    return FindValueScene(
        numbers={"edge": edge},
        statement=statement,
        slots={"labels": labels},
    )


# --- g3_l56 Lv2 -------------------------------------------------------------
def _scene_box_surface_shortest_path(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    depth = int(draw(p["edge_domain"], rng))
    width = int(draw(p["edge_domain"], rng))
    height = int(draw(p["edge_domain"], rng))
    labels = _draw_consecutive_labels(2, rng)
    start, goal = labels[0], labels[1]
    statement = (
        f"縦 {depth}cm、横 {width}cm、高さ {height}cm の直方体がある。"
        f"底面の頂点{start}から、底面と、横 {width}cm・高さ {height}cm の側面との"
        f"2つの面だけを通って、{start}から最も遠い頂点{goal}まで表面上を進む。"
        f"この2つの面を1つの平面に開いて、{start}から{goal}までの道のりが最も短くなるときの"
        "長さを求めよ"
    )
    return FindValueScene(
        numbers={"depth": depth, "width": width, "height": height},
        statement=statement,
        slots={"points": labels},
    )


# --- g3_l56 Lv4 -------------------------------------------------------------
def _scene_cone_surface_shortest_path(p: Mapping[str, Any], rng: Rng) -> FindValueScene:
    radius = int(draw(p["radius_domain"], rng))
    ratio = int(draw(p["slant_ratio_domain"], rng))
    unit = str(draw(p["unit_domain"], rng))
    slant = radius * ratio
    labels = _draw_consecutive_labels(1, rng)
    point = labels[0]
    statement = (
        f"底面の半径 {radius}{unit}、母線の長さ {slant}{unit} の円錐がある。"
        f"底面の周上の1点{point}から側面をひとまわりして{point}にもどる最短の道のりを、"
        "展開図を用いて求めよ"
    )
    return FindValueScene(
        numbers={"radius": radius, "slant": slant, "unit": unit},
        statement=statement,
        slots={"point": point},
    )


SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], FindValueScene]] = {
    "right_triangle_missing_side": _scene_right_triangle_missing_side,
    "isosceles_height_area": _scene_isosceles_height_area,
    "height_from_special_angles": _scene_height_from_special_angles,
    "coordinate_distance": _scene_coordinate_distance,
    "equidistant_point_on_x_axis": _scene_equidistant_point_on_x_axis,
    "box_diagonal": _scene_box_diagonal,
    "square_pyramid_height_volume": _scene_square_pyramid_height_volume,
    "regular_tetrahedron_height_volume": _scene_regular_tetrahedron_height_volume,
    "box_surface_shortest_path": _scene_box_surface_shortest_path,
    "cone_surface_shortest_path": _scene_cone_surface_shortest_path,
}


# ---------------------------------------------------------------------------
# recipe（find_value 10 セル）
# ---------------------------------------------------------------------------
def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


# 答えが大きすぎたときに引き直す回数。切れたら**最後の組をそのまま使う**
# （生成が失敗して1セル丸ごと消えるより、大きい答えが1問出るほうが軽い）。
# 引き直しが常態化しているセルは `python -m engine.eval.answer_size` が上限超えとして
# 見つけるので、そのときは定義域か上限の宣言を直す。
_ANSWER_SIZE_REDRAWS = 40


def _draw_scene_with_answer_in_range(
    ctx: CellContext, rng: Rng, kind: str
) -> tuple[FindValueScene, Solution]:
    """答えの大きさが上限内になる組を引く（超えたら組み直す）。

    定義域は広いまま、**答えの根号の中・分母・分子**に上限を置く。
    「縦 7cm・横 12cm・高さ 13cm の直方体の対角線 → √362」のような、
    素因数分解もできない答えを消すのがねらい（`EVALUATION.md` D-32）。

    辺を小さくしても根号の中は下がらない（3,4,12 なら √169 = 13 で根号が消え、
    2,2,3 でも √17 は残る）ので、定義域を狭める向きでは直らない。
    """
    p = ctx.spec_level.params
    limits = limits_for(ctx.spec_level)
    scene = solutions = None
    for attempt in range(_ANSWER_SIZE_REDRAWS):
        attempt_rng = rng.spawn(attempt) if attempt else rng
        scene = SCENE_BUILDERS[kind](p, attempt_rng)
        solutions = SOLVE_BUILDERS[kind](scene.numbers)
        assert len(solutions) == 1, f"find_value は小問1つ: {kind}"
        display = str(getattr(solutions[0].answer, "display", "") or "")
        if not answer_is_too_big(display, limits):
            break
    assert scene is not None and solutions is not None
    return scene, solutions[0]


@register_recipe(RECIPE_NAME, provides_concepts=_FIND_VALUE_CONCEPTS)
def pythagorean_find_value_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三平方の定理の利用の求値（g3_l53/l54/l55/l56.find_value・answer-first）。"""
    kind = str(ctx.spec_level.params["scenario_kind"])
    scene, sol = _draw_scene_with_answer_in_range(ctx, rng, kind)
    asked = ctx.spec_level.asked[0] if ctx.spec_level.asked else "value"

    sub_question = SubQuestionMR(
        label="(1)", asked=asked, answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=list(ctx.spec_level.cause_tags),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"scenario_kind": kind, "numbers": scene.numbers, "slots": scene.slots},
        given={"condition": scene.statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
# g3_l53.knowledge Lv1: 特別な直角三角形の辺の比
# ---------------------------------------------------------------------------
# 角の大きさ → その角に**対する**辺の長さ（最も簡単な整数と根号での表し方）。
# 30-60-90 は 1:√3:2、45-45-90 は 1:1:√2。
_SIDE_TOKEN_30_60_90 = {30: "1", 60: "√3", 90: "2"}
_SIDE_TOKEN_45_45_90 = {45: "1", 90: "√2"}
# 妨害選択肢の候補（同じ特別な直角三角形の中で作れる比を決まった順に並べる）。
_RATIO_POOL_30_60_90 = ["1:√3", "1:2", "√3:2", "√3:1", "2:1", "2:√3"]
_RATIO_POOL_45_45_90 = ["1:1", "1:√2", "√2:1"]


def _side_tokens(right_index: int, acute_index: int, acute_angle: int) -> list[str]:
    """各頂点に**対する**辺の長さの表し方を、頂点の並び順に返す。"""
    angles = [0, 0, 0]
    angles[right_index] = 90
    angles[acute_index] = acute_angle
    third = [i for i in range(3) if i not in (right_index, acute_index)][0]
    angles[third] = 90 - acute_angle
    table = _SIDE_TOKEN_45_45_90 if acute_angle == 45 else _SIDE_TOKEN_30_60_90
    return [table[a] for a in angles]


def solve_special_right_triangle_ratio(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53.knowledge Lv1: 指定された2辺の長さの比を、特別な直角三角形の比から答える。"""
    right_index = int(numbers["right_index"])
    acute_index = int(numbers["acute_index"])
    acute_angle = int(numbers["acute_angle"])
    first, second = int(numbers["first_side"]), int(numbers["second_side"])
    tokens = _side_tokens(right_index, acute_index, acute_angle)
    correct = f"{tokens[first]}:{tokens[second]}"
    pool = _RATIO_POOL_45_45_90 if acute_angle == 45 else _RATIO_POOL_30_60_90
    distractors = [r for r in pool if r != correct][:2]
    return [
        Solution(
            answer=ChoiceAnswer(
                correct=correct, distractors=distractors,
                fact_id="pythagorean.special_right_triangle_ratio",
            ),
            steps=[
                Step(
                    op="identify_special_right_triangle", args=[],
                    result_srepr="",
                    result_display=(
                        "45°、45°、90°の直角三角形" if acute_angle == 45
                        else "30°、60°、90°の直角三角形"
                    ),
                    narration="直角三角形の角の大きさから、どちらの特別な直角三角形に"
                    "あたるかを見分ける。",
                ),
                Step(
                    op="recall_side_ratio", args=[],
                    result_srepr=correct, result_display=correct,
                    narration="その特別な直角三角形で決まっている三つの辺の長さの比を"
                    "思い出し、聞かれている二つの辺の比を答える。",
                ),
            ],
        )
    ]


@register_recipe(KNOWLEDGE_RECIPE_NAME, provides_concepts=_KNOWLEDGE_CONCEPTS)
def special_right_triangle_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """特別な直角三角形の辺の比を答える（g3_l53.knowledge Lv1・answer-first）。"""
    p = ctx.spec_level.params
    tri = _draw_consecutive_labels(3, rng)
    right_index = int(draw({"int_set": [0, 1, 2]}, rng))
    acute_index = int(_draw_from([i for i in range(3) if i != right_index], rng))
    acute_angle = int(draw(p["acute_angle_domain"], rng))
    first = int(draw({"int_set": [0, 1, 2]}, rng))
    second = int(_draw_from([i for i in range(3) if i != first], rng))

    numbers = {
        "right_index": right_index, "acute_index": acute_index, "acute_angle": acute_angle,
        "first_side": first, "second_side": second,
    }
    sol = solve_special_right_triangle_ratio(numbers)[0]

    def side_name(i: int) -> str:
        other = [j for j in range(3) if j != i]
        return f"辺{tri[other[0]]}{tri[other[1]]}"

    statement = (
        f"∠{tri[right_index]}=90°、∠{tri[acute_index]}={acute_angle}° である"
        f"直角三角形{tri}について、{side_name(first)}と{side_name(second)}の長さの比を、"
        "最も簡単な整数と根号を使って、この順に表せ"
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=list(ctx.spec_level.cause_tags),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"numbers": numbers, "slots": {"triangle": tri}},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe=KNOWLEDGE_RECIPE_NAME),
    )


__all__ = [
    "KNOWLEDGE_RECIPE_NAME",
    "RECIPE_NAME",
    "SCENE_BUILDERS",
    "SOLVE_BUILDERS",
    "pythagorean_find_value_recipe",
    "solve_special_right_triangle_ratio",
    "special_right_triangle_ratio_recipe",
]


# ---------------------------------------------------------------------------
# g3_l54.graph_table Lv2: 座標平面に2点をとり、直角三角形を把握する
#
# find_value Lv2（2点間の距離を求める）と同じ題材で、問うものが「長さ」ではなく
# **どの直角三角形に落とすか**である点が違う（g3_l55 の断面セルと同じ関係）。
# 答えの図は生徒が描き込むので、問題図は方眼＋与えられた2点まで。
# ---------------------------------------------------------------------------
_COORDINATE_TRIANGLE_CONCEPTS = ["pythagorean.coordinate_right_triangle"]


@register_recipe(
    "math.coordinate_right_triangle", provides_concepts=_COORDINATE_TRIANGLE_CONCEPTS
)
def coordinate_right_triangle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2点を斜辺とする直角三角形をかき、2辺の長さを答える（answer-first）。

    x・y の差がともに 0 でない2点を引く（軸に平行だと三角形にならない）。
    点名は連続する2文字（A,B のように呼ぶ慣例）。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        x1 = int(draw(p["coord_domain"], rng))
        y1 = int(draw(p["coord_domain"], rng))
        x2 = int(draw(p["coord_domain"], rng))
        y2 = int(draw(p["coord_domain"], rng))
        if x1 != x2 and y1 != y2:
            break
    else:  # pragma: no cover - 有界リトライを使い切る確率は無視できる
        raise ValueError("coordinate_right_triangle_recipe: 軸に平行でない2点を引けず")

    start = int(draw({"int_range": [0, len(_ALPHABET) - 2]}, rng))
    label_a, label_b = _ALPHABET[start], _ALPHABET[start + 1]

    sol = cast(
        Solution, REGISTRY.solver("math.coordinate_right_triangle_legs")(x1, y1, x2, y2)
    )
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "pts": [f"({x1}, {y1})", f"({x2}, {y2})"],
        "point_labels": [label_a, label_b],
        # 直角の頂点は solver が決めたものをそのまま渡す（対応表を2か所に持たない）。
        "right_angle_pt": f"({x2}, {y1})",
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
    }
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_coordinate_triangle_solution_svg(params),
    )
    statement = (
        f"座標平面上に2点 {label_a}({x1}, {y1})、{label_b}({x2}, {y2}) をとり、"
        f"線分 {label_a}{label_b} を斜辺とする直角三角形を、直角をはさむ2辺が座標軸に"
        "平行になるようにかき込め。また、その2辺の長さを答えよ"
    )
    visual_plan = VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params) + [label_a, label_b],
        elements=[
            VisualElement(kind="grid", attrs={}),
            VisualElement(kind="axis", attrs={}),
            # 与えられた2点は問題図に出す（答えは直角三角形のほうなので "point_given"）。
            VisualElement(kind="point_given", attrs={}),
        ],
    )
    sub_question = SubQuestionMR(
        label="(1)", asked="draw_graph", answer=answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=list(ctx.spec_level.cause_tags),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0, params=params,
        given={"condition": statement}, sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.coordinate_right_triangle"),
    )
