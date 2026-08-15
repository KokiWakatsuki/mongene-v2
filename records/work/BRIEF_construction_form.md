# 作図セル（form: construction）新設ブリーフ

## 何を作るのか

**この form はまだ1セルも実装されていない**（実装済み 578 セルの内訳は knowledge 145 /
calculation 144 / find_value 105 / word_problem 100 / graph_table 76 / proof 8）。
残り9セルすべてが g1_l41〜l44 の基本作図なので、**form ごと立ち上げる**のがこの仕事。

| unit | Lv | 台帳 desc |
|---|---|---|
| g1_l41 垂直二等分線 | 1 | 線分の垂直二等分線を基本手順で作図する |
| g1_l41 | 2 | 2点から等距離の点・線分の中点など性質を使った作図 |
| g1_l42 角の二等分線 | 1 | 角の二等分線を基本手順で作図する |
| g1_l42 | 2 | 2辺から等距離の点・角の二等分の性質を使った作図 |
| g1_l43 垂線 | 1 | 直線上の点/直線外の点を通る垂線を基本手順で作図する |
| g1_l43 | 2 | 点と直線の距離・垂線の足を求める作図 |
| g1_l44 作図の利用 | 2 | 1つの基本作図で条件を満たす点/線を作図する（誘導あり） |
| g1_l44 | 3 | 2つの基本作図の交点として条件を満たす点を作図する（組合せ） |
| g1_l44 | 4 | どの作図を使うか方針から自分で構成する（誘導なし） |

`engine/curriculum/math/units.generated.yaml` の `example` に、この単元で出したい問題文が
そのまま書いてある。**それを正として読むこと**（「作図に用いた線は消さずに残すこと」まで含めて）。

## 答えの形（設計の要）

`engine/core/contracts.py` の `GraphAnswer` は、コメントに「graph_table「かく」・
**construction**」と書いてある——**この form のために用意されている**。core は触らない。

- `GraphAnswer.features`: 作図で得られる対象を**検証可能な形**で持つ（点Pの座標・
  直線の式・「2点から等距離」という特徴）。`Feature.srepr` は sympy の srepr。
- `GraphAnswer.solution_svg_ref`: **模範解答図**（コンパスの弧と作図線が入ったもの）。
  問題図（与えられた線分・角・点だけ）とは別部品で、開示制御の対象。
- `SubQuestionMR.steps`: 作図の手順を1手ずつ。**`op` に基本作図の識別子**
  （`perp_bisector` / `angle_bisector` / `perpendicular` など）を入れる。

**`op` 列が Lv 間で違うことが、eval の level_sep を通す条件**。ここは自然に効く——
g1_l44 Lv2 は基本作図1つ（op 1個）、Lv3 は2つの交点（op 2個）、Lv4 は方針を選ぶ行が
増える、という差が台帳 desc そのものだからである。

## 図（描画資産）

**作図の図は「弧」を描けないと成立しない。** 既存の `engine/packs/math/visuals/` に
円弧を描く資産があるか先に確認し、無ければ**新しいモジュールを足す**
（既存ファイルを書き換えるのではなく新規ファイルにする）。必要な要素:

- 与えられた図（線分AB・∠AOB・直線ℓと点P）
- コンパスの弧（中心と半径と角度範囲）— 交わる2つの弧が交点を作るところが見えること
- 作図線（弧の交点どうしを結ぶ直線）

**図は必ず PNG に起こして目視する。** ゲートは図の内容の誤りを検出しない。
過去に「二等辺三角形が上下逆さま」「交点のラベルが線に埋もれる」を目視だけで発見している。
作図の図では特に、**弧が交わって見えるか**（半径が小さすぎると交わらない）を見ること。

## 問題のパラメータ化

`dup_rate ≤ 0.20` には**約250通り**の変種が要る。与える図のパラメータ
（線分の長さ・角の大きさ・点の位置・向き）を連続的に動かすこと。型を数個並べるだけでは落ちる。

## 触ってよいファイル

- `engine/packs/math/recipes/<新規>.py` / `solvers/<新規>.py` / `templates/<新規>.py`
- `engine/packs/math/visuals/<新規>.py`（弧を描く資産）
- `engine/curriculum/math/families/g1_l41.construction.yaml` ほか4本（新規作成）
- `scratchpad/` 配下（新しい名前で作る。既存ファイルを上書きしない）

**触らない**: `engine/core/` 配下、`engine/packs/math/geometry/` 配下、既存の recipe /
solver / template / visual モジュール（読むのは自由）。

## 落とし穴（既知・全部踏んである）

1. **概念IDの配線切れ**。recipe の `provides_concepts` に family が使う概念IDを全部載せる。
   載せ忘れると `check_cell` は通るのに台帳（capabilities）に載らない。
2. 概念IDは `concepts.yaml` にも `id` / `label` / `unit` の登録が要る。
3. **Lv 間で op 列が同じだと level_sep が落ちる**。
4. 問題文の数字が答えと衝突する事故が繰り返し起きている。生成した文面を実際に読む。

## 検証（全部通すまで完了ではない）

```
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py g1_l41 construction 1,2
PYTHONPATH=. .venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py     # 検査[1]が 0
```

## 報告

- 開いたセル一覧（unit / Lv / 与える図 / 作図手順を1行ずつ）
- 追加したファイルと登録名（recipe / solver / template / visual / 概念ID）
- 実測値（rejects・dup_rate・各 Lv の op 列）と、図の PNG を目視した結果
- **git commit はしない**（親がまとめて行う）
