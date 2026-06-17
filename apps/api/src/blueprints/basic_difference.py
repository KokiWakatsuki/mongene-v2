"""BasicDifferenceStructure（§17.4 #4, §18.4 完全実装）

くり抜き・回転体・切断・展開図。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.cutout_verb import CutoutVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_basic_difference_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="BasicDifferenceStructure",
        blueprint_version="v1",
        noun_slots={
            "base_solid": NounSlot(
                slot_name="base_solid",
                accepted_tags=["space_geometry"],
                accepted_noun_types=["PrismAtom"],
                required=True,
                constraints_override={"is_cube": False, "max_height": 10},
            ),
            "cutout_solid": NounSlot(
                slot_name="cutout_solid",
                accepted_tags=["space_geometry"],
                accepted_noun_types=["PyramidAtom"],
                required=True,
                constraints_override={"max_base_side": 3, "max_height": 3},
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="volume"),
                input_slots=["base_solid"],
                output_slot="base_volume",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="volume"),
                input_slots=["cutout_solid"],
                output_slot="cutout_volume",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=CutoutVerb(),
                input_slots=["base_solid", "cutout_solid"],
                output_slot="remaining_volume",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="3D_Renderer",
            compatible_noun_types=["PrismAtom", "PyramidAtom"],
            required=True,
        ),
        supported_forms=["word_problem", "calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 60)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=["元の立体の体積", "くり抜く部分の体積"],
            final_question="くり抜き後の残った立体の体積を求めなさい",
        ),
    )
