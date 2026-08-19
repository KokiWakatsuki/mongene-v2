"""場面に着せる語彙を引く（共通の仕掛け。日本語はここに書かない）。

## なぜ別 module か

文章題の recipe は「関係（数の引き方）／語彙の抽選／場面（日本語）」の3層に割る
（記録 records/docs/scene_formulation_charter_2026-08-19.md §3）。語彙の**引き方**は
どの単元でも同じなので、ここに1つだけ置く。**同じ規約を複数の場所に複製しない**——
頂点名から `I` を外す作業で規約が4か所に散っていて、1か所直しても消えなかった。

以前は `word_problem_linear` が事実上この役をしていて、他の recipe がそこから
`_split_pair` などを import していた（`recipes/__init__.py` に import 順の注意書きが
必要になっていた）。ここへ移して、その依存を切る。

## ★引く順番は変えられない

同じ seed から同じ問題が出ることは golden が固定している。語彙を引く位置が動くと
RNG の消費が変わって、**構造だけ変えたつもりで中身も変わる**。だから
`draw_vocab` に渡す手の並びは、割る前のコードが引いていた順のままにする
（順番を測る道具: records/work/scan_scene_draw_order.py）。
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from engine.core.rng import Rng, draw, draw_many


def split_pair(token: str) -> tuple[str, str]:
    """"ノート|冊" → ("ノート", "冊")。"""
    left, _, right = str(token).partition("|")
    return left, right


def draw_pair_token(candidates: list[Any], rng: Rng) -> tuple[str, str]:
    """カタログから1つ引いて `名前|助数詞` を割る（`draw(list(...))` を1回消費）。"""
    return split_pair(str(draw(list(candidates), rng)))


def draw_index(candidates: Sequence[Any], rng: Rng) -> Any:
    """添字で1つ引く（`draw({"int_range": ...})` を1回消費）。

    `draw_pair_token` と**消費の仕方が違う**ので、割る前のコードがどちらを使って
    いたかで選ぶ。取り違えると同じ seed から別の問題が出る。
    """
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def draw_distinct(candidates: list[Any], rng: Rng, k: int) -> list[Any]:
    """候補配列から相異な k 個（文字列はドメイン記法外なので添字で引く）。"""
    idxs = draw_many({"int_range": [0, len(candidates) - 1], "distinct": ["value"]}, rng, k=k)
    return [candidates[int(i)] for i in idxs]


def draw_priced_item(candidates: list[Any], rng: Rng) -> tuple[str, str, int]:
    """`品名|助数詞|下限|上限` から (品名, 助数詞, 値段) を引く。

    値段を品物と無関係に引くと「1本277円の鉛筆」「1本39円の輪ゴム」が出る。
    実物の問題集の値段は 10円刻みで、しかも品物の相場に収まっている。

    **品物→値段の2段で引かず、(品物,値段) の組を平らにして1回で引く。**
    2段だと相場の狭い品物（シール 10〜100 の10通り）が、広い品物（りんご
    100〜300 の21通り）と同じ確率で選ばれ、組の分布が偏って dup_rate が跳ねる。

    ★これは**語彙と数を1回で引く**唯一の場所で、3層にきれいに割れない
    （値段が品物の相場に紐づいているのは場面として正しいので、そのままにする）。
    """
    pairs: list[tuple[str, str, int]] = []
    for tok in candidates:
        name, counter, lo, hi = str(tok).split("|")
        pairs.extend((name, counter, price) for price in range(int(lo), int(hi) + 1, 10))
    idx = int(draw({"int_range": [0, len(pairs) - 1]}, rng))
    return pairs[idx]


# 1手 = (引き方, カタログ, 入れる名前の並び)。カタログの値は `名前|助数詞` の形で
# 詰めてあるので、`|` で割った順に名前へ入る。
#
#   "one"       `draw(list(...))` で1つ引いて `|` で割る
#   "index"     `draw({"int_range": ...})` で1つ引いて `|` で割る（消費が "one" と違う）
#   "distinct2" 相異な2つを引いて、それぞれ `|` で割って順に並べる
#   "priced"    `名前|助数詞|下限|上限` から (名前, 助数詞, 値段) を1回で引く
#               （`draw_priced_item`。**語彙と数を1回で引く**＝分けられない）
#
# カタログは**params の鍵（str）でも、その場に書いた並び（tuple/list）でもよい**。
# 場面の言い方の並び（`("larger", "subtract", "sum")`）のように YAML に載っていない
# ものがあるため。並びを直接書くほうは、その module の定数を渡す。
VocabStep = tuple[str, "str | Sequence[Any]", tuple[str, ...]]


def _catalog(catalog: str | Sequence[Any], p: Mapping[str, Any]) -> list[Any]:
    """カタログを解く（params の鍵ならひく／並びならそのまま）。"""
    return list(p[catalog]) if isinstance(catalog, str) else list(catalog)


def draw_vocab(steps: Sequence[VocabStep], p: Mapping[str, Any], rng: Rng) -> dict[str, str]:
    """宣言どおりに語彙を引く。**場面を足すときはここに1行足すだけ。**

    返す値は**すべて文字列**。相場（値段の上下限・速さの上下限）を一緒に持ってくる手が
    あり、それを受け取るのは Relation だから——`v["speed_lo"]` を `int()` にして使う。
    語彙が数の定義域を決める場面（「歩く」なら時速3〜6km）は実際にあり、
    そこは3層にきれいに割れない（`draw_priced_item` の docstring 参照）。
    """
    out: dict[str, str] = {}
    for how, catalog, names in steps:
        values = _catalog(catalog, p)
        if how == "one":
            parts = str(draw(values, rng)).split("|")
        elif how == "index":
            parts = str(draw_index(values, rng)).split("|")
        elif how == "priced":
            name, counter, price = draw_priced_item(values, rng)
            parts = [name, counter, str(price)]
        elif how == "distinct2":
            parts = [
                piece
                for tok in draw_distinct(values, rng, 2)
                for piece in str(tok).split("|")
            ]
        else:  # pragma: no cover - 宣言の誤りは構成時に落とす
            raise ValueError(f"未知の語彙の引き方: {how}")
        for name, value in zip(names, parts, strict=False):
            out[name] = value
    return out
