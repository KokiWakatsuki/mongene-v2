"""G-SC3（骨格）— 場面文の言い方が、関係と食い違っていないか。

## なぜこれを見るか

場面を量産するときに壊れるのは「日本語だけが違う問題」ではなく、
**日本語が関係と食い違う問題**である。checker は同じ立式コードをもう一度通すだけ
なので、日本語がどうであれ必ず一致する＝**構造的に検出できない**（charter §4 作業2）。
実際に7回のセッションを生き延びた欠陥がこれで、g3_l37 は「2等分」と書いてあるのに
解いているのは等積だった。どのゲートも通っていた。

## 何を見るか

関係ごとに宣言された「必ずある言い方（並びのそれぞれについて、どれか1つ）」と
「あってはならない言い方」を、場面文（`given.scenario` と小問文）に当てる。
宣言は recipe 側の `RELATION_PHRASES`（関係の隣に置く＝場面を足すとき同じ file を触る）。

実行:
  .venv/bin/python records/work/check_scene_skeleton.py [--seeds N]
  .venv/bin/python records/work/check_scene_skeleton.py --self-test
"""
from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env

sys.path.insert(0, "records/work")

_Phrases = Mapping[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]]


def _declared() -> dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]]:
    """層に割れた recipe から `RELATION_PHRASES` を集める。

    ★同じ `scenario_kind` を2つの module が使っていることがある
    （`price_count_diff` は1元1次と連立の両方にある）。同じ宣言なら問題ないが、
    **食い違っていたら混ぜずに落とす**——黙って片方で上書きすると、どちらを
    見ているのか分からなくなる。
    """
    from engine.packs.math.recipes import (  # noqa: PLC0415
        word_problem_expression,
        word_problem_linear,
        word_problem_proportion_frequency,
        word_problem_quadratic,
        word_problem_system,
    )

    out: dict[str, tuple] = {}
    clash: list[str] = []
    for mod in (word_problem_linear, word_problem_system,
                word_problem_proportion_frequency, word_problem_quadratic,
                word_problem_expression):
        for kind, spec in mod.RELATION_PHRASES.items():
            if kind in out and out[kind] != spec:
                clash.append(kind)
            out[kind] = spec
    if clash:
        raise ValueError(f"同じ scenario_kind に食い違う宣言: {sorted(set(clash))}")
    return out


def scene_phrases() -> dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]]:
    """場面ごとの宣言（`scenes.SceneSpec` の requires / forbids）。

    関係の不変（`RELATION_PHRASES`）とは別に、**場面の側の不変**もある
    （入園料の場面なら「入園料」「大人」「子ども」が出ていること）。
    場面を足したら `scenes.py` にこれも書く＝触るのは1 file のまま。
    """
    from engine.packs.math.recipes.scenes import SCENES  # noqa: PLC0415

    return {s.id: (s.requires, s.forbids) for s in SCENES}


def violations(kind: str, text: str, phrases: _Phrases,
               scene: str = "", scenes: _Phrases | None = None) -> list[str]:
    """1つの場面文を見る。返すのは違反の並び（空なら合格）。

    `scene` があれば、その場面が宣言した言い方も合わせて見る。
    """
    spec = phrases.get(kind)
    if spec is None:
        return [f"{kind}: 宣言が無い（場面を足したら RELATION_PHRASES にも足す）"]
    requires, forbids = spec
    if scene and scenes is not None:
        if scene not in scenes:
            return [f"{scene}: 場面の宣言が無い（scenes.py に requires を書く）"]
        s_req, s_forbid = scenes[scene]
        requires = requires + s_req
        forbids = forbids + s_forbid
    bad: list[str] = []
    for alternatives in requires:
        if not any(a in text for a in alternatives):
            bad.append(f"{kind}: どれも出ていない {list(alternatives)}")
    bad.extend(f"{kind}: 出てはいけない {word!r}" for word in forbids if word in text)
    return bad


def _cells() -> list[tuple[str, str, int]]:
    from build_corpus import load_cells  # noqa: PLC0415

    return [(u, f, lv) for u, f, lv, _c, _e, _fl in load_cells() if f == "word_problem"]


def self_test(phrases: _Phrases) -> int:
    """合成した場面文で、**落ちる場合も通る場合も**出ることを確かめる。"""
    fails = 0
    cases: list[tuple[str, str, str, bool]] = [
        # (名前, kind, 場面文, 合格するか)
        ("総数が与えられている", "price_count",
         "1個130円のりんごと1個110円のレモンを合わせて10個買った。代金は1200円。", True),
        ("総数の言い方が無い", "price_count",
         "1個130円のりんごと1個110円のレモンを10個買った。代金は1200円。", False),
        ("差の関係に「合わせて」が混ざる", "price_count_diff",
         "りんごとレモンを合わせて買った。レモンはりんごより3個多く、代金は1200円。", False),
        ("差の関係（正しい）", "price_count_diff",
         "りんごとレモンを買った。レモンはりんごより3個多く、代金は1200円。", True),
        ("配る関係に余りが無い", "surplus_shortage",
         "何人かの生徒に画用紙を配る。1人に3枚ずつ配ると2枚足りない。", False),
        # ★「ずつ」を素で禁じると、正しい日本語の「それぞれ何gずつ混ぜれば」に当たる。
        # 禁じたいのは**配る意味**の「ずつ」なので「ずつ配」「ずつ座」で指す。
        ("問いの「それぞれ何gずつ」は許す", "salt_mixture",
         "5%の食塩水と14%の食塩水を混ぜて9%の食塩水を900gつくりたい。"
         "それぞれ何gずつ混ぜればよいか求めよ。", True),
        ("配る意味の「ずつ」は落とす", "salt_mixture",
         "食塩水を混ぜる。1人に3gずつ配ると2g余る。", False),
    ]
    for name, kind, text, want_ok in cases:
        got = violations(kind, text, phrases)
        ok = (not got) == want_ok
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: "
              f"期待={'合格' if want_ok else '違反'} / 実際={got or '合格'}")
    unknown = violations("そんな関係は無い", "文", phrases)
    ok = bool(unknown)
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}宣言の無い関係は落とす: {unknown}")
    return fails


def main(argv: Sequence[str]) -> int:
    bootstrap()
    phrases = _declared()
    scenes = scene_phrases()
    if "--self-test" in argv:
        return 1 if self_test(phrases) else 0
    seeds = 5
    if "--seeds" in argv:
        seeds = int(argv[argv.index("--seeds") + 1])
    env = make_env()
    bad: list[str] = []
    n_checked = 0
    kinds_seen: set[str] = set()
    for unit, form, level in _cells():
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        for seed in range(1, seeds + 1):
            # ★`generate` の戻りは**描画済みの結果**で `params` を持たない。
            # そこを見て「1件も見ていない」を出した——0件を返す走査は、まず
            # 検査が動いているかを疑う。params と場面文は MR から取る。
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            # ★式の軸（`form`）があれば**そちらが関係の名前**（1つの関係に式が
            # 2通り以上あるとき、要求する言い方が変わる）。
            kind = str(r.mr.params.get("form", "")
                       or r.mr.params.get("scenario_kind", ""))
            if not kind or kind not in phrases:
                continue        # 層に割っていない recipe のセルは対象外
            kinds_seen.add(kind)
            n_checked += 1
            # 場面文と、小問が読む文（`ask_formulation` / `ask_value` など）。
            text = " ".join(
                [*(str(v) for v in r.mr.given.values()),
                 *(str(v) for v in r.mr.context_slots.values())]
            )
            scene = str(r.mr.params.get("scene", ""))
            for v in violations(kind, text, phrases, scene, scenes):
                bad.append(f"{unit}.{form}.Lv{level} seed{seed}"
                           f"{'[' + scene + ']' if scene else ''}: {v}")
    print(f"見た問題 {n_checked} 件 / 関係 {len(kinds_seen)} 種"
          f"（宣言は {len(phrases)} 種）/ seed 1..{seeds}")
    if len(kinds_seen) < len(phrases):
        print(f"  一度も出なかった関係: {sorted(set(phrases) - kinds_seen)}")
    if not n_checked:
        print("=== 1件も見ていない＝検査が動いていない ===")
        return 1
    if bad:
        print(f"=== 骨格の食い違い {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== 骨格の食い違いは無い ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
