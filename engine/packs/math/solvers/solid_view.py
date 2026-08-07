"""立体の見え方（回転体・投影図・展開図・断面）の独立再計算ソルバ（§6.2 double-solve）。

solver は**問題パラメータだけ**（元になる平面図形の種類と2辺の長さ・立体の種類と寸法）
から答えと steps を導く。純粋・決定論・厳密（sympy）演算。乱数は引かない。
図そのものは `visuals/solid.py` が描く——ここが返すのは「何ができるか」「どの長さが
どこに来るか」という**数学の答え**だけで、描画の px は recipe が決める。

C8（g1_l49 面が動いてできる立体・回転体）クラスタ。

## 回転体の決まり方（教科書の3つ）

  長方形     を1辺を軸に1回転 → 円柱（底面の半径＝軸に垂直な辺・高さ＝軸の辺）
  直角三角形 を直角をはさむ1辺を軸に1回転 → 円錐（半径＝もう一方の辺・高さ＝軸の辺）
  半円       を直径を軸に1回転 → 球（半径＝半円の半径）

## 回転の軸を含む平面で切った断面

  円柱 → 長方形（横 2r・縦 h）／円錐 → 二等辺三角形（底辺 2r・高さ h）／球 → 円（半径 r）
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Feature, GraphAnswer, Solution, Step
from engine.core.registry import register_solver

# 元の平面図形 -> (できる立体, 断面の形)
_REVOLUTION: dict[str, tuple[str, str]] = {
    "rectangle": ("円柱", "長方形"),
    "right_triangle": ("円錐", "二等辺三角形"),
    "semicircle": ("球", "円"),
}

# 選択肢の母集団（もっともらしい誤り＝ほかの立体）。
_SOLID_POOL = ["円柱", "円錐", "球", "三角柱", "四角柱", "四角錐"]


def _dims(shape: str, axis_len: int, other_len: int) -> tuple[sympy.Integer, sympy.Integer]:
    """(底面の半径, 高さ)。球は高さを持たないので半径だけが意味を持つ。"""
    r = sympy.Integer(other_len)
    h = sympy.Integer(axis_len)
    return r, h


def _steps(ops: list[str], narration: dict[str, str], phrase: dict[str, str],
           srepr: str, disp: str) -> list[Step]:
    return [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else phrase[op],
            narration=narration[op],
        )
        for i, op in enumerate(ops)
    ]


_NAME_OPS = ["identify_rotation_axis", "name_solid_of_revolution"]
_NAME_NARRATION = {
    "identify_rotation_axis": "どの辺を軸にして回すのかを図で確かめ、軸から離れている部分がどこを通るかを考える。",
    "name_solid_of_revolution": "軸のまわりを一回転したとき、面が通る範囲がどんな立体になるかを答える。",
}
_NAME_PHRASE = {"identify_rotation_axis": "回転の軸を確かめる"}


@register_solver("math.solid_of_revolution_name")
def solid_of_revolution_name(shape: object) -> Solution:
    """回転させてできる立体の名前を答える（g1_l49.graph_table Lv1）。

    元の平面図形の種類だけで決まる（辺の長さには依らない）。
    """
    shape_s = str(shape)
    if shape_s not in _REVOLUTION:
        raise ValueError(f"未知の元の図形: {shape_s!r}")
    name, _section = _REVOLUTION[shape_s]
    distractors = [s for s in _SOLID_POOL if s != name]
    answer = ChoiceAnswer(
        correct=name, distractors=distractors, fact_id=f"solid_of_revolution.{shape_s}"
    )
    return Solution(
        answer=answer,
        steps=_steps(_NAME_OPS, _NAME_NARRATION, _NAME_PHRASE, "", name),
    )


_SKETCH_OPS = [
    "identify_rotation_axis",
    "determine_radius_and_height",
    "draw_solid_sketch",
]
_SKETCH_NARRATION = {
    "identify_rotation_axis": "どの辺を軸にして回すのかを図で確かめる。",
    "determine_radius_and_height": "軸に垂直な辺の長さが底面の半径に、軸に重なる辺の長さが高さになることを確かめる。",
    "draw_solid_sketch": "底面の円をつぶれた楕円でかき、見えない部分を破線にして見取図を仕上げる。",
}
_SKETCH_PHRASE = {
    "identify_rotation_axis": "回転の軸を確かめる",
    "determine_radius_and_height": "底面の半径と高さを決める",
}


@register_solver("math.solid_of_revolution_sketch")
def solid_of_revolution_sketch(shape: object, axis_len: object, other_len: object) -> Solution:
    """回転体の見取図をかき、底面の半径と高さを答える（g1_l49.graph_table Lv2）。

    答えは「立体の種類・底面の半径・高さ」の特徴集合。図の px は recipe が決める。
    """
    shape_s = str(shape)
    if shape_s not in ("rectangle", "right_triangle"):
        raise ValueError(f"見取図に高さを書き入れられない元の図形: {shape_s!r}")
    a, b = int(axis_len), int(other_len)
    if a <= 0 or b <= 0:
        raise ValueError("辺の長さは正であること")
    name, _ = _REVOLUTION[shape_s]
    r, h = _dims(shape_s, a, b)
    features = [
        Feature(kind="solid_name", srepr=sympy.srepr(sympy.Symbol(name)), display=name),
        Feature(kind="base_radius", srepr=sympy.srepr(r), display=f"底面の半径 {r}"),
        Feature(kind="height", srepr=sympy.srepr(h), display=f"高さ {h}"),
    ]
    disp = f"{name}（底面の半径 {r}、高さ {h}）"
    srepr = sympy.srepr(sympy.Tuple(sympy.Symbol(name), r, h))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_SKETCH_OPS, _SKETCH_NARRATION, _SKETCH_PHRASE, srepr, disp),
    )


_SECTION_OPS = [
    "identify_section_plane",
    "determine_section_shape",
    "draw_section",
]
_SECTION_NARRATION = {
    "identify_section_plane": "回転の軸をふくむ平面で切ると、軸の両側に同じ形が現れることを確かめる。",
    "determine_section_shape": "軸の片側にできる図形と、それを軸で折り返した図形を合わせて、切り口の形を決める。",
    "draw_section": "決めた形を、底辺と高さの長さがわかるようにかく。",
}
_SECTION_PHRASE = {
    "identify_section_plane": "切る平面を確かめる",
    "determine_section_shape": "切り口の形を決める",
}


@register_solver("math.solid_of_revolution_section")
def solid_of_revolution_section(shape: object, axis_len: object, other_len: object) -> Solution:
    """回転の軸をふくむ平面で切った断面の形と寸法を答える（g1_l49.graph_table Lv3）。

    断面は軸の両側に同じ図形が現れるので、**横は半径の2倍**になる。
    ここを取り違える（半径のままにする）のがこの単元の典型的な誤り。
    """
    shape_s = str(shape)
    if shape_s not in ("rectangle", "right_triangle"):
        raise ValueError(f"断面を多角形でかけない元の図形: {shape_s!r}")
    a, b = int(axis_len), int(other_len)
    if a <= 0 or b <= 0:
        raise ValueError("辺の長さは正であること")
    _name, section = _REVOLUTION[shape_s]
    r, h = _dims(shape_s, a, b)
    width = 2 * r  # 軸の両側に現れるので半径の2倍
    features = [
        Feature(
            kind="section_shape", srepr=sympy.srepr(sympy.Symbol(section)), display=section
        ),
        Feature(kind="section_width", srepr=sympy.srepr(width), display=f"横 {width}"),
        Feature(kind="section_height", srepr=sympy.srepr(h), display=f"縦 {h}"),
    ]
    disp = f"{section}（横 {width}、縦 {h}）"
    srepr = sympy.srepr(sympy.Tuple(sympy.Symbol(section), width, h))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_SECTION_OPS, _SECTION_NARRATION, _SECTION_PHRASE, srepr, disp),
    )


__all__ = [
    "solid_of_revolution_name",
    "solid_of_revolution_sketch",
    "solid_of_revolution_section",
]
