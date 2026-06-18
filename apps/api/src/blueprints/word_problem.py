"""WordProblemStructure（§17.4 #2）

文章題立式（速さ・濃度・割合・仕事算・過不足算）。StoryContext を要求。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.solve_eq_verb import SolveEqVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_word_problem_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="WordProblemStructure",
        blueprint_version="v1",
        noun_slots={
            "equation": NounSlot(
                slot_name="equation",
                accepted_tags=["linear_equation"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=SolveEqVerb(),
                input_slots=["equation"],
                output_slot="solution",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(component_type="NullRenderer", required=False),
        supported_forms=["word_problem"],
        story_required=True,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 30)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="方程式を立てて解きなさい",
        ),
    )
