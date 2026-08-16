"""retry_stats（実装設計 §6.1・§8.3・Task10）— 有界リトライ発動率と構成失敗の分布。

§6.1: 構成的生成（answer-first）はリトライ原則禁止。構成で保証しきれない希な条件のみ
`@bounded_retry(3)` を宣言でき、eval が発動率を記録し **5% 超はスペック不合格**。

セル × N seeds で MR 構築を試み:
  - **retry 発動率** = attempts > 1 だった seed の割合（bounded_retry 宣言セルのみ非0になり得る）。
  - **構成失敗率** = 有界回数内に構成しきれず MR を得られなかった seed の割合。
  - どの recipe が bounded_retry を宣言しているか（宣言があるのに発動しないのは健全）。

CLI: `python -m engine.eval.retry_stats [--seeds N] [--threshold R] [--json] [--out PATH]`
終了コード: 全セルの retry 発動率 ≤ 閾（既定 0.05）かつ構成失敗0=0 / 超過=1。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.contracts import Coordinate
from engine.eval._parallel import pmap
from engine.eval._harness import (
    EvalEnv,
    build_mr,
    cell_request,
    make_env,
    select_cells,
)

_DEFAULT_SEEDS = 100
_DEFAULT_THRESHOLD = 0.05


@dataclass
class CellRetryStats:
    cell: str
    seeds: int
    declares_bounded_retry: bool
    retry_invocations: int          # attempts > 1
    construct_failures: int         # 有界内に構成しきれなかった
    retry_rate: float
    failure_rate: float
    over_threshold: bool
    failure_samples: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.over_threshold and self.construct_failures == 0


def _declares_bounded_retry(env: EvalEnv, coord: "Coordinate") -> bool:
    """セルの recipe が `_bounded_retry` を宣言しているか。"""
    from engine.core.contracts import CellContext
    from engine.core.pipeline import resolve

    ctx = resolve(
        cell_request(coord, 1),
        curriculum=env.curriculum, families=env.families, registry=env.registry,
    )
    if isinstance(ctx, CellContext):
        recipe_fn = env.registry.recipe(ctx.spec_level.recipe)
        return bool(getattr(recipe_fn, "_bounded_retry", 0))
    return False


def cell_retry_stats(env: EvalEnv, coord: Coordinate, seeds: int, threshold: float) -> CellRetryStats:
    retries = 0
    failures = 0
    samples: list[dict[str, object]] = []
    for seed in range(1, seeds + 1):
        r = build_mr(coord, seed, env)
        if not r.ok:
            failures += 1
            if len(samples) < 5:
                samples.append({"seed": seed, "error": r.error})
            continue
        if r.attempts > 1:
            retries += 1
    retry_rate = retries / seeds if seeds else 0.0
    failure_rate = failures / seeds if seeds else 0.0
    return CellRetryStats(
        cell=f"{coord.unit}.{coord.form}.Lv{coord.level}",
        seeds=seeds,
        declares_bounded_retry=_declares_bounded_retry(env, coord),
        retry_invocations=retries,
        construct_failures=failures,
        retry_rate=round(retry_rate, 4),
        failure_rate=round(failure_rate, 4),
        over_threshold=retry_rate > threshold,
        failure_samples=samples,
    )


@dataclass
class RetryStatsReport:
    seeds: int
    threshold: float
    cells: list[CellRetryStats]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cells)

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "threshold": self.threshold,
            "ok": self.ok,
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
        }


def _cell_job(env: EvalEnv, coord: Coordinate, seeds: int, threshold: float) -> CellRetryStats:
    """ワーカー1つが担当するセル1つ分（`_parallel.pmap` から呼ばれる）。"""
    return cell_retry_stats(env, coord, seeds, threshold)


def run_retry_stats(
    env: EvalEnv | None = None,
    *,
    seeds: int = _DEFAULT_SEEDS,
    threshold: float = _DEFAULT_THRESHOLD,
    jobs: int | None = None,
    only: str | None = None,
) -> RetryStatsReport:
    env = env if env is not None else make_env()
    coords = select_cells(env, only)
    cells = pmap(_cell_job, [(c, seeds, threshold) for c in coords], jobs=jobs)
    return RetryStatsReport(seeds=seeds, threshold=threshold, cells=cells)


def _format_text(report: RetryStatsReport) -> str:
    lines = [
        f"retry_stats (seeds={report.seeds}, threshold={report.threshold}) — "
        f"{'OK' if report.ok else 'FAIL'}"
    ]
    for c in report.cells:
        mark = "✓" if c.ok else "✗"
        br = "bounded_retry宣言" if c.declares_bounded_retry else "リトライ無宣言"
        detail = (
            f" retry_rate={c.retry_rate} ({c.retry_invocations}/{c.seeds}) "
            f"failures={c.construct_failures} [{br}]"
        )
        lines.append(f"  {mark} {c.cell}{detail}")
        if c.failure_samples:
            lines.append(f"      failure_samples={c.failure_samples}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retry_stats", description="有界リトライ発動率・構成失敗分布")
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument(
        "--only", default=None,
        help="セル名（unit.form.LvN）の正規表現で走査を絞る（テスト・部分確認用）",
    )
    parser.add_argument(
        "--jobs", type=int, default=None,
        help="並列プロセス数（既定はコア数-1）。1 で逐次",
    )
    parser.add_argument("--threshold", type=float, default=_DEFAULT_THRESHOLD)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_retry_stats(seeds=args.seeds, threshold=args.threshold, only=args.only, jobs=args.jobs)
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
