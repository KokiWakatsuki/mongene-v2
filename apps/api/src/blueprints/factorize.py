"""FactorizeStructure Blueprint

2 本の PolynomialAtom の積を展開した式を問題文に、
因数分解形を答えとして生成する Blueprint。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.factorize_verb import FactorizeVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_factorize_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="FactorizeStructure",
        blueprint_version="v1",
        noun_slots={
            "left": NounSlot(
                slot_name="left",
                accepted_tags=["polynomial"],
                accepted_noun_types=["PolynomialAtom"],
                required=True,
            ),
            "right": NounSlot(
                slot_name="right",
                accepted_tags=["polynomial"],
                accepted_noun_types=["PolynomialAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=FactorizeVerb(),
                input_slots=["left", "right"],
                output_slot="factored",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["PolynomialAtom"],
            required=False,
        ),
        supported_forms=["calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 20)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="次の式を因数分解しなさい",
        ),
    )
