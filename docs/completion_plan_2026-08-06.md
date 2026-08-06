# エンジン完成計画（2026-08-06 起点・429/630）

## 0. 前提の確認（実測）

**一次方程式・二次方程式は既に完成している。**

| 単元 | 残り |
|---|---|
| g1_l21〜l26（一次方程式） | 0 |
| g1_l27（方程式の利用・速さ） | **1**（word_problem Lv4） |
| g3_l24〜l30（二次方程式） | 0 |
| g3_l31（2次方程式の利用・動点） | **2**（word_problem Lv3/Lv4） |

優先しても伸びしろは3セルしかない。しかもこの3セルは**動点・速さの Lv4**で、
C6（y=ax²）の動点セルと同じ機構を要求する。→ Phase 1 に相乗りさせる。

## 1. 残り201セルの実態

| form | 残り | 性質 |
|---|---|---|
| graph_table | 58 | 曲線（放物線・双曲線）の描画資産がない |
| proof | 51 | **form ごと未実装**（frame も solver も checker もゼロ） |
| find_value | 36 | 既存 solver の横展開（空間図形・相似・円・三平方） |
| word_problem | 36 | **Lv4 発展 20・Lv3 12**＝易しいものは全部済んでいる |
| knowledge | 10 | 空間図形の用語（C8） |
| construction | 9 | form ごと未実装 |
| calculation | 1 | — |

### 「文章題の括りで一気に」はもう効かない

残り36の word_problem は Lv4 発展（20）と exam 融合（14）が中心で、
一つずつ違う数学（動点・空間図形・箱ひげ図・標本調査）を要求する。
form 単位で括る償却はすでに使い切った（word_problem_linear.py が6セル、
word_problem_quadratic.py が4セルを賄った、あの手は残っていない）。

**代わりに効くのは「単元クラスタ × form 横断」。**
同じ場面が graph_table と word_problem の両方に出るため、
場面ビルダーを1つ書けば2 form ぶん取れる。

例: `g3_l31`（動点・2次方程式で「面積が S になるのは何秒後か」）と
`g3_l38`（動点・2次関数で「面積 y を x の式で表せ」）は**同じ動く点の場面**。
1つの scene で両方賄える。

---

## Phase 0：未マージの回収（最優先・最も安い）

前セッションで投入したサブエージェント4体分の作業が worktree に未コミットで残っている。

| worktree | 内容 |
|---|---|
| `agent-a30aabe1be2d40155` | C10 相似・円 find_value（family 6本＋checker） |
| `agent-a618d72924f65b436` | C8 空間図形 計量（family 3本＋registry） |
| `agent-a8e8bcc4fb91f2ce3` | C10 三平方 find_value（solver `pythagorean_find_value.py`） |
| `agent-ab5d60e8b08501e46` | C8 空間図形 knowledge（solver `g1_space.py`） |

いずれも基点は `7545348` に揃っている。
検証（`check_cell.py` 100seed 実測 → テスト → eval）→ 順次マージ。

**競合面は `concepts.yaml` と各 `__init__.py` だけ**（追記のみ）なので、順番にマージすれば
衝突は軽微。→ 見込み 429 → 約460。

---

## Phase 1：曲線グラフ基盤 → C4 + C6 + 動点 word_problem（約26セル）★最大レバレッジ

### 投資（1回）
`visuals/graph.py` はいま直線しか描けない（`register_visual("math.linear_graph")`・
`visual_plan.elements` の `kind == "line"` のみ）。
グリッド土台（`render_grid_svg` / `_GridScaffold`）は曲線非依存なので、
`kind == "curve"`（サンプリング点列 → polyline）を足すのは局所的な拡張。

これ1本で放物線・双曲線・比例直線がすべて描けるようになる。

### 回収（並列3体）

| 束 | セル |
|---|---|
| C4 比例・反比例 graph_table | g1_l30/l31/l32/l34/l35/l36 → 12（C4 が 17/29 → 29/29 完成） |
| C6 y=ax² graph_table + knowledge | g3_l33/l34/l36/l37/l38 → 8（C6 が 13/21 → 21/21 完成） |
| 動点・速さ word_problem | g3_l31 Lv3/Lv4・g3_l38 Lv4・g3_l37 Lv3/Lv4・g1_l36 Lv4・g1_l27 Lv4 → 6 |

**3束目に、優先したい一次方程式・二次方程式の残り3セルが全部入る。**

---

## Phase 2：C8 空間図形（24セル・0%）

丸ごと未着手の最大の白地。Phase 0 で2体分が回収済みになる想定なので残りを埋める。
- knowledge 7（多面体・ねじれの位置・回転体・投影図・球）
- find_value 8（表面積・体積・球）
- graph_table 等 9

図は不要なセルが多く（用語・計量）、単価が安い。

## Phase 3：C10 図形 find_value 残り（約20セル）

Phase 0 で2体分が回収済みの想定。残りは三平方の応用（g3_l53/l54/l55/l56）が中心。
Phase 1 の座標平面資産が g3_l54（2点間の距離）に効く。

## Phase 4：C11 データ・統計（14セル）

g1_l54〜l58・g2_l52〜l57・g3_l57/l58。
graph_table（ヒストグラム・箱ひげ図）と word_problem（統計的探究プロセス・標本調査）。
箱ひげ図の描画が新規資産。**Lv2 の word_problem が4つある＝残り少ない易しい文章題**。

## Phase 5：C13 exam 融合（17セル）

`exam_l1`〜`exam_l7` の find_value / graph_table / word_problem。
**既存単元 solver の合成**（`packs/math/recipes/exam_fusion.py` が既にある）ので
新しい数学はほぼ不要。ただし Lv3/Lv4 のみ＝多段構成が要る。
Phase 1〜4 が終わっているほど安くなるので、後半に置く。

## Phase 6：C15 proof（51セル）★最大の投資

form ごと未実装。frame・solver・checker・テンプレートを新規に設計する必要がある。

設計の勘所（未検討・着手時に詰める）:
- 「証明を書かせる」ではなく**証明の骨格を穴埋めさせる**形式に落とす
  （仮定・使う定理・結論の対応づけ）ことで T1 決定論に収まるか
- 合同条件・相似条件・円周角の3系統でテンプレート化できるか
- 答えの照合は「文字列一致」ではなく**根拠の集合一致**にできるか

対象は g2_l38〜l50（合同・三角形と四角形）が13単元で最大の塊。

## Phase 7：C16 construction（9セル）

M2 送り扱い。最後。

---

## 進め方の運用ルール（前セッションで踏んだ事故の再発防止）

1. **worktree の基点確認を必ず最初にやらせる**
   （過去に旧 master 基点で作られる事故が複数回。ずれていたら `merge --ff-only` で揃える）
2. **`spec_cli check` の `dup_rate` は常に 0.0 で当てにならない**
   → `scratchpad/check_cell.py` の 100seed 実測が本物
3. **ゲートは答えが 0 や 1 に潰れる退化を素通りする**
   → property テストで固定する
4. **eval は「テスト緑」とは別に必ず回す**
   （fingerprint が op 列なので Lv 間で op 列が同じだと level_sep が黙って壊れる）
5. **level_sep は「何を文字に置くか」を動かすのが一番効く**
6. **params は「本文に出ている数値」だけ**（導出値を置くと検証に穴があく）
7. **並列度は3〜4体**。競合面は `concepts.yaml` と各 `__init__.py` のみ（追記）なので
   順次マージすれば衝突は軽微
8. engine 検証は `--no-cov` 必須

## 見込み

| Phase | 累計 |
|---|---|
| 0 回収 | 約460 |
| 1 曲線グラフ | 約486 |
| 2 C8 空間図形 | 約505 |
| 3 C10 残り | 約520 |
| 4 C11 統計 | 約534 |
| 5 C13 exam | 約551 |
| 6 C15 proof | 約602 |
| 7 C16 construction | 611 + 端数 = 630 |

Phase 0〜5 で **551/630（87%）**。残りは proof と construction という
「form ごと新規設計」の2つだけになる。
