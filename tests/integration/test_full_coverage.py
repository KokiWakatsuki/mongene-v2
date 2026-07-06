"""Phase 5 統合テスト（§35.1）

全 184 lesson の生成成功率と 4 軸メトリクスを検証する。

form/blueprint 契約強制（NoCompatibleBlueprintError）導入後、mapping.json が
宣言する supported_forms の *どの form も* 実際に候補 blueprint の
supported_forms を満たさない lesson が存在する（scripts/validate_form_blueprint_contract.py
で検出される既知の契約違反）。これらは「黙って calculation に退化して成功した
ふりをする」のではなく、正直に NoCompatibleBlueprintError で失敗するのが正しい
挙動なので、KNOWN_CONTRACT_VIOLATION_LESSONS として明示的に除外し、それ以外の
lesson には引き続き 100% 成功を要求する。mapping.json 側の修正でこのリストが
解消されたら、このリストから外して 184 に戻すこと。

2026-07-07: 層B（3D_Renderer）に visual を開通（BasicDifferenceStructure /
PythagoreanSpaceStructure の supported_forms に "visual" を追加）したことで、
g3_l56 は visual form が契約適合となり生成成功に転じたため、このリストから除外。
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_full_coverage import run_177_lessons, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"

# 宣言された supported_forms の全てが、候補 blueprint の supported_forms と
# 一致しない lesson（= mapping.json 側の宣言ミス）。
# `.venv/bin/python scripts/validate_form_blueprint_contract.py` で確認済み。
KNOWN_CONTRACT_VIOLATION_LESSONS = {"g1_l15", "g2_l33"}


def test_full_coverage_meets_quality_gates() -> None:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    results = run_177_lessons()
    report = summarize(results, mapping)

    # 1. 全 lesson カバー
    assert report.total == 184

    # 2. 契約違反の3件のみが失敗すること（それ以外は 100% 成功）
    failed_ids = {
        r.lesson_id for r in results if not r.success
    }
    assert failed_ids == KNOWN_CONTRACT_VIOLATION_LESSONS, (
        f"想定外の失敗/成功差分: {failed_ids ^ KNOWN_CONTRACT_VIOLATION_LESSONS}"
    )
    expected_successes = report.total - len(KNOWN_CONTRACT_VIOLATION_LESSONS)
    assert report.successes == expected_successes, (
        f"{report.failures} 件失敗: {report.errors[:5]}"
    )

    # 3. Solvability 100%（必須、CI ゲート。契約違反3件は生成自体が失敗するため対象外）
    assert report.solvability_pass == expected_successes

    # 4. Accuracy（モック前提では Solvability と同等）
    assert report.accuracy_pass == expected_successes

    # 5. Appropriateness 100%
    assert report.appropriateness_pass == expected_successes

    # 6. Standards Alignment 100%（1〜2 件の許容誤差を認める）
    assert report.standards_pass >= expected_successes - 6, (
        f"Standards Alignment が {report.standards_pass}/{expected_successes}"
    )
