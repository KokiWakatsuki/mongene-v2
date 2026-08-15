"""text_quality — 生徒に見せる文そのものの質を測る2つの検査（実装設計 §8.3 の追加ゲート）。

4つの既存ゲート（coverage / dup_rate / level_sep / retry）はどれも**構造**しか見ていない。
「その問題が教材としてありうるか」を測るものが無かったため、次の2つが長く残っていた
（`scratchpad/corpus/EVALUATION.md`）:

  - **D-10 記号の食い違い**（12セル）… 問題文の頂点名は dup のためにランダム化される
    のに solver の表示文が点名を直書きしていて、「三角形AKJ の面積を求めよ」と問うて
    「三角形ADE:台形DBCE」と答えていた。生徒は答えと問題の対応が取れない。
    ついでに「解説に生の sympy（`Eq(...)`）が出ている」（D-25）もこの検査が釣り上げた。
  - **D-17 中身のないヒント**（26セル）… 1手で解ける問題は「最後の手は答えを明かすので
    ヒントにしない」という規則で候補が空になり、既定文に落ちていた。

どちらも `scratchpad/scan_point_names.py` / `scan_empty_hints.py` として走査の形で
動いていたものを、**回帰の歯止め**としてゲートに昇格させた。どちらも 0件が合格。

**2つの検査は1回の generate を共有する**（別々に回すと生成が二重になる）。

CLI: `python -m engine.eval.text_quality [--seeds N] [--json] [--out PATH]`
終了コード: 疑いが0件なら 0、1件でもあれば 1。
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
from engine.eval._harness import EvalEnv, capability_cells, cell_request, make_env

_DEFAULT_SEEDS = 3

_UPPER = re.compile(r"[A-Z]")

# 記号ではなく単位・語として出る大文字（問題文に無くても点名の食い違いではない）。
_ALLOW = frozenset("LX")  # L=リットル / X=未知（まず出ないが保険）

# 一般形の書き方に出る大文字は、問題文の記号ではなく「式そのもの」の代わり。
# `A=B=C` は「3つの式が等しい等式」の一般形（g2_l15.calculation.Lv2 のヒント
# 「A=B=C を A=C と B=C の2つの式に分けて連立方程式にする」）で、教科書どおりの表記。
# 例外はこの1つだけ——増やすときは、必ず「問題文の記号ではない」ことを確かめてから。
_GENERAL_FORM_EXCEPTIONS: tuple[tuple[str, str], ...] = (("A=B=C", "ABC"),)

# 中身のないヒント（`t1_template.py` の `_DEFAULT_MINIMAL_HINT`）。
_EMPTY_HINT = "問題文の与えられた値をもう一度確認しよう。"


@dataclass
class CellTextQuality:
    cell: str
    seeds: int
    generated: int
    # 答え・ヒント・解説に出るのに問題文に一度も出ない大文字（記号の食い違い）。
    stray_symbols: list[str] = field(default_factory=list)
    stray_samples: list[str] = field(default_factory=list)
    # 中身のないヒントに落ちた小問があったか。
    empty_hint: bool = False
    empty_hint_sample: str = ""

    @property
    def ok(self) -> bool:
        return not self.stray_symbols and not self.empty_hint


def _solution_texts(res: object) -> list[tuple[str, str]]:
    """(どこ, 文字列) の一覧。答え・選択肢・ヒント・解説の全部を見る。"""
    out: list[tuple[str, str]] = []
    for sq in getattr(res, "sub_questions", []):
        answer = sq.answer
        display = getattr(answer, "display", None)
        if display:
            out.append(("答え", str(display)))
        correct = getattr(answer, "correct", None)
        if correct is not None:
            out.append(("答え", str(correct)))
        for d in getattr(answer, "distractors", None) or []:
            out.append(("選択肢", str(d)))
        for h in sq.hints:
            out.append(("ヒント", str(h)))
        for st in sq.solution_steps:
            out.append(("解説", f"{st.result_display} :: {st.narration}"))
        if sq.explanation:
            out.append(("解説", str(sq.explanation)))
    return out


def _allowed_symbols(text: str) -> frozenset[str]:
    """その文だけで許される大文字（一般形の書き方に出るもの）。"""
    extra = "".join(letters for pattern, letters in _GENERAL_FORM_EXCEPTIONS if pattern in text)
    return _ALLOW | frozenset(extra)


def cell_text_quality(env: EvalEnv, coord: Coordinate, seeds: int) -> CellTextQuality:
    result = CellTextQuality(
        cell=f"{coord.unit}.{coord.form}.Lv{coord.level}", seeds=seeds, generated=0
    )
    stray: dict[str, str] = {}
    for seed in range(1, seeds + 1):
        res = generate(
            cell_request(coord, seed),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        result.generated += 1

        problem = res.problem_text + " ".join(sq.prompt_text or "" for sq in res.sub_questions)
        in_problem = frozenset(_UPPER.findall(problem))
        for where, text in _solution_texts(res):
            allowed = in_problem | _allowed_symbols(text)
            for ch in sorted(frozenset(_UPPER.findall(text)) - allowed):
                stray.setdefault(ch, f"[{where}] {text.splitlines()[0][:110]}")

        if not result.empty_hint:
            for sq in res.sub_questions:
                if _EMPTY_HINT in sq.hints:
                    result.empty_hint = True
                    result.empty_hint_sample = f"{sq.prompt_text} / hints={list(sq.hints)}"
                    break

    result.stray_symbols = sorted(stray)
    result.stray_samples = [stray[ch] for ch in result.stray_symbols][:3]
    return result


@dataclass
class TextQualityReport:
    seeds: int
    cells: list[CellTextQuality]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.cells)

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "ok": self.ok,
            "stray_symbol_cells": [c.cell for c in self.cells if c.stray_symbols],
            "empty_hint_cells": [c.cell for c in self.cells if c.empty_hint],
            "cells": [asdict(c) | {"ok": c.ok} for c in self.cells],
        }


def run_text_quality(env: EvalEnv | None = None, *, seeds: int = _DEFAULT_SEEDS) -> TextQualityReport:
    env = env if env is not None else make_env()
    cells = [cell_text_quality(env, coord, seeds) for coord in capability_cells(env)]
    return TextQualityReport(seeds=seeds, cells=cells)


def _format_text(report: TextQualityReport) -> str:
    stray = [c for c in report.cells if c.stray_symbols]
    empty = [c for c in report.cells if c.empty_hint]
    lines = [
        f"text_quality (seeds={report.seeds}) — {'OK' if report.ok else 'FAIL'}",
        f"  記号の食い違い: {len(stray)} セル / 中身のないヒント: {len(empty)} セル",
    ]
    for c in stray:
        lines.append(f"  ✗ {c.cell} 問題文に無い記号: {''.join(c.stray_symbols)}")
        lines.extend(f"      {s}" for s in c.stray_samples)
    for c in empty:
        lines.append(f"  ✗ {c.cell} 中身のないヒント: {c.empty_hint_sample[:110]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="text_quality", description="記号の食い違い・中身のないヒントの検査"
    )
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_text_quality(seeds=args.seeds)
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
