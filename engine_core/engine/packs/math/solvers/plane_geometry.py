"""平面図形まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く（recipe の構成値は見ない）。
純粋・決定論であること。乱数は引かない。

C7（g1 平面図形）クラスタのうち、新規 visual 基盤を要さない非 visual セル群を扱う:
  - `math.judge_transformation_invariant`: g1_l38/l39/l40.knowledge Lv1（平行移動・回転
    移動・対称移動の不変性の判別）
  - `math.judge_construction_property`: g1_l41/l42.knowledge Lv1（垂直二等分線・角の二等分線
    上の点が2端/2辺から等距離という性質の判別）
  - `math.judge_circle_property`: g1_l45.knowledge Lv2（弧と中心角の比例・接線と半径の
    垂直性の判別）
  - `math.sector_arc_length_or_area`: g1_l46.find_value Lv1（半径・中心角からおうぎ形の
    弧の長さ/面積を求める）
  - `math.sector_solve_central_angle`: g1_l46.find_value Lv2（面積から中心角を逆算する）

用語想起（直線・線分・半直線・角／垂線の足・距離／基本作図の選択／円の用語）は既存の
`math.term_recall` ハブ（letter_expr.py の `_TERM_MAPS`）に domain を追加して対応する。

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。ChoiceAnswer の
correct/distractor は漢数字のみ＝digit-free（鉄則①）。
"""
from __future__ import annotations

import re

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

# ---------------------------------------------------------------------------
# math.judge_transformation_invariant（g1_l38/l39/l40.knowledge Lv1）
# ---------------------------------------------------------------------------
_TRANSFORMATION_JUDGE: dict[str, tuple[str, str, str]] = {
    # topic: (correct, distractor, fact_id 用の説明)
    "parallel_translation": ("変わらない", "変わる", "平行移動しても対応する辺の長さや図形の大きさ"),
    "rotation": ("等しい", "等しくない", "回転移動で対応する点と回転の中心との距離"),
    "reflection": ("垂直に二等分される", "平行に二等分される", "対称移動で対応する2点を結ぶ線分と対称の軸との関係"),
}
_TRANSFORMATION_NARRATION_S1: dict[str, str] = {
    "parallel_translation": "図形を平行移動する前と後で、対応する部分を見比べる。",
    "rotation": "図形を回転移動する前と後で、対応する点と回転の中心との関係を見比べる。",
    "reflection": "図形を対称移動する前と後で、対応する点を結ぶ線分と対称の軸との関係を見比べる。",
}


@register_solver("math.judge_transformation_invariant")
def judge_transformation_invariant(topic: object) -> Solution:
    """平行移動・回転移動・対称移動の性質(不変量)を判別する（knowledge・g1_l38/l39/l40 Lv1）。

    topic（移動の種類）だけから判定する（具体的な図形・場面は recipe が構成する surface
    であり double-solve）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    t = str(topic)
    if t not in _TRANSFORMATION_JUDGE:
        raise ValueError(f"未知の topic: {t!r}")
    correct, distractor, _desc = _TRANSFORMATION_JUDGE[t]
    steps = [
        Step(
            op="compare_before_after",
            args=[],
            result_srepr=t,
            # 見比べた結果（＝答えそのもの）は次の手なので、ここは括弧なしにする。
            result_display="",
            narration=_TRANSFORMATION_NARRATION_S1[t],
        ),
        Step(
            op="judge_transformation_invariant",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="移動の性質として、その関係がつねに成り立つかどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[distractor], fact_id=f"transformation_invariant.{t}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_construction_property（g1_l41/l42.knowledge Lv1）
# ---------------------------------------------------------------------------
_CONSTRUCTION_PROPERTY_NARRATION: dict[str, str] = {
    "perpendicular_bisector": "垂直二等分線上の点から、線分の両端までの距離を見比べる。",
    "angle_bisector": "角の二等分線上の点から、角をつくる2辺までの距離を見比べる。",
}


@register_solver("math.judge_construction_property")
def judge_construction_property(topic: object) -> Solution:
    """垂直二等分線/角の二等分線上の点が2端(2辺)から等距離という性質を判別する

    （knowledge・g1_l41/l42 Lv1）。topic（作図の種類）だけから判定する（具体的な図形は
    recipe が構成する surface であり double-solve、恒真の性質）。答えは ChoiceAnswer。
    """
    t = str(topic)
    if t not in _CONSTRUCTION_PROPERTY_NARRATION:
        raise ValueError(f"未知の topic: {t!r}")
    correct, distractor = "等しい", "等しくない"
    steps = [
        Step(
            op="identify_construction_property",
            args=[],
            result_srepr=t,
            result_display="",
            narration=_CONSTRUCTION_PROPERTY_NARRATION[t],
        ),
        Step(
            op="judge_construction_property",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その距離どうしの関係を判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[distractor], fact_id=f"construction_property.{t}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_circle_property（g1_l45.knowledge Lv2）
# ---------------------------------------------------------------------------
_CIRCLE_PROPERTY_JUDGE: dict[str, tuple[str, list[str], str]] = {
    "arc_central_angle_proportional": (
        "正しい", ["誤り"],
        "1つの円で中心角と弧の長さが比例するかどうかを見比べる。",
    ),
    "tangent_perpendicular": (
        "垂直", ["平行", "一定でない"],
        "円の接線と、接点を通る半径との位置関係を見比べる。",
    ),
}


@register_solver("math.judge_circle_property")
def judge_circle_property(concept: object) -> Solution:
    """弧と中心角の比例/接線と半径の垂直性を判別する（knowledge・g1_l45 Lv2）。

    concept（性質の種類）だけから判定する（具体的な場面は recipe が構成する surface で
    あり double-solve、恒真の性質）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    c = str(concept)
    if c not in _CIRCLE_PROPERTY_JUDGE:
        raise ValueError(f"未知の concept: {c!r}")
    correct, distractors, narration_s1 = _CIRCLE_PROPERTY_JUDGE[c]
    steps = [
        Step(
            op="identify_circle_property",
            args=[],
            result_srepr=c,
            result_display="",
            narration=narration_s1,
        ),
        Step(
            op="judge_circle_property",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="その性質がつねに成り立つ関係かどうかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id=f"circle_property.{c}")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_point_line_distance_meaning（g1_l37.knowledge Lv2）
#
# g1_l37 Lv1（用語想起・math.term_recall・domain="line_angle_terms"）と op 列が衝突
# しないよう（level_sep・G-FP）、term_recall ハブを使わず専用 solver にする（恒真・
# 引数は使わない＝ math.explain_sample_ratio_rationale と同型）。
# ---------------------------------------------------------------------------
@register_solver("math.judge_point_line_distance_meaning")
def judge_point_line_distance_meaning(dummy: object) -> Solution:
    """「点と直線との距離」がどの線分の長さを指すかを判別する（knowledge・g1_l37 Lv2）。

    恒真の定義判別のため引数は使わない（double-solve）。答えは ChoiceAnswer。
    """
    correct = "垂線の長さ"
    distractors = ["直線上の適当な点までの線分の長さ", "直線に平行に引いた線分の長さ"]
    steps = [
        Step(
            op="identify_point_and_line",
            args=[],
            result_srepr="",
            result_display="",
            narration="点と直線の位置関係を読み取る。",
        ),
        Step(
            op="judge_distance_definition",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="点と直線との距離が、どの線分の長さを指すかを判別する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id="point_line_distance.meaning")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# おうぎ形の弧の長さ・面積（表示は sympy の "pi" を "π" に直す・radical.py と同型）。
# ---------------------------------------------------------------------------
_PI_STAR_RE = re.compile(r"\*pi")


def _fmt_pi_display(expr: sympy.Expr) -> str:
    """π を含む式の表示形（`n*pi`→`nπ`・裸の `pi`→`π`）。"""
    s = _PI_STAR_RE.sub("π", sympy.sstr(expr))
    return s.replace("pi", "π")


# ---------------------------------------------------------------------------
# math.sector_arc_length_or_area（g1_l46.find_value Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.sector_arc_length_or_area")
def sector_arc_length_or_area(radius: object, angle: object, target: object) -> Solution:
    """半径と中心角からおうぎ形の弧の長さ/面積を公式にあてはめて求める（g1_l46.find_value Lv1）。

    半径・中心角・求める対象(target)だけから計算する（double-solve）。答えは単一値の
    SymbolicAnswer（π を含む厳密値）。narration に数字は書かない。
    """
    r = sympy.Integer(int(str(radius)))
    a = sympy.Integer(int(str(angle)))
    t = str(target)
    if t == "arc_length":
        expr = sympy.Rational(1, 180) * r * a * sympy.pi
        narration = "弧の長さの公式（半径×中心角の割合×2π）にあてはめて計算する。"
    else:
        expr = sympy.Rational(1, 360) * r * r * a * sympy.pi
        narration = "おうぎ形の面積の公式（半径の2乗×中心角の割合×π）にあてはめて計算する。"
    disp = _fmt_pi_display(expr)
    srepr = sympy.srepr(expr)
    steps = [
        Step(
            op="identify_radius_and_angle",
            args=[],
            result_srepr="",
            result_display=f"半径 {sympy.sstr(r)}、中心角 {sympy.sstr(a)}°",
            narration="おうぎ形の半径と中心角の大きさを読み取る。",
        ),
        Step(
            op="apply_sector_formula",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration=narration,
            # **公式に値を入れた式が1行も無かった。** 「公式にあてはめて計算する」と
            # 言うだけで、`2π × 3 × 30/360` が出ていない（実物は必ず代入式を書く）。
            # detail は narration を置きかえるので、**目的（何の公式か）を落とさない**。
            detail=(
                f"弧の長さの公式にあてはめて、2π × {sympy.sstr(r)} × "
                f"{sympy.sstr(a)}/360 を計算する。"
                if t == "arc_length"
                else f"おうぎ形の面積の公式にあてはめて、π × {sympy.sstr(r)}² × "
                     f"{sympy.sstr(a)}/360 を計算する。"
            ),
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.sector_solve_central_angle（g1_l46.find_value Lv2）
# ---------------------------------------------------------------------------
@register_solver("math.sector_solve_central_angle")
def sector_solve_central_angle(radius: object, area_pi_coeff: object) -> Solution:
    """おうぎ形の面積(π の係数)と半径から中心角の大きさを逆算する（g1_l46.find_value Lv2）。

    半径・面積(πの係数)だけから計算する（double-solve）。答えは単一値(度数)の
    SymbolicAnswer。narration に数字は書かない。
    """
    r = sympy.Integer(int(str(radius)))
    k = sympy.Rational(str(area_pi_coeff))
    angle = k * 360 / (r * r)
    # 角の答えには「°」を付ける（同じセルの面積・体積は cm²・cm³ を付けている
    # のに、中心角だけ単位が落ちていた）。
    disp = f"{sympy.sstr(angle)}°"
    srepr = sympy.srepr(angle)
    steps = [
        Step(
            op="form_area_equation",
            args=[],
            result_srepr="",
            result_display=f"{sympy.sstr(r)}² × π × x/360 = {sympy.sstr(k)}π",
            narration="おうぎ形の面積の公式に、半径と分からない中心角をあてはめて方程式をつくる。",
        ),
        Step(
            op="solve_for_central_angle",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="方程式を中心角について解き、その大きさを求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


_AREA_BISECT_OPS = [
    "compute_quadrilateral_area",
    "set_half_area_condition",
    "solve_for_point_on_side",
]

_AREA_BISECT_NARRATION: dict[str, str] = {
    "compute_quadrilateral_area": "まわりの座標から四角形全体の面積を求める。",
    "set_half_area_condition": "頂点を通る直線が面積を2等分するのだから、"
                               "分けられた一方の三角形の面積が全体の半分になる、という式を立てる。",
    "solve_for_point_on_side": "その三角形は辺の上の点までの長さを底辺とみられるので、"
                               "面積の式を長さについて解いて、点の位置を求める。",
}

def _area_bisect_display(op: str, whole, abc) -> str:
    """面積を2等分する点の手の括弧（この手で得た値・式）。"""
    if op == "compute_quadrilateral_area":
        return sympy.sstr(whole)
    if op == "set_half_area_condition":
        return f"△ABP = {sympy.sstr(sympy.Rational(whole, 2))}（△ABC = {sympy.sstr(abc)}）"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


def _polygon_area(pts: list[tuple[sympy.Expr, sympy.Expr]]) -> sympy.Expr:
    """多角形の面積（shoelace 公式・符号なし・厳密値）。"""
    total = sympy.Integer(0)
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return sympy.Rational(1, 2) * abs(sympy.nsimplify(total))


@register_solver("math.area_bisecting_point_on_side")
def area_bisecting_point_on_side(
    ax: object, ay: object, bx: object, by: object,
    cx: object, cy: object, dx: object, dy: object,
) -> Solution:
    """四角形ABCDの頂点Aを通り面積を2等分する直線が、辺BC と交わる点 P を求める

    （g2_l50.find_value Lv3）。8つの座標だけから計算する（double-solve）。

    P は辺BC 上の点なので P = B + t(C−B) とおける。三角形ABP の面積は
    三角形ABC の面積の t 倍だから、t = (全体の面積の半分) ÷ (三角形ABC の面積)。
    答えは Tuple(P の x 座標, P の y 座標)。**求めた P で三角形ABP の面積を組み直し、
    全体の半分に戻ることを確かめる**（別経路の検算）。
    """
    a = (sympy.Integer(int(str(ax))), sympy.Integer(int(str(ay))))
    b = (sympy.Integer(int(str(bx))), sympy.Integer(int(str(by))))
    c = (sympy.Integer(int(str(cx))), sympy.Integer(int(str(cy))))
    d = (sympy.Integer(int(str(dx))), sympy.Integer(int(str(dy))))

    whole = _polygon_area([a, b, c, d])
    abc = _polygon_area([a, b, c])
    if abc == 0:
        raise ValueError("三角形ABCがつぶれている")
    t = sympy.Rational(whole, 2 * abc)
    if not (0 < t < 1):
        raise ValueError(f"点Pが辺BCの内側に来ない（t={t}）")
    p = (b[0] + t * (c[0] - b[0]), b[1] + t * (c[1] - b[1]))
    # 恒真: 求めた P で三角形ABP を組み直すと、面積は全体のちょうど半分になる。
    if sympy.simplify(_polygon_area([a, b, p]) - whole / 2) != 0:
        raise ValueError("三角形ABPの面積が全体の半分に戻らない")

    result = sympy.Tuple(p[0], p[1])
    ratio_num, ratio_den = sympy.Rational(t).p, sympy.Rational(t).q - sympy.Rational(t).p
    disp = (
        f"P({sympy.sstr(p[0])}, {sympy.sstr(p[1])})"
        f"（BP:PC = {ratio_num}:{ratio_den}）"
    )
    srepr = sympy.srepr(result)
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_AREA_BISECT_OPS) - 1 else "",
            result_display=disp if i == len(_AREA_BISECT_OPS) - 1
            else _area_bisect_display(op, whole, abc),
            narration=_AREA_BISECT_NARRATION[op],
        )
        for i, op in enumerate(_AREA_BISECT_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)
