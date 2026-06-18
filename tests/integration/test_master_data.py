"""Phase 4 マスターデータの自己検証テスト"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MASTER = REPO_ROOT / "master_data"


def _load_mapping() -> dict:
    return json.loads((MASTER / "mapping.json").read_text(encoding="utf-8"))


def _load_seed() -> dict:
    raw = json.loads((MASTER / "mapping_seed.json").read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}


def _load_curriculum() -> list:
    return json.loads((MASTER / "curriculum_math.json").read_text(encoding="utf-8"))


def _load_graph() -> dict:
    return yaml.safe_load((MASTER / "prerequisite_graph.yaml").read_text(encoding="utf-8"))


EXPECTED_BLUEPRINTS = {
    "BasicCalculationStructure",
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
}


def test_mapping_covers_all_177_lessons() -> None:
    mapping = _load_mapping()
    curriculum = _load_curriculum()
    grade_map = {"中学1年": 1, "中学2年": 2, "中学3年": 3}
    expected = set()
    for ge in curriculum:
        g = grade_map[ge["grade"]]
        for d in ge["domains"]:
            for lu in d["large_units"]:
                for mu in lu["middle_units"]:
                    for su in mu["small_units"]:
                        expected.add(f"g{g}_l{su['lesson_number']}")
    assert len(expected) == 177
    assert set(mapping.keys()) == expected


def test_mapping_references_only_known_blueprints() -> None:
    mapping = _load_mapping()
    for lid, m in mapping.items():
        assert m["execute_blueprint"] in EXPECTED_BLUEPRINTS, f"{lid}: {m['execute_blueprint']}"


def test_mapping_has_supported_forms() -> None:
    mapping = _load_mapping()
    for lid, m in mapping.items():
        assert m["supported_forms"], f"{lid} の supported_forms が空"


def test_seed_blueprints_match() -> None:
    mapping = _load_mapping()
    seed = _load_seed()
    for sid, sdata in seed.items():
        assert sid in mapping
        assert mapping[sid]["execute_blueprint"] == sdata["execute_blueprint"]


def test_prerequisite_graph_is_dag() -> None:
    doc = _load_graph()
    g = nx.DiGraph()
    for node in doc["nodes"]:
        g.add_node(node["id"])
    for node in doc["nodes"]:
        for prereq in node.get("requires", []):
            g.add_edge(node["id"], prereq)
    assert nx.is_directed_acyclic_graph(g)


def test_prerequisite_graph_covers_mapping() -> None:
    mapping = _load_mapping()
    doc = _load_graph()
    graph_ids = {n["id"] for n in doc["nodes"]}
    assert graph_ids == set(mapping.keys())


def test_scenarios_yaml_loads() -> None:
    data = yaml.safe_load((MASTER / "scenarios.yaml").read_text(encoding="utf-8"))
    assert len(data["scenarios"]) >= 10
    for s in data["scenarios"]:
        assert "id" in s
        assert "category" in s
        assert "applicable_lesson_ids" in s


def test_few_shot_seeds_are_valid_yaml() -> None:
    seeds_dir = MASTER / "few_shot_seeds"
    files = list(seeds_dir.glob("*.yaml"))
    assert files, "few_shot_seeds に YAML ファイルが無い"
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert "examples" in data
        assert isinstance(data["examples"], list)
