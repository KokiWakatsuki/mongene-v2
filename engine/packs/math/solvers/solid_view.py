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


# ---------------------------------------------------------------------------
# 投影図（g1_l50.graph_table Lv1/Lv2/Lv3）
#
# 立体 -> (立面図の形, 平面図の形)。**この組で立体が一意に決まる**ことがこの単元の要点で、
# Lv1（両方の図から立体を読む）と Lv3（片方＋条件から立体を特定する）はその一意性を問う。
# 描画側（visuals/solid.py の _PROJECTION_SHAPES）と同じ対応を持つので、
# 両者が一致することをテストで固定する（片方だけ直すと図と答えが食い違う）。
# ---------------------------------------------------------------------------
_PROJECTION: dict[str, tuple[str, str]] = {
    "square_prism": ("rect", "square"),
    "cube": ("square", "square"),
    "cylinder": ("rect", "circle"),
    "cone": ("triangle", "circle"),
    "sphere": ("circle", "circle"),
    "square_pyramid": ("triangle", "square_with_diagonals"),
    "triangular_prism": ("rect", "triangle"),
}

_SOLID_JP: dict[str, str] = {
    "square_prism": "四角柱",
    "cube": "立方体",
    "cylinder": "円柱",
    "cone": "円錐",
    "sphere": "球",
    "square_pyramid": "正四角錐",
    "triangular_prism": "三角柱",
}

_SHAPE_JP: dict[str, str] = {
    "rect": "長方形",
    "square": "正方形",
    "circle": "円",
    "triangle": "三角形",
    "square_with_diagonals": "対角線のひかれた正方形",
}


def solid_name_jp(kind: str) -> str:
    return _SOLID_JP[kind]


def projection_shapes(kind: str) -> tuple[str, str]:
    """(立面図の形, 平面図の形)。描画側と共有する対応表への唯一の入口。"""
    if kind not in _PROJECTION:
        raise ValueError(f"投影図に未対応の立体: {kind!r}")
    return _PROJECTION[kind]


def solid_from_views(elevation: str, plan: str) -> str:
    """(立面図, 平面図) から立体を一意に決める。決まらなければ例外。"""
    hits = [k for k, v in _PROJECTION.items() if v == (elevation, plan)]
    if len(hits) != 1:
        raise ValueError(f"立体が一意に決まらない: 立面図={elevation!r} 平面図={plan!r} -> {hits}")
    return hits[0]


_READ_PROJ_OPS = ["read_elevation_and_plan", "identify_solid_from_projection"]
_READ_PROJ_NARRATION = {
    "read_elevation_and_plan": "真正面から見た図（立面図）と真上から見た図（平面図）が、それぞれどんな形かを読み取る。",
    "identify_solid_from_projection": "その二つの形の組み合わせになる立体はどれかを考えて答える。",
}
_READ_PROJ_PHRASE = {"read_elevation_and_plan": "二つの図の形を読み取る"}


@register_solver("math.solid_from_projection")
def solid_from_projection(elevation: object, plan: object) -> Solution:
    """投影図（立面図・平面図）から立体を答える（g1_l50.graph_table Lv1）。"""
    kind = solid_from_views(str(elevation), str(plan))
    name = _SOLID_JP[kind]
    distractors = [v for k, v in _SOLID_JP.items() if k != kind]
    answer = ChoiceAnswer(
        correct=name, distractors=distractors, fact_id=f"projection_to_solid.{kind}"
    )
    return Solution(
        answer=answer,
        steps=_steps(_READ_PROJ_OPS, _READ_PROJ_NARRATION, _READ_PROJ_PHRASE, "", name),
    )


_DRAW_PROJ_OPS = ["determine_elevation", "determine_plan", "draw_projection"]
_DRAW_PROJ_NARRATION = {
    "determine_elevation": "立体を真正面から見たときに、外側の輪郭がどんな形になるかを考える。",
    "determine_plan": "同じ立体を真上から見たときに、外側の輪郭がどんな形になるかを考える。",
    "draw_projection": "立面図を上、平面図を下にそろえて並べ、対応する位置がたてにそろうようにかく。",
}
_DRAW_PROJ_PHRASE = {
    "determine_elevation": "立面図の形を決める",
    "determine_plan": "平面図の形を決める",
}


@register_solver("math.projection_views_of_solid")
def projection_views_of_solid(kind: object, base: object, height: object) -> Solution:
    """立体の立面図・平面図の形と寸法を答える（g1_l50.graph_table Lv2）。"""
    kind_s = str(kind)
    elev, plan = projection_shapes(kind_s)
    b, h = int(base), int(height)
    if b <= 0 or h <= 0:
        raise ValueError("底面の辺・高さは正であること")
    features = [
        Feature(
            kind="elevation_shape", srepr=sympy.srepr(sympy.Symbol(elev)),
            display=f"立面図は{_SHAPE_JP[elev]}",
        ),
        Feature(
            kind="plan_shape", srepr=sympy.srepr(sympy.Symbol(plan)),
            display=f"平面図は{_SHAPE_JP[plan]}",
        ),
        Feature(kind="base_length", srepr=sympy.srepr(sympy.Integer(b)), display=f"底面 {b}"),
        Feature(kind="height", srepr=sympy.srepr(sympy.Integer(h)), display=f"高さ {h}"),
    ]
    disp = f"立面図は{_SHAPE_JP[elev]}、平面図は{_SHAPE_JP[plan]}"
    srepr = sympy.srepr(
        sympy.Tuple(sympy.Symbol(elev), sympy.Symbol(plan), sympy.Integer(b), sympy.Integer(h))
    )
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_DRAW_PROJ_OPS, _DRAW_PROJ_NARRATION, _DRAW_PROJ_PHRASE, srepr, disp),
    )


_COMPLETE_OPS = ["read_given_view", "identify_solid_from_partial", "draw_missing_view"]
_COMPLETE_NARRATION = {
    "read_given_view": "与えられているほうの図がどんな形かを読み取る。",
    "identify_solid_from_partial": "その形になる立体をすべて挙げ、もう一方の図についての条件に合うものを一つに絞る。",
    "draw_missing_view": "絞りこんだ立体を、与えられていないほうの向きから見た形にかく。",
}
_COMPLETE_PHRASE = {
    "read_given_view": "与えられた図の形を読み取る",
    "identify_solid_from_partial": "立体を一つに絞る",
}


@register_solver("math.complete_projection")
def complete_projection(plan: object, elevation: object) -> Solution:
    """平面図と「立面図がどんな形か」の条件から立体を特定し、立面図を答える。

    （g1_l50.graph_table Lv3）。組が一意に決まらない場合は solid_from_views が例外にする。
    """
    plan_s, elev_s = str(plan), str(elevation)
    kind = solid_from_views(elev_s, plan_s)
    name = _SOLID_JP[kind]
    features = [
        Feature(
            kind="solid_name", srepr=sympy.srepr(sympy.Symbol(name)), display=name,
        ),
        Feature(
            kind="elevation_shape", srepr=sympy.srepr(sympy.Symbol(elev_s)),
            display=f"立面図は{_SHAPE_JP[elev_s]}",
        ),
    ]
    disp = f"{name}（立面図は{_SHAPE_JP[elev_s]}）"
    srepr = sympy.srepr(sympy.Tuple(sympy.Symbol(name), sympy.Symbol(elev_s)))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_COMPLETE_OPS, _COMPLETE_NARRATION, _COMPLETE_PHRASE, srepr, disp),
    )


__all__ = [
    "solid_of_revolution_name",
    "solid_of_revolution_sketch",
    "solid_of_revolution_section",
    "solid_from_projection",
    "projection_views_of_solid",
    "complete_projection",
    "projection_shapes",
    "solid_from_views",
    "solid_name_jp",
]
