"""SimilarityStructure Blueprint（中3・相似/線分比/中点連結の長さ算出）

相似比・平行線と線分の比・中点連結定理で「長さ x を求める」calc 問題を生成する。
数学核は比 a:b = c:x を解く（ProportionAtom + SolveSimilarityVerb）で、context により
幾何の定理文脈を narration と問い文に付け、bare な比例式計算（題材ズレ）を避ける。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.solve_similarity_verb import SolveSimilarityVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot

_FINAL_Q = {
    "similarity_ratio": "相似な図形の相似比と対応する辺の長さから、$x$ の長さを求めなさい。",
    "parallel_segments": "平行線と線分の比の定理を使って、$x$ の長さを求めなさい。",
    "midpoint_connector": "中点連結定理を使って、$x$ の長さを求めなさい。",
}


def build_similarity_blueprint(params: dict | None = None) -> BlueprintDefinition:
    p = params or {}
    context = p.get("context", "similarity_ratio")
    final_q = _FINAL_Q.get(context, _FINAL_Q["similarity_ratio"])
    return BlueprintDefinition(
        blueprint_id="SimilarityStructure",
        blueprint_version="v1",
        noun_slots={
            "ratio": NounSlot(
                slot_name="ratio",
                accepted_tags=["proportion_equation"],
                accepted_noun_types=["ProportionAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=SolveSimilarityVerb(context=context),
                input_slots=["ratio"],
                output_slot="length",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["ProportionAtom"],
            required=False,
        ),
        supported_forms=["calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 55)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question=final_q,
        ),
    )
