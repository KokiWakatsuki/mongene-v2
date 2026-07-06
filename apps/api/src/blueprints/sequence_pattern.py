"""SequencePatternStructure（§17.4 #11）

マッチ棒・図形成長・段と列・分数列・ピラミッド型。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.generalize_formula_verb import GeneralizeFormulaVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_sequence_pattern_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="SequencePatternStructure",
        blueprint_version="v1",
        noun_slots={
            "sequence": NounSlot(
                slot_name="sequence",
                accepted_tags=["sequence"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=GeneralizeFormulaVerb(),
                input_slots=["sequence"],
                output_slot="formula",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(component_type="NullRenderer", required=False),
        supported_forms=["calculation", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 55)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=["第 5 項の値"],
            final_question="第 n 項の一般式を求めなさい",
        ),
    )
