"""WordProblemFormulationStructure（立式型の文章題・§17.4）

「数量を文字式で表す／等式・不等式で表す」型の文章題。方程式を立てて解く
WordProblemStructure（linear_equation 専用）と異なり、答えは **式そのもの**（解かない）。
FormulateVerb を中核に持ち、number/polynomial 系の Atom を受け付ける。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.formulate_verb import FormulateVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_word_problem_formulation_blueprint(params: dict | None = None) -> BlueprintDefinition:
    mode = (params or {}).get("mode", "expression")
    return BlueprintDefinition(
        blueprint_id="WordProblemFormulationStructure",
        blueprint_version="v1",
        noun_slots={
            "quantity": NounSlot(
                slot_name="quantity",
                accepted_tags=["polynomial", "number"],
                accepted_noun_types=["PolynomialAtom", "NumberAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=FormulateVerb(mode=mode),
                input_slots=["quantity"],
                output_slot="formula",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(component_type="NullRenderer", required=False),
        supported_forms=["word_problem"],
        story_required=True,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 20)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="下線部の数量を文字式で表しなさい",
        ),
    )
