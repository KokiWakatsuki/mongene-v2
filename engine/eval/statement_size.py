"""statement_size — 問題文に出る数の大きさを単位ごとに測る（7つ目のゲート）。

`answer_size`（6つ目）は**答え**を測る。こちらは**問題文**を測る。両方要る理由:

```
1辺 339cm の正三角形ABCで、辺BCの長さと∠Aの大きさを求めよ   → 答えは 339cm と 60°
```

答えは正しく、割り切れてもいて、`answer_size` では1つも引っかからない。
**壊れているのは場面のほう**で、3.4m の正三角形は教材に出ない（作図もできない）。

測り方は `engine/core/verify/statement_size.py`（recipe と共有する単一の真実）。
単位ごとに上限を置き、超えるセルは family YAML に理由つきで宣言する
（`statement_size_max` / `statement_size_reason`）。**単位の無い裸の数は測らない。**

CLI: `python -m engine.eval.statement_size [--seeds N] [--only 正規表現] [--json]`
終了コード: 全セルが上限内なら 0、超えるセルがあれば 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.contracts import Coordinate, Unsupported
from engine.core.pipeline import generate
from engine.core.verify.statement_size import (
    DEFAULT_UNIT_LIMITS,
    limits_for,
    statement_hits,
)
from engine.eval._harness import EvalEnv, capability_cells, cell_request, make_env

_DEFAULT_SEEDS = 5


@dataclass
class CellStatementSize:
    cell: str
    seeds: int
    generated: int
    over: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    declared_reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.over


def _limits_and_reason(env: EvalEnv, coord: Coordinate) -> tuple[dict[str, int], str]:
    spec = env.families.get(f"math.{coord.unit}.{coord.form}")
    level = spec.levels.get(str(coord.level)) if spec else None
    reason = (getattr(level, "statement_size_reason", "") or "") if level else ""
    return limits_for(level), reason


def cell_statement_size(env: EvalEnv, coord: Coordinate, seeds: int) -> CellStatementSize:
    limits, reason = _limits_and_reason(env, coord)
    result = CellStatementSize(
        cell=f"{coord.unit}.{coord.form}.Lv{coord.level}",
        seeds=seeds, generated=0, declared_reason=reason,
    )
    worst: dict[str, tuple[float, str]] = {}
    for seed in range(1, seeds + 1):
        res = generate(
            cell_request(coord, seed),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        result.generated += 1
        text = res.problem_text + " ".join(sq.prompt_text or "" for sq in res.sub_questions)
        for hit in statement_hits(text, limits):
            if hit.unit not in worst or hit.value > worst[hit.unit][0]:
                worst[hit.unit] = (hit.value, f"{hit} (seed {seed})")
    result.over = sorted(worst)
    result.samples = [worst[u][1] for u in result.over][:3]
    return result


@dataclass
class StatementSizeReport:
    seeds: int
    cells: list[CellStatementSize]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cells)

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "ok": self.ok,
            "default_unit_limits": DEFAULT_UNIT_LIMITS,
            "over_cells": [c.cell for c in self.cells if c.over],
            "declared_cells": [c.cell for c in self.cells if c.declared_reason],
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
        }


def run_statement_size(
    env: EvalEnv | None = None, *, seeds: int = _DEFAULT_SEEDS, only: str | None = None
) -> StatementSizeReport:
    env = env if env is not None else make_env()
    coords = capability_cells(env)
    if only:
        pat = re.compile(only)
        coords = [c for c in coords if pat.search(f"{c.unit}.{c.form}.Lv{c.level}")]
    return StatementSizeReport(
        seeds=seeds, cells=[cell_statement_size(env, c, seeds) for c in coords]
    )


def _format_text(report: StatementSizeReport) -> str:
    over = [c for c in report.cells if c.over]
    declared = [c for c in report.cells if c.declared_reason]
    lines = [
        f"statement_size (seeds={report.seeds}) — {'OK' if report.ok else 'FAIL'}",
        f"  上限超え: {len(over)} セル / 上限を宣言しているセル: {len(declared)}",
    ]
    for c in over:
        lines.append(f"  ✗ {c.cell} 上限超えの単位: {','.join(c.over)}")
        lines.extend(f"      {s[:120]}" for s in c.samples)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="statement_size", description="問題文の数の大きさ（単位ごと）の検査"
    )
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument("--only", default=None, help="セル名の正規表現で絞る")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_statement_size(seeds=args.seeds, only=args.only)
    payload = report.to_json()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else _format_text(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
