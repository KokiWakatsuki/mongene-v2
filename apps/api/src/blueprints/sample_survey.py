"""SampleSurveyStructure Blueprint

SampleAtom + EstimatePopulationVerb を組み合わせた標本調査問題。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.estimate_population_verb import EstimatePopulationVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_sample_survey_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="SampleSurveyStructure",
        blueprint_version="v1",
        noun_slots={
            "sample": NounSlot(
                slot_name="sample",
                accepted_tags=["sampling_survey"],
                accepted_noun_types=["SampleAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=EstimatePopulationVerb(estimation_type="total_count"),
                input_slots=["sample"],
                output_slot="estimate",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["SampleAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 30)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="標本から母集団の総数を推定しなさい",
        ),
    )
