"""問題重複排除機構（§12.6）"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.api.src.core.representation.middle_representation import MiddleRepresentation


class DuplicationGuard:
    def __init__(self, db_path: str = "master_data/cache/dedup.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_problems (
                hash TEXT PRIMARY KEY,
                lesson_id TEXT,
                blueprint_id TEXT,
                seed INTEGER,
                problem_text_preview TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def compute_hash(self, mr: "MiddleRepresentation") -> str:
        # §12.6 ハッシュ粒度の分岐
        # - 証明問題: logic_steps の operation_name 列で判定（言い回し違いを別問題扱い）
        # - 計算/文章題: answer + logic_steps の sympy_expr で判定
        components: list[str] = []
        if mr.problem_form == "proof":
            for sq in mr.sub_questions:
                for step in sq.logic_steps:
                    components.append(step.operation_name)
        else:
            for sq in mr.sub_questions:
                components.append(str(sq.answer.sympy_form))
                for step in sq.logic_steps:
                    components.append(str(step.sympy_expr))
        return hashlib.sha256("|".join(components).encode()).hexdigest()

    def is_duplicate(self, mr: "MiddleRepresentation") -> bool:
        h = self.compute_hash(mr)
        row = self.conn.execute(
            "SELECT 1 FROM generated_problems WHERE hash = ?", (h,)
        ).fetchone()
        return row is not None

    def register(self, mr: "MiddleRepresentation", problem_text: str) -> None:
        h = self.compute_hash(mr)
        self.conn.execute(
            "INSERT OR IGNORE INTO generated_problems (hash, lesson_id, blueprint_id, seed, problem_text_preview) VALUES (?, ?, ?, ?, ?)",
            (h, mr.blueprint_id, mr.blueprint_id, mr.seed, problem_text[:200]),
        )
        self.conn.commit()

    def reset(self) -> None:
        self.conn.execute("DELETE FROM generated_problems")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
