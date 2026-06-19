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

    return {
        "BasicCalculationStructure": build_basic_calculation_blueprint,
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
    }


def load_blueprint(blueprint_id: str) -> BlueprintDefinition:
    builders = _builder_map()
    if blueprint_id not in builders:
        raise KeyError(f"未登録の Blueprint: {blueprint_id}")
    return builders[blueprint_id]()


def list_blueprints() -> list[str]:
    return sorted(_builder_map().keys())
