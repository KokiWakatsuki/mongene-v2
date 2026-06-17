"""BasicCalculationStructure Blueprint（§17.4, §41.2 step 22）

Phase 1 の垂直スライス用に NumberAtom + CalculateArithmeticVerb のみで動く最低実装。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.calculate_arithmetic_verb import CalculateArithmeticVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_basic_calculation_blueprint() -> BlueprintDefinition:
    """中1 四則計算用の最小 Blueprint"""
    return BlueprintDefinition(
        blueprint_id="BasicCalculationStructure",
        blueprint_version="v1",
        noun_slots={
            "left": NounSlot(
                slot_name="left",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom"],
                required=True,
            ),
            "right": NounSlot(
                slot_name="right",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=CalculateArithmeticVerb(operation="+"),
                input_slots=["left", "right"],
                output_slot="result",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["NumberAtom"],
            required=False,
        ),
        supported_forms=["calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 11)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question="次の計算をしなさい",
        ),
    )


# 旧 API（Phase 1 互換、tests/integration/test_hello_world.py 用）
BLUEPRINT_REGISTRY = {
    "BasicCalculationStructure": build_basic_calculation_blueprint,
}


def load_blueprint(blueprint_id: str) -> BlueprintDefinition:
    """旧 API（Phase 1 互換）。新規コードは apps.api.src.blueprints.registry.load_blueprint を使用"""
    if blueprint_id not in BLUEPRINT_REGISTRY:
        raise KeyError(f"未登録の Blueprint: {blueprint_id}")
    return BLUEPRINT_REGISTRY[blueprint_id]()
