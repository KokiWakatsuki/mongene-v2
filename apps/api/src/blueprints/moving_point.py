"""MovingPointStructure（§17.4 #6）

動点による面積変化（時間関数）。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_moving_point_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="MovingPointStructure",
        blueprint_version="v1",
        noun_slots={
            "base_shape": NounSlot(
                slot_name="base_shape",
                accepted_tags=["plane_geometry"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="area"),
                input_slots=["base_shape"],
                output_slot="area",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom"],
            required=True,
        ),
        # NOTE(2026-07-07): calc/visual は意図的に未開通。MovingPointStructure は
        # (1) noun_slot が accepted_tags=["plane_geometry"] のみで CircleAtom が混入
        #     （動点問題なのに円が約57%出る）、(2) 3小問が動点の時間変化を反映せず
        #     全て同一答えを返す、という構造欠陥を持つ。契約哲学「壊れた出力を隠すより
        #     422で誠実に失敗」に従い、これらが直る（accepted_noun_types付与＋
        #     時間パラメトリックな面積Verb）までは word_problem 以外を開通しない。
        #     詳細は docs/HANDOFF_2026-07-06.md §13。
        supported_forms=["word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 65)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=["t=2 秒の点 P の位置", "△APQ の面積を t の式で表す"],
            final_question="△APQ の面積が最大となる時刻 t と、その面積",
        ),
    )
