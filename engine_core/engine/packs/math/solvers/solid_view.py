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

import re

import sympy

from engine.core.contracts import ChoiceAnswer, Feature, GraphAnswer, Solution, Step
from engine.core.registry import register_solver

_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


def _fmt_len(v: sympy.Expr) -> str:
    """長さの教材表記（sqrt(n)→√n・`*` を書かない）。

    quadratic_function._fmt_scalar と同じ規約にそろえる（表記が単元で揺れないように）。
    """
    return _SQRT_RE.sub(r"√\1", str(sympy.sstr(sympy.together(v)))).replace("*", "")


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
_NAME_PHRASE = {"identify_rotation_axis": ""}


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
def _sketch_phrase(r: sympy.Integer, h: sympy.Integer) -> dict[str, str]:
    """見取図の手の括弧（この手で得た寸法）。指示の言い直しは置かない（面③）。"""
    return {
        "identify_rotation_axis": "",
        "determine_radius_and_height": f"底面の半径 {r}、高さ {h}",
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
        steps=_steps(_SKETCH_OPS, _SKETCH_NARRATION, _sketch_phrase(r, h), srepr, disp),
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
def _section_phrase(section: str) -> dict[str, str]:
    """断面の手の括弧（この手で分かった形）。"""
    return {
        "identify_section_plane": "回転の軸をふくむ平面",
        "determine_section_shape": section,
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
        steps=_steps(_SECTION_OPS, _SECTION_NARRATION, _section_phrase(section), srepr, disp),
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
_READ_PROJ_PHRASE = {"read_elevation_and_plan": ""}


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
def _draw_proj_phrase(elev: str, plan: str) -> dict[str, str]:
    """投影図の手の括弧（決まった形）。"""
    return {
        "determine_elevation": _SHAPE_JP[elev],
        "determine_plan": _SHAPE_JP[plan],
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
        steps=_steps(_DRAW_PROJ_OPS, _DRAW_PROJ_NARRATION, _draw_proj_phrase(elev, plan), srepr, disp),
    )


_COMPLETE_OPS = ["read_given_view", "identify_solid_from_partial", "draw_missing_view"]
_COMPLETE_NARRATION = {
    "read_given_view": "与えられているほうの図がどんな形かを読み取る。",
    "identify_solid_from_partial": "その形になる立体をすべて挙げ、もう一方の図についての条件に合うものを一つに絞る。",
    "draw_missing_view": "絞りこんだ立体を、与えられていないほうの向きから見た形にかく。",
}
def _plan_candidates(plan_shape: str) -> list[str]:
    """その平面図になる立体を、対応表からすべて挙げる（`_PROJECTION` が唯一の出典）。"""
    return [_SOLID_JP[k] for k, (_elev, plan) in _PROJECTION.items() if plan == plan_shape]


def _complete_phrase(plan_shape: str, name: str) -> dict[str, str]:
    """投影図を補う手の括弧（読み取った形と絞りこんだ立体）。"""
    return {
        "read_given_view": _SHAPE_JP[plan_shape],
        # **「すべて挙げ」と言うなら挙げる。** 候補を1つも書かずに答えの立体へ
        # 飛んでいたので、「絞る」作業が解説の中に存在しなかった。
        "identify_solid_from_partial": (
            "、".join(_plan_candidates(plan_shape)) + f" → {name}"
        ),
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
        steps=_steps(_COMPLETE_OPS, _COMPLETE_NARRATION, _complete_phrase(plan_s, name), srepr, disp),
    )


# ---------------------------------------------------------------------------
# 展開図（g1_l51.graph_table Lv2/Lv3）
#
# 角柱の展開図は「側面の帯（長方形）＋底面2枚」。側面の長方形は
#   縦 = 立体の高さ／横 = 底面の周の長さ（正n角柱なら n×1辺）
# ここを「横＝1辺」と取り違えるのがこの単元の典型的な誤り。
#
# 複合立体（円柱の上に円錐）の側面は、円柱側面の長方形（縦 h・横 2πr）と
# 円錐側面のおうぎ形（半径＝母線 l＝√(r²+h²)・弧の長さ 2πr）に分かれる。
# ---------------------------------------------------------------------------
_NET_OPS = ["unfold_lateral_faces", "determine_side_rectangle_size", "draw_net"]
_NET_NARRATION = {
    "unfold_lateral_faces": "側面をすべて切り開いて横一列に並べると、ひとつながりの長方形になることを確かめる。",
    "determine_side_rectangle_size": "その長方形の縦は立体の高さ、横は底面の周の長さになることから、それぞれの長さを求める。",
    "draw_net": "側面の長方形に底面をつけ加えて展開図を仕上げ、縦と横の長さを書き入れる。",
}
def _net_phrase(base_jp: str, h: int, width: int) -> dict[str, str]:
    """展開図の手の括弧（開いた形と寸法）。"""
    return {
        "unfold_lateral_faces": f"底面が{base_jp}の1枚の長方形",
        "determine_side_rectangle_size": f"縦 {h}、横 {width}",
    }


@register_solver("math.prism_net_side_rectangle")
def prism_net_side_rectangle(face_count: object, base: object, height: object) -> Solution:
    """正n角柱の展開図で、側面の長方形の縦と横を答える（g1_l51.graph_table Lv2）。"""
    n, b, h = int(face_count), int(base), int(height)
    if n < 3 or b <= 0 or h <= 0:
        raise ValueError("面の数は3以上、辺と高さは正であること")
    width = n * b  # 底面の周の長さ（「横＝1辺」と取り違えるのが典型的な誤り）
    base_jp = {3: "正三角形", 4: "正方形", 5: "正五角形", 6: "正六角形"}.get(n, f"正{n}角形")
    features = [
        Feature(
            kind="side_rect_height", srepr=sympy.srepr(sympy.Integer(h)),
            display=f"側面の長方形の縦 {h}",
        ),
        Feature(
            kind="side_rect_width", srepr=sympy.srepr(sympy.Integer(width)),
            display=f"側面の長方形の横 {width}",
        ),
        Feature(
            kind="base_edge_count", srepr=sympy.srepr(sympy.Integer(n)),
            display=f"底面は{base_jp}",
        ),
    ]
    disp = f"側面の長方形は縦 {h}、横 {width}"
    srepr = sympy.srepr(sympy.Tuple(sympy.Integer(h), sympy.Integer(width), sympy.Integer(n)))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_NET_OPS, _NET_NARRATION, _net_phrase(base_jp, h, width), srepr, disp),
    )


_COMPOSITE_OPS = [
    "separate_lateral_surfaces",
    "unfold_cylinder_side",
    "unfold_cone_side",
    "draw_composite_net",
]
_COMPOSITE_NARRATION = {
    "separate_lateral_surfaces": "側面を、円柱の部分と円錐の部分の二つに分けて考える。",
    "unfold_cylinder_side": "円柱の側面を切り開くと長方形になり、その横は底面の円周の長さになることを確かめる。",
    "unfold_cone_side": "円錐の側面を切り開くとおうぎ形になり、その半径は母線の長さ、弧の長さは底面の円周の長さになることを確かめる。",
    "draw_composite_net": "求めた長さを書き入れて、二つをならべた側面の展開図をかく。",
}
def _composite_phrase(h1: int, circ: str, slant: sympy.Expr) -> dict[str, str]:
    """組み合わせた立体の展開図の手の括弧（開いた各面の寸法）。"""
    return {
        "separate_lateral_surfaces": "円柱の側面と円錐の側面",
        "unfold_cylinder_side": f"縦 {h1}、横 {circ} の長方形",
        "unfold_cone_side": f"半径 {slant}、弧の長さ {circ} のおうぎ形",
    }


@register_solver("math.composite_side_net")
def composite_side_net(
    radius: object, cylinder_height: object, cone_height: object
) -> Solution:
    """円柱の上に円錐をのせた立体の、側面の展開図に要る長さを答える。

    （g1_l51.graph_table Lv3）。母線 l=√(r²+h²) が整数になる組だけを recipe が引く。
    """
    r, h1, h2 = int(radius), int(cylinder_height), int(cone_height)
    if r <= 0 or h1 <= 0 or h2 <= 0:
        raise ValueError("半径・高さは正であること")
    slant = sympy.sqrt(sympy.Integer(r) ** 2 + sympy.Integer(h2) ** 2)
    if not slant.is_Integer:
        raise ValueError(f"母線が整数にならない: {slant}")
    circumference = 2 * sympy.pi * r
    # 表示は教科書表記（"6π"）にそろえる。sympy の既定表示は "6*pi" で読めない。
    circ_disp = f"{2 * r}π"
    features = [
        Feature(
            kind="cylinder_side_height", srepr=sympy.srepr(sympy.Integer(h1)),
            display=f"円柱の側面の縦 {h1}",
        ),
        Feature(
            kind="cylinder_side_width", srepr=sympy.srepr(circumference),
            display=f"円柱の側面の横 {circ_disp}",
        ),
        Feature(
            kind="sector_radius", srepr=sympy.srepr(slant),
            display=f"おうぎ形の半径 {slant}",
        ),
        Feature(
            kind="sector_arc_length", srepr=sympy.srepr(circumference),
            display=f"おうぎ形の弧の長さ {circ_disp}",
        ),
    ]
    disp = (
        f"円柱の側面は縦 {h1}・横 {circ_disp}、"
        f"円錐の側面のおうぎ形は半径 {slant}・弧の長さ {circ_disp}"
    )
    srepr = sympy.srepr(
        sympy.Tuple(sympy.Integer(h1), circumference, slant, circumference)
    )
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(
            _COMPOSITE_OPS, _COMPOSITE_NARRATION,
            _composite_phrase(h1, circ_disp, slant), srepr, disp,
        ),
    )


# ---------------------------------------------------------------------------
# 直方体の断面と、表面上の最短距離（g3_l55/g3_l56.graph_table Lv2）
#
# どちらも「立体の問題を平面の直角三角形に落とす」ことが要点で、計算そのものは
# 三平方の定理。solver は落とした先の**平面図形の寸法**を返す。
# ---------------------------------------------------------------------------
_BOX_SECTION_OPS = [
    "identify_section_plane",
    "compute_base_diagonal",
    "draw_section_with_diagonal",
]
_BOX_SECTION_NARRATION = {
    "identify_section_plane": "向かい合う二つの頂点をふくむ平面で切ると、切り口が長方形になることを確かめる。",
    "compute_base_diagonal": "その長方形の横は底面の対角線なので、底面の二辺から三平方の定理で求める。",
    "draw_section_with_diagonal": "切り口の長方形を平面にかき出し、対角線をひいて、対角線を求めるのに使う直角三角形を示す。",
}
def _box_section_phrase(base_diag: sympy.Expr) -> dict[str, str]:
    """直方体の断面の手の括弧（分かった形と長さ）。"""
    return {
        "identify_section_plane": "長方形",
        "compute_base_diagonal": _fmt_len(base_diag),
    }


@register_solver("math.box_section_diagonal")
def box_section_diagonal(side_a: object, side_b: object, height: object) -> Solution:
    """直方体の対角線をふくむ断面（長方形）の寸法を答える（g3_l55.graph_table Lv2）。

    横＝底面の対角線 √(a²+b²)、縦＝高さ、対角線＝立体の対角線 √(a²+b²+h²)。
    """
    a, b, h = int(side_a), int(side_b), int(height)
    if a <= 0 or b <= 0 or h <= 0:
        raise ValueError("辺の長さは正であること")
    base_diag = sympy.sqrt(sympy.Integer(a) ** 2 + sympy.Integer(b) ** 2)
    body_diag = sympy.sqrt(base_diag**2 + sympy.Integer(h) ** 2)
    features = [
        Feature(
            kind="section_width", srepr=sympy.srepr(base_diag),
            display=f"切り口の横（底面の対角線） {_fmt_len(base_diag)}",
        ),
        Feature(
            kind="section_height", srepr=sympy.srepr(sympy.Integer(h)),
            display=f"切り口の縦（高さ） {h}",
        ),
        Feature(
            kind="body_diagonal", srepr=sympy.srepr(body_diag),
            display=f"立体の対角線 {_fmt_len(body_diag)}",
        ),
    ]
    disp = (
        f"切り口は横 {_fmt_len(base_diag)}、縦 {h} の長方形で、"
        f"対角線は {_fmt_len(body_diag)}"
    )
    srepr = sympy.srepr(sympy.Tuple(base_diag, sympy.Integer(h), body_diag))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(
            _BOX_SECTION_OPS, _BOX_SECTION_NARRATION,
            _box_section_phrase(base_diag), srepr, disp,
        ),
    )


_UNFOLD_OPS = ["choose_two_faces", "unfold_to_plane", "draw_straight_path"]
_UNFOLD_NARRATION = {
    "choose_two_faces": "出発点と目的地が、どの二つの面をまたいでいるかを確かめる。",
    "unfold_to_plane": "その二つの面を一つの平面に開くと、横が二辺の長さの和、縦が残りの辺の長さの長方形になることを確かめる。",
    "draw_straight_path": "開いた図の上で二点を直線で結び、その長さを三平方の定理で求める。",
}
def _unfold_phrase(width: sympy.Expr, h: int) -> dict[str, str]:
    """展開して最短経路を見る手の括弧（開いた長方形の寸法）。"""
    return {
        "choose_two_faces": "となり合う2面",
        "unfold_to_plane": f"横 {width}、縦 {h} の長方形",
    }


@register_solver("math.box_unfold_shortest_path")
def box_unfold_shortest_path(side_a: object, side_b: object, height: object) -> Solution:
    """直方体のとなり合う2面を開いた展開図と、その上の最短経路を答える。

    （g3_l56.graph_table Lv2）。開いた長方形は横 a+b・縦 h で、最短の道のりは
    その対角線 √((a+b)²+h²)。
    """
    a, b, h = int(side_a), int(side_b), int(height)
    if a <= 0 or b <= 0 or h <= 0:
        raise ValueError("辺の長さは正であること")
    width = sympy.Integer(a + b)
    path = sympy.sqrt(width**2 + sympy.Integer(h) ** 2)
    features = [
        Feature(
            kind="unfolded_width", srepr=sympy.srepr(width),
            display=f"開いた長方形の横 {width}",
        ),
        Feature(
            kind="unfolded_height", srepr=sympy.srepr(sympy.Integer(h)),
            display=f"開いた長方形の縦 {h}",
        ),
        Feature(
            kind="shortest_path", srepr=sympy.srepr(path),
            display=f"最短の道のり {_fmt_len(path)}",
        ),
    ]
    disp = f"開いた長方形は横 {width}、縦 {h} で、最短の道のりは {_fmt_len(path)}"
    srepr = sympy.srepr(sympy.Tuple(width, sympy.Integer(h), path))
    return Solution(
        answer=GraphAnswer(features=features, solution_svg_ref=""),
        steps=_steps(_UNFOLD_OPS, _UNFOLD_NARRATION, _unfold_phrase(width, h), srepr, disp),
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
    "prism_net_side_rectangle",
    "composite_side_net",
    "box_section_diagonal",
    "box_unfold_shortest_path",
]
