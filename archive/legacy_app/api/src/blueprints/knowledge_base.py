"""KnowledgeBaseStructure Blueprint

知識問題（概念・用語の確認）専用の Blueprint。
mapping.json の difficulty_levels.knowledge[lv].blueprint_params.knowledge_hint を
subquestion_strategy.final_question として使用することで、
prompt_hint が「概念確認型」のテキストになる。

KnowledgeCheckVerb の operation_name は "knowledge_check" なので、
subquestion_builder の _augment_prompt_hint（計算式追加）はスキップされる。
"""
from __future__ import annotations

from apps.api.src.atoms.verb.knowledge_check_verb import KnowledgeCheckVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot


def _normalize_hint(raw: str) -> str:
    """テーマ名のみの文字列を問いかけ形式に変換する。"""
    if not raw.endswith(("なさい", "？", "か", "い", "せよ")):
        return f"次の問いに答えなさい：{raw}について説明しなさい。"
    return raw


def build_knowledge_base_blueprint(params: dict | None = None) -> BlueprintDefinition:
    params = params or {}

    # 複数候補 knowledge_hints があれば全て正規化。なければ単一 knowledge_hint を使用
    raw_hints: list[str] = params.get("knowledge_hints", [])
    if not raw_hints:
        raw_hints = [params.get("knowledge_hint", "次の問いに答えなさい")]
    hints = [_normalize_hint(h) for h in raw_hints]

    return BlueprintDefinition(
        blueprint_id="KnowledgeBaseStructure",
        blueprint_version="v1",
        noun_slots={
            "subject": NounSlot(
                slot_name="subject",
                accepted_tags=["number"],
                accepted_noun_types=["NumberAtom"],
                required=True,
            ),
        },
        verb_invocations=[
            VerbInvocation(
                verb=KnowledgeCheckVerb(hints=hints),
                input_slots=["subject"],
                output_slot="result",
                on_failure="retry_seed",
            ),
        ],
        visual_slot=VisualSlot(
            component_type="NullRenderer",
            compatible_noun_types=["NumberAtom"],
            required=False,
        ),
        supported_forms=["knowledge"],
        story_required=False,
        base_difficulty_calculator=lambda nouns, ctx: int(ctx.get("y_base", 30)),
        subquestion_strategy=SubQuestionStrategy(
            strategy_type="single",
            target_count=1,
            intermediate_outputs=[],
            final_question=hints[0],
        ),
    )
