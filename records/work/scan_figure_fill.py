"""方眼の図で、**描かれたものが枠のどれだけを占めるか**を測る。

## なぜ要るか

座標平面は縦横等スケールで、しかも原点が見えるように最小の広さを確保する。
そのため**データが原点から遠く、かつ小さいとき**、枠のほとんどが空白になる。
実例（g2_l23 Lv2）: (-4,-15)〜(-3,-11) の線分1本に対して枠が -12..12 × -16..7。
線分は枠の 3% しか占めず、印刷すると何も無い方眼に見える。

座標が正しいかは `check_figure_matches_givens.py` が見ている。こちらは
**読めるか**を見る——同じ図の別の面で、座標の照合では絶対に出てこない。

出すのは占有率（データの外接矩形の面積 ÷ 枠の面積）。閾値は置かず、小さい順に
並べて出す（どこで切るかは図を見て決める）。

実行:
  .venv/bin/python records/work/scan_figure_fill.py [--seeds N]
"""
from __future__ import annotations

import sys

from engine.core.contracts import Unsupported
from engine.eval._harness import build_mr, capability_cells, family_of, make_env
from engine.packs.math.visuals.graph import (
    _parse_point,
    compute_grid_spec_from_params,
)


def _fill_ratio(params: dict) -> float | None:
    pts_raw = list(params.get("pts") or [])
    pts_raw += list(params.get("bbox_pts") or [])
    if len(pts_raw) < 2:
        return None
    pts = [_parse_point(s) for s in pts_raw]
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    spec = compute_grid_spec_from_params(params)
    w, h = spec.x_hi - spec.x_lo, spec.y_hi - spec.y_lo
    if w <= 0 or h <= 0:
        return None
    # 幅・高さのどちらかが 0 の並び（水平・垂直に並ぶ点）でも「細長さ」を見たいので、
    # 面積比ではなく**辺ごとの比の小さいほう**を使う。
    return min((max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h)


def main() -> int:
    seeds = 3
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    env = make_env()
    rows: list[tuple[float, str]] = []
    looked = 0
    for coord in capability_cells(env):
        worst: tuple[float, int] | None = None
        for seed in range(1, seeds + 1):
            try:
                r = build_mr(coord, seed, env)
            except Exception:  # noqa: BLE001 - 図を持たないセルは params が違う
                continue
            mr = getattr(r, "mr", r)
            if isinstance(mr, Unsupported) or mr.visual_plan is None:
                continue
            # **直線・曲線のセルは測らない。** そこでの `pts` は枠の広さを決める
            # ための2点で、描かれる線は枠の端から端まで伸びる。pts の外接矩形を
            # 「描かれたもの」とみなすと、正しく枠いっぱいの直線を 6% と報告する
            # ——道具が見ているものと図に描かれているものが違う。
            kinds = {e.kind for e in mr.visual_plan.elements}
            if not (kinds & {"polygon", "point", "segment"}) or (kinds & {"line", "curve"}):
                continue
            try:
                ratio = _fill_ratio(mr.params)
            except Exception:  # noqa: BLE001 - 方眼以外の図（立体・作図）は pts を持たない
                continue
            if ratio is None:
                continue
            looked += 1
            if worst is None or ratio < worst[0]:
                worst = (ratio, seed)
        if worst is not None:
            rows.append((worst[0], f"{family_of(coord)}.Lv{coord.level} (seed {worst[1]})"))

    rows.sort()
    # **比べる相手の個数を必ず出す。** 0 件のとき、図が無いのか走査が動いていないのかを
    # 区別できるようにする。
    print(f"方眼の図を持つセル {len(rows)}／測った図 {looked} 枚（seeds={seeds}）\n")
    print("占有率の小さい順（枠に対して、描かれたものが占める辺の割合）:")
    for ratio, name in rows[:25]:
        print(f"  {ratio:5.1%}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
