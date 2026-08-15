"""Task3: curriculum ローダと curriculum_lint のテスト。"""
from __future__ import annotations

import dataclasses

import pytest

from engine.core.curriculum import (
    Concept,
    CurriculumModel,
    ErrorCause,
    PrereqEdge,
    Remediation,
    lint_curriculum,
    load_curriculum,
)


@pytest.fixture(scope="module")
def model() -> CurriculumModel:
    return load_curriculum()


def test_all_184_units_loaded(model: CurriculumModel):
    # input_spec の 184 レッスン + exam レッスンが載る
    assert len(model.units) >= 184
    assert model.has_unit("g2_l25")
    assert model.has_unit("g2_l24")
    assert model.has_unit("g1_l36")


def test_taxonomy_queries(model: CurriculumModel):
    assert model.has_form("g2_l25", "find_value")
    assert model.has_level("g2_l25", "find_value", 2)
    assert model.has_level("g2_l25", "find_value", 3)
    assert model.has_level("g2_l25", "graph_table", 2)
    assert model.has_level("g2_l24", "find_value", 1)
    assert not model.has_level("g2_l25", "find_value", 1)  # 疎: Lv1 は無い
    assert not model.has_form("g2_l25", "proof")


def test_level_meta_has_desc_example(model: CurriculumModel):
    meta = model.level_meta("g2_l25", "find_value", 2)
    assert "desc" in meta and meta["desc"]
    assert "example" in meta and meta["example"]


def test_vertical_string_curriculum_is_clean(model: CurriculumModel):
    errors = lint_curriculum(model)
    assert errors == [], f"想定外の lint エラー: {errors}"


def test_gq7r_static_holds(model: CurriculumModel):
    """各要因の target_concepts が戻り先セルの単元概念に含まれる（G-Q7r の静的前提）。"""
    for cid, cause in model.error_causes.items():
        rem_unit_concepts = {c.id for c in model.concepts.values() if c.unit == cause.remediation.unit}
        for tc in cause.target_concepts:
            assert tc in model.concepts, f"{cid}: {tc} 未定義"
            # 戻り先単元が対象概念を扱う（概念の unit と remediation.unit が一致）
            assert model.concepts[tc].unit == cause.remediation.unit, (
                f"{cid}: 対象概念 {tc} の単元と戻り先単元が不一致")
        assert rem_unit_concepts  # 戻り先単元に概念が定義されている


def test_curriculum_view(model: CurriculumModel):
    view = model.curriculum_view("g2_l25")
    assert "linear_function.expression_from_two_points" in view["unit_concepts"]
    assert "graph.read_lattice_points" in view["unit_concepts"]
    assert view["cause_ids"]


# --- lint の各規則の fail テスト（合成モデル）---
def _base_model() -> CurriculumModel:
    return CurriculumModel(
        units={"u1": {"forms": {"find_value": {"levels": {"1": {"desc": "d"}}}}}},
        concepts={"c1": Concept("c1", "l", "u1")},
        error_causes={},
        prerequisites=[],
    )


def test_lint_c1_missing_unit():
    m = _base_model()
    m.concepts["c2"] = Concept("c2", "l", "nope")
    errs = lint_curriculum(m)
    assert any(e.rule == "C1" for e in errs)


def test_lint_c2_missing_target_concept():
    m = _base_model()
    m.error_causes["x"] = ErrorCause("x", "l", ("ghost",), Remediation("u1", "find_value", 1))
    errs = lint_curriculum(m)
    assert any(e.rule == "C2" for e in errs)


def test_lint_c3_missing_remediation_coord():
    m = _base_model()
    m.error_causes["x"] = ErrorCause("x", "l", ("c1",), Remediation("u1", "find_value", 9))
    errs = lint_curriculum(m)
    assert any(e.rule == "C3" for e in errs)


def test_lint_c5_cycle_detected():
    m = _base_model()
    m.units["u2"] = {"forms": {}}
    m.prerequisites = [PrereqEdge("u1", "u2"), PrereqEdge("u2", "u1")]
    errs = lint_curriculum(m)
    assert any(e.rule == "C5" for e in errs)


def test_dataclasses_are_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Concept("a", "b", "c").id = "x"  # type: ignore[misc]
