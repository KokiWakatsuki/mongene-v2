# 別アカウント Opus への指示文（そのまま貼り付け可）

このリポジトリ（mongene-v2 / /Users/koki/workspace/mongene-v2）で進行中の作業を引き継いでください。
別アカウントからの引き継ぎで、あなたにはメモリも会話履歴もありません。

## 最初に読む
1. `docs/HANDOFF_2026-07-06.md` の冒頭「★ 最新の現在地」→ **🚩 次の主戦略（§17）** を必ず読む。
2. 続けて **§17 全体**（質の監査ループ＝真因・2フェーズ・Phase A 手順・既存インフラ）。
3. 文脈補完に §2（システム構成）・§4（中核戦略）・§16（generate-then-verify）・§9（能力ギャップ）。
4. `git log --oneline -20` で直近コミットを確認。HANDOFF はこのプロジェクト唯一の引き継ぎ媒体。

## あなたのタスク＝質の監査ループ Phase A（題材忠実性・LLMフリー・今すぐ着手可）
ゴール完成度評価で、正しさ(SymPy moat)は堅いが**意味的な質（題材忠実性・自然さ・難易度）が停滞**と判明。
これは決定論ゲートでは測れないため、**Opus(あなた)を監査役とする generate→audit→fix→再生成ループ**を回す。
**Phase A は /inspect（LLMフリー）で全1516セルの MR をダンプし、あなたが題材一致を判定→構造パターンで
一括修正する。クォータ0で最大の穴（題材ズレ）を潰す。**

### 手順（§17.4 準拠・全体評価→個別評価の使い分け）
1. **全MRダンプ生成**: `scripts/dump_mr_corpus.py`（新規・`build_ground_truth_corpus.py`/`corpus_seed.py` 流用）で
   全 lesson×form×lv を pinned seed で /inspect し `reports/mr_dump/mr_corpus.jsonl` に保存
   （{lesson,title,large_unit,form,lv,blueprint_id,sampled_atoms(型),operation_names,answers,prompt_hints,visual要約}）。
   LLMフリー・数分。`reports/` は gitignore 済（ローカル生成物）。
2. **【全体評価＝安く広く】決定論の構造スキャン（LLMフリー）**: ダンプ全1516行を機械ルールで題材ズレ候補を
   自動フラグ（空/重複 difficulty_levels、operation と単元の不整合＝関数なのに arithmetic、面積比なのに単一
   measure_area、evaluate期待だが intersect、blueprint と title 不整合、退化答え）。**Opus が深く見るべきセルを絞る**。
3. **【個別評価＝絞って深く】チャンク監査（再開可能）**: フラグセル＋各 large_unit のサンプルを **あなた(Opus)が
   意味判断**し、各セルを `OK|MISMATCH|WEAK`＋issue＋suggested_fix で `reports/quality_audit.jsonl` に追記
   （済みはスキップ）。ここで初めて LLM 予算を使う＝「LLMでしか判定できない意味的一致」に集中
   （例「反比例レッスンなのに MR が arithmetic 加算＝MISMATCH」）。
4. **構造パターンで束ねて一括修正**: 同型の題材ズレをまとめ blueprint 再配線 / verb 追加 / atom 制約で直す。
   **雛形＝コミット `4c0a347`（反比例 calc を BasicCalc→CoordinatePlaneStructure に再配線）**。
5. **再ダンプ→再監査**で MISMATCH を 0 に寄せる。

## 厳守事項
- **moat 不変**: SymPy が計算した答え・数値・logic_steps は絶対に変えない。監査は「表示/題材」を直すだけ。
- **評価の原則（ユーザー・§17.0）**: 数学的に検証できるものは決定論で（LLMを浪費しない）、**LLMでしか評価できない
  意味的質（題材・自然さ・意味的難易度）にはLLMを使う**。監査役 Opus は生成器(SymPy/Gemini)と別モデルなので
  循環しない。**LLMは有限なので全体評価（広く安く候補特定）と個別評価（絞って深く判定）を使い分ける**。
  決定論ゲート（G1-G7）と ground truth は引き続き LLMフリー。
- Python は必ず `.venv/bin/python`。runner 直呼びは `apps.api.main` 経由 import
  ＋`BlueprintRunner(dedup, diversity, translator, atom_selector, blueprint_loader, scenario_bank)` 構築、
  `GenerationRequest(problem_form=, lesson_id=, target_level=, seed=)`。
- 回帰: `SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/ -q`（現 448 通過を維持）。
  契約違反0維持（`SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/validate_form_blueprint_contract.py`）・生成不能form0
  （`tests/integration/test_master_data.py::test_declared_forms_have_generatable_levels`）。
- `master_data/mapping.json` は非標準のインライン配列整形。`json.dump` で全体再整形しない（外科的テキスト編集で最小diff）。
- **作業分担**: 思考・設計・監査判断・レビューは Opus（あなた）、機械的実装は必要なら Sonnet サブエージェントに委譲可。
  ただしサブエージェントの完了報告は鵜呑みにせず `git log/status`・`git diff`・検証スクリプト再実行で実体確認。
- **サブタスク／マイルストーンごとに逐次コミット**（push はユーザーが明示依頼するまでしない）。
  コミットメッセージ末尾に必ず：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- **マイルストーンごとに `docs/HANDOFF_2026-07-06.md` を更新・コミット**（§17 の進捗・監査結果サマリ・
  一括修正した題材ズレのパターンを追記）。双方向引き継ぎの最優先規律。複数アカウントを行き来し、メモリ・履歴は非共有。
- 複数セッションが同一作業ツリーを触ると未コミット変更が失われうる。自分の work は早めにコミットして確定。

## 現在の git 状態
master・HEAD は最新の HANDOFF 更新コミット・作業ツリークリーン・push なし。
pytest 448 通過・契約違反0・生成不能form0。

## Phase B（後続・要 LLM クォータ）
Phase A を通ったセルの product（翻訳済み問題文）を Gemini or Claude で生成（`scripts/build_product_corpus.py`）→
文章・図の自然さを Opus が監査→プロンプト/few-shot/図を修正。クォータが用意でき次第。
