"""面③ の作業表を作る。`scan_step_values.py` の判定を使い、**ソースの位置つき**で出す。

出力は 1 行 1 op（TSV）:

    ファイル:行  op  判定  narration  result_display  セル数  代表セル

ファイル順・行順に並ぶので、上から順に直せる。

    .venv/bin/python records/work/step_worklist.py > records/work/worklist.tsv
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from engine.eval._harness import build_mr, capability_cells, make_env

sys.path.insert(0, "records/work")
from engine_paths import PACKS_DIR  # エンジンの場所は1か所で解決する
from scan_step_values import classify  # noqa: E402

_SEEDS = 2


def _op_locations() -> dict[str, list[str]]:
    """op 名 → 「ファイル:行」（`op="…"` が書かれている場所）。"""
    out: dict[str, list[str]] = defaultdict(list)
    pat = re.compile(r'op=["\']([a-z0-9_]+)["\']')
    for p in sorted(PACKS_DIR.rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = pat.search(line)
            if m:
                out[m.group(1)].append(f"{p}:{i}")
    return out


def main() -> int:
    env = make_env()
    loc = _op_locations()
    seen: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    verdict_of: dict[tuple[str, str, str], str] = {}

    for coord in capability_cells(env):
        for seed in range(1, _SEEDS + 1):
            res = build_mr(coord, seed, env)
            if not res.ok:
                continue
            for sq in res.mr.sub_questions:
                for st in sq.steps:
                    v = classify(st.narration, st.result_display)
                    if not v:
                        continue
                    key = (st.op, st.narration, st.result_display)
                    verdict_of[key] = v
                    seen[key].add(f"{coord.unit}.{coord.form}.Lv{coord.level}")

    rows = []
    for (op, nar, disp), cells in seen.items():
        where = ";".join(loc.get(op, [])) or "?"
        rows.append((where, op, verdict_of[(op, nar, disp)], nar, disp, len(cells),
                     ",".join(sorted(cells)[:3])))
    rows.sort()
    print("place\top\tverdict\tnarration\tresult_display\tn_cells\tcells")
    for r in rows:
        print("\t".join(str(x) for x in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
