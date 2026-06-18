"""中間表現データモデル（§12.1）"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import sympy

from apps.api.src.core.abc.visuals import VisualDSL


@dataclass
class LogicStep:
    operation_name: str
    operands: List[str]
    sympy_expr: sympy.Expr
    narration_hint: str


@dataclass
class AnswerObject:
    type: Literal["numeric", "expression", "proof", "set", "graph"]
    sympy_form: Optional[sympy.Expr]
    text_form: str
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubQuestion:
    label: str
    prompt_hint: str
    logic_steps: List[LogicStep]
    answer: AnswerObject
    depends_on: List[str] = field(default_factory=list)


@dataclass
class MiddleRepresentation:
    problem_structure_type: str
    selected_tags: List[str]
    difficulty_score: float
    problem_form: Literal["word_problem", "calculation", "proof"]
    sub_questions: List[SubQuestion]
    visual_dsl: Optional[VisualDSL]
    seed: int
    blueprint_id: str
    blueprint_version: str
    # サンプルされた Atom の型情報・主要パラメータ（LLM プロンプトに渡して用語を一致させる）
    sampled_nouns_info: Dict[str, Dict[str, Any]] = field(default_factory=dict)
