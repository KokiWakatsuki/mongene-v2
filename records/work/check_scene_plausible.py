"""G-SC5（場面の妥当性）— 引いた数が、場面として成り立つ大きさか。

「式としては解けるが、場面としてありえない」問題が実際に出ていた（斜面432m・
円周角231°・歩いて30km・面積312cm²の畑）。**読解でしか捕まらない**と思われていたが、
数の上下限は宣言できる。宣言は recipe 側の `RELATION_BOUNDS`（関係の隣）。

★**わざと二重にする。** 上下限は候補列挙（`*_candidates`）とは別の原理で書いてある
——列挙のほうを緩めたときに、ここが鳴るのが目的（double-solve と同じ考え）。

## 上限は「場面としてありえる限界」で、実物より広いのが正常

ここが見るのは**ありえなさ**であって、いまの挙動を凍結することではない
（凍結は golden の仕事）。だから実測の最大より上限が広いのは当たり前で、
そのぶんが**定義域を広げたときの余裕**になる。

ただし桁で離れていると（実測の10倍以上）、その宣言はもう何も言っていない。
そこだけ一覧に出す——黙って通すと、検査があることだけが残って中身が無くなる。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/check_scene_plausible.py [--seeds N]
  PYTHONPATH=engine_core .venv/bin/python records/work/check_scene_plausible.py --self-test
"""
from __future__ import annotations

import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env

sys.path.insert(0, "records/work")

# 鍵は (recipe の名前, scenario_kind)。
# ★**scenario_kind だけでは足りない。** `price_count_diff` は1元1次（word_problem_linear）
# と連立（word_problem_system）の**両方にあって中身が違う**（前者は本文に代金 `cost`、
# 後者は合計 `total` が出る）。名前で1つに畳むと、どちらかの宣言が消える。
_Bounds = dict[tuple[str, str], dict[str, tuple[float, float]]]


def declared() -> _Bounds:
    """層に割れた recipe から `RELATION_BOUNDS` を集める（食い違ったら落とす）。"""
    from engine.packs.math.recipes import (  # noqa: PLC0415
        word_problem_expression,
        word_problem_linear,
        word_problem_proportion_frequency,
        word_problem_quadratic,
        word_problem_system,
    )

    out: _Bounds = {}
    for mod in (word_problem_linear, word_problem_system,
                word_problem_proportion_frequency, word_problem_quadratic,
                word_problem_expression):
        for kind, rows in mod.RELATION_BOUNDS.items():
            out[(mod.RECIPE_NAME, kind)] = {name: (lo, hi) for name, lo, hi in rows}
    return out


def violations(key: tuple[str, str], numbers: dict, bounds: _Bounds) -> list[str]:
    """1つの MR の数を見る。返すのは違反の並び（空なら合格）。"""
    kind = key[1]
    spec = bounds.get(key)
    if spec is None:
        return [f"{kind}: 宣言が無い（場面を足したら RELATION_BOUNDS にも足す）"]
    bad: list[str] = []
    for name, raw in numbers.items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue        # 文字（変数名）は数ではない
        if name not in spec:
            bad.append(f"{kind}: 数 {name!r} の上下限が宣言されていない")
            continue
        lo, hi = spec[name]
        if not lo <= value <= hi:
            bad.append(f"{kind}: {name}={value:g} が {lo:g}〜{hi:g} の外")
    return bad


def self_test(bounds: _Bounds) -> int:
    fails = 0
    L = "math.word_problem_linear_equation"
    S = "math.word_problem_system_equations"
    Q = "math.word_problem_quadratic"
    # ★recipe の名前は推測せず実物から取る。最初 Q を
    # "math.word_problem_quadratic_equation" と書いていて、2件が「宣言が無い」で
    # 通ってしまい、上下限の判定を一度も通していなかった（合成データが当たっていない）。
    cases = [
        ("歩く速さで時速60km", (S, "distance_time"),
         {"speed_walk": "60", "speed_bike": "12", "distance": "20", "total_time": "3"}, False),
        ("まともな通学", (S, "distance_time"),
         {"speed_walk": "4", "speed_bike": "12", "distance": "20", "total_time": "3"}, True),
        ("濃度100%の食塩水", (S, "salt_mixture"),
         {"percent_a": "100", "percent_b": "20", "percent_mix": "60", "weight": "900"}, False),
        ("連続する2数の積が13万", (Q, "consecutive_integers"),
         {"product": "132860", "gap": "1"}, False),
        ("宣言していない数が増えた", (Q, "consecutive_integers"),
         {"product": "56", "gap": "1", "newcomer": "3"}, False),
    ]
    for name, key, numbers, want_ok in cases:
        got = violations(key, numbers, bounds)
        ok = (not got) == want_ok
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: "
              f"期待={'合格' if want_ok else '違反'} / 実際={got or '合格'}")
    unknown = violations((L, "そんな関係は無い"), {"x": "1"}, bounds)
    ok = bool(unknown)
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}宣言の無い関係は落とす: {unknown}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    bounds = declared()
    if "--self-test" in argv:
        return 1 if self_test(bounds) else 0
    seeds = 20
    if "--seeds" in argv:
        seeds = int(argv[argv.index("--seeds") + 1])
    from build_corpus import load_cells  # noqa: PLC0415

    env = make_env()
    bad: list[str] = []
    n_checked = 0
    observed: dict[tuple[tuple[str, str], str], float] = {}
    for unit, form, level, _c, _e, _f in load_cells():
        if form != "word_problem":
            continue
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        for seed in range(1, seeds + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            key = (r.mr.provenance.recipe, str(r.mr.params.get("scenario_kind", "")))
            numbers = r.mr.params.get("numbers")
            if key not in bounds or not isinstance(numbers, dict):
                continue        # 層に割っていない recipe のセルは対象外
            n_checked += 1
            for name, raw in numbers.items():
                try:
                    observed[(key, name)] = max(
                        observed.get((key, name), float("-inf")), float(raw)
                    )
                except (TypeError, ValueError):
                    continue
            for v in violations(key, numbers, bounds):
                bad.append(f"{unit}.{form}.Lv{level} seed{seed}: {v}")
    print(f"見た問題 {n_checked} 件 / 関係 {len(bounds)} 種 / seed 1..{seeds}")
    if not n_checked:
        print("=== 1件も見ていない＝検査が動いていない ===")
        return 1
    loose = [
        f"{key[1]}.{name}: 上限 {spec[name][1]:g} に対し実物の最大 {top:g}"
        for (key, name), top in sorted(observed.items())
        if (spec := bounds.get(key)) and name in spec
        and top * 10 < spec[name][1] and spec[name][1] > 10
    ]
    if bad:
        print(f"=== 場面として成り立たない数 {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== 場面として成り立たない数は無い ===")
    if loose:
        print(f"\n上限が実物の10倍以上ある宣言 {len(loose)} 件"
              "（もう何も言っていない＝場面の限界を書き直す）:")
        for line in loose[:30]:
            print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
