"""ConstructionStructure（§17.4 #8）

条件を満たす点 P の作図・軌跡。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.construct_geometry_verb import ConstructGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_construction_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="ConstructionStructure",
        blueprint_version="v1",
        noun_slots={
            "point_a": NounSlot(
                slot_name="point_a",
                accepted_tags=["coordinate"],
                required=True,
            ),
            "point_b": NounSlot(
                slot_name="point_b",
                accepted_tags=["coordinate"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=ConstructGeometryVerb(construction_type="perp_bisector"),
                input_slots=["point_a", "point_b"],
                output_slot="construction",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PointAtom", "PolygonAtom", "CircleAtom"],
            required=True,
        ),
        supported_forms=["word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 50)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="条件を満たす点 P の作図手順を示しなさい",
        ),
    )
