"""GraphStructure Blueprint - 関数グラフの書き方・読み取り問題専用

対応する lesson タイプ:
  - 比例・反比例のグラフ（中1）
  - 一次関数のグラフ（中2）
  - y=ax² のグラフ（中3）

supported_forms: ["graph", "calculation"]
  - graph: グラフを書いて特徴を調べる問題
  - calculation: 式から値を計算する問題
"""
from __future__ import annotations

from apps.api.src.atoms.verb.graph_drawing_verb import GraphDrawingVerb
from apps.api.src.atoms.verb.intersect_verb import IntersectVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_graph_structure_blueprint() -> BlueprintDefinition:
    """1 つの関数のグラフ問題（書き方・切片・代表点）"""
    return BlueprintDefinition(
        blueprint_id="GraphStructure",
        blueprint_version="v1",
        noun_slots={
            "func": NounSlot(
                slot_name="func",
                accepted_tags=["linear_function"],  # LinearFuncAtom / QuadraticFuncAtom
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=GraphDrawingVerb(),
                input_slots=["func"],
                output_slot="graph_points",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Graph_Renderer",
            compatible_noun_types=["LinearFuncAtom", "QuadraticFuncAtom", "InverseFuncAtom"],
            required=True,
        ),
        supported_forms=["graph", "calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 20)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=[
                "関数の式を確認し、y切片と傾きを求めなさい",
                "代表点（x=1, x=2）の座標を求めなさい",
            ],
            intermediate_slots=["graph_points", "graph_points"],
            final_question="グラフをかきなさい（または、グラフの特徴をすべて求めなさい）",
            final_slot="graph_points",
        ),
    )


def build_two_functions_blueprint() -> BlueprintDefinition:
    """2 つの関数の交点・面積問題（中2〜中3）"""
    return BlueprintDefinition(
        blueprint_id="TwoFunctionsStructure",
        blueprint_version="v1",
        noun_slots={
            "func_a": NounSlot(
                slot_name="func_a",
                accepted_tags=["linear_function"],
                required=True,
            ),
            "func_b": NounSlot(
                slot_name="func_b",
                accepted_tags=["linear_function"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=GraphDrawingVerb(),
                input_slots=["func_a"],
                output_slot="graph_a",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=GraphDrawingVerb(),
                input_slots=["func_b"],
                output_slot="graph_b",
                on_failure="retry_seed",
            ),
            VerbInvocation(
                verb=IntersectVerb(),
                input_slots=["func_a", "func_b"],
                output_slot="intersection",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Graph_Renderer",
            compatible_noun_types=["LinearFuncAtom", "QuadraticFuncAtom"],
            required=True,
        ),
        supported_forms=["graph", "word_problem"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 40)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="incremental",
            target_count=2,
            intermediate_outputs=[
                "2 つの関数のグラフをかきなさい",
                "2 直線の交点の座標を求めなさい",
            ],
            intermediate_slots=["graph_a", "intersection"],
            final_question="交点と座標軸で囲まれる三角形の面積を求めなさい",
            final_slot="intersection",
        ),
    )
