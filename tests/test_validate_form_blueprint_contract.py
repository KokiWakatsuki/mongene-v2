"""scripts/validate_form_blueprint_contract.py の軽いテスト（LLMフリー）。

このスクリプトは mapping.json 全件を走査し、宣言された supported_forms の
どの form も候補 blueprint の supported_forms を満たさない「静かなフォールバック」
違反ペアを検出する。CI を赤くしない可視化用ツールだが、検出ロジック自体は
BlueprintRunner.run() の契約強制と同じでなければ意味が無いため、既知の違反が
確実に検出されることを確認する。
"""
from __future__ import annotations

from scripts.validate_form_blueprint_contract import validate_contract


def test_validate_contract_returns_violation_list() -> None:
    result = validate_contract()
    assert isinstance(result["violations"], list)
    assert isinstance(result["total_declared"], int)
    assert isinstance(result["total_violations"], int)
    assert result["total_declared"] > 0
    assert result["total_violations"] == len(result["violations"])


def test_known_violation_g1_l30_visual_is_detected() -> None:
    """g1_l30 は mapping.supported_forms に visual を含むが、execute_blueprint は
    BasicCalculationStructure（supported_forms=["calculation"]）のみで visual を
    サポートしない。Opus のパイロット調査で実証済みの既知の違反。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g1_l30", "visual") in violation_keys


def test_known_violation_g2_l7_proof_is_detected() -> None:
    """g2_l7 は proof を宣言するが execute_blueprint は BasicCalculationStructure
    のみで proof をサポートしない。Opus のパイロット調査で実証済みの既知の違反。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g2_l7", "proof") in violation_keys


def test_by_form_breakdown_matches_violation_list() -> None:
    result = validate_contract()
    for form, stats in result["by_form"].items():
        actual = sum(1 for v in result["violations"] if v["form"] == form)
        assert stats["violations"] == actual, f"form={form} の集計が一致しない"


def test_knowledge_form_has_no_known_violations() -> None:
    """全走査時点（Opus調査）で knowledge form の違反は0件だった。
    回帰があればこのテストで検知する。
    """
    result = validate_contract()
    assert result["by_form"]["knowledge"]["violations"] == 0
