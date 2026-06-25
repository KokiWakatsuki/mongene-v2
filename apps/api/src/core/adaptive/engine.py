"""次手決定オーケストレーター（前提グラフ + 習熟状態 → 次に出す問題の仕様）。

生成本体（/problems/generate）は呼ばず、生成リクエストの『仕様』だけを決める純粋ロジック。
副作用（DB 読み取り）は AdaptiveStore 経由で注入し、テスト可能に保つ。

MVP の制約:
  * problem_form は calculation のみ（自動採点が成立する numeric/expression 中心）。
  * 完全習得ゲート: 習得済み lesson の全前提を満たす『未習得フロンティア』から、
    進行中（attempted・未習得）を優先して継続、無ければ最浅の新規 lesson を選ぶ。
  * grade <= 生徒の学年 でフィルタ（先取りしない）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from apps.api.src.core.adaptive.ability_mapping import target_difficulty_for
from apps.api.src.core.curriculum.prerequisite_loader import PrerequisiteGraph
from apps.api.src.core.store.adaptive_store import AdaptiveStore
from apps.api.src.core.store.models import MasteryState, Student


class NoLessonAvailableError(Exception):
    """出題可能な lesson が無い（全習得 or 形式非対応）。"""


@dataclass
class NextDecision:
    lesson_id: str
    lesson_title: str
    grade: int
    problem_form: str
    target_difficulty: int
    mastery: MasteryState
    rationale: str


def decide_next_lesson(
    student: Student,
    store: AdaptiveStore,
    graph: PrerequisiteGraph,
    mapping: Dict[str, Any],
    *,
    problem_form: str = "calculation",
) -> NextDecision:
    mastered = store.mastered_lesson_ids(student.id)
    frontier = graph.frontier(mastered)  # トポロジカル順（浅い順）

    candidates = [
        lid
        for lid in frontier
        if lid in mapping
        and problem_form in mapping[lid].get("supported_forms", [])
        and mapping[lid].get("grade", 99) <= student.grade
    ]
    if not candidates:
        raise NoLessonAvailableError(
            f"student={student.id} grade={student.grade} form={problem_form}: "
            "出題可能な未習得 lesson がありません（全習得 または 形式非対応）"
        )

    # 進行中（attempted かつ未習得）を優先して継続、無ければ最浅の新規 lesson
    in_progress = [lid for lid in candidates if store.get_mastery(student.id, lid).attempted]
    lesson_id = in_progress[0] if in_progress else candidates[0]

    m = mapping[lesson_id]
    state = store.get_mastery(student.id, lesson_id)
    target = target_difficulty_for(
        y_base=int(m["y_base"]),
        raw_y_base=int(m.get("raw_y_base", m["y_base"])),
        problem_form=problem_form,
        state=state,
    )
    rationale = "継続学習（習得まで反復）" if state.attempted else "新規単元（前提を満たす最浅フロンティア）"
    return NextDecision(
        lesson_id=lesson_id,
        lesson_title=m.get("title", lesson_id),
        grade=int(m.get("grade", student.grade)),
        problem_form=problem_form,
        target_difficulty=target,
        mastery=state,
        rationale=rationale,
    )
