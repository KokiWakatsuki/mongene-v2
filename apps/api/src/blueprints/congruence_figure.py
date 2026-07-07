"""CongruenceFigureStructure（visual 用・合同/相似の2図形提示）

ProofStructure が持つ「2図形＋対応マーク」の描画（builder._build_congruence_proof）を
visual form でも使えるようにするための blueprint。証明そのものではなく、
「図の2つの図形が合同（相似）であること・対応する辺と角」を図から読み取って答える
題材を出す。proof_type を params で切り替え（congruence / similarity）。

答え・logic_steps は ProveGeometryVerb に委譲（表示のみ builder が2図形へ拡張）。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.prove_geometry_verb import ProveGeometryVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def build_congruence_figure_blueprint(params: dict | None = None) -> BlueprintDefinition:
    p = params or {}
    proof_type = p.get("proof_type", "congruence")
    condition_set = p.get("condition_set", "SAS")
    # 答えは「△ABC ≡ △DEF」等の1式なので、問いも合同/相似の式表現に限定する
    # （対応辺・角を全列挙させると答え(1式)と不整合になる＝Phase B で確認）。
    if proof_type == "similarity":
        final_q = "図の2つの三角形は相似である。対応する頂点の順に、記号 ∽ を使って相似を式で表しなさい。"
    else:
        final_q = "図の2つの三角形は合同である。対応する頂点の順に、記号 ≡ を使って合同を式で表しなさい。"
    return BlueprintDefinition(
        blueprint_id="CongruenceFigureStructure",
        blueprint_version="v1",
        noun_slots={
            "figure_a": NounSlot(
                slot_name="figure_a",
                accepted_tags=["plane_geometry"],
                required=True,
                constraints_override={"polygon_type": "triangle"},
            ),
            "figure_b": NounSlot(
                slot_name="figure_b",
                accepted_tags=["plane_geometry"],
                required=True,
                constraints_override={"polygon_type": "triangle"},
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=ProveGeometryVerb(proof_type=proof_type, condition_set=condition_set),
                input_slots=["figure_a", "figure_b"],
                output_slot="proof",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="2D_Geometry_Renderer",
            compatible_noun_types=["PolygonAtom"],
            required=True,
        ),
        supported_forms=["visual"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 55)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            final_question=final_q,
        ),
    )
