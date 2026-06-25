"""前提単元グラフ（`master_data/prerequisite_graph.yaml`）のローダーと探索ユーティリティ。

このグラフは 177 lesson を `requires`（前提 lesson のリスト）で結んだ DAG であり、
完全習得学習における「次に出すべき単元の選定」と「誤答時の前提診断（根本原因の単元欠損）」
の土台になる。これまでコードからは一度も読まれていなかった（死蔵データ）ため、本モジュールが
初めての正規ローダーとなる。

エッジの向き
------------
学習順の方向（前提 → それを必要とする lesson）で有向グラフを構築する。すなわち
lesson L の `requires: [p1, p2]` に対して `p1 -> L`, `p2 -> L` のエッジを張る。これにより

  * ``predecessors(L)`` = L の直接の前提（= requires）
  * ``ancestors(L)``    = L の全ての（推移的）前提
  * ``out_degree(n)``   = n に依存する lesson 数（= 被参照度 / ハブ度）
  * ``topological_sort`` = 前提が先に来る学習順

が自然に得られる。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set

import networkx as nx
import yaml

# リポジトリルート（apps/api/src/core/curriculum/this_file → 6 つ上が repo root）
_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_GRAPH_PATH = _REPO_ROOT / "master_data" / "prerequisite_graph.yaml"
DEFAULT_MAPPING_PATH = _REPO_ROOT / "master_data" / "mapping.json"


class PrerequisiteGraphError(ValueError):
    """前提グラフの構造的不整合（dangling 参照・循環・mapping 不一致など）。"""


class PrerequisiteGraph:
    """前提単元 DAG のラッパー。生成判断には依存しない純粋なクエリ層。"""

    def __init__(self, graph: nx.DiGraph) -> None:
        self._g = graph

    # ── 基本情報 ──────────────────────────────────────────────
    @property
    def graph(self) -> nx.DiGraph:
        return self._g

    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def has(self, lesson_id: str) -> bool:
        return self._g.has_node(lesson_id)

    def lesson_ids(self) -> List[str]:
        return list(self._g.nodes)

    def title(self, lesson_id: str) -> str:
        return str(self._g.nodes[lesson_id].get("title", ""))

    def grade(self, lesson_id: str) -> Optional[int]:
        return self._g.nodes[lesson_id].get("grade")

    # ── 前提・依存の探索 ─────────────────────────────────────
    def prerequisites(self, lesson_id: str) -> List[str]:
        """直接の前提 lesson（= requires）。"""
        self._require_node(lesson_id)
        return sorted(self._g.predecessors(lesson_id))

    def all_prerequisites(self, lesson_id: str) -> Set[str]:
        """推移的に辿った全ての前提 lesson。"""
        self._require_node(lesson_id)
        return set(nx.ancestors(self._g, lesson_id))

    def dependents(self, lesson_id: str) -> List[str]:
        """この lesson を直接の前提とする lesson 群。"""
        self._require_node(lesson_id)
        return sorted(self._g.successors(lesson_id))

    def all_dependents(self, lesson_id: str) -> Set[str]:
        self._require_node(lesson_id)
        return set(nx.descendants(self._g, lesson_id))

    def dependency_count(self, lesson_id: str) -> int:
        """この lesson に依存する直接後続の数（被参照度・ハブ度）。

        前提診断で根本原因の優先度付けに使う（被参照が多い前提ほど重要）。
        """
        self._require_node(lesson_id)
        return self._g.out_degree(lesson_id)

    def roots(self) -> List[str]:
        """前提を持たない lesson（学習の起点）。"""
        return sorted(n for n in self._g.nodes if self._g.in_degree(n) == 0)

    def topological_order(self) -> List[str]:
        """前提が先に来る学習順（安定化のためタイブレークは lesson_id 昇順）。"""
        return list(nx.lexicographical_topological_sort(self._g))

    # ── 完全習得ループ向けクエリ ─────────────────────────────
    def frontier(self, mastered: Set[str]) -> List[str]:
        """『未習得かつ全前提を習得済み』の lesson 群（学習可能フロンティア）。

        完全習得学習で「次に出してよい単元」の候補。トポロジカル順（=浅い順）で返す。
        """
        result: List[str] = []
        for lesson_id in self.topological_order():
            if lesson_id in mastered:
                continue
            if all(p in mastered for p in self._g.predecessors(lesson_id)):
                result.append(lesson_id)
        return result

    def unmet_prerequisites(self, lesson_id: str, mastered: Set[str]) -> List[str]:
        """指定 lesson の直接前提のうち、まだ習得していないもの。"""
        return [p for p in self.prerequisites(lesson_id) if p not in mastered]

    # ── 内部 ─────────────────────────────────────────────────
    def _require_node(self, lesson_id: str) -> None:
        if not self._g.has_node(lesson_id):
            raise PrerequisiteGraphError(f"未登録の lesson_id: {lesson_id}")

    # ── 構築 ─────────────────────────────────────────────────
    @classmethod
    def from_nodes(cls, nodes: List[dict], *, validate: bool = True) -> "PrerequisiteGraph":
        g = nx.DiGraph()
        for node in nodes:
            node_id = node.get("id")
            if not node_id:
                raise PrerequisiteGraphError(f"id を持たないノード: {node!r}")
            g.add_node(node_id, title=node.get("title", ""), grade=node.get("grade"))
        # エッジは全ノード登録後に張る（前方参照対応）
        dangling: List[str] = []
        for node in nodes:
            node_id = node["id"]
            for prereq in node.get("requires") or []:
                if not g.has_node(prereq):
                    dangling.append(f"{node_id} -> {prereq}")
                    continue
                g.add_edge(prereq, node_id)
        graph = cls(g)
        if validate:
            graph._validate(dangling)
        return graph

    def _validate(self, dangling: List[str]) -> None:
        if dangling:
            raise PrerequisiteGraphError(
                f"存在しない前提 lesson を参照: {', '.join(dangling[:10])}"
                + (" ..." if len(dangling) > 10 else "")
            )
        if not nx.is_directed_acyclic_graph(self._g):
            cycle = nx.find_cycle(self._g)
            raise PrerequisiteGraphError(f"前提グラフが循環している: {cycle}")

    def assert_matches_mapping(self, mapping_lesson_ids: Set[str]) -> None:
        """mapping.json の lesson_id 集合と一致するか検証する。"""
        graph_ids = set(self._g.nodes)
        only_graph = graph_ids - mapping_lesson_ids
        only_mapping = mapping_lesson_ids - graph_ids
        if only_graph or only_mapping:
            raise PrerequisiteGraphError(
                "前提グラフと mapping.json の lesson_id が不一致: "
                f"graph のみ={sorted(only_graph)[:5]}, mapping のみ={sorted(only_mapping)[:5]}"
            )


def load_prerequisite_graph(
    graph_path: Optional[Path] = None,
    *,
    mapping_path: Optional[Path] = None,
    validate: bool = True,
) -> PrerequisiteGraph:
    """YAML から前提グラフをロードする。

    Parameters
    ----------
    graph_path:
        prerequisite_graph.yaml のパス（省略時は master_data の既定）。
    mapping_path:
        指定すると mapping.json の lesson_id 集合との一致も検証する。
    validate:
        dangling 参照・循環の検証を行うか。
    """
    path = graph_path or DEFAULT_GRAPH_PATH
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes") if isinstance(data, dict) else data
    if not nodes:
        raise PrerequisiteGraphError(f"前提グラフが空: {path}")
    graph = PrerequisiteGraph.from_nodes(nodes, validate=validate)

    if mapping_path is not None:
        import json

        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        graph.assert_matches_mapping(set(mapping.keys()))

    return graph


@lru_cache(maxsize=1)
def get_default_prerequisite_graph() -> PrerequisiteGraph:
    """既定パスから読み込んだ前提グラフのプロセス内シングルトン。

    mapping.json との一致も検証する（起動時に不整合を早期検出）。
    """
    return load_prerequisite_graph(mapping_path=DEFAULT_MAPPING_PATH)


def _mapping_lesson_ids(mapping_path: Optional[Path] = None) -> Set[str]:
    import json

    path = mapping_path or DEFAULT_MAPPING_PATH
    return set(json.loads(path.read_text(encoding="utf-8")).keys())
