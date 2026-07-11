"""検証ゲートの枠組み（実装設計 §5・§8.2）。

`run_gates(obj, ctx, stage)` が `registry.gates(stage)` を登録順に実行し、
最初の失敗で `GateFailure` を投げる。generate() はこれを捕捉して
`Unsupported(verification_exhausted)` に変換する。

本ファイルはゲートの *枠組み* と、枠組みが機能することを示す最小ゲート
`G-SCHEMA`（mr 段: 全小問に concept_tags 非空・answer 非None）を1つ登録する。
フル Q ゲート（G-SIG/G-FP/G-Q1/G-Q2/G-Q7/G-Q5t/G-GND/G-T3/G-Q5v/G-STY）は
Task6 が本体を追加する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from engine.core.registry import REGISTRY, _Registry, register_gate

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


class GateFailure(Exception):
    """ゲート失敗（run_gates が投げる。generate が捕捉し Unsupported 化する）。"""

    def __init__(self, gate_name: str, detail: str) -> None:
        self.gate_name = gate_name
        self.detail = detail
        super().__init__(f"gate {gate_name} failed: {detail}")


def run_gates(obj: object, ctx: "CellContext", stage: str, *, registry: _Registry = REGISTRY) -> None:
    """`registry.gates(stage)` を登録順に実行する。最初の失敗で GateFailure を投げる。

    全ゲート通過時は何も返さない（None）。
    """
    for name, fn in registry.gates(stage):
        ok, detail = fn(obj, ctx)
        if not ok:
            raise GateFailure(name, detail)


# ---------------------------------------------------------------------------
# G-SCHEMA（mr 段）: 枠組みが機能することを示す最小ゲート。
# 全小問について concept_tags が非空・answer が None でないことを検査する。
# ---------------------------------------------------------------------------
@register_gate("mr", "G-SCHEMA")
def _gate_schema(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    if not mr.sub_questions:
        return False, "sub_questions が空"
    for sq in mr.sub_questions:
        if not sq.concept_tags:
            return False, f"{sq.label}: concept_tags が空"
        if sq.answer is None:
            return False, f"{sq.label}: answer が None"
    return True, ""


__all__ = ["GateFailure", "run_gates"]
