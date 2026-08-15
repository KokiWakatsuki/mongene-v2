"""SolveEquationStructure Blueprint

一次・二次・連立方程式の「解きなさい」型問題を生成する。
EquationAtom を一つ選び SolveEqVerb で解く。
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


def build_solve_equation_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="SolveEquationStructure",
        blueprint_version="v1",
        noun_slots={
            "equation": NounSlot(
                slot_name="equation",
                accepted_tags=["linear_equation"],
                accepted_noun_types=["EquationAtom", "ProportionAtom"],
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
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["EquationAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 11)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="次の方程式を解きなさい",
        ),
    )


BLUEPRINT_REGISTRY = {
    "SolveEquationStructure": build_solve_equation_blueprint,
}
