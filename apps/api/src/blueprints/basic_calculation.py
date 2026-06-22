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
    """BasicCalculationStructure: 四則・方程式・展開・因数分解・整数論（設計書 §17.4）

    slot の accepted_tags を空にして mapping の required_tags に委ねる（§38.2）。
    → number タグ lesson: NumberAtom が選ばれ足し算・引き算
    → polynomial タグ lesson: PolynomialAtom が選ばれ展開・因数分解
    → square_root タグ lesson: SquareRootAtom が選ばれ根号計算
    """
    return BlueprintDefinition(
        blueprint_id="BasicCalculationStructure",
        blueprint_version="v1",
        noun_slots={
            # accepted_noun_types で CalculateArithmeticVerb が受け付ける型を明示
            # → required_tags が "polynomial" なら PolynomialAtom が選ばれる（§38.2）
            # → required_tags が "linear_equation" 等の場合 NumberAtom にフォールバック
            "left": NounSlot(
                slot_name="left",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom", "PolynomialAtom", "SquareRootAtom"],
                required=True,
            ),
            "right": NounSlot(
                slot_name="right",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom", "PolynomialAtom", "SquareRootAtom"],
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
