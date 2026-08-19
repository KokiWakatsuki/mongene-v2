"""「明らかに違う問題」を、単元・form・Lv ごとに、型を全部出す。

## 何を1問とするか
**セルをまたいだ重複除去はしない。** 同じ単元・form で Lv だけ違えば、型が同じでも
別々に1問出す（Lv 差が数値の範囲だけで付いているセルもあるため）。
1セルの中では、型の数だけ出す。

## 型の見分け方
family YAML の params にある列挙のうち、**話の骨格が変わる軸**だけを型とみなす。
軸か中身かは設計が記録していないので、名前の規約でここに明文化する:

  型の軸  `*_set`（concept_set を除く）・`term_kinds`  ただし人名・題材・品物・場所・
          色を指す `*_set` は中身なので除く（person_pair_set・subject_set など）
  中身    `*_candidates`・`*_range`・`*_domain`・`*_pool`

これに加えて **解く筋道の言葉（narration）** も鍵に混ぜる。YAML に出ない分岐
（g2_l38 Lv3 の「証明する枝」と「反例を出す枝」）はこれでしか拾えない。

## seed の引き方
型は rng が引くので、狙って出せない。**期待する型数だけ出るまで seed を増やす**
（上限あり）。取りこぼしたら `log` に出す——黙って打ち切ると「全部見た」と読めてしまう。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/build_corpus.py
"""
from __future__ import annotations

import glob
import argparse
import json
import os
import re
from pathlib import Path
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import yaml

from engine.core.contracts import (
    Coordinate,
    GenerateRequest,
    ProofAnswer,
    Unsupported,
)
from engine.core.pipeline import generate
from engine.eval._harness import build_mr, make_env

# **出力先は外から差せる。** ここが `records/work/corpus` 固定だったので、
# `engine_core/` だけをメインプロジェクトへ移すと「生成はできるが結果がどこにも
# 残らない」状態になっていた（引き継ぎ書 §3 の穴）。
# 優先順: 引数 --out > 環境変数 MONGENE_CORPUS_DIR > 既定（このリポジトリの場所）。
_DEFAULT_OUT = Path(os.environ.get("MONGENE_CORPUS_DIR", "records/work/corpus"))

# 名前は `_set` でも、中身の差し替えでしかない軸。
_FILLER_HINTS = ("person", "subject", "item", "color", "place", "object", "name")
_SEEDS_PER_TYPE = 60      # 型1つあたり、これだけ seed を引いてみる
_SEED_CAP = 2400          # 1セルの上限


def _answer_text(answer: object) -> str:
    """答えの表示。**選択肢と作図にも文字列を出す**（走査に見えるようにするため）。

    `display` を持つのは数値・式・証明の答えだけで、選択（ChoiceAnswer）は `correct`、
    作図とグラフ（GraphAnswer）は特徴点の並びが答えにあたる。ここが空だと
    「答えが空」が213セルに出て、その中の欠陥（分数の相対度数など）を文面の走査が
    一度も見ないままになる。
    """
    display = getattr(answer, "display", None)
    if display:
        return str(display)
    correct = getattr(answer, "correct", None)
    if correct:
        return str(correct)
    features = getattr(answer, "features", None)
    if features:
        # **`f.kind` を前に足さない。** 足していたので `intersection 交点 (-1, 6)`・
        # `min 最小値 6` と出て、「答えに英語のスロット名が漏れている」と読み違えた。
        # 漏れていたのはこの道具のほうで、engine は `f.display` しか出していない
        # （どの display も日本語のラベルを持っている）。
        # 読む道具が足したものは、読む人には engine の出力と区別できない。
        return "、".join(f.display for f in features)
    return str(getattr(answer, "text", "") or "")


def _conclusion_text(answer: object) -> str:
    """型の鍵に入れる答え（**結論だけ**。導出は入れない）。

    ★`ProofAnswer` は答えの中に**証明の全文**が入っている。これを鍵に入れると
    seed ごとに文面が変わって型が爆発する（実測 g3_l51.proof.Lv3 が 5 → 276、
    g2_l38.proof.Lv3 が 6 → 130）。証明の型は family YAML の `proof_id` / `prop_id`
    が宣言しているので、鍵には入れない。

    区別は engine 自身の宣言（答えのクラス）で行う。鍵の名前や長さでは選ばない。
    """
    if isinstance(answer, ProofAnswer):
        return ""
    return _answer_text(answer)


def type_axes(params: dict) -> list[str]:
    """型の軸になる params のキー。

    **数値だけの列挙は型ではない。** `denominator_set: [2,3,4,5,6,8,9,10]` は
    `x/9 + x/2 = 33` と `x/10 + x/6 = 8` を作り分けるだけで、問題の型は同じである
    （最初これを型と数えて、8型あることにしてしまった）。
    """
    out = []
    for k, v in params.items():
        if not (isinstance(v, list) and len(v) > 1):
            continue
        if not (k.endswith("_set") and k != "concept_set" or k == "term_kinds"):
            continue
        if any(h in k for h in _FILLER_HINTS):
            continue
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            continue  # 数値の列挙＝中身の差し替え
        out.append(k)
    return sorted(out)


def _mask_names(v: object) -> object:
    """点名（連続する大文字）を伏せる。数字と日本語はそのまま。

    型の鍵に使う。`labels` のような表層の軸が鍵に入っていると、名前だけ違う問題が
    別の型になる。文字列以外はそのまま返す（数値の軸は伏せてはいけない）。
    """
    if isinstance(v, str):
        return re.sub(r"[A-Z]", "＊", v)
    if isinstance(v, (list, tuple)):
        return [_mask_names(x) for x in v]
    return v


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")
# 語彙かどうかは「ASCII でない」では決められない。★`given_disp` に入っている
# `1/6×8×(-3.5)` は `×` が ASCII でないので語彙と判定され、**計算式まるごとが
# 伏せ字になって** g1_l6.calculation.Lv2 の3型が1型に潰れた（取りこぼし1件として
# 表に出た）。語彙は**かな・漢字を含む語**である。`×÷²−` や全角記号は語彙ではない。
_JA_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uff66-\uff9d]")


def _mask_surface(v: object, universe: Sequence[str] = ()) -> object:
    """型の鍵に使う表層の伏せ字（語彙＋点名＋数値）。

    順番が要る。語彙は生の値で照合するので、**数を伏せる前に**差し替える
    （`answer_labels` の「12%の食塩水は」は数を伏せると値と一致しなくなる）。
    """
    if isinstance(v, str):
        s = mask_vocab(v, universe) if universe else v
        return _NUMBER_RE.sub("＃", str(_mask_names(s)))
    if isinstance(v, (list, tuple)):
        return [_mask_surface(x, universe) for x in v]
    return v


# ---------------------------------------------------------------------------
# 型を「文型 / 語彙 / 数」に分ける（作業0・charter §4）
# ---------------------------------------------------------------------------
# ★**鍵の名前で「表層らしいもの」を並べて除いてはいけない。** それをやると
# `item_a`（語彙）や `line_cost`（係数の並び）を取りこぼし、100セルすべてが
# seed 数と同じ型数になる（＝走査が動いていない）。ここは**engine 自身の宣言**に
# 従う——recipe は `params["slots"]` を「語彙」、`params["numbers"]` を
# 「場面文に出ている数値」として作っている（word_problem_system.SystemScene）。
#
#   語彙（伏せる）  `slots` の下の値すべて／トップレベルの**日本語を含む文字列**で
#                   型の軸として宣言されていないもの（item_a・statement・answer_labels）
#   構成（残す）    ASCII の識別子（concept=distributive・method=elimination・
#                   scenario_kind）と、型の軸として YAML が宣言したキーの値
#   数（別に数える） `numbers` の下と、文中の数字（既存の `＃` 伏せ字）
#
# `numbers` の下を語彙として伏せないのは、そこに構成の語が混ざるため——
# exam_l5.Lv3 は `numbers.target_quantity` に「和」「積」を入れている（さいころの
# 和が5になる確率と積が6になる確率は、数え上げの筋道が違う＝別の文型）。
# 伏せると型を潰すので、**潰すより多く数える側に倒す**。
_VOCAB_ROOT = "slots"


_ASCII_UNIT_RE = re.compile(r"[A-Za-z]{1,4}")


def _vocab_word(v: str) -> bool:
    """語彙として伏せてよい文字列か。

    - かな・漢字を含む語（品名・人名・場所・助数詞）
    - **数字を含まない短いラテン文字の並び**＝単位（`cm` `km` `g` `L`）と変数の文字。
      ★これを入れないと、答えの「170cm以上180cm未満」と「50回以上55回未満」が
      別の文型になる（`回` は漢字なので伏せるのに `cm` は伏せないため）。

    式は語彙ではない。`1/6×8×(-3.5)` や `3cm²` は数字を含むので外れる
    （「ASCII でない文字を含む」で選んで式まるごと伏せた失敗の再発防止）。
    長いラテン語（`elimination`・`radius`）は構成フラグなので入れない。
    """
    if not v or _NUMBER_RE.fullmatch(v):
        return False
    return bool(_JA_RE.search(v)) or bool(_ASCII_UNIT_RE.fullmatch(v))


def vocab_of(params: Mapping[str, Any], axes: Sequence[str],
             filler_words: Sequence[str] = ()) -> dict[str, str]:
    """語彙 → 差し込む札（`〈鍵〉`）。札は鍵ごとに別なので役割の区別は残る。

    札に使う `〈〉` は ASCII ではないので、あとの数値・点名の伏せ字に食われない。

    `filler_words` は **YAML が「中身」と宣言したカタログの値**（`*_candidates` と
    人名・品物の `*_set`、および値が語彙だったので軸から外したカタログ）。params に
    出てこない語彙がここでしか拾えない——助数詞がその例で、`container_set` に
    `"袋|玉|個"` と詰められていて recipe は `slots` に `袋` と `玉` しか載せない。
    「個」が残ると、品物名だけが違う問題が別の型として数えられる。
    """
    out: dict[str, str] = {}

    def walk(path: str, v: object) -> None:
        if isinstance(v, str):
            # かな・漢字を含まないもの（構成フラグ・単位・式）は語彙ではない。
            if _vocab_word(v):
                out.setdefault(v, f"〈{path}〉")
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(f"{path}.{k}", x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(path, x)

    for k, v in params.items():
        if k in axes:
            continue            # 型の軸として宣言された値は構成である
        if k == _VOCAB_ROOT:
            walk(k, v)          # `slots` の下は深さを問わず語彙
        elif not isinstance(v, dict):
            walk(k, v)          # トップレベルの文字列とその並び（`numbers` は見ない）
    # params 側に札があるものは上書きしない（役割つきの札のほうが情報が多い）。
    for w in filler_words:
        if _vocab_word(w):
            out.setdefault(w, "〈語彙〉")
    return out


def mask_vocab(text: str, universe: Sequence[str]) -> str:
    """語彙を1種類の札（`〈語彙〉`）に差し替える。**長いものから**。

    ★**渡すのはセル共通の語彙集合で、その seed が引いた値ではない。**
    引いた値だけを消すと、伏せ字の当たる場所が seed ごとに変わって、
    **畳むはずの操作が型を割る**（実測3件）:

      `unit="回"` の seed では「上回る」の回が消え、`unit="分"` の seed では消えない
      → g1_l56.graph_table.Lv3 の1文型が3文型に割れた
      `unit="点"` が「点を打ち」に当たって g1_l55.graph_table.Lv2 が2文型に
      同じ「個」が、slots から来た seed は `〈slots.counter〉`、カタログから来た seed は
      `〈語彙〉` になって g1_l12.word_problem.Lv1 が2文型に

    セル共通の集合を全部の文に当てれば、当たる場所は seed に依らない。熟語の一部を
    余分に消すことはあるが（「半〈語彙〉」「上〈語彙〉る」）、**全部の seed で同じように
    消える**ので型の数は動かない。札を役割ごとに分けないのも同じ理由——同じ語が
    seed によって別の役割に入ることがある。

    余分に消したせいで**本物の文型が畳まれた**場合は、「取りこぼした型」
    （期待 N / 出たのは M）として表に出る。0件や過大な数を黙って出さない。
    """
    for value in sorted(universe, key=len, reverse=True):
        if value in text:
            text = text.replace(value, "〈語彙〉")
    return text


_ARITH_RE = re.compile(r"[0-9/.\-+*^]+")


def _answer_skeleton(text: str, universe: Sequence[str]) -> str:
    """答えの骨格＝**語である部分だけ**（数と算術記号は落とす）。

    ★数を `＃` に置き換えるだけでは足りない。同じ型の答えが、引いた数によって
    約せたり約せなかったりして式の形が変わる——g1_l53.find_value.Lv1（球）は
    体積が `36π cm³` になる seed と `32π/3 cm³` になる seed があり、`＃π` と `＃π/＃` が
    別の文型として数えられた（実測 2 → 4 型）。**数は文型ではない**ので、
    答えからは数と算術記号ごと落とす。

    残るのは「表面積 π〈語彙〉²、体積 π〈語彙〉³」のような語の並びで、
    「全数調査」と「標本調査」のような**答えの種類の違い**はここに残る。
    """
    masked = str(_mask_surface(text, universe))
    return _ARITH_RE.sub("", masked.replace("＃", ""))


def vocab_paths(params: Mapping[str, Any], axes: Sequence[str]) -> dict[str, str]:
    """語彙の置き場所 → その回に入っていた値（`vocab_of` の逆向き）。

    札の `〈〉` は外す（置き場所の名前として読むため。伏せ字は `mask_vocab` が
    1種類の札で当てるので、ここでの札は名前としてしか使わない）。
    """
    return {path.strip("〈〉"): value for value, path in vocab_of(params, axes).items()}


def structural_paths(rows: Sequence[tuple], axes: Sequence[str],
                     universe: Sequence[str]) -> set[str]:
    """語彙のように見えて**構造である置き場所**（答えがその値の関数になっているもの）。

    ★これが無いと、**答えの種類を決めている値まで語彙として伏せてしまう**。
    g3_l57.word_problem.Lv2（全数調査か標本調査か）は調査の場面16通りを
    `slots` に入れており、場面文の形はどれも同じだが**答えが「全数調査」と
    「標本調査」に分かれる**。伏せると 16 型が 1 型に潰れた。

    答えそのものを鍵に入れるのは誤り（答えは引いた数の関数なので、数が型として
    戻ってくる）。ここでは**答えを「置き場所が語彙かどうかの判定」にだけ使う**。

    判定: 置き場所 P の値ごとに答えの骨格を集め、次の3つがそろったとき P は構造である。

      (a) どの値も**2回以上観測されている**（1回ずつしか出ていないと (b) が
          自動的に成り立ってしまう＝品名40通りのセルが全部構造になる）
      (b) 同じ値なら答えの骨格がいつも同じ（＝答えがその値の関数になっている）
      (c) 骨格が2通り以上ある（＝値によって答えが変わる）

    単射までは求めない。g3_l57 は場面16通りに対して答えは「全数調査」「標本調査」の
    2通りで、16対16ではない。
    """
    per_path: dict[str, dict[str, set[tuple]]] = {}
    counts: dict[str, dict[str, int]] = {}
    for _seed, params, _nar, answers in rows:
        skel = tuple(_answer_skeleton(a, universe) for a in answers)
        for path, value in vocab_paths(params, axes).items():
            per_path.setdefault(path, {}).setdefault(value, set()).add(skel)
            counts.setdefault(path, {})[value] = counts.setdefault(path, {}).get(value, 0) + 1
    out: set[str] = set()
    for path, by_value in per_path.items():
        if len(by_value) < 2:
            continue
        if min(counts[path].values()) < 2:
            continue                                   # (a) 値ごとの観測が足りない
        if any(len(skels) != 1 for skels in by_value.values()):
            continue                                   # (b) 答えが値の関数でない
        if len({next(iter(s)) for s in by_value.values()}) > 1:
            out.add(path)                               # (c) 値によって答えが変わる
    return out


def type_key(params: Mapping[str, Any], narration: Sequence[str],
             axes: Sequence[str], text: str | None = None,
             universe: Sequence[str] = ()) -> str:
    """**文型の鍵**（作業0 の物差し・これが型の唯一の定義）。

    入るもの: 型の軸として宣言された値／解く筋道（narration）の骨格／
    （軸が対応づかないセルだけ）問題文の骨格。
    落とすもの: 語彙・数・点名。

    ★**答えは鍵に入れない。** 答えは引いた数の関数なので、入れると数が型として
    戻ってくる（実測 943 → 1650 型・178セルが水増し。g1_l13.calculation.Lv2 は
    1 → 59、g1_l1.knowledge.Lv1 は「正の数」「負の数」で 1 → 2）。
    答えは**何を語彙とみなすかを決めるため**にだけ使う（`structural_paths`）。

    `universe` は**セル共通の語彙集合**。seed ごとに変えてはいけない
    （理由は `mask_vocab` の docstring）。

    ★**この関数の外に同じ判定を書かない。** 頂点名から `I` を外す作業で同じ規約が
    4か所に散っていて、1か所直しても消えなかった（4→2→0）。型の数え方も同じ轍を
    踏みやすい（`count_patterns_wp.py` はここを呼ぶ）。
    """
    parts: list[object] = [[a, _mask_names(params.get(a))] for a in axes]
    parts.append([_mask_surface(s, universe) for s in narration])
    if text is not None:
        parts.append(text_skeleton(text, universe))
    return json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)


def vocab_catalogs(catalogs: Sequence[set], vocab_values: set[str]) -> list[int]:
    """カタログのうち、**値が語彙として伏せられるもの**の添字。

    YAML は `dice_scene_set` を型の軸と宣言するが、その値は recipe が `slots` へ入れる
    ＝engine 自身が語彙と宣言している。**宣言が2か所で食い違うので、実物
    （slots に入ったか）を正とする**。ここを見ないと「期待8型／出たのは4型」と
    取りこぼしに見えてしまう（潰したのは語彙で、取りこぼしではない）。

    `container_set: ["袋|玉|個", ...]` のように1つの値に語彙を詰めている軸があるので、
    `|` で割った部品も照合する（この詰め方は複数の recipe が使っている）。
    """
    out = []
    for i, values in enumerate(catalogs):
        parts: set[str] = set()
        for dumped in values:
            try:
                raw = json.loads(dumped)
            except (TypeError, ValueError):
                continue
            if isinstance(raw, str):
                parts.add(raw)
                parts.update(raw.split("|"))
        if parts & vocab_values:
            out.append(i)
    return out


def vocab_key(params: Mapping[str, Any], axes: Sequence[str],
              filler_words: Sequence[str] = ()) -> str:
    """語彙の組み合わせ（何通りの語彙が出たかを数えるための鍵）。

    **問題文に出た語彙ではなく、その回に引かれた語彙**を数える（params 由来だけ）。
    `filler_words` はカタログ全体なので seed ごとに変わらない＝鍵には入れない。
    """
    return json.dumps(sorted(vocab_of(params, axes)), ensure_ascii=False)


def number_key(params: Mapping[str, Any]) -> str:
    """数の組み合わせ（何通りの数が出たかを数えるための鍵）。"""
    return json.dumps(params.get("numbers", {}), ensure_ascii=False,
                      sort_keys=True, default=str)


def text_skeleton(text: str, universe: Sequence[str] = ()) -> str:
    """問題文から数字を落とした骨格（話が違えばここが変わる）。

    `scene_set` のように**カタログが params に載らない**セルがある（場面は問題文を
    変えるのに、params には数値しか残らない）。名前でも値でも対応づけられないので、
    最後は問題文そのものの形で見分ける。

    ★**点名（大文字）も落とす。** 落としていなかったので、数値も場面も同じで
    頂点名だけ違う問題を別の型として数え、問題集に同じ問題が2回載っていた
    （実測 12問/6組）。`dup_key` から表層を外したのと同じ理由——
    **名前が違うだけの問題は別の問題ではない**。

    ★**語彙も落とす**（作業0）。落としていなかったので、数も構成も同じで品物名だけ
    違う問題を別の型として数えていた（g2_l16.word_problem.Lv2 が 49 型／文型は1つ）。
    これは charter が「段階2に入らない」と決めた違いそのものである。
    """
    if universe:
        text = mask_vocab(text, universe)
    return re.sub(r"[A-Z]", "＊", re.sub(r"\d+", "#", text))


def _catalog_words(values: Any) -> set[str]:
    """カタログの値から語彙になりうる文字列を取り出す（`|` の詰め方も割る）。"""
    out: set[str] = set()
    stack = [values]
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            out.add(v)
            out.update(v.split("|"))
        elif isinstance(v, dict):
            stack.extend(v.values())
        elif isinstance(v, (list, tuple)):
            stack.extend(v)
    return {w for w in out if _vocab_word(w)}


def load_cells() -> list[tuple[str, str, int, list[set], int, set[str]]]:
    """(unit, form, level, カタログの値の集合たち, 期待する型数) を family YAML から作る。

    **軸は名前で照合できない。** YAML は `proof_set` と宣言するが、MR に載るのは
    `proof_id` である（`scene_set` → `scene` も同様）。名前の対応は設計が持っていないので、
    **値の集合**を持ち回り、MR のどのパラメータがその集合から値を取っているかを
    実測で対応づける（`match_axis_keys`）。
    """
    cells = []
    for path in sorted(glob.glob("engine_core/engine/curriculum/math/families/*.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit, form = doc["family"].removeprefix("math.").rsplit(".", 1)
        for lv, spec in (doc.get("levels") or {}).items():
            params = spec.get("params") or {}
            catalogs = []
            axis_names = type_axes(params)
            expected = 1
            for a in axis_names:
                values = {json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
                          for v in params[a]}
                catalogs.append(values)
                expected *= len(params[a])
            # **YAML が「中身」と宣言したカタログの値**＝語彙。`*_candidates` と、
            # 人名・品物・場所を指す `*_set`（type_axes が除いたもの）がここに来る。
            # params に出ない助数詞をここで拾う（`container_set: ["袋|玉|個"]`）。
            filler: set[str] = set()
            for k, v in params.items():
                if k not in axis_names:
                    filler |= _catalog_words(v)
            cells.append((unit, form, int(lv), catalogs, expected, filler))
    # **中1 → 中2 → 中3 → 入試の順に並べる。** ファイル名順（sorted(glob)）だと
    # exam が先頭に来て、レッスン番号も文字列順（g1_l1 → g1_l10 → g1_l2）になる。
    grade_order = {"g1": 0, "g2": 1, "g3": 2, "exam": 3}
    form_order = {
        "knowledge": 0, "calculation": 1, "find_value": 2, "graph_table": 3,
        "construction": 4, "proof": 5, "word_problem": 6,
    }

    def key(c: tuple) -> tuple:
        grade, _, lesson = c[0].partition("_l")
        return (grade_order.get(grade, 9), int(lesson or 0), form_order.get(c[1], 9), c[2])

    return sorted(cells, key=key)


def match_axis_keys(rows: list[dict], catalogs: list[set]) -> list[str]:
    """MR params のうち、カタログの値を取っているキーを見つける（値で照合）。"""
    observed: dict[str, set[str]] = {}
    for params in rows:
        for k, v in params.items():
            observed.setdefault(k, set()).add(
                json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
            )
    keys: list[str] = []
    for values in catalogs:
        for k, seen in sorted(observed.items()):
            if k in keys:
                continue
            # そのキーの観測値がすべてカタログに含まれ、2つ以上の値を取っていること
            if len(seen) > 1 and seen <= values:
                keys.append(k)
                break
    return keys


@dataclass
class CellTypes:
    """1セルを測った結果（型は文型・語彙と数は別に数える）。"""

    axes: list[str]
    expected: int
    use_text: bool
    demoted: int                     # 語彙だったので軸から外したカタログの本数
    rows: list[tuple[int, dict, tuple, tuple]]
    types: dict[str, int]            # 文型の鍵 → 代表になる seed
    labels: dict[str, str]           # 文型の鍵 → 読めるラベル
    vocab: set[str]                  # 出た語彙の組み合わせ
    numbers: set[str]                # 出た数の組み合わせ


def measure_cell(unit: str, form: str, level: int, catalogs: Sequence[set],
                 expected: int, filler_words: set[str], env: Any) -> CellTypes:
    """1セルの**文型を数える**（作業0 の物差し・唯一の実装）。

    `build_corpus` の本体と `count_patterns_wp.py` が両方ここを呼ぶ。同じ判定を
    2か所に書くと、片方を直しても数字が変わらない（頂点名の `I` で踏んだ轍）。
    """
    coord = Coordinate(subject="math", unit=unit, form=form, level=level)
    budget = min(_SEED_CAP, max(_SEEDS_PER_TYPE, expected * _SEEDS_PER_TYPE))

    # まず引けるだけ引いて、params と narration を貯める。
    seen_rows: list[tuple[int, dict, tuple, tuple]] = []
    for seed in range(1, budget + 1):
        r = build_mr(coord, seed, env)
        if not r.ok or r.mr is None:
            continue
        narration = tuple(
            s.narration for sq in r.mr.sub_questions for s in (sq.steps or ())
        )
        answers = tuple(_conclusion_text(sq.answer) for sq in r.mr.sub_questions)
        seen_rows.append((seed, dict(r.mr.params), narration, answers))
        if len(seen_rows) >= _SEEDS_PER_TYPE * max(1, expected):
            break

    # カタログの値を取っているキーを、値で対応づける。
    axes = match_axis_keys([p for _, p, _, _ in seen_rows], catalogs)
    # ★**語彙のカタログは型の軸から外す**（作業0）。外さないと、語彙を畳んだぶんが
    # そのまま「取りこぼした型」として報告される。
    all_vocab: set[str] = set()
    for _, params, _, _ in seen_rows:
        all_vocab |= set(vocab_of(params, axes))
    # ★**答えを決めている置き場所は語彙ではない**（`structural_paths`）。
    # 仮の語彙集合で答えを伏せてから判定する（多めに伏せるほど判定は厳しくなる）。
    structural = structural_paths(seen_rows, axes, sorted(all_vocab | set(filler_words),
                                                          key=len, reverse=True))
    if structural:
        keep: set[str] = set()
        for _, params, _, _ in seen_rows:
            for path, value in vocab_paths(params, axes).items():
                if path in structural:
                    keep.add(value)
        all_vocab -= keep
    vocab_idx = set(vocab_catalogs(catalogs, all_vocab))
    # 軸から外したカタログの値も語彙として伏せる（`dice_scene_set` の場面文など）。
    filler = set(filler_words)
    for i in vocab_idx:
        for dumped in catalogs[i]:
            try:
                filler |= _catalog_words(json.loads(dumped))
            except (TypeError, ValueError):
                continue
    if vocab_idx:
        expected = 1
        for i, values in enumerate(catalogs):
            if i not in vocab_idx:
                expected *= len(values)
    # ★**セル共通の語彙集合**（seed ごとに変えない。mask_vocab の docstring に理由）。
    universe = sorted(all_vocab | filler, key=len, reverse=True)
    # 対応づかないカタログが残ったら、問題文の骨格で見分ける（scene_set など）。
    # ★**語彙のカタログを外したぶんで判定を切らない。** struct_catalogs で判定したら
    # exam_l5.Lv4 のように「軸ゼロ／カタログは語彙だけ」のセルで問題文を一度も読まなく
    # なり、`numbers` に入っている構成の語（和・積）を見落として 22型 → 1型 になった。
    use_text = len(axes) < len(catalogs)

    found: dict[str, int] = {}
    labels: dict[str, str] = {}      # 鍵 → 読めるラベル（鍵を読み直さない）
    # 型は「文型」で数える。語彙と数は**別に数えて併記する**（作業0）——
    # 同じ数にまとめてしまうと、場面を足しても増えていないものと混ざって
    # 効果が数字に出ない（charter §2）。
    seen_vocab: set[str] = set()
    seen_numbers: set[str] = set()
    for seed, params, narration, answers in seen_rows:
        seen_vocab.add(vocab_key(params, axes))  # 語彙は params 由来だけを数える
        seen_numbers.add(number_key(params))
        text = None
        if use_text:
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=seed),
                curriculum=env.curriculum, families=env.families,
                registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            text = res.problem_text
        key = type_key(params, narration, axes, text, universe)
        if key not in found:
            found[key] = seed
            axis_part = "・".join(
                f"{a}={params.get(a)}" for a in axes if params.get(a) is not None
            )
            labels[key] = axis_part or ("場面ちがい" if use_text else "（軸なし）")
        # 期待型数に達したら打ち切る（問題文を読むのは重い）。ただし**語彙のカタログを
        # 外したセルでは打ち切らない**——expected が本当の型数より小さいので、
        # 1つ目の seed で止まって「型は1つ」と誤って報告する。
        if use_text and not vocab_idx and len(found) >= expected:
            break
    return CellTypes(axes=axes, expected=expected, use_text=use_text,
                     demoted=len(vocab_idx), rows=seen_rows, types=found,
                     labels=labels, vocab=seen_vocab, numbers=seen_numbers)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_corpus", description="全セルの型を書き出す（生成物の置き場は --out）"
    )
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help="生成物の出力先（既定: 環境変数 MONGENE_CORPUS_DIR か records/work/corpus）",
    )
    args = parser.parse_args()
    out_dir: Path = args.out
    figs_dir = out_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    env = make_env()
    try:
        import cairosvg  # noqa: PLC0415
    except ImportError:
        cairosvg = None  # type: ignore[assignment]

    lines: list[str] = [
        "# 生成できる問題の全型（単元・form・Lv ごと）\n",
        "セルをまたいだ重複除去はしていない。1セルにつき最低1問、"
        "型が複数あるセルはその全部。\n",
        "**型は「文型」で数える**（作業0）。品物名・人名だけが違うもの（語彙）と、"
        "数だけが違うものは同じ型として1問に畳み、何通り出たかは見出しに併記する。\n",
    ]
    shortfalls: list[str] = []
    demoted: list[str] = []      # 語彙だったので型の軸から外したカタログ
    n_problems = n_figs = 0
    # 型（文型）とは別に、語彙と数が何通り出たかを積む（作業0・charter §4）。
    n_vocab = n_numbers = 0

    for unit, form, level, catalogs, expected, filler_words in load_cells():
        cell = f"{unit}.{form}.Lv{level}"
        m = measure_cell(unit, form, level, catalogs, expected, filler_words, env)
        axes, found, labels = m.axes, m.types, m.labels
        seen_rows, seen_vocab, seen_numbers = m.rows, m.vocab, m.numbers
        if m.demoted:
            demoted.append(f"{cell}: 語彙のカタログ {m.demoted} 本を軸から外した"
                           f"（期待型数 → {m.expected}）")
        if len(found) < m.expected:
            shortfalls.append(f"{cell}: 期待 {m.expected} 型 / 出たのは {len(found)} 型")

        # ★**問題文と図がどちらも同じものは、同じ問題である。**
        # 使う文字を b にするか c にするかだけが違う2つが別々の型として載って、
        # 問題集に同じ問題文が2回出ていた（2026-08-19 の外部評価で指摘）。
        # 一方で投影図のセルは**問題文が同じで図が違う**＝別の問題なので、
        # 図まで見て判定する。
        emitted: set[tuple[str, str]] = set()
        rendered: list[tuple[str, int, Any]] = []
        for key, seed in sorted(found.items(), key=lambda kv: kv[1]):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form, level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if not isinstance(res, Unsupported):
                mark = (res.problem_text, res.visual_svg or "")
                if mark in emitted:
                    continue
                emitted.add(mark)
            rendered.append((key, seed, res))

        n_vocab += len(seen_vocab)
        n_numbers += len(seen_numbers)
        lines.append(f"\n---\n\n## {cell}  — 型 {len(rendered)} 個"
                     + (f"（軸: {', '.join(axes)}）" if axes else "")
                     + f"　／　語彙 {len(seen_vocab)} 通り・数 {len(seen_numbers)} 通り"
                     f"（{len(seen_rows)} seed で観測）")
        for i, (key, seed, res) in enumerate(rendered, start=1):
            if isinstance(res, Unsupported):
                lines.append(f"\n### 型{i}  （生成不可: {res.code}）\n")
                continue
            n_problems += 1
            multi = len(res.sub_questions) > 1
            # **答えは全小問ぶん出す。** 1つ目しか出していなかったので、(2)(3) の答えを
            # 走査が一度も見ていなかった。選択肢の答え（ChoiceAnswer）と作図の答え
            # （GraphAnswer）も出す——これらが空欄だったため「答えが空」が213セルに
            # 出ていて、その中の欠陥は文面の走査に一度もかからなかった。
            ans = " ／ ".join(
                f"{s.label} {_answer_text(s.answer)}" if multi else _answer_text(s.answer)
                for s in res.sub_questions
            )
            # **解説とヒントも全小問ぶん出す（2026-08-16）。** 答えだけを直して
            # ここを `sub_questions[0]` のままにしていたので、(2) 以降の解説を
            # 走査も読み手も一度も見ていなかった。連立方程式の「消去して解く」段は
            # 小問(2)にあるのに、読むと「式を立てて終わっている」ように見えていた
            # ——**同じ根（1つ目しか出さない）の別の出口**。
            exp = "\n\n".join(
                (f"{s.label} {s.explanation}" if multi else str(s.explanation))
                for s in res.sub_questions if s.explanation
            )
            hints = " ／ ".join(
                (f"{s.label} " if multi else "") + " / ".join(s.hints)
                for s in res.sub_questions if s.hints
            )

            fig = "（図なし）"
            if res.visual_svg:
                stem = f"{unit}_{form}_Lv{level}_{i}"
                (figs_dir / f"{stem}.svg").write_text(res.visual_svg, encoding="utf-8")
                fig = f"records/work/corpus/figs/{stem}.svg"
                if cairosvg is not None:
                    cairosvg.svg2png(
                        bytestring=res.visual_svg.encode("utf-8"),
                        write_to=str(figs_dir / f"{stem}.png"), output_width=520,
                    )
                    fig = f"records/work/corpus/figs/{stem}.png"
                n_figs += 1

            lines.append(f"\n### 型{i}  `{labels[key]}`  (seed {seed})\n")
            lines.append(f"**問題**\n\n{res.problem_text}\n")
            # **問いも全小問ぶん。** ここだけ `sub_questions[0]` が残っていて、
            # (2)(3) の問いが INDEX に一度も出ていなかった。
            asks = " ／ ".join(
                (f"{s.label} {s.prompt_text}" if multi else str(s.prompt_text))
                for s in res.sub_questions
            )
            lines.append(f"**問い** {asks}\n")
            lines.append(f"**図** {fig}\n")
            lines.append(f"**答え** {ans}\n")
            lines.append(f"**解説**\n\n{exp}\n")
            if hints:
                lines.append(f"**ヒント** {hints}\n")

    if demoted:
        lines.insert(2, "\n## 型の軸から外したカタログ（値が語彙だったもの・作業0）\n\n"
                     + "\n".join(f"- {d}" for d in demoted) + "\n")
    if shortfalls:
        lines.insert(2, "\n## 取りこぼした型（seed を引き切れなかったセル）\n\n"
                     + "\n".join(f"- {s}" for s in shortfalls) + "\n")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"問題 {n_problems} 個（＝文型の数）/ 図 {n_figs} 枚 → {out_dir / 'INDEX.md'}")
    print(f"引いた seed の中で観測した 語彙 {n_vocab} 通り・数 {n_numbers} 通り"
          "（型としては数えない）")
    if demoted:
        print(f"語彙だったので軸から外したカタログ: {len(demoted)} セル分")
    if shortfalls:
        print(f"取りこぼし {len(shortfalls)} セル（INDEX.md の冒頭に列挙した）")


if __name__ == "__main__":
    main()
