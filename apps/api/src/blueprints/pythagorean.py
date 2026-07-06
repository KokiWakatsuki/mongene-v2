"""PythagoreanStructure Blueprint（三平方の定理専用）

三平方の定理で辺の長さや距離を求める Blueprint。
PythagoreanLengthVerb を中核に持つ。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.pythagorean_length_verb import PythagoreanLengthVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_pythagorean_blueprint(params: dict | None = None) -> BlueprintDefinition:
    """三平方の定理で辺の長さを求める。

    params["mode"] == "two_points": 座標平面上の2点間の距離（PointAtom 2つ使用）
    それ以外:                        直角三角形の斜辺・脚（PolygonAtom 使用）
    """
    p = params or {}
    mode = p.get("mode", "polygon")

    if mode == "two_points":
        return BlueprintDefinition(
            blueprint_id="PythagoreanStructure",
            blueprint_version="v1",
            noun_slots={
                "point_a": NounSlot(
                    slot_name="point_a",
                    accepted_tags=["coordinate"],
                    accepted_noun_types=["PointAtom"],
                    required=True,
                ),
                "point_b": NounSlot(
                    slot_name="point_b",
                    accepted_tags=["coordinate"],
                    accepted_noun_types=["PointAtom"],
                    required=True,
                ),
            },
            verb_invocations=[
                VerbInvocation(
                    verb=PythagoreanLengthVerb(mode="hypotenuse"),
                    input_slots=["point_a", "point_b"],
                    output_slot="distance",
                    on_failure="retry_seed",
                ),
            ],
            visual_slot=VisualSlot(
                component_type="Graph_Renderer",
                compatible_noun_types=["PointAtom"],
                required=True,
            ),
            supported_forms=["visual", "word_problem"],
            story_required=False,
            base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 65)),
            subquestion_strategy=SubQuestionStrategy(
                strategy_type="single",
                final_question="三平方の定理を用いて求めなさい",
            ),
        )

    # デフォルト: polygon モード（直角三角形）
    return BlueprintDefinition(
        blueprint_id="PythagoreanStructure",
        blueprint_version="v1",
        noun_slots={
            "right_triangle": NounSlot(
                slot_name="right_triangle",
                accepted_tags=["plane_geometry"],
                accepted_noun_types=["PolygonAtom", "PointAtom"],
                required=True,
                constraints_override={"polygon_type": "right_triangle", "max_side_length": 15},
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=PythagoreanLengthVerb(mode="hypotenuse"),
                input_slots=["right_triangle"],
                output_slot="hypotenuse",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom"],
            required=True,
        ),
        supported_forms=["visual", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 65)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question="三平方の定理を用いて求めなさい",
        ),
    )


def build_pythagorean_space_blueprint(params: dict | None = None) -> BlueprintDefinition:
    """空間図形（直方体・角錐）で三平方の定理を利用する"""
    from apps.api.src.atoms.verb.shortest_path_on_solid_verb import ShortestPathOnSolidVerb

    return BlueprintDefinition(
        blueprint_id="PythagoreanSpaceStructure",
        blueprint_version="v1",
        noun_slots={
            "solid": NounSlot(
                slot_name="solid",
                accepted_tags=["space_geometry"],
                required=True,
            ),
        },
        verb_invocations=[
            # まず体積/母線を計算
            VerbInvocation(
                verb=PythagoreanLengthVerb(mode="hypotenuse"),
                input_slots=["solid"],
                output_slot="slant_length",
                on_failure="retry_seed",
            ),
            # 次に展開図の最短距離を計算
            VerbInvocation(
                verb=ShortestPathOnSolidVerb(),
                input_slots=["solid"],
                output_slot="shortest_path",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="3D_Renderer",
            compatible_noun_types=["PrismAtom", "PyramidAtom"],
            required=True,
        ),
        supported_forms=["word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 78)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=["母線または空間対角線の長さを求める"],
            intermediate_slots=["slant_length"],
            final_question="展開図を利用して表面上の最短距離を求めなさい",
            final_slot="shortest_path",
        ),
    )
