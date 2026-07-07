"""AngleProofStructure（§17.4, §26）

平行線と交線がつくる角（錯角・同位角・同側内角）の性質の証明専用 Blueprint。
LineAngleAtom 1 つに対して ProveAngleRelationVerb を適用する。中2 g2_l31 の proof form。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.prove_angle_relation_verb import ProveAngleRelationVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_angle_proof_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="AngleProofStructure",
        blueprint_version="v1",
        noun_slots={
            "angle": NounSlot(
                slot_name="angle",
                accepted_tags=["parallel_lines"],
                accepted_noun_types=["LineAngleAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=ProveAngleRelationVerb(),
                input_slots=["angle"],
                output_slot="proof",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["LineAngleAtom"],
            required=False,
        ),
        supported_forms=["proof"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 40)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="次のことを証明しなさい",
        ),
    )
