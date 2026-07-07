"""DataProbabilityStructure（§17.4 #10）

樹形図・確率・ヒストグラム・箱ひげ図・標本調査。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.calculate_probability_verb import CalculateProbabilityVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_data_probability_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="DataProbabilityStructure",
        blueprint_version="v1",
        noun_slots={
            "event": NounSlot(
                slot_name="event",
                accepted_tags=["probability"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=CalculateProbabilityVerb(),
                input_slots=["event"],
                output_slot="probability",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Tree_Renderer",
            compatible_noun_types=["EventAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 40)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="確率を求めなさい",
        ),
    )
