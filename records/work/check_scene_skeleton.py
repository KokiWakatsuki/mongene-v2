"""G-SC3（骨格）— 場面文の言い方が、関係と食い違っていないか。

## なぜこれを見るか

場面を量産するときに壊れるのは「日本語だけが違う問題」ではなく、
**日本語が関係と食い違う問題**である。checker は同じ立式コードをもう一度通すだけ
なので、日本語がどうであれ必ず一致する＝**構造的に検出できない**（charter §4 作業2）。
実際に7回のセッションを生き延びた欠陥がこれで、g3_l37 は「2等分」と書いてあるのに
解いているのは等積だった。どのゲートも通っていた。

## 何を見るか

「必ずある言い方（並びのそれぞれについて、どれか1つ）」と「あってはならない言い方」を、
場面文（`given.scenario` と小問文）に当てる。宣言は**2か所にあり、役目が違う**。

  - 関係の側 `RELATION_PHRASES`（recipe 内・関係の隣）
    ＝**式が要求する**言い方。「積」「面積」「合わせて」
  - 場面の側 棚の `requires` / `forbids`（`SceneSpec.requires`）
    ＝**この場面に固有の**言い方。「入園料」「小さい方」「1辺」

★2つに分かれているのは、1つの関係に場面が何通りも乗るから。関係の宣言だけでは
同じ関係の2つの場面を区別できない（どちらも通る）。棚の在り処は `scene_shelves.py`。

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
    """場面ごとの宣言（棚の `requires` / `forbids`）。

    関係の不変（`RELATION_PHRASES`）とは別に、**場面の側の不変**もある
    （入園料の場面なら「入園料」「大人」「子ども」が出ていること）。
    場面を足したら棚にこれも書く＝触るのは1 file のまま。

    ★**棚は module ごとに分かれている**（`scenes.SCENES` と
    `word_problem_quadratic.SCENE_SHELF`）。以前ここは `scenes.SCENES` だけを
    見ていたので、2次の場面に当たると「場面の宣言が無い」を20件出した——
    宣言が無いのではなく**別の棚にあった**。棚の在り処は
    `scene_shelves.py` が1か所で答える。
    """
    from scene_shelves import phrases_by_scene  # noqa: PLC0415

    return phrases_by_scene()


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
            return [f"{scene}: 場面の宣言が無い"
                    "（棚の SceneSpec に requires を書く。棚の一覧は scene_shelves.py）"]
        s_req, s_forbid = scenes[scene]
        requires = requires + s_req
        forbids = forbids + s_forbid
    bad: list[str] = []
    for alternatives in requires:
        if not any(a in text for a in alternatives):
            bad.append(f"{kind}: どれも出ていない {list(alternatives)}")
    bad.extend(f"{kind}: 出てはいけない {word!r}" for word in forbids if word in text)
    return bad


def hint_violations(kind: str, text: str, phrases: _Phrases,
                    scene: str = "", scenes: _Phrases | None = None) -> list[str]:
    """ヒントのもとになる**概念のラベル**に、あってはならない言い方が出ていないか。

    ★`requires` は当てない。ラベルは場面文を言い直すものではないので、
    「必ずある言い方」を要求すると正しいラベルまで落ちる。
    見るのは `forbids` だけ——**ラベルが場面と食い違っている**ときに鳴る。

    ★これは実際に起きた欠陥から足した。g1_l36 Lv3 の場面は 2026-08-19 に
    「先に出た人を追いかける」（中2 の1次関数だった）から「水そう」へ変えたが、
    **概念の label を直し忘れていた**。label はそのままヒントとして生徒に出るので、
    水そうの問題に「2人の時間と道のりの関係を式にし、グラフの交点から追いつく
    時間を求める」というヒントが付いていた。
    ゲートも既存の走査もこれを見ていない——**場面文の検査はヒントを見ていなかった**。
    """
    out: list[str] = []
    spec = phrases.get(kind)
    forbids: tuple[str, ...] = spec[1] if spec else ()
    if scene and scenes is not None and scene in scenes:
        forbids = forbids + scenes[scene][1]
    out.extend(f"{kind}: ヒントに出てはいけない {w!r}" for w in forbids if w in text)
    return out


def _cells() -> list[tuple[str, str, int]]:
    from build_corpus import load_cells  # noqa: PLC0415

    return [(u, f, lv) for u, f, lv, _c, _e, _fl in load_cells() if f == "word_problem"]


def self_test(phrases: _Phrases, scenes: _Phrases | None = None) -> int:
    """合成した場面文で、**落ちる場合も通る場合も**出ることを確かめる。

    ★後半（`scene_cases`）は**場面の側の宣言**を当てる。棚が複数になったので、
    「関係は合っているが場面が言うべきことを言っていない」を捕まえられるかを
    ここで押さえる（実物の走査は 0 件を返すので、それだけでは検査が動いている
    証拠にならない）。
    """
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

    if scenes is None:
        return fails

    # --- 場面の側の宣言（棚をまたぐ）-----------------------------------------
    scene_cases: list[tuple[str, str, str, str, bool]] = [
        # (名前, kind, 場面, 場面文, 合格するか)
        ("長方形（正しい）", "rectangle_area", "rectangle_small",
         "横が縦より3cm長い長方形の紙がある。その面積は40cm²である。縦の長さを x cm とする。", True),
        ("長方形なのに「横」が無い", "rectangle_area", "rectangle_small",
         "縦より3cm長い長方形の紙がある。その面積は40cm²である。", False),
        ("長方形なのに正方形と言う", "rectangle_area", "rectangle_small",
         "横が縦より3cm長い正方形の紙がある。その面積は40cm²である。縦 x cm。", False),
        ("連続する数（正しい）", "consecutive_integers", "consecutive_numbers",
         "連続する2つの正の整数がある。この2数の積は56である。小さい方の数を x とする。", True),
        # ★どちらを x にしたかを言わないと、答えの2つを取り違えても検出できない。
        ("どちらを x にしたか言っていない", "consecutive_integers", "consecutive_numbers",
         "連続する2つの正の整数がある。この2数の積は56である。", False),
        ("数の場面に cm が出る", "consecutive_integers", "consecutive_numbers",
         "連続する2つの正の整数がある。この2数の積は56cmである。小さい方の数を x とする。", False),
        ("正方形の変形（正しい）", "square_cut", "square_reshape",
         "1辺が10cmの正方形がある。縦を x cm 短くし、横を x cm 長くして"
         "長方形をつくったところ、面積が96cm²になった。", True),
        # ★片方だけだと (s−x)(s+x) でなく別の式の場面になる。
        ("「短く」だけで「長く」が無い", "square_cut", "square_reshape",
         "1辺が10cmの正方形がある。縦を x cm 短くして長方形をつくったところ、"
         "面積が96cm²になった。", False),
    ]
    for name, kind, scene, text, want_ok in scene_cases:
        got = violations(kind, text, phrases, scene, scenes)
        ok = (not got) == want_ok
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}場面「{name}」: "
              f"期待={'合格' if want_ok else '違反'} / 実際={got or '合格'}")

    # --- ヒント（概念のラベル）の食い違い ---------------------------------
    # ★実際に起きた欠陥をそのまま置く。g1_l36 の場面は「先に出た人を追いかける」
    # （中2 の1次関数）から水そうへ変わったが、概念の label が直っていなかった。
    hint_cases: list[tuple[str, str, str, str, bool]] = [
        ("直す前のラベル（水そうなのに道のり）", "meet_two_motions", "tank_fill_both",
         "2人の時間と道のりの関係を式にし、グラフの交点から追いつく時間を求める", False),
        ("直した後のラベル", "meet_two_motions", "tank_fill_both",
         "1つの場面から比例と反比例の両方を立式し、2つの量を求める", True),
        # ★ラベルは場面文を言い直すものではないので、`requires` は当てない。
        # 「空の」「水」が無くても落ちてはいけない。
        ("必要な語が無くても落ちない（requires は当てない）", "meet_two_motions",
         "tank_fill_both", "反比例の関係を使って時間を求める", True),
    ]
    for name, kind, scene, label, want_ok in hint_cases:
        got = hint_violations(kind, label, phrases, scene, scenes)
        ok = (not got) == want_ok
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}ヒント「{name}」: "
              f"期待={'合格' if want_ok else '違反'} / 実際={got or '合格'}")

    # ★棚に無い名前は落とす（棚を足し忘れたまま params に名前が載る事故を捕まえる）。
    unknown_scene = violations("rectangle_area", "横が縦より3cm長い長方形。面積40cm²。",
                               phrases, "そんな場面は無い", scenes)
    ok = bool(unknown_scene)
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}棚に無い場面は落とす: {unknown_scene}")
    return fails


def main(argv: Sequence[str]) -> int:
    bootstrap()
    phrases = _declared()
    scenes = scene_phrases()
    if "--self-test" in argv:
        return 1 if self_test(phrases, scenes) else 0
    seeds = 5
    if "--seeds" in argv:
        seeds = int(argv[argv.index("--seeds") + 1])
    env = make_env()
    # 概念 id → 日本語名。ヒントはこれから作られるので、食い違いはここに出る。
    from engine.core.curriculum import load_curriculum  # noqa: PLC0415
    concept_labels = {cid: c.label for cid, c in load_curriculum().concepts.items()}
    bad: list[str] = []
    n_checked = 0
    n_hints = 0
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
            # ★ヒントのもとになる**概念のラベル**も見る。
            # `SubQuestionMR` はヒントを持たない——ヒントはテンプレートが
            # `concept_tags` の日本語名から作る。だから欠陥はラベルの側にある。
            # 場面文の検査はここを見ていなかったので、場面を直してラベルを
            # 直し忘れた食い違いが通り抜けていた（g1_l36 Lv3）。
            labels = " ".join(
                concept_labels[t]
                for sq in r.mr.sub_questions for t in sq.concept_tags
                if t in concept_labels
            )
            if labels:
                n_hints += 1
                for v in hint_violations(kind, labels, phrases, scene, scenes):
                    bad.append(f"{unit}.{form}.Lv{level} seed{seed}"
                               f"{'[' + scene + ']' if scene else ''}: {v}")
    print(f"見た問題 {n_checked} 件（うちヒントつき {n_hints} 件）/ 関係 {len(kinds_seen)} 種"
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
