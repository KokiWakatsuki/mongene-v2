"""前提単元グラフ・ローダーのテスト。"""
from __future__ import annotations

import pytest

from apps.api.src.core.curriculum.prerequisite_loader import (
    DEFAULT_GRAPH_PATH,
    DEFAULT_MAPPING_PATH,
    PrerequisiteGraph,
    PrerequisiteGraphError,
    get_default_prerequisite_graph,
    load_prerequisite_graph,
    _mapping_lesson_ids,
)


# ── 合成グラフ（決定論的に振る舞いを検証） ──
#   a -> b -> c
#        a -> c   （a は b と c の前提。c は a,b を要する）
#   d は孤立ルート
_SAMPLE_NODES = [
    {"id": "a", "title": "A", "grade": 1, "requires": []},
    {"id": "b", "title": "B", "grade": 1, "requires": ["a"]},
    {"id": "c", "title": "C", "grade": 2, "requires": ["a", "b"]},
    {"id": "d", "title": "D", "grade": 1, "requires": []},
]


def _sample() -> PrerequisiteGraph:
    return PrerequisiteGraph.from_nodes(_SAMPLE_NODES)


def test_basic_size_and_membership() -> None:
    g = _sample()
    assert len(g) == 4
    assert g.has("a") and not g.has("zzz")
    assert g.title("c") == "C"
    assert g.grade("c") == 2


def test_prerequisites_and_dependents() -> None:
    g = _sample()
    assert g.prerequisites("c") == ["a", "b"]
    assert g.prerequisites("a") == []
    assert g.dependents("a") == ["b", "c"]
    assert g.all_prerequisites("c") == {"a", "b"}


def test_dependency_count_is_outdegree() -> None:
    g = _sample()
    # a は b,c の前提 → 被参照度 2、d は誰の前提でもない → 0
    assert g.dependency_count("a") == 2
    assert g.dependency_count("d") == 0


def test_roots_have_no_prerequisites() -> None:
    g = _sample()
    assert g.roots() == ["a", "d"]


def test_topological_order_respects_prerequisites() -> None:
    g = _sample()
    order = g.topological_order()
    assert order.index("a") < order.index("b") < order.index("c")


def test_frontier_advances_as_lessons_are_mastered() -> None:
    g = _sample()
    # 何も習得していない: 前提ゼロの a,d が候補
    assert g.frontier(set()) == ["a", "d"]
    # a を習得 → b がフロンティアに（c はまだ b 未習得で不可）
    assert g.frontier({"a"}) == ["b", "d"]
    # a,b 習得 → c が解放
    assert g.frontier({"a", "b"}) == ["c", "d"]


def test_unmet_prerequisites() -> None:
    g = _sample()
    assert g.unmet_prerequisites("c", {"a"}) == ["b"]
    assert g.unmet_prerequisites("c", {"a", "b"}) == []


def test_unknown_lesson_raises() -> None:
    g = _sample()
    with pytest.raises(PrerequisiteGraphError):
        g.prerequisites("zzz")


def test_dangling_reference_rejected() -> None:
    bad = [{"id": "x", "requires": ["nonexistent"]}]
    with pytest.raises(PrerequisiteGraphError, match="存在しない前提"):
        PrerequisiteGraph.from_nodes(bad)


def test_cycle_rejected() -> None:
    cyclic = [
        {"id": "p", "requires": ["q"]},
        {"id": "q", "requires": ["p"]},
    ]
    with pytest.raises(PrerequisiteGraphError, match="循環"):
        PrerequisiteGraph.from_nodes(cyclic)


def test_node_without_id_rejected() -> None:
    with pytest.raises(PrerequisiteGraphError):
        PrerequisiteGraph.from_nodes([{"title": "no id"}])


def test_assert_matches_mapping_detects_mismatch() -> None:
    g = _sample()
    with pytest.raises(PrerequisiteGraphError, match="不一致"):
        g.assert_matches_mapping({"a", "b"})  # c, d が欠落
    g.assert_matches_mapping({"a", "b", "c", "d"})  # 一致なら例外なし


# ── 実データ（master_data の本番グラフ） ──

def test_real_graph_loads_and_is_dag() -> None:
    g = load_prerequisite_graph()
    assert len(g) == 177
    # 全 lesson が DAG として整合（dangling/循環なし → 例外が出ない）
    assert len(g.topological_order()) == 177


def test_real_graph_matches_mapping() -> None:
    g = load_prerequisite_graph(mapping_path=DEFAULT_MAPPING_PATH)
    assert set(g.lesson_ids()) == _mapping_lesson_ids()


def test_real_graph_has_known_roots() -> None:
    g = load_prerequisite_graph()
    roots = g.roots()
    # g1_l1（符号のついた数）は前提を持たない起点のはず
    assert "g1_l1" in roots


def test_real_graph_frontier_from_scratch_is_roots() -> None:
    g = load_prerequisite_graph()
    assert set(g.frontier(set())) == set(g.roots())


def test_default_singleton_is_cached() -> None:
    a = get_default_prerequisite_graph()
    b = get_default_prerequisite_graph()
    assert a is b
    assert DEFAULT_GRAPH_PATH.exists()
