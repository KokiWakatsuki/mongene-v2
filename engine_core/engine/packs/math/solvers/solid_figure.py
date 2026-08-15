"""空間図形の「計量」（表面積・体積）まわりの独立再計算ソルバ（C8・g1_l51/l52/l53 横展開）。

solver は**問題パラメータだけ**（mode と values の辞書）から答えと steps を導く
（recipe の乱数選択は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C8（g1 空間図形の計量）クラスタの9セルを1つの汎用ソルバに集約する:
  `math.solid_figure_measure(mode, values)` が立体の種類・問う量を mode で切り替えて
  厳密に計算する（mode ごとに steps の op 列を変える＝level_sep）。答えは
  SymbolicAnswer（π を含む厳密値・cm²/cm³ 単位つき表示）。

  mode 一覧（=各セルの signature と対応）:
    l51_direct_surface            : g1_l51.find_value Lv1（角柱・円柱の表面積・直接）
    l51_cone_central_angle        : g1_l51.find_value Lv2（円錐の中心角経由の表面積）
    l51_composite_or_reverse_surface : g1_l51.find_value Lv3（複合立体／逆算の表面積）
    l52_cylinder_volume_substitution : g1_l52.calculation Lv1（円柱の体積・公式代入）
    l52_prism_pyramid_volume_direct  : g1_l52.find_value Lv1（角柱・角錐の体積・直接）
    l52_right_triangle_volume_multistep : g1_l52.find_value Lv2（直角三角形底面・多段）
    l52_composite_or_reverse_volume  : g1_l52.find_value Lv3（複合立体／逆算の体積）
    l53_sphere_direct             : g1_l53.find_value Lv1（球の表面積・体積を直接）
    l53_hemisphere_or_reverse     : g1_l53.find_value Lv2（半球／逆算の表面積）

  answer-first: 半径・母線・高さ等を先に整数で引き、そこから表面積/体積を厳密計算する
  （逆算 variant は「もとの値を使って係数を組み立て、その係数から同じ値が再構成できる」
  恒真な構成＝sector_solve_central_angle と同型）。

narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。π を含む式は `_fmt_pi` で
"n*pi"→"nπ"・裸の "pi"→"π" に整形し、単位（cm²/cm³）を末尾に空白区切りで付す。
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_measure

_PI_STAR_RE = re.compile(r"\*pi")


def _fmt_pi(expr: sympy.Expr, unit: str = "") -> str:
    """π を含む式の表示形（`n*pi`→`nπ`・裸の `pi`→`π`）。単位があれば末尾に空白区切り。"""
    s = _PI_STAR_RE.sub("π", sympy.sstr(expr)).replace("pi", "π").replace("*", "")
    return f"{s} {unit}" if unit else s


def _fmt_plain(expr: sympy.Expr, unit: str = "") -> str:
    """π を含まない値の表示形。単位があれば末尾に空白区切り。

    **有限小数で書ける値は小数で書く。** 量には小数で答えるのが教材の作法で、
    「三角柱の体積 225/2 cm³」は「112.5 cm³」でなければならない
    （底面が直角をはさむ2辺 3cm・5cm の直角三角形＝底面積が 15/2 になる場合）。
    割り切れない値は分数のまま出す（量として書けない形を隠さない）。
    """
    if isinstance(expr, sympy.Rational):
        return f"{fmt_measure(expr)} {unit}" if unit else fmt_measure(expr)
    s = sympy.sstr(expr).replace("*", "")
    return f"{s} {unit}" if unit else s


def _i(v: object) -> sympy.Integer:
    return sympy.Integer(int(str(v)))


# ---------------------------------------------------------------------------
# 底面の面積・周（多角形底面のみ。円は各 mode 内で直接 pi*r**2 を使う）
# ---------------------------------------------------------------------------
def _square_area(edge: sympy.Integer) -> sympy.Expr:
    return edge**2


def _square_perimeter(edge: sympy.Integer) -> sympy.Expr:
    return 4 * edge


def _rect_area(width: sympy.Integer, depth: sympy.Integer) -> sympy.Expr:
    return width * depth


def _rect_perimeter(width: sympy.Integer, depth: sympy.Integer) -> sympy.Expr:
    return 2 * (width + depth)


# ---------------------------------------------------------------------------
# mode = l51_direct_surface（g1_l51.find_value Lv1）
# ---------------------------------------------------------------------------
def _handle_l51_direct_surface(values: Mapping[str, object]) -> Solution:
    shape = str(values["shape"])
    h = _i(values["height"])
    if shape == "square_prism":
        edge = _i(values["edge"])
        base_area = _square_area(edge)
        perimeter = _square_perimeter(edge)
        lateral = perimeter * h
        total = lateral + 2 * base_area
    elif shape == "rect_prism":
        w, d = _i(values["width"]), _i(values["depth"])
        base_area = _rect_area(w, d)
        perimeter = _rect_perimeter(w, d)
        lateral = perimeter * h
        total = lateral + 2 * base_area
    elif shape == "cylinder":
        r = _i(values["radius"])
        base_area = sympy.pi * r**2
        lateral = 2 * sympy.pi * r * h
        total = lateral + 2 * base_area
    else:
        raise ValueError(f"未知の shape: {shape!r}")

    fmt = _fmt_pi if shape == "cylinder" else _fmt_plain
    disp = fmt(total, "cm²")
    srepr = sympy.srepr(total)
    steps = [
        Step(
            op="compute_base_area",
            args=[],
            result_srepr=sympy.srepr(base_area),
            result_display=fmt(base_area, "cm²"),
            narration="底面の形の面積の公式を使って、底面1つ分の面積を求める。",
        ),
        Step(
            op="compute_lateral_area",
            args=[],
            result_srepr=sympy.srepr(lateral),
            result_display=fmt(lateral, "cm²"),
            narration="側面の面積を、（底面の周の長さ、または円周）×（高さ）で求める。",
        ),
        Step(
            op="sum_surface_area",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="底面2つ分の面積と側面の面積を合計して、表面積を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l51_cone_central_angle（g1_l51.find_value Lv2）
# ---------------------------------------------------------------------------
def _handle_l51_cone_central_angle(values: Mapping[str, object]) -> Solution:
    r = _i(values["radius"])
    l = _i(values["slant"])
    central_angle = sympy.Integer(360) * r / l
    lateral = sympy.pi * r * l
    base_area = sympy.pi * r**2
    total = lateral + base_area

    disp = _fmt_pi(total, "cm²")
    srepr = sympy.srepr(total)
    steps = [
        Step(
            op="compute_central_angle_ratio",
            args=[],
            result_srepr=sympy.srepr(central_angle),
            result_display=_fmt_plain(central_angle, "°"),
            narration=(
                "側面のおうぎ形の弧の長さは底面の円周と等しいので、母線を半径とする"
                "円全体に対する割合から、側面のおうぎ形の中心角の大きさを求める。"
            ),
        ),
        Step(
            op="compute_lateral_sector_area",
            args=[],
            result_srepr=sympy.srepr(lateral),
            result_display=_fmt_pi(lateral, "cm²"),
            narration="求めた中心角の割合を使って、側面のおうぎ形の面積を求める。",
        ),
        Step(
            op="compute_base_area",
            args=[],
            result_srepr=sympy.srepr(base_area),
            result_display=_fmt_pi(base_area, "cm²"),
            narration="底面の円の面積を求める。",
        ),
        Step(
            op="sum_surface_area_from_parts",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="側面のおうぎ形の面積と底面の面積を合計して、表面積を求める。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l51_composite_or_reverse_surface（g1_l51.find_value Lv3）
# ---------------------------------------------------------------------------
def _handle_l51_composite_or_reverse_surface(values: Mapping[str, object]) -> Solution:
    variant = str(values["variant"])
    if variant == "hemisphere_cylinder":
        r, h = _i(values["radius"]), _i(values["height"])
        curved = 2 * sympy.pi * r**2
        cyl_lateral = 2 * sympy.pi * r * h
        cyl_bottom = sympy.pi * r**2
        total = curved + cyl_lateral + cyl_bottom
        disp = _fmt_pi(total, "cm²")
        srepr = sympy.srepr(total)
        steps = [
            Step(
                op="identify_overlapping_faces",
                args=[], result_srepr="", result_display="半球の底面と円柱の上面が重なり内部にかくれる",
                narration=(
                    "半球と円柱をぴったり貼り合わせた面（半球の底面＝円柱の上面）は"
                    "立体の内部にかくれるため、表面積には数えないことを確認する。"
                ),
            ),
            Step(
                op="compute_each_face_area",
                args=[], result_srepr=sympy.srepr(curved + cyl_lateral),
                result_display=_fmt_pi(curved, "cm²") + " と " + _fmt_pi(cyl_lateral, "cm²")
                + " と " + _fmt_pi(cyl_bottom, "cm²"),
                narration="半球の曲面・円柱の側面・円柱の底面のそれぞれの面積を求める。",
            ),
            Step(
                op="sum_surface_area_excluding_overlap",
                args=[], result_srepr=srepr, result_display=disp,
                narration="重なって隠れる面を除いた、外に見えている面をすべて合計する。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    if variant == "cylinder_cone":
        r, h, l = _i(values["radius"]), _i(values["height"]), _i(values["slant"])
        cyl_bottom = sympy.pi * r**2
        cyl_lateral = 2 * sympy.pi * r * h
        cone_lateral = sympy.pi * r * l
        total = cyl_bottom + cyl_lateral + cone_lateral
        disp = _fmt_pi(total, "cm²")
        srepr = sympy.srepr(total)
        steps = [
            Step(
                op="identify_overlapping_faces",
                args=[], result_srepr="", result_display="円柱の上面と円錐の底面が重なり内部にかくれる",
                narration=(
                    "円柱と円錐をぴったり重ねた面（円柱の上面＝円錐の底面）は立体の"
                    "内部にかくれるため、表面積には数えないことを確認する。"
                ),
            ),
            Step(
                op="compute_each_face_area",
                args=[], result_srepr=sympy.srepr(cyl_bottom + cyl_lateral),
                result_display=_fmt_pi(cyl_bottom, "cm²") + " と " + _fmt_pi(cyl_lateral, "cm²")
                + " と " + _fmt_pi(cone_lateral, "cm²"),
                narration="円柱の底面・円柱の側面・円錐の側面のそれぞれの面積を求める。",
            ),
            Step(
                op="sum_surface_area_excluding_overlap",
                args=[], result_srepr=srepr, result_display=disp,
                narration="重なって隠れる面を除いた、外に見えている面をすべて合計する。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    if variant == "reverse_cylinder_radius":
        h = _i(values["height"])
        k = _i(values["area_coeff"])  # k = 2r^2 + 2rh（表面積 = kπ）
        disc = h**2 + 2 * k
        r = (-h + sympy.sqrt(disc)) / 2
        srepr = sympy.srepr(r)
        disp = _fmt_plain(r, "cm")
        steps = [
            Step(
                op="form_surface_area_equation",
                args=[], result_srepr="", result_display=f"2πr² + 2πr × {h} = {k}π",
                narration=(
                    "円柱の表面積の公式に、高さと表面積の値をあてはめ、半径 r についての"
                    "方程式をつくる。"
                ),
            ),
            Step(
                op="solve_equation_for_radius",
                args=[], result_srepr=srepr, result_display=disp,
                narration="この方程式を r について解き、正の値を半径として答える。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    raise ValueError(f"未知の variant: {variant!r}")


# ---------------------------------------------------------------------------
# mode = l52_cylinder_volume_substitution（g1_l52.calculation Lv1）
# ---------------------------------------------------------------------------
def _handle_l52_cylinder_volume_substitution(values: Mapping[str, object]) -> Solution:
    r, h = _i(values["radius"]), _i(values["height"])
    volume = sympy.pi * r**2 * h
    disp = _fmt_pi(volume, "cm³")
    srepr = sympy.srepr(volume)
    steps = [
        Step(
            op="substitute_into_volume_formula",
            args=[], result_srepr="", result_display=f"π × {r}² × {h}",
            narration="体積の公式に、与えられた半径と高さの値をそれぞれ代入する。",
        ),
        Step(
            op="evaluate_volume_expression",
            args=[], result_srepr=srepr, result_display=disp,
            narration="代入した式を計算して、体積を求める（円周率はπのままにする）。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l52_prism_pyramid_volume_direct（g1_l52.find_value Lv1）
# ---------------------------------------------------------------------------
def _handle_l52_prism_pyramid_volume_direct(values: Mapping[str, object]) -> Solution:
    shape = str(values["shape"])
    h = _i(values["height"])
    if shape in ("square_prism", "square_pyramid"):
        base_area = _square_area(_i(values["edge"]))
    elif shape in ("rect_prism", "rect_pyramid"):
        base_area = _rect_area(_i(values["width"]), _i(values["depth"]))
    else:
        raise ValueError(f"未知の shape: {shape!r}")
    is_pyramid = shape.endswith("_pyramid")
    volume = (sympy.Rational(1, 3) if is_pyramid else sympy.Integer(1)) * base_area * h

    disp = _fmt_plain(volume, "cm³")
    srepr = sympy.srepr(volume)
    narration2 = (
        "底面積に高さをかけ、さらに 1/3 をかけて、角錐の体積を求める。"
        if is_pyramid else "底面積に高さをかけて、角柱の体積を求める。"
    )
    steps = [
        Step(
            op="compute_base_area",
            args=[], result_srepr=sympy.srepr(base_area), result_display=_fmt_plain(base_area, "cm²"),
            narration="底面の形の面積の公式を使って、底面積を求める。",
        ),
        Step(
            op="apply_volume_formula",
            args=[], result_srepr=srepr, result_display=disp,
            narration=narration2,
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l52_right_triangle_volume_multistep（g1_l52.find_value Lv2）
# ---------------------------------------------------------------------------
def _handle_l52_right_triangle_volume_multistep(values: Mapping[str, object]) -> Solution:
    shape = str(values["shape"])
    p, q, h = _i(values["leg1"]), _i(values["leg2"]), _i(values["height"])
    product = p * q
    base_area = sympy.Rational(product, 2)
    is_pyramid = shape == "right_triangle_pyramid"
    volume = (sympy.Rational(1, 3) if is_pyramid else sympy.Integer(1)) * base_area * h

    disp = _fmt_plain(volume, "cm³")
    srepr = sympy.srepr(volume)
    narration3 = (
        "底面積に高さをかけ、さらに 1/3 をかけて、角錐の体積を求める。"
        if is_pyramid else "底面積に高さをかけて、角柱の体積を求める。"
    )
    steps = [
        Step(
            op="multiply_the_two_legs",
            args=[], result_srepr=sympy.srepr(product), result_display=_fmt_plain(product, "cm²"),
            narration="直角をはさむ2辺の長さをかけ合わせる。",
        ),
        Step(
            op="halve_for_triangle_base_area",
            args=[], result_srepr=sympy.srepr(base_area), result_display=_fmt_plain(base_area, "cm²"),
            narration="直角三角形の面積は長方形の半分なので、かけた値を2でわって底面積を求める。",
        ),
        Step(
            op="apply_volume_formula",
            args=[], result_srepr=srepr, result_display=disp,
            narration=narration3,
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l52_composite_or_reverse_volume（g1_l52.find_value Lv3）
# ---------------------------------------------------------------------------
def _handle_l52_composite_or_reverse_volume(values: Mapping[str, object]) -> Solution:
    variant = str(values["variant"])
    if variant == "cube_pyramid_composite":
        a, h2 = _i(values["edge"]), _i(values["pyramid_height"])
        cube_v = a**3
        pyramid_v = sympy.Rational(1, 3) * a**2 * h2
        total = cube_v + pyramid_v
        disp = _fmt_plain(total, "cm³")
        srepr = sympy.srepr(total)
        steps = [
            Step(
                op="compute_component_volumes",
                args=[], result_srepr=sympy.srepr(sympy.Tuple(cube_v, pyramid_v)),
                result_display=_fmt_plain(cube_v, "cm³") + " と " + _fmt_plain(pyramid_v, "cm³"),
                narration="立方体の部分と正四角錐の部分に分けて、それぞれの体積を求める。",
            ),
            Step(
                op="sum_component_volumes",
                args=[], result_srepr=srepr, result_display=disp,
                narration="2つの部分の体積を合計して、立体全体の体積を求める。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    if variant == "reverse_pyramid_height":
        a = _i(values["edge"])
        k = _i(values["total_volume_coeff"])  # k = a^3 + (1/3)a^2*h2
        h2 = sympy.Integer(3) * (k - a**3) / a**2
        srepr = sympy.srepr(h2)
        disp = _fmt_plain(h2, "cm")
        steps = [
            Step(
                op="form_volume_equation",
                args=[], result_srepr="", result_display=f"{a}³ + {a}² × h / 3 = {k}",
                narration=(
                    "立方体の体積と、高さの分からない正四角錐の体積の公式に、辺の長さと"
                    "全体の体積の値をあてはめ、高さについての方程式をつくる。"
                ),
            ),
            Step(
                op="solve_for_missing_height",
                args=[], result_srepr=srepr, result_display=disp,
                narration="この方程式を高さについて解き、正四角錐の高さを求める。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    raise ValueError(f"未知の variant: {variant!r}")


# ---------------------------------------------------------------------------
# mode = l53_sphere_direct（g1_l53.find_value Lv1）
# ---------------------------------------------------------------------------
def _handle_l53_sphere_direct(values: Mapping[str, object]) -> Solution:
    r = _i(values["radius"])
    unit = str(values.get("unit", "cm"))
    surface = 4 * sympy.pi * r**2
    volume = sympy.Rational(4, 3) * sympy.pi * r**3
    disp = f"表面積 {_fmt_pi(surface, unit + '²')}、体積 {_fmt_pi(volume, unit + '³')}"
    srepr = sympy.srepr(sympy.Tuple(surface, volume))
    steps = [
        # 第1手は variant 中立（半径で与えられても直径で与えられても同じ手）。
        # これを置くことで「与え方」を dup の第2の軸にしても op 列が変わらない
        # ＝G-FP が安定する（BRIEF「★単一パラメータのセルは原理的に通らない」）。
        Step(
            op="read_radius_from_statement",
            args=[], result_srepr="", result_display=f"{r}",
            narration="問題文から球の半径を読み取る（直径で与えられているときは半分にする）。",
        ),
        Step(
            op="apply_sphere_surface_formula",
            args=[], result_srepr=sympy.srepr(surface), result_display=_fmt_pi(surface, "cm²"),
            # narration に数字を書かない（鉄則）。"4πr²" の ² が答え表示の "cm²" 由来の
            # トークン '2' と衝突し、G-Q5t が 120seed 中114件を漏洩と判定していた。
            narration="球の表面積の公式に半径の値をあてはめて計算する（半径の平方に比例する）。",
        ),
        Step(
            op="apply_sphere_volume_formula",
            args=[], result_srepr=srepr, result_display=disp,
            narration="球の体積の公式に半径の値をあてはめて計算する（半径の立方に比例する）。",
        ),
    ]
    steps[1] = Step(
        op=steps[1].op, args=[], result_srepr=steps[1].result_srepr,
        result_display=_fmt_pi(surface, unit + "²"), narration=steps[1].narration,
    )
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# mode = l53_hemisphere_or_reverse（g1_l53.find_value Lv2）
# ---------------------------------------------------------------------------
def _handle_l53_hemisphere_or_reverse(values: Mapping[str, object]) -> Solution:
    variant = str(values["variant"])
    if variant == "hemisphere_surface":
        r = _i(values["radius"])
        unit = str(values.get("unit", "cm"))
        curved = 2 * sympy.pi * r**2
        flat = sympy.pi * r**2
        total = curved + flat
        disp = _fmt_pi(total, unit + "²")
        srepr = sympy.srepr(total)
        steps = [
            # Lv1 と同じ variant 中立の第1手（与え方を dup の軸にするため）。
            Step(
                op="read_radius_from_statement",
                args=[], result_srepr="", result_display=f"{r}",
                narration="問題文から球の半径を読み取る（直径で与えられているときは半分にする）。",
            ),
            Step(
                op="identify_hemisphere_faces",
                args=[], result_srepr="", result_display="曲面と切り口の円の2つの面からなる",
                narration="半球の表面は、球面の半分の曲面と、切り口にできる円の2つの面からなることを確認する。",
            ),
            Step(
                op="compute_curved_and_flat_area",
                args=[], result_srepr=sympy.srepr(sympy.Tuple(curved, flat)),
                result_display=_fmt_pi(curved, unit + "²") + " と " + _fmt_pi(flat, unit + "²"),
                narration="球の表面積の公式の半分から曲面の面積を、円の面積の公式から切り口の面積を求める。",
            ),
            Step(
                op="sum_hemisphere_surface_area",
                args=[], result_srepr=srepr, result_display=disp,
                narration="曲面の面積と切り口の面積を合計して、半球の表面積を求める。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    if variant == "reverse_sphere_radius":
        k = _i(values["area_coeff"])  # k = 4r^2（表面積 = kπ）
        r = sympy.sqrt(k / sympy.Integer(4))
        srepr = sympy.srepr(r)
        disp = _fmt_plain(r, "cm")
        steps = [
            Step(
                op="form_sphere_surface_equation",
                args=[], result_srepr="", result_display=f"4πr² = {k}π",
                narration="球の表面積の公式に、表面積の値をあてはめ、半径 r についての方程式をつくる。",
            ),
            Step(
                op="solve_for_radius",
                args=[], result_srepr=srepr, result_display=disp,
                narration="この方程式を r について解き、正の値を半径として答える。",
            ),
        ]
        return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
    raise ValueError(f"未知の variant: {variant!r}")


_MODE_HANDLERS = {
    "l51_direct_surface": _handle_l51_direct_surface,
    "l51_cone_central_angle": _handle_l51_cone_central_angle,
    "l51_composite_or_reverse_surface": _handle_l51_composite_or_reverse_surface,
    "l52_cylinder_volume_substitution": _handle_l52_cylinder_volume_substitution,
    "l52_prism_pyramid_volume_direct": _handle_l52_prism_pyramid_volume_direct,
    "l52_right_triangle_volume_multistep": _handle_l52_right_triangle_volume_multistep,
    "l52_composite_or_reverse_volume": _handle_l52_composite_or_reverse_volume,
    "l53_sphere_direct": _handle_l53_sphere_direct,
    "l53_hemisphere_or_reverse": _handle_l53_hemisphere_or_reverse,
}


@register_solver("math.solid_figure_measure")
def solid_figure_measure(mode: object, values: object) -> Solution:
    """空間図形の表面積・体積を mode で切り替えて求める（C8・g1_l51/l52/l53 横展開）。

    問題パラメータ（mode・寸法の辞書 values）だけから sympy で厳密計算する
    （double-solve）。答えは SymbolicAnswer（π を含む厳密値。cm²/cm³ 単位つき表示）。
    mode ごとに steps の op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    handler = _MODE_HANDLERS.get(mode_s)
    if handler is None:
        raise ValueError(f"未知の mode: {mode_s!r}")
    return handler(cast("Mapping[str, object]", values))


__all__ = ["solid_figure_measure"]
