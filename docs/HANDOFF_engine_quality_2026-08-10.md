# 引き継ぎ（2026-08-09〜10・生成した問題の「質」の修正）

前提の引き継ぎ書は `scratchpad/HANDOFF_2026-08-09_quality_fixes.md`（1回目）と
`scratchpad/HANDOFF_2026-08-09b_quality_fixes.md`（2回目・詳細版）。
**この文書は別の環境へ渡すための自己完結版**で、完了したものだけを記録する。

---

## 1. 何をしたか（1行で）

台帳630セルの実装が終わったあと、**生成される問題そのものの質**を評価し、
記録された欠陥24件と、直す過程で新しく見つけた欠陥5件を、**全部直した**。

---

## 2. いまの状態（すべて実測値）

| | 状態 | いつ測ったか |
|---|---|---|
| 台帳の充足 | **630 / 630** | `audit_progress.py` 監査 OK |
| `engine_tests` | **49,589 passed / 0 failed**（golden 込み） | 最後の修正を含めて完走 |
| golden | **279 / 279 再承認済み** | 最後の修正のあと |
| `engine.eval`（4ゲート） | coverage / dup_rate / level_sep / retry すべて OK | **下記の但し書きを読むこと** |
| 図 | 905枚を座標で照合して食い違い0 | 回帰なし |
| 質の欠陥 | 記録24件＋新規5件を**全件修正** | 各セル `check_cell.py` 実測 |

### 但し書き（ここだけ未確認）

`engine.eval` は **1つ前の版で OK**（4ゲート全通過）。そのあと入れた
**最後の4件の修正（下の §3 の「2周目」）については eval を再走中に引き継いだ**。
`engine_tests` 49,589 は最後の4件を含めて通っている。
**再開したら最初に `engine.eval` を回すこと**（約25分・exit 0 が DoD）。

```bash
PYTHONPATH=. .venv/bin/python -m engine.eval
```

---

## 3. 直した欠陥（記録は `scratchpad/corpus/FIXES.md` に全部ある）

### 大きいもの

| | 中身 | 規模 |
|---|---|---|
| D-10 | 答え・解説が問題文と**別の点名**（「三角形AKJ」と問うて「三角形ADE」と答える） | 12セル |
| D-16 | 作図の答えが、**図に無い座標系**と中学範囲外の `ax+by+c=0` | 9セル |
| D-12 | 数と設定の現実味（`34762/37`・`13824:68921`・`415292π/3` ほか） | 17セル群 |
| D-17 | 1手のセルのヒントが**中身なし**（「与えられた値をもう一度確認しよう」） | 26セル |
| D-2 | 正負の数の答えの分母が最大420 | 4セル |
| D-11/D-15 | 図の PNG に背景が無い（暗い画面で線が消える）・`ℓ` が豆腐 | 図を持つ130セル |
| D-14 | 統計データが機械的（`4,8,4,8…`）・**100m走が9.1秒** | 2セル |
| D-13/D-7 | 存在しない道具（28面・20面・17面のさいころ／87枚のカード）・樹形図で数えられない51人 | 10セル超 |
| D-19/D-24 | 相対度数・割合を**分数**で答えている（`363/646`・`27/40`・`1/8`） | 8セル |
| D-1/D-3/D-4/D-5/D-6/D-8/D-9/D-18/D-20/D-21/D-22/D-23 | 個別 | 各1〜6セル |

### 直す過程で新しく見つけたもの

| | 中身 |
|---|---|
| D-25 | 解説に**生の sympy** が出ていた（`Eq(5*x + y, 45)` → `5x + y = 45`） |
| D-25b | 「線分ABと線分CDが点Oで交わり、AB∥CD」＝**図として成り立たない文**（交わるのは AC と BD） |
| D-26 | 小数で与えた累乗の答えが分数（`(-0.9)³ → -729/1000` → `-0.729`） |
| D-27 | **座標軸の目盛りラベルが重なって読めない**（`-16-15-14-13…`） |
| D-28 | **コーパスを作り直したら、同じ根の取りこぼしが11件**（2周分） |

---

## 4. 次の人がいちばん知るべきこと（順に）

### ① コーパスを作り直して読み直すまで、同じ根の別の出口は見えない

D-13（存在しない道具）を「直した」あとに `build_corpus.py` → `scan_defects.py` を
回したら、**同じ単元の別セルに 20面・17面・14面・9面のさいころが残っていた**。
さらに直してもう一度回したら、**また4件出た**（87枚のカード・標本比率の分数）。

**1セルずつ直すと必ず取りこぼす。「作り直す → 走査 → 直す」を、走査が空になるまで回す。**

### ② dup_rate を通す手は、この順に試す（`FIXES.md` 冒頭にも書いた）

0. **定義域ではなく「答えの大きさ」で測る**（まずこれ）
   — 定義域は広いまま、答えの分母・分子・根号の中に上限を置いて超えたら組み直す。
   `g1_l3〜l6` は定義域を1つも狭めずに分母420→12・dup 0.00 になった
1. **軸を増やす** — 場面・道具・問い方（数を小さく保ったまま組み合わせを稼ぐ）
2. **params に記録する** — 場面が params に無いと `dup_key` が話の違いを見落とす
3. **問題空間の狭さを宣言する** — `SpecLevel.dup_rate_max`（`dup_rate_reason` 必須）

**定義域を広げて通すのはもうしない。狭めるのも最後の手。**

### ③ 数が小さくても「場面に対して値がありえない」ことがある

「さいころを800回投げて1の目が756回（相対度数0.945）」「100m走が9.1秒」は
数がすべて小さい。**場面ごとに起こりうる値の幅を持たせる**しかない
（`_FREQUENCY_TOOLS` / `_TIMED_EVENTS` がその形）。数の大きさの検査では捕まらない。

### ④ 定義域を触ったら必ず `check_cell` を回す

`peek` は問題文しか見せない。定義域を狭めた瞬間に dup が跳ねたことに気づけず、
`g1_l2` を 0.41 にしたまま進めて **20分の eval の最後で落ちた**。

### ⑤ 図のテキストは whitelist と実描画の**両方**を同じ関数から作る

D-27 で目盛りを間引いたとき、`tick_labels_from_params`（G-Q5v の whitelist）と
`_grid_ticks`（実描画）の片方だけ直すとゲートが落ちる。

### ⑥ テストが recipe と solver を両側で結合していると、正しい修正で落ちる

`test_recall_rule_double_solve_property` は solver を labels 無しで呼んで
recipe の答えと比べていた。**checker と同じ経路**（`mr.params` から渡す）に直した。

---

## 5. 道具（すべて `scratchpad/` にある。この commit に含めた）

| 道具 | 何をするか |
|---|---|
| `scratchpad/check_cell.py` | **1セルの実測（rejects / dup）。これが本物の検証** |
| `scratchpad/scan_defects.py` | コーパスを走査して文面の粗さ10種を数える（**再発検査**） |
| `scratchpad/scan_point_names.py` | 答え・解説の記号が問題文にあるか（全630セル・D-10） |
| `scratchpad/scan_big_numbers.py` | セルごとの最大の数・答えの分母を大きい順に（D-12） |
| `scratchpad/scan_empty_hints.py` | 中身のないヒントに落ちているセル（D-17） |
| `scratchpad/check_figure_matches_givens.py` | 図の座標が仮定を満たすか（905枚） |
| `scratchpad/peek_many.py` | 複数セル・複数 seed をまとめて素で見る |
| `scratchpad/audit_progress.py` | 進捗の6検査（**進捗を書く前に必ず回す**） |
| `scratchpad/build_corpus.py` → `build_html.py` | 全型のコーパス生成（約14分＋1分） |

記録は `scratchpad/corpus/EVALUATION.md`（欠陥29件・全件✅）と
`scratchpad/corpus/FIXES.md`（直し方と実測値）。

**`scratchpad/corpus/mongene_problems.html`（2.5MB）と `figs/` は commit していない**
（再生成できるため）。読みたいときは `build_corpus.py` → `build_html.py`。

---

## 6. 実測コマンド

```bash
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>
PYTHONPATH=. .venv/bin/python scratchpad/scan_defects.py
PYTHONPATH=. .venv/bin/python -m pytest engine_tests -q --no-cov -n auto   # 約25分
PYTHONPATH=. .venv/bin/python -m engine.eval                              # 約25分・exit 0 が DoD
```

**`pytest -q`（パス指定なし）はエンジンを1本もテストしない。**
`pyproject.toml` の `testpaths=["tests"]` が旧 apps スタックを指すので、
`engine_tests` を必ず明示すること。

**問題文か答えの表示を変えたら golden の再承認が要る。** 1プロセスで回すこと
（family ごとに subprocess を起こすと10倍遅い）:

```bash
PYTHONPATH=. .venv/bin/python - <<'EOF'
import pathlib
from engine.tools import spec_cli
for p in sorted(pathlib.Path("engine_tests/golden").iterdir()):
    if p.is_dir() and p.name != "__pycache__":
        spec_cli.main(["approve", p.name])
EOF
```

**同時に2つ走らせないこと**（同じ golden を書き合う）。
`pkill -f spec_cli` は効かない（`python -` で動くので）。`ps` で pid を見て kill する。

環境: シェルは fish、python は `.venv/bin/python`、`timeout` コマンドは無い。

---

## 7. 次の一手

1. **`engine.eval` を回す**（§2 の但し書き。最後の4件がまだ eval を通っていない）
2. **`build_corpus.py` → `build_html.py` → `scan_defects.py` を回し、走査が空になるまで直す**
   （§4 の①。いまは 2周目まで済んでいて、3周目が未実施）
3. 未精読のところを読む（word_problem 90セル・中2 knowledge・中3 calculation）
4. 走査3つ（`scan_point_names` `scan_big_numbers` `scan_empty_hints`）をゲートに昇格させる
   — `scan_point_names` の偽陽性は1件だけ（`g2_l15` の「A=B=C」）なので、
   除外規則を1つ足せばそのまま入る

---

## 8. 残っている「欠陥ではないが判断が要るもの」

| | 中身 | なぜ残したか |
|---|---|---|
| D-12 の裾 | 素因数分解 3822・複合立体 16320cm³・不等式の 2896円 | 大半は教材として通る範囲。一律に狭めない |
| 未精読 | word_problem 90セル・中2 knowledge・中3 calculation | 通読はしたが精読していない |
| `dup_rate_max` の宣言 | 確率まわり5セル（0.35〜0.80）・多角形6セル（0.90）・絶対値1セル（0.30）・連続2数1セル（0.60） | どれも**問題空間が本質的に狭い**ため。理由は各 YAML の `dup_rate_reason` に書いてある |
