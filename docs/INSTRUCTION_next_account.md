# 別アカウント Opus への指示文（そのまま貼り付け可）

このリポジトリ（mongene-v2 / /Users/koki/workspace/mongene-v2）で進行中の作業を引き継いでください。
別アカウントからの引き継ぎで、あなたにはメモリも会話履歴もありません。

## 最初に読む
1. `docs/HANDOFF_2026-07-06.md` 冒頭「★ 最新の現在地」の **🎯🎯 最新の到達点（§17.8-17.13）** を読む。
2. 続けて **§17 全体**（特に §17.0 評価の原則、§17.7 図形の残 scope、§17.8 Phase B 発見、§17.9-17.13 打開策1-5、§17.13 残作業と定点観測）。
3. 文脈補完に §2（システム構成）・§4（中核戦略）・§16（generate-then-verify）・§9（能力ギャップ）。
4. `git log --oneline -25` で直近コミットを確認。HANDOFF はこのプロジェクト唯一の引き継ぎ媒体。

## いまどこにいるか（要約）
- 正しさ(SymPy moat)＋契約違反0 は堅い。「質の監査ループ」を **Phase A（題材忠実性・LLMフリー）→ Phase B（翻訳後 product の自然さ・要LLM）** まで一巡した。
- **Phase B の最大発見＝moat は弱い**: 決定論ゲート（契約/SymPy/is_clean）は「答えが計算と一致」は保証するが「**問題として意味が通るか**」は保証しない（確率6/7・面積0・二等辺の頂角底角曖昧 が全ゲートを通過していた）。
- これを受け **打開策1-5 を系統実施**（§17.9-17.13）: ①確率の実標本空間化 ②退化検出ゲート ③MR意味的曖昧性解消 ④offline generate-then-verify＋接地ゲート精緻化 ⑤プロンプト自然さ（通貨は円/離散量に分数禁止）。
- **完成度 ~40% → ~65-68%**。pytest **461**・契約違反0・生成不能form0。HEAD=`9924678`（作業ツリーclean）。

## あなたのタスク＝残りを費用対効果順に潰す（ユーザー指定「費用対効果が高いものから」）
残る主レバーは §17.13 に列挙済み。**安い順**に:
1. **【最小・まず着手】g2_l46 平行四辺形 calc の配線**: `parallelogram_adjacent` theorem は実装済み（`find_angle_verb.py`）。g2_l41 二等辺と同じ手（per-level `blueprint_override`＝AngleCalculationStructure＋`required_tags` に `angles` を OR 追加＋他form の空制約 level に PolygonAtom を pin）で calc lv1（角度）を配線するだけ。雛形コミット＝g2_l41（`7c2517b` 系）と g3_l49（`bdba14b`）。**calc lv2-4 は辺の長さ/代数題材なので対象外・据置**。
2. **visual題材ズレ ~26レッスンの横展開**（§17.7）: 円周角 g3_l49 の再配線パターン（既存 AngleCalculationStructure・CircleAngleAtom）を他の円レッスンへ。合同/相似の proof レッスンの visual（今は measure_area＝面積を出す題材ズレ）は **ProofStructure が proof 専用**なので、visual 用に「2図形＋対応マーク」を出す `CongruenceFigureStructure` 相当の新 blueprint が要る（中規模）。移動系 g1_l38/39/40 は**孤児の `TransformShapeVerb`（translation/rotation/reflection/revolution・実装済だが未配線）**＋2D before/after renderer。
3. **図形capability**: 相似 `SimilarityStructure`（`ProportionAtom`＋`solve_proportion` 既存を内部に、幾何 framing＋2図形 visual）＝中3相似の本丸。g2_l25 の2点→式決定 verb。
4. **④-4 プロンプト/few-shot 底上げ**（要 LLM クォータで効果測定）。

各修正後、**Phase B 定点観測**（下記）で完成度が上がったか確認する。

## Phase B（品質監査ループ）の回し方＝この体制を維持せよ
- **評価原則（§17.0・ユーザー厳守）**: 数学的に検証できるものは決定論で（LLMを浪費しない）。**LLMでしか測れない意味的質（題材・自然さ）にはLLMを使う**が、**生成器と監査役は別モデルにして循環を避ける**。
- **生成器＝Haiku 4.5 のサブエージェント**（使用中の生成モデル `gemini-3-flash` と同格）、**監査役＝Opus（あなた・main）**。`GEMINI_API_KEY` は未設定なので Gemini は使えない＝Claude 経路で回す。
- **手順**:
  1. 代表サンプルを選ぶ（例: 全学年×全5form×large_unit を代表する10レッスン、mid レベル＝31セル）。
  2. GT 再生成: `SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/build_ground_truth_corpus.py`（LLMフリー）。
  3. 翻訳プロンプト書き出し: `.venv/bin/python scripts/build_product_corpus.py --engine claude --dump --lesson <L>`（`_staging/{key}.prompt.txt`＋`.mr.json`。APIキー不要）。
  4. **翻訳**: Haiku 4.5 サブエージェントに `_staging/{key}.prompt.txt` を読ませ、指示通りの JSON を `_responses/{key}.json` に書かせる（バッチ分割・model="haiku"）。
  5. 組み立て: `build_product_corpus.py --engine claude --ingest --lesson <L>`（答えは GT の SymPy 値で固定）。
  6. **検証**: `.venv/bin/python scripts/verify_products.py`（解答漏洩/数値接地の PASS率）＋**Opus(あなた)が題材忠実性・文章/図の自然さを監査**。
  7. 破綻カテゴリを構造パターンで束ねて修正 → 再測定。

## 厳守事項
- **moat 不変**: SymPy が計算した答え・数値・logic_steps は絶対に変えない。監査は「表示/題材/翻訳」を直すだけ。退化ゲート（打開策2）は「答えが正しくても問題が破綻」を弾く別軸。
- **決定論ゲートを過信しない（Phase B の教訓）**: 契約違反0でも「意味が破綻」した問題は通る。新しい題材/verb を足したら **必ず Phase B で実 product を見る**（MR だけ見て安心しない）。
- Python は必ず `.venv/bin/python`。runner 直呼びは `apps.api.main` 経由 import＋`BlueprintRunner(dedup, diversity, translator, atom_selector, blueprint_loader, scenario_bank)` 構築、`GenerationRequest(problem_form=, lesson_id=, target_level=, seed=)`。
- **回帰**: `SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/ -q`（現 **461** 通過を維持）。契約違反0（`scripts/validate_form_blueprint_contract.py`）・生成不能form0（`tests/integration/test_master_data.py::test_declared_forms_have_generatable_levels`）。
- `master_data/mapping.json` は非標準のインライン配列整形。`json.dump` で全体再整形しない（外科的テキスト編集で最小diff。同一 ebf ブロックが複数レッスンで重複するので行番号指定 or レッスン範囲限定の Python 編集が安全）。
- **図形 re-wire の必須テクニック（実証済・毎回要る）**:
  - **tag-coupling 税**: atom 選択は lesson-level `required_tags`（OR 支配）が決める。目的 atom（LineAngleAtom/CircleAngleAtom）を候補化するため required_tags に必要タグ（`angles`/`circle_angles`）を OR 追加し、**同レッスンの他 form の空制約 level に PolygonAtom を明示 pin** して proof 等を非破壊に保つ（`atom_selector.py` Step2/preferred_noun_types）。
  - **per-level `blueprint_override`**: 図形 calc は角度 level と代数 level（周/連立/根号）が混在→丸ごと再配線不可。level 個別に `blueprint_override` で対応 blueprint を差す。
- **作業分担**: 思考・設計・監査判断・レビューは Opus（あなた）、機械的実装／Phase B 翻訳は Haiku/Sonnet サブエージェントに委譲可。ただし完了報告は鵜呑みにせず `git log/status`・`git diff`・検証スクリプト再実行で実体確認。
- **サブタスク／マイルストーンごとに逐次コミット**（push はユーザーが明示依頼するまでしない）。コミットメッセージ末尾に必ず：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- **マイルストーンごとに `docs/HANDOFF_2026-07-06.md` を更新・コミット**（§17 に追記）。双方向引き継ぎの最優先規律。複数アカウントを行き来し、メモリ・履歴は非共有。
- 複数セッションが同一作業ツリーを触ると未コミット変更が失われうる。自分の work は早めにコミットして確定。

## 現在の git 状態
master・HEAD `9924678`・作業ツリークリーン・push なし。pytest **461**・契約違反0・生成不能form0。
`reports/`・`tests/fixtures/reference_corpus/` は gitignore 済（Phase B の中間生成物はローカル・再生成可能）。
