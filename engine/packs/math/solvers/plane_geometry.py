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
            result_display=_TRANSFORMATION_NARRATION_S1[t],
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
            result_display=_CONSTRUCTION_PROPERTY_NARRATION[t],
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
            result_display=narration_s1,
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
            result_display="点と直線の位置関係を読み取る",
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
            result_display="半径と中心角の大きさを読み取る",
            narration="おうぎ形の半径と中心角の大きさを読み取る。",
        ),
        Step(
            op="apply_sector_formula",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration=narration,
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
    disp = sympy.sstr(angle)
    srepr = sympy.srepr(angle)
    steps = [
        Step(
            op="form_area_equation",
            args=[],
            result_srepr="",
            result_display="面積の公式に半径とわからない中心角をあてはめ方程式をつくる",
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
