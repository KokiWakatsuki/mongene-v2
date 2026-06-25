"""生徒エンドポイント（個別最適化ループの identity 正本）。"""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.src.domains.learning.deps import get_mapping, get_store
from apps.api.src.core.store.models import Student

router = APIRouter(prefix="/students", tags=["students"])


class StudentCreateRequest(BaseModel):
    grade: int = Field(ge=1, le=3)
    external_id: Optional[str] = None
    student_id: Optional[str] = None  # 省略時はサーバ採番


class StudentResponse(BaseModel):
    id: str
    grade: int
    external_id: Optional[str] = None


class MasteryItem(BaseModel):
    lesson_id: str
    title: str
    mastery: float
    mastered: bool
    attempted: bool
    attempt_count: int
    correct_streak: int


class MasterySummary(BaseModel):
    student_id: str
    mastered_count: int
    in_progress_count: int
    lessons: List[MasteryItem]


@router.post("", response_model=StudentResponse)
def create_student(req: StudentCreateRequest) -> StudentResponse:
    store = get_store()
    student_id = req.student_id or uuid.uuid4().hex
    store.upsert_student(Student(id=student_id, grade=req.grade, external_id=req.external_id))
    return StudentResponse(id=student_id, grade=req.grade, external_id=req.external_id)


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: str) -> StudentResponse:
    student = get_store().get_student(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"未登録の student_id: {student_id}")
    return StudentResponse(id=student.id, grade=student.grade, external_id=student.external_id)


@router.get("/{student_id}/mastery", response_model=MasterySummary)
def get_mastery(student_id: str) -> MasterySummary:
    store = get_store()
    if store.get_student(student_id) is None:
        raise HTTPException(status_code=404, detail=f"未登録の student_id: {student_id}")
    mapping = get_mapping()
    states = store.all_mastery(student_id)
    lessons = [
        MasteryItem(
            lesson_id=s.lesson_id,
            title=mapping.get(s.lesson_id, {}).get("title", s.lesson_id),
            mastery=round(s.mastery, 3),
            mastered=s.mastered,
            attempted=s.attempted,
            attempt_count=s.attempt_count,
            correct_streak=s.correct_streak,
        )
        for s in states
    ]
    return MasterySummary(
        student_id=student_id,
        mastered_count=sum(1 for s in states if s.mastered),
        in_progress_count=sum(1 for s in states if s.attempted and not s.mastered),
        lessons=lessons,
    )
