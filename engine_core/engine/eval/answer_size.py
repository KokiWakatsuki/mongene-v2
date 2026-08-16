"""answer_size — 答えの大きさ（分母・分子・根号の中）を測る。

`scratchpad/scan_big_numbers.py` は「問題文と答えに出る最大の数」を大きい順に並べる
だけで、**合否の基準を持っていない**（道具の説明自身が「数が大きいこと自体は欠陥では
ない」と書いている）。標本調査の「20000個」・有効数字の「9780」のように、**問題文の数は
大きくて正しい**ものがあるので、問題文の数は基準にならない。

基準になるのは**答えの形**である。生徒は答えをノートに書き写して丸をつける。
`-107/12` や `√1234` は、計算が合っていても中学の答えとして成り立たない。逆に確率は
約分した分数で答えるのが作法なので、`5/36`（さいころ2個）のように**分母が大きいのが
正しい**単元がある。だから一律の上限ではなく、`dup_rate_max` と同じく **family YAML で
理由つきに宣言できる上限**にしてある（`answer_size_max` / `answer_size_reason`）。

測るのは3つだけ:

| 何 | なぜ |
|---|---|
| 分母 | 約分後の分母。ここが大きいと筆算で扱えない |
| 分子 | 仮分数の分子。`-107/12` のような答えを釣る |
| 根号の中 | 素因数分解して外に出しきったあとの数。`√1234` を釣る |

**整数そのものの大きさは測らない。** 答えが `20000個`（標本調査の推定）や `9780`
（有効数字）になるのは正しく、上限を置くと単元ごとの宣言だらけになって歯止めの意味が
消える。ここで測るのは「**割り切れなさ・開けなさ**の大きさ」である。

CLI: `python -m engine.eval.answer_size [--seeds N] [--json] [--out PATH]`
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
from engine.core.verify.answer_size import (
    DEFAULT_LIMITS,
    AnswerMagnitudes,
    answer_magnitudes,
    limits_for,
)
from engine.eval._harness import EvalEnv, capability_cells, cell_request, make_env
from engine.eval._parallel import pmap

_DEFAULT_SEEDS = 5


@dataclass
class CellAnswerSize:
    cell: str
    seeds: int
    generated: int
    limits: dict[str, int]
    denominator: int = 0
    numerator: int = 0
    radicand: int = 0
    over: list[str] = field(default_factory=list)
    samples: list[str] = field(default_factory=list)
    declared_reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.over


def _limits_for(env: EvalEnv, coord: Coordinate) -> tuple[dict[str, int], str]:
    """そのセルの上限（`answer_size_max` があればそれ）と、宣言の理由。

    上限の解釈は `engine.core.verify.answer_size.limits_for` が持つ（recipe の
    「組み直す／組み直さない」の判定と同じ関数を通す）。ここは理由の文字列だけを足す。
    """
    spec = env.families.get(f"math.{coord.unit}.{coord.form}")
    level = spec.levels.get(str(coord.level)) if spec else None
    reason = (getattr(level, "answer_size_reason", "") or "") if level else ""
    return limits_for(level), reason


def _answer_texts(res: object) -> list[str]:
    out: list[str] = []
    for sq in getattr(res, "sub_questions", []):
        answer = sq.answer
        display = getattr(answer, "display", None)
        if display:
            out.append(str(display))
        else:
            correct = getattr(answer, "correct", None)
            if correct is not None:
                out.append(str(correct))
    return out


def cell_answer_size(env: EvalEnv, coord: Coordinate, seeds: int) -> CellAnswerSize:
    limits, reason = _limits_for(env, coord)
    result = CellAnswerSize(
        cell=f"{coord.unit}.{coord.form}.Lv{coord.level}",
        seeds=seeds,
        generated=0,
        limits=limits,
        declared_reason=reason,
    )
    samples: dict[str, str] = {}
    for seed in range(1, seeds + 1):
        res = generate(
            cell_request(coord, seed),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        result.generated += 1
        for text in _answer_texts(res):
            m = answer_magnitudes(text)
            for name in DEFAULT_LIMITS:
                if getattr(m, name) > getattr(result, name):
                    setattr(result, name, getattr(m, name))
                    if getattr(m, name) > limits[name]:
                        samples[name] = f"{name}={getattr(m, name)} (seed {seed}) :: {m.sample}"
    result.over = AnswerMagnitudes(
        denominator=result.denominator, numerator=result.numerator, radicand=result.radicand
    ).over(limits)
    result.samples = [samples[n] for n in result.over if n in samples]
    return result


@dataclass
class AnswerSizeReport:
    seeds: int
    cells: list[CellAnswerSize]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cells)

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "ok": self.ok,
            "default_limits": DEFAULT_LIMITS,
            "over_cells": [c.cell for c in self.cells if c.over],
            "declared_cells": [c.cell for c in self.cells if c.declared_reason],
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
        }


def _cell_job(env: EvalEnv, coord: Coordinate, seeds: int) -> CellAnswerSize:
    """ワーカー1つが担当するセル1つ分（`_parallel.pmap` から呼ばれる）。"""
    return cell_answer_size(env, coord, seeds)


def run_answer_size(
    env: EvalEnv | None = None,
    *,
    seeds: int = _DEFAULT_SEEDS,
    only: str | None = None,
    jobs: int | None = None,
) -> AnswerSizeReport:
    env = env if env is not None else make_env()
    coords = capability_cells(env)
    if only:
        pat = re.compile(only)
        coords = [c for c in coords if pat.search(f"{c.unit}.{c.form}.Lv{c.level}")]
    cells = pmap(_cell_job, [(c, seeds) for c in coords], jobs=jobs)
    return AnswerSizeReport(seeds=seeds, cells=cells)


def _format_text(report: AnswerSizeReport) -> str:
    over = [c for c in report.cells if c.over]
    declared = [c for c in report.cells if c.declared_reason]
    lines = [
        f"answer_size (seeds={report.seeds}, 既定の上限={DEFAULT_LIMITS}) — "
        f"{'OK' if report.ok else 'FAIL'}",
        f"  上限超え: {len(over)} セル / 上限を宣言しているセル: {len(declared)}",
    ]
    for c in over:
        lines.append(f"  ✗ {c.cell} 上限超え: {','.join(c.over)}（上限 {c.limits}）")
        lines.extend(f"      {s[:110]}" for s in c.samples)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="answer_size", description="答えの大きさ（分母・分子・根号の中）の検査"
    )
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument("--only", default=None, help="セル名の正規表現で絞る（実測の当たり用）")
    parser.add_argument("--all", action="store_true", help="上限内のセルも実測値を出す")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_answer_size(seeds=args.seeds, only=args.only)
    if args.all:
        for c in report.cells:
            print(
                f"  {'✓' if c.ok else '✗'} {c.cell} 分母{c.denominator} 分子{c.numerator} "
                f"根号{c.radicand}"
            )
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
