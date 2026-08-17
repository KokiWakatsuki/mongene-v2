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
from math import gcd
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
from engine.core.verify.answer_size import answer_is_too_big, limits_for

RECIPE_NAME = "math.word_problem_pythagorean"

_PYTHAGOREAN_WP_CONCEPTS = [
    "pythagorean.word_problem_rhombus_diagonal_area",
    "pythagorean.word_problem_square_pyramid_volume",
    "pythagorean.word_problem_box_shortest_path",
    # scenario_kind を足したら必ずここにも足す（無いと lint R6 が落ちる。
    # check_cell は通るので pytest 全走まで気づかない）。
    "pythagorean.word_problem_cube_vertex_to_plane",
    "pythagorean.word_problem_box_shortest_path_choose",
    # exam_l4（入試融合・三平方と空間図形）— C13。既存の空間図形資産の再利用なので
    # exam_fusion.py ではなくこのモジュールに置く（exam_l5/l6 と同じ判断）。
    "exam.box_space_diagonal",
    "exam.cube_guided_diagonal_area_path",
    "exam.regular_tetrahedron_height_volume",
    # g3_l53.word_problem Lv4（Phase E の端物）。
    "pythagorean.word_problem_triangle_height_area_solo",
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


def _step(
    op: str, narration: str, value: sympy.Expr | None = None, unit: str = "",
    note: str = "",
) -> Step:
    """1手＝1 Step。値は result_display にだけ置く（narration に数字を書かない）。

    `note` は値の出ない手（補助線をひく・断面をとらえる）の括弧に入れる**その手で
    得たもの**（面③）。空のままだと括弧なしの行になり、何をつかんだかが残らない。
    """
    if value is None:
        return Step(op=op, args=[], result_srepr="", result_display=note, narration=narration)
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
                note="（対角線）×（対角線）÷ 2",
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
                note=f"横 {unfolded_width}、縦 {height} の長方形",
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
            result_display="、".join(f"{_fmt(v, 'cm')}" for v in values),
            narration="となり合う二つの面の開き方が三通りあることを確かめ、それぞれで開いた長方形の縦と横を書き出す。",
        ),
        Step(
            op="compare_three_paths", args=[], result_srepr="",
            result_display=f"最も短いのは {_fmt(shortest, 'cm')}",
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


def solve_exam_box_space_diagonal(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l4.find_value Lv3: 直方体の対角線を、断面の直角三角形に落として求める。

    新しい数学はゼロ。底面の対角線 √(a²+b²) を出し（既存
    `math.pythagorean_hypotenuse`）、それを直角をはさむ一方の辺、高さをもう一方と
    する直角三角形にもう一度あてる——という**2段の適用**そのものがこのセルの中身。
    """
    a, b, h = (int(numbers[k]) for k in ("edge_a", "edge_b", "height"))
    base_diagonal = _hypotenuse(a, b)
    space_diagonal = _hypotenuse(base_diagonal, h)
    # 恒真: 立体の対角線の二乗は3辺の二乗の和（別経路での確かめ）。
    assert sympy.simplify(space_diagonal**2 - (a**2 + b**2 + h**2)) == 0
    steps = [
        _step(
            "compute_base_diagonal",
            "底面は長方形だから、となり合う2辺を直角をはさむ2辺とみて、"
            "三平方の定理から底面の対角線の長さを求める。",
            base_diagonal, "cm",
        ),
        _step(
            "identify_section_right_triangle",
            "求める対角線は、いま求めた底面の対角線と高さを直角をはさむ2辺とする"
            "直角三角形の斜辺になる。この直角三角形が立体の断面である。",
            note=f"直角をはさむ2辺は {_fmt(base_diagonal, 'cm')} と {h}cm",
        ),
        _step(
            "apply_pythagorean_theorem",
            "その直角三角形に三平方の定理をあてて、立体の対角線の長さを求める。",
            space_diagonal, "cm",
        ),
    ]
    return [Solution(answer=_symbolic(space_diagonal, "cm"), steps=steps)]


def solve_exam_cube_guided(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l4.word_problem Lv3: 立方体で (1)対角線 (2)正三角形の面積 (3)表面の最短。

    3小問が**それぞれ別の落とし方**を要求するのが誘導ありの眼目:
      (1) 断面の直角三角形（対角線）
      (2) 面の対角線がつくる正三角形（面積は正三角形の公式）
      (3) 2面を開いた展開図（最短の道のり）
    """
    a = sympy.Integer(int(numbers["edge"]))
    face_diagonal = _hypotenuse(a, a)
    space_diagonal = _hypotenuse(face_diagonal, a)
    triangle_area = sympy.simplify(sympy.sqrt(3) / 4 * face_diagonal**2)
    shortest = _hypotenuse(2 * a, a)
    # 恒真: 対角線は 1辺の √3 倍、最短の道のりは 1辺の √5 倍。
    assert sympy.simplify(space_diagonal - a * sympy.sqrt(3)) == 0
    assert sympy.simplify(shortest - a * sympy.sqrt(5)) == 0

    diagonal_solution = Solution(
        answer=_symbolic(space_diagonal, "cm"),
        steps=[
            _step(
                "compute_face_diagonal",
                "面の対角線を、となり合う2辺を直角をはさむ2辺とする直角三角形から求める。",
                face_diagonal, "cm",
            ),
            _step(
                "apply_pythagorean_theorem",
                "その面の対角線と、それに垂直な辺を直角をはさむ2辺とする断面の"
                "直角三角形に三平方の定理をあてて、立体の対角線を求める。",
                space_diagonal, "cm",
            ),
        ],
    )
    area_solution = Solution(
        answer=_symbolic(triangle_area, "cm²"),
        steps=[
            _step(
                "identify_equilateral_triangle",
                "3つの頂点を結ぶ三角形の辺は、どれも立方体の面の対角線だから、"
                "この三角形は正三角形である。",
                face_diagonal, "cm",
            ),
            _step(
                "compute_equilateral_area",
                "正三角形の高さを三平方の定理で求める見方から、"
                "1辺の長さだけで面積が求められることを使って面積を求める。",
                triangle_area, "cm²",
            ),
        ],
    )
    path_solution = Solution(
        answer=_symbolic(shortest, "cm"),
        steps=[
            _step(
                "unfold_two_side_faces",
                "表面上を進む最短の道のりを考えるために、通る二つの面を"
                "一つの平面に開いた展開図をかく。",
                note=f"横 {2 * a}、縦 {a} の長方形",
            ),
            _step(
                "identify_right_triangle",
                "開いた図は、横が1辺の2つ分、縦が1辺の長方形になる。"
                "道のりが最も短くなるのは出発点と到着点を結ぶ線分のときである。",
                2 * a, "cm",
            ),
            _step(
                "apply_pythagorean_theorem",
                "その線分を斜辺とする直角三角形に三平方の定理をあてて、"
                "最短の道のりを求める。",
                shortest, "cm",
            ),
        ],
    )
    return [diagonal_solution, area_solution, path_solution]


def solve_exam_regular_tetrahedron(numbers: Mapping[str, Any]) -> list[Solution]:
    """exam_l4.word_problem Lv4: 正四面体の高さと体積（誘導なし・断面を自分で取り出す）。

    垂線の足は底面の正三角形の重心で、頂点から重心までの距離は中線の三分の二。
    その長さと辺を直角をはさむ辺・斜辺とする**自分で取り出した断面**の直角三角形から
    高さが出る。体積は底面積（正三角形）と高さから。答えは
    Tuple(高さ, 体積)＝一度に二つの量を問う（誘導なしなので小問に割らない）。
    """
    a = sympy.Integer(int(numbers["edge"]))
    median = sympy.simplify(sympy.sqrt(3) / 2 * a)          # 底面の中線
    centroid_distance = sympy.simplify(sympy.Rational(2, 3) * median)
    height = sympy.simplify(sympy.sqrt(a**2 - centroid_distance**2))
    base_area = sympy.simplify(sympy.sqrt(3) / 4 * a**2)
    volume = sympy.simplify(sympy.Rational(1, 3) * base_area * height)
    # 恒真: 正四面体の高さは 1辺の √6/3 倍、体積は 1辺の三乗の √2/12 倍。
    assert sympy.simplify(height - sympy.sqrt(6) / 3 * a) == 0
    assert sympy.simplify(volume - sympy.sqrt(2) / 12 * a**3) == 0

    result = sympy.Tuple(height, volume)
    display = f"高さ {_fmt(height, 'cm')}、体積 {_fmt(volume, 'cm³')}"
    steps = [
        _step(
            "locate_foot_of_perpendicular",
            "底面は正三角形だから、頂点から下ろした垂線の足は底面の重心にあたる。"
            "重心は中線を頂点から三分の二のところで分ける。",
            centroid_distance, "cm",
        ),
        _step(
            "take_section_right_triangle",
            "頂点・垂線の足・底面の1つの頂点を通る平面で切り取ると、"
            "辺を斜辺、いま求めた長さを直角をはさむ一方の辺とする直角三角形が現れる。",
            note=f"斜辺 {a}cm、他の1辺 {_fmt(centroid_distance, 'cm')}",
        ),
        _step(
            "apply_pythagorean_theorem",
            "その直角三角形に三平方の定理をあてて、高さを求める。",
            height, "cm",
        ),
        Step(
            op="compute_pyramid_volume", args=[], result_srepr=sympy.srepr(result),
            # この手で得たのは体積だけ（高さは前の手）。答え全体を写さない。
            result_display=_fmt(volume, "cm³"),
            narration="底面の正三角形の面積と、いま求めた高さから、"
            "角錐の体積は底面積と高さの積の三分の一であることを使って体積を求める。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(result), display=display), steps=steps
        )
    ]


def solve_triangle_height_area_solo(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l53.word_problem Lv4: 3辺がわかる三角形の、底辺に対する高さと面積（誘導なし）。

    誘導なしの眼目は**補助線を自分で引く**こと。頂点から底辺に垂線を下ろすと、底辺が
    2つに分かれて直角三角形が2つできる。分けた一方を x とおくと、2つの直角三角形が
    同じ高さを共有することから
        c² − x² = b² − (a − x)²   ⇒   x = (c² − b² + a²) / (2a)
    が立ち、そこから高さが求まる。**未知数を自分で置く**ところまでが解法の一部なので、
    steps もその順（補助線 → 文字を置く → 2通りに表す → 高さ → 面積）で組む。
    """
    a = sympy.Integer(int(numbers["base"]))          # BC（底辺）
    b = sympy.Integer(int(numbers["side_b"]))        # CA
    c = sympy.Integer(int(numbers["side_c"]))        # AB
    x = sympy.Rational(c**2 - b**2 + a**2, 2 * a)    # B から垂線の足までの長さ
    if not (0 < x < a):
        raise ValueError("垂線の足が底辺の内側に来ない（補助線の場面が成立しない）")
    height = sympy.sqrt(c**2 - x**2)
    # 恒真: もう一方の直角三角形からも同じ高さが出る（2通りに表した式が一致する）。
    assert sympy.simplify(height**2 - (b**2 - (a - x) ** 2)) == 0
    area = sympy.Rational(1, 2) * a * height
    result = sympy.Tuple(height, area)
    display = f"高さ {_fmt(height, 'cm')}、面積 {_fmt(area, 'cm²')}"
    steps = [
        _step(
            "draw_auxiliary_perpendicular",
            "3辺の長さしかわかっていないので、頂点から底辺に垂線を引く補助線を自分で入れる。"
            "底辺が2つに分かれて、高さを共有する直角三角形が2つできる。",
            note="頂点から底辺への垂線",
        ),
        _step(
            "set_unknown_on_base",
            "分かれた底辺の一方の長さを文字でおくと、もう一方は底辺の長さからその分をひいた"
            "残りになる。",
            x, "cm",
        ),
        _step(
            "express_height_two_ways",
            "2つの直角三角形それぞれで、高さの二乗を三平方の定理で表す。"
            "高さは共通だから、その2つの式は等しい。この方程式を解いて、"
            "分けた底辺の長さを求める。",
            note=f"{c}² - x² = {b}² - ({a} - x)²",
        ),
        _step(
            "apply_pythagorean_theorem",
            "求めた長さを一方の直角三角形にあてはめて、三平方の定理から高さを求める。",
            height, "cm",
        ),
        Step(
            op="compute_triangle_area", args=[], result_srepr=sympy.srepr(result),
            # この手で得たのは面積だけ（高さは前の手）。
            result_display=_fmt(area, "cm²"),
            narration="底辺と、いま求めた高さから、三角形の面積を求める。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(result), display=display), steps=steps
        )
    ]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "rhombus_diagonal_area": solve_rhombus_diagonal_area,
    "square_pyramid_height_volume": solve_square_pyramid_height_volume,
    "box_surface_shortest_path": solve_box_surface_shortest_path,
    "cube_vertex_to_plane": solve_cube_vertex_to_plane,
    "box_shortest_path_choose": solve_box_shortest_path_choose,
    "triangle_height_area_solo": solve_triangle_height_area_solo,
    "exam_box_space_diagonal": solve_exam_box_space_diagonal,
    # 数学は g3_l56 Lv4 と同じ（問い文の置き場所だけが違う）ので solve は共有する。
    "exam_box_shortest_path_choose": solve_box_shortest_path_choose,
    "exam_cube_guided": solve_exam_cube_guided,
    "exam_regular_tetrahedron": solve_exam_regular_tetrahedron,
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


def _exam_box_diagonal_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(縦, 横, 高さ) の候補。**対角線が整数になる**組だけを残す。

    立体の対角線は √(a²+b²+h²) で、一般には無理数のまま答えてよいのだが、
    ここは「断面に落とせば三平方が2回で済む」という筋道を見せるセルなので、
    答えが整数に落ちる組（3,4,12→13 のような組）に絞って読みやすくする。
    3辺は相異にする（立方体だと底面の対角線を経由する意味が薄れる）。
    """
    lo, hi = (int(v) for v in p["edge_range"])
    out: list[tuple[int, int, int]] = []
    for a in range(lo, hi + 1):
        for b in range(a + 1, hi + 1):
            for h in range(b + 1, hi + 1):
                total = a * a + b * b + h * h
                root = sympy.Integer(total)
                if sympy.sqrt(root).is_Integer:
                    out.append((a, b, h))
    return out


def _scene_exam_box_space_diagonal(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """exam_l4.find_value Lv3: 直方体の対角線（問い文は given.condition に載せる）。"""
    a, b, h = _draw_from(_exam_box_diagonal_candidates(p), rng)
    n = _draw_consecutive_labels(8, rng)
    solid = f"{n[0]}{n[1]}{n[2]}{n[3]}-{n[4]}{n[5]}{n[6]}{n[7]}"
    statement = (
        f"縦{a}cm、横{b}cm、高さ{h}cmの直方体{solid}がある。"
        f"対角線{n[0]}{n[6]}の長さを、断面の直角三角形に三平方の定理を用いて求めよ"
    )
    return PythagoreanScene(
        numbers={"edge_a": a, "edge_b": b, "height": h},
        scenario=statement, ask_texts=("",), slots={"solid": solid},
    )


def _triangle_height_area_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(底辺BC, CA, AB) の候補。**高さが整数**に落ちる三角形だけを残す。

    高さが無理数だと面積も無理数になり、「補助線を引いて高さを出す」という筋道より
    式の処理に目が行ってしまう。二等辺（CA=AB）は垂線の足が中点に来て
    「未知数を置いて2通りに表す」段が要らなくなるので外す。
    """
    lo, hi = (int(v) for v in p["side_range"])
    out: list[tuple[int, int, int]] = []
    for base in range(lo, hi + 1):
        for side_b in range(lo, hi + 1):
            for side_c in range(lo, hi + 1):
                if side_b == side_c:
                    continue
                if not (base + side_b > side_c and side_b + side_c > base
                        and side_c + base > side_b):
                    continue
                num = side_c**2 - side_b**2 + base**2
                if num % (2 * base):
                    continue
                x = num // (2 * base)
                if not (0 < x < base):
                    continue
                height_squared = side_c**2 - x**2
                height = sympy.Integer(height_squared)
                if not sympy.sqrt(height).is_Integer or height_squared == 0:
                    continue
                out.append((base, side_b, side_c))
    return out


def _scene_triangle_height_area_solo(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """g3_l53.word_problem Lv4: 3辺を与えて高さと面積（誘導なし1小問）。"""
    base, side_b, side_c = _draw_from(_triangle_height_area_candidates(p), rng)
    n = _draw_consecutive_labels(3, rng)
    scenario = (
        f"{n[0]}{n[1]}が{side_c}cm、{n[1]}{n[2]}が{base}cm、{n[2]}{n[0]}が{side_b}cmの"
        f"三角形{n}がある。"
    )
    ask_texts = (
        f"必要な補助線を自分で引き、辺{n[1]}{n[2]}を底辺としたときの高さと"
        f"三角形{n}の面積を求めよ。",
    )
    return PythagoreanScene(
        numbers={"base": base, "side_b": side_b, "side_c": side_c},
        scenario=scenario, ask_texts=ask_texts, slots={"vertices": n},
    )


def _scene_exam_box_shortest_choose(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """exam_l4.find_value Lv4: 開き方を自分で選ぶ最短距離（問い文は condition に載せる）。

    数学は既存の `box_shortest_path_choose` と同じで、違いは
    **問い文を given.condition の中に畳む**こと（find_value のテンプレートは
    context_slots の小問文を描かないので、ask に置くと問いが本文から消える）。
    """
    cands = [int(v) for v in _domain_values(p["edge_domain"])]
    edge_a = int(draw({"int_set": cands}, rng))
    edge_b = int(draw({"int_set": [v for v in cands if v != edge_a]}, rng))
    height = int(draw({"int_set": [v for v in cands if v not in (edge_a, edge_b)]}, rng))
    n = _draw_consecutive_labels(8, rng)
    base, top = n[:4], n[4:]
    statement = (
        f"辺{base[0]}{base[1]}の長さが{edge_a}cm、辺{base[1]}{base[2]}の長さが{edge_b}cm、"
        f"高さが{height}cmの直方体{base}-{top}がある（{base}が底面、{top}が上面で、"
        f"辺{base[0]}{top[0]}が高さにあたる）。この直方体の表面上を頂点{base[0]}から"
        f"頂点{top[2]}まで進むとき、どの面をどのように開くと最短になるかを自分で判断し、"
        "その最短の道のりを求めよ"
    )
    return PythagoreanScene(
        numbers={"edge_a": edge_a, "edge_b": edge_b, "height": height},
        scenario=statement, ask_texts=("",), slots={"labels": n},
    )


def _scene_exam_cube_guided(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """exam_l4.word_problem Lv3: 立方体の誘導あり3小問。"""
    edge = int(draw(p["edge_domain"], rng))
    n = _draw_consecutive_labels(8, rng)
    solid = f"{n[0]}{n[1]}{n[2]}{n[3]}-{n[4]}{n[5]}{n[6]}{n[7]}"
    scenario = f"1辺が{edge}cmの立方体{solid}がある。"
    ask_texts = (
        f"対角線{n[0]}{n[6]}の長さを求めよ。",
        f"三角形{n[0]}{n[5]}{n[7]}の面積を求めよ。",
        f"頂点{n[1]}から表面上を通って頂点{n[7]}まで進むときの最短の道のりを、"
        "展開図を利用して求めよ。",
    )
    return PythagoreanScene(
        numbers={"edge": edge}, scenario=scenario, ask_texts=ask_texts,
        slots={"solid": solid},
    )


# 正四面体の体積 a³√2/12 の、既約分数にしたときの分子の上限。
# 1辺6cm → 18√2、12cm → 144√2、18cm → 486√2 までが読める大きさ。
_MAX_TETRAHEDRON_VOLUME_NUMERATOR = 500


def _tetrahedron_edges(domain: Mapping[str, Any]) -> list[int]:
    """1辺の候補のうち、**体積の係数が上限内**のものだけ（原則⓪: 答えの大きさで測る）。"""
    lo, hi = (int(v) for v in cast("list[object]", domain["int_range"]))
    return [
        a
        for a in range(lo, hi + 1)
        if a**3 // gcd(a**3, 12) <= _MAX_TETRAHEDRON_VOLUME_NUMERATOR
    ]


def _scene_exam_regular_tetrahedron(p: Mapping[str, Any], rng: Rng) -> PythagoreanScene:
    """exam_l4.word_problem Lv4: 正四面体の高さと体積（誘導なし1小問）。

    **体積の係数が大きくなる1辺は引き直す**（EVALUATION D-31。体積は 1辺³×√2/12 なので、
    定義域を 2〜24 に狭めても 1辺23cm で `12167√2/12 cm³` になっていた。壊れているのは
    定義域の広さではなく答えの大きさ＝原則⓪）。教科書は1辺6cm（18√2）のあたりを使う。
    """
    edge = int(draw({"int_set": _tetrahedron_edges(p["edge_domain"])}, rng))
    n = _draw_consecutive_labels(4, rng)
    foot = str(_draw_from([str(v) for v in p["foot_candidates"] if str(v) not in n], rng))
    scenario = f"1辺が{edge}cmの正四面体{n}がある。"
    ask_texts = (
        f"点{n[0]}から底面{n[1]}{n[2]}{n[3]}に下ろした垂線の足を{foot}とするとき、"
        f"この正四面体の高さ{n[0]}{foot}と体積を求めよ。必要な断面は自分で取り出してよい。",
    )
    return PythagoreanScene(
        numbers={"edge": edge}, scenario=scenario, ask_texts=ask_texts,
        slots={"vertices": n, "foot": foot},
    )


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], PythagoreanScene]] = {
    "rhombus_diagonal_area": _scene_rhombus_diagonal_area,
    "square_pyramid_height_volume": _scene_square_pyramid_height_volume,
    "box_surface_shortest_path": _scene_box_surface_shortest_path,
    "cube_vertex_to_plane": _scene_cube_vertex_to_plane,
    "box_shortest_path_choose": _scene_box_shortest_path_choose,
    "triangle_height_area_solo": _scene_triangle_height_area_solo,
    "exam_box_space_diagonal": _scene_exam_box_space_diagonal,
    "exam_box_shortest_path_choose": _scene_exam_box_shortest_choose,
    "exam_cube_guided": _scene_exam_cube_guided,
    "exam_regular_tetrahedron": _scene_exam_regular_tetrahedron,
}


# ---------------------------------------------------------------------------
# recipe（3セル共通。scenario_kind が題材＝どの立体・どの平面図形かを選ぶ）
# ---------------------------------------------------------------------------
# 答えが大きすぎたときに引き直す回数（`pythagorean_find_value.py` と同じ理由）。
_ANSWER_SIZE_REDRAWS = 40


def _draw_scene_with_answer_in_range(
    ctx: CellContext, rng: Rng, kind: str
) -> tuple[PythagoreanScene, list[Solution]]:
    """答えの大きさ（根号の中・分母・分子）が上限内になる組を引く。

    定義域は広いまま、超えたら組み直す（`engine.core.verify.answer_size`）。
    小問が2つあるセルは**どちらの答えも**上限内であることを見る。
    """
    p = ctx.spec_level.params
    limits = limits_for(ctx.spec_level)
    scene = solutions = None
    for attempt in range(_ANSWER_SIZE_REDRAWS):
        attempt_rng = rng.spawn(attempt) if attempt else rng
        scene = _SCENE_BUILDERS[kind](p, attempt_rng)
        solutions = SOLVE_BUILDERS[kind](scene.numbers)
        displays = [str(getattr(s.answer, "display", "") or "") for s in solutions]
        if not any(answer_is_too_big(d, limits) for d in displays):
            break
    assert scene is not None and solutions is not None
    return scene, solutions


@register_recipe(RECIPE_NAME, provides_concepts=_PYTHAGOREAN_WP_CONCEPTS)
def word_problem_pythagorean(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene, solutions = _draw_scene_with_answer_in_range(ctx, rng, kind)
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
        if text:
            context_slots[f"ask_{i + 1}"] = text
    if len(scene.ask_texts) == 1 and scene.ask_texts[0]:
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
        # find_value の frame は given に "scenario" を許さない（語彙が condition 側）。
        # 場面文の中身は同じなので、どのキーに載せるかだけを family が決める。
        given={str(p.get("given_key", "scenario")): scene.scenario},
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
