"""SimultaneousEquationsStructure Blueprint

2 つの EquationAtom（ax + by = c 形式）を連立して解く問題を生成する。
g2_l11〜l15（加減法・代入法・連立方程式）に使用。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.simultaneous_eq_verb import SimultaneousEqVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_simultaneous_equations_blueprint(params: dict | None = None) -> BlueprintDefinition:
    params = params or {}
    allow_fraction = bool(params.get("allow_fraction", False))
    return BlueprintDefinition(
        blueprint_id="SimultaneousEquationsStructure",
        blueprint_version="v1",
        noun_slots={
            "eq_a": NounSlot(
                slot_name="eq_a",
                accepted_tags=["linear_equation"],
                accepted_noun_types=["EquationAtom"],
                required=True,
            ),
            "eq_b": NounSlot(
                slot_name="eq_b",
                accepted_tags=["linear_equation"],
                accepted_noun_types=["EquationAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=SimultaneousEqVerb(allow_fraction=allow_fraction),
                input_slots=["eq_a", "eq_b"],
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
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 40)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="次の連立方程式を解きなさい",
        ),
    )
