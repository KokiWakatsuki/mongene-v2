"""D-10 の検査: 答え・ヒント・解説に出る記号が、問題文に出ているか。

問題文の頂点名は recipe が引く（dup_rate のためにランダム化される）のに、
solver の表示文が点名を直書きしていると、「三角形AKJ の面積を求めよ」と問うて
「三角形ADE:台形DBCE」と答えることになる。

**問題文に一度も出ない大文字の記号**が答え・ヒント・解説に出たら疑いとして挙げる。
問題文に出ていれば（別の役割で使われていても）ここでは通す——過検出を避けるため。

実行:
  .venv/bin/python records/work/scan_point_names.py [--seeds N] [unit.form.Lv ...]
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

_UPPER = re.compile(r"[A-Z]")

# 記号ではなく単位・語として出る大文字。問題文に無くても点名の食い違いではない。
_ALLOW = set("LX")  # L=リットル / X=未知（まず出ないが保険）


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


def solution_texts(res) -> list[tuple[str, str]]:
    """(どこ, 文字列) の一覧。"""
    out = []
    for sq in res.sub_questions:
        ans = sq.answer
        disp = getattr(ans, "display", None)
        if disp:
            out.append(("答え", str(disp)))
        for d in getattr(ans, "distractors", None) or []:
            out.append(("選択肢", str(d)))
        cor = getattr(ans, "correct", None)
        if cor is not None:
            out.append(("答え", str(cor)))
        for h in sq.hints:
            out.append(("ヒント", str(h)))
        for st in sq.solution_steps:
            out.append(("解説", f"{st.result_display} :: {st.narration}"))
        if sq.explanation:
            out.append(("解説", str(sq.explanation)))
    return out


def main() -> int:
    args = sys.argv[1:]
    seeds = 5
    if args and args[0] == "--seeds":
        seeds = int(args[1])
        args = args[2:]
    cells = [tuple(s.rsplit(".", 2)) for s in args] if args else None
    if cells:
        cells = [(u, f, int(lv.lstrip("Lv"))) for u, f, lv in cells]
    else:
        cells = all_cells()

    env = make_env()
    flagged: dict[tuple, dict[str, tuple[str, str]]] = {}
    for unit, form, lv in cells:
        for seed in range(1, seeds + 1):
            req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
            res = generate(
                req, curriculum=env.curriculum, families=env.families, registry=env.registry
            )
            if isinstance(res, Unsupported):
                continue
            problem = res.problem_text + " ".join(
                sq.prompt_text or "" for sq in res.sub_questions
            )
            in_problem = set(_UPPER.findall(problem)) | _ALLOW
            for where, text in solution_texts(res):
                for ch in sorted(set(_UPPER.findall(text)) - in_problem):
                    flagged.setdefault((unit, form, lv), {}).setdefault(
                        ch, (where, text.replace("\n", " / ")[:110])
                    )

    for (unit, form, lv), hits in flagged.items():
        letters = "".join(sorted(hits))
        print(f"\n## {unit}.{form}.Lv{lv}  余分な記号: {letters}")
        seen = set()
        for ch, (where, text) in sorted(hits.items()):
            if text in seen:
                continue
            seen.add(text)
            print(f"   [{where}] {text}")
    print(f"\n=== {len(flagged)} セルに疑い（{len(cells)} セル走査・各 {seeds} seed） ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
