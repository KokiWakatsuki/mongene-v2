# 引き継ぎ書 engine 2026-07-14（P2/C3 数と式g3 ほぼ制圧・180/630・最優先=開発サイクル高速化）

## ★★ 運用モデル（2026-07-14 A/Bテストで決定・最優先で従うこと）★★
- **統括＋実装＝Sonnet5・レベル「高」**。C3/C5 の calc・knowledge セルと本§4級の core改修は、**Sonnet5-高 が Opus4.8-超高 と実測 full parity**（同一課題を Sonnet5-高×2＋Opus4.8-超高×1 に解かせ、Opus-超高が敵対採点。実走で `spec_cli ok:true`・101テストpass・mypy/ruff clean・dup 0.07 を確認。**むしろ Opus-超高 の方が台帳不整合の latent 欠陥を出した**＝この構造化・チェックリスト型の仕事は「モデル強度」より「ガードレール」が効く）。
- **手順0（毎セッション必須）**：アプリのモデル選択で **Sonnet5・レベル高** に設定してから着手する。**モデル/レベルはセッションUI設定でファイルに残らない**ので、新アカウント・新セッションでは毎回この設定から始める。
- **難所だけ Opus 検証ゲート**：**幾何(C7-C10)・visual配線・proof(C15)・frame語彙変更** は parity 未検証＝リスク領域。これらの approve 前に、**Opus のサブエージェント/ワークフローで差分を DoD＋台帳に照らし敵対レビュー**させる（＝セッションは Sonnet5-高 のまま、検証パスだけ Opus に委譲。`ultracode` を付けると多エージェント総動員）。バックログ（C3残/C5/calc/knowledge）には検証ゲート不要。
- **モデル非依存の追加ガードレール2つ**（Opus-超高 ですら踏んだ箇所・lint非対象）：①approve前に family の level キーを `units.generated.yaml` の台帳と diff（捏造レベル/欠落レベル検出）。②新規 template を作らず**登録済みテンプレを再利用**する。
- **この日の A/Bテスト副産物**：(a) §4 高速化の**parity検証済み参照diff**（mtimeキーで118 family+5 curriculum を網羅・lru_cache版とlock版の両案）がワークフロー出力に保存済み。(b) **C3 残 l22「式の値」の全ゲート通過実装が git stash に退避**（`stash@{0}`・spec_cli ok・101テストpass）。→ §5.1 着手時に流用可。

本書は **Phase P2 を継続**し、C1 を完成（数直線・図つき初セル）＋ **C3（g3 数と式）の非幾何パートを 0→66% まで開通**した記録。
次アカウントの**最優先は「開発サイクルの高速化」**（§4・generate の YAML 再パースを消す。実測 395ms→4ms・約100倍）。

## 0. まず読む順
1. `docs/goal_spec_2026-07-12.md`（ゴール仕様 v1.0・完成＝green 630/630・台帳 C1-C16）
2. **本書（最新）**
3. `docs/HANDOFF_engine_2026-07-13h.md`（§2 bespoke 学び・§3.1 図つきセルの配線）
4. `docs/HANDOFF_engine_2026-07-13g.md`（§2 knowledge 3ハブ定石）／`docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック）

venv は `.venv/bin/python`。ブランチ `engine-m0-rework`。

## 1. 現状（このアカウント終了時点）
- **合計 180/630（28.6%）**。**C1 69/69（100%完成）・C2 32/32（100%）・C3 45/68（66%）・C5 34/36（94%）**。
- 最新コミット `8f53e04`。**作業ツリー clean**（`scratchpad/` のみ untracked）。フルスイート **22777 passed**（単独走行・約6:23）。
- 学年別: g1 69/209・g2 66/197・g3 45/189・exam 0/35。

### このアカウントのコミット（#74〜#79）
- `1b924c1` #74 C1完成 l2 graph_table Lv1 数直線（図つき初C1・**新 `visuals/number_line.py`** 1次元SVGレンダラ）
- `a0a41c3` #75 C3展開 l1〜l6 calc 11セル（**solver `math.expand_expression`**=sympy.expand・polynomial.py）
- `235e6f9` #76 C3因数分解 l7〜l11 calc 8セル（**solver `math.factor_expression`**=sympy.factor・polynomial.py）
- `b6cdb9c` #77 C3平方根 l14/l17〜l21 calc 10セル（**新 `radical.py`**・`math.simplify_radical`=expand+radsimp）
- `86d9bba` #78 C3二次方程式 l24〜l28 calc 9セル（**新 `quadratic.py`**・`math.solve_quadratic`=sympy.solve）
- `8f53e04` #79 C3 knowledge 7セル（既存ハブ term_recall/recall_rule に domain/topic 追加・新solverゼロ）

## 2. このアカウントの新しい学び（重要順）

### 2-#1 ★generate() は毎回 YAML を再パースする（＝最優先の高速化対象・§4）
`generate()` → `resolve()`/`assemble_problem()` は `_default_families()`（**118 family YAML を全パース**）と `load_curriculum()` を**無キャッシュで毎回**実行する。cProfile で `yaml.scanner` が 2.9s/3.2s を占める。
- **実測**: default(無キャッシュ) **395 ms/generate** vs families/curriculum を注入(キャッシュ相当) **4 ms/generate ＝約100倍**。
- 影響: golden slice（**540 golden を全件 generate 再生成**）＋ test_eval_suite が generate を大量に呼ぶ → フルスイートが 1ワーカーに集中し 6:23 に漸増。dup 測定・大量生成も遅い。
- 回避運用（現状）: **dup 測定・大量検証は `build_mr`（`eval._harness.build_mr` は env キャッシュで高速）で行う**。generate 系はスモークと最終ゲートに限定。

### 2-#2 ★式/根号/解の答えの G-Q5t（漏洩）
- 展開/因数分解の答えは**自由変数を含む式** → G-Q5t は `_expr_has_free_symbol` 分岐で **display 全体一致のみ検査**（個々係数は非検査＝積の形と展開/因数分解形は構造が違い漏洩しない）。
- 平方根/2次解の答えは**定数扱い**（√は自由変数でない）→ 数値トークン検査。だが**問題文の数値はすべて given 由来（whitelist）・テンプレは数字なし**なので、答えが問題文に現れる値はすべて whitelist され漏洩しない。
- **★narration に数字を書かない（鉄則⑨）は徹底が要る**: #78 で `compute_discriminant` の narration「b²-4ac」の **"4" が答えの根号係数トークン(-4)と衝突**し G-Q5t 漏洩（l26 Lv3 seed7）。判別式は「根号の中の値」等と語で述べる。**ただし "0" は given の "=0" で常に whitelist されるので narration に使ってよい**（積が0・=0の形）。

### 2-#3 ★sympy の等価判定に `diff.evalf()` を使うな（ハングする）
`diff.evalf()` は**記号的にゼロの式でゼロ確定のため精度を無限に上げてハングする**（radical で6分間99%CPUで発覚）。→ recipe/test の恒真確認は **`diff.equals(0)`**（数値サンプリング併用で確実に止まる・~5-30ms）を使う。solve 系は各解を代入して `.subs(x,r).equals(0)`。

### 2-#4 ★sympy は平方根を自動簡約する → solver は expand で十分速い
`sqrt(3)*sqrt(6)` は sympify 時点で `3√2` に、`sqrt(48)` は `4√3` に自動簡約される。非有理化系は **`sympy.expand`(0.4ms)** が `sympy.simplify`(6.7ms)と**同結果で約15倍速**（全modeで実測一致）。有理化（分母に根号）系のみ `sympy.radsimp` が要る。

### 2-#5 ★段階的相異ドロー必須（無限ループ回避）
`while len({k1,k2,k3}) < 3: k3 = draw(...)` は **k1==k2 のとき3つ揃わず無限ループ**（radical add_roots_simplify で数分ハング）。→ 各段で前の値を除外して引く（k2≠k1・k3∉{k1,k2}）。dup 用の単一自由度セルは範囲を広く（共通因数 ax²+bx=0 は a,b のみ→a∈2..6・b∈±40で400通り）。

### 2-#6 ★図つきセルの配線（#74・C1初）と knowledge ハブ償却（#79）
- 図つき: recipe が `MR.visual_plan(style/labels/elements)` を返す → family yaml `text.visual_builder` で登録名選択 → `core/render/t1_template.py::render_visual` が `registry.visual(name)(mr,ctx)` を呼び SVG 生成。**G-Q5v** は SVG の全 `<text>` ⊆ `visual_plan.labels`（集合所属）＋ asked→forbidden_visual_elements の kind を含めない。答えの値は `<text>` で描かない。
- knowledge 償却: **`_TERM_MAPS[domain]`/`_RULE_MAPS[topic]` に辞書追加 ＋ recipe の `_draw_term_statement`/`_draw_rule_statement` に branch 追加（surface に具体例）＋ provides_concepts 追加 ＋ concepts.yaml ＋ family ＋ test_recipes の `_TERM_RECALL_CELLS`/`_RULE_RECALL_CELLS` に追加**。**答えは漢字/漢数字で digit-free 必須**（二次方程式・根号・循環小数）。既存ハブへの追加のみ＝既存 golden 不変。

### 2-#7 背景プロセスの掃除（ユーザー指摘対応）
- **`until [ -s file ]; do sleep N; done` の待機ループは使うな**（監視先が空だと永久ループ）。background task の**完了通知**で待つ。
- 暴走した inline `python -c` は `pkill -f <部分文字列>` で取りこぼす（parens/改行が混じる）→ **PID 指定で kill**。**`pkill -f Python` は uvicorn（ユーザーの API サーバ）を巻き込むため分類器が拒否する**。

## 3. 最優先タスク（§4）: 開発サイクルの高速化 ★委任

### 4.1 何を直すか
`generate()` が呼ぶ **`_default_families()` と `load_curriculum()` の結果をプロセス内でキャッシュ**し、YAML 再パースを1回に集約する。**実測で generate が 395ms→4ms（約100倍）**、フルスイート ~6:23 → 推定 ~2分、golden slice 540件 ~216s → ~2s になる見込み。

### 4.2 実装方針（`engine/core/pipeline.py`・core 改修＝慎重に）
- `_default_families()`（`engine/core/pipeline.py:41`）と `load_curriculum()`（`engine/core/curriculum.py`）に **`functools.lru_cache`（引数なしの既定経路）** を付けるのが最小。test_recipes.py の `_make_ctx` が既に `lru_cache(maxsize=1)` で同型の高速化を実証済み（313ms→数秒、60倍）＝**同じ手筋**。
- **注意（キャッシュ無効化の要検討点）**:
  1. `spec_cli approve`（golden 生成）や `test_all_m0_families_lint_clean` の**一部テストは family/concepts YAML を編集してから generate/capabilities を呼ぶ**可能性がある → 単純な process-lifetime lru_cache だと**編集後もスタール**する。対策候補: (a) family/concepts の **mtime をキーに含める**キャッシュ、(b) 編集する側が `<cache>.cache_clear()` を呼ぶ、(c) core は無キャッシュのまま残し、`generate()` に「families/curriculum を渡さない場合はモジュールキャッシュを引く」薄い層を足す。**最も安全なのは mtime キー**（ファイル変更を自動追随）。
  2. `capabilities()`（`pipeline.py:373`）と `goal_progress`・`eval._harness` も `_default_families()`/`load_curriculum()` を使う → キャッシュ化の恩恵が波及するが、同じスタール注意が要る。
  3. テストで custom families を注入する経路（`generate(req, families=..., curriculum=...)`）は**引数優先**なので影響しない（既存動作不変）。
- **代替/追加の高速化**: golden slice（`engine_tests/golden/test_golden_slice.py`）は 540 パラメータが1モジュールに集中し **xdist が1ワーカーに寄せる**。`@pytest.mark.parametrize` の分散を効かせる（`pytest -n auto --dist loadscope` ではなく `loadfile`/`load`）か、golden 比較を「再生成」でなく「保存済み Problem の再パース＋deterministic 再構築の軽量比較」にする案もあるが、**まず 4.2 のキャッシュだけで golden slice は ~100倍速くなる**ので、キャッシュ優先。

### 4.3 検証（DoD）
- キャッシュ後に **`generate` の結果が完全にバイト一致**すること（golden slice が全 pass ＝回帰なし）。
- **family/concepts YAML を編集 → generate が新結果を返す**ことを確認（mtime キーなら自動、lru_cache なら cache_clear テストを足す）。
- mypy --strict / ruff clean。**フルスイート単独**で緑＋**総時間が短縮**したことを確認（before 6:23 → after 記録）。
- core 改修なので、`test_generate*`・`test_golden_slice`・`test_eval_suite`・`test_capabilities` を重点的に見る。

## 5. 残タスク（高速化の次）

### 5.1 C3 の残（23/68）
- **平方根 calc 残**: l15 大小比較（√5<√8・compare/order 型・答えは不等号 or 順序 Tuple）・l16 有理数無理数/循環小数（**decimal↔fraction 変換 calc**・5/11→循環小数・0.27循環→分数）・l22 式の値（x=√3+1 で x²-2x を代入＝**radical を式に代入**・expand 再利用可）。
- **calc 残**: l12 式の計算の利用（数の計算への応用・式の値）。
- **knowledge Lv2/classify/verify 残**（専用 solver 要）: l3 乗法公式の識別・l14 Lv2（√(a²)=|a| 判別）・l16 Lv2（有理数/無理数の分類）・l24 Lv2（値が解かの verify＝solve_quadratic evaluate 再利用可）・l26 Lv1（a,b,c 識別・数値答えを ChoiceAnswer 化＝digit-free 工夫要）・l28 Lv2（解法判断）。
- l13 は図形の証明（proof）＝**C15 送り**（word_problem/proof は T3・M1 寄り）。

### 5.2 その先（C3完成後）
- **C5 残2**（g2 一次関数の詰め）。
- **最大の山＝幾何 C7〜C10（140セル）＋ proof C15（51）**＝全体の約3割。図 required・独立ファイル大量増のため**サブエージェント並列**が本領（別ファイルなら並行可・共有ファイルは直列）。まず高速化を入れてから並列展開すると回転が速い。

## 6. 資産（このアカウントで追加）
- **新モジュール**: `packs/math/visuals/number_line.py`（1次元数直線SVG）・`packs/math/{solvers,recipes,checkers,templates}/radical.py`（平方根）・同 `quadratic.py`（2次方程式）。各 `__init__.py` に import 登録済み。
- **polynomial.py に追加**: solver `expand_expression`/`factor_expression`、recipe `expand_product`/`factor_polynomial`、checker・template（lf_expand_v1/lf_factor_v1）。
- **letter_expr.py に追加**（#79 knowledge）: `_TERM_MAPS` に square_root/real_numbers/quadratic_terms、`_RULE_MAPS` に expansion_meaning/factorization_relation/sqrt_magnitude、recipe の statement branch、provides_concepts。
- **families**: g3_l1〜l11.calculation（展開/因数分解）・g3_l14/l17〜l21.calculation（平方根）・g3_l24〜l28.calculation（2次）・g3_l2/l7/l14/l15/l16/l22/l24.knowledge。golden 全 approve 済。
- **concepts.yaml**: polynomial.expand_*/factor_*・radical.*・quadratic.*・各 knowledge concept。
- **tests**: test_recipes.py に `_EXPAND_CELLS`/`_FACTOR_CELLS`/`_RADICAL_CELLS`/`_QUADRATIC_CELLS` の property＋construct、`_TERM_RECALL_CELLS`/`_RULE_RECALL_CELLS` に C3 分追加。

## 7. 次アカウントへの指示（要約）
1. **状態確認**: `git log --oneline -6`・`git status`・`goal_progress`（180/630・C3 45/68・clean）。フルスイートを1回単独で走らせ 22777 passed を確認（緑なら健全）。
2. **最優先＝§4 開発サイクル高速化**（generate の YAML 再パースをキャッシュ）。**core 改修なので mtime キー等でスタール回避＋フルスイートで回帰ゼロを確認**。before/after の総時間を記録。
3. その後 §5.1 で C3 完成 → C5 残2 → 幾何/proof（サブエージェント並列）。
4. **DoD 順**（#75-#79 と同じ）: solver等5点セット → `pytest -k` → **dup は build_mr で100seed実測（≤0.20）** → spec_cli approve(golden) → golden slice → mypy strict/ruff（新規のみ clean・既存 test_recipes の E702 債務は無視） → `engine.eval`（exit0・dup/level_sep/coverage） → **フルスイート単独** → commit。

### 鉄則（不変・§2 に追補）
- ①答えテキストに ASCII 数字禁止（漢数字・品名・和語・漢字で digit-free 化。ただし "0" は "=0" で whitelist され安全）。
- ②dup は自由度の個数（calc は N プール400+／ChoiceAnswer は surface を params に／単一自由度は範囲を広く）。**測定は build_mr で高速に**。
- ③form=knowledge は asked=choice のみ（G-Q2）。ChoiceAnswer は surface を params に含める。
- ④level_sep は同一 family 内で **op 列（fp）を相異**させる（数値域だけ変えると P-1 偽レベル回帰）。
- ⑤退化を有界リトライで除外（定数化・答え0・平方⇔平方差・k1==k2 無限ループ）。**等価判定は `.equals(0)`（evalf はハング）**。
- ⑥新 family/level は `test_recipes.py` の `_*_CELLS` に必ず追加（property は自動増えず）。
- ⑦narration に数字を書かない（"b²-4ac" の 4 が漏洩した実バグ・§2-#2）。"0" は例外。
- ⑧frame の vocab を触ったら `test_frames.py` の厳密検査を追随。今回の C3 は frame 変更なし（既存 calculation/knowledge 語彙で足りた）。
- ⑨背景待ちは**完了通知**で（sleep ループ禁止）。暴走 python は PID 指定 kill（`pkill -f Python` は uvicorn を巻き込み拒否される）。
