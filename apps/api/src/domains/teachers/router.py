"""教師宣言エンドポイント（§35.2, §6）"""
from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter

from apps.api.src.domains.problems.schemas import TeacherUnlearnedInput

router = APIRouter(prefix="/teachers", tags=["teachers"])

# シンプルな in-memory ストア（永続化は §20）
_classes: Dict[str, List[str]] = {}


@router.post("/unlearned")
def declare_unlearned(payload: TeacherUnlearnedInput) -> Dict[str, object]:
    _classes[payload.class_id] = list(payload.unlearned_lesson_ids)
    return {"class_id": payload.class_id, "unlearned_lesson_ids": _classes[payload.class_id]}


@router.get("/unlearned/{class_id}")
def get_unlearned(class_id: str) -> Dict[str, object]:
    return {"class_id": class_id, "unlearned_lesson_ids": _classes.get(class_id, [])}
