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
        # check_same_thread=False で BackgroundTasks (別 thread) からのアクセスを許可
        # 競合は SQLite 内部のロックで自動シリアライズされる
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
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
        # problem_form と selected_tags を先頭に加えて
        # 異なるレッスン・難易度で同一数学答案が重複扱いにならないようにする
        components: list[str] = [mr.problem_form]
        # レッスン固有タグ（上位3件）をプレフィックスに含める
        components.extend(sorted(mr.selected_tags)[:3])

        if mr.problem_form == "proof":
            # 証明問題: operation_name + 合同/相似条件(operands[2]) + 頂点ラベル(proof_output) で判定
            import json as _json
            for sq in mr.sub_questions:
                for step in sq.logic_steps:
                    components.append(step.operation_name)
                    if len(step.operands) >= 3:
                        components.append(str(step.operands[2]))  # condition_set (SAS/SSS/etc.)
                    # proof_output JSON から to_prove を取得（頂点ラベルを含む）
                    for op in step.operands:
                        if isinstance(op, str) and op.startswith("{"):
                            try:
                                po = _json.loads(op)
                                tp = po.get("to_prove", "")
                                if tp:
                                    components.append(tp[:30])  # △ABC ≡ △DEF 等
                            except Exception:
                                pass
                            break
        else:
            for sq in mr.sub_questions:
                components.append(str(sq.answer.sympy_form))
                for step in sq.logic_steps:
                    components.append(str(step.sympy_expr))
                    # operands の先頭 2 件も含める（同答案でも式の形が違う問題を区別）
                    components.extend(str(o) for o in step.operands[:2])
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
