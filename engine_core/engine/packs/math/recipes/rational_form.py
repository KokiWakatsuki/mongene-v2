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


def _repeating_period(q: int) -> int:
    """1/q の循環節の長さ（＝10 の法 q' における位数。q' は q から 2,5 を除いた数）。"""
    m = q
    while m % 2 == 0:
        m //= 2
    while m % 5 == 0:
        m //= 5
    if m == 1:
        return 0
    k, r = 1, 10 % m
    while r != 1:
        r = r * 10 % m
        k += 1
    return k


# 分母候補（Lv1）: 小数が必ず循環し、**循環節が6桁までに収まる** 2〜99 の整数。
# 循環節の長さを見ずに広くとっていたため「9/92 → 0.0̇97826086956521739130434̇」という、
# 手では書き出せない答えが出ていた（教科書は 1/3・1/7・5/6 のように短い周期を扱う）。
# 周期の上限を入れても分子との組は1000通り以上あるので、dup_rate は困らない。
_MAX_REPEATING_PERIOD = 6
_REPEATING_DENOMINATORS = [
    q
    for q in range(2, 100)
    if _has_non_terminating_factor(q) and _repeating_period(q) <= _MAX_REPEATING_PERIOD
]


# 循環小数→分数（Lv2）の答えの分母の上限。教科書が扱うのは 1/3・4/33・5/6・7/30 の
# ように分母99までで、`821/1980` のような分数は約分しても意味を持たない。
_MAX_ANSWER_DENOMINATOR = 99


def _decimal_to_fraction_denominator(non_repeating: str, repeating: str) -> int:
    """0.<非循環部><循環節> を既約分数にしたときの分母（整数演算だけで求める）。"""
    m, n = len(non_repeating), len(repeating)
    num = int(non_repeating + repeating) - int(non_repeating or "0")
    den = (10**n - 1) * 10**m
    return den // gcd(num, den) if num else 1


def _valid_repeating_pairs() -> list[tuple[str, str]]:
    """(非循環部, 循環節) のうち、**答えの分母が上限内**のものを全部並べる。

    以前は桁数 m・n を一様に引いてから桁を引き、上限を超えたら引き直していた。
    これだと (m,n)=(0,1) の9通りしかない組に全体の 1/9 の確率が集まり、
    dup_rate が 0.30 まで跳ねる。**組を先に全部作って、そこから一様に引く**と
    943通りに散る（実測 dup 0.30 → 0.05）。
    「答えの大きさで測る」（原則⓪）と「軸を増やす」（原則①）は両立する。
    """
    out: list[tuple[str, str]] = []
    for m in (0, 1, 2):
        for n in (1, 2, 3):
            for head in range(10**m):
                non_repeating = f"{head:0{m}d}" if m else ""
                for block in range(10**n):
                    repeating = f"{block:0{n}d}"
                    # 循環節の先頭は0でない・全桁が同じだと短い周期に退化する
                    # （"55" は実質周期1の 0.5̇ と同値。鉄則⑤: 構成時に排除）。
                    if repeating[0] == "0" or (n > 1 and len(set(repeating)) == 1):
                        continue
                    if (
                        _decimal_to_fraction_denominator(non_repeating, repeating)
                        <= _MAX_ANSWER_DENOMINATOR
                    ):
                        out.append((non_repeating, repeating))
    return out


_REPEATING_PAIRS = _valid_repeating_pairs()


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


def _construct_decimal_to_fraction(ctx: CellContext, rng: Rng, mode: str) -> MR:
    # 非循環部（0〜2桁）と循環節（1〜3桁）の組。**答えの分母が99以下の組だけ**を
    # あらかじめ並べておき、そこから一様に引く（`_valid_repeating_pairs` の説明を参照。
    # 桁の定義域は狭めていない＝原則⓪「答えの大きさで測る」）。
    index = int(draw({"int_range": [0, len(_REPEATING_PAIRS) - 1]}, rng))
    non_repeating, repeating = _REPEATING_PAIRS[index]

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
