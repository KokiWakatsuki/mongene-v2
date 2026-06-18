"""API 用 Pydantic モデル（§31）"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class CurriculumInput(BaseModel):
    grade: Literal[1, 2, 3]
    domain: Optional[str] = None
    large_unit: Optional[str] = None
    lesson_ids: List[str] = Field(default_factory=list)


class ProblemGenerationRequest(BaseModel):
    curriculum: CurriculumInput
    problem_form: Literal["word_problem", "calculation", "proof"]
    target_difficulty: int = Field(ge=1, le=100)
    unlearned_lesson_ids: List[str] = Field(default_factory=list)


class AnswerSchema(BaseModel):
    type: Literal["numeric", "expression", "proof", "set", "graph"]
    sympy_form: Optional[str] = None
    text_form: str
    extras: dict[str, Any] = Field(default_factory=dict)


class SubQuestionSchema(BaseModel):
    label: str
    prompt_text: str
    answer: AnswerSchema
    explanation_text: Optional[str] = None


class VisualsSchema(BaseModel):
    problem_diagram_url: Optional[str] = None
    explanation_diagram_url: Optional[str] = None


class MetadataSchema(BaseModel):
    base_difficulty: int
    adjustment_delta: int = 0
    used_atoms: List[str]
    seed: int
    blueprint_id: str
    blueprint_version: str
    model_used: str = "gemini-flash-lite-latest"
    git_commit: Optional[str] = None


class ProblemGenerationResponse(BaseModel):
    content_problem_text: str
    sub_questions: List[SubQuestionSchema]
    visuals: VisualsSchema
    metadata: MetadataSchema


class TeacherUnlearnedInput(BaseModel):
    """教師宣言: クラスがまだ習っていない lesson_ids"""

    class_id: str
    unlearned_lesson_ids: List[str]
