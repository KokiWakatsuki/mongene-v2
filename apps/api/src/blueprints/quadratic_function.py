"""QuadraticFunctionStructure Blueprint

放物線 y=ax² と直線 y=mx+n の交点を求める問題を生成する。
y=ax² の二次関数単元（g3_l32〜l37）および exam_l2 に使用。
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


def build_quadratic_function_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="QuadraticFunctionStructure",
        blueprint_version="v1",
        noun_slots={
            "func_q": NounSlot(
                slot_name="func_q",
                accepted_tags=["quadratic_function"],
                accepted_noun_types=["QuadraticFuncAtom"],
                required=True,
            ),
            "func_l": NounSlot(
                slot_name="func_l",
                accepted_tags=["linear_function"],
                accepted_noun_types=["LinearFuncAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=IntersectVerb(),
                input_slots=["func_q", "func_l"],
                output_slot="intersection",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Graph_Renderer",
            compatible_noun_types=["QuadraticFuncAtom", "LinearFuncAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 60)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="放物線と直線の交点の座標を求めなさい",
        ),
    )
