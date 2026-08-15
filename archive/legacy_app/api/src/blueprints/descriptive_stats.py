"""DescriptiveStatsStructure Blueprint

DataSetAtom + AnalyzeDataVerb を組み合わせた統計（代表値・四分位数）問題。
metric は blueprint_params 経由で指定する（デフォルト: mean）。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.analyze_data_verb import AnalyzeDataVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot

_METRIC_LABEL = {
    "mean": "平均値",
    "median": "中央値",
    "mode": "最頻値",
    "q1": "第1四分位数",
    "q3": "第3四分位数",
    "iqr": "四分位範囲",
    "cumulative_frequency": "累積度数",
    "cumulative_relative_frequency": "累積相対度数",
}


def build_descriptive_stats_blueprint(params: dict | None = None) -> BlueprintDefinition:
    metric = (params or {}).get("metric", "mean")
    label = _METRIC_LABEL.get(metric, metric)
    return BlueprintDefinition(
        blueprint_id="DescriptiveStatsStructure",
        blueprint_version="v1",
        noun_slots={
            "dataset": NounSlot(
                slot_name="dataset",
                accepted_tags=["statistics"],
                accepted_noun_types=["DataSetAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=AnalyzeDataVerb(metric=metric),
                input_slots=["dataset"],
                output_slot="result",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Table_Chart_Renderer",
            compatible_noun_types=["DataSetAtom"],
            required=False,
        ),
        supported_forms=["calculation", "word_problem", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 20)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question=f"データの{label}を求めなさい",
        ),
    )
