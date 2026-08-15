"""マッピング JSON の自己検証（§28.3）

1. 全 177 lesson カバー
2. 前提グラフが DAG
3. mapping_seed.json と execute_blueprint が一致
4. 各 mapping が現存 Blueprint を参照している
5. supported_forms が空でない
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import networkx as nx
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CURRICULUM_PATH = REPO_ROOT / "master_data" / "curriculum_math.json"
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
SEED_PATH = REPO_ROOT / "master_data" / "mapping_seed.json"
GRAPH_PATH = REPO_ROOT / "master_data" / "prerequisite_graph.yaml"

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
VALID_FORMS = {"knowledge", "calculation", "visual", "word_problem", "proof"}


def enumerate_lesson_ids(curriculum: list) -> set[str]:
    grade_map = {"中学1年": 1, "中学2年": 2, "中学3年": 3}
    ids = set()
    for grade_entry in curriculum:
        g = grade_map[grade_entry["grade"]]
        for d in grade_entry["domains"]:
            for lu in d["large_units"]:
                for mu in lu["middle_units"]:
                    for su in mu["small_units"]:
                        ids.add(f"g{g}_l{su['lesson_number']}")
    return ids


def verify() -> List[str]:
    errors: List[str] = []
    curriculum = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    seed_raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    seed = {k: v for k, v in seed_raw.items() if not k.startswith("_") and isinstance(v, dict)}

    expected = enumerate_lesson_ids(curriculum)

    # 1. 全 lesson カバー
    missing = expected - set(mapping.keys())
    extra = set(mapping.keys()) - expected
    if missing:
        errors.append(f"[mapping] 未カバー: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        errors.append(f"[mapping] 余分なエントリ: {sorted(extra)[:10]}")

    # 2. seed との execute_blueprint 一致
    for sid, sdata in seed.items():
        if sid not in mapping:
            errors.append(f"[seed] {sid} が mapping に無い")
            continue
        if mapping[sid].get("execute_blueprint") != sdata.get("execute_blueprint"):
            errors.append(
                f"[seed] {sid} Blueprint 不一致: "
                f"seed={sdata.get('execute_blueprint')} vs gen={mapping[sid].get('execute_blueprint')}"
            )

    # 3. 全 mapping が有効な Blueprint を参照
    for lid, m in mapping.items():
        bp = m.get("execute_blueprint")
        if bp not in EXPECTED_BLUEPRINTS:
            errors.append(f"[blueprint] {lid} が未登録 Blueprint を参照: {bp}")
        if not m.get("supported_forms"):
            errors.append(f"[forms] {lid} の supported_forms が空")
        for f in m.get("supported_forms", []):
            if f not in VALID_FORMS:
                errors.append(f"[forms] {lid} に未定義の form: {f}")

    # 4. 前提グラフが DAG
    graph_doc = yaml.safe_load(GRAPH_PATH.read_text(encoding="utf-8"))
    g = nx.DiGraph()
    for node in graph_doc["nodes"]:
        g.add_node(node["id"])
    for node in graph_doc["nodes"]:
        for prereq in node.get("requires", []):
            g.add_edge(node["id"], prereq)
    if not nx.is_directed_acyclic_graph(g):
        cycles = list(nx.simple_cycles(g))
        errors.append(f"[graph] DAG ではない。サイクル例: {cycles[:3]}")

    # 5. 前提グラフのノードが mapping を全カバー
    graph_nodes = {n["id"] for n in graph_doc["nodes"]}
    if graph_nodes != set(mapping.keys()):
        diff = (graph_nodes - set(mapping.keys())) | (set(mapping.keys()) - graph_nodes)
        errors.append(f"[graph] mapping と node 集合がズレ: {sorted(diff)[:5]}")

    return errors


def main() -> None:
    errors = verify()
    if errors:
        print(f"検証失敗: {len(errors)} 件のエラー")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print("検証成功: マッピング 177 件 + 前提グラフ + seed 一致 OK")


if __name__ == "__main__":
    main()
