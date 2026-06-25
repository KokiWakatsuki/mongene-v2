"""学習者状態の SQLite 永続化（`DuplicationGuard` と同じ接続スタイル）。

テーブル: students / student_mastery / problem / attempt / grading_event。
MVP 用の薄いリポジトリ。生成本体には一切依存しない（付加レイヤ）。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional, Set

from apps.api.src.core.store.models import (
    Attempt,
    GradingEvent,
    MasteryState,
    ProblemRecord,
    Student,
)

_DEFAULT_DB = "master_data/cache/adaptive.db"


class AdaptiveStore:
    def __init__(self, db_path: str = _DEFAULT_DB) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        # check_same_thread=False で BackgroundTasks（別 thread）からのアクセスを許可
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                external_id TEXT,
                grade INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS student_mastery (
                student_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                mastery REAL NOT NULL DEFAULT 0.0,
                attempted INTEGER NOT NULL DEFAULT 0,
                p_known REAL,
                theta REAL,
                recent_window TEXT NOT NULL DEFAULT '[]',
                correct_streak INTEGER NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                mastered INTEGER NOT NULL DEFAULT 0,
                last_seen TIMESTAMP,
                PRIMARY KEY (student_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS problem (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                lesson_ids TEXT NOT NULL,
                problem_form TEXT NOT NULL,
                target_difficulty INTEGER NOT NULL,
                base_difficulty INTEGER NOT NULL,
                seed INTEGER NOT NULL,
                blueprint_id TEXT NOT NULL,
                blueprint_version TEXT NOT NULL,
                sub_questions TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attempt (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL,
                problem_form TEXT NOT NULL,
                seed INTEGER NOT NULL,
                blueprint_id TEXT NOT NULL,
                blueprint_version TEXT NOT NULL,
                sympy_form TEXT,
                student_answer TEXT,
                is_correct INTEGER NOT NULL,
                score INTEGER NOT NULL,
                max_score INTEGER NOT NULL,
                error_type TEXT,
                route TEXT NOT NULL DEFAULT 'auto',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS grading_event (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                problem_id TEXT NOT NULL,
                route TEXT NOT NULL,
                raw_result TEXT NOT NULL DEFAULT '{}',
                normalized TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_mastery_student ON student_mastery(student_id);
            CREATE INDEX IF NOT EXISTS idx_attempt_student_lesson ON attempt(student_id, lesson_id);
            CREATE INDEX IF NOT EXISTS idx_problem_student ON problem(student_id);
            """
        )
        self.conn.commit()

    # ── students ─────────────────────────────────────────────
    def upsert_student(self, student: Student) -> None:
        self.conn.execute(
            """
            INSERT INTO students (id, external_id, grade) VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET external_id=excluded.external_id, grade=excluded.grade
            """,
            (student.id, student.external_id, student.grade),
        )
        self.conn.commit()

    def get_student(self, student_id: str) -> Optional[Student]:
        row = self.conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()
        if row is None:
            return None
        return Student(
            id=row["id"],
            grade=row["grade"],
            external_id=row["external_id"],
            created_at=row["created_at"],
        )

    def list_students(self) -> List[Student]:
        rows = self.conn.execute("SELECT * FROM students ORDER BY created_at").fetchall()
        return [
            Student(id=r["id"], grade=r["grade"], external_id=r["external_id"], created_at=r["created_at"])
            for r in rows
        ]

    # ── mastery ──────────────────────────────────────────────
    def upsert_mastery(self, state: MasteryState) -> None:
        self.conn.execute(
            """
            INSERT INTO student_mastery
                (student_id, lesson_id, mastery, attempted, p_known, theta,
                 recent_window, correct_streak, attempt_count, mastered, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(student_id, lesson_id) DO UPDATE SET
                mastery=excluded.mastery,
                attempted=excluded.attempted,
                p_known=excluded.p_known,
                theta=excluded.theta,
                recent_window=excluded.recent_window,
                correct_streak=excluded.correct_streak,
                attempt_count=excluded.attempt_count,
                mastered=excluded.mastered,
                last_seen=CURRENT_TIMESTAMP
            """,
            (
                state.student_id,
                state.lesson_id,
                state.mastery,
                int(state.attempted),
                state.p_known,
                state.theta,
                json.dumps(state.recent_window),
                state.correct_streak,
                state.attempt_count,
                int(state.mastered),
            ),
        )
        self.conn.commit()

    def get_mastery(self, student_id: str, lesson_id: str) -> MasteryState:
        """習熟状態を返す。未登録なら未出題(attempted=False)の既定値。"""
        row = self.conn.execute(
            "SELECT * FROM student_mastery WHERE student_id = ? AND lesson_id = ?",
            (student_id, lesson_id),
        ).fetchone()
        if row is None:
            return MasteryState(student_id=student_id, lesson_id=lesson_id)
        return self._row_to_mastery(row)

    def all_mastery(self, student_id: str) -> List[MasteryState]:
        rows = self.conn.execute(
            "SELECT * FROM student_mastery WHERE student_id = ? ORDER BY lesson_id",
            (student_id,),
        ).fetchall()
        return [self._row_to_mastery(r) for r in rows]

    def mastered_lesson_ids(self, student_id: str) -> Set[str]:
        rows = self.conn.execute(
            "SELECT lesson_id FROM student_mastery WHERE student_id = ? AND mastered = 1",
            (student_id,),
        ).fetchall()
        return {r["lesson_id"] for r in rows}

    @staticmethod
    def _row_to_mastery(row: sqlite3.Row) -> MasteryState:
        return MasteryState(
            student_id=row["student_id"],
            lesson_id=row["lesson_id"],
            mastery=row["mastery"],
            attempted=bool(row["attempted"]),
            p_known=row["p_known"],
            theta=row["theta"],
            recent_window=json.loads(row["recent_window"]),
            correct_streak=row["correct_streak"],
            attempt_count=row["attempt_count"],
            mastered=bool(row["mastered"]),
            last_seen=row["last_seen"],
        )

    # ── problem ──────────────────────────────────────────────
    def save_problem(self, problem: ProblemRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO problem
                (id, student_id, lesson_ids, problem_form, target_difficulty,
                 base_difficulty, seed, blueprint_id, blueprint_version, sub_questions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                problem.id,
                problem.student_id,
                json.dumps(problem.lesson_ids),
                problem.problem_form,
                problem.target_difficulty,
                problem.base_difficulty,
                problem.seed,
                problem.blueprint_id,
                problem.blueprint_version,
                json.dumps(problem.sub_questions, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def get_problem(self, problem_id: str) -> Optional[ProblemRecord]:
        row = self.conn.execute(
            "SELECT * FROM problem WHERE id = ?", (problem_id,)
        ).fetchone()
        if row is None:
            return None
        return ProblemRecord(
            id=row["id"],
            student_id=row["student_id"],
            lesson_ids=json.loads(row["lesson_ids"]),
            problem_form=row["problem_form"],
            target_difficulty=row["target_difficulty"],
            base_difficulty=row["base_difficulty"],
            seed=row["seed"],
            blueprint_id=row["blueprint_id"],
            blueprint_version=row["blueprint_version"],
            sub_questions=json.loads(row["sub_questions"]),
            created_at=row["created_at"],
        )

    # ── attempt ──────────────────────────────────────────────
    def record_attempt(self, attempt: Attempt) -> None:
        self.conn.execute(
            """
            INSERT INTO attempt
                (id, student_id, problem_id, lesson_id, problem_form, seed,
                 blueprint_id, blueprint_version, sympy_form, student_answer,
                 is_correct, score, max_score, error_type, route)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.id,
                attempt.student_id,
                attempt.problem_id,
                attempt.lesson_id,
                attempt.problem_form,
                attempt.seed,
                attempt.blueprint_id,
                attempt.blueprint_version,
                attempt.sympy_form,
                attempt.student_answer,
                int(attempt.is_correct),
                attempt.score,
                attempt.max_score,
                attempt.error_type,
                attempt.route,
            ),
        )
        self.conn.commit()

    def attempts_for(self, student_id: str, lesson_id: str) -> List[Attempt]:
        rows = self.conn.execute(
            "SELECT * FROM attempt WHERE student_id = ? AND lesson_id = ? ORDER BY created_at",
            (student_id, lesson_id),
        ).fetchall()
        return [self._row_to_attempt(r) for r in rows]

    @staticmethod
    def _row_to_attempt(row: sqlite3.Row) -> Attempt:
        return Attempt(
            id=row["id"],
            student_id=row["student_id"],
            problem_id=row["problem_id"],
            lesson_id=row["lesson_id"],
            problem_form=row["problem_form"],
            seed=row["seed"],
            blueprint_id=row["blueprint_id"],
            blueprint_version=row["blueprint_version"],
            sympy_form=row["sympy_form"],
            student_answer=row["student_answer"],
            is_correct=bool(row["is_correct"]),
            score=row["score"],
            max_score=row["max_score"],
            error_type=row["error_type"],
            route=row["route"],
            created_at=row["created_at"],
        )

    # ── grading_event ────────────────────────────────────────
    def record_grading_event(self, event: GradingEvent) -> None:
        self.conn.execute(
            """
            INSERT INTO grading_event (id, student_id, problem_id, route, raw_result, normalized)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING
            """,
            (
                event.id,
                event.student_id,
                event.problem_id,
                event.route,
                json.dumps(event.raw_result, ensure_ascii=False),
                json.dumps(event.normalized, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    # ── lifecycle ────────────────────────────────────────────
    def reset(self) -> None:
        self.conn.executescript(
            "DELETE FROM students; DELETE FROM student_mastery; "
            "DELETE FROM problem; DELETE FROM attempt; DELETE FROM grading_event;"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
