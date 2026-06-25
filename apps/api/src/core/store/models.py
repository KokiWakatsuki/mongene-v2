"""学習者状態の永続化レコード（データクラス）。

設計の要点（敵対的レビューの指摘を反映）:
  * MasteryState は ``attempted`` を持ち「未出題（初学）」と「未習得」を区別する。
    これを欠くと初学者の前提診断が常に最深ルート（g1_l1 等）に張り付く。
  * Attempt は ``seed`` + ``blueprint_id`` + ``blueprint_version`` を保存する。
    生成 seed は毎回変化するため、これらが無いと問題の再現・履歴突合・間隔反復ができない。
  * mastery 判定は「練習相（ZPD）」と「習得確認相（基準難易度）」を分離する想定で、
    recent_window / correct_streak は確認相の系列を保持する。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Student:
    id: str
    grade: int
    external_id: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class MasteryState:
    """生徒 × lesson の習熟状態。

    mastery: 0.0–1.0。MVP は確認相の直近正答率。後フェーズで BKT の p_known に差し替え可能。
    p_known / theta: BKT / IRT 用（MVP では None）。I/F を変えずに段階導入できる。
    """

    student_id: str
    lesson_id: str
    mastery: float = 0.0
    attempted: bool = False
    p_known: Optional[float] = None
    theta: Optional[float] = None
    recent_window: List[bool] = field(default_factory=list)
    correct_streak: int = 0
    attempt_count: int = 0
    mastered: bool = False
    last_seen: Optional[str] = None


@dataclass
class ProblemRecord:
    """mongene が生成した問題の永続化。採点結果を lesson に戻すための原本。

    1 問 1 lesson が基本だが、複合単元（unit_mix）拡張に備え lesson_ids は配列で保持する。
    sub_questions には label / prompt / answer.sympy_form / max_score を保存し、
    デジタル自動採点（経路 A）の照合に使う。
    """

    id: str
    student_id: str
    lesson_ids: List[str]
    problem_form: str
    target_difficulty: int
    base_difficulty: int
    seed: int
    blueprint_id: str
    blueprint_version: str
    sub_questions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None


@dataclass
class Attempt:
    """1 つの小問に対する 1 回の解答・採点結果。"""

    id: str
    student_id: str
    problem_id: str
    lesson_id: str
    problem_form: str
    seed: int
    blueprint_id: str
    blueprint_version: str
    sympy_form: Optional[str]
    student_answer: Optional[str]
    is_correct: bool
    score: int
    max_score: int
    error_type: Optional[str] = None
    route: str = "auto"  # "auto"（経路A: SymPy自動採点）/ "vision"（経路B: ScoGene）
    created_at: Optional[str] = None


@dataclass
class GradingEvent:
    """採点 1 回分のイベント（監査・再計算用に原データを丸ごと保持）。

    raw_result: ScoGene GradingResult もしくは auto_grader の生結果。
    normalized: per-question を {lesson_id, is_correct, score, max_score, error_type} に正規化したリスト。
    """

    id: str
    student_id: str
    problem_id: str
    route: str
    raw_result: Dict[str, Any] = field(default_factory=dict)
    normalized: List[Dict[str, Any]] = field(default_factory=list)
    created_at: Optional[str] = None
