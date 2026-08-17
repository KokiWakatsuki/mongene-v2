"""C8 g1 空間図形クラスタ（g1_l47/l48 の knowledge Lv2）の独立再計算ソルバ（§6.2）。

用語想起（g1_l47/l48/l49/l50 Lv1）と規則想起（g1_l53 Lv1）は既存ハブ
`math.term_recall_definition` / `math.recall_rule_statement`（letter_expr.py）に
domain/topic を足して賄うため、ここには含まれない（新設ソルバは判別型の3つだけ）。

  - `math.judge_polyhedron_element_count`: n角柱/n角錐の面・辺・頂点の数についての
    主張を検証する（g1_l47.knowledge Lv2・mode="element_count"）
  - `math.judge_regular_polyhedron_condition`: 1つの頂点に集まる正多角形の面の数から、
    正多面体を組み立てられるかを角の和で判別する（同 Lv2・mode="regular_condition"）
  - `math.judge_solid_position_relation`: 直方体の 辺と辺／辺と面 の位置関係を判別する
    （g1_l48.knowledge Lv2・mode="edge_edge"/"edge_face"）

いずれも答えは ChoiceAnswer で **数字トークンを含まない**（G-Q5t 素通り・digit-free は
term_recall/recall_rule と同じ鉄則）。narration にも数字を書かない。
op 列は同一レベル内の全 mode で揃える（1レベル＝1 signature＝1 op 列・G-FP 安定）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step
from engine.core.registry import register_solver

# ---------------------------------------------------------------------------
# math.judge_polyhedron_element_count（g1_l47.knowledge Lv2・mode="element_count"）
# ---------------------------------------------------------------------------
ELEMENT_QUANTITIES: tuple[str, ...] = ("faces", "edges", "vertices")

# 解説の括弧に出す日本語（面③。「読み取った結果」＝何の数を問われているか）。
_QUANTITY_JP: dict[str, str] = {"faces": "面", "edges": "辺", "vertices": "頂点"}
ELEMENT_LABEL_JA: dict[str, str] = {"faces": "面", "edges": "辺", "vertices": "頂点"}
SOLID_LABEL_JA: dict[str, str] = {"prism": "角柱", "pyramid": "角錐"}


def true_element_count(n: int, solid_type: str, quantity: str) -> int:
    """n角柱/n角錐（n=底面の辺の数）の面・辺・頂点の数を公式で求める。"""
    if solid_type == "prism":
        return {"faces": n + 2, "edges": 3 * n, "vertices": 2 * n}[quantity]
    if solid_type == "pyramid":
        return {"faces": n + 1, "edges": 2 * n, "vertices": n + 1}[quantity]
    raise ValueError(f"未知の solid_type: {solid_type!r}")


#: 正多角形の実物の呼び方（「正3角形」とは書かない／4は「正方形」）。
_REGULAR_POLYGON_JP = {
    3: "正三角形", 4: "正方形", 5: "正五角形", 6: "正六角形",
    7: "正七角形", 8: "正八角形", 9: "正九角形", 10: "正十角形",
}


def _judge_steps(
    correct: str,
    s1_display: str,
    s1_narration: str,
    s2_narration: str,
    s2_detail: str = "",
) -> list[Step]:
    """g1_l47 Lv2 共通の op 列 [read_claim, judge_claim]（mode 間で不変＝G-FP 安定）。

    `s2_detail` は**実際に計算した数**を解説だけに出すためのもの。
    「公式で実際の個数を求め、主張されている個数と比べて」と言いながら、
    括弧には「誤り」しか出ておらず、**生徒が自分の答えと突き合わせる数が
    どこにも無かった**。narration には入れない（ヒントに流れて G-Q5t に触る）。
    """
    return [
        Step(
            op="read_claim",
            args=[],
            result_srepr="claim",
            result_display=s1_display,
            narration=s1_narration,
        ),
        Step(
            op="judge_claim",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=s2_narration,
            detail=s2_detail or s2_narration,
        ),
    ]


@register_solver("math.judge_polyhedron_element_count")
def judge_polyhedron_element_count(
    n: object, solid_type: object, quantity: object, candidate: object
) -> Solution:
    """n角柱/n角錐の面・辺・頂点の数についての主張の正誤を判別する（g1_l47.knowledge Lv2）。

    n（底面の辺の数）・solid_type（prism/pyramid）・quantity（faces/edges/vertices）・
    candidate（主張されている個数）だけから公式で計算し直して判定する（double-solve）。
    答えは ChoiceAnswer（正しい/誤り・数字トークンなし）。
    """
    n_i = int(str(n))
    st = str(solid_type)
    q = str(quantity)
    cand = int(str(candidate))
    if n_i < 3:
        raise ValueError(f"底面の辺の数は3以上であること: {n_i!r}")
    if q not in ELEMENT_QUANTITIES:
        raise ValueError(f"未知の quantity: {q!r}")
    actual = true_element_count(n_i, st, q)
    is_true = cand == actual
    correct = "正しい" if is_true else "誤り"
    other = "誤り" if is_true else "正しい"
    solid_jp = "角柱" if st == "prism" else "角錐"
    verdict = "主張と同じなので正しい" if is_true else f"主張の {cand} とちがうので誤り"
    steps = _judge_steps(
        correct,
        f"{_QUANTITY_JP[q]}の数の主張",
        "立体の種類（角柱か角錐か）と、数を主張されている量（面・辺・頂点のどれか）を読み取る。",
        "底面の辺の数から公式で実際の個数を求め、主張されている個数と比べて正誤を判別する。",
        s2_detail=(
            "底面の辺の数から公式で実際の個数を求め、主張されている個数と比べる。"
            f"底面の辺が {n_i} の{solid_jp}なので、{_QUANTITY_JP[q]}の数は {actual}。"
            f"{verdict}。"
        ),
    )
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id=f"polyhedron_element_count.{st}.{q}"
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_regular_polyhedron_condition（g1_l47.knowledge Lv2・mode="regular_condition"）
# ---------------------------------------------------------------------------
@register_solver("math.judge_regular_polyhedron_condition")
def judge_regular_polyhedron_condition(shape_sides: object, count_at_vertex: object) -> Solution:
    """1つの頂点に集まる正多角形の面の数から、正多面体を組み立てられるかを判別する。

    （g1_l47.knowledge Lv2）。shape_sides（面である正多角形の辺の数）・count_at_vertex
    （1つの頂点に集まる面の数）だけから、頂点に集まる角の和が360°未満かで判定する
    （sympy.Rational による厳密計算・double-solve）。答えは ChoiceAnswer（正しい/誤り）。
    """
    m = int(str(shape_sides))
    k = int(str(count_at_vertex))
    if m < 3 or k < 3:
        raise ValueError(f"多角形の辺の数・頂点に集まる面の数は3以上であること: m={m!r}, k={k!r}")
    interior_angle = sympy.Rational((m - 2) * 180, m)
    total = interior_angle * k
    can_form = bool(total < 360)
    correct = "正しい" if can_form else "誤り"
    other = "誤り" if can_form else "正しい"
    # **「正3角形」と書いていた。** 問題文は「正三角形」なので、括弧だけ算用数字に
    # なっていた。三・四・五・六は漢数字が実物の書き方（四角形は「正方形」）。
    poly_jp = _REGULAR_POLYGON_JP.get(m, f"正{m}角形")
    steps = _judge_steps(
        correct,
        f"{poly_jp}が{k}枚",
        "面になっている正多角形の種類と、1つの頂点に集まる面の数を読み取る。",
        (
            "その正多角形の1つの内角の大きさに、集まる面の数をかけた角の和を求め、"
            "それが一まわりの角より小さいときだけ、折り曲げて立体の頂点にできると判別する。"
        ),
        # **なぜそうするかを落とさない。** 数だけを入れると
        # 「正三角形の1つの内角は 60°、…（正しい）」となって、
        # 何のためにこの計算をしているのかが解説から消える。目的の文を先に置く。
        s2_detail=(
            "その正多角形の1つの内角の大きさに、集まる面の数をかけた角の和を求め、"
            "それが一まわりの角より小さいかどうかを見る。"
            f"{poly_jp}の1つの内角は {interior_angle}° だから "
            f"{interior_angle}° × {k} = {total}°。"
            + (
                "一まわりの 360° より小さいので、折り曲げて立体の頂点にできる。"
                if can_form
                else "一まわりの 360° より小さくないので、折り曲げて立体の頂点にできない。"
            )
        ),
    )
    answer = ChoiceAnswer(
        correct=correct,
        distractors=[other],
        fact_id="regular_polyhedron_condition.vertex_angle_sum",
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 直方体の標準座標（g1_l48.knowledge Lv2）。
#
# 頂点名は recipe 側が引いた8文字（底面4つ→上面4つの順）で与えられ、ここで標準座標
# A(0,0,0) B(1,0,0) C(1,1,0) D(0,1,0) / E(0,0,1) F(1,0,1) G(1,1,1) H(0,1,1) に
# 対応づける。実際の辺の長さによらず位置関係（平行/垂直に交わる/ねじれの位置）は
# 軸に平行な方向ベクトルの組合せだけで決まるので、単位立方体の座標で十分。
# ---------------------------------------------------------------------------
_CANONICAL_COORD: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
)
# 標準ラベル ABCD-EFGH での辺・面（recipe はこの添字並びを使って名前を組み立てる）。
CUBOID_EDGE_INDICES: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 0),   # 底面 AB BC CD DA
    (4, 5), (5, 6), (6, 7), (7, 4),   # 上面 EF FG GH HE
    (0, 4), (1, 5), (2, 6), (3, 7),   # 側の辺 AE BF CG DH
)
CUBOID_FACE_INDICES: tuple[tuple[int, int, int, int], ...] = (
    (0, 1, 2, 3),   # ABCD 底面
    (4, 5, 6, 7),   # EFGH 上面
    (0, 1, 5, 4),   # ABFE
    (3, 2, 6, 7),   # DCGH
    (0, 3, 7, 4),   # ADHE
    (1, 2, 6, 5),   # BCGF
)
EDGE_EDGE_OPTIONS: tuple[str, ...] = ("平行", "垂直に交わる", "ねじれの位置")
EDGE_FACE_OPTIONS: tuple[str, ...] = ("平行", "面上にある", "垂直に交わる")

_Vec = tuple[int, int, int]


def _sub(u: _Vec, v: _Vec) -> _Vec:
    return (u[0] - v[0], u[1] - v[1], u[2] - v[2])


def _cross(u: _Vec, v: _Vec) -> _Vec:
    return (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])


def _dot(u: _Vec, v: _Vec) -> int:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _coord_map(labels: str) -> dict[str, _Vec]:
    if len(labels) != 8 or len(set(labels)) != 8:
        raise ValueError(f"頂点ラベルは相異なる8文字であること: {labels!r}")
    return {ch: _CANONICAL_COORD[i] for i, ch in enumerate(labels)}


def _classify_edge_edge(coord: dict[str, _Vec], e1: str, e2: str) -> str:
    p1, p2 = coord[e1[0]], coord[e1[1]]
    q1, q2 = coord[e2[0]], coord[e2[1]]
    d1, d2 = _sub(p2, p1), _sub(q2, q1)
    cross = _cross(d1, d2)
    if cross == (0, 0, 0):
        return "平行"
    # 直方体の辺の方向は3本の軸方向しかないため、方向が異なる2辺は交わっていれば
    # 必ず垂直に交わる。交わるかどうかは3重積（同一平面上にあるか）で判別する。
    return "垂直に交わる" if _dot(_sub(q1, p1), cross) == 0 else "ねじれの位置"


def _classify_edge_face(coord: dict[str, _Vec], edge: str, face: str) -> str:
    p0, p1, _p2, p3 = (coord[ch] for ch in face)
    normal = _cross(_sub(p1, p0), _sub(p3, p0))
    ea, eb = coord[edge[0]], coord[edge[1]]
    if _dot(normal, _sub(eb, ea)) == 0:
        # 辺の方向は面と平行。始点が面の平面上にあれば辺は面にふくまれる。
        return "面上にある" if _dot(normal, _sub(ea, p0)) == 0 else "平行"
    # 平行でなければ辺の方向は面の法線と同じ向き＝面に垂直に交わる。
    return "垂直に交わる"


@register_solver("math.judge_solid_position_relation")
def judge_solid_position_relation(
    labels: object, mode: object, first: object, second: object
) -> Solution:
    """直方体の 辺と辺／辺と面 の位置関係を判別する（g1_l48.knowledge Lv2）。

    頂点ラベル（底面4つ→上面4つの順の8文字）と、問われている2つの対象の名前だけから、
    標準座標で方向ベクトル・法線ベクトルを計算し直して判定する（double-solve）。
    答えは ChoiceAnswer（平行／垂直に交わる／ねじれの位置 ほか・数字トークンなし）。
    """
    coord = _coord_map(str(labels))
    md = str(mode)
    a, b = str(first), str(second)
    if md == "edge_edge":
        if len(a) != 2 or len(b) != 2 or a == b:
            raise ValueError(f"辺の指定が不正: {a!r}, {b!r}")
        correct = _classify_edge_edge(coord, a, b)
        options = EDGE_EDGE_OPTIONS
        s1_display = ""
        s1_narration = "直方体の中で、位置関係を問われている2つの辺がどれかを読み取る。"
        s2_narration = (
            "2辺の向きが同じなら平行、向きが異なり交わっていれば垂直に交わる、"
            "向きが異なり交わりもしなければねじれの位置と判別する。"
        )
        fact_id = "spatial_position.edge_edge"
    elif md == "edge_face":
        if len(a) != 2 or len(b) != 4:
            raise ValueError(f"辺/面の指定が不正: {a!r}, {b!r}")
        correct = _classify_edge_face(coord, a, b)
        options = EDGE_FACE_OPTIONS
        s1_display = ""
        s1_narration = "直方体の中で、位置関係を問われている辺と面がどれかを読み取る。"
        s2_narration = (
            "辺が面にふくまれていれば面上にある、辺が面とどこまでいっても交わらなければ平行、"
            "辺が面と一点で直角に交わっていれば垂直に交わると判別する。"
        )
        fact_id = "spatial_position.edge_face"
    else:
        raise ValueError(f"未知の mode: {md!r}")

    distractors = [o for o in options if o != correct]
    steps = [
        Step(
            op="read_position_query",
            args=[],
            result_srepr=f"{md}:{a}:{b}",
            result_display=s1_display,
            narration=s1_narration,
        ),
        Step(
            op="classify_relation",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=s2_narration,
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id=fact_id)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "CUBOID_EDGE_INDICES",
    "CUBOID_FACE_INDICES",
    "EDGE_EDGE_OPTIONS",
    "EDGE_FACE_OPTIONS",
    "ELEMENT_LABEL_JA",
    "ELEMENT_QUANTITIES",
    "SOLID_LABEL_JA",
    "judge_polyhedron_element_count",
    "judge_regular_polyhedron_condition",
    "judge_solid_position_relation",
    "true_element_count",
]
