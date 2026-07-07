"""ContextualCalculationStructure（文脈計算型の文章題・§17.4）

「日常の場面に即して計算する」型の文章題。BasicCalculationStructure と同じ
CalculateArithmeticVerb（SymPy で計算・答えを保証）を用いつつ、story_required=True で
場面設定を必須にし supported_forms=["word_problem"] とする。

- 方程式を立てて解く WordProblemStructure（linear_equation 専用）とも、
- 式そのものが答えの WordProblemFormulationStructure（立式）とも異なり、
答えは **計算結果の数/式**（story で文脈化する）。

number/polynomial/square_root のいずれの Atom も受け付け、lesson の required_tags に委ねる。
params.operation: 四則演算子（None なら Verb 側でランダム）。
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


def build_contextual_calculation_blueprint(params: dict | None = None) -> BlueprintDefinition:
    op = (params or {}).get("operation", "+")
    return BlueprintDefinition(
        blueprint_id="ContextualCalculationStructure",
        blueprint_version="v1",
        noun_slots={
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
                verb=CalculateArithmeticVerb(operation=op),
                input_slots=["left", "right"],
                output_slot="result",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(component_type="NullRenderer", required=False),
        supported_forms=["word_problem"],
        story_required=True,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 20)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="場面に即して計算し、答えを求めなさい",
        ),
    )
