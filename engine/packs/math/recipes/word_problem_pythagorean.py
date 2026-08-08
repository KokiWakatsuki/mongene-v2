"""三平方の定理の利用（form=word_problem・C14 の三平方クラスタ）。

g3_l53 / g3_l55 / g3_l56 の word_problem Lv3（いずれも「誘導あり・図形設定→小問が
連なる」）を1つの recipe で賄う。数学は既存 solver
（`math.pythagorean_hypotenuse` / `math.solve_quadratic`）に委ねる＝**新 solver ゼロ**。

## 既存 solver への委ね方（なぜ新 solver が要らないか）

三平方の利用で使う計算は2種類しかない。

  - **斜辺を求める**（直角をはさむ2辺 → 斜辺）: `math.pythagorean_hypotenuse` を
    そのまま呼ぶ。
  - **直角をはさむ辺を求める**（斜辺と一方の辺 → 他方の辺）: 中学生が実際に書く
    立式そのまま「x² + a² = c²」を `math.solve_quadratic`（mode=
    `solve_product_form_positive_root`＝正の解を1つ選ぶ）に渡す。長さは正の数
    だから正の解がちょうど1つ選ばれる。専用の「leg solver」を足すより、既に
    g3_l29/l30 の図形立式で使われている「立式して正の解を採る」経路を再利用する
    ほうが素直で、solver も増えない。

面積・体積（ひし形の面積・角錐の体積・長方形の面積）は solver の出力を sympy で
そのまま合成する（`word_problem_probability.solve_multiple_union` と同じパターン）。

**無理数の扱い**: `sympy.nsimplify(文字列)` は偽の閉形式を返す既知の罠なので使わない。
solver が返した srepr を `sympy.sympify` で復元し、sympy オブジェクトのまま合成する。

## 3セルの対応

  - g3_l53 Lv3 (`rhombus_diagonal_area`): 1辺と対角線の一方が与えられたひし形。
    (1) もう一方の対角線 (2) 面積。対角線が互いの中点で垂直に交わることから
    直角三角形を作り、`math.solve_quadratic` で半分の長さを求めて倍にする。
  - g3_l55 Lv3 (`square_pyramid_height_volume`): 底面が正方形・側辺がすべて等しい
    正四角錐。(1) 高さ (2) 体積。底面の対角線を
    `math.pythagorean_hypotenuse`（直角をはさむ2辺が正方形の2辺）で求め、その半分を
    使って `math.solve_quadratic` で高さを出し、体積は底面積×高さ÷3 で合成する。
  - g3_l56 Lv3 (`box_surface_shortest_path`): 直方体の表面上を、となり合う2つの側面を
    通って対角の頂点まで進む最短の道のり。(1) 最短の道のり (2) 通る2側面の面積の和。
    展開すると「横＝2辺の和・縦＝高さ」の長方形になるので、最短の道のりはその対角線
    ＝`math.pythagorean_hypotenuse` そのもの。

## 図を持てない form での場面文（台帳からの逸脱と理由）

word_problem の frame の `asked_vocab` は `{formulation, value}` だけで、作図小問を
構造的に持てない（§ブリーフ契約5）。三平方の利用は本来「図を読む」題材なので、
**文章だけで図形が一意に定まるように場面文を書く**ことでこれを埋めている:

  - ひし形は「1辺の長さ」と「対角線の一方の長さ」で合同を除いて一意。
  - 正四角錐は「底面の正方形の1辺」と「他の辺（側辺）の長さ」で一意。
  - 直方体は3辺の長さで一意。経路は「どの2つの側面を通るか」を頂点名で明示する
    （どちらの向きに開いても展開後の長方形は同じなので、最短の道のりは一意）。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている長さだけで、答え（対角線・高さ・面積・
体積・最短距離）は入っていない。頂点名・題材語は `params["slots"]` に置く
（`numbers` は数値専用＝params 忠実性の機械検査の対象）。checker は同じ
`SOLVE_BUILDERS` を通して solver を呼び直す。

## narration に数字を書かない

長さの半分・和・積は語で述べ、値は `result_display` にのみ置く。既存 solver の steps は
題材語彙（「直角をはさむ2辺」）とズレる場面があるので、3 kind とも合成後の意味に沿った
steps をここで組み直す。
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

RECIPE_NAME = "math.word_problem_pythagorean"

_PYTHAGOREAN_WP_CONCEPTS = [
    "pythagorean.word_problem_rhombus_diagonal_area",
    "pythagorean.word_problem_square_pyramid_volume",
    "pythagorean.word_problem_box_shortest_path",
    # scenario_kind を足したら必ずここにも足す（無いと lint R6 が落ちる。
    # check_cell は通るので pytest 全走まで気づかない）。
    "pythagorean.word_problem_cube_vertex_to_plane",
    "pythagorean.word_problem_box_shortest_path_choose",
]

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 正の解をちょうど1つ選ぶ mode（長さは正の数）。g3_l29/l30 の図形立式と同じ経路。
_POSITIVE_ROOT_MODE = "solve_product_form_positive_root"
_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


# ---------------------------------------------------------------------------
# 表示（√ 表記・`*` 除去）。nsimplify は使わない（偽の閉形式を返す罠）。
# ---------------------------------------------------------------------------
def _fmt(value: sympy.Expr, unit: str) -> str:
    """値と単位の表示（sqrt(n)→√n・`*` 除去）。

    単位の前に空白を入れるのは、分数の答え（角錐の体積は底面積×高さ÷3 なので
    "100√14/3" のような形になる）で単位が分母に続いて読めてしまうのを避けるため。
    """
    body = _SQRT_RE.sub(r"√\1", sympy.sstr(value)).replace("*", "")
    return f"{body} {unit}" if unit else body


def _symbolic(value: sympy.Expr, unit: str) -> SymbolicAnswer:
    return SymbolicAnswer(srepr=sympy.srepr(value), display=_fmt(value, unit))


def _step(op: str, narration: str, value: sympy.Expr | None = None, unit: str = "") -> Step:
    """1手＝1 Step。値は result_display にだけ置く（narration に数字を書かない）。"""
    if value is None:
        return Step(op=op, args=[], result_srepr="", result_display="", narration=narration)
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


def _leg(hypotenuse: int, known_leg_squared: int) -> sympy.Expr:
    """斜辺と一方の辺 → 他方の辺。

    中学生の立式そのまま「x² + (既知の辺)² = (斜辺)²」を `math.solve_quadratic` に
    渡し、正の解を採る（長さは正の数）。専用 solver を足さないための経路。
    """
    solver = REGISTRY.solver("math.solve_quadratic")
    sol = cast(Solution, solver(f"x**2 + {known_leg_squared} = {hypotenuse**2}", _POSITIVE_ROOT_MODE))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Expr, sympy.sympify(sol.answer.srepr))


# ---------------------------------------------------------------------------
# 場面文と、そこから solve に渡す数値
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PythagoreanScene:
    """場面文と、そこから solve に渡す数値。

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す数値だけの辞書（params に
    そのまま載り、checker が同じ関数へ渡す）。頂点名・題材語は `slots` に置く。
    """

    numbers: dict[str, Any]
    scenario: str
    # 小問文。誘導ありは2つ、誘導なし（Lv4）は1つ。長さは solve 側が返す
    # Solution の数と一致していなければならない（recipe が assert する）。
    ask_texts: tuple[str, ...]
    slots: dict[str, str]


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「場面の数値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_rhombus_diagonal_area(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53 Lv3: 1辺と対角線の一方が与えられたひし形の (1)他方の対角線 (2)面積。"""
    side = int(numbers["side"])
    diagonal = int(numbers["diagonal"])
    half_given = diagonal // 2
    half_other = _leg(side, half_given * half_given)
    other = cast(sympy.Expr, 2 * half_other)
    area = cast(sympy.Expr, sympy.Rational(1, 2) * diagonal * other)

    diagonal_solution = Solution(
        answer=_symbolic(other, "cm"),
        steps=[
            _step(
                "halve_given_diagonal",
                "ひし形の対角線は、それぞれの中点で垂直に交わるから、与えられた対角線の"
                "長さの半分をとって、直角三角形の直角をはさむ辺の長さを求める。",
                sympy.Integer(half_given), "cm",
            ),
            _step(
                "apply_pythagorean_theorem",
                "ひし形の辺を斜辺、いま求めた長さを直角をはさむ一方の辺とする直角三角形で、"
                "三平方の定理からもう一方の辺の長さを求める。",
                half_other, "cm",
            ),
            _step(
                "restore_full_diagonal",
                "求めた長さは対角線の半分だから、これをもとにもどして、"
                "対角線全体の長さを求める。",
                other, "cm",
            ),
        ],
    )
    area_solution = Solution(
        answer=_symbolic(area, "cm²"),
        steps=[
            _step(
                "recall_rhombus_area_rule",
                "ひし形の面積は、対角線どうしの積の半分で求められることを使う。",
            ),
            _step(
                "compute_rhombus_area",
                "与えられた対角線の長さと、いま求めた対角線の長さをかけ、その半分をとって"
                "ひし形の面積を求める。",
                area, "cm²",
            ),
        ],
    )
    return [diagonal_solution, area_solution]


def solve_square_pyramid_height_volume(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l55 Lv3: 底面が正方形で側辺がすべて等しい正四角錐の (1)高さ (2)体積。"""
    base_edge = int(numbers["base_edge"])
    lateral_edge = int(numbers["lateral_edge"])
    base_diagonal = _hypotenuse(base_edge, base_edge)
    # 底面の対角線の半分（垂線の足は対角線の交点）。base_edge は偶数なので
    # (対角線の半分)² = base_edge²/2 は整数になる。
    half_diagonal_squared = base_edge * base_edge // 2
    height = _leg(lateral_edge, half_diagonal_squared)
    base_area = sympy.Integer(base_edge * base_edge)
    volume = cast(sympy.Expr, sympy.Rational(1, 3) * base_area * height)

    height_solution = Solution(
        answer=_symbolic(height, "cm"),
        steps=[
            _step(
                "compute_base_diagonal",
                "底面は正方形だから、となり合う辺を直角をはさむ2辺とみて、"
                "三平方の定理から底面の対角線の長さを求める。",
                base_diagonal, "cm",
            ),
            _step(
                "halve_base_diagonal",
                "頂点から底面に下ろした垂線の足は底面の対角線の交点だから、"
                "対角線の長さの半分が、直角三角形の直角をはさむ一方の辺になる。",
                cast(sympy.Expr, sympy.Rational(1, 2) * base_diagonal), "cm",
            ),
            _step(
                "apply_pythagorean_theorem",
                "側面の辺を斜辺、いま求めた長さを直角をはさむ一方の辺とする直角三角形で、"
                "三平方の定理から高さを求める。",
                height, "cm",
            ),
        ],
    )
    volume_solution = Solution(
        answer=_symbolic(volume, "cm³"),
        steps=[
            _step(
                "compute_base_area",
                "底面は正方形だから、その1辺の長さから底面積を求める。",
                base_area, "cm²",
            ),
            _step(
                "apply_pyramid_volume_rule",
                "角錐の体積は、底面積と高さの積の三分の一で求められることを使って、"
                "体積を求める。",
                volume, "cm³",
            ),
        ],
    )
    return [height_solution, volume_solution]


def solve_box_surface_shortest_path(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l56 Lv3: 直方体の表面上の (1)最短の道のり (2)通る2側面の面積の和。"""
    edge_a = int(numbers["edge_a"])
    edge_b = int(numbers["edge_b"])
    height = int(numbers["height"])
    # 2つの側面を1つの平面に開くと、横が2辺の和・縦が高さの長方形になる。
    unfolded_width = edge_a + edge_b
    shortest = _hypotenuse(unfolded_width, height)
    area = sympy.Integer(unfolded_width * height)

    path_solution = Solution(
        answer=_symbolic(shortest, "cm"),
        steps=[
            _step(
                "unfold_two_side_faces",
                "表面上の最短の道のりを考えるために、通る二つの側面を"
                "一つの平面に開いた展開図をかく。",
            ),
            _step(
                "identify_right_triangle",
                "開いた図では二つの側面が横に並んだ長方形になり、"
                "道のりが最も短くなるのは出発点と到着点を結ぶ線分のときだから、"
                "その線分を斜辺とする直角三角形をとらえる。",
                sympy.Integer(unfolded_width), "cm",
            ),
            _step(
                "apply_pythagorean_theorem",
                "直角をはさむ2辺は、底面の二つの辺の長さの和と、直方体の高さだから、"
                "三平方の定理から最短の道のりを求める。",
                shortest, "cm",
            ),
        ],
    )
    area_solution = Solution(
        answer=_symbolic(area, "cm²"),
        steps=[
            _step(
                "combine_two_side_faces",
                "開いた二つの側面は、あわせて横が底面の二つの辺の長さの和、"
                "縦が直方体の高さである一つの長方形になる。",
                sympy.Integer(unfolded_width), "cm",
            ),
            _step(
                "compute_rectangle_area",
                "その長方形の縦と横の長さをかけて、通る側面の面積の和を求める。",
                area, "cm²",
            ),
        ],
    )
    return [path_solution, area_solution]



def solve_cube_vertex_to_plane(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l55 Lv4: 立方体の1つの頂点から、向かい合う3頂点がつくる平面までの距離。

    立方体 ABCD-EFGH の頂点 B から平面 ACF に下ろした垂線の長さを、三角錐 B-ACF の
    体積を2通りに表して求める（誘導なしで方針を自分で立てるセル）。
      体積 = (1/3)·(1辺)²·(1辺)/2 = a³/6
      三角形 ACF は1辺 a√2 の正三角形 → 面積 = (√3/4)(a√2)² = (√3/2)a²
      よって (1/3)·(√3/2)a²·h = a³/6 ⇒ h = (√3/3)a
    """
    a = sympy.Integer(int(numbers["edge"]))
    volume = a**3 / 6
    face_area = sympy.sqrt(3) / 2 * a**2
    height = sympy.simplify(3 * volume / face_area)
    # 恒真: 求めた高さを体積の式に戻すと、もとの体積に一致する。
    assert sympy.simplify(face_area * height / 3 - volume) == 0
    steps = [
        Step(
            op="express_volume_two_ways", args=[], result_srepr=sympy.srepr(volume),
            result_display=_fmt(volume, "cm³"),
            narration=(
                "三角錐の体積を、直角をはさむ三つの辺を使う見方と、"
                "求める垂線を高さとみる見方の二通りで表すことにする。"
            ),
        ),
        Step(
            op="compute_equilateral_face_area", args=[], result_srepr=sympy.srepr(face_area),
            result_display=_fmt(face_area, "cm²"),
            narration="底面とみる三角形は正三角形なので、その一辺の長さから面積を求める。",
        ),
        Step(
            op="solve_for_perpendicular", args=[], result_srepr=sympy.srepr(height),
            result_display=_fmt(height, "cm"),
            narration="二通りに表した体積が等しいとおいて、垂線の長さについて解く。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(height), display=_fmt(height, "cm")),
            steps=steps,
        )
    ]


def solve_box_shortest_path_choose(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l56 Lv4: 直方体の表面上の最短距離を、開き方を自分で選んで求める。

    となり合う2面の開き方は3通りあり、開いた長方形の対角線はそれぞれ
      √((a+b)²+c²) ／ √((b+c)²+a²) ／ √((c+a)²+b²)
    最短になるのは**小さい2辺を足す**開き方。3辺が相異なら最小は一意に決まる
    （recipe が3辺を相異に構成する）。
    """
    a, b, c = (sympy.Integer(int(numbers[k])) for k in ("edge_a", "edge_b", "height"))
    cands = [
        sympy.sqrt((a + b) ** 2 + c**2),
        sympy.sqrt((b + c) ** 2 + a**2),
        sympy.sqrt((c + a) ** 2 + b**2),
    ]
    values = sorted(cands, key=lambda v: float(v.evalf()))
    shortest = values[0]
    if float(values[0].evalf()) >= float(values[1].evalf()):
        raise ValueError("最短の開き方が一意に決まらない")
    # 恒真: 最短は「小さい2辺を足す」開き方（3辺を並べ替えて確かめる）。
    s1, s2, s3 = sorted([a, b, c], key=lambda v: float(v.evalf()))
    assert sympy.simplify(shortest - sympy.sqrt((s1 + s2) ** 2 + s3**2)) == 0
    steps = [
        Step(
            op="enumerate_unfoldings", args=[], result_srepr="",
            result_display="三通りの開き方を書き出す",
            narration="となり合う二つの面の開き方が三通りあることを確かめ、それぞれで開いた長方形の縦と横を書き出す。",
        ),
        Step(
            op="compare_three_paths", args=[], result_srepr="",
            result_display="どの開き方が最も短いかを比べる",
            narration="開いた長方形の対角線の長さを三通りとも式にして比べ、最も短くなるのがどれかを決める。",
        ),
        Step(
            op="compute_shortest_path", args=[], result_srepr=sympy.srepr(shortest),
            result_display=_fmt(shortest, "cm"),
            narration="選んだ開き方の長方形について、対角線の長さを三平方の定理で求める。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(shortest), display=_fmt(shortest, "cm")),
            steps=steps,
        )
    ]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "rhombus_diagonal_area": solve_rhombus_diagonal_area,
    "square_pyramid_height_volume": solve_square_pyramid_height_volume,
    "box_surface_shortest_path": solve_box_surface_shortest_path,
    "cube_vertex_to_plane": solve_cube_vertex_to_plane,
    "box_shortest_path_choose": solve_box_shortest_path_choose,
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ。数値・頂点名を引いて場面文と numbers を組む）
# ---------------------------------------------------------------------------
def _draw_consecutive_labels(count: int, rng: Rng) -> str:
    """連続する count 文字の大文字（"ABCD" / "EFGH" …）を引く。

    多角形・立体の頂点名は連続文字で書くのが慣例なので、ばらばらの文字を引かない。
    """
    start = int(draw({"int_range": [0, len(_ALPHABET) - count]}, rng))
    return _ALPHABET[start : start + count]


def _draw_from(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _rhombus_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(1辺, 与える対角線) の候補列挙。

    対角線は偶数（半分が整数になる）・対角線の半分 < 1辺（ひし形が退化しない）。
    """
    side_lo, side_hi = (int(v) for v in p["side_range"])
    diag_lo, diag_hi = (int(v) for v in p["diagonal_range"])
    out: list[tuple[int, int]] = []
    for diagonal in range(diag_lo + diag_lo % 2, diag_hi + 1, 2):
        for side in range(side_lo, side_hi + 1):
            if diagonal // 2 < side:
                out.append((side, diagonal))
    return out


def _scene_rhombus_diagonal_area(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    side, diagonal = _draw_from(_rhombus_candidates(p), rng)
    labels = _draw_consecutive_labels(4, rng)
    scenario = (
        f"1辺の長さが{side}cmのひし形{labels}があり、"
        f"対角線{labels[0]}{labels[2]}の長さは{diagonal}cmである。"
    )
    ask_texts = (
        f"対角線{labels[1]}{labels[3]}の長さを求めよ。",
        "このひし形の面積を求めよ。",
    )
    return PythagoreanScene(
        numbers={"side": side, "diagonal": diagonal},
        scenario=scenario,
        ask_texts=ask_texts,
        slots={"labels": labels},
    )


def _square_pyramid_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(底面の1辺, 側辺) の候補列挙。

    底面の1辺は偶数（対角線の半分の二乗が整数になる）・高さの二乗
    (側辺² − 1辺²/2) が正で小さすぎない（つぶれた錐にしない）。
    """
    base_lo, base_hi = (int(v) for v in p["base_edge_range"])
    lat_lo, lat_hi = (int(v) for v in p["lateral_edge_range"])
    min_height_squared = int(p["min_height_squared"])
    out: list[tuple[int, int]] = []
    for base_edge in range(base_lo + base_lo % 2, base_hi + 1, 2):
        for lateral_edge in range(lat_lo, lat_hi + 1):
            if lateral_edge**2 - base_edge**2 // 2 >= min_height_squared:
                out.append((base_edge, lateral_edge))
    return out


def _scene_square_pyramid_height_volume(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    base_edge, lateral_edge = _draw_from(_square_pyramid_candidates(p), rng)
    base_labels = _draw_consecutive_labels(4, rng)
    apex = str(_draw_from([str(v) for v in p["apex_candidates"] if str(v) not in base_labels], rng))
    scenario = (
        f"底面が1辺{base_edge}cmの正方形{base_labels}で、"
        f"底面以外の辺の長さがすべて{lateral_edge}cmである正四角錐{apex}-{base_labels}がある。"
    )
    ask_texts = (
        "この正四角錐の高さを求めよ。",
        "この正四角錐の体積を求めよ。",
    )
    return PythagoreanScene(
        numbers={"base_edge": base_edge, "lateral_edge": lateral_edge},
        scenario=scenario,
        ask_texts=ask_texts,
        slots={"base_labels": base_labels, "apex": apex},
    )


def _scene_box_surface_shortest_path(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    edge_a = int(draw(p["edge_domain"], rng))
    edge_b = int(draw(p["edge_domain"], rng))
    height = int(draw(p["height_domain"], rng))
    labels = _draw_consecutive_labels(8, rng)
    base, top = labels[:4], labels[4:]
    item = str(_draw_from([str(v) for v in p["item_candidates"]], rng))
    scenario = (
        f"辺{base[0]}{base[1]}の長さが{edge_b}cm、辺{base[1]}{base[2]}の長さが{edge_a}cm、"
        f"高さが{height}cmの直方体{base}-{top}の形をした{item}がある。"
        f"ここで{base}は底面、{top}は上面で、辺{base[0]}{top[0]}が高さにあたる。"
        f"この{item}の表面上を、頂点{base[0]}から、側面{base[0]}{base[1]}{top[1]}{top[0]}と"
        f"側面{base[1]}{base[2]}{top[2]}{top[1]}を通って、頂点{top[2]}まで進む。"
    )
    ask_texts = (
        "進む道のりが最も短くなるときの、その道のりの長さを求めよ。",
        "この二つの側面の面積の和を求めよ。",
    )
    return PythagoreanScene(
        numbers={"edge_a": edge_a, "edge_b": edge_b, "height": height},
        scenario=scenario,
        ask_texts=ask_texts,
        slots={"labels": labels, "item": item},
    )



def _scene_cube_vertex_to_plane(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    edge = int(draw(p["edge_domain"], rng))
    labels = _draw_consecutive_labels(8, rng)
    base, top = labels[:4], labels[4:]
    scenario = (
        f"1辺が{edge}cmの立方体{base}-{top}がある。"
        f"ここで{base}は底面、{top}は上面で、辺{base[0]}{top[0]}が高さにあたる。"
    )
    ask = (
        f"頂点{base[1]}から平面{base[0]}{base[2]}{top[1]}に下ろした垂線の長さを、"
        "立体の体積を二通りに表す方針を自分で立てて求めよ。"
    )
    return PythagoreanScene(
        numbers={"edge": edge},
        scenario=scenario,
        ask_texts=(ask,),
        slots={"labels": labels},
    )


def _scene_box_shortest_path_choose(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """3辺を相異に引く（最短の開き方が一意に決まるようにする）。"""
    cands = [int(v) for v in _domain_values(p["edge_domain"])]
    edge_a = int(draw({"int_set": cands}, rng))
    edge_b = int(draw({"int_set": [v for v in cands if v != edge_a]}, rng))
    height = int(draw({"int_set": [v for v in cands if v not in (edge_a, edge_b)]}, rng))
    labels = _draw_consecutive_labels(8, rng)
    base, top = labels[:4], labels[4:]
    item = str(_draw_from([str(v) for v in p["item_candidates"]], rng))
    scenario = (
        f"辺{base[0]}{base[1]}の長さが{edge_a}cm、辺{base[1]}{base[2]}の長さが{edge_b}cm、"
        f"高さが{height}cmの直方体{base}-{top}の形をした{item}がある。"
        f"ここで{base}は底面、{top}は上面で、辺{base[0]}{top[0]}が高さにあたる。"
    )
    ask = (
        f"この{item}の表面上を頂点{base[0]}から頂点{top[2]}まで進むとき、"
        "どの面をどのように開くと最短になるかを自分で判断し、その最短の道のりを求めよ。"
    )
    return PythagoreanScene(
        numbers={"edge_a": edge_a, "edge_b": edge_b, "height": height},
        scenario=scenario,
        ask_texts=(ask,),
        slots={"labels": labels, "item": item},
    )


def _domain_values(spec: Any) -> list[int]:
    """int_range / int_set のどちらでも候補の実値を返す（3辺を相異に引くため）。"""
    if isinstance(spec, Mapping) and "int_range" in spec:
        lo, hi = (int(v) for v in spec["int_range"])
        return list(range(lo, hi + 1))
    if isinstance(spec, Mapping) and "int_set" in spec:
        return [int(v) for v in spec["int_set"]]
    return [int(v) for v in spec]


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], PythagoreanScene]] = {
    "rhombus_diagonal_area": _scene_rhombus_diagonal_area,
    "square_pyramid_height_volume": _scene_square_pyramid_height_volume,
    "box_surface_shortest_path": _scene_box_surface_shortest_path,
    "cube_vertex_to_plane": _scene_cube_vertex_to_plane,
    "box_shortest_path_choose": _scene_box_shortest_path_choose,
}


# ---------------------------------------------------------------------------
# recipe（3セル共通。scenario_kind が題材＝どの立体・どの平面図形かを選ぶ）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_PYTHAGOREAN_WP_CONCEPTS)
def word_problem_pythagorean(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_BUILDERS[kind](p, rng)
    solutions = SOLVE_BUILDERS[kind](scene.numbers)
    assert len(solutions) == len(scene.ask_texts)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})",
            asked="value",
            answer=sol.answer,
            steps=sol.steps,
            concept_tags=concept_tags,
            cause_tags=cause_tags,
        )
        for i, sol in enumerate(solutions)
    ]

    context_slots = dict(scene.slots)
    for i, text in enumerate(scene.ask_texts):
        context_slots[f"ask_{i + 1}"] = text
    if len(scene.ask_texts) == 1:
        # 誘導なしのセルは wp_linear_solo_v1（scenario + ask_value）を使う。
        context_slots["ask_value"] = scene.ask_texts[0]

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 場面文が読者に見せている長さだけ（答えは入れない）。checker はここから
            # solver を呼び直す。頂点名・題材語は slots（numbers は数値専用）。
            "scenario_kind": kind,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            "slots": dict(scene.slots),
        },
        given={"scenario": scene.scenario},
        context_slots=context_slots,
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "SOLVE_BUILDERS",
    "PythagoreanScene",
    "solve_box_surface_shortest_path",
    "solve_rhombus_diagonal_area",
    "solve_square_pyramid_height_volume",
    "word_problem_pythagorean",
]
