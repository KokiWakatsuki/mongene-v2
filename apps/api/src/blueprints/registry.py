"""Blueprint 統合レジストリ（Phase 3）

全 Blueprint を一元的に load する。
"""
from __future__ import annotations

from typing import Callable, Dict

from apps.api.src.core.abc.blueprint import BlueprintDefinition


def _builder_map() -> Dict[str, Callable[[], BlueprintDefinition]]:
    """各 Blueprint モジュールの build 関数を集約（遅延 import で循環参照を防ぐ）"""
    from apps.api.src.blueprints.angle_calculation import build_angle_calculation_blueprint
    from apps.api.src.blueprints.basic_calculation import build_basic_calculation_blueprint
    from apps.api.src.blueprints.basic_difference import build_basic_difference_blueprint
    from apps.api.src.blueprints.basic_geometry_measurement import (
        build_basic_geometry_measurement_blueprint,
    )
    from apps.api.src.blueprints.algebraic_proof import build_algebraic_proof_blueprint
    from apps.api.src.blueprints.construction import build_construction_blueprint
    from apps.api.src.blueprints.data_probability import build_data_probability_blueprint
    from apps.api.src.blueprints.function_geometry_fusion import (
        build_function_geometry_fusion_blueprint,
    )
    from apps.api.src.blueprints.moving_point import build_moving_point_blueprint
    from apps.api.src.blueprints.proof import build_proof_blueprint
    from apps.api.src.blueprints.sequence_pattern import build_sequence_pattern_blueprint
    from apps.api.src.blueprints.word_problem import build_word_problem_blueprint
    from apps.api.src.blueprints.pythagorean import (
        build_pythagorean_blueprint,
        build_pythagorean_space_blueprint,
    )
    from apps.api.src.blueprints.solve_equation import build_solve_equation_blueprint
    from apps.api.src.blueprints.descriptive_stats import build_descriptive_stats_blueprint
    from apps.api.src.blueprints.sample_survey import build_sample_survey_blueprint
    from apps.api.src.blueprints.factorize import build_factorize_blueprint
    from apps.api.src.blueprints.quadratic_function import build_quadratic_function_blueprint
    from apps.api.src.blueprints.simultaneous_equations import build_simultaneous_equations_blueprint
    from apps.api.src.blueprints.knowledge_base import build_knowledge_base_blueprint
    from apps.api.src.blueprints.word_problem_formulation import (
        build_word_problem_formulation_blueprint,
    )
    from apps.api.src.blueprints.contextual_calculation import (
        build_contextual_calculation_blueprint,
    )
    from apps.api.src.blueprints.coordinate_plane import build_coordinate_plane_blueprint
    from apps.api.src.blueprints.angle_proof import build_angle_proof_blueprint
    from apps.api.src.blueprints.congruence_figure import build_congruence_figure_blueprint

    return {
        "BasicCalculationStructure": build_basic_calculation_blueprint,
        "SolveEquationStructure": build_solve_equation_blueprint,
        "WordProblemStructure": build_word_problem_blueprint,
        "BasicGeometryMeasurementStructure": build_basic_geometry_measurement_blueprint,
        "BasicDifferenceStructure": build_basic_difference_blueprint,
        "FunctionGeometryFusionStructure": build_function_geometry_fusion_blueprint,
        "MovingPointStructure": build_moving_point_blueprint,
        "AngleCalculationStructure": build_angle_calculation_blueprint,
        "ConstructionStructure": build_construction_blueprint,
        "ProofStructure": build_proof_blueprint,
        "DataProbabilityStructure": build_data_probability_blueprint,
        "SequencePatternStructure": build_sequence_pattern_blueprint,
        "PythagoreanStructure": build_pythagorean_blueprint,
        "PythagoreanSpaceStructure": build_pythagorean_space_blueprint,
        "DescriptiveStatsStructure": build_descriptive_stats_blueprint,
        "SampleSurveyStructure": build_sample_survey_blueprint,
        "FactorizeStructure": build_factorize_blueprint,
        "QuadraticFunctionStructure": build_quadratic_function_blueprint,
        "SimultaneousEquationsStructure": build_simultaneous_equations_blueprint,
        "KnowledgeBaseStructure": build_knowledge_base_blueprint,
        "AlgebraicProofStructure": build_algebraic_proof_blueprint,
        "WordProblemFormulationStructure": build_word_problem_formulation_blueprint,
        "ContextualCalculationStructure": build_contextual_calculation_blueprint,
        "CoordinatePlaneStructure": build_coordinate_plane_blueprint,
        "AngleProofStructure": build_angle_proof_blueprint,
        "CongruenceFigureStructure": build_congruence_figure_blueprint,
    }


def load_blueprint(blueprint_id: str, params: dict | None = None) -> BlueprintDefinition:
    builders = _builder_map()
    if blueprint_id not in builders:
        raise KeyError(f"未登録の Blueprint: {blueprint_id}")
    return builders[blueprint_id](params=params or {})


def list_blueprints() -> list[str]:
    return sorted(_builder_map().keys())
