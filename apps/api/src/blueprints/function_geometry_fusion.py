"""FunctionGeometryFusionStructure（§17.4 #5）

グラフ上の図形・交点・面積。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.intersect_verb import IntersectVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_function_geometry_fusion_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="FunctionGeometryFusionStructure",
        blueprint_version="v1",
        noun_slots={
            "func_a": NounSlot(
                slot_name="func_a",
                accepted_tags=["linear_function"],
                required=True,
            ),
            "func_b": NounSlot(
                slot_name="func_b",
                accepted_tags=["linear_function"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=IntersectVerb(),
                input_slots=["func_a", "func_b"],
                output_slot="intersection",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Graph_Renderer",
            compatible_noun_types=["LinearFuncAtom", "QuadraticFuncAtom"],
            required=True,
        ),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 50)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=["2 つの関数の交点座標"],
            final_question="交点と座標軸で囲まれる三角形の面積",
        ),
    )
