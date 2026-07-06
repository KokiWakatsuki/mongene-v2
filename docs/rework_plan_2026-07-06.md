# 再設計・再構築 計画書（実装者：Sonnet 向け）

作成日: 2026-07-06
計画立案: Opus（設計レビュー担当）
実装: Sonnet

---

## 0. この計画書の位置づけ

生成精度が伸び悩んでいる原因を、個別バグではなく**アーキテクチャの賭け方**と**評価ループの空回り**という2つの構造問題として診断した（詳細は本書 §1）。
本計画は、その診断に基づく **3フェーズの再構築**を定義する。実装は本書の順序（フェーズ1→2→3）で進めること。

**最重要の設計思想（本書の背骨）**:
> フェーズ2で作る「LLMを使わない決定論的評価器」は、フェーズ3で「生成時の受理／棄却フィルタ（verifier）」として再利用する。
> つまり **evaluator = verifier**。評価のための作業は捨て駒にならず、そのまま製品の品質保証機構になる。

**ユーザーからの制約（厳守）**:
- 評価ループは**LLMを使わない**（LLM-as-judge 禁止）。理由: (a) 生成AIと評価AIが同一だと自己満足的で循環する、(b) Geminiクォータを評価に食わせない、(c) 決定論的評価は再現可能・無料・高速。
- 生成（＝製品を作る工程）にはLLMを使ってよい。ただし後述の通り**生成は稀に・評価は毎回**という非対称にして、LLMコストを評価ループから切り離す。

---

## 1. 診断サマリ（なぜ伸び悩むか）

### 1.1 設計思想の問題：「計算骨格ファースト」を全形式に強制
システムの背骨は「Blueprint+Verb が SymPy で数値の答えを計算 → MiddleRepresentation(数値骨格) → LLM が翻訳」。
これは `calculation` には最適（SymPyが正しさを保証＝本システムの moat）。しかし残り4形式
（`word_problem` / `proof` / `knowledge` / `visual`）にも同じ型を強制しており、依存関係が逆。
- 証拠: `BasicCalculationStructure` は `supported_forms=["calculation"]` だけ宣言するのに、mappingは同レッスンに
  `knowledge`/`visual`/`word_problem` を要求 → 契約矛盾を誰も止めず、静かに計算問題へフォールバック。
- 結果: 「符号のついた数」の word_problem が `(-1)+25=24` の素の足し算になる。`knowledge=0%`, `proof=20%` の真因。
- **form も difficulty も、計算骨格に後付けした「LLMへのスタイル指示」に過ぎず、生成の構造を決めていない。**

### 1.2 評価ループの問題：測っている対象が製品ではない
- 評価は `/inspect`(LLM前) か**モックLLM**に対して実施 → 非計算形式は肝心のLLM工程を通す前で測られ、当然全滅（偽陰性）。
- 修正の打点が症状レベル: 失敗レッスン群に専用Blueprintを1つずつ追加（11→17個）。線形に増やしても
  `form × lesson × level` の3次元モデルには手が入らず、指標は揺れるが登らない。
- 固定された正解基準（参照問題セット）が無く、「改善」が測定不能でループが漂流。

### 1.3 打ち手の方向
- 非計算形式は「骨格→翻訳」から「**生成してから検証（generate-then-verify）**」へ反転。
- 評価を**実出力（LLM後）× 決定論ゲート**に固定。オペランドジッターの難易度を構造特徴ベースに置換。

---

## フェーズ1：未コミット変更の整理（最優先・小）

### 目的
作業ツリーが不整合。**コミット済みの `master_data/mapping.json` が、未コミットの新Blueprintファイル群を参照している**
ため、いま `git checkout` し直すと import 崩壊で壊れる。まず HEAD を自己完結・再現可能な状態に戻す。

### 現状の分類（git status を以下に仕分けよ）
| 種別 | 対象 | 処理 |
|---|---|---|
| A. コミットすべき機能実体 | 未追跡の新Blueprint: `solve_equation.py`, `descriptive_stats.py`, `sample_survey.py`, `factorize.py`, `quadratic_function.py`, `simultaneous_equations.py`, `knowledge_base.py` / 新Verb: `factorize_verb.py`, `simultaneous_eq_verb.py`, `triangle_area_verb.py` / 修正: `registry.py`(params機構), 各 atom/blueprint/translator/router | コミット |
| B. 上記に連動する既存修正・テスト | `M` が付いた atoms/blueprints/tests 群 | Aと同じ論理単位でコミット |
| C. 評価成果物（コミット不要） | `reports/*.json`（eval_batch_*, eval_retry_*, inspect_results 等 45件）, `reports/*.md`(評価レポート), `reports/generated_problems.jsonl`, `reports/forms_research.csv` | `.gitignore` に追加して除外 |
| D. ゴミ | `.DS_Store`, `docs/.DS_Store` | 削除 + `.gitignore` に `.DS_Store` 追加 |
| E. ドキュメント | `docs/*.md`(設計書), `docs/problem_image_collection/`, `docs/atom_verb_spec.json` | 内容確認の上コミット |

### タスク
1. `.gitignore` に `**/.DS_Store` と `reports/*.json` `reports/*.jsonl` `reports/*.csv`（設計上コミットしたい成果物があれば例外指定）を追加。既存の `reports/perf_eval/` 除外はそのまま。
2. 既存の `.DS_Store` を追跡から除去（`git rm --cached`）し削除。
3. **論理単位でコミットを分割**（例: ①新Blueprint+Verb+registry の param機構、②連動する atom/test 修正、③mapping関連、④docs）。
   各コミット後に `SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/ -q` で **256件全通過**を確認。
4. コミットメッセージ末尾に指定の Co-Authored-By を付与。

### 完了条件
- `git status` がクリーン（追跡対象に評価成果物・.DS_Store が残らない）。
- クリーンな作業ツリーで `pytest` 全通過。
- `git stash` → checkout → 復帰しても import 崩壊しない（HEAD 自己完結性の確認）。

### 落とし穴
- 新Blueprintを消してはいけない（mapping.json が参照済み。消すと 17→11 で mapping 不整合）。**コミットして整合させる**のが正。
- ただし「症状ごとにBlueprintを増やす」路線自体はフェーズ3で見直す。ここでは**現状を壊さず固定するだけ**。

---

## フェーズ2：測り方の修正 ＝ 決定論的評価ハーネス構築（本計画の中核）

### 目的
**LLMを使わず**、**実際の生成出力（LLM後の最終問題）**に対して、再現可能・無料・高速に品質を測る仕組みを作る。
これが後段（フェーズ3）で生成時の受理／棄却フィルタに昇格する。

### 2.1 生成と評価の分離（LLMコストを評価から切り離す設計）
- **生成は稀に**: レッスン×形式×レベルの**参照コーパス**を一度だけ実LLMで生成し、`tests/fixtures/reference_corpus/` に凍結保存する。
  生成手段は Gemini 有料枠 or Claude Code CLI（クォータ回避）。**システムを変更したレッスンだけ再生成**する差分運用。
- **評価は毎回**: 凍結コーパス（保存済みJSON）に対してゲート群を回す。ここは 100% LLM不使用・無料。
- これにより「AIは修正に使い、評価はLLMなし」というユーザー制約を構造的に満たす。

### 2.2 決定論ゲート群（SymPyの ground truth を利用、LLM判定なし）
各生成問題に対し、以下のゲートを pass/fail で判定する。**答え・入力数値・形式ラベル・単元タグはシステムが既に保持している**ため、
LLM無しで機械照合できる。ゲートは `scripts/eval_gates/` に1ファイル1ゲートで実装（拡張しやすく）。

| ID | ゲート名 | 判定内容（決定論） | ground truth 源 |
|---|---|---|---|
| G1 | 答え漏洩 | SymPyの答えの値が problem_text に出現していたら FAIL | `answer.sympy_form/text_form` |
| G2 | 数値整合 | Verbが使った入力数値（寸法・オペランド）が problem_text に過不足なく出現。LLMが数値を捏造/改変したら FAIL | `sampled_nouns_info`, logic_steps operands |
| G3 | 答え正当性 | 生成問題文の数式を SymPy で再解答し、ground truth と一致するか（計算形式で自動化。他形式は G4 で代替） | SymPy 再計算 |
| G4 | 形式適合 | 形式別ヒューリスティック（下記 2.3） | `problem_form` |
| G5 | 範囲逸脱 | problem_text/answer が当該学年の未習語彙・演算を含んだら FAIL。`forbidden_words.txt` と `prerequisite_graph.yaml`（未習単元の語彙）で照合 | grade, prerequisite_graph |
| G6 | 難易度単調性 | 構造難易度特徴（下記 2.4）を min<mid<max で単調増加しているか | MR（logic_steps数・数値規模・√/π/分数の有無等） |
| G7 | レンダリング健全性 | LaTeX がパース可能・`$$`/`\[` 不使用・visual形式は SVG が非空かつ整形式XML | problem_text, visual SVG |

**スコア集計**: レッスン×形式×レベルごとに G1–G7 の pass/fail ベクトルを出し、
「全ハードゲート通過率」を主指標にする。これがLLM評価の A/B/E を置き換える再現可能指標。

### 2.3 形式適合(G4)の決定論ルール（LLMを使わない形式判定）
完全ではないが、**構造欠陥の高再現率検出器**として機能する:
- `knowledge`: 「次の計算をしなさい」や `式＝数値` の裸パターンを**含んだら FAIL**。定義/性質/正誤/用語/穴埋めのマーカーを**含むべき**。
- `proof`: 「証明」＋構造マーカー（仮定/結論/∴/合同/相似/∠/△）を含むべき。裸の計算式なら FAIL。
- `word_problem`: 場面設定名詞（工場/公園/店/速さ/人数… の語彙リスト）を含むべき。裸の式なら FAIL。
- `visual`: `visual_dsl` が非 null（component_type ≠ NullRenderer）**かつ** 本文が「図/グラフ/右の図」を参照。
- `calculation`: 式を含み物語を含まない。

### 2.4 難易度特徴(G6)の定義（オペランドジッターの廃止）
難易度を「数値の大きさ」ではなく**構造特徴の合成**で測る。最低限:
`step数 = len(logic_steps)`, 数値の桁/絶対値, √/π/分数/負数の有無, sub_question 数, 補助線/補助要素の要否。
これらから合成難易度スコアを算出し、min<mid<max の単調性を検査する。
（フェーズ3の難易度モデル再設計と同じ特徴セットを使う＝二度手間にしない。）

### 2.5 自然さの天井について（正直な限界）
決定論ゲートは**欠陥検出（漏洩・形式崩れ・範囲逸脱・答え誤り）には強いが、「市販問題集レベルの自然さ」は完全証明できない**。
- 日常の反復ループはゲート（LLM不使用）を主駆動にする。
- 自然さの校正は、**マイルストーンごとに 50 問程度の人手 or LLM スポットチェック**を**ループの外**で行う（毎回は回さない）。
- これによりループのLLMフリー性を保ちつつ、自然さのギャップを隠さない。

### タスク
1. `tests/fixtures/reference_corpus/` の設計（レッスン×形式×レベルのキーで凍結）。生成スクリプトは差分再生成対応。
2. `scripts/eval_gates/` に G1–G7 を1ファイル1ゲートで実装。各ゲートは `(problem, ground_truth) -> PASS/FAIL/理由`。
3. `scripts/run_gates.py`（凍結コーパス全走査 → ゲート通過率レポート `reports/gate_report.md`）。
4. 既存の `scripts/evaluate_*.py`（LLM/モック依存の旧評価）は**廃止予定**として明記。混同を避ける。

### 完了条件
- 凍結コーパスに対し `run_gates.py` が LLM を一切呼ばずに通過率レポートを出す。
- G1（答え漏洩）が現状の generated_problems.jsonl の「答え:24」漏洩を確実に検出できる（回帰テスト）。
- ゲート自体の単体テストがある（各ゲートに pass例/fail例のフィクスチャ）。

---

## フェーズ3：システム修正（generate-then-verify への反転）

### 目的
非計算形式の依存関係を反転し、フェーズ2の評価器を**生成時の verifier** として組み込む。moat（正しさ保証）は保つ。

### 3.1 形式ごとに生成戦略を分岐
| 形式 | 戦略 | 実装方針 |
|---|---|---|
| calculation / measurement / function | **記号ファースト（現状維持）** | SymPyが答えを保証。触らない |
| word_problem / proof / knowledge / visual | **LLMファースト → ゲート検証** | LLMがレッスン/形式/レベル/制約を条件に問題+答えを生成 → フェーズ2ゲート(G1,G2,G4,G5,G7)で受理/棄却。落ちたら再生成 |

**要点**: フェーズ2の `scripts/eval_gates/` を**実行時にも呼べるモジュール**として設計しておく（offline評価と runtime検証で同一コード）。

### 3.2 form/blueprint 契約の強制（静かなフォールバックの根絶）
- mapping が形式Xを要求するのに、割当Blueprintの `supported_forms` にXが無ければ**ロード時に検証エラー**にする。
  現状は静かに calculation へ落ちている。`registry.load_blueprint` か mapping 検証スクリプトに契約チェックを追加。
- これにより「knowledge を要求したのに足し算が出る」類が構造的に起きなくなる。

### 3.3 難易度モデルの再設計
- `docs/difficulty_level_design.md`（既存）の離散Lv制に沿い、**レベルを構造特徴（フェーズ2の 2.4）でレッスンごとに定義**。
- オペランドの乱数振りではなく、「ステップ数・無理数の有無・補助線の要否」等でLvを分離。

### 3.4 「症状ごとBlueprint追加」路線の停止
- フェーズ1で固定した17個以上に、**個別レッスン救済のためのBlueprintを安易に足さない**。
  新規追加は「新しい数学的構造クラスが必要なとき」のみ。form/difficulty の不足はBlueprint追加では直らない（診断§1.1）。

### タスク（フェーズ2完了後に詳細化。ここでは方向のみ）
1. 非計算形式の LLMファースト生成パス（generate-then-verify ループ）を1形式で試作（推奨: `knowledge`＝現状0%で伸びしろ最大）。
2. フェーズ2ゲートを runtime verifier として接続。棄却→再生成の上限リトライを設計。
3. form/blueprint 契約検証を mapping ロードに追加。
4. 難易度特徴ベースのLv定義へ移行。

### 完了条件
- `knowledge` 形式が、決定論ゲート G4(knowledge) を実運用で通過する問題を生成できる。
- form/blueprint 契約違反が mapping ロード時に検出される（テストあり）。
- pytest 全通過を維持。

---

## 実施順序と原則（再掲）
1. **フェーズ1**（整理）→ HEAD を自己完結・256テスト通過で固定。
2. **フェーズ2**（決定論評価器）→ LLM無しで実出力を測れる状態にする。**ここが最重要**。
3. **フェーズ3**（generate-then-verify 反転）→ フェーズ2の評価器を verifier に昇格。

原則:
- SymPyが計算した数値・答えは絶対に変更しない（moat）。
- 各タスク後に `pytest` 全通過を確認、コミットを論理単位で分割。
- 評価ループにLLMを入れない。生成は稀・評価は毎回の非対称を守る。
- 症状ごとのBlueprint追加で問題を握り潰さない。form/difficulty は構造で直す。
