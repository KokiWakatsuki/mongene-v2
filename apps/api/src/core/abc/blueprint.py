"""Blueprint 定義（§12.1, §27）"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional

from apps.api.src.core.abc.atoms import NounAtom
from apps.api.src.core.abc.visuals import VisualSlot


@dataclass
class NounSlot:
    slot_name: str
    accepted_tags: List[str] = field(default_factory=list)
    accepted_noun_types: List[str] = field(default_factory=list)
    required: bool = True
    constraints_override: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryContext:
    scenario_id: str
    characters: List[str]
    setting: str
    units: Dict[str, str]
    narrative_hint: str


@dataclass
class VerbInvocation:
    verb: Any
    input_slots: List[str]
    output_slot: str
    on_failure: Literal["retry_seed", "fallback_atom", "abort"] = "retry_seed"


@dataclass
class SubQuestionStrategy:
    strategy_type: Literal["single", "incremental", "guided", "ladder"]
    target_count: int = 1
    intermediate_outputs: List[str] = field(default_factory=list)
    final_question: str = ""
    # intermediate_outputs[i] に対応する logic_steps_by_slot のキー
    # 指定があれば slot ごとに別々の logic_step を割り当てる（同じ答えが繰り返される問題を回避）
    intermediate_slots: List[str] = field(default_factory=list)
    final_slot: str | None = None


# (sampled_nouns, ctx) -> y_base (1-100)
BaseDifficultyCalc = Callable[[Dict[str, NounAtom], Dict[str, Any]], int]


@dataclass
class BlueprintDefinition:
    blueprint_id: str
    blueprint_version: str
    noun_slots: Dict[str, NounSlot]
    verb_invocations: List[VerbInvocation]
    visual_slot: Optional[VisualSlot]
    supported_forms: List[Literal["word_problem", "calculation", "proof"]]
    base_difficulty_calculator: BaseDifficultyCalc
    story_required: bool = False
    subquestion_strategy: Optional[SubQuestionStrategy] = None
