"""ProofStructure（§17.4 #9, §26）

図形合同・相似・代数的証明・反例。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.prove_geometry_verb import ProveGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_proof_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="ProofStructure",
        blueprint_version="v1",
        noun_slots={
            "figure_a": NounSlot(
                slot_name="figure_a",
                accepted_tags=[],
                accepted_noun_types=["PolygonAtom"],
                required=True,
                constraints_override={"polygon_type": "triangle"},
            ),
            "figure_b": NounSlot(
                slot_name="figure_b",
                accepted_tags=[],
                accepted_noun_types=["PolygonAtom"],
                required=True,
                constraints_override={"polygon_type": "triangle"},
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=ProveGeometryVerb(proof_type="congruence", condition_set="SAS"),
                input_slots=["figure_a", "figure_b"],
                output_slot="proof",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom"],
            required=True,
        ),
        supported_forms=["proof"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 55)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="証明しなさい",
        ),
    )
