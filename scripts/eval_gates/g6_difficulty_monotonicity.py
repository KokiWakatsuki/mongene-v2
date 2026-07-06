"""G6 難易度単調性 (difficulty_monotonicity)

spec §3-G6: product 不要・LLMゼロで走る唯一のゲート。
- ground truth の MR から難易度特徴ベクトルを算出（`difficulty_features.py`）。
- 合成難易度スコアを定義し、同一 (lesson, form) で min < mid < max の単調増加を検査。
  単調でなければ FAIL。

このゲートだけは他ゲートと違い、判定対象が「1問」ではなく「同一 (lesson, form) の
min/mid/max 3問」である。`run_gates.py` からは `check_monotonicity` を直接呼ぶ。

`check(product, ground_truth)` という共通シグネチャも用意するが、このゲートは
product を使わないため引数の product は無視し、ground_truth に
`{"min": {...}, "mid": {...}, "max": {...}}` の3キーを持たせて渡す運用とする
（spec §2a の契約 `check(product, ground_truth) -> GateResult` を満たしつつ、
実質は ground-truth-only である点を明記）。
"""
from __future__ import annotations

from typing import Any, Optional

from scripts.eval_gates.common import GateResult
from scripts.eval_gates.difficulty_features import compute_difficulty_features

GATE_ID = "G6"


def check_monotonicity(
    gt_min: dict[str, Any],
    gt_mid: dict[str, Any],
    gt_max: dict[str, Any],
) -> GateResult:
    """同一 (lesson, form) の min/mid/max ground truth 3問から難易度単調性を判定する。

    product は不要。LLMゼロで走る。
    """
    features_min = compute_difficulty_features(gt_min)
    features_mid = compute_difficulty_features(gt_mid)
    features_max = compute_difficulty_features(gt_max)

    score_min = features_min.composite_score()
    score_mid = features_mid.composite_score()
    score_max = features_max.composite_score()

    details = {
        "score_min": score_min,
        "score_mid": score_mid,
        "score_max": score_max,
        "features_min": features_min.to_dict(),
        "features_mid": features_mid.to_dict(),
        "features_max": features_max.to_dict(),
    }

    if score_min < score_mid < score_max:
        return GateResult(
            GATE_ID,
            "PASS",
            f"難易度スコアが単調増加: {score_min:.2f} < {score_mid:.2f} < {score_max:.2f}",
            details=details,
        )

    return GateResult(
        GATE_ID,
        "FAIL",
        f"難易度スコアが単調増加していない: min={score_min:.2f}, mid={score_mid:.2f}, max={score_max:.2f}",
        details=details,
    )


def check(product: Optional[dict[str, Any]], ground_truth: dict[str, Any]) -> GateResult:
    """§2a の共通契約 `check(product, ground_truth) -> GateResult` に合わせたラッパー。

    G6 は本質的に product 不要・3問（min/mid/max）比較のゲートなので、
    `ground_truth = {"min": ..., "mid": ..., "max": ...}` の形で渡すことを期待する。
    単一問しか渡されない場合（他ゲートと同じ呼び出し規約で誤って呼ばれた場合）は
    判定不能として N/A を返す。
    """
    if not all(k in ground_truth for k in ("min", "mid", "max")):
        return GateResult(
            GATE_ID,
            "N/A",
            "G6 は同一 (lesson, form) の min/mid/max 3問が必要。"
            " ground_truth に 'min'/'mid'/'max' キーで3問を渡すこと（check_monotonicity を直接使うのを推奨）。",
        )
    return check_monotonicity(ground_truth["min"], ground_truth["mid"], ground_truth["max"])
