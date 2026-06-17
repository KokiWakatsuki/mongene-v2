"""AngleCalculationStructure（§17.4 #7）

平行線・多角形・円周角・円内接四角形・接弦角。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.find_angle_verb import FindAngleVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_angle_calculation_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="AngleCalculationStructure",
        blueprint_version="v1",
        noun_slots={
            "angle_source": NounSlot(
                slot_name="angle_source",
                accepted_tags=[],
                accepted_noun_types=["LineAngleAtom", "CircleAngleAtom", "PolygonAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=FindAngleVerb(theorem="parallel_alternate"),
                input_slots=["angle_source"],
                output_slot="target_angle",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["LineAngleAtom", "CircleAngleAtom", "PolygonAtom"],
            required=True,
        ),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 45)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="角の大きさを求めなさい",
        ),
    )
