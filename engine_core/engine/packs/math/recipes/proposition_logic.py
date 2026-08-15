"""命題の逆と反例のセルの recipe（Phase E 端物・g2_l38.knowledge Lv2）。

小問は2つ（どちらも asked=choice）:
  (1) この命題の逆として正しいものを選べ
  (2) その逆が正しくないことを示す反例を選べ
「逆を述べよ」「反例を挙げよ」という記述は engine が採点できないので、
**候補から選ばせる**形に畳む（判別も提示も、選ぶという同じ操作でできる）。

命題は数値をパラメータに持つ3つの型から引く。**カタログに数個並べるだけでは
dup が通らない**ので、数値と変数名を動かして変種を作る。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.proposition_logic import _KINDS, _parts, _statement

_PROPOSITION_CONCEPTS = ["proof_logic_terms.converse_and_counterexample"]


@register_recipe("math.proposition_converse", provides_concepts=_PROPOSITION_CONCEPTS)
def proposition_converse_recipe(ctx: CellContext, rng: Rng) -> MR:
    """命題の逆を選び、その逆の反例を選ぶ（g2_l38.knowledge Lv2・answer-first）。

    どの型も「もとの命題は正しく、逆は正しくない」ようにパラメータを縛る
    （そうでないと (2) の反例が存在しない）。
      multiple: a = b·k（bの倍数がaの倍数とは限らない）
      greater : a > b（x>b でも x>a とは限らない）
      positive: 和が正でも両方が正とは限らない
    """
    p = ctx.spec_level.params
    kind = str(_KINDS[int(draw({"int_range": [0, len(_KINDS) - 1]}, rng))])
    variables = [str(v) for v in p["variable_candidates"]]
    var = variables[int(draw({"int_range": [0, len(variables) - 1]}, rng))]

    if kind == "multiple":
        b = int(draw(p["base_domain"], rng))
        k = int(draw(p["factor_domain"], rng))
        a, b_val = b * k, b
    elif kind == "greater":
        b_val = int(draw(p["value_domain"], rng))
        a = b_val + int(draw(p["gap_domain"], rng))
    else:
        a = int(draw(p["value_domain"], rng))
        b_val = int(draw(p["gap_domain"], rng))

    converse = cast(Solution, REGISTRY.solver("math.proposition_converse_choice")(kind, var, a, b_val))
    counter = cast(
        Solution, REGISTRY.solver("math.proposition_counterexample_choice")(kind, var, a, b_val)
    )

    hypothesis, conclusion = _parts(kind, var, a, b_val)
    statement = (
        f"「{_statement(hypothesis, conclusion)}」という命題について、次の問いに答えよ。"
        "(1) この命題の逆として正しいものを選べ。"
        "(2) (1)で選んだ逆が正しくないことを示す反例として適切なものを選べ"
    )

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"kind": kind, "var": var, "a": a, "b": b_val},
        given={"statement": statement},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="choice", answer=converse.answer, steps=converse.steps,
                concept_tags=concept_tags, cause_tags=cause_tags,
            ),
            SubQuestionMR(
                label="(2)", asked="choice", answer=counter.answer, steps=counter.steps,
                concept_tags=concept_tags, cause_tags=cause_tags,
            ),
        ],
        visual_plan=None,
        provenance=Provenance(recipe="math.proposition_converse"),
    )
