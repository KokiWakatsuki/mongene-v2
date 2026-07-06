"""API 用 Pydantic モデル（§31）"""
from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class CurriculumInput(BaseModel):
    grade: Literal[1, 2, 3]
    domain: Optional[str] = None
    large_unit: Optional[str] = None
    lesson_ids: List[str] = Field(default_factory=list)


class ProblemGenerationRequest(BaseModel):
    curriculum: CurriculumInput
    problem_form: Literal["word_problem", "calculation", "proof", "knowledge", "visual"]
    target_difficulty: Optional[int] = Field(default=None, ge=1, le=100)
    target_level: Optional[int] = Field(default=None, ge=1)
    unlearned_lesson_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_difficulty_or_level(self) -> "ProblemGenerationRequest":
        if self.target_difficulty is None and self.target_level is None:
            raise ValueError("target_difficulty または target_level のどちらかを指定してください")
        return self


class AnswerSchema(BaseModel):
    type: Literal["numeric", "expression", "proof", "set", "graph", "knowledge"]
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
