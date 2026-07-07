"""MovingPointStructure（§17.4 #6）

動点による三角形面積の時間変化。点 P が図形の底辺を基線として一定の速さで高さ方向に
進むとき、三角形の面積 S(t) が時刻 t の関数として変化する（比例／1次）。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.moving_point_area_verb import MovingPointAreaVerb
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
        blueprint_version="v2",
        noun_slots={
            # 底面図形。accepted_noun_types で PolygonAtom に限定し CircleAtom 混入を防ぐ
            # （2026-07-07 §9 の構造欠陥①を解消）。
            "figure": NounSlot(
                slot_name="figure",
                accepted_tags=["plane_geometry"],
                accepted_noun_types=["PolygonAtom"],
                required=True,
            ),
            # 動点（速さ v を提供）。accepted_tags は空にして required_tags=plane_geometry
            # のフィルタで落ちないようにする（AtomSelector のフォールバック経路）。
            "mover": NounSlot(
                slot_name="mover",
                accepted_tags=[],
                accepted_noun_types=["MovingPointAtom"],
                required=True,
            ),
        },
        # 同一の sampled atom を共有する 3 つの決定論 query で、動点設定が整合した
        # 3 小問（特定時刻の面積 / t の式 / 最大面積）を作る（§9 の構造欠陥②を解消）。
        verb_invocations=[
            VerbInvocation(
                verb=MovingPointAreaVerb(query="area_at_t"),
                input_slots=["figure", "mover"],
                output_slot="area_at_t",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=MovingPointAreaVerb(query="area_function"),
                input_slots=["figure", "mover"],
                output_slot="area_function",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=MovingPointAreaVerb(query="max_area"),
                input_slots=["figure", "mover"],
                output_slot="max_area",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom"],
            required=True,
        ),
        # §9 の構造欠陥（① CircleAtom 混入・② 3 小問同一答え）を解消したため calc/visual を開通。
        supported_forms=["calculation", "word_problem", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 65)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=[
                "点 P が出発してからの時間を t 秒とするとき、ある時刻での三角形の面積",
                "三角形の面積 S を t の式で表しなさい",
            ],
            intermediate_slots=["area_at_t", "area_function"],
            final_question="点 P が動くときの三角形の面積の最大値を求めなさい",
            final_slot="max_area",
        ),
    )
