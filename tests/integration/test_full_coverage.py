"""Phase 5 統合テスト（§35.1）

全 177 lesson の生成成功率と 4 軸メトリクスを検証する。
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_full_coverage import run_177_lessons, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"


def test_full_coverage_meets_quality_gates() -> None:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    results = run_177_lessons()
    report = summarize(results, mapping)

    # 1. 全 lesson カバー
    assert report.total == 177

    # 2. 100% 成功率
    assert report.successes == 177, f"{report.failures} 件失敗: {report.errors[:5]}"

    # 3. Solvability 100%（必須、CI ゲート）
    assert report.solvability_pass == 177

    # 4. Accuracy（モック前提では Solvability と同等）
    assert report.accuracy_pass == 177

    # 5. Appropriateness 100%
    assert report.appropriateness_pass == 177

    # 6. Standards Alignment 100%（1〜2 件の許容誤差を認める）
    assert report.standards_pass >= 175, f"Standards Alignment が {report.standards_pass}/177"
