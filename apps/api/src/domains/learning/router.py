"""学習ループ エンドポイント（採点→習熟更新→次手決定→生成の閉ループ）。

生成本体（/problems/generate の内部実装）を再利用するが、個別最適化では生徒ごとに
問題が変わるため prefetch キャッシュは使わず runner を直接呼ぶ（他生徒への問題漏れ防止）。
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.src.core.adaptive.engine import (
    NoLessonAvailableError,
    candidate_lessons,
    decide_next_lesson,
)
from apps.api.src.core.adaptive.mastery import update_mastery
from apps.api.src.core.grading.auto_grader import grade_answer
from apps.api.src.core.exceptions import MongeneError
from apps.api.src.core.runner.blueprint_runner import GenerationRequest
from apps.api.src.core.store.models import Attempt, GradingEvent, ProblemRecord
from apps.api.src.domains.learning.deps import get_graph, get_mapping, get_store
from apps.api.src.domains.problems.router import _build_response, _get_runner
from apps.api.src.domains.problems.schemas import (
    CurriculumInput,
    ProblemGenerationRequest,
    ProblemGenerationResponse,
)

router = APIRouter(prefix="/learning", tags=["learning"])

_DEFAULT_MAX_SCORE = 10


# ── スキーマ ────────────────────────────────────────────────
class NextRequest(BaseModel):
    student_id: str
    large_unit: Optional[str] = None  # 大単元フォーカス（任意）。指定するとその単元を優先


class MasterySnapshot(BaseModel):
    mastery: float
    mastered: bool
    attempted: bool
    attempt_count: int
    correct_streak: int


class NextResponse(BaseModel):
    problem_id: str
    lesson_id: str
    lesson_title: str
    large_unit: str
    target_difficulty: int
    rationale: str
    problem: ProblemGenerationResponse
    mastery: MasterySnapshot


class PathItem(BaseModel):
    lesson_id: str
    title: str
    large_unit: str
    grade: int


class PathResponse(BaseModel):
    student_id: str
    upcoming: List[PathItem]


class AnswerItem(BaseModel):
    label: str
    answer: str


class SubmitRequest(BaseModel):
    student_id: str
    problem_id: str
    answers: List[AnswerItem]


class QuestionResult(BaseModel):
    label: str
    gradable: bool
    is_correct: bool
    error_type: Optional[str] = None
    expected: Optional[str] = None
    student_answer: Optional[str] = None


class SubmitResponse(BaseModel):
    problem_id: str
    lesson_id: str
    results: List[QuestionResult]
    overall_correct: Optional[bool]
    route_b_needed: bool
    mastery: MasterySnapshot
    mastered: bool


def _snapshot(state) -> MasterySnapshot:
    return MasterySnapshot(
        mastery=round(state.mastery, 3),
        mastered=state.mastered,
        attempted=state.attempted,
        attempt_count=state.attempt_count,
        correct_streak=state.correct_streak,
    )


# ── /learning/next ──────────────────────────────────────────
@router.post("/next", response_model=NextResponse)
def next_problem(req: NextRequest) -> NextResponse:
    store = get_store()
    student = store.get_student(req.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"未登録の student_id: {req.student_id}")

    mapping = get_mapping()
    graph = get_graph()
    try:
        decision = decide_next_lesson(
            student, store, graph, mapping, focus_large_unit=req.large_unit
        )
    except NoLessonAvailableError as e:
        raise HTTPException(status_code=409, detail=str(e))

    lesson_mapping = mapping[decision.lesson_id]
    runner = _get_runner()
    gen_request = GenerationRequest(
        target_difficulty=decision.target_difficulty,
        problem_form=decision.problem_form,
        lesson_id=decision.lesson_id,
        unlearned_lesson_ids=[],
    )
    try:
        result = runner.run(gen_request, lesson_mapping)
    except MongeneError as e:
        raise HTTPException(status_code=500, detail=f"問題生成に失敗: {e}")

    # メタデータ整形のため合成リクエストを使って既存ビルダを再利用
    synthetic_request = ProblemGenerationRequest(
        curriculum=CurriculumInput(grade=student.grade, lesson_ids=[decision.lesson_id]),
        problem_form=decision.problem_form,
        target_difficulty=decision.target_difficulty,
    )
    response = _build_response(result, synthetic_request, lesson_mapping)

    problem_id = uuid.uuid4().hex
    sub_q_records: List[Dict[str, Any]] = [
        {
            "label": sq.label,
            "prompt_text": sq.prompt_text,
            "type": sq.answer.type,
            "sympy_form": sq.answer.sympy_form,
            "text_form": sq.answer.text_form,
            "max_score": _DEFAULT_MAX_SCORE,
        }
        for sq in response.sub_questions
    ]
    store.save_problem(
        ProblemRecord(
            id=problem_id,
            student_id=student.id,
            lesson_ids=[decision.lesson_id],
            problem_form=decision.problem_form,
            target_difficulty=decision.target_difficulty,
            base_difficulty=response.metadata.base_difficulty,
            seed=response.metadata.seed,
            blueprint_id=response.metadata.blueprint_id,
            blueprint_version=response.metadata.blueprint_version,
            sub_questions=sub_q_records,
        )
    )

    return NextResponse(
        problem_id=problem_id,
        lesson_id=decision.lesson_id,
        lesson_title=decision.lesson_title,
        large_unit=decision.large_unit,
        target_difficulty=decision.target_difficulty,
        rationale=decision.rationale,
        problem=response,
        mastery=_snapshot(decision.mastery),
    )


@router.get("/path/{student_id}", response_model=PathResponse)
def learning_path(student_id: str, limit: int = 8) -> PathResponse:
    """前提グラフが導く『次に出題され得る単元』の予定（学習パス）を返す。

    完全習得で前提を満たした未習得フロンティアを教科書順に並べたもの。
    グラフが出題順を支配していることを可視化するための read-only エンドポイント。
    """
    store = get_store()
    student = store.get_student(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"未登録の student_id: {student_id}")
    mapping = get_mapping()
    graph = get_graph()
    upcoming = candidate_lessons(student, store, graph, mapping)[: max(0, limit)]
    return PathResponse(
        student_id=student_id,
        upcoming=[
            PathItem(
                lesson_id=lid,
                title=mapping[lid].get("title", lid),
                large_unit=mapping[lid].get("large_unit", ""),
                grade=int(mapping[lid].get("grade", student.grade)),
            )
            for lid in upcoming
        ],
    )


# ── /learning/submit ────────────────────────────────────────
@router.post("/submit", response_model=SubmitResponse)
def submit_answers(req: SubmitRequest) -> SubmitResponse:
    store = get_store()
    student = store.get_student(req.student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"未登録の student_id: {req.student_id}")
    problem = store.get_problem(req.problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail=f"未登録の problem_id: {req.problem_id}")
    if problem.student_id != student.id:
        raise HTTPException(status_code=403, detail="この問題は別の生徒のものです")

    lesson_id = problem.lesson_ids[0]
    answers_by_label = {a.label: a.answer for a in req.answers}

    results: List[QuestionResult] = []
    gradable_flags: List[bool] = []
    normalized: List[Dict[str, Any]] = []

    for sq in problem.sub_questions:
        label = sq["label"]
        expected = sq.get("sympy_form")
        atype = sq.get("type", "numeric")
        student_ans = answers_by_label.get(label)
        outcome = grade_answer(expected, student_ans, atype)

        score = sq.get("max_score", _DEFAULT_MAX_SCORE) if outcome.is_correct else 0
        store.record_attempt(
            Attempt(
                id=uuid.uuid4().hex,
                student_id=student.id,
                problem_id=problem.id,
                lesson_id=lesson_id,
                problem_form=problem.problem_form,
                seed=problem.seed,
                blueprint_id=problem.blueprint_id,
                blueprint_version=problem.blueprint_version,
                sympy_form=expected,
                student_answer=student_ans,
                is_correct=outcome.is_correct,
                score=score,
                max_score=sq.get("max_score", _DEFAULT_MAX_SCORE),
                error_type=outcome.error_type,
                route="auto",
            )
        )
        results.append(
            QuestionResult(
                label=label,
                gradable=outcome.gradable,
                is_correct=outcome.is_correct,
                error_type=outcome.error_type,
                expected=sq.get("text_form") or expected,
                student_answer=student_ans,
            )
        )
        normalized.append(
            {
                "lesson_id": lesson_id,
                "label": label,
                "is_correct": outcome.is_correct,
                "score": score,
                "max_score": sq.get("max_score", _DEFAULT_MAX_SCORE),
                "error_type": outcome.error_type,
            }
        )
        if outcome.gradable:
            gradable_flags.append(outcome.is_correct)

    # 1 問 = 1 習熟観測（自動採点可能な小問が全て正解なら正答）
    state = store.get_mastery(student.id, lesson_id)
    overall_correct: Optional[bool] = None
    if gradable_flags:
        overall_correct = all(gradable_flags)
        update_mastery(state, overall_correct)
        store.upsert_mastery(state)

    store.record_grading_event(
        GradingEvent(
            id=uuid.uuid4().hex,
            student_id=student.id,
            problem_id=problem.id,
            route="auto",
            raw_result={"answers": answers_by_label},
            normalized=normalized,
        )
    )

    return SubmitResponse(
        problem_id=problem.id,
        lesson_id=lesson_id,
        results=results,
        overall_correct=overall_correct,
        route_b_needed=overall_correct is None,  # 自動採点不能（proof 等）→ ScoGene(経路B) へ
        mastery=_snapshot(state),
        mastered=state.mastered,
    )
