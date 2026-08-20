"""dup_rate から**表層（点名・人名・品物）を外したら**どうなるかを、全セルで測る。

## なぜ測るのか

`dup_key` は `signature + 正規化 params` のハッシュで、params には点名（`labels`・
`slots`）が入っている。点名を入れたのは「dup を下げるため」だったが、その結果
**数値が完全に同じで頂点名だけ違う問題を、別物として数えている**
（exam_l3.find_value.Lv4 の seed2/3/19 は `side=20, speed=2, area=120` で一致）。

メモリにある「質のゲートの構造的な矛盾」そのもの。直すなら
「dup_key から表層を外す → 超えたセルの**数値の軸を広げる**」だが、
広げる作業に入る前に**何セルが超えるのか**を知らないと見積もれない。

実行:
  .venv/bin/python records/work/measure_dup_without_labels.py [--seeds N]
"""
from __future__ import annotations

import argparse
import glob
import json

import yaml

from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env
from engine_paths import FAMILIES_DIR  # エンジンの場所は1か所で解決する

# 表層＝答えにも解き方にも効かない見た目だけの軸。build_corpus の `_FILLER_HINTS`
# と同じ考え方に、図形の点名（labels/slots/points）を足したもの。
_SURFACE_HINTS = (
    "label", "slot", "point", "name", "person", "subject", "item",
    "color", "place", "object", "scene", "unit",
)
_THRESHOLD = 0.20


def _core(params: dict) -> str:
    core = {k: v for k, v in params.items() if not any(h in k for h in _SURFACE_HINTS)}
    return json.dumps(core, sort_keys=True, ensure_ascii=False, default=str)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=100)
    args = ap.parse_args()
    env = make_env()

    cells = []
    for path in sorted(glob.glob(str(FAMILIES_DIR / "*.yaml"))):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit, form = doc["family"].removeprefix("math.").rsplit(".", 1)
        for lv in (doc.get("levels") or {}):
            cells.append((unit, form, int(lv)))

    over: list[tuple[str, float, float]] = []
    n_measured = 0
    for unit, form, lv in cells:
        coord = Coordinate(subject="math", unit=unit, form=form, level=lv)
        full, core = [], []
        for seed in range(1, args.seeds + 1):
            r = build_mr(coord, seed, env)
            if r.mr is None:
                continue
            full.append(json.dumps(r.mr.params, sort_keys=True, ensure_ascii=False, default=str))
            core.append(_core(r.mr.params))
        if not full:
            continue
        n_measured += 1
        dup_now = 1 - len(set(full)) / len(full)
        dup_core = 1 - len(set(core)) / len(core)
        if dup_core > _THRESHOLD:
            over.append((f"{unit}.{form}.Lv{lv}", dup_now, dup_core))

    print(f"測ったセル {n_measured} 個（seeds={args.seeds}・閾値 {_THRESHOLD}）")
    print(f"**表層を外すと閾値を超えるセル: {len(over)} 個**\n")
    print(f"{'セル':<34}{'現行':>8}{'表層なし':>10}")
    for cell, a, b in sorted(over, key=lambda x: -x[2]):
        print(f"{cell:<34}{a:>8.2f}{b:>10.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
