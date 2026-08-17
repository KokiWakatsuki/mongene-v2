"""証明の答えに出る角名が、問題文の書き方と食い違っていないかを数える。

## なぜ要るか

`g2_l32.proof.Lv2` の問題文は「∠OAB ＝ ∠OCD である」と書いているのに、
証明の「仮定より」の行は「∠BAO ＝ ∠DCO」と**逆順**で書いていた。
同じ角なので数学的には正しいが、生徒は仮定を書き写す手を最初に習うので、
問題文と違う並びで書かれていると対応が取れない。

## 使い方

    PYTHONPATH=engine_core .venv/bin/python records/work/scan_proof_angle_names.py

`--seeds` で seed 数、`--units` で単元を絞れる。

## ★ヒアドキュメントで測らないこと

同じ走査をシェルのヒアドキュメントで流したときは「2208 個中 0 件」と出たが、
単体で回すと同じ seed が発火した（`g2_l32` seed 1）。ファイルに置いて実行する。
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_ANGLE = re.compile(r"∠([A-Z]{3})")

_PROOF_UNITS = [
    "g2_l32", "g2_l38", "g2_l39", "g2_l40", "g2_l41", "g2_l42", "g2_l43",
    "g2_l44", "g2_l45", "g2_l46", "g2_l47", "g2_l48", "g2_l49", "g2_l50",
    "g3_l41", "g3_l42", "g3_l43", "g3_l44", "g3_l45", "g3_l46", "g3_l47",
    "g3_l48", "g3_l49", "g3_l50", "exam_l6",
]


def _answer_text(answer: object) -> str:
    """証明の答えは `text`（`display` は None）。**ここを間違えると全部 0 件になる。**"""
    return (
        getattr(answer, "text", None)
        or getattr(answer, "display", None)
        or str(getattr(answer, "correct", "") or "")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=12)
    ap.add_argument("--units", nargs="*", default=_PROOF_UNITS)
    args = ap.parse_args()

    env = make_env()
    checked = 0
    reversed_hits: Counter[str] = Counter()
    samples: list[str] = []
    problem_angles_seen = 0

    for unit in args.units:
        for level in (2, 3, 4):
            for seed in range(1, args.seeds + 1):
                res = generate(
                    GenerateRequest(
                        subject="math", unit=unit, form="proof", level=level, seed=seed
                    ),
                    curriculum=env.curriculum,
                    families=env.families,
                    registry=env.registry,
                )
                if isinstance(res, Unsupported):
                    continue
                in_problem = set(_ANGLE.findall(res.problem_text))
                problem_angles_seen += len(in_problem)
                for sq in res.sub_questions:
                    for name in set(_ANGLE.findall(_answer_text(sq.answer))):
                        checked += 1
                        if name not in in_problem and name[::-1] in in_problem:
                            cell = f"{unit}.proof.Lv{level}"
                            reversed_hits[cell] += 1
                            if len(samples) < 8:
                                samples.append(
                                    f"{cell} seed{seed}: 問題文 ∠{name[::-1]} → 答え ∠{name}"
                                )

    # **0 件を信じる前に、比べる相手が空でないことを示す。**
    print(f"問題文から読めた角: {problem_angles_seen} 個")
    print(f"答えに出た角: {checked} 個")
    print(f"■ 問題文と逆順で書かれている角: {sum(reversed_hits.values())} 個 "
          f"/ {len(reversed_hits)} セル")
    for cell, n in reversed_hits.most_common():
        print(f"    {cell}: {n}")
    for s in samples:
        print(f"    例 {s}")
    return 1 if reversed_hits else 0


if __name__ == "__main__":
    sys.exit(main())
