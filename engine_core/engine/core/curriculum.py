"""カリキュラムモデルのローダと curriculum_lint（Task3 / 実装設計 §3・§5.2・§8.1）。

カリキュラムモデル = 共有データ資産（単元タクソノミー・概念・誤答要因・前提DAG・fact）。
本モジュールは *データファイルを読む* だけで、`engine.packs` / `engine.curriculum` を
Python import しない（§3 依存規律。import-linter が検査するのは import であり、
YAML の読み込みは規律に反しない）。

正の分界（N-6）:
- units（タクソノミー）の正 = units.generated.yaml（変換生成・手編集禁止）。
- concepts / error_causes / prerequisites / facts の正 = 各手書き YAML。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "curriculum" / "math"


@dataclass(frozen=True)
class Concept:
    id: str
    label: str
    unit: str


@dataclass(frozen=True)
class Remediation:
    unit: str
    form: str
    level: int | None = None


@dataclass(frozen=True)
class ErrorCause:
    id: str
    label: str
    target_concepts: tuple[str, ...]
    remediation: Remediation


@dataclass(frozen=True)
class PrereqEdge:
    src: str
    dst: str


@dataclass(frozen=True)
class Fact:
    id: str
    statement: str
    truth: bool
    source_unit: str


@dataclass
class CurriculumModel:
    units: dict[str, Any]
    concepts: dict[str, Concept]
    error_causes: dict[str, ErrorCause]
    prerequisites: list[PrereqEdge]
    facts: dict[str, Fact] = field(default_factory=dict)

    # --- タクソノミー問い合わせ（resolve が使う）---
    def has_unit(self, unit: str) -> bool:
        return unit in self.units

    def has_form(self, unit: str, form: str) -> bool:
        return unit in self.units and form in self.units[unit].get("forms", {})

    def has_level(self, unit: str, form: str, level: int) -> bool:
        if not self.has_form(unit, form):
            return False
        return str(level) in self.units[unit]["forms"][form].get("levels", {})

    def level_meta(self, unit: str, form: str, level: int) -> dict[str, Any]:
        meta: dict[str, Any] = self.units[unit]["forms"][form]["levels"][str(level)]
        return meta

    # --- 概念・要因 ---
    def concept_ids(self) -> set[str]:
        return set(self.concepts.keys())

    def cause_ids(self) -> set[str]:
        return set(self.error_causes.keys())

    def get_cause(self, cause_id: str) -> ErrorCause | None:
        return self.error_causes.get(cause_id)

    def curriculum_view(self, unit: str) -> dict[str, Any]:
        """CellContext に載せる部分ビュー（そのセルが参照してよい概念・要因辞書）。"""
        return {
            "concept_ids": self.concept_ids(),
            "cause_ids": self.cause_ids(),
            "unit_concepts": {cid for cid, c in self.concepts.items() if c.unit == unit},
            # 概念の日本語名。**ヒントをここから作る**——解説の手順を写すのでなく、
            # 「この問題で使う考え方」を言う（`t1_template._build_hints`）。
            "concept_labels": {cid: c.label for cid, c in self.concepts.items() if c.label},
        }


def load_curriculum(directory: str | Path = _DEFAULT_DIR) -> CurriculumModel:
    d = Path(directory)
    units_doc = yaml.safe_load((d / "units.generated.yaml").read_text(encoding="utf-8"))
    concepts_doc = yaml.safe_load((d / "concepts.yaml").read_text(encoding="utf-8")) or {}
    causes_doc = yaml.safe_load((d / "error_causes.yaml").read_text(encoding="utf-8")) or {}
    prereq_doc = yaml.safe_load((d / "prerequisites.yaml").read_text(encoding="utf-8")) or {}
    facts_doc = yaml.safe_load((d / "facts.yaml").read_text(encoding="utf-8")) or {}

    concepts = {
        c["id"]: Concept(id=c["id"], label=c.get("label", ""), unit=c["unit"])
        for c in (concepts_doc.get("concepts") or [])
    }
    causes = {}
    for c in causes_doc.get("error_causes") or []:
        rem = c["remediation"]
        causes[c["id"]] = ErrorCause(
            id=c["id"], label=c.get("label", ""),
            target_concepts=tuple(c.get("target_concepts", [])),
            remediation=Remediation(unit=rem["unit"], form=rem["form"], level=rem.get("level")),
        )
    prereqs = [PrereqEdge(src=e["from"], dst=e["to"]) for e in (prereq_doc.get("prerequisites") or [])]
    facts = {
        f["id"]: Fact(id=f["id"], statement=f.get("statement", ""),
                      truth=bool(f.get("truth", True)), source_unit=f.get("source_unit", ""))
        for f in (facts_doc.get("facts") or [])
    }
    return CurriculumModel(units=units_doc.get("units", {}), concepts=concepts,
                           error_causes=causes, prerequisites=prereqs, facts=facts)


# ---------------------------------------------------------------------------
# curriculum_lint（§8.1）: 参照整合・DAG 非循環・G-Q7r 静的検査
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CurriculumLintError:
    rule: str
    message: str


def _find_cycle(edges: list[PrereqEdge]) -> list[str] | None:
    """有向グラフの循環を1つ検出（DFS）。"""
    graph: dict[str, list[str]] = {}
    for e in edges:
        graph.setdefault(e.src, []).append(e.dst)
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for nxt in graph.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                idx = stack.index(nxt)
                return stack[idx:] + [nxt]
            if color.get(nxt, WHITE) == WHITE:
                res = dfs(nxt)
                if res:
                    return res
        stack.pop()
        color[node] = BLACK
        return None

    for n in list(graph.keys()):
        if color.get(n, WHITE) == WHITE:
            res = dfs(n)
            if res:
                return res
    return None


def lint_curriculum(model: CurriculumModel) -> list[CurriculumLintError]:
    errors: list[CurriculumLintError] = []

    # C1: concept.unit が units に実在
    for cid, c in model.concepts.items():
        if not model.has_unit(c.unit):
            errors.append(CurriculumLintError("C1", f"concept {cid}: 単元 {c.unit} が存在しない"))

    # C2: error_cause.target_concepts が concepts に実在
    for cid, cause in model.error_causes.items():
        for tc in cause.target_concepts:
            if tc not in model.concepts:
                errors.append(CurriculumLintError("C2", f"cause {cid}: 概念 {tc} が存在しない"))

    # C3: remediation 座標が units タクソノミーに実在
    for cid, cause in model.error_causes.items():
        rem = cause.remediation
        if rem.level is not None:
            if not model.has_level(rem.unit, rem.form, rem.level):
                errors.append(CurriculumLintError(
                    "C3", f"cause {cid}: 戻り先 {rem.unit}/{rem.form}/Lv{rem.level} が存在しない"))
        elif not model.has_form(rem.unit, rem.form):
            errors.append(CurriculumLintError(
                "C3", f"cause {cid}: 戻り先 {rem.unit}/{rem.form} が存在しない"))

    # C4: prerequisites の両端が units に実在
    for e in model.prerequisites:
        for endpoint in (e.src, e.dst):
            if not model.has_unit(endpoint):
                errors.append(CurriculumLintError("C4", f"prerequisite: 単元 {endpoint} が存在しない"))

    # C5: 前提 DAG が非循環
    cycle = _find_cycle(model.prerequisites)
    if cycle:
        errors.append(CurriculumLintError("C5", f"前提グラフに循環: {' -> '.join(cycle)}"))

    # C6: fact.source_unit が実在
    for fid, f in model.facts.items():
        if f.source_unit and not model.has_unit(f.source_unit):
            errors.append(CurriculumLintError("C6", f"fact {fid}: 単元 {f.source_unit} が存在しない"))

    return errors


__all__ = [
    "Concept", "Remediation", "ErrorCause", "PrereqEdge", "Fact",
    "CurriculumModel", "load_curriculum", "CurriculumLintError", "lint_curriculum",
]
