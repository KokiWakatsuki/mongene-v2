"""学習者状態 SQLite ストアのテスト。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from apps.api.src.core.store import (
    AdaptiveStore,
    Attempt,
    GradingEvent,
    MasteryState,
    ProblemRecord,
    Student,
)


@pytest.fixture()
def store() -> AdaptiveStore:
    db = Path(tempfile.mkdtemp()) / "adaptive_test.db"
    s = AdaptiveStore(db_path=str(db))
    yield s
    s.close()


def test_student_upsert_and_get(store: AdaptiveStore) -> None:
    assert store.get_student("s1") is None
    store.upsert_student(Student(id="s1", grade=3, external_id="ext-1"))
    got = store.get_student("s1")
    assert got is not None
    assert got.grade == 3 and got.external_id == "ext-1"
    # upsert で更新できる
    store.upsert_student(Student(id="s1", grade=2))
    assert store.get_student("s1").grade == 2
    assert len(store.list_students()) == 1


def test_mastery_default_when_absent(store: AdaptiveStore) -> None:
    m = store.get_mastery("s1", "g1_l1")
    assert m.attempted is False
    assert m.mastery == 0.0
    assert m.mastered is False
    assert m.recent_window == []


def test_mastery_upsert_roundtrip(store: AdaptiveStore) -> None:
    state = MasteryState(
        student_id="s1",
        lesson_id="g1_l5",
        mastery=0.8,
        attempted=True,
        recent_window=[True, False, True],
        correct_streak=2,
        attempt_count=3,
        mastered=False,
    )
    store.upsert_mastery(state)
    got = store.get_mastery("s1", "g1_l5")
    assert got.mastery == 0.8
    assert got.attempted is True
    assert got.recent_window == [True, False, True]
    assert got.correct_streak == 2
    assert got.attempt_count == 3
    assert got.last_seen is not None  # CURRENT_TIMESTAMP が入る


def test_mastery_update_existing(store: AdaptiveStore) -> None:
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="g1_l5", mastery=0.3))
    store.upsert_mastery(
        MasteryState(student_id="s1", lesson_id="g1_l5", mastery=0.9, mastered=True, attempted=True)
    )
    got = store.get_mastery("s1", "g1_l5")
    assert got.mastery == 0.9 and got.mastered is True


def test_mastered_lesson_ids_and_all_mastery(store: AdaptiveStore) -> None:
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="g1_l1", mastered=True, attempted=True))
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="g1_l2", mastered=False, attempted=True))
    store.upsert_mastery(MasteryState(student_id="s2", lesson_id="g1_l1", mastered=True))
    assert store.mastered_lesson_ids("s1") == {"g1_l1"}
    assert len(store.all_mastery("s1")) == 2


def test_problem_save_and_get(store: AdaptiveStore) -> None:
    p = ProblemRecord(
        id="p1",
        student_id="s1",
        lesson_ids=["g1_l5"],
        problem_form="calculation",
        target_difficulty=20,
        base_difficulty=10,
        seed=12345,
        blueprint_id="BasicCalculationStructure",
        blueprint_version="v1",
        sub_questions=[{"label": "(1)", "sympy_form": "x + 2", "max_score": 10}],
    )
    store.save_problem(p)
    got = store.get_problem("p1")
    assert got is not None
    assert got.lesson_ids == ["g1_l5"]
    assert got.seed == 12345
    assert got.sub_questions[0]["sympy_form"] == "x + 2"
    assert store.get_problem("missing") is None


def test_attempt_record_and_query(store: AdaptiveStore) -> None:
    store.record_attempt(
        Attempt(
            id="a1",
            student_id="s1",
            problem_id="p1",
            lesson_id="g1_l5",
            problem_form="calculation",
            seed=1,
            blueprint_id="BasicCalculationStructure",
            blueprint_version="v1",
            sympy_form="x + 2",
            student_answer="x+2",
            is_correct=True,
            score=10,
            max_score=10,
            route="auto",
        )
    )
    attempts = store.attempts_for("s1", "g1_l5")
    assert len(attempts) == 1
    assert attempts[0].is_correct is True
    assert attempts[0].route == "auto"
    assert store.attempts_for("s1", "g9_l99") == []


def test_grading_event_record(store: AdaptiveStore) -> None:
    store.record_grading_event(
        GradingEvent(
            id="ge1",
            student_id="s1",
            problem_id="p1",
            route="vision",
            raw_result={"total_score": 10},
            normalized=[{"lesson_id": "g1_l5", "is_correct": True, "score": 10, "max_score": 10}],
        )
    )
    # 同一 ID は冪等（二重投入で例外にならない）
    store.record_grading_event(
        GradingEvent(id="ge1", student_id="s1", problem_id="p1", route="vision")
    )
    row = store.conn.execute("SELECT COUNT(*) AS c FROM grading_event").fetchone()
    assert row["c"] == 1


def test_reset_clears_all(store: AdaptiveStore) -> None:
    store.upsert_student(Student(id="s1", grade=1))
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="g1_l1"))
    store.reset()
    assert store.get_student("s1") is None
    assert store.all_mastery("s1") == []
