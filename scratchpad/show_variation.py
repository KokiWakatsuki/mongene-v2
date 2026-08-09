"""1セルの中で問題がどう変わるかを、seed を並べて見る。

実行: PYTHONPATH=. .venv/bin/python scratchpad/show_variation.py g3_l26 calculation 2 8
"""
from __future__ import annotations

import json
import sys

from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env


def pattern_key(params: dict) -> str:
    out = {k: v for k, v in sorted(params.items()) if isinstance(v, (bool, str))}
    return json.dumps(out, ensure_ascii=False, sort_keys=True) or "{}"


def main() -> None:
    unit, form, level = sys.argv[1], sys.argv[2], int(sys.argv[3])
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    env = make_env()
    coord = Coordinate(subject="math", unit=unit, form=form, level=level)
    print(f"=========== {unit}.{form}.Lv{level} ===========")
    for seed in range(1, n + 1):
        r = build_mr(coord, seed, env)
        if not r.ok or r.mr is None:
            print(f"seed {seed}: FAIL {r.error}")
            continue
        mr = r.mr
        text = env.render_text(mr) if hasattr(env, "render_text") else None
        sq = mr.sub_questions[0]
        ans = getattr(sq.answer, "text", None) or getattr(sq.answer, "value_display", "")
        print(f"\n[seed {seed}]  型={pattern_key(mr.params)}")
        print(f"  given  : {mr.given}")
        print(f"  問い   : {sq.prompt_text if hasattr(sq, 'prompt_text') else ''}")
        print(f"  答え   : {str(ans)[:160]}")
        if text:
            print(f"  文     : {text}")


if __name__ == "__main__":
    main()
