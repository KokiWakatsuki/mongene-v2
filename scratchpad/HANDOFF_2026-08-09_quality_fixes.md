# 引き継ぎ（2026-08-09・問題の質の評価と修正）

前のセッションでやったこと: **台帳 630/630 を達成 → 生成した全問題を評価 → 修正に着手**。
このファイルは中断時点の全状態。作業ツリーは**すべて未コミット**。

---

## 1. いまどこにいるか

| | 状態 |
|---|---|
| 台帳の充足 | **630 / 630（100%）**。`audit_progress.py` 監査 OK |
| `engine_tests` | **49,589 passed / 0 failed**（golden 280 family 再承認済み） |
| `engine.eval` | 630/630 で exit 0（**ただし修正前の結果。要再走**） |
| 質の評価 | **全630セル・989型を通読済み**。24件の欠陥を記録 |
| 修正 | **8件完了・13件未着手** |

**テストは全部緑の状態で引き継ぐ。** ここから壊れたら、それは新しい変更のせい。

読むべき3つのファイル（この順で）:

1. `scratchpad/corpus/EVALUATION.md` — 欠陥24件の記録（何が・どこに・どう確かめたか）
2. `scratchpad/corpus/FIXES.md` — 直した8件と、直し方の原則
3. `scratchpad/corpus/INDEX.md` — 989問の実物（24,148行）

生成物: `scratchpad/corpus/mongene_problems.html`（2.0MB・図282枚を埋め込んだ閲覧用）

---

## 2. 評価で分かった、いちばん大事なこと

**「教材としてありうるか」を測るものが、エンジンのどこにも無い。**

ゲートは4つ（coverage / dup_rate / level_sep / retry）あるが、どれも構造しか見ない。
しかも **`dup_rate ≤ 0.20` は質と逆向きに働く**。閾値を通すには1セル約250通り要り、
一番簡単な増やし方が「定義域を広げること」だったため:

```
正348角形 / 1つの内角が 4860/29° / 内角の和が21060°
1個のさいころ（1から28までの目が出る）
100m走の記録（十分の一秒）: 91 ← 9.1秒。世界記録より速い
7/9-(-1.2)+4/7-0.6 → 614/315
```

**これは推測ではない。** 確率の recipe に、そのままのコメントが残っていた:

> `# coin は trials しか自由度がなく単独では dup_rate が閾値を超えるため、faces も振れる`

### 直し方の原則（`FIXES.md` にも書いた）

この順に試すこと。**定義域を広げて通すのは、もうしない。**

1. **軸を増やす** — 場面・道具・記号で、数を小さく保ったまま組み合わせを稼ぐ
2. **params に記録する** — 場面が params に無いと `dup_key` が話の違いを見落とす
3. **問題空間の狭さを宣言する** — 上2つで届かないなら `dup_rate_max` に理由つきで宣言

3つ目のために `SpecLevel` に `dup_rate_max` / `dup_rate_reason` を新設した
（理由が無いと pydantic の検証で落ちる。質の低下が黙って隠れないように）。

**成功例**: 確率 `g2_l54.find_value.Lv3` は、道具を実在するものに戻して
dup 0.76 まで悪化したが、場面を61通りに増やし params に記録して **0.15** で通した。

---

## 3. 直したもの（8件・すべて実測済み）

| | 内容 | 確認 |
|---|---|---|
| D-1 | 絶対値の二重 `\|-17/13\|` → 裸の数 | rejects=0/120 |
| D-3 | 助詞前の空白 **56セル → 0セル** | 全630セル走査 |
| D-22 | 「〜を何というか を何といいますか」 | 全走査で0件 |
| D-4 | 「平行四辺形である であることを証明せよ」6セル | 四角形・数式の両方 |
| D-20 | `y = -62/5/x` → `y = -62/(5x)` | 6セル rejects=0/120 |
| D-13a | 28面のさいころ → 実在する道具（61場面） | dup 0.15 |
| D-13b | 正348角形 → 正五角形〜正三十六角形（6セル） | 内角・外角とも整数 |
| D-10a | 答えが別名だった3セル | `三角形AKJ:台形KBMJ` ほか |

### 修正で踏んだ罠（次も踏む可能性がある）

- **`recipes/proportion.py` に solver と同じ表示関数の写しがあった。**
  solver だけ直しても問題文は変わらない。import で一本化した。
  **表示関数が2か所にある箇所は他にもあるかもしれない。**
- **golden 279 family が全部古くなった。** E-3（問いかけの日本語化）で
  全セルの `prompt_text` が変わったため。再承認済み（失敗0）。
  **今後も問題文を変えたら `spec approve` が要る。**

---

## 4. まだ直していないもの（13件・影響の大きい順）

### 最優先

**D-10 残り（解説だけが別の点名・9セル）**
`g2_l28.word_problem.Lv4` / `g3_l31.word_problem.Lv3,Lv4` /
`g3_l42.knowledge.Lv1` `g3_l42.find_value.Lv2` /
`g3_l43.knowledge.Lv1` `g3_l43.find_value.Lv2,Lv3` / `g3_l48.knowledge.Lv2`

直し方は答え側3セルと同じ: **recipe が引いた頂点名を solver に渡す**
（`labels` は多くの場合すでに params にある）。手本は
`solvers/similarity_scale_ratio.py` の `_points()` と
`solvers/exam_linear_figure.py` の `lines_intersection_and_triangle_area`。

**D-16 作図の答えが、図に無い座標系と中学範囲外の式（作図9セル・26型すべて）**
```
問題: 定規とコンパスだけを使って、この線分の垂直二等分線を作図せよ。
答え: 中点(2, -5) / 線分CDの垂直二等分線＝直線 2x - 5y - 29 = 0
```
図には座標軸が**一切ない**（実測: 線1本と C・D のラベルだけ、目盛り0本）。
`ax + by + c = 0` は中学の範囲外（一次関数は中2、一般形は高校数II）。
**手順そのものは教科書どおりなので、直しは表示層で閉じるはず。**

**D-12 数と設定の現実味（127セルに数が100以上）**
- 図形の辺の長さが3桁（`EF=111cm, FA=11cm` → `10370/111`）
- 相似比 24:41 → 体積比 13824:68921
- 球の体積 595508π/3 m³
- 樹形図で数えられない人数（`n_domain: [4, 60]` → 51人で124,950通り）

### 中くらい

| | 中身 | 座標 |
|---|---|---|
| D-2 | 正負の数の分母が最大420（半数以上が使えない） | `g1_l3` `g1_l4` `g1_l5` の Lv2 |
| D-14 | 統計データが機械的（`4,8,4,8,5,7…`）・100m走が9.1秒 | `g1_l58.word_problem.Lv2,Lv3` |
| D-17 | 1手のセルのヒントが中身なし | 25セル（`t1_template.py:196`） |
| D-18 | 平方根の根号の中が平方数（60問中29問） | `g3_l17` `g3_l18` の Lv2 |
| D-6 | 「右の図で」と書いてあるのに図が無い | `g3_l42.find_value.Lv3` `g3_l47.find_value.Lv3` |
| D-8 | 問題文が答えを言っている | `g1_l30.graph_table.Lv1` |

### 小さい

D-5（数直線の答えが仮分数）/ D-9（正解が複数あるのに1つしか持たない）/
D-19・D-24（相対度数を分数で）/ D-21（Lv1 の答えが Lv2 の形式）/
D-23（角度・比が分数）/ D-11・D-15（図の PNG に背景が無い・`ℓ` が豆腐）

---

## 5. 作った道具（残してある）

| 道具 | 何をするか |
|---|---|
| `scratchpad/check_cell.py` | 1セルの実測（rejects / dup）。**これが本物の検証** |
| `scratchpad/peek.py` | 1セル1seedを素で見る |
| `scratchpad/audit_progress.py` | 進捗の6検査（**進捗を書く前に必ず回す**） |
| `scratchpad/build_corpus.py` | 全型のコーパス生成（約14分） |
| `scratchpad/build_html.py` | コーパス → 閲覧用HTML（約1分） |
| `scratchpad/scan_defects.py` | 文面の粗さ8種を機械で走査 |
| `scratchpad/check_figure_matches_givens.py` | **図の座標が仮定を満たすか**（905枚で食い違い0） |
| `scratchpad/contact_sheet.py` | 図を格子に並べて目視 |
| `scratchpad/count_types_static.py` | family YAML から型を静的に数える |

---

## 6. 実測コマンド

```bash
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>
PYTHONPATH=. .venv/bin/python scratchpad/peek.py <unit> <form> <lv> <seed>
PYTHONPATH=. .venv/bin/python -m pytest engine_tests -q --no-cov -n auto
PYTHONPATH=. .venv/bin/python -m engine.eval            # 約20分・exit 0 が DoD
```

**`pytest -q`（パス指定なし）はエンジンをテストしない。** `pyproject.toml:41` が
`testpaths = ["tests"]` を指しているので、旧 apps スタックの472本しか走らない。
**必ず `engine_tests` を明示すること。** `engine_tests/eval/test_eval_suite.py` は
eval 全走を含むので単独で20分以上かかる（`--deselect` するか `-n auto` を使う）。

シェルは fish。`python` は無い（`.venv/bin/python`）。`timeout` コマンドも無い。

---

## 7. 未コミットの変更（全部）

```
変更  76ファイル（golden 除く）＋ engine_tests/golden 約900ファイル
新規  g2_l38.proof.yaml / g3_l51.proof.yaml / g3_l52.proof.yaml
      conditional_proof.py × 4（solver/recipe/checker/template）
      pythagoras_proof.py × 4（同上）
```

**コミットしていない。** 内訳:

- 前セッションの proof 8セル（g2_l38・g2_l40〜42・g3_l51/l52）— 実測 ALL_OK 済み
- 機構の修正（`deduce._MAX_ROUNDS` 12→24、合同2回の段分け、台形の図の点の位置）
- テストの修正2件（`not_implemented` の発火方法、図の質フィルタのテスト）
- 問いかけの日本語化28種類（`t1_template.py`）
- 今回の質の修正8件
- golden 279 family の再承認

---

## 8. 次の一手（推奨）

1. **D-10 の残り9セル**を片づける（手本があるので機械的）
2. **D-16 作図の答え**（9セル・26型に効く。表示層で閉じる見込み）
3. **D-12 の数の設計**（127セル。原則1〜3を順に当てる）
4. 全部済んだら `build_corpus.py` → `build_html.py` で**コーパスを作り直して見比べる**
5. `engine.eval` を再走（修正前の結果しかない）

**ゲートを足すことも検討に値する。** 今回見つけた欠陥は、機械で書ける検査でほぼ捕まる:

| 検査 | 捕まるもの |
|---|---|
| 答えと問題文の記号が対応しているか | D-10（12セル） |
| 問題文の数が単元ごとの上限を超えていないか | D-12/D-13（127セル） |
| 図に言及しているのに図が無いか | D-6 |
| 答えが問題文にそのまま出ていないか | D-8 |
| 図の座標が仮定を満たすか | 実装済み（`check_figure_matches_givens.py`） |
