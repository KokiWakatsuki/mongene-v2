"""BasicGeometryMeasurementStructure（§17.4 #3）

平面・空間図形の面積・体積・表面積を計算する。

`params.measure_type`（既定 "area"）で `MeasureGeometryVerb` の計測種別を切り替えられる。
例: g1_l51（柱体・錐体の表面積）は `blueprint_params: {"measure_type": "surface_area"}` で
PrismAtom/PyramidAtom/SphereAtom の `surface_area_expr` を直接問う（`area` 指定時の
「立体なら volume を優先」フォールバックを回避し、表面積を確実に問えるようにするため）。
"""
from __future__ import annotations

from typing import List

from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb, MeasureType
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot

# measure_type ごとの visual 互換 Atom（3D立体の表面積/体積は 3D_Renderer で描画する）
_VISUAL_COMPONENT_BY_MEASURE_TYPE = {
    "surface_area": "3D_Renderer",
    "volume": "3D_Renderer",
}
_COMPATIBLE_NOUN_TYPES_BY_MEASURE_TYPE = {
    "surface_area": ["PrismAtom", "PyramidAtom", "SphereAtom"],
    "volume": ["PrismAtom", "PyramidAtom", "SphereAtom"],
}


def build_basic_geometry_measurement_blueprint(params: dict | None = None) -> BlueprintDefinition:
    params = params or {}
    measure_type: MeasureType = params.get("measure_type", "area")
    visual_component = _VISUAL_COMPONENT_BY_MEASURE_TYPE.get(measure_type, "2D_Geometry_Renderer")
    compatible_noun_types: List[str] = _COMPATIBLE_NOUN_TYPES_BY_MEASURE_TYPE.get(
        measure_type, ["PolygonAtom", "CircleAtom"]
    )
    return BlueprintDefinition(
        blueprint_id="BasicGeometryMeasurementStructure",
        blueprint_version="v1",
        noun_slots={
            "shape": NounSlot(
                slot_name="shape",
                accepted_tags=["geometry"],  # plane_geometry/space_geometry 両方を含む共通タグ
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type=measure_type),
                input_slots=["shape"],
                output_slot="measure",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type=visual_component,
            compatible_noun_types=compatible_noun_types,
            required=False,
        ),
        supported_forms=["word_problem", "calculation", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 25)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="図形の面積（または体積・表面積）を求めなさい",
        ),
    )
