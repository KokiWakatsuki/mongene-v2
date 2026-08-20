"""D-17 の検査: ヒントが中身のないフォールバックになっているセルを挙げる。

1手で解ける問題は「最後の手は答えを明かすので出さない」という規則で候補が空になり、
`_DEFAULT_MINIMAL_HINT`（「問題文の与えられた値をもう一度確認しよう。」）に落ちる。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/scan_empty_hints.py [--seeds N]
"""
from __future__ import annotations

import glob
import sys

import yaml

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env
from engine_paths import FAMILIES_DIR  # エンジンの場所は1か所で解決する

_DEFAULT = "問題文の与えられた値をもう一度確認しよう。"


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
    seeds = 3
    if args and args[0] == "--seeds":
        seeds = int(args[1])

    env = make_env()
    hits = []
    for unit, form, lv in all_cells():
        sample = ""
        for seed in range(1, seeds + 1):
            req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
            res = generate(
                req, curriculum=env.curriculum, families=env.families, registry=env.registry
            )
            if isinstance(res, Unsupported):
                continue
            for sq in res.sub_questions:
                if _DEFAULT in sq.hints:
                    sample = f"{res.problem_text.splitlines()[-1][:60]} / hints={sq.hints}"
        if sample:
            hits.append((unit, form, lv, sample))

    for unit, form, lv, sample in hits:
        print(f"{unit}.{form}.Lv{lv}\n    {sample}")
    print(f"\n=== 中身のないヒント {len(hits)} セル ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
