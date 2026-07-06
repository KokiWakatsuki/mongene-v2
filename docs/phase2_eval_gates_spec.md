# フェーズ2 実装仕様書：決定論的評価ハーネス（実装者：Sonnet 向け）

作成日: 2026-07-06
親計画: `docs/rework_plan_2026-07-06.md`（§フェーズ2）
立案: Opus

---

## 0. このフェーズのゴール（1行）
**LLMを一切使わず**、実際の生成問題を再現可能・無料・高速に採点する `run_gates.py` を作る。
このゲート群はフェーズ3で生成時の受理／棄却フィルタ（verifier）に昇格する（evaluator = verifier）。

## 1. 最重要の構造（LLMフリーの担保）
評価に必要なデータは2種類。**片方は完全にLLMフリー**である点を最大限に使う。

| データ | 取得元 | LLM要否 | 内容 |
|---|---|---|---|
| **ground truth（正解側）** | `/problems/inspect`（＝ runner を SKIP_LLM で回した生MR） | **不要** | 答え(`answer.sympy_form/text_form`)、必要入力数値(`logic_steps[].operands`, `sampled_atoms`)、`problem_form`、`selected_tags`、難易度特徴(logic_steps数・sympy_expr) |
| **product（製品側）** | `/problems/generate` の `content_problem_text` 等 | **必要（1回だけ）** | LLM翻訳後の問題文・解説・図URL |

→ **ground truth は全 lesson×form×level を即・無料で全生成できる**。product だけが実LLMを1度だけ要し、凍結する。
→ 一部ゲート（G6難易度単調性、G1/G2の正解側健全性）は **product無し＝ground truthだけで走る**。難易度モデルの検証はLLMゼロで今すぐ回せる。

## 2. 実装を2段に分ける（推奨順）

### 2a. ゲート実装 + 単体テスト（**LLM完全不要**・先行）
`scripts/eval_gates/` に G1〜G7 を1ファイル1ゲートで実装。各ゲートは純関数:
```python
def check(product: dict, ground_truth: dict) -> GateResult
# GateResult = {gate_id, verdict: "PASS"|"FAIL"|"WARN"|"N/A", reason: str}
```
各ゲートに `tests/eval_gates/test_gN.py` を付け、**合成した pass例/fail例のフィクスチャ**で検証（実LLM出力もコーパスも不要）。
これで大半のフェーズ2が LLM ゼロ・その場で完結する。

### 2b. 参照コーパス構築 + 全走査（product側だけ実LLMを1回）
- `scripts/build_ground_truth_corpus.py`: 全 lesson×form×level×seed を inspect 相当で生成し
  `tests/fixtures/reference_corpus/ground_truth/{lesson}_{form}_{level}.json` に保存（**LLMフリー・高速**）。
- `scripts/build_product_corpus.py`: 同キーで `/generate` を実LLMで走らせ `.../product/{...}.json` に保存（**実LLM・1回・凍結**）。
  - Geminiクォータ回避: LLMプロンプト（`_mr_to_yaml` + `PROBLEM_TRANSLATION_PROMPT`）をファイルへダンプし、Claude Code CLI が翻訳結果を書き戻すモードを用意してよい。手段は問わないが「稀に生成・凍結」を守る。
- `scripts/run_gates.py`: `ground_truth/` と `product/` をキーでペアリングし全ゲートを走査 → `reports/gate_report.md`（除外対象だがローカル確認用）+ 機械可読な `gate_results`（コミット可否は別途判断）。
  - **product が無いキーは ground-truth 単独ゲート（G6等）のみ走らせる**。差分運用（変更したlessonのみ product 再生成）を可能にする。

---

## 3. ゲート仕様（G1〜G7）

各ゲートの ground truth 参照は §1 のフィールド。数値の照合は **正規化**して行う（全角/半角、`−`/`-`、`1/2`と`\dfrac{1}{2}`、`\left(`等のLaTeX装飾を除去してから比較）。正規化ユーティリティは共通化する。

### G1 答え漏洩（answer_leakage）
- **正解値の集合** = 各 sub_question の「最終出力」= `logic_steps` 末尾の `sympy_expr`、および `answer.sympy_form/text_form`。
- content_problem_text（＋各 sub_question の prompt_text）に正解値が出現したら **FAIL**。
- **例外**: 正解値がたまたま入力オペランド(G2の必要数値)と一致する場合は誤検出になりうるので **WARN** に格下げ。
- 回帰確認: 旧 `reports/generated_problems.jsonl` の「答え: 24」を確実に FAIL にできること。

### G2 数値整合（number_consistency）
- **必要入力数値** = `logic_steps[].operands` の数値 ＋ `sampled_atoms` の寸法(dimensions_cm 等)。
- これらが content_problem_text に**過不足なく**出現するか。
  - 必要数値が欠落 → **FAIL**（LLMが数値を落とした/改変した）。
  - 入力にも正解にも無い「素性不明の数値」が問題文の数値スロットに出現 → **WARN**（図番号(1)(2)等は許容リストで除外）。

### G3 答え正当性（answer_correctness）
- スコープを明示: **`calculation` 形式のみ自動化**。content_problem_text から数式を抽出し SymPy で再解答、ground truth の答えと一致するか。
- 非計算形式は **N/A**（G1/G2/G4 で代替）。過剰な自然言語パースを試みない（誤判定を避ける）。

### G4 形式適合（form_conformance）
形式別ヒューリスティック。判定語彙は `master_data/eval_lexicons.yaml`（新規・編集可能）に外出しする。
- `knowledge`: 「次の計算をしなさい」や裸の `式＝数値` を**含んだら FAIL**。定義/性質/正誤/用語/穴埋め等のマーカーを**含むべき**（無ければ FAIL）。
- `proof`: 「証明」＋構造マーカー（仮定/結論/∴/合同/相似/∠/△）を含むべき。裸の計算式のみ → FAIL。
- `word_problem`: 場面設定語彙（工場/公園/店/速さ/人数/代金… ＝ lexicon）を含むべき。裸の式のみ → FAIL。
- `visual`: `visuals.problem_diagram_url` が非null（≠NullRenderer由来の空）**かつ** 本文が「図/グラフ/右の図/下の図」を参照。
- `calculation`: 式を含み、物語語彙を含まない。

### G5 範囲逸脱（syllabus_range）
- content_problem_text＋explanation が `master_data/forbidden_words.txt`（既存・353語）に該当したら FAIL。
- さらに `master_data/prerequisite_graph.yaml` を使い、当該 lesson の前提に**含まれない未習単元の固有語彙**が出たら FAIL（初期は用語ブロックリストで簡易実装、拡張余地として明記）。

### G6 難易度レベル健全性（difficulty_level_soundness）※ product不要・LLMゼロで走る
> **【重要・2026-07-06 改訂】** 旧版は min/mid/max の連続 target_difficulty を合成スコアで単調性検査していたが、これは**測定軸の誤り**。
> 現行は離散Lv制（`mapping.json.difficulty_levels[form]` に Lv1..LvN を定義、`target_level` で生成。184/184定義済み）。
> min/mid/max は生成に存在しない（設計書 difficulty_level_design.md §6）。また多くの単元の難易度は「正の数同士<同符号<異符号」のように
> **問題の"型"**で定義され、合成スコア（数の大小/step数）では順位化できない。→ 合成スコア単調性は廃止。

正しいLLMフリー判定は **target_level 軸**で以下2つ:
- **G6-a 制約適合（conformance）**: 各 (lesson, form, Lv) を `target_level=Lv` で /inspect 生成し、その問題が当該Lvの
  `atom_constraints`（＋ベース設定へのマージ後）を満たすか。例: Lv1 が `allow_negative=false` なら負のオペランドが出ない、
  `max_value` 超過が無い、`max_terms` 準拠。**違反＝FAIL**（＝レベル定義がランナーに効いていない実バグ）。
- **G6-b レベル非崩壊（distinctness）】※2026-07-06 生成ベースに再設計（`scripts/eval_gates/g6_difficulty_level_soundness.py`）:
  - 旧版は `atom_constraints + blueprint_override + verb_config` の**静的シグネチャ**のみで判定しており、
    knowledge（difficulty は `blueprint_params.knowledge_hint` で表現）や construction/visual
    （`construction_type` 等で表現）が静的シグネチャに現れないフィールドでしか区別されないため
    **偽陽性で崩壊判定されていた**（385中41件 FAIL のうち相当数が偽陽性）。
  - 新版は次の手順で判定する:
    1. 効率のため「静的シグネチャが同一の Lv ペア」を崩壊候補としてプレフィルタする（旧ロジック流用）。
    2. 候補ペアについてのみ、各 Lv を `target_level=Lv` で **M回（デフォルト6）** `/inspect` 生成し
       （LLMフリー・`SKIP_LLM_IN_TESTS=true`）、各サンプルから**生成内容フィンガープリント**
       （`build_generation_fingerprint`）を作る。フィンガープリントは
       `(answer.type, operation_name, operand個数, 非数値operand, narration_hint文字列)` から構成する。
       **数値オペランドの具体値・符号は意図的に除外**する（同一 Lv 内でも seed 乱数で変わり、
       M回のサンプリングでは分布全体を観測しきれず「たまたま重ならない」だけで区別できたと
       誤判定する偽PASSの原因になるため。allow_negative/max_value 等の数値制約の適否は G6-a の管轄）。
    3. 候補ペアの Lv 間でフィンガープリント**集合**が完全一致（M回生成しても一度も区別できない）
       なら FAIL（真の崩壊）。集合が異なれば（knowledge_hint 文言差・construction_type 差等）
       静的シグネチャが同一でも PASS。
    4. 静的シグネチャが最初から異なる Lv ペアは生成せず PASS（プレフィルタで除外・高速化）。
    5. 候補ペアのいずれかの Lv が1件も生成できない（NoCompatibleBlueprintError 等）場合は
       判定不能として除外する（偽FAILを出さない・精度優先）。
  - `sample_fn` 未指定時は後方互換のため旧・静的シグネチャのみのフォールバック判定になる
    （単体テストの一部・生成器を用意できない環境向け）。
- **意味的順序（Lv4が本当にLv1より難しいか）は決定論では判定不能**。LLM/人手のマイルストーン・スポットチェックに回す（設計書§12 Phase5）。日常ループには入れない。
- `difficulty_features.py`（step_count等）は G6 の主判定には使わないが、参考表示に流用可。フェーズ3の難易度設計とも共有。

### G7 レンダリング健全性（render_sanity）
- content_problem_text＋explanation の LaTeX: `$...$` が均衡し、`$$` `\[` `\]`（ブロック数式）を**使っていない**こと。使用で FAIL。
- 各 `$...$` の中括弧均衡＋既知コマンド範囲チェック（フルKaTeX検証はNode依存のため任意。最低限の構文チェックを必須とする）。
- `visual` 形式: 図URL/SVG が非空かつ整形式XML（`xml.etree` でパース可能）であること。

---

## 4. スコア集計
- レッスン×形式×レベルごとに G1〜G7 の verdict ベクトルを出す。
- 主指標 = **全ハードゲート（FAIL対象）通過率**。WARN/N/A は別集計。
- `reports/gate_report.md` に「形式別・ゲート別の通過率マトリクス」を出力。これがLLM評価 A/B/E を置換する再現可能指標。

## 5. 完了条件
- `scripts/eval_gates/` に G1〜G7、各に単体テスト（合成フィクスチャ、LLM不要）。pytest 全通過（既存256＋新規）。
- `run_gates.py` が凍結コーパスに対し **LLMを一切呼ばず** 通過率レポートを出す。
- G6（難易度単調性）が ground-truth コーパス単独で走り、現状の「min/mid/maxで難易度が分離しない」箇所を検出できる。
- G1 が旧 generated_problems.jsonl の答え漏洩を検出できる（回帰）。

## 6. 原則・落とし穴
- **評価ループにLLMを入れない**。ground truth とゲートは常にLLMフリー。product は稀に生成・凍結。
- ゲートは純関数＋データ外出し（lexicon/forbidden語）で**拡張しやすく**。ハードコードで個別レッスンを握り潰さない。
- G3/G5 は完全自動化が難しい領域。**スコープを狭く・誤判定を出さない**方を優先（高精度・中再現率）。取りこぼしはG1/G2/G4で補う。
- 「自然さ（市販レベル）」はゲートで証明しきれない。マイルストーンごとの人手/LLMスポットチェックは**ループ外**で別途（毎回は回さない）。
- SymPyの答えは不変（moat）。ゲートは答えを検査するが変更しない。
