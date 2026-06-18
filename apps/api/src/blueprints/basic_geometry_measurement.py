"""BasicGeometryMeasurementStructure（§17.4 #3）

平面・空間図形の面積・体積・表面積を計算する。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_basic_geometry_measurement_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="BasicGeometryMeasurementStructure",
        blueprint_version="v1",
        noun_slots={
            "shape": NounSlot(
                slot_name="shape",
                accepted_tags=["geometry"],  # plane_geometry/space_geometry 両方を含む共通タグ
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="area"),
                input_slots=["shape"],
                output_slot="measure",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom", "CircleAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 25)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="図形の面積（または体積・表面積）を求めなさい",
        ),
    )
