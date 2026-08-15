"""平面図形まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C7（g1 平面図形）クラスタのうち g1_l38〜l46 の非 visual セル群（plane_geometry.py の
solver 群）に対応する recipe を集約する。乱数は `engine.core.rng.draw` 以外で解釈しない。
用語想起（g1_l37/l43/l44/l45 Lv1）は既存 `math.term_recall` ハブ（letter_expr.py）に
domain を追加して対応するため、ここには含まれない。
"""
from __future__ import annotations

from functools import lru_cache
from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.solvers.plane_geometry import _fmt_pi_display


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g1_l38/l39/l40.knowledge Lv1: 平行移動・回転移動・対称移動の不変性の判別
# ---------------------------------------------------------------------------
_TRANSFORMATION_INVARIANT_CONCEPTS = [
    "transformation_invariant.parallel_translation",
    "transformation_invariant.rotation",
    "transformation_invariant.reflection",
]


@register_recipe("math.judge_transformation_invariant", provides_concepts=_TRANSFORMATION_INVARIANT_CONCEPTS)
def judge_transformation_invariant_recipe(ctx: CellContext, rng: Rng) -> MR:
    """平行移動/回転移動/対称移動の性質(不変量)を判別する（g1_l38/l39/l40.knowledge Lv1）。"""
    p = ctx.spec_level.params
    topic = str(p["topic"])
    surface: dict[str, object]
    if topic == "parallel_translation":
        m = int(draw(p["distance_domain"], rng))
        n = int(draw(p["distance_domain"], rng))
        # 目盛りを1〜10 に狭めた分の広さは**向き**で戻す（実物も4方向を使う）。
        h = str(draw(["右", "左"], rng))
        v = str(draw(["上", "下"], rng))
        statement = (
            f"図形を、{h}へ{m}目盛り、{v}へ{n}目盛りだけ平行移動した。移動前後で、"
            "対応する辺の長さと図形の大きさの関係を答えよ"
        )
        surface = {"m": m, "n": n, "h": h, "v": v}
    elif topic == "rotation":
        (o,) = _draw_named_figures([1], rng)
        deg = int(draw(p["angle_domain"], rng))
        statement = (
            f"図形を、点{o}を中心として{deg}°回転移動した。移動前後で、対応する点と、"
            f"回転の中心{o}からの距離の関係を答えよ"
        )
        surface = {"center": o, "deg": deg}
    else:  # reflection
        line = str(draw(cast("list[str]", p["line_domain"]), rng))
        (v,) = _draw_named_figures([2], rng)
        pa, pb = v
        statement = (
            f"図形を、直線{line}を対称の軸として対称移動した。移動前後で、対応する2点"
            f"{pa}、{pb}を結ぶ線分と、対称の軸{line}との関係を答えよ"
        )
        surface = {"line": line, "a": pa, "b": pb}

    solver = REGISTRY.solver("math.judge_transformation_invariant")
    sol = cast(Solution, solver(topic))

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"topic": topic, **surface},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_transformation_invariant"),
    )


# ---------------------------------------------------------------------------
# g1_l41/l42.knowledge Lv1: 垂直二等分線/角の二等分線上の点の等距離性の判別
# ---------------------------------------------------------------------------
_CONSTRUCTION_PROPERTY_CONCEPTS = [
    "construction_property.perpendicular_bisector",
    "construction_property.angle_bisector",
]


@register_recipe("math.judge_construction_property", provides_concepts=_CONSTRUCTION_PROPERTY_CONCEPTS)
def judge_construction_property_recipe(ctx: CellContext, rng: Rng) -> MR:
    """垂直二等分線/角の二等分線上の点が2端(2辺)から等距離という性質を判別する

    （g1_l41/l42.knowledge Lv1）。
    """
    p = ctx.spec_level.params
    topic = str(p["topic"])
    if topic == "perpendicular_bisector":
        seg, extra = _draw_named_figures([2, 1], rng)
        a, b = seg
        pt = extra
        # 点名をアルファベット順に直したぶん、言い回しを軸に足す（実物も
        # 「〜上に点Pをとる」「〜をひき、その上の点をPとする」の両方を使う）。
        phrasing = int(draw({"int_set": [0, 1]}, rng))
        if phrasing:
            statement = (
                f"線分{a}{b}の垂直二等分線をひき、その線上の点を{pt}とする。このとき、"
                f"{pt}{a}と{pt}{b}の長さの関係を、その理由となる性質の名前とともに答えよ"
            )
        else:
            statement = (
                f"線分{a}{b}の垂直二等分線上に点{pt}をとる。このとき、{pt}{a}と{pt}{b}の"
                "長さの関係を、その理由となる性質の名前とともに答えよ"
            )
        # 言い回しは場面の違いなので params に記録する（dup_key は params だけを見る）。
        surface = {"a": a, "b": b, "pt": pt, "phrasing": str(phrasing)}
    else:  # angle_bisector
        tri, extra = _draw_named_figures([3, 1], rng)
        o, a, b = tri
        pt = extra
        phrasing = int(draw({"int_set": [0, 1]}, rng))
        if phrasing:
            statement = (
                f"∠{a}{o}{b}の二等分線をひき、その線上の点を{pt}とする。{pt}から2辺"
                f"{o}{a}、{o}{b}に垂線を引くとき、{pt}から2辺までの距離の関係を答えよ"
            )
        else:
            statement = (
                f"∠{a}{o}{b}の二等分線上に点{pt}をとり、{pt}から2辺{o}{a}、{o}{b}に垂線を"
                f"引く。このとき、{pt}から2辺までの距離の関係を答えよ"
            )
        surface = {"o": o, "a": a, "b": b, "pt": pt, "phrasing": str(phrasing)}

    solver = REGISTRY.solver("math.judge_construction_property")
    sol = cast(Solution, solver(topic))

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"topic": topic, **surface},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_construction_property"),
    )


# ---------------------------------------------------------------------------
# g1_l37.knowledge Lv2: 「点と直線との距離」の意味の判別
# ---------------------------------------------------------------------------
_POINT_LINE_DISTANCE_MEANING_CONCEPTS = ["point_line_distance.meaning"]


@register_recipe(
    "math.judge_point_line_distance_meaning", provides_concepts=_POINT_LINE_DISTANCE_MEANING_CONCEPTS
)
def judge_point_line_distance_meaning_recipe(ctx: CellContext, rng: Rng) -> MR:
    """「点と直線との距離」がどの線分の長さを指すかを判別する（g1_l37.knowledge Lv2）。"""
    # 実物は「点Pと直線ABとの距離」——直線は連続した2文字、点は別の1文字。
    line, extra = _draw_named_figures([2, 1], rng)
    a, b = line
    pt = extra
    statement = (
        f"点{pt}と直線{a}{b}がある。「点{pt}と直線{a}{b}との距離」とは、どの線分の"
        "長さのことか、図に即して答えよ"
    )

    solver = REGISTRY.solver("math.judge_point_line_distance_meaning")
    sol = cast(Solution, solver("_"))

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"pt": pt, "a": a, "b": b},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_point_line_distance_meaning"),
    )


# ---------------------------------------------------------------------------
# g1_l45.knowledge Lv2: 弧と中心角の比例/接線と半径の垂直性の判別
# ---------------------------------------------------------------------------
_CIRCLE_PROPERTY_CONCEPTS = ["circle_property.judge"]


@register_recipe("math.judge_circle_property", provides_concepts=_CIRCLE_PROPERTY_CONCEPTS)
def judge_circle_property_recipe(ctx: CellContext, rng: Rng) -> MR:
    """弧と中心角の比例/接線と半径の垂直性を判別する（g1_l45.knowledge Lv2）。"""
    p = ctx.spec_level.params
    concept = str(draw(cast("list[str]", p["concept_set"]), rng))
    if concept == "arc_central_angle_proportional":
        (o,) = _draw_named_figures([1], rng)
        r = int(draw(p["number_domain"], rng))
        # **問いの形と答えの形をそろえる**（EVALUATION R-8）。答えは「正しい／誤り」の
        # 判別（`math.judge_circle_property`）なのに、問題文が「どうなるか、答えよ」と
        # 値を尋ねていた——生徒は「2倍になる」と書き、正解の「正しい」と一致しない。
        statement = (
            f"中心{o}、半径{r}cmの円で、「中心角の大きさを2倍にすると、それに対する"
            "弧の長さも2倍になる」といえるか、答えよ"
        )
        surface = {"center": o, "r": r}
    else:  # tangent_perpendicular
        # 円の中心と接点は続きの文字である必要がない（実物は「中心Oの円に点Aで
        # 接する接線」）。離れていてよい2つとして引くと組合せが広がる。
        one, other = _draw_named_figures([1, 1], rng)
        o, t = one, other
        statement = (
            f"中心{o}の円に、点{t}で接する接線がある。この接線と、点{t}を通る半径"
            f"{o}{t}がつくる角の大きさの性質を答えよ"
        )
        surface = {"center": o, "tangent_point": t}

    solver = REGISTRY.solver("math.judge_circle_property")
    sol = cast(Solution, solver(concept))

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"concept": concept, **surface},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_circle_property"),
    )


# ---------------------------------------------------------------------------
# g1_l46.find_value Lv1: 半径・中心角からおうぎ形の弧の長さ/面積を求める
# ---------------------------------------------------------------------------
_SECTOR_ARC_LENGTH_OR_AREA_CONCEPTS = ["sector.arc_length_or_area"]


@register_recipe("math.sector_arc_length_or_area", provides_concepts=_SECTOR_ARC_LENGTH_OR_AREA_CONCEPTS)
def sector_arc_length_or_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """半径・中心角からおうぎ形の弧の長さ/面積を求める（g1_l46.find_value Lv1・answer-first）。"""
    p = ctx.spec_level.params
    # **答えの π の前の数の分母を小さく保つ。** 半径と中心角を無関係に引いていたので
    # 「半径13cm・中心角150° → 845π/12」のような、教材では出さない答えが出ていた。
    # 弧の長さは 2rθ/360、面積は r²θ/360。どちらも分母 ≤ 4 に収まる組だけを採る
    # （Lv2 が「分母 ≤ 12」で同じ手を使っているのと同型）。
    den_max = int(p.get("coefficient_denominator_max", 4))
    for _ in range(400):
        r = int(draw(p["radius_domain"], rng))
        angle = int(draw(cast("list[int]", p["angle_domain"]), rng))
        target = str(draw(cast("list[str]", p["target_set"]), rng))
        coeff = (
            sympy.Rational(2 * r * angle, 360) if target == "arc_length"
            else sympy.Rational(r * r * angle, 360)
        )
        if coeff.q <= den_max:
            break
    else:
        raise ValueError("sector_arc_length_or_area_recipe: 係数の分母が小さい組を構成できず")

    solver = REGISTRY.solver("math.sector_arc_length_or_area")
    sol = cast(Solution, solver(str(r), str(angle), target))
    assert isinstance(sol.answer, SymbolicAnswer)

    asked_label = "弧の長さ" if target == "arc_length" else "面積"
    statement = (
        f"半径{r}cm、中心角{angle}°のおうぎ形がある。このおうぎ形の{asked_label}を"
        "求めよ。ただし円周率はπとする"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"radius": r, "angle": angle, "target": target},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.sector_arc_length_or_area"),
    )


# ---------------------------------------------------------------------------
# g1_l46.find_value Lv2: 面積から中心角の大きさを逆算する
# ---------------------------------------------------------------------------
_SECTOR_SOLVE_CENTRAL_ANGLE_CONCEPTS = ["sector.solve_central_angle"]


@register_recipe("math.sector_solve_central_angle", provides_concepts=_SECTOR_SOLVE_CENTRAL_ANGLE_CONCEPTS)
def sector_solve_central_angle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """おうぎ形の面積から中心角の大きさを逆算する（g1_l46.find_value Lv2・answer-first）。

    半径 r と中心角 angle を先に引き、面積の係数 k=r²·angle/360 の分母が小さい(≤12・
    あまり煩雑でない)組合せだけを採用する（有界リトライ・compare_signed_numbers と同型。
    分母=1固定にすると採用される半径がごく一部に偏り dup_rate が悪化するため、分母の
    上限をゆるめて採用の幅を広くとる）。
    """
    p = ctx.spec_level.params
    for _ in range(200):
        r = int(draw(p["radius_domain"], rng))
        angle = int(draw(cast("list[int]", p["angle_domain"]), rng))
        k = sympy.Rational(r * r * angle, 360)
        # **与える面積の係数は分母 2 まで。** 上限12だと「面積が 44π/3 cm²」
        # 「32π/5 cm²」という、実物の教材が与件として書かない形になっていた。
        if k.q <= 2:
            break
    else:
        raise ValueError("sector_solve_central_angle: 分母が小さい面積を構成できず")

    solver = REGISTRY.solver("math.sector_solve_central_angle")
    sol = cast(Solution, solver(str(r), str(k)))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Integer(angle)), "double-solve 不一致: 中心角"

    area_disp = _fmt_pi_display(k * sympy.pi)
    statement = (
        f"半径{r}cmのおうぎ形の面積が{area_disp}cm²である。このおうぎ形の中心角の"
        "大きさを求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"radius": r, "angle": angle, "area_coeff": str(k)},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.sector_solve_central_angle"),
    )


# ---------------------------------------------------------------------------
# g2_l50.find_value Lv3: 四角形の面積を2等分する直線と辺BCの交点
#
# 「作図的な逆算」を採点可能にするために、四角形を**座標で与える**。座標があれば
# 面積も点の位置も一意に決まり、「面積の関係から点の位置を求める」という台帳の
# 要求（desc: 面積を2等分する直線を引くなど逆算・作図的に求める）をそのまま満たせる。
# ---------------------------------------------------------------------------
_AREA_BISECT_CONCEPTS = ["equal_area.bisecting_line_point"]


def _convex_in_order(pts: list[tuple[int, int]]) -> bool:
    """4点がその順に凸四角形をなすか（外積の符号がすべて同じ）。"""
    def cross(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    signs = [cross(pts[i], pts[(i + 1) % 4], pts[(i + 2) % 4]) for i in range(4)]
    return all(s > 0 for s in signs) or all(s < 0 for s in signs)


@lru_cache(maxsize=8)
def _area_bisect_candidates(
    c_hi: int, ax_hi: int, ay_hi: int, dx_hi: int, dy_hi: int
) -> tuple[tuple[int, int, int, int, int], ...]:
    """(c, ax, ay, dx, dy) の候補。B=(0,0)・C=(c,0) に固定して数え上げる。

    P の x 座標は（全体の面積）÷（Aの y 座標）になるので、それが**整数**で
    かつ 0 < Px < c（辺BC の内側）になる組だけを残す。凸四角形であることも要る
    （へこんでいると「頂点Aを通る直線が辺BCと交わる」が成り立たない場合がある）。
    """
    out: list[tuple[int, int, int, int, int]] = []
    for c in range(4, c_hi + 1):
        for ax in range(0, ax_hi + 1):
            for ay in range(2, ay_hi + 1):
                for dx in range(ax + 1, dx_hi + 1):
                    for dy in range(2, dy_hi + 1):
                        quad = [(ax, ay), (0, 0), (c, 0), (dx, dy)]
                        if not _convex_in_order(quad):
                            continue
                        twice = abs(ax * (0 - dy) + c * dy + dx * ay)
                        if twice % (2 * ay):
                            continue
                        px = twice // (2 * ay)
                        if 0 < px < c:
                            out.append((c, ax, ay, dx, dy))
    return tuple(out)


@register_recipe("math.area_bisecting_point", provides_concepts=_AREA_BISECT_CONCEPTS)
def area_bisecting_point_recipe(ctx: CellContext, rng: Rng) -> MR:
    """面積を2等分する直線と辺BCの交点を求める（g2_l50.find_value Lv3・answer-first）。"""
    p = ctx.spec_level.params
    cands = _area_bisect_candidates(
        int(p["c_max"]), int(p["ax_max"]), int(p["ay_max"]), int(p["dx_max"]), int(p["dy_max"])
    )
    c, ax, ay, dx, dy = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]

    sol = cast(
        Solution,
        REGISTRY.solver("math.area_bisecting_point_on_side")(ax, ay, 0, 0, c, 0, dx, dy),
    )
    statement = (
        f"座標平面上に四角形ABCDがあり、A({ax}, {ay})、B(0, 0)、C({c}, 0)、D({dx}, {dy})である。"
        "頂点Aを通り、この四角形の面積を2等分する直線を1本引く。"
        "その直線が辺BCと交わる点をPとするとき、点Pの座標を面積の関係から求めよ"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ax": ax, "ay": ay, "bx": 0, "by": 0, "cx": c, "cy": 0, "dx": dx, "dy": dy},
        given={"condition": statement},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="coordinate", answer=sol.answer, steps=sol.steps,
                concept_tags=list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=None,
        provenance=Provenance(recipe="math.area_bisecting_point"),
    )
