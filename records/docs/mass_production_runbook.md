# 量産の手順（AI が数式と場面を1組つくるとき）

理想型の図（`量産できる設計図`）を、実際に回せる手順にしたもの。
**1組 = 数式パーツ1つ ＋ それが必要とする場面（升）＋ checker**。

★この手順の目的は「AI に書かせること」ではなく、**書かせたものを人が読まずに
判定できるようにすること**。だから関門を通る順番と、落ちたときの戻し先を先に決める。

---

## 0. 前提（今できること・できないこと）

| | 状態 |
|---|---|
| 設計書が数式・文型を複数選べる | ✅ `formulas:` / `scenes:`（棚に無い名前は spec_lint R9 で落ちる） |
| 役割の型で場面が乗る棚 | ⚠️ **5つ・33場面**（1元1次12／2次5／比例と度数4／連立7／文字の式5）。棚に乗っているのは **28 / 630 セル（4.4%）**。★層に割れた5モジュールの**全関係**が棚から引く（旧経路は削除済み） |
| 関門①解ける | ✅ pytest の二重解き・非退化条件 |
| 関門②経路の独立 | ✅ `check_write_scope.py`（差分で見る） |
| 関門③日本語と式の一致 | ✅ `bt_dump_scenes.py` → 読み手 → `bt_check.py`（値で比較） |
| 関門④場面が現実に成り立つ | ✅ `wk_dump.py` → 読み手 → `wk_check.py`（対照つき） |
| 関門⑤学年に合う | ✅ `check_unit_fit.py`（導入学年は台帳から測る） |

つまり**いま量産テストを回せるのは 22 セル**——1元1次（2関係）・2次・比例と度数・
連立・文字の式の文章題。word_problem は全部で100セルなので、残り78セルには
まだ棚が無い（うち21本の recipe は1セル専用に書かれている）。
その他6形式の530セルは**場面という概念が無い**ので棚出しの対象外。

★**層に割れた5モジュールは全部棚に乗った**（2026-08-20）。次に増やすには
**まだ層に割れていない recipe** を割る必要がある——word_problem の残り72セルは
31本の recipe が賄っていて、うち21本は1セル専用に書かれている。
「問い方が同じなら単元がばらばらでも1投資で束ねられる」が過去に効いているので、
束ねられる組を探すのが先。

棚の一覧と、それぞれの場面・役割の型・宣言はこれで引ける:

```bash
PYTHONPATH=records/work .venv/bin/python records/work/scene_shelves.py
```

★**棚を足したら `records/work/scene_shelves.py` の `_SHELVES` に1行足す。**
検査（G-SC1・G-SC3・層の検査）はそこから棚の在り処を引くので、検査側には何も足さない。
これを1か所にしていなかったとき、作業3 で `scenes.py` に移した6場面が
**3つの検査から同時に外れ、外れたことに気づけなかった**（残りが通るので緑に見える）。

---

## 1. 役割を2つに割る（★同じ手に両方を書かせない）

```
書き手（author）    数式パーツ・文型パーツ・recipe・設計書
確かめ手（checker） checker とそのテスト（★書き手の実装を見ずに書く）
```

**別のセッションに割る。** 同じ手が両方を書くと、同じ誤解が2本に入って
二重解きが一致してしまい、①〜③の関門は全部通る。前例がある——checker が立式コードを
再利用していたために「日本語だけが違う問題」が7回のセッションを生き延びた。

確かめ手に渡すのは **問題文と式の宣言だけ**（recipe の実装は渡さない）。

```bash
.venv/bin/python records/work/check_write_scope.py --role author
.venv/bin/python records/work/check_write_scope.py --role checker --range HEAD~1..HEAD
```

---

## 2. 書き手への指示に入れるもの

1. **単元と難易度**（台帳の `desc` / `example` をそのまま渡す）
2. **役割の型** — 既存の型に乗せるのか、新しい型を作るのか
   - 既存の型なら、棚の場面がそのまま乗る（升を書かなくてよい）
   - 新しい型なら、**乗せたい場面の数だけ升を書く**（1升 12〜16行）
3. **失敗カタログ**（`records/work/failure_catalog.yaml`）
   ★これを渡さないと、同じ失敗をやり直す。施設と料金名の対応も実在する額面も、
   engine の宣言からは導けない
4. **答えを先に引く**こと・**非退化条件**を関係の隣に書くこと
5. 増やした軸を **params に載せる**こと（★載せないと `dup_key` に効かず、
   場面を5倍にしても重複率は1ミリも下がらない）

---

## 3. 関門を通す順番

速いものから。落ちたら後ろは走らせない。

```bash
# ① 解ける・退化しない（数十秒）
.venv/bin/python records/work/check_cell.py <unit> word_problem <lv>

# ⑤ 学年に合う（数分）
PYTHONPATH=records/work .venv/bin/python records/work/check_unit_fit.py --seeds 3

# ② 経路の独立（一瞬）
.venv/bin/python records/work/check_write_scope.py --role author

# ③ 日本語と式の一致（読み手が要る）
PYTHONPATH=records/work .venv/bin/python records/work/bt_dump_scenes.py --per 3
#   → 読み手が records/work/bt/answers.tsv を書く（問題文だけを渡す）
.venv/bin/python records/work/bt_check.py

# ④ 場面が現実に成り立つ（読み手が要る）
PYTHONPATH=records/work .venv/bin/python records/work/wk_dump.py
#   → 読み手が records/work/wk/verdicts.<model>.tsv を書く
PYTHONPATH=records/work .venv/bin/python records/work/wk_check.py --verdicts <path>

# 全部通ったら、まとめて1回だけ全走
.venv/bin/python -m pytest ../mongene-engine/tests -q -n7
.venv/bin/python -m engine.eval
.venv/bin/python records/work/approve_all.py
```

★**小さい修正で全走を回さない。** `check_cell` で確かめ、最後に1回だけ。
全走は1周およそ25分（golden 17分・eval 19分・pytest 23分を並列で）。

---

## 4. 読み手（③④）の選び方 — ★対照で測る

読み手は問題文だけを読む別のAIで、**その読み手が見えているかどうかを対照で測る**。
`wk_dump.py` は失敗カタログの「過去に実際に engine が出した悪い例」を id を伏せて混ぜる。

```
対照を1つでも見落とした回は、実物の判定を読まずに打ち切る
（「該当なし」が、問題が無いのか読み手が見ていないのかを区別できないため）
```

実測（2026-08-20・155問＝実物149＋対照6）は
`records/docs/wk_reader_comparison_2026-08-20.md` に残す。

---

## 5. 落ちたときの戻し先

| 落ちた関門 | 戻す先 |
|---|---|
| ①②⑤ | 書き手に差し戻す（機械が理由を出しているので、そのまま渡せる） |
| ③ | 日本語か式のどちらかが違う。**どちらかは読み手の答えを見れば分かる** |
| ④ | **失敗カタログに1件足す**（種類・悪い例の原文・なぜ悪い・直し方） |

★④で出た型がカタログに無い型だったら、それは**検査の穴**であって1件の欠陥ではない。
カタログに足すと、次の回から読み手の判定項目と対照の両方に入る。
このループの外側で検査が強くなることはない。
