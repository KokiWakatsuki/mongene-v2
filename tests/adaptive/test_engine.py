"""次手決定オーケストレーターのテスト（合成グラフ + 合成 mapping）。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from apps.api.src.core.adaptive.engine import NoLessonAvailableError, decide_next_lesson
from apps.api.src.core.curriculum.prerequisite_loader import PrerequisiteGraph
from apps.api.src.core.store.adaptive_store import AdaptiveStore
from apps.api.src.core.store.models import MasteryState, Student

# a -> b（b は a を要する）, c は別形式専用, d は中2
_NODES = [
    {"id": "a", "title": "A", "grade": 1, "requires": []},
    {"id": "b", "title": "B", "grade": 1, "requires": ["a"]},
    {"id": "c", "title": "C", "grade": 1, "requires": []},
    {"id": "d", "title": "D", "grade": 2, "requires": []},
]
_MAPPING = {
    "a": {"grade": 1, "title": "A", "supported_forms": ["calculation"], "y_base": 5, "raw_y_base": 150},
    "b": {"grade": 1, "title": "B", "supported_forms": ["calculation"], "y_base": 10, "raw_y_base": 300},
    "c": {"grade": 1, "title": "C", "supported_forms": ["proof"], "y_base": 8, "raw_y_base": 250},
    "d": {"grade": 2, "title": "D", "supported_forms": ["calculation"], "y_base": 12, "raw_y_base": 400},
}


@pytest.fixture()
def store() -> AdaptiveStore:
    db = Path(tempfile.mkdtemp()) / "engine_test.db"
    s = AdaptiveStore(db_path=str(db))
    yield s
    s.close()


def _graph() -> PrerequisiteGraph:
    return PrerequisiteGraph.from_nodes(_NODES)


def test_fresh_student_gets_shallow_calc_root(store: AdaptiveStore) -> None:
    student = Student(id="s1", grade=1)
    store.upsert_student(student)
    d = decide_next_lesson(student, store, _graph(), _MAPPING)
    # a はルートの calculation lesson。c は proof専用で除外、d は学年超過で除外
    assert d.lesson_id == "a"
    assert d.problem_form == "calculation"
    assert 1 <= d.target_difficulty <= 100
    assert "新規" in d.rationale


def test_skips_unsupported_form_and_higher_grade(store: AdaptiveStore) -> None:
    student = Student(id="s1", grade=1)
    store.upsert_student(student)
    # a を習得済みにする → 次は b（c=proof専用, d=中2 は候補外）
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="a", mastered=True, attempted=True))
    d = decide_next_lesson(student, store, _graph(), _MAPPING)
    assert d.lesson_id == "b"


def test_continues_in_progress_lesson(store: AdaptiveStore) -> None:
    student = Student(id="s1", grade=1)
    store.upsert_student(student)
    # a を着手済み(未習得) → 習得まで a を継続
    store.upsert_mastery(MasteryState(student_id="s1", lesson_id="a", attempted=True, mastered=False))
    d = decide_next_lesson(student, store, _graph(), _MAPPING)
    assert d.lesson_id == "a"
    assert "継続" in d.rationale


def test_no_lesson_available_when_all_mastered(store: AdaptiveStore) -> None:
    student = Student(id="s1", grade=1)
    store.upsert_student(student)
    for lid in ("a", "b"):
        store.upsert_mastery(MasteryState(student_id="s1", lesson_id=lid, mastered=True, attempted=True))
    with pytest.raises(NoLessonAvailableError):
        decide_next_lesson(student, store, _graph(), _MAPPING)
