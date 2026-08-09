"""基本作図（form: construction）の recipe（構成的生成・answer-first。§6.1）。

C7（g1 平面図形）の作図セル: g1_l41（垂直二等分線）/ g1_l42（角の二等分線）/
g1_l43（垂線）/ g1_l44（作図の利用）。**この form の最初の実装**である。

この form の型（units.generated.yaml の desc/example を正とする）
--------------------------------------------------------------
問題文は「与えられた図」＋「何を作図するか」＋「作図に用いた線は残すこと」の3点で
固定されている。動くのは**図**である。したがって:

- `given` は frame 語彙どおり `construction_conditions` の1本だけ（与えられた図の言い方）。
- 問題の多様性は図のパラメータ（線分の向きと長さ・角の大きさ・点の位置・記号の名前）が
  作る。**型を数個並べるだけでは dup_rate 0.20 を割れない**ので、妥当な組を全列挙して
  index を1回引く（`draw` 以外で乱数を解釈しない・H8）。
- 答えは `GraphAnswer`。作図で得られる直線は正規化係数、点は座標で持ち、独立ソルバと
  突き合わせる（double-solve）。**模範解答図**（弧つき）は `solution_svg_ref` に入れる。

level_sep（Lv 間で構造が変わるところ）
--------------------------------------
基本作図1つ（弧2〜3手＋直線1手）が Lv1。応用の Lv では「交点をとる」「足を示す」
「どの作図を使うか決める」という手が積み増され、steps の op 列が相異する。

厳密性の担保
------------
角の二等分線の向きは u/|u| + v/|v| で一般には無理数になる。そこで角の2辺は
**長さが整数の方向ベクトル**（(3,4) など）からだけ引く。すると二等分線の向きは
u|v| + v|u| という整数ベクトルになり、交点も有理点に閉じる（近似一致に頼らない）。

G-Q5t（漏洩）の設計: テンプレートにも narration にも数字を書かない。本文に出る数は
「2点」「3点」「1つ」「2辺」のような助数詞だけで、これは given 由来かつ助数詞除去の
対象なので、答えの座標と衝突しない。
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.visuals.construction_figure import (
    figures_angle,
    figures_angle_with_chord,
    figures_perp_bisector_segment,
    figures_point_and_line,
    figures_point_line_foot,
    figures_three_points,
    figures_triangle_bisector,
    figures_two_points,
    figures_two_points_and_line,
)

_LINE_NAME = "ℓ"
_IntVec = tuple[int, int]


# ---------------------------------------------------------------------------
# MR 組み立ての共通部
# ---------------------------------------------------------------------------
def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _sub_question(ctx: CellContext, *, answer: Any, steps: list[Any]) -> SubQuestionMR:
    return SubQuestionMR(
        label="(1)",
        asked="construction_steps",
        answer=answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=list(ctx.spec_level.cause_tags),
    )


def _mr(
    ctx: CellContext,
    *,
    params: dict[str, Any],
    conditions: str,
    answer: Any,
    steps: list[Any],
    figure_svg: str,
    labels: list[str],
    elements: list[str],
    recipe: str,
) -> MR:
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given={"construction_conditions": conditions},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[_sub_question(ctx, answer=answer, steps=steps)],
        visual_plan=VisualPlan(
            style="construction",
            labels=labels,
            elements=[VisualElement(kind=k, attrs={}) for k in elements],
        ),
        provenance=Provenance(recipe=recipe),
    )


def _answer(sol: Solution, solution_svg: str) -> GraphAnswer:
    assert isinstance(sol.answer, GraphAnswer)
    return GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)


def _feat(sol: Solution, kind: str) -> Any:
    """solver が返した特徴を1つ取り出す（同じ kind が2つあれば構成の誤り）。"""
    assert isinstance(sol.answer, GraphAnswer)
    hits = [f for f in sol.answer.features if f.kind == kind]
    assert len(hits) == 1, f"特徴 {kind!r} が {len(hits)} 個ある"
    return sympy.sympify(hits[0].srepr)


def _assert_point(sol: Solution, kind: str, expected: tuple[Any, Any]) -> None:
    got = _feat(sol, kind)
    assert tuple(got) == tuple(expected), (
        f"double-solve 不一致（{kind}）: 構成 {tuple(expected)} != solver {tuple(got)}"
    )


def _assert_line(
    sol: Solution,
    kind: str,
    *,
    through: tuple[Any, Any],
    perpendicular_to: tuple[Any, Any] | None = None,
    parallel_to: tuple[Any, Any] | None = None,
) -> tuple[Any, Any]:
    """直線の特徴 (a, b, c) を**満たすべき条件**で検証し、その向きベクトルを返す。

    solver と同じ式で座標を組み直しても検証にならないので、「その点を通る」
    「この向きに垂直/平行」という定義そのものを突き合わせる。
    """
    a, b, c = _feat(sol, kind)
    assert (a, b) != (0, 0), f"{kind}: 直線になっていない"
    assert a * through[0] + b * through[1] + c == 0, f"{kind}: 通るはずの点を通っていない"
    if perpendicular_to is not None:
        # 直線が v に垂直 ⇔ 法線 (a, b) が v に平行
        assert a * perpendicular_to[1] - b * perpendicular_to[0] == 0, f"{kind}: 垂直でない"
    if parallel_to is not None:
        assert a * parallel_to[0] + b * parallel_to[1] == 0, f"{kind}: 平行でない"
    return (-b, a)


def _assert_bisects(direction: tuple[Any, Any], u: tuple[Any, Any], v: tuple[Any, Any]) -> None:
    """向き direction が u と v のなす角を二等分していることを確かめる。

    cos の等式 (u·d)/|u| = (v·d)/|v| の分母を払った形で見る（無理数を持ち込まない）。
    内積が 0 でないことで、角の内側を向いた二等分線であることも押さえる。
    """
    lu = sympy.sqrt(u[0] ** 2 + u[1] ** 2)
    lv = sympy.sqrt(v[0] ** 2 + v[1] ** 2)
    du = u[0] * direction[0] + u[1] * direction[1]
    dv = v[0] * direction[0] + v[1] * direction[1]
    assert sympy.simplify(du * lv - dv * lu) == 0, "角を二等分していない"
    assert du != 0, "二等分線が辺に垂直になっている"


def _pick(combos: tuple[Any, ...], rng: Rng) -> Any:
    """全列挙した組から index を1回だけ引く（順に引くと確率が偏る・§6.1）。"""
    return combos[int(draw({"int_set": list(range(len(combos)))}, rng))]


# ---------------------------------------------------------------------------
# 整数ベクトルの候補（列挙は family の params だけで決まるので lru_cache が効く）
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _vectors(lo: int, hi: int) -> tuple[_IntVec, ...]:
    """長さが lo 以上 hi 以下の格子ベクトル。"""
    return tuple(
        (x, y)
        for x in range(-hi, hi + 1)
        for y in range(-hi, hi + 1)
        if (x, y) != (0, 0) and lo * lo <= x * x + y * y <= hi * hi
    )


@lru_cache(maxsize=None)
def _integer_length_vectors(lo: int, hi: int) -> tuple[_IntVec, ...]:
    """長さが**整数**の格子ベクトル（角の二等分線を有理数に閉じるために使う）。"""
    out: list[_IntVec] = []
    for x in range(-hi, hi + 1):
        for y in range(-hi, hi + 1):
            if (x, y) == (0, 0):
                continue
            n2 = x * x + y * y
            r = math.isqrt(n2)
            if r * r == n2 and lo <= r <= hi:
                out.append((x, y))
    return tuple(out)


def _angle_deg(u: _IntVec, v: _IntVec) -> float:
    cross = u[0] * v[1] - u[1] * v[0]
    dot = u[0] * v[0] + u[1] * v[1]
    return math.degrees(math.atan2(abs(cross), dot))


def _f(v: object) -> float:
    return float(sympy.Rational(v))


def _fpt(x: object, y: object) -> tuple[float, float]:
    return (_f(x), _f(y))


# ---------------------------------------------------------------------------
# g1_l41.construction Lv1 — 線分の垂直二等分線
# ---------------------------------------------------------------------------
_PERP_BISECTOR_CONCEPTS = ["construction.perpendicular_bisector_basic"]

_SEGMENT_NAMES: tuple[tuple[str, str], ...] = (
    ("A", "B"), ("P", "Q"), ("C", "D"), ("M", "N"), ("A", "C"),
)


@lru_cache(maxsize=None)
def _combos_segment(lo: int, hi: int, n_names: int) -> tuple[tuple[_IntVec, int], ...]:
    return tuple((v, i) for v in _vectors(lo, hi) for i in range(n_names))


@register_recipe(
    "math.construct_perpendicular_bisector", provides_concepts=_PERP_BISECTOR_CONCEPTS
)
def construct_perpendicular_bisector(ctx: CellContext, rng: Rng) -> MR:
    """線分の垂直二等分線を基本手順で作図する（g1_l41.construction Lv1）。

    動かすのは線分の向き・長さ・端点の記号。答えは中点と垂直二等分線（正規形の係数）。
    """
    p = ctx.spec_level.params
    combos = _combos_segment(int(p["len_min"]), int(p["len_max"]), len(_SEGMENT_NAMES))
    (vx, vy), name_idx = _pick(combos, rng)
    na, nb = _SEGMENT_NAMES[name_idx]
    ax, ay, bx, by = 0, 0, vx, vy

    solver = REGISTRY.solver("math.perpendicular_bisector_of_segment")
    sol = cast(Solution, solver(ax, ay, bx, by, na, nb))
    mid = (sympy.Rational(ax + bx, 2), sympy.Rational(ay + by, 2))
    _assert_point(sol, "midpoint", mid)
    _assert_line(
        sol, "perpendicular_bisector", through=mid, perpendicular_to=(bx - ax, by - ay)
    )

    problem_svg, solution_svg = figures_perp_bisector_segment(
        (ax, ay), (bx, by), na, nb
    )
    return _mr(
        ctx,
        params={"ax": ax, "ay": ay, "bx": bx, "by": by, "name_a": na, "name_b": nb},
        conditions=f"線分{na}{nb}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[na, nb],
        elements=["given_segment", "given_point", "given_point"],
        recipe="math.construct_perpendicular_bisector",
    )


# ---------------------------------------------------------------------------
# g1_l41.construction Lv2 — 2点から等距離で直線上にある点
# ---------------------------------------------------------------------------
_EQUIDISTANT_ON_LINE_CONCEPTS = ["construction.equidistant_point_on_line"]

_LINE_DIRS: tuple[_IntVec, ...] = ((1, 0), (5, 1), (5, -1), (4, 1), (4, -1), (3, 1))
_PAIR_NAMES: tuple[tuple[str, str], ...] = (("A", "B"), ("C", "D"), ("M", "N"))


@lru_cache(maxsize=None)
def _combos_point_on_line(
    box: int, off_min2: int, vlo: int, vhi: int, pmax: int, n_names: int
) -> tuple[tuple[int, int, int, _IntVec, int], ...]:
    """(直線の向きの index, ax, ay, AB ベクトル, 記号の index) の妥当な組を全列挙する。

    妥当 = 2点が直線から離れている・垂直二等分線が直線と平行でない・交点 P が枠に収まる。
    すべて整数演算で判定する（有理数の生成を避けて列挙を軽くする）。
    """
    out: list[tuple[int, int, int, _IntVec, int]] = []
    vecs = _vectors(vlo, vhi)
    for di, d in enumerate(_LINE_DIRS):
        d2 = d[0] * d[0] + d[1] * d[1]
        for ax in range(-box, box + 1):
            for ay in range(-box, box + 1):
                cross_a = d[0] * ay - d[1] * ax
                if cross_a * cross_a * 4 < off_min2 * d2:
                    continue
                for v in vecs:
                    bx, by = ax + v[0], ay + v[1]
                    if abs(bx) > box or abs(by) > box:
                        continue
                    cross_b = d[0] * by - d[1] * bx
                    if cross_b * cross_b * 4 < off_min2 * d2:
                        continue
                    den = 2 * (v[0] * d[0] + v[1] * d[1])
                    if den == 0:
                        continue
                    num = v[0] * (ax + bx) + v[1] * (ay + by)
                    if abs(d[0] * num) > pmax * abs(den) or abs(d[1] * num) > pmax * abs(den):
                        continue
                    for i in range(n_names):
                        out.append((di, ax, ay, v, i))
    return tuple(out)


@register_recipe(
    "math.construct_equidistant_point_on_line", provides_concepts=_EQUIDISTANT_ON_LINE_CONCEPTS
)
def construct_equidistant_point_on_line(ctx: CellContext, rng: Rng) -> MR:
    """2点から等距離で直線ℓ上にある点Pを作図で求める（g1_l41.construction Lv2）。

    Lv1 の3手（弧・弧・直線）に「交点をとる」「その点が求める点と確かめる」が積み増され、
    op 列が相異する＝level_sep。
    """
    p = ctx.spec_level.params
    combos = _combos_point_on_line(
        int(p["box"]), int(p["offset_min_sq4"]), int(p["len_min"]), int(p["len_max"]),
        int(p["point_max"]), len(_PAIR_NAMES),
    )
    di, ax, ay, v, name_idx = _pick(combos, rng)
    d = _LINE_DIRS[di]
    na, nb = _PAIR_NAMES[name_idx]
    bx, by = ax + v[0], ay + v[1]

    solver = REGISTRY.solver("math.equidistant_point_on_line")
    sol = cast(Solution, solver(ax, ay, bx, by, 0, 0, d[0], d[1], na, nb))
    mid = (sympy.Rational(ax + bx, 2), sympy.Rational(ay + by, 2))
    _assert_line(sol, "perpendicular_bisector", through=mid, perpendicular_to=v)
    p_pt = _feat(sol, "point")
    # 求める点の条件そのもので確かめる: 2点から等距離であり、かつ直線ℓ（原点を通り向き d）上にある。
    assert (p_pt[0] - ax) ** 2 + (p_pt[1] - ay) ** 2 == (p_pt[0] - bx) ** 2 + (p_pt[1] - by) ** 2
    assert p_pt[0] * d[1] - p_pt[1] * d[0] == 0

    problem_svg, solution_svg = figures_two_points_and_line(
        (ax, ay), (bx, by), na, nb, (0.0, 0.0), d, _LINE_NAME, _fpt(*p_pt), "P"
    )
    return _mr(
        ctx,
        params={
            "ax": ax, "ay": ay, "bx": bx, "by": by,
            "lx": 0, "ly": 0, "ldx": d[0], "ldy": d[1],
            "name_a": na, "name_b": nb, "line_name": _LINE_NAME,
        },
        conditions=f"2点{na}、{nb}と直線{_LINE_NAME}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[na, nb, _LINE_NAME],
        elements=["given_line", "given_point", "given_point"],
        recipe="math.construct_equidistant_point_on_line",
    )


# ---------------------------------------------------------------------------
# g1_l42.construction Lv1 — 角の二等分線
# ---------------------------------------------------------------------------
_ANGLE_BISECTOR_CONCEPTS = ["construction.angle_bisector_basic"]

_ANGLE_NAMES: tuple[tuple[str, str, str], ...] = (
    ("O", "A", "B"), ("O", "X", "Y"), ("B", "A", "C"), ("O", "P", "Q"),
)
_ANGLE_NAMES_NO_P: tuple[tuple[str, str, str], ...] = (
    ("O", "A", "B"), ("O", "X", "Y"), ("B", "A", "C"),
)


@lru_cache(maxsize=None)
def _combos_angle(
    lo: int, hi: int, amin: int, amax: int, n_names: int
) -> tuple[tuple[_IntVec, _IntVec, int], ...]:
    vecs = _integer_length_vectors(lo, hi)
    out: list[tuple[_IntVec, _IntVec, int]] = []
    for u in vecs:
        for v in vecs:
            if u[0] * v[1] - u[1] * v[0] == 0:
                continue
            ang = _angle_deg(u, v)
            if not (amin <= ang <= amax):
                continue
            for i in range(n_names):
                out.append((u, v, i))
    return tuple(out)


@register_recipe("math.construct_angle_bisector", provides_concepts=_ANGLE_BISECTOR_CONCEPTS)
def construct_angle_bisector(ctx: CellContext, rng: Rng) -> MR:
    """角の二等分線を基本手順で作図する（g1_l42.construction Lv1）。

    2辺は**長さが整数の方向ベクトル**から引くので、二等分線の向き u|v|+v|u| は整数に
    なり、答えを厳密に照合できる。
    """
    p = ctx.spec_level.params
    combos = _combos_angle(
        int(p["side_min"]), int(p["side_max"]), int(p["angle_min"]), int(p["angle_max"]),
        len(_ANGLE_NAMES),
    )
    u, v, name_idx = _pick(combos, rng)
    no, n1, n2 = _ANGLE_NAMES[name_idx]

    solver = REGISTRY.solver("math.angle_bisector_of_angle")
    sol = cast(Solution, solver(0, 0, u[0], u[1], v[0], v[1], no, n1, n2))
    _assert_point(sol, "vertex", (sympy.Integer(0), sympy.Integer(0)))
    _assert_bisects(_assert_line(sol, "angle_bisector", through=(0, 0)), u, v)

    problem_svg, solution_svg = figures_angle(
        (0.0, 0.0), (float(u[0]), float(u[1])), (float(v[0]), float(v[1])), no, n1, n2
    )
    return _mr(
        ctx,
        params={
            "ox": 0, "oy": 0, "ux": u[0], "uy": u[1], "vx": v[0], "vy": v[1],
            "name_o": no, "name_1": n1, "name_2": n2,
        },
        conditions=f"∠{n1}{no}{n2}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[no, n1, n2],
        elements=["given_ray", "given_ray", "given_point", "given_point", "given_point"],
        recipe="math.construct_angle_bisector",
    )


# ---------------------------------------------------------------------------
# g1_l42.construction Lv2 — 2辺から等距離で線分上にある点
# ---------------------------------------------------------------------------
_EQUIDISTANT_SIDES_CONCEPTS = ["construction.equidistant_point_from_two_sides"]


@register_recipe(
    "math.construct_equidistant_point_from_two_sides",
    provides_concepts=_EQUIDISTANT_SIDES_CONCEPTS,
)
def construct_equidistant_point_from_two_sides(ctx: CellContext, rng: Rng) -> MR:
    """角の2辺から等距離で、2辺の端を結ぶ線分上にある点Pを求める（g1_l42 Lv2）。

    二等分線は必ず線分XYの内部で交わるので、退化（交点が線分の外に出る）は構成上起きない。
    Lv1 の3手に「交点をとる」「性質で確かめる」が積み増され op 列が相異＝level_sep。
    """
    p = ctx.spec_level.params
    combos = _combos_angle(
        int(p["side_min"]), int(p["side_max"]), int(p["angle_min"]), int(p["angle_max"]),
        len(_ANGLE_NAMES_NO_P),
    )
    u, v, name_idx = _pick(combos, rng)
    no, n1, n2 = _ANGLE_NAMES_NO_P[name_idx]

    solver = REGISTRY.solver("math.equidistant_point_from_two_sides")
    sol = cast(Solution, solver(0, 0, u[0], u[1], v[0], v[1], no, n1, n2))
    _assert_bisects(_assert_line(sol, "angle_bisector", through=(0, 0)), u, v)
    p_pt = _feat(sol, "point")
    # 求める点の条件そのもの: 角の二等分線上（頂点は原点なので OP がその向き）で、
    # かつ線分 XY の内側にある。
    _assert_bisects((p_pt[0], p_pt[1]), u, v)
    assert (p_pt[0] - u[0]) * (v[1] - u[1]) - (p_pt[1] - u[1]) * (v[0] - u[0]) == 0
    assert (p_pt[0] - u[0]) * (v[0] - u[0]) + (p_pt[1] - u[1]) * (v[1] - u[1]) > 0
    assert (p_pt[0] - v[0]) * (u[0] - v[0]) + (p_pt[1] - v[1]) * (u[1] - v[1]) > 0

    problem_svg, solution_svg = figures_angle_with_chord(
        (0.0, 0.0), (float(u[0]), float(u[1])), (float(v[0]), float(v[1])),
        no, n1, n2, _fpt(*p_pt), "P",
    )
    return _mr(
        ctx,
        params={
            "ox": 0, "oy": 0, "ux": u[0], "uy": u[1], "vx": v[0], "vy": v[1],
            "name_o": no, "name_1": n1, "name_2": n2,
        },
        conditions=f"∠{n1}{no}{n2}と線分{n1}{n2}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[no, n1, n2],
        elements=["given_ray", "given_ray", "given_segment", "given_point"],
        recipe="math.construct_equidistant_point_from_two_sides",
    )


# ---------------------------------------------------------------------------
# g1_l43.construction Lv1 — 点を通る垂線
# ---------------------------------------------------------------------------
_PERPENDICULAR_CONCEPTS = ["construction.perpendicular_basic"]

_PERP_DIRS: tuple[_IntVec, ...] = ((1, 0), (5, 1), (5, -1), (4, 1), (4, -1), (3, 1), (3, -1))
_PERP_POINT_NAMES: tuple[str, ...] = ("P", "Q", "A")


@lru_cache(maxsize=None)
def _combos_point_and_line(
    box: int, dmin2: int, dmax2: int, n_names: int, allow_on_line: bool
) -> tuple[tuple[int, int, int, int], ...]:
    """(直線の向き index, px, py, 記号 index)。距離が範囲内、または直線上（許す場合）。"""
    out: list[tuple[int, int, int, int]] = []
    for di, d in enumerate(_PERP_DIRS):
        d2 = d[0] * d[0] + d[1] * d[1]
        for px in range(-box, box + 1):
            for py in range(-box, box + 1):
                if (px, py) == (0, 0):
                    continue
                cross = d[0] * py - d[1] * px
                sq = cross * cross
                on_line = cross == 0
                if on_line:
                    if not allow_on_line:
                        continue
                elif not (dmin2 * d2 <= sq * 100 <= dmax2 * d2):
                    continue
                for i in range(n_names):
                    out.append((di, px, py, i))
    return tuple(out)


@register_recipe("math.construct_perpendicular", provides_concepts=_PERPENDICULAR_CONCEPTS)
def construct_perpendicular(ctx: CellContext, rng: Rng) -> MR:
    """直線上の点／直線外の点を通る垂線を基本手順で作図する（g1_l43.construction Lv1）。

    台帳 desc のとおり2つの場合（直線上／直線外）を両方出す。手順は同じ（点を中心に
    直線と二点で交わる円→その二点から等半径の弧→交点と結ぶ）なので op 列は変わらない。
    """
    p = ctx.spec_level.params
    combos = _combos_point_and_line(
        int(p["box"]), int(p["dist_min_sq100"]), int(p["dist_max_sq100"]),
        len(_PERP_POINT_NAMES), True,
    )
    di, px, py, name_idx = _pick(combos, rng)
    d = _PERP_DIRS[di]
    name = _PERP_POINT_NAMES[name_idx]
    on_line = d[0] * py - d[1] * px == 0

    solver = REGISTRY.solver("math.perpendicular_through_point")
    sol = cast(Solution, solver(px, py, 0, 0, d[0], d[1], name))
    _assert_point(sol, "through_point", (sympy.Integer(px), sympy.Integer(py)))
    _assert_line(sol, "perpendicular_line", through=(px, py), perpendicular_to=d)

    t = sympy.Rational(px * d[0] + py * d[1], d[0] ** 2 + d[1] ** 2)
    foot = (t * d[0], t * d[1])
    problem_svg, solution_svg = figures_point_and_line(
        (float(px), float(py)), (0.0, 0.0), d, _LINE_NAME, name, _fpt(*foot)
    )
    where = "その直線上の" if on_line else "その直線上にない"
    return _mr(
        ctx,
        params={
            "px": px, "py": py, "lx": 0, "ly": 0, "ldx": d[0], "ldy": d[1],
            "name_p": name, "line_name": _LINE_NAME,
        },
        conditions=f"直線{_LINE_NAME}と、{where}点{name}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[name, _LINE_NAME],
        elements=["given_line", "given_point"],
        recipe="math.construct_perpendicular",
    )


# ---------------------------------------------------------------------------
# g1_l43.construction Lv2 — 垂線の足と点と直線の距離
# ---------------------------------------------------------------------------
_FOOT_DISTANCE_CONCEPTS = ["construction.foot_and_point_line_distance"]


@register_recipe(
    "math.construct_foot_and_distance", provides_concepts=_FOOT_DISTANCE_CONCEPTS
)
def construct_foot_and_distance(ctx: CellContext, rng: Rng) -> MR:
    """点と直線の距離を表す線分をかき、垂線の足Hを示す（g1_l43.construction Lv2）。

    点は必ず直線の外（距離が正）。Lv1 の3手に「足に印をつける」「距離の線分をひく」が
    積み増され op 列が相異＝level_sep。
    """
    p = ctx.spec_level.params
    combos = _combos_point_and_line(
        int(p["box"]), int(p["dist_min_sq100"]), int(p["dist_max_sq100"]), 1, False
    )
    di, px, py, _ = _pick(combos, rng)
    d = _PERP_DIRS[di]
    name, hname = "P", "H"

    solver = REGISTRY.solver("math.foot_and_point_line_distance")
    sol = cast(Solution, solver(px, py, 0, 0, d[0], d[1], name, hname))
    _assert_line(sol, "perpendicular_line", through=(px, py), perpendicular_to=d)
    foot = _feat(sol, "foot")
    # 垂線の足の条件そのもの: 直線ℓ（原点を通り向き d）上にあり、PH が ℓ に垂直。
    assert foot[0] * d[1] - foot[1] * d[0] == 0
    assert (px - foot[0]) * d[0] + (py - foot[1]) * d[1] == 0

    problem_svg, solution_svg = figures_point_line_foot(
        (float(px), float(py)), (0.0, 0.0), d, _LINE_NAME, name, _fpt(*foot), hname
    )
    return _mr(
        ctx,
        params={
            "px": px, "py": py, "lx": 0, "ly": 0, "ldx": d[0], "ldy": d[1],
            "name_p": name, "name_h": hname, "line_name": _LINE_NAME,
        },
        conditions=f"直線{_LINE_NAME}と、直線上にない点{name}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[name, _LINE_NAME],
        elements=["given_line", "given_point"],
        recipe="math.construct_foot_and_distance",
    )


# ---------------------------------------------------------------------------
# g1_l44.construction Lv2 — 2点から等距離にある点の集まり（基本作図1つ・誘導あり）
# ---------------------------------------------------------------------------
_LOCUS_TWO_POINTS_CONCEPTS = ["construction.locus_equidistant_two_points"]

_LOCUS_NAMES: tuple[tuple[str, str], ...] = (
    ("A", "B"), ("C", "D"), ("M", "N"), ("P", "Q"), ("A", "C"), ("B", "D"),
)


@register_recipe(
    "math.construct_locus_equidistant_two_points", provides_concepts=_LOCUS_TWO_POINTS_CONCEPTS
)
def construct_locus_equidistant_two_points(ctx: CellContext, rng: Rng) -> MR:
    """2点から等距離にある点の集まりを、基本作図1つで作図する（g1_l44.construction Lv2）。

    与えられるのは**2点だけ**（線分ではない）。「どの基本作図を使うか」を選ぶ手が
    先頭に立つ（誘導あり）ので、g1_l41 Lv1 と同じ図でも手順の構造が違う。
    """
    p = ctx.spec_level.params
    combos = _combos_segment(int(p["len_min"]), int(p["len_max"]), len(_LOCUS_NAMES))
    (vx, vy), name_idx = _pick(combos, rng)
    na, nb = _LOCUS_NAMES[name_idx]

    solver = REGISTRY.solver("math.locus_equidistant_two_points")
    sol = cast(Solution, solver(0, 0, vx, vy, na, nb))
    mid = (sympy.Rational(vx, 2), sympy.Rational(vy, 2))
    _assert_point(sol, "midpoint", mid)
    _assert_line(sol, "perpendicular_bisector", through=mid, perpendicular_to=(vx, vy))

    problem_svg, solution_svg = figures_two_points((0.0, 0.0), (float(vx), float(vy)), na, nb)
    return _mr(
        ctx,
        params={"ax": 0, "ay": 0, "bx": vx, "by": vy, "name_a": na, "name_b": nb},
        conditions=f"2点{na}、{nb}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[na, nb],
        elements=["given_point", "given_point"],
        recipe="math.construct_locus_equidistant_two_points",
    )


# ---------------------------------------------------------------------------
# g1_l44.construction Lv3 — 3点から等距離にある点（基本作図2つの交点）
# ---------------------------------------------------------------------------
_THREE_POINTS_CONCEPTS = ["construction.circumcenter_three_points"]

_TRIPLE_NAMES: tuple[tuple[str, str, str], ...] = (
    ("A", "B", "C"), ("K", "L", "M"), ("D", "E", "F"),
)


@lru_cache(maxsize=None)
def _combos_three_points(
    lo: int, hi: int, cross_min: int, pmax: int, n_names: int
) -> tuple[tuple[_IntVec, _IntVec, int], ...]:
    """(AB ベクトル, AC ベクトル, 記号 index)。3点は同一直線上になく、外心が枠に収まる。"""
    vecs = _vectors(lo, hi)
    out: list[tuple[_IntVec, _IntVec, int]] = []
    for b in vecs:
        nb2 = b[0] * b[0] + b[1] * b[1]
        for c in vecs:
            det = b[0] * c[1] - b[1] * c[0]
            if abs(det) < cross_min:
                continue
            nc2 = c[0] * c[0] + c[1] * c[1]
            den = 2 * det
            num_x = nb2 * c[1] - nc2 * b[1]
            num_y = b[0] * nc2 - c[0] * nb2
            if abs(num_x) > pmax * abs(den) or abs(num_y) > pmax * abs(den):
                continue
            for i in range(n_names):
                out.append((b, c, i))
    return tuple(out)


@register_recipe(
    "math.construct_equidistant_point_three", provides_concepts=_THREE_POINTS_CONCEPTS
)
def construct_equidistant_point_three(ctx: CellContext, rng: Rng) -> MR:
    """3点から等距離にある点Pを、垂直二等分線2本の交点として作図する（g1_l44 Lv3）。

    Lv2（基本作図1つ）に対し、2本目の垂直二等分線と交点をとる手が加わる（8手）。
    """
    p = ctx.spec_level.params
    combos = _combos_three_points(
        int(p["len_min"]), int(p["len_max"]), int(p["cross_min"]), int(p["point_max"]),
        len(_TRIPLE_NAMES),
    )
    b, c, name_idx = _pick(combos, rng)
    na, nb, nc = _TRIPLE_NAMES[name_idx]

    solver = REGISTRY.solver("math.circumcenter_of_three_points")
    sol = cast(Solution, solver(0, 0, b[0], b[1], c[0], c[1], na, nb, nc))
    _assert_line(
        sol, "perpendicular_bisector_first",
        through=(sympy.Rational(b[0], 2), sympy.Rational(b[1], 2)), perpendicular_to=b,
    )
    _assert_line(
        sol, "perpendicular_bisector_second",
        through=(sympy.Rational(b[0] + c[0], 2), sympy.Rational(b[1] + c[1], 2)),
        perpendicular_to=(c[0] - b[0], c[1] - b[1]),
    )
    center = _feat(sol, "point")
    # 求める点の条件そのもの: 3点からの距離がすべて等しい。
    da = center[0] ** 2 + center[1] ** 2
    db = (center[0] - b[0]) ** 2 + (center[1] - b[1]) ** 2
    dc = (center[0] - c[0]) ** 2 + (center[1] - c[1]) ** 2
    assert da == db == dc, "3点から等距離になっていない"

    problem_svg, solution_svg = figures_three_points(
        (0.0, 0.0), (float(b[0]), float(b[1])), (float(c[0]), float(c[1])),
        na, nb, nc, _fpt(*center), "P",
    )
    return _mr(
        ctx,
        params={
            "ax": 0, "ay": 0, "bx": b[0], "by": b[1], "cx": c[0], "cy": c[1],
            "name_a": na, "name_b": nb, "name_c": nc,
        },
        conditions=f"3点{na}、{nb}、{nc}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[na, nb, nc],
        elements=["given_point", "given_point", "given_point"],
        recipe="math.construct_equidistant_point_three",
    )


# ---------------------------------------------------------------------------
# g1_l44.construction Lv4 — 辺上にあり2辺から等距離の点（方針から構成・誘導なし）
# ---------------------------------------------------------------------------
_SIDE_EQUIDISTANT_CONCEPTS = ["construction.point_on_side_equidistant_two_sides"]


@lru_cache(maxsize=None)
def _combos_triangle_bisector(
    lo: int, hi: int, amin: int, amax: int
) -> tuple[tuple[_IntVec, _IntVec], ...]:
    """(AB ベクトル, AC ベクトル)。長さは整数かつ相異（P が辺の中点に潰れない）。"""
    vecs = _integer_length_vectors(lo, hi)
    out: list[tuple[_IntVec, _IntVec]] = []
    for u in vecs:
        lu = math.isqrt(u[0] ** 2 + u[1] ** 2)
        for v in vecs:
            lv = math.isqrt(v[0] ** 2 + v[1] ** 2)
            if lu == lv:
                continue
            if u[0] * v[1] - u[1] * v[0] == 0:
                continue
            if not (amin <= _angle_deg(u, v) <= amax):
                continue
            out.append((u, v))
    return tuple(out)


@register_recipe(
    "math.construct_point_on_side_equidistant", provides_concepts=_SIDE_EQUIDISTANT_CONCEPTS
)
def construct_point_on_side_equidistant(ctx: CellContext, rng: Rng) -> MR:
    """辺BC上にあり2辺AB、ACから等距離にある点Pを作図する（g1_l44.construction Lv4）。

    誘導が無いので、手順の先頭に「どの基本作図を使うか決める」手が立つ（方針の構成）。
    2辺の長さを相異にしてあるので、P は辺の中点には潰れない（退化の排除）。
    """
    p = ctx.spec_level.params
    combos = _combos_triangle_bisector(
        int(p["side_min"]), int(p["side_max"]), int(p["angle_min"]), int(p["angle_max"])
    )
    u, v = _pick(combos, rng)
    na, nb, nc = "A", "B", "C"

    solver = REGISTRY.solver("math.point_on_side_equidistant_from_two_sides")
    sol = cast(Solution, solver(0, 0, u[0], u[1], v[0], v[1], na, nb, nc))
    _assert_bisects(_assert_line(sol, "angle_bisector", through=(0, 0)), u, v)
    p_pt = _feat(sol, "point")
    # 求める点の条件そのもの: 頂点Aの角の二等分線上にあり、辺BC の内側にある。
    _assert_bisects((p_pt[0], p_pt[1]), u, v)
    assert (p_pt[0] - u[0]) * (v[1] - u[1]) - (p_pt[1] - u[1]) * (v[0] - u[0]) == 0
    assert (p_pt[0] - u[0]) * (v[0] - u[0]) + (p_pt[1] - u[1]) * (v[1] - u[1]) > 0
    assert (p_pt[0] - v[0]) * (u[0] - v[0]) + (p_pt[1] - v[1]) * (u[1] - v[1]) > 0

    problem_svg, solution_svg = figures_triangle_bisector(
        (0.0, 0.0), (float(u[0]), float(u[1])), (float(v[0]), float(v[1])),
        na, nb, nc, _fpt(*p_pt), "P",
    )
    return _mr(
        ctx,
        params={
            "ax": 0, "ay": 0, "ux": u[0], "uy": u[1], "vx": v[0], "vy": v[1],
            "name_a": na, "name_b": nb, "name_c": nc,
        },
        conditions=f"三角形{na}{nb}{nc}",
        answer=_answer(sol, solution_svg),
        steps=sol.steps,
        figure_svg=problem_svg,
        labels=[na, nb, nc],
        elements=["given_segment", "given_segment", "given_segment", "given_point"],
        recipe="math.construct_point_on_side_equidistant",
    )


__all__ = [
    "construct_perpendicular_bisector",
    "construct_equidistant_point_on_line",
    "construct_angle_bisector",
    "construct_equidistant_point_from_two_sides",
    "construct_perpendicular",
    "construct_foot_and_distance",
    "construct_locus_equidistant_two_points",
    "construct_equidistant_point_three",
    "construct_point_on_side_equidistant",
]
