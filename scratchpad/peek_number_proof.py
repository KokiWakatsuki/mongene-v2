"""生成された「数の性質の説明」を問題文・解答・解説・ヒントまで通しで読む。"""
from __future__ import annotations

import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate

bootstrap()
cells = [("g2_l7", 2), ("g2_l7", 3), ("g2_l8", 2), ("g2_l8", 3), ("g3_l13", 2), ("g3_l13", 3)]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
for unit, lv in cells:
    for seed in range(1, n + 1):
        r = generate(GenerateRequest(subject="math", unit=unit, form="proof", level=lv, seed=seed))
        if isinstance(r, Unsupported):
            print(f"!! {unit} Lv{lv} seed{seed}: {r.code} {r.detail}")
            continue
        sq = r.sub_questions[0]
        print(f"===== {unit}.proof.Lv{lv} seed{seed}")
        print("[問題]", r.problem_text)
        print("[問い]", sq.prompt_text)
        print("[解答]")
        for line in sq.answer.text.split("\n"):
            print("   ", line)
        print("[解説]")
        for line in sq.explanation.split("\n"):
            print("   ", line)
        print("[ヒント]", " / ".join(sq.hints))
        print()
