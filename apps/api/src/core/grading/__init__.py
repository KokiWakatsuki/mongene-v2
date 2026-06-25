"""自動採点（経路A: SymPy による厳密照合）。

mongene が生成時に確定保持する `sympy_form`（正答）と生徒のデジタル入力を厳密比較する。
ScoGene（経路B: 手書きビジョン採点）を経由せず無料・即時・確定的に正誤を得る。
proof / set / graph 型は経路A対象外（経路Bへ回す）。
"""
from __future__ import annotations

from apps.api.src.core.grading.auto_grader import GradeOutcome, grade_answer

__all__ = ["GradeOutcome", "grade_answer"]
