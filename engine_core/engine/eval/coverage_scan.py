"""coverage_scan（実装設計 §8.3・N-5・Task10）— 生成不能0・ゲート素通り0 の検証。

capabilities の全 base セル × S seeds を generate し、
  - **生成不能0**: どの (cell, seed) も Problem を返す（Unsupported が出ない）
  - **ゲート素通り0**: Problem を返した各段に登録ゲートが1つ以上存在した
    （run_gates は空リストなら自明通過するため、実際に検証が走ったことを保証する）
を検査する。あわせて remedial 対応表（全誤答要因）を走査し、送り先セルへ解決して
G-Q7r（戻り先 concept_tags ⊇ 要因 target_concepts）を通ることを固定する。

CLI: `python -m engine.eval.coverage_scan [--seeds N] [--json] [--out PATH]`
終了コード: 全合格=0 / 失敗あり=1（CI 連携。§8.4 nightly）。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.contracts import Problem
from engine.core.pipeline import generate
from engine.eval._parallel import pmap
from engine.eval._harness import (
    Coordinate,
    EvalEnv,
    cell_request,
    make_env,
    remedial_cases,
    remedial_request,
    unreferenced_causes,
    select_cells,
)

_DEFAULT_SEEDS = 5


@dataclass
class CellResult:
    cell: str
    seeds: int
    generated: int
    failures: list[dict[str, object]] = field(default_factory=list)
    passthrough_stages: list[str] = field(default_factory=list)  # ゲート0の段（素通り）

    @property
    def ok(self) -> bool:
        return not self.failures and not self.passthrough_stages


@dataclass
class RemedialResult:
    cause_id: str
    requesting: str
    resolved: str | None
    seeds: int
    generated: int
    q7r_ok: bool
    failures: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures and self.q7r_ok and self.generated == self.seeds


def _stage_gate_counts(env: EvalEnv) -> dict[str, int]:
    return {stage: len(env.registry.gates(stage)) for stage in ("mr", "text", "visual")}


def scan_cells(
    env: EvalEnv, seeds: int, *, jobs: int | None = None, only: str | None = None
) -> list[CellResult]:
    """セル単位で並列に走らせる（セルどうしは独立）。"""
    return pmap(_cell_job, [(c, seeds) for c in select_cells(env, only)], jobs=jobs)


def _cell_job(env: EvalEnv, coord: Coordinate, seeds: int) -> CellResult:
    """ワーカー1つが担当するセル1つ分（`_parallel.pmap` から呼ばれる）。"""
    gate_counts = _stage_gate_counts(env)
    res = CellResult(cell=f"{coord.unit}.{coord.form}.Lv{coord.level}", seeds=seeds, generated=0)
    uses_visual = False
    for seed in range(1, seeds + 1):
        problem = generate(
            cell_request(coord, seed),
            curriculum=env.curriculum,
            families=env.families,
            registry=env.registry,
        )
        if isinstance(problem, Problem):
            res.generated += 1
            if problem.visual_svg is not None:
                uses_visual = True
        else:
            res.failures.append({"seed": seed, "code": problem.code, "detail": problem.detail})
    # ゲート素通り検査: 実際に使われた段のゲートが 0 なら素通り（自明通過）。
    required_stages = ["mr", "text"] + (["visual"] if uses_visual else [])
    res.passthrough_stages = [s for s in required_stages if gate_counts[s] == 0]
    return res


def scan_remedial(env: EvalEnv, seeds: int) -> list[RemedialResult]:
    results: list[RemedialResult] = []
    for case in remedial_cases(env):
        req_label = f"{case.requesting.unit}.{case.requesting.form}.Lv{case.requesting.level}"
        res = RemedialResult(
            cause_id=case.cause_id, requesting=req_label, resolved=None,
            seeds=seeds, generated=0, q7r_ok=True,
        )
        for seed in range(1, seeds + 1):
            problem = generate(
                remedial_request(case, seed),
                curriculum=env.curriculum,
                families=env.families,
                registry=env.registry,
            )
            if not isinstance(problem, Problem):
                res.failures.append({"seed": seed, "code": problem.code, "detail": problem.detail})
                continue
            res.generated += 1
            rc = problem.meta.resolved
            res.resolved = f"{rc.unit}.{rc.form}.Lv{rc.level}"
            # G-Q7r: 戻り先セルの concept_tags が要因の target_concepts を被覆
            missing = [tc for tc in case.target_concepts if tc not in problem.meta.concept_tags]
            if missing:
                res.q7r_ok = False
                res.failures.append({"seed": seed, "q7r_missing_concepts": missing})
        results.append(res)
    return results


@dataclass
class CoverageReport:
    seeds: int
    cells: list[CellResult]
    remedial: list[RemedialResult]
    unreferenced_causes: list[str]
    gate_counts: dict[str, int]

    @property
    def ok(self) -> bool:
        return (
            all(c.ok for c in self.cells)
            and all(r.ok for r in self.remedial)
            and not self.unreferenced_causes
            and all(v > 0 for v in self.gate_counts.values())
        )

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "ok": self.ok,
            "gate_counts": self.gate_counts,
            "unreferenced_causes": self.unreferenced_causes,
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
            "remedial": [asdict(r) | {"ok": r.ok} for r in self.remedial],
        }


def run_coverage_scan(
    env: EvalEnv | None = None,
    *,
    seeds: int = _DEFAULT_SEEDS,
    jobs: int | None = None,
    only: str | None = None,
) -> CoverageReport:
    env = env if env is not None else make_env()
    return CoverageReport(
        seeds=seeds,
        cells=scan_cells(env, seeds, jobs=jobs, only=only),
        remedial=scan_remedial(env, seeds),
        unreferenced_causes=unreferenced_causes(env),
        gate_counts=_stage_gate_counts(env),
    )


def _format_text(report: CoverageReport) -> str:
    lines = [f"coverage_scan (seeds={report.seeds}) — {'OK' if report.ok else 'FAIL'}"]
    lines.append(f"  gate_counts: {report.gate_counts}")
    for c in report.cells:
        mark = "✓" if c.ok else "✗"
        detail = f" generated={c.generated}/{c.seeds}"
        if c.passthrough_stages:
            detail += f" passthrough={c.passthrough_stages}"
        if c.failures:
            detail += f" failures={c.failures[:3]}"
        lines.append(f"  {mark} {c.cell}{detail}")
    lines.append("  remedial:")
    for r in report.remedial:
        mark = "✓" if r.ok else "✗"
        detail = f" {r.requesting} -> {r.resolved} generated={r.generated}/{r.seeds} q7r={'ok' if r.q7r_ok else 'FAIL'}"
        if r.failures:
            detail += f" failures={r.failures[:3]}"
        lines.append(f"    {mark} {r.cause_id}{detail}")
    if report.unreferenced_causes:
        lines.append(f"  ⚠ 送り側不在の要因: {report.unreferenced_causes}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coverage_scan", description="生成不能0・ゲート素通り0 の検証")
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument(
        "--only", default=None,
        help="セル名（unit.form.LvN）の正規表現で走査を絞る（テスト・部分確認用）",
    )
    parser.add_argument(
        "--jobs", type=int, default=None,
        help="並列プロセス数（既定はコア数-1）。1 で逐次",
    )
    parser.add_argument("--json", action="store_true", help="JSON でレポート出力")
    parser.add_argument("--out", type=Path, default=None, help="JSON レポートの保存先")
    args = parser.parse_args(argv)

    report = run_coverage_scan(seeds=args.seeds, only=args.only, jobs=args.jobs)
    payload = report.to_json()

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
