"""動点（正方形の辺上を動く点）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は正方形の1辺 s・速さ v・経過時間 t を answer-first で構成し、独立ソルバ
math.solve_moving_point_area（`engine/packs/math/solvers/motion.py`）で三角形 APD の
面積を再計算する（double-solve）。visual は不要（座標幾何の数式のみで完結）。

C3（g3_l31.find_value・2次方程式の利用「動点」）クラスタ。乱数は
`engine.core.rng.draw` 以外で解釈しない。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, CellContext, Provenance, Solution, SubQuestionMR, SymbolicAnswer
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

_MOTION_CONCEPTS = [
    "motion.area_single_segment",
    "motion.area_two_segment",
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


@register_recipe("math.solve_moving_point_area", provides_concepts=_MOTION_CONCEPTS)
def solve_moving_point_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正方形の辺上を動く点 P による三角形 APD の面積を求める MR を組む（C3 g3_l31.find_value）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "single_segment":
        s, v, t, condition = _construct_single_segment(rng)
    elif mode == "two_segment":
        s, v, t, condition = _construct_two_segment(rng)
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.solve_moving_point_area")
    sol = cast(Solution, solver(s, v, t, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 独立に構成した s,v,t から shoelace 公式で再計算した面積と一致する（.equals で
    # 堅牢にゼロ判定）。
    expected = _expected_area(s, v, t, mode)
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: s={s},v={v},t={t},mode={mode} の面積 {expected} != {sol.answer.srepr}"
    )
    assert not sympy.sympify(sol.answer.srepr).free_symbols

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"s": s, "v": v, "t": t, "mode": mode},
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_moving_point_area"),
    )


def _expected_area(s: int, v: int, t: int, mode: str) -> sympy.Rational:
    """独立検証用: shoelace 公式を素直に展開した式で面積を再計算する。"""
    s_v, d = sympy.Integer(s), sympy.Integer(v) * sympy.Integer(t)
    if mode == "single_segment":
        px, py = d, sympy.Integer(0)
    else:
        px, py = s_v, d - s_v
    ax, ay, dx, dy = sympy.Integer(0), sympy.Integer(0), sympy.Integer(0), s_v
    return sympy.Rational(1, 2) * sympy.Abs(ax * (py - dy) + px * (dy - ay) + dx * (ay - py))


def _construct_single_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv2: 点 P が辺 AB 上（1区間）にあるときの構成。

    速さ v・経過時間 t を先に決め AP の長さ p=v·t を求め、1辺 s は p より大きい偶数
    （面積 p·s/2 を整数にするため・鉄則⑤: 構成時に整数解を保証）に絞って引く。
    """
    v = int(draw({"int_range": [1, 5]}, rng))
    t = int(draw({"int_range": [2, 10]}, rng))
    p = v * t
    s_cands = [x for x in range(p + 2, p + 42) if x % 2 == 0]
    s = int(draw({"int_set": s_cands}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDで、点PはAを出発し辺AB上を毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


def _construct_two_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv3: 点 P が A→B→C の2区間目（辺 BC 上）にあるときの構成。

    1辺 s は偶数（面積 s²/2 を整数にするため）に限定し、速さ v から経過距離
    d=v·t が s<d<2s（確実に2区間目）となる t の範囲を計算し、その範囲から引く
    （鉄則⑤: 実行時の場合分け判定ではなく構成時に区間を保証）。
    """
    s = int(draw({"int_set": list(range(6, 41, 2))}, rng))
    v = int(draw({"int_range": [1, 4]}, rng))
    t_lo = s // v + 1
    t_hi = (2 * s - 1) // v
    t = int(draw({"int_range": [t_lo, t_hi]}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDの辺上を、点PがA→B→Cの順に毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


__all__ = ["solve_moving_point_area_recipe"]
