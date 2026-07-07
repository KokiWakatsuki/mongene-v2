"""CoordinatePlaneStructure Blueprint

座標平面上の比例 $y=ax$／反比例 $y=a/x$ のグラフを題材にする。
中1「関数」単元の比例・反比例レッスン（g1_l29/31/32＝比例、g1_l34/35＝反比例）の
visual/calculation form に用いる。

Graph_Renderer が LinearFuncAtom／InverseFuncAtom を直線／双曲線として描画し、
EvaluateFunctionVerb がグラフ上の点 $y_0=f(x_0)$ を SymPy 代入で求める（moat）。

params:
    func_type: "proportion" | "inverse"
        比例なら LinearFuncAtom（force_proportion は mapping の atom_constraints で付与）、
        反比例なら InverseFuncAtom のみをスロット候補にする。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.evaluate_function_verb import EvaluateFunctionVerb
from apps.api.src.atoms.verb.read_coordinate_verb import ReadCoordinateVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_coordinate_plane_blueprint(params: dict | None = None) -> BlueprintDefinition:
    params = params or {}
    func_type = params.get("func_type", "proportion")

    if func_type == "point":
        noun_type = "PointAtom"
        tag = "coordinate"
        verb = ReadCoordinateVerb()
        question = "座標平面上の点をとり、その点の座標を答えなさい"
    elif func_type == "inverse":
        noun_type = "InverseFuncAtom"
        tag = "inverse_proportion"
        verb = EvaluateFunctionVerb()
        question = "反比例のグラフをかき、指定した x の値に対応する y の値を求めなさい"
    else:
        noun_type = "LinearFuncAtom"
        tag = "linear_function"
        verb = EvaluateFunctionVerb()
        question = "比例のグラフをかき、指定した x の値に対応する y の値を求めなさい"

    return BlueprintDefinition(
        blueprint_id="CoordinatePlaneStructure",
        blueprint_version="v1",
        noun_slots={
            "func": NounSlot(
                slot_name="func",
                accepted_tags=[tag],
                accepted_noun_types=[noun_type],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=verb,
                input_slots=["func"],
                output_slot="value",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="Graph_Renderer",
            compatible_noun_types=[noun_type],
            required=False,
        ),
        supported_forms=["visual", "calculation"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 30)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            final_question=question,
        ),
    )
