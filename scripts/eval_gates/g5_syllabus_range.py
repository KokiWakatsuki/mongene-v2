"""G5 範囲逸脱 (syllabus_range)

spec §3-G5:
- content_problem_text＋explanation が `master_data/forbidden_words.txt`（既存・353語）に
  該当したら FAIL。
- さらに `master_data/prerequisite_graph.yaml` を使い、当該 lesson の前提に含まれない
  未習単元の固有語彙が出たら FAIL（初期は用語ブロックリストで簡易実装、拡張余地あり）。

G3/G5 は誤判定を出さない方を優先（高精度・中再現率）。未習単元チェックは、
lesson が prerequisite_graph に存在し、かつ unlearned_lesson_ids が明示的に
渡されている場合のみ実施する（無ければ N/A 寄りにフォールバックし、過検知を避ける）。

LLM は使わない。
"""
from __future__ import annotations

from typing import Any

from scripts.eval_gates.common import GateResult, load_forbidden_words, load_prerequisite_graph

GATE_ID = "G5"

# 未習単元語彙ブロックリスト: lesson_id -> このlessonでは使ってはいけない固有語彙
# 初期実装は簡易的なもの。拡張余地は spec §3-G5 に明記されている。
_UNLEARNED_VOCAB_BLOCKLIST: dict[str, list[str]] = {
    # 例: 中1で「平方根」はまだ習っていない単元なので、正の数・負の数のレッスンに出たらおかしい
    "g1_l1": ["平方根", "二次方程式", "因数分解"],
    "g1_l2": ["平方根", "二次方程式", "因数分解"],
}


def _full_text(product: dict[str, Any]) -> str:
    content = product.get("content_problem_text", "") or ""
    explanations = [
        sq.get("explanation_text", "") or "" for sq in product.get("sub_questions", []) or []
    ]
    return "\n".join([content, *explanations])


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    text = _full_text(product)
    if not text.strip():
        return GateResult(GATE_ID, "N/A", "検査対象のテキストが空")

    forbidden_words = load_forbidden_words()
    hit_forbidden = [w for w in forbidden_words if w in text]
    if hit_forbidden:
        return GateResult(
            GATE_ID,
            "FAIL",
            f"禁止語彙が問題文/解説に出現: {hit_forbidden[:5]}",
            details={"forbidden_hits": hit_forbidden},
        )

    lesson_id = ground_truth.get("lesson_id")
    if lesson_id:
        graph = load_prerequisite_graph()
        node = graph.get(lesson_id)
        if node is not None:
            blocklist = _UNLEARNED_VOCAB_BLOCKLIST.get(lesson_id, [])
            hit_unlearned = [w for w in blocklist if w in text]
            if hit_unlearned:
                return GateResult(
                    GATE_ID,
                    "FAIL",
                    f"未習単元の固有語彙が出現: {hit_unlearned}",
                    details={"unlearned_hits": hit_unlearned, "lesson_id": lesson_id},
                )

    return GateResult(GATE_ID, "PASS", "禁止語彙・未習語彙は検出されなかった")
