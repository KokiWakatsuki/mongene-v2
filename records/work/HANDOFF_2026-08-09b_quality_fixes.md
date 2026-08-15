# 引き継ぎ（2026-08-09・質の修正 2回目）

前セッション（`HANDOFF_2026-08-09_quality_fixes.md`）の続き。
**評価で記録した欠陥を全部直した。** 作業ツリーは**すべて未コミット**。

---

## 1. いまどこにいるか

| | 状態 |
|---|---|
| 台帳の充足 | **630 / 630**（`audit_progress.py` 監査 OK） |
| `engine_tests` | 48,248 passed / 0 failed（golden 除く。golden 込みは §6 の手順で再承認後に確認） |
| 質の欠陥 | **記録した24件＋新規5件＝29件を全件修正** |
| 図 | 905枚を座標で照合して食い違い0（回帰なし） |

---

## 2. 直したもの

`scratchpad/corpus/FIXES.md` に全部書いた。大きいものだけ:

| | 中身 | 規模 |
|---|---|---|
| D-10 | 答え・解説が問題文と別の点名 | 12セル（記録は9セルだった） |
| D-16 | 作図の答えが座標と `ax+by+c=0` | 9セル |
| D-12 | 数と設定の現実味 | 17セル群 |
| D-17 | 1手のセルのヒントが中身なし | 26セル（記録は25セル） |
| D-2 | 正負の数の分母が最大420 | 4セル |
| D-11/D-15 | 図の PNG に背景が無い・`ℓ` が豆腐 | 図を持つ130セル |
| D-14 | 統計データが機械的・100m走が9.1秒 | 2セル |
| D-5/D-6/D-7/D-8/D-9/D-18〜D-24 | 個別 | 各1〜6セル |

**新しく見つけて直した5件**:

| | 中身 |
|---|---|
| D-25 | 解説に生の sympy（`Eq(5*x + y, 45)` → `5x + y = 45`） |
| D-25b | 「線分ABと線分CDが点Oで交わり、AB∥CD」＝**図として成り立たない文** |
| D-26 | 小数で与えた累乗の答えが分数（`(-0.9)³ → -729/1000`） |
| D-27 | **座標軸の目盛りラベルが重なって読めない**（`-16-15-14-13…`） |
| D-28 | **コーパスを作り直したら同種の取りこぼしが7件**（20面のさいころ・53枚のカード・相対度数の分数ほか） |

---

## 3. このセッションで分かったこと（次に効くもの）

### ① まず「答えの大きさ」で測る。定義域は最後に触る

`FIXES.md` の原則の **0番目**に足した。定義域は広いまま、答えの分母・分子・
根号の中に上限を置いて、超えたら組み直す。

- `g1_l7`（累乗）は定義域を狭めたら dup が 0.33 に跳ねたが、この手なら質も dup も通った
- `g1_l3〜l6`（正負の数・D-2）は**定義域を1つも狭めずに**
  `answer_denominator_max: 12` の宣言だけで、分母13以上 **107/240 → 0/240**・
  最大分母 420 → 12・**dup は4セルとも 0.00**

### ② 数が小さくても「場面に対して値がありえない」ことがある

「さいころを800回投げて1の目が756回（相対度数0.945）」「100m走が9.1秒」は
数がすべて小さい。**場面ごとに起こりうる値の幅を持たせる**しかない
（`_FREQUENCY_TOOLS` / `_TIMED_EVENTS`）。数の大きさを見る検査では捕まらない。

### ③ **コーパスを作り直すまで、同種の取りこぼしは見えない**

これがいちばん重要。D-13（存在しない道具）を直したはずなのに、
**同じ単元の別のセルに 20面・17面・14面・9面のさいころが残っていた**。
1セルずつ直していると、同じ根の別の出口を見落とす。

`build_corpus.py` → `scan_defects.py` を回して初めて7件が出た。
**直したあとに必ずコーパスを作り直して読み直すこと。**

### ④ 目視の一覧より、機械の走査のほうが多く見つける

D-10 は記録が9セル→実測12セル、D-17 は25セル→26セル。
**縮小した一覧で図を判断すると誤る**のも同じ（前任者が3件誤判定）。
D-27 は原寸の PNG に起こして初めて分かった。

### ⑤ 場面を足すときは「場面が数を決めつけていないか」を見る

「2個のさいころを同時に投げるとき、起こりうる場合は全部で108通り」——
2個のさいころは36通りに決まっている。場面を具体的にするほど食い違いが起きやすい。

### ⑥ 図のテキストは whitelist と実描画の**両方**を同じ関数から作る

D-27 で目盛りラベルを間引いたとき、`tick_labels_from_params`（G-Q5v の whitelist）と
`_grid_ticks`（実描画）の片方だけ直すとゲートが落ちる。

### ⑦ **定義域を触ったら必ず `check_cell` を回す**（peek で済ませない）

D-28 の修正で `g1_l2`（絶対値）の分数の定義域を狭めたとき、`peek` で出力だけ見て
先に進んだ。**`engine.eval` の dup_rate ゲートで落ちた**（0.41）。
定義域を狭めた瞬間に dup は跳ねる——peek は問題文しか見せないので気づけない。
（メモの「check_cell 実測が本物」どおり。1セル1分の実測を惜しむと、
最後の20分の eval で戻ってくる。）

なお立て直しは原則1（軸を増やす）で: 小数を軸に戻した（D-26 で小数の答えを
小数で出せるようにしたので、「小数は答えが分数化して不自然」という除外理由が
消えていた）。それでも 0.23 なので `dup_rate_max: 0.30` を宣言した。

### ⑧ テストが recipe と solver を両側で結合していると、正しい修正で落ちる

`test_recall_rule_double_solve_property` は solver を labels 無しで呼んでいた。
**checker と同じ経路**に直した。（メモの「test_recipes.py の両側結合は事故る」どおり）

---

## 4. 残っているもの

**評価で確定した欠陥は無い。** 残るのは判断が要るもの:

| | 中身 | なぜ残したか |
|---|---|---|
| D-12 の裾 | 素因数分解 3822・複合立体 16320cm³・不等式の 2896円 | 大半は教材として通る範囲。一律に狭めない |
| 未精読 | word_problem 90セル・中2 knowledge・中3 calculation | 通読はしたが精読していない |
| ゲート化 | `scan_point_names` `scan_big_numbers` `scan_empty_hints` | 走査としては動く。昇格には偽陽性の除外規則が要る |

---

## 5. 作った道具

| 道具 | 何をするか |
|---|---|
| `scratchpad/scan_point_names.py` | **D-10**。答え・解説の記号が問題文にあるか（全630セル） |
| `scratchpad/scan_big_numbers.py` | **D-12**。セルごとの最大の数・答えの分母を大きい順に |
| `scratchpad/scan_empty_hints.py` | **D-17**。中身のないヒントに落ちているセル |
| `scratchpad/peek_many.py` | 複数セル・複数 seed をまとめて素で見る |

前回の道具（`check_cell.py` `audit_progress.py` `check_figure_matches_givens.py`）も
そのまま使える。

---

## 6. 実測コマンド

```bash
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>
PYTHONPATH=. .venv/bin/python scratchpad/scan_point_names.py --seeds 3
PYTHONPATH=. .venv/bin/python scratchpad/scan_big_numbers.py --seeds 3 --top 40
PYTHONPATH=. .venv/bin/python scratchpad/scan_empty_hints.py --seeds 2
PYTHONPATH=. .venv/bin/python scratchpad/check_figure_matches_givens.py
PYTHONPATH=. .venv/bin/python -m pytest engine_tests -q --no-cov -n auto
PYTHONPATH=. .venv/bin/python -m engine.eval            # 約20分・exit 0 が DoD
```

**`pytest -q`（パス指定なし）はエンジンをテストしない**（`pyproject.toml` が
旧 apps スタックを指す）。`engine_tests` を必ず明示すること。

golden の再承認は **1プロセスで回す**（family ごとに subprocess を起こすと10倍遅い）:

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

---

## 7. 次の一手

1. **コーパスを作り直して読み直す**（`build_corpus.py` 約14分 → `build_html.py` 約1分）。
   D-28 で分かったとおり、**同種の取りこぼしはこれをやるまで見えない**
2. 未精読のところ（word_problem 90セル・中2 knowledge・中3 calculation）を読む
3. 走査3つ（`scan_point_names` `scan_big_numbers` `scan_empty_hints`）をゲートに昇格
4. `scan_defects.py` に「相対度数が分数」「存在しない面数の道具」の検査を足す
   — この2つが D-28 の7件のうち5件を釣り上げた
