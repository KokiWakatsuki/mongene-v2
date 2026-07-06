"""BasicDifferenceStructure（§17.4 #4, §18.4 設計書通り実装）

くり抜き・回転体・切断・展開図。

設計書 §18.4 より:
- base_solid: PrismAtom / PyramidAtom / SphereAtom（3 種）
- cutout_solid: PrismAtom / PyramidAtom / SphereAtom（3 種）
→ 9 通りの組み合わせが 1 Blueprint から生まれる
"""
from __future__ import annotations

from apps.api.src.atoms.verb.cutout_verb import CutoutVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.atoms.verb.pythagorean_length_verb import PythagoreanLengthVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_basic_difference_blueprint(params: dict | None = None) -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="BasicDifferenceStructure",
        blueprint_version="v1",
        noun_slots={
            # base_solid: 直方体・角柱系（SphereAtom は「何かをくり抜かれる主立体」として不自然なため prism タグで絞る）
            "base_solid": NounSlot(
                slot_name="base_solid",
                accepted_tags=["space_geometry", "prism"],  # PrismAtom のみ prism タグを持つ
                required=True,
            ),
            # cutout_solid: くり抜く立体（pyramid/sphere/prism 全て可）
            "cutout_solid": NounSlot(
                slot_name="cutout_solid",
                accepted_tags=["space_geometry"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="volume"),
                input_slots=["base_solid"],
                output_slot="base_volume",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=PythagoreanLengthVerb(mode="hypotenuse"),
                input_slots=["cutout_solid"],
                output_slot="pythagorean_length",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=MeasureGeometryVerb(measure_type="volume"),
                input_slots=["cutout_solid"],
                output_slot="cutout_volume",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=CutoutVerb(),
                input_slots=["base_solid", "cutout_solid"],
                output_slot="remaining_volume",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="3D_Renderer",
            compatible_noun_types=["PrismAtom", "PyramidAtom", "SphereAtom"],
            required=True,
        ),
        supported_forms=["calculation", "word_problem", "visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 60)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=3,
            intermediate_outputs=[
                "元の立体の体積を求めなさい",
                "三平方の定理を用いて、くり抜く立体の母線または対角線の長さを求めなさい",
                "くり抜く立体の体積を求めなさい",
            ],
            intermediate_slots=["base_volume", "pythagorean_length", "cutout_volume"],
            final_question="くり抜き後の残った立体の体積を求めなさい",
            final_slot="remaining_volume",
        ),
    )
