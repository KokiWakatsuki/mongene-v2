"""Phase 3 Blueprint レジストリと各 Blueprint の最低限テスト"""
from __future__ import annotations

from pathlib import Path

import pytest

# 各 Atom/Verb モジュールをインポートして registry を発火させる
from apps.api.src.atoms.noun import (  # noqa: F401
    circle_atom,
    data_set_atom,
    equation_atom,
    event_atom,
    line_angle_atom,
    linear_func_atom,
    moving_point_atom,
    number_atom,
    point_atom,
    polygon_atom,
    prism_atom,
    pyramid_atom,
    sequence_atom,
)
from apps.api.src.atoms.verb import (  # noqa: F401
    calculate_arithmetic_verb,
    calculate_probability_verb,
    construct_geometry_verb,
    cutout_verb,
    find_angle_verb,
    generalize_formula_verb,
    intersect_verb,
    measure_geometry_verb,
    prove_geometry_verb,
    solve_eq_verb,
)
from apps.api.src.blueprints.registry import list_blueprints, load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import (
    BlueprintRunner,
    GenerationRequest,
)

EXPECTED_BLUEPRINTS = {
    "BasicCalculationStructure",
    "SolveEquationStructure",
    "WordProblemStructure",
    "BasicGeometryMeasurementStructure",
    "BasicDifferenceStructure",
    "FunctionGeometryFusionStructure",
    "MovingPointStructure",
    "AngleCalculationStructure",
    "ConstructionStructure",
    "ProofStructure",
    "DataProbabilityStructure",
    "SequencePatternStructure",
    "PythagoreanStructure",
    "PythagoreanSpaceStructure",
    "DescriptiveStatsStructure",
    "SampleSurveyStructure",
    "FactorizeStructure",
    "QuadraticFunctionStructure",
    "SimultaneousEquationsStructure",
    "KnowledgeBaseStructure",
    "AlgebraicProofStructure",
    "WordProblemFormulationStructure",
    "ContextualCalculationStructure",
    "CoordinatePlaneStructure",
}


def test_all_blueprints_registered() -> None:
    registered = set(list_blueprints())
    assert registered == EXPECTED_BLUEPRINTS


@pytest.mark.parametrize("bp_id", sorted(EXPECTED_BLUEPRINTS))
def test_each_blueprint_loads(bp_id: str) -> None:
    bp = load_blueprint(bp_id)
    assert bp.blueprint_id == bp_id
    assert bp.blueprint_version.startswith("v")
    assert bp.noun_slots, f"{bp_id} に noun_slot が無い"
    assert bp.verb_invocations, f"{bp_id} に verb_invocation が無い"
    assert bp.supported_forms, f"{bp_id} に supported_forms が無い"


def _make_runner(tmp_db: Path) -> BlueprintRunner:
    dedup = DuplicationGuard(db_path=str(tmp_db))
    return BlueprintRunner(
        dedup=dedup,
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=30,
    )


def _mapping_for(blueprint_id: str, grade: int, y_base: int, form: str) -> dict:
    return {
        "target_lesson_id": "g1_l1",
        "title": "test",
        "grade": grade,
        "lesson_number": 1,
        "execute_blueprint": blueprint_id,
        "required_tags": [],
        "optional_tags": [],
        "atom_constraints": {
            "NumberAtom": {"max_value": 10},
            "EquationAtom": {"degree": 1, "max_coefficient": 5, "is_integer_solution": True},
            "PrismAtom": {"is_cube": False, "max_height": 10, "base_shape_type": "square"},
            "PyramidAtom": {"max_base_side": 2, "max_height": 2},
            "PolygonAtom": {"polygon_type": "triangle", "max_side_length": 5},
            "CircleAtom": {"is_sector": False, "max_radius": 5},
            "LinearFuncAtom": {"max_slope": 3},
            "LineAngleAtom": {"relation_type": "alternate"},
            "PointAtom": {"range_x": (-5, 5), "range_y": (-5, 5)},
            "EventAtom": {"event_type": "dice", "num_trials": 1},
            "SequenceAtom": {"pattern_type": "arithmetic"},
        },
        "visual_component": "NullRenderer",
        "y_base": y_base,
        "supported_forms": [form],
    }


def test_basic_calculation_runs(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=15, problem_form="calculation", lesson_id="g1_l5")
    result = runner.run(request, _mapping_for("BasicCalculationStructure", 1, 13, "calculation"))
    assert result.middle_representation.sub_questions


def test_word_problem_runs(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=30, problem_form="word_problem", lesson_id="g1_l25")
    result = runner.run(request, _mapping_for("WordProblemStructure", 1, 30, "word_problem"))
    assert result.middle_representation.sub_questions


def test_basic_geometry_measurement_runs(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=25, problem_form="calculation", lesson_id="g2_l10")
    result = runner.run(
        request, _mapping_for("BasicGeometryMeasurementStructure", 2, 25, "calculation")
    )
    assert result.middle_representation.sub_questions


def test_data_probability_runs(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=40, problem_form="calculation", lesson_id="g2_l50")
    result = runner.run(request, _mapping_for("DataProbabilityStructure", 2, 40, "calculation"))
    assert result.middle_representation.sub_questions


def test_sequence_pattern_runs(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=55, problem_form="calculation", lesson_id="g3_l30")
    result = runner.run(request, _mapping_for("SequencePatternStructure", 3, 55, "calculation"))
    assert result.middle_representation.sub_questions


def test_angle_calculation_runs(tmp_path: Path) -> None:
    # AngleCalculationStructure の supported_forms は Slice 3a（2026-07-07）で
    # ["calculation", "word_problem"] に是正済み（visual は builder 未対応の
    # ため Slice 3b まで追加しない）。ここでは word_problem 経路を引き続き検証する。
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(target_difficulty=45, problem_form="word_problem", lesson_id="g2_l40")
    result = runner.run(request, _mapping_for("AngleCalculationStructure", 2, 45, "word_problem"))
    assert result.middle_representation.sub_questions
