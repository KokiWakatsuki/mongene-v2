"""AlgebraicProofStructure（§17.4 #9, §26）

代数的証明（偶数・奇数の性質など）専用の Blueprint。
NumberAtom/PolynomialAtom 1 つに対して ProveAlgebraicVerb を適用する。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.prove_algebraic_verb import ProveAlgebraicVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_algebraic_proof_blueprint(params: dict | None = None) -> BlueprintDefinition:
    p = params or {}
    proof_type = p.get("proof_type", "even_odd")
    return BlueprintDefinition(
        blueprint_id="AlgebraicProofStructure",
        blueprint_version="v1",
        noun_slots={
            "target": NounSlot(
                slot_name="target",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom", "PolynomialAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=ProveAlgebraicVerb(proof_type=proof_type),
                input_slots=["target"],
                output_slot="proof",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["NumberAtom"],
            required=False,
        ),
        supported_forms=["proof"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 12)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="次のことを証明しなさい",
        ),
    )
