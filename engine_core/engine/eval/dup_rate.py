"""dup_rate（実装設計 §4.4・§8.3・D-1・Task10）— 重複率の2系統測定。

2系統（§4.4 の H2 接地）:
  1. **dup_key 系**（セル内）: セル × N seeds の `dup_key`（signature + 正規化 params）
     衝突率。≤ 0.20（D-1 仮値）を閾とする。「同一セルが実質同じ問題を量産していないか」。
  2. **fp 系**（family 横断）: 異なる signature（= 異なるレベル）が同一の計算指紋 fp を
     共有していないか。共有していれば「別署名を貼った実質同一構造」（宣言の嘘）であり、
     重複の第2の姿として可視化する。level_sep の fp 相異検査と表裏だが、dup_rate 側は
     「重複」の観点で family 内の全 (signature, fp) を突き合わせる。

セル内の fp は同一 signature ゆえ全 seed で一定（G-FP が保証）。よって fp 系は
セル単位ではなく family 単位で「署名をまたぐ fp 衝突」を測るのが意味論的に正しい。

CLI: `python -m engine.eval.dup_rate [--seeds N] [--threshold R] [--json] [--out PATH]`
終了コード: 全合格=0 / 閾超過 or 署名跨ぎ fp 衝突あり=1。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.contracts import Coordinate
from engine.core.signature import dup_key, fingerprint_hash
from engine.eval._parallel import pmap
from engine.eval._harness import (
    EvalEnv,
    build_mr,
    capability_cells,
    family_of,
    make_env,
    select_cells,
)

_DEFAULT_SEEDS = 100
_DEFAULT_THRESHOLD = 0.20


@dataclass
class CellDupRate:
    cell: str
    seeds: int
    generated: int
    distinct_dup_keys: int
    dup_rate: float
    distinct_fps: int  # 期待 1（同一 signature ゆえ fp 一定＝ G-FP 安定の傍証）
    over_threshold: bool
    build_failures: list[dict[str, object]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.over_threshold and not self.build_failures


@dataclass
class FamilyFpCollision:
    """family 内で複数 signature が同一 fp を共有している（実質同一構造・別署名）。"""

    family: str
    fp: str
    signatures: list[str]


def _threshold_for(env: EvalEnv, coord: Coordinate, default: float) -> float:
    """そのセルに宣言された重複率の上限（無ければ既定）。

    多角形の内角・外角のように**教材にありうる設定が十数通りしかない**単元がある。
    既定の 0.20 を通そうとすると「正348角形」を作ることになるので、
    family YAML の `dup_rate_max` で宣言できるようにしてある（理由の記載が必須）。
    """
    spec = env.families.get(f"math.{coord.unit}.{coord.form}")
    level = spec.levels.get(str(coord.level)) if spec else None
    declared = getattr(level, "dup_rate_max", None) if level else None
    return float(declared) if declared is not None else default


def cell_dup_rate(env: EvalEnv, coord: Coordinate, seeds: int, threshold: float) -> CellDupRate:
    threshold = _threshold_for(env, coord, threshold)
    dup_keys: list[str] = []
    fps: set[str] = set()
    failures: list[dict[str, object]] = []
    for seed in range(1, seeds + 1):
        r = build_mr(coord, seed, env)
        if not r.ok or r.mr is None:
            failures.append({"seed": seed, "error": r.error})
            continue
        dup_keys.append(dup_key(r.mr))
        fps.add(fingerprint_hash(r.mr))
    generated = len(dup_keys)
    distinct = len(set(dup_keys))
    rate = (generated - distinct) / generated if generated else 0.0
    return CellDupRate(
        cell=f"{coord.unit}.{coord.form}.Lv{coord.level}",
        seeds=seeds,
        generated=generated,
        distinct_dup_keys=distinct,
        dup_rate=round(rate, 4),
        distinct_fps=len(fps),
        over_threshold=rate > threshold,
        build_failures=failures,
    )


def family_fp_collisions(env: EvalEnv, seeds: int) -> list[FamilyFpCollision]:
    """family ごとに全レベルの (signature -> fp) を集め、fp を共有する複数 signature を検出。"""
    # family -> fp -> set(signature)
    by_family: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for coord in capability_cells(env):
        fam = family_of(coord)
        # 各レベルは fp 一定なので seed=1 の1件で signature/fp を代表させれば十分だが、
        # G-FP 未成立の異常検知も兼ねて数 seed を確認する。
        for seed in range(1, min(seeds, 5) + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            by_family[fam][fingerprint_hash(r.mr)].add(r.mr.signature)

    collisions: list[FamilyFpCollision] = []
    for fam, fp_map in sorted(by_family.items()):
        for fp, sigs in sorted(fp_map.items()):
            if len(sigs) >= 2:
                collisions.append(FamilyFpCollision(family=fam, fp=fp, signatures=sorted(sigs)))
    return collisions


@dataclass
class DupRateReport:
    seeds: int
    threshold: float
    cells: list[CellDupRate]
    fp_collisions: list[FamilyFpCollision]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cells) and not self.fp_collisions

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "threshold": self.threshold,
            "ok": self.ok,
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
            "fp_collisions": [asdict(x) for x in self.fp_collisions],
        }


def _cell_job(
    env: EvalEnv, coord: Coordinate, seeds: int, threshold: float
) -> tuple[CellDupRate, list[tuple[str, str, str]]]:
    """ワーカー1つが担当するセル1つ分（`_parallel.pmap` から呼ばれる）。

    dup_rate の集計と fp の収集を**1回の呼び出しでまとめて**返す。別々の pmap に
    すると、そのたびにワーカーを起こし直して bootstrap のぶんだけ実時間が伸びる。
    """
    cell = cell_dup_rate(env, coord, seeds, threshold)
    fam = family_of(coord)
    fps: list[tuple[str, str, str]] = []
    for seed in range(1, min(seeds, 5) + 1):
        r = build_mr(coord, seed, env)
        if not r.ok or r.mr is None:
            continue
        fps.append((fam, fingerprint_hash(r.mr), r.mr.signature))
    return cell, fps


def run_dup_rate(
    env: EvalEnv | None = None,
    *,
    seeds: int = _DEFAULT_SEEDS,
    threshold: float = _DEFAULT_THRESHOLD,
    jobs: int | None = None,
    only: str | None = None,
) -> DupRateReport:
    env = env if env is not None else make_env()
    coords = select_cells(env, only)
    # **セルどうしは独立**（`cell_dup_rate` はそのセルの seed からしか読まない）ので、
    # プロセスに配っても測る値は変わらない。
    pairs = pmap(_cell_job, [(c, seeds, threshold) for c in coords], jobs=jobs)
    cells = [c for c, _ in pairs]
    by_family: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for _, rows in pairs:
        for fam, fp, sig in rows:
            by_family[fam][fp].add(sig)
    collisions = [
        FamilyFpCollision(family=fam, fp=fp, signatures=sorted(sigs))
        for fam, fp_map in sorted(by_family.items())
        for fp, sigs in sorted(fp_map.items())
        if len(sigs) >= 2
    ]
    return DupRateReport(
        seeds=seeds,
        threshold=threshold,
        cells=cells,
        fp_collisions=collisions,
    )


def _format_text(report: DupRateReport) -> str:
    lines = [
        f"dup_rate (seeds={report.seeds}, threshold={report.threshold}) — "
        f"{'OK' if report.ok else 'FAIL'}"
    ]
    lines.append("  [dup_key 系] セル内 dup_key 衝突率:")
    for c in report.cells:
        mark = "✓" if c.ok else "✗"
        detail = f" dup_rate={c.dup_rate} (distinct {c.distinct_dup_keys}/{c.generated}) fps={c.distinct_fps}"
        if c.build_failures:
            detail += f" build_failures={len(c.build_failures)}"
        lines.append(f"    {mark} {c.cell}{detail}")
    lines.append("  [fp 系] family 内の署名跨ぎ fp 衝突:")
    if not report.fp_collisions:
        lines.append("    ✓ なし（各 signature の fp は相異）")
    else:
        for x in report.fp_collisions:
            lines.append(f"    ✗ {x.family}: fp={x.fp} を共有 {x.signatures}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dup_rate", description="重複率の2系統測定（dup_key / fp）")
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

    report = run_dup_rate(seeds=args.seeds, threshold=args.threshold, only=args.only, jobs=args.jobs)
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
