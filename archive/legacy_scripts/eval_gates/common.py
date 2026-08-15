"""評価ゲート共通ユーティリティ（数値正規化・GateResult 定義）。

フェーズ2仕様書 `docs/phase2_eval_gates_spec.md` §3 冒頭:
「数値の照合は正規化して行う（全角/半角、`−`/`-`、`1/2` と `\\dfrac{1}{2}`、
`\\left(` 等の LaTeX 装飾を除去してから比較）」を実装する。

数値正規化コアは app 層 `apps/api/src/core/evaluation/number_normalize.py` に移設し、
ここからは re-export する（オフライン評価とランタイム翻訳器で同一実装を共有＝
「evaluator = verifier」昇格・HANDOFF §4）。import パス `scripts.eval_gates.common`
は不変。

LLM は一切使わない。純粋な文字列処理のみ。
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

# 数値正規化コアは app 層に移設済み。既存ゲートの import 互換のため re-export する。
from apps.api.src.core.evaluation.number_normalize import (  # noqa: F401
    contains_number,
    dedupe_preserve_order,
    extract_numbers,
    normalize_math_text,
    numbers_equal,
)

Verdict = Literal["PASS", "FAIL", "WARN", "N/A"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LEXICON_PATH = REPO_ROOT / "master_data" / "eval_lexicons.yaml"
DEFAULT_FORBIDDEN_WORDS_PATH = REPO_ROOT / "master_data" / "forbidden_words.txt"
DEFAULT_PREREQUISITE_GRAPH_PATH = REPO_ROOT / "master_data" / "prerequisite_graph.yaml"


@functools.lru_cache(maxsize=8)
def _load_yaml_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_lexicons(path: Optional[Path] = None) -> dict[str, Any]:
    """`master_data/eval_lexicons.yaml` を読み込む（キャッシュ付き）。"""
    p = path or DEFAULT_LEXICON_PATH
    return _load_yaml_cached(str(p))


@functools.lru_cache(maxsize=8)
def load_forbidden_words(path: Optional[str] = None) -> tuple[str, ...]:
    p = Path(path) if path else DEFAULT_FORBIDDEN_WORDS_PATH
    if not p.exists():
        return tuple()
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return tuple(words)


@functools.lru_cache(maxsize=8)
def load_prerequisite_graph(path: Optional[str] = None) -> dict[str, dict[str, Any]]:
    """`prerequisite_graph.yaml` を lesson_id -> {title, grade, requires} の dict に変換。"""
    p = Path(path) if path else DEFAULT_PREREQUISITE_GRAPH_PATH
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    nodes = data.get("nodes", [])
    return {node["id"]: node for node in nodes if "id" in node}


@dataclass
class GateResult:
    """1ゲートの判定結果。

    `run_gates.py` から呼ぶときも、単体テストから呼ぶときも同じ形。
    """

    gate_id: str
    verdict: Verdict
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "details": self.details,
        }


# 数値正規化関数（normalize_math_text / extract_numbers / numbers_equal /
# contains_number / dedupe_preserve_order）は
# apps/api/src/core/evaluation/number_normalize.py に移設し、冒頭で re-export 済み。
