"""前提単元グラフを生成する（§21.2, §16.5）

mapping.json の lesson 一覧 + キーワードベースの依存推論で DAG を構築する。
NetworkX で DAG 性を確認する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import networkx as nx
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
OUTPUT_PATH = REPO_ROOT / "master_data" / "prerequisite_graph.yaml"


# (lesson title regex, 前提となるタグ・キーワード)
# 「このトピックが出るなら、これらの前提タグを使う lesson が要る」
PREREQ_KEYWORDS: List[tuple[str, List[str]]] = [
    (r"三平方|ピタゴラス", ["平方根"]),
    (r"二次方程式|解の公式", ["平方根", "因数分解", "一次方程式"]),
    (r"連立方程式", ["一次方程式"]),
    (r"一次関数", ["比例", "座標"]),
    (r"二次関数|y=ax\^2|放物線", ["一次関数", "比例"]),
    (r"反比例", ["比例"]),
    (r"円周角", ["円", "中心角", "三角形"]),
    (r"展開|因数分解", ["多項式", "分配法則"]),
    (r"平方根", ["有理数", "整数"]),
    (r"標本調査|母集団", ["確率", "度数"]),
    (r"四分位|箱ひげ", ["度数", "中央値"]),
    (r"相似", ["合同"]),
    (r"作図", ["円", "直線"]),
    (r"動点|時間 t", ["一次関数", "面積"]),
    (r"くり抜|切断|展開図", ["体積", "表面積"]),
    (r"立体|空間.*図形", ["平面.*図形", "面積"]),
]


def build_graph(mapping: Dict) -> nx.DiGraph:
    g = nx.DiGraph()
    # 全 lesson をノード追加
    for lid, m in mapping.items():
        g.add_node(lid, title=m["title"], grade=m["grade"])

    # 学年内の前後順序を弱い前提として追加
    by_grade: Dict[int, List[tuple[int, str]]] = {}
    for lid, m in mapping.items():
        by_grade.setdefault(m["grade"], []).append((m["lesson_number"], lid))
    for grade, items in by_grade.items():
        items.sort()
        # 連続する lesson 間で前→後ろを依存とすると DAG が密になる
        # 代わりに large_unit 切替時に直前の lesson だけを前提にする
        prev_lu = None
        prev_lid = None
        for ln, lid in items:
            cur_lu = mapping[lid].get("large_unit")
            if prev_lid is not None and prev_lu == cur_lu:
                g.add_edge(lid, prev_lid)  # cur → 前提（prev）
            prev_lu = cur_lu
            prev_lid = lid

    # キーワードベースの追加依存
    title_index: Dict[str, List[str]] = {}
    for lid, m in mapping.items():
        for kw_pattern, _ in PREREQ_KEYWORDS:
            if re.search(kw_pattern, m["title"]) or re.search(kw_pattern, m.get("large_unit", "")):
                title_index.setdefault(kw_pattern, []).append(lid)

    for lid, m in mapping.items():
        text = f"{m.get('large_unit', '')} {m['title']}"
        for kw_pattern, prereq_keywords in PREREQ_KEYWORDS:
            if not re.search(kw_pattern, text):
                continue
            # この lesson は kw_pattern を扱う → prereq_keywords 系の lesson に依存
            for prereq_kw in prereq_keywords:
                for other_lid, other_m in mapping.items():
                    if other_lid == lid:
                        continue
                    if other_m["grade"] > m["grade"]:
                        continue
                    other_text = f"{other_m.get('large_unit', '')} {other_m['title']}"
                    if re.search(prereq_kw, other_text):
                        # サイクル防止: lid → other_lid を追加する前に
                        # other_lid から lid へ既に到達可能なら skip
                        if not nx.has_path(g, other_lid, lid):
                            g.add_edge(lid, other_lid)
                        break

    return g


def to_yaml_doc(g: nx.DiGraph, mapping: Dict) -> Dict:
    nodes = []
    for lid in sorted(g.nodes()):
        prereqs = sorted(g.successors(lid))
        nodes.append(
            {
                "id": lid,
                "title": mapping[lid]["title"],
                "grade": mapping[lid]["grade"],
                "requires": prereqs,
            }
        )
    return {"nodes": nodes}


def main() -> None:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    g = build_graph(mapping)
    assert nx.is_directed_acyclic_graph(g), "前提グラフが DAG ではない"
    doc = to_yaml_doc(g, mapping)
    OUTPUT_PATH.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"DAG nodes={g.number_of_nodes()} edges={g.number_of_edges()} -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
