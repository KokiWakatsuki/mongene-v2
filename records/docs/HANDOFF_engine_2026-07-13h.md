# 引き継ぎ書 engine 2026-07-13h（P2/C1 bespoke 4セル・C1 68/69・134/630）

本書は **Phase P2 を継続**し、C1（g1 数と式）の残 bespoke セルを実装した記録。
knowledge の cheap 横展開（13g で完了）に続き、**汎用ハブに乗らない bespoke 4セル**
（素因数分解 calc・科学的記数法 calc・有効数字判別 knowledge・式の意味解釈 knowledge）を
1セル群ずつ DoD 緑にしてコミットした。**残る C1 は l2 graph_table Lv1（数直線＝図つき初 C1）1セルのみ**。

## 0. まず読む順
1. `docs/goal_spec_2026-07-12.md`（ゴール仕様 v1.0・完成＝green 630/630・台帳 C1-C16）
2. **本書（最新）**
3. `docs/HANDOFF_engine_2026-07-13g.md`（§2 knowledge 3ハブ定石・§4 資産・§5 落とし穴）
4. `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック・§5 落とし穴の原典）

venv は `.venv/bin/python`。ブランチ `engine-m0-rework`。

## 1. 現状（このセッション終了時点）
- **合計 134/630（21.3%）**。**C1 g1 数と式 68/69（99%）**。C2 32/32・C5 34/36。
- コミット（このセッション）:
  - `c2133be` #70 素因数分解 calc l11 Lv1/Lv2（factorize_integer 新設）
  - `f299353` #71 科学的記数法 calc l60 Lv1/Lv2（scientific_notation 新設）
  - `e35ce20` #72 有効数字の桁判別 knowledge l60 Lv2（count_significant_figures 新設）
  - `432457f` #73 式の意味の解釈 knowledge l12 Lv2（interpret_expression 新設）
- 作業ツリーは clean（`scratchpad/` のみ untracked）。

### ⚠️ #73 の未確認事項（次アカウントが冒頭で処理すること）
#73（l12 knowledge Lv2）は **アカウント引き継ぎのためフルスイートを 99% 完了時点（失敗0）で
中断してコミット**した。他ゲート（check_cell gate0/dup0.01・spec lint0・mypy/ruff clean・
eval OK・targeted 201 passed・横断構造テスト257 passed = lint_clean/capabilities/curriculum/
concepts/frames/golden）はすべて green。**最初にフルスイートを単独で1回走らせ、18490+ passed を
確認せよ**（l12 は共有コード非変更＝ほぼ確実に緑）:
```
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q
```
（#71 で `frames.py` の calculation given_vocab に `sig_figs` を追加した際、
`test_frames.py::test_calculation_vocab_and_visual` の期待セットを追随修正済み＝この種の
「frame 語彙を厳密検査するテスト」は frame を触ったら必ず追随が要る。l12 は frame 非変更。）

## 2. このセッションの新しい学び（bespoke の定石）

### 2-#1 ★上付き指数は NFKC で通常数字に分解される（G-Q5t の要注意点）
`normalize_math_text` は NFKC 正規化するため、**`2³×3²` → `23×32`**（³→3・²→2 が基数に連結）、
`2⁵`→`25` になる。つまり display の上付きは「基数＋指数を連結した多桁数」トークンになり、
**素因数 2・3 単体トークンは display からは出ない**（srepr 側 `2**3*3**2` からは 2,3 が出る）。
- 素因数分解（#70）: 答えトークンは {連結多桁, 素因数, 指数}。問題文の数値は対象数 N のみ
  （whitelist）。素因数・指数・連結数はいずれも N と一致しないため素通り。**120seed 実測で確認**。
- 旧コメント「上付きは extract_numbers 非抽出」は**誤り**（NFKC 前提が抜けていた）。実挙動は連結。

### 2-#2 ★"10" を含む記法（科学的記数法）の漏洩回避（#71）
問題文が `a×10ⁿ（1以上10未満）` を含む＝**構造的に 1 と 10 が問題文の数値トークンに出る**
（whitelist されない）。よって答えトークンから 1・10 を排除する:
- srepr を **`4.8E4` 形**にして "10" トークンを出さない（`4.8*10**4` だと "10" が出て衝突）。
- display `4.8×10⁴` は NFKC で `4.8×104`＝"104"（≥100・単独 "10" は出ない）。
- 指数を **2〜9** に制御（1・10 を避ける）、**mantissa≠1**（純粋な10の累乗・丸め繰り上がりを
  構成側で除外）。丸め繰り上がり例 `9990,有効数字2桁→1.0×10⁴`（mantissa 1）は**有界リトライで除外**。
- 有効数字桁は **given に持たせて whitelist 化**（`sig_figs` を calculation frame に追加）。
  「○桁」は counter 正規表現（`_COUNTER_EXPR_RE` に「桁」あり）で scan 前に strip される二重安全。

### 2-#3 ★knowledge の数値答えは「漢数字・品名」で digit-free 化して素通り（#72/#73）
knowledge form は G-Q2 で asked=choice のみ。ChoiceAnswer の correct/distractors に **ASCII 数字を
入れない**のが鉄則①。桁数など数値の答えは:
- #72 有効数字桁: `三けた`（漢数字 二/三/四/五）＝ASCII 数字なし → answer トークン0で G-Q5t 素通り。
- #73 式の意味: 品名で記述（`買ったりんご全部の代金と…の合計`）・個数は `ひとつずつ` 等の
  和語で表現 → digit-free。誤選択肢も同様に品名・和語のみ。
これで問題文に 3x+5y など同じ数字があっても answer 側にトークンが無く**衝突が原理的に起きない**。

### 2-#4 bespoke の level_sep は mode 別 op 列（既存 calc と同じ流儀）
- 素因数分解: Lv1 `[divide_out_primes_in_order, write_prime_power_form]`（2手）/
  Lv2 `[test_successive_prime_divisors, …, …]`（3手・大きい素数の試し割りを先頭に追加）。
- 科学的記数法: Lv1 `[locate_decimal_point, write_scientific_form]` / Lv2 は
  `round_to_significant_figures` を先頭に追加。
- signature も Lv 毎に相異（R2 lint 必須）。knowledge の新セルも Lv1 と op 列を変えて level_sep。

### 2-#5 dup は「N の候補プールを 400+」で確保（calc の単一整数パラメータ）
calc の答えは対象数 N の決定論的関数＝**dup_key は N のみで分散**。100-seed 実測は推定より高く出る
（birthday 推定 0.135 → 実測 0.19）ので、**推定 ~0.11（候補 400+）を目安に**プールを取る。
- 素因数分解: 最大素因数のふるい（`lpf[n]==n ⇔ 素数`・O(n log log n)）で層別。
  Lv1 maxp≤13・[12,3000]→C=409（実測 dup 0.10）。Lv2 17≤maxp≤47・[200,3000]（dup 0.07）。
- knowledge の ChoiceAnswer は surface（measurement・品名・個数）を **params に含めて dup 分散**（鉄則④）。

### 2-#6 §10 sanction を必ず source_desc に明記
仕様の一部を落とす／絞るときは理由を source_desc に書く（監査可能性）:
- 素因数分解 Lv2「素数か合成数かの Yes/No 判定」は答えの型が分解形と異なるため独立セル化せず、
  試し割り手順として内包。
- 科学的記数法 Lv2「誤差の範囲を求める」は答えの型（区間）が違うため落とし、
  「有効数字指定＋四捨五入」に絞る。実世界題材（km 等）は word_problem 相当のため calc は単位なし数。
- 有効数字 knowledge Lv2「誤差の意味を適用」も型が違うため「桁の判別」に絞る。

## 3. 残タスク（優先順）

### 3.1 C1 の残（1/69）— l2 graph_table Lv1（数直線・図つき初 C1）
仕様（units.generated.yaml g1_l2.graph_table Lv1・基礎）:
> desc: 数直線上の点が表す数を読む／数を数直線に示す
> example: 数直線上で点Pが -3 と -2 のちょうど真ん中にある。Pが表す数を答えよ。（答え -5/2）

**これは C1 唯一の visual required セル**で、他 calc/knowledge と機構が違う。調査済みの要点:
- graph_table frame は `visual="required"`（`frames.py` GRAPH_TABLE_FRAME）。
  asked_vocab に `read_point`（読み取り）あり。given_vocab は expression/data_table/situation_params
  等（数直線の点位置を渡す新キーが要るなら 横展開の前例に倣い frame に追加＋test_frames 追随）。
- **図の描画は `register_visual("<name>")(builder)` で登録**（`engine/packs/math/visuals/graph.py`
  末尾 `register_visual("math.linear_graph")(render_linear_graph)` 参照）。builder は `(mr, ctx)->str(svg)`。
  family yaml の `text: {visual_builder: <name>}` で選択（`render/t1_template.py::render_visual` が
  `ctx.spec_level.text["visual_builder"]` を引く）。**数直線レンダラは未実装＝新規に書く**
  （既存は 2次元グリッド `render_grid_svg`。1次元数直線 SVG を新設するのが素直）。
- 図内テキストは `visual_plan.labels`（whitelist）に入れたものだけ許可（G-Q5v が SVG の
  `<text>` を labels と照合）。目盛の数値文字列を labels に機械一致させる（linear.py の
  `tick_labels` の流儀）。**答えの点 P の値そのものは labels に入れない**（漏洩）。
- 答え: 読み取りは SymbolicAnswer（例 -5/2）。G-Q5t は「答えの値が problem_text/hints/図に出ない」
  こと。図の目盛（-3,-2 等）は given/labels 由来で whitelist、点 P の値（真ん中 -5/2）は出さない。
  「ちょうど真ん中」型なら答えは端点の平均＝given から機械導出できて double-solve が綺麗。
- dup: 端点ペア（-3,-2 等）と分割位置（真ん中/1:2 等）で分散。surface を params に。
- **図つきは初 C1** なので、まず既存 g2 の graph_table（`g2_l21/l25/l26/l27` の draw/read）と
  `visuals/graph.py`・`render/t1_template.py::render_visual`・G-Q5v（`quality_gates.py`）を精読し、
  1次元版レンダラの最小実装から入るのが安全。図無し部分（recipe/solver/checker）は #70-#73 と同じ流儀。

### 3.2 その先（C1 完成後）
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
幾何 C7-C10・proof C15 は独立ファイルで大量に増える群＝**サブエージェント並列**が本領を発揮。

## 4. 資産（このセッションで追加したもの）
すべて既存の C1 calc/knowledge ファイルに追記。新規モジュールは作っていない。

### solvers
- `packs/math/solvers/arithmetic.py`:
  - `factorization_forms(n)` / `@register_solver("math.factorize_integer")`（素因数分解）
  - `scientific_forms(n, sig_figs)` / `@register_solver("math.scientific_notation")`（a×10ⁿ）
- `packs/math/solvers/letter_expr.py`:
  - `@register_solver("math.count_significant_figures")`（有効数字桁・漢数字 ChoiceAnswer）
  - `@register_solver("math.interpret_expression")`（式の意味・品名 ChoiceAnswer）

### recipes（同名で recipes/ 側に）
- `recipes/arithmetic.py`: `math.factorize_integer`（最大素因数ふるい `_LPF` で層別）、
  `math.scientific_notation`（mantissa≠1・指数2〜9 のガード）
- `recipes/letter_expr.py`: `math.count_significant_figures`、`math.interpret_expression`

### checkers / templates / concepts / frames / families
- checkers: `math.factorize_integer.double_solve` / `math.scientific_notation.double_solve`
  （arithmetic.py）、`math.count_significant_figures.double_solve` /
  `math.interpret_expression.double_solve`（letter_expr.py）
- templates: `lf_calc_factorize_v1` / `lf_calc_sci_notation_v1` / `lf_calc_sci_sigfig_v1`
  （arithmetic.py）、`lf_sigfig_judge_v1` / `lf_interpret_expr_v1`（letter_expr.py）
- concepts.yaml: `prime_factorization.execute_basic/advanced`・`scientific_notation.express_basic/sigfig`・
  `approximation.judge_significant_figures`・`letter_meaning.interpret_expression`
- frames.py: calculation given_vocab に `sig_figs` 追加（test_frames.py 追随済み）
- families: `g1_l11.calculation.yaml`（新）・`g1_l60.calculation.yaml`（新）・
  `g1_l60.knowledge.yaml`（Lv2 追記）・`g1_l12.knowledge.yaml`（Lv2 追記）
- golden: 各 family の新レベル分を approve 済み（既存レベルは不変）
- tests: `engine_tests/unit/test_recipes.py` に construct + double_solve property を追加
  （factorize/scientific_notation/significant_figures/interpret_expression 各 100-200 seed）

## 5. 次アカウントへの指示（要約）
1. **状態確認**: `git log --oneline -6`・`git status`・`goal_progress`（134/630・C1 68/69 を確認）。
2. **フルスイートを1回単独で走らせる**（#73 の最終ゲート確認・18490+ passed 期待）。緑なら次へ。
   ※万一 fail が出たら l12 関連（interpret_expression / g1_l12.knowledge / concepts）を疑う。
3. **C1 最後の1セル = l2 graph_table Lv1** を §3.1 の順で実装（図つき初 C1・新規数直線レンダラ）。
   DoD 順は #70-#73 と同じ: solver等5点セット → `pytest -k` → `check_cell`（gate0/dup≤0.20）→
   `spec_cli check`（背景可・遅い）→ `spec_cli approve`（golden）→ golden slice test →
   mypy --strict / ruff → `engine.eval` → **フルスイート単独** → コミット。
   図つきは G-Q5v（`visual_plan.labels` 白名簿）を追加で通す点だけ #70-#73 と異なる。
4. C1 完成（69/69）→ **C3 g3 数と式** へ。以降 幾何/proof はサブエージェント並列を検討。

### 鉄則（13g から不変・追補は §2）
- ①答えテキストに ASCII 数字禁止（→ 漢数字・品名・和語で digit-free 化）。
- ②dup は自由度の個数（calc は N プール 400+／ChoiceAnswer は surface を params に）。
- ③form=knowledge は asked=choice のみ（G-Q2）。
- ④ChoiceAnswer は surface を params に含めないと dup≈0.96。
- ⑤保留セルは realize の軸をずらすと入る（判別不可→意味想起／型が違うなら §10 sanction で絞る）。
- ⑥新 family/level は `test_recipes.py` の `_*_CELLS` か個別テストに必ず追加（property は自動増えず）。
- ⑦フルスイート背景実行中に新 yaml を書くと `test_all_m0_families_lint_clean` が偽陽性で落ちる
   ＝編集完了後に単独で回す。
- ⑧frame の vocab を触ったら `test_frames.py` の厳密検査を必ず追随修正。
- ⑨narration に数字を書かない（G-Q5t 偽陽性の元）。
- ⑩上付き指数は NFKC で通常数字に分解される（§2-#1）。"10" を含む記法は srepr を E 記法にして
   衝突回避（§2-#2）。
