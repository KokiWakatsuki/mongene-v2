"""分数⇔循環小数の相互変換 recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は問題パラメータ（Lv1: 分母 q・分子 p／Lv2: 非循環部・循環節の桁）を answer-first
で構成し、独立ソルバ（`math.fraction_to_repeating_decimal`／`math.repeating_decimal_to_fraction`、
`engine/packs/math/solvers/rational_form.py`）で答えを再計算する（double-solve）。

C3（g3_l16.calculation・有理数の形）クラスタ。乱数は `engine.core.rng.draw` 以外で解釈しない。
"""
from __future__ import annotations

from math import gcd
from typing import cast

from engine.core.contracts import MR, CellContext, Provenance, Solution, SubQuestionMR, SymbolicAnswer
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.rational_form import fmt_repeating_decimal

_RATIONAL_FORM_CONCEPTS = [
    "rational_form.fraction_to_decimal",
    "rational_form.decimal_to_fraction",
]

def _has_non_terminating_factor(q: int) -> bool:
    """q から 2,5 を割り切れるだけ除いた後に 1 より大きく残るか（＝小数が必ず循環する）。"""
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    return q > 1


# 分母候補（Lv1）: 2,5 以外の素因数を持つ（＝小数が必ず循環する）2〜99 の整数。
# dup（自由度）を広く取るため範囲を大きめにする（鉄則②）。
_REPEATING_DENOMINATORS = [q for q in range(2, 100) if _has_non_terminating_factor(q)]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


@register_recipe("math.convert_rational_decimal_form", provides_concepts=_RATIONAL_FORM_CONCEPTS)
def convert_rational_decimal_form(ctx: CellContext, rng: Rng) -> MR:
    """分数⇔循環小数の相互変換 MR を組む（answer-first・calculation Lv1/Lv2）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "fraction_to_repeating_decimal":
        return _construct_fraction_to_decimal(ctx, rng, mode)
    if mode == "repeating_decimal_to_fraction":
        return _construct_decimal_to_fraction(ctx, rng, mode)
    raise ValueError(f"未知の mode: {mode!r}")


def _construct_fraction_to_decimal(ctx: CellContext, rng: Rng, mode: str) -> MR:
    q = int(draw({"int_set": _REPEATING_DENOMINATORS}, rng))
    # 0<p<q・p,q が既約（gcd=1）となる p のみを候補にする（構成時に排除・鉄則⑤）。
    p_cands = [v for v in range(1, q) if gcd(v, q) == 1]
    p = int(draw({"int_set": p_cands}, rng))

    solver = REGISTRY.solver("math.fraction_to_repeating_decimal")
    sol = cast(Solution, solver(p, q))
    assert isinstance(sol.answer, SymbolicAnswer)

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
        params={"mode": mode, "p": p, "q": q},
        given={"expression": f"{p}/{q}"},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.convert_rational_decimal_form"),
    )


def _draw_repeating_block(rng: Rng, n: int) -> str:
    """循環節の桁（長さ n）を構成する。全桁が同じ数字だと n 未満の周期に退化する
    （例 n=2 の"55"は実質周期1の0.5̇と同値）ため、最後の桁だけ「それまでの桁が
    全部同じ数字」のときに限りその数字を除外して引く（鉄則⑤: 構成時に排除）。
    """
    first = int(draw({"int_range": [1, 9]}, rng))
    digits = [first]
    for i in range(1, n):
        if i == n - 1 and all(d == first for d in digits):
            cands = [v for v in range(0, 10) if v != first]
        else:
            cands = list(range(0, 10))
        digits.append(int(draw({"int_set": cands}, rng)))
    return "".join(str(d) for d in digits)


def _construct_decimal_to_fraction(ctx: CellContext, rng: Rng, mode: str) -> MR:
    # 非循環部の桁数 m（0〜2桁）と循環節の桁数 n（1〜3桁）。dup（自由度）を広く取るため
    # 範囲を広めにする（鉄則②）。
    m = int(draw({"int_set": [0, 1, 2]}, rng))
    n = int(draw({"int_set": [1, 2, 3]}, rng))
    non_repeating = "".join(str(int(draw({"int_range": [0, 9]}, rng))) for _ in range(m))
    repeating = _draw_repeating_block(rng, n)

    solver = REGISTRY.solver("math.repeating_decimal_to_fraction")
    sol = cast(Solution, solver(non_repeating, repeating))
    assert isinstance(sol.answer, SymbolicAnswer)

    given_disp = fmt_repeating_decimal(non_repeating, repeating)
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
        params={"mode": mode, "non_repeating": non_repeating, "repeating": repeating},
        given={"expression": given_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.convert_rational_decimal_form"),
    )


__all__ = ["convert_rational_decimal_form"]
