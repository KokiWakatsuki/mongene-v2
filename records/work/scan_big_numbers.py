"""D-12 の検査: 問題文と答えに出る数の大きさを、全セルで測る。

「教材としてありうる数か」を測るものがエンジンに無いので、まず**規模を測る**。
セルごとに、いくつかの seed で「問題文に出る最大の数」「答えに出る最大の数」
「答えの分母の最大」を取り、大きい順に並べる。

数が大きいこと自体は欠陥ではない（標本調査の「20000個」・有効数字の「9780」は
適切）。**その数が計算に効くのに大きい**ものを見つけるための当たりをつける道具。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/scan_big_numbers.py [--seeds N] [--top N]
"""
from __future__ import annotations

import glob
import re
import sys

import yaml

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env
from engine_paths import FAMILIES_DIR  # エンジンの場所は1か所で解決する

_NUM = re.compile(r"\d+")
_FRAC = re.compile(r"(\d+)\s*/\s*(\d+)")


def all_cells() -> list[tuple[str, str, int]]:
    cells = []
    for path in sorted(glob.glob(str(FAMILIES_DIR / "*.yaml"))):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit, form = doc["family"].removeprefix("math.").rsplit(".", 1)
        for lv in (doc.get("levels") or {}):
            cells.append((unit, form, int(lv)))
    grade_order = {"g1": 0, "g2": 1, "g3": 2, "exam": 3}

    def key(c: tuple) -> tuple:
        grade, _, lesson = c[0].partition("_l")
        return (grade_order.get(grade, 9), int(lesson or 0), c[1], c[2])

    return sorted(cells, key=key)


def main() -> int:
    args = sys.argv[1:]
    seeds, top = 3, 60
    while args and args[0].startswith("--"):
        if args[0] == "--seeds":
            seeds = int(args[1])
        elif args[0] == "--top":
            top = int(args[1])
        args = args[2:]

    env = make_env()
    rows = []
    for unit, form, lv in all_cells():
        q_max = a_max = den_max = 0
        sample_q = sample_a = ""
        for seed in range(1, seeds + 1):
            req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
            res = generate(
                req, curriculum=env.curriculum, families=env.families, registry=env.registry
            )
            if isinstance(res, Unsupported):
                continue
            q = res.problem_text + " ".join(sq.prompt_text or "" for sq in res.sub_questions)
            a = " ".join(
                str(getattr(sq.answer, "display", None) or getattr(sq.answer, "correct", ""))
                for sq in res.sub_questions
            )
            qm = max((int(x) for x in _NUM.findall(q)), default=0)
            am = max((int(x) for x in _NUM.findall(a)), default=0)
            dm = max((int(d) for _, d in _FRAC.findall(a)), default=0)
            if qm > q_max:
                q_max, sample_q = qm, q.replace("\n", " ")[:90]
            if am > a_max:
                a_max, sample_a = am, a[:60]
            den_max = max(den_max, dm)
        rows.append((max(q_max, a_max), q_max, a_max, den_max, unit, form, lv, sample_q, sample_a))

    rows.sort(reverse=True)
    print(f"{'最大':>8} {'問題':>7} {'答え':>8} {'分母':>5}  セル")
    for worst, qm, am, dm, unit, form, lv, sq, sa in rows[:top]:
        print(f"{worst:>8} {qm:>7} {am:>8} {dm:>5}  {unit}.{form}.Lv{lv}")
        print(f"           Q: {sq}")
        print(f"           A: {sa}")

    buckets = [(0, 20), (21, 50), (51, 99), (100, 999), (1000, 10**18)]
    print("\n問題文に出る最大の数の分布")
    for lo, hi in buckets:
        n = sum(1 for r in rows if lo <= r[1] <= hi)
        print(f"  {lo}〜{hi if hi < 10**18 else ''}: {n} セル")
    return 0


if __name__ == "__main__":
    sys.exit(main())
