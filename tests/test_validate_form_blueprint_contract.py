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


def test_moving_point_g2_l29_calculation_violation_is_fixed() -> None:
    """g2_l29（動点の問題）はかつて calculation を宣言しながら候補が MovingPointStructure
    のみ、かつ MovingPointStructure が構造欠陥（CircleAtom混入・3小問同一答え）で凍結され
    calculation 未対応だったため honest 422 の契約違反だった。時間パラメトリックな
    MovingPointAreaVerb 実装で構造欠陥を解消し calc/visual を開通したため違反が消えたことを
    回帰検知する（§9 の凍結解除）。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g2_l29", "calculation") not in violation_keys
    assert ("g2_l29", "visual") not in violation_keys


def test_no_contract_violations_remain() -> None:
    """MovingPoint 凍結解除で凍結分を含む全契約違反が解消（違反 0）。
    新たに未対応 form を宣言すると検出器が拾って FAIL する回帰ガード。
    """
    result = validate_contract()
    assert result["violations"] == [], f"想定外の契約違反: {result['violations']}"


def test_g2_l16_calculation_violation_is_fixed() -> None:
    """g2_l16（個数と代金）はかつて calc を宣言しながら候補が WordProblemStructure のみで
    違反だった。calc を SimultaneousEquationsStructure に配線して解消。回帰を検知する。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g2_l16", "calculation") not in violation_keys


def test_g1_l30_visual_violation_is_fixed() -> None:
    """g1_l30(座標) はかつて visual を宣言しながら候補が BasicCalculationStructure
    のみで違反だった。CoordinatePlaneStructure(func_type=point)+ReadCoordinateVerb を
    実装し execute_blueprint_by_form.visual に配線して解消。回帰をこのテストで検知する。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g1_l30", "visual") not in violation_keys


def test_g2_l7_proof_violation_is_fixed() -> None:
    """g2_l7 はかつて proof を宣言しながら execute_blueprint が BasicCalculationStructure
    のみで proof をサポートせず違反だった（Opus のパイロット調査で実証済み）。
    代数証明capability パイロット(even_odd)で execute_blueprint_by_form.proof に
    AlgebraicProofStructure を配線し、この違反は解消された。回帰があればこのテストで検知する。
    """
    result = validate_contract()
    violation_keys = {(v["lesson_id"], v["form"]) for v in result["violations"]}
    assert ("g2_l7", "proof") not in violation_keys


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
