"""カリキュラム構造（前提単元グラフ）の読み込みと探索。

個別最適化・完全習得学習ループの基盤層。`prerequisite_graph.yaml`（177 lesson の
DAG）をコードから初めて利用する。詳細は `docs/difficulty_adjustment/` および
提案システム設計（前提診断・単元シーケンシング）を参照。
"""
from __future__ import annotations

from apps.api.src.core.curriculum.prerequisite_loader import (
    PrerequisiteGraph,
    PrerequisiteGraphError,
    load_prerequisite_graph,
)

__all__ = [
    "PrerequisiteGraph",
    "PrerequisiteGraphError",
    "load_prerequisite_graph",
]
