"""G-SC4（単位・共起）— 語と助数詞、人と物の言い方が対になっているか。

## ① 品物と助数詞が対か

場面文は「1{助数詞}{値段}円の{品名}」の形で品名と助数詞を並べる。ところが
`_scene_price_count` のように**1つの助数詞を2つの品名に使い回す**場面がある。
いまは g1_l25 Lv2 のカタログが全部「個」なので合っているが、そこへ「ノート|冊」を
足した瞬間に「1個110円のノート」が出る。**カタログの中身に依存した暗黙の前提**で、
どこにも書かれていない。

見る形: **その回に引かれた品名**（`slots` に入っている）について、場面文が助数詞を
使って数えているなら、**その品名の助数詞が使われていること**。
宣言は増やさない——助数詞はカタログの `品名|助数詞` が持っているものを読む。

★ここは2回外した。
  1. カタログの品名を**場面文の部分一致**で探したので、「クリアファイル」の中の
     「ファイル」（冊）や「ビー玉」の中の「玉」（個）に当たって誤検出した。
     → **その回に引かれた品名だけ**を見る（`slots` が持っている）
  2. 品名が出ていても**数えていない**場面がある（「1mの重さが3gのリボン」＝長さで測る／
     「長方形のカードの面積」＝形として出る）。助数詞が要るのは数えるときだけ。
     → 場面文が助数詞を1つも使っていないなら見ない

## ② 人に「いる」・物に「ある」

「がいる」の直前は人、「がある」の直前は人でないこと。
人の語はカタログ（`person`・`name_*` などの slots に入る値）から集める。

## ③ 答えの単位

**助数詞と一致するとは限らない**（実測: 答えが「円」で助数詞が個/冊/本/枚、
答えが「人」で助数詞が「枚」＝配る物の助数詞）。等しさを要求するのは誤りなので、
ここでは見ない。関係ごとの妥当性は G-SC5（`RELATION_BOUNDS`）が持つ。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/check_scene_words.py [--seeds N]
  PYTHONPATH=engine_core .venv/bin/python records/work/check_scene_words.py --self-test
"""
from __future__ import annotations

import glob
import sys

import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env

sys.path.insert(0, "records/work")
from engine_paths import FAMILIES_DIR  # エンジンの場所は1か所で解決する

# 助数詞（閉じた言語の事実。カタログの写しではない）。
_COUNTERS = frozenset(
    {"個", "本", "枚", "冊", "台", "匹", "頭", "着", "足", "杯", "皿", "点"}
)
# 人を指す slots の鍵（engine 自身の名づけ）。
_PERSON_KEYS = ("person", "name_", "first", "second", "student", "child")


def catalog_pairs() -> dict[str, str]:
    """カタログの `品名|助数詞` から {品名: 助数詞}。

    `|` は場所の対（`家|駅`）や場面文にも使われているので、**2つめが助数詞のもの
    だけ**を採る。助数詞の集合は `_COUNTERS`（言語の事実）で、カタログの写しではない。
    """
    out: dict[str, str] = {}
    for path in sorted(glob.glob(str(FAMILIES_DIR / "*.yaml"))):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        for spec in (doc.get("levels") or {}).values():
            for value in (spec.get("params") or {}).values():
                if not isinstance(value, list):
                    continue
                for tok in value:
                    if not isinstance(tok, str) or "|" not in tok:
                        continue
                    parts = tok.split("|")
                    if len(parts) >= 2 and parts[1] in _COUNTERS:
                        out[parts[0]] = parts[1]
    return out


def person_words(slots_seen: dict[str, set[str]]) -> set[str]:
    """人を指す語（`slots` の鍵で選ぶ＝engine 自身の名づけ）。"""
    out: set[str] = set()
    for key, values in slots_seen.items():
        if any(h in key for h in _PERSON_KEYS):
            out |= values
    return out


def violations(text: str, pairs: dict[str, str], persons: set[str],
               drawn: tuple[str, ...] = ()) -> list[str]:
    """1つの場面文を見る。返すのは違反の並び（空なら合格）。

    `drawn` はその回に引かれた品名（`slots` の値）。渡さないと何も見ない
    ——部分一致で探すと「クリアファイル」の中の「ファイル」に当たる。
    """
    bad: list[str] = []
    counts = {c for c in _COUNTERS if c in text}
    if counts:      # 助数詞を1つも使っていない場面は「数えていない」＝見ない
        for item in drawn:
            counter = pairs.get(item)
            if counter and counter not in counts:
                bad.append(f"品名 {item!r} を {sorted(counts)} で数えている"
                           f"（正しくは {counter!r}）")
    for marker, want_person in (("がいる", True), ("がある", False)):
        idx = text.find(marker)
        while idx > 0:
            before = text[:idx]
            hit = next((p for p in persons if before.endswith(p)), None)
            if want_person and hit is None:
                bad.append(f"「がいる」の直前が人でない: …{before[-8:]!r}")
            if not want_person and hit is not None:
                bad.append(f"「がある」の直前が人（{hit}）")
            idx = text.find(marker, idx + 1)
    return bad


def self_test(pairs: dict[str, str], persons: set[str]) -> int:
    fails = 0
    cases = [
        ("助数詞が対（個）", "1個130円のりんごと1個110円のレモンを合わせて10個買った。",
         ("りんご", "レモン"), True),
        ("品名に合わない助数詞", "あるノートをn個仕入れ、1個あたりa円で売った。",
         ("ノート",), False),
        ("助数詞が2種類とも出ている", "1冊130円のノートと1本110円のえん筆を買った。",
         ("ノート", "えん筆"), True),
        # ★引かれていない品名を部分一致で拾わない（クリアファイル／ファイル）。
        ("長い品名の中に短い品名がある",
         "ボールペンを何本かとクリアファイルを何枚か買った。", ("ボールペン",), True),
        # ★数えていない場面は見ない（長さで測る・形として出る）。
        ("数えていない品名（長さで測る）", "1mの重さが3gのリボンがある。", ("リボン",), True),
        ("人に「がいる」", "分速80mで歩く生徒がいる。", (), True),
        ("物に「がいる」", "2Lの水そうがいる。", (), False),
        ("人に「がある」", "分速80mで歩く生徒がある。", (), False),
    ]
    for name, text, drawn, want_ok in cases:
        got = violations(text, pairs, persons, drawn)
        ok = (not got) == want_ok
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: "
              f"期待={'合格' if want_ok else '違反'} / 実際={got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    from build_corpus import load_cells  # noqa: PLC0415

    pairs = catalog_pairs()
    seeds = 20
    if "--seeds" in argv:
        seeds = int(argv[argv.index("--seeds") + 1])
    env = make_env()
    # 人の語は実物の slots から集める（1周めで集めて2周めで見る）。
    slots_seen: dict[str, set[str]] = {}
    texts: list[tuple[str, str, tuple[str, ...]]] = []
    cells = [(u, f, lv) for u, f, lv, _c, _e, _fl in load_cells() if f == "word_problem"]
    for unit, form, level in cells:
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        for seed in range(1, seeds + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            slots = r.mr.params.get("slots")
            if isinstance(slots, dict):
                for k, v in slots.items():
                    slots_seen.setdefault(k, set()).add(str(v))
            drawn = tuple(str(v) for v in (slots or {}).values()) \
                if isinstance(slots, dict) else ()
            texts.append((f"{unit}.{form}.Lv{level} seed{seed}",
                          " ".join(str(v) for v in r.mr.given.values()), drawn))
    persons = person_words(slots_seen)
    if "--self-test" in argv:
        return 1 if self_test(pairs, persons) else 0
    print(f"品名と助数詞の組 {len(pairs)} / 人の語 {len(persons)} / 場面文 {len(texts)}")
    if not pairs or not persons or not texts:
        print("=== 材料がそろっていない＝検査が動いていない ===")
        return 1
    bad: list[str] = []
    for label, text, drawn in texts:
        bad.extend(f"{label}: {v}" for v in violations(text, pairs, persons, drawn))
    if bad:
        print(f"=== 語と助数詞の食い違い {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== 語と助数詞の食い違いは無い ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
