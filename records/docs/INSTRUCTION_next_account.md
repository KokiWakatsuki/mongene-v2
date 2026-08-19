# 別アカウント Opus への指示文（そのまま貼り付け可）

> **★2026-08-19 追記: この文書は 2026-07-07 時点のもので、局面が変わっている。**
> いま進行中の作業（式と場面の切り離し）を引き継ぐなら、まず
> **`records/docs/HANDOFF_scene_split_2026-08-19.md`** を読むこと。
> 基準は `records/docs/scene_formulation_charter_2026-08-19.md`、
> 進捗は `records/work/logs/PROGRESS.md`。
> 以下は当時の記録として残してある（アーキテクチャの背景には今も使える）。

このリポジトリ（mongene-v2 / /Users/koki/workspace/mongene-v2）で進行中の作業を引き継いでください。
別アカウントからの引き継ぎで、あなたにはメモリも会話履歴もありません。

## 最初に読む
1. `docs/HANDOFF_2026-07-06.md` 冒頭「★ 最新の現在地」の **🎯🎯🎯🎯🎯🎯🎯 最新の到達点（§17.18）** を読む。
2. 続けて **§17.14-17.18**（capability 開通・図の自然さ修正・本番Gemini再測定・次タスク）。文脈補完に §17.0（評価原則）・§17.7（図形残scope）・§2（システム構成）・§4（中核戦略）。
3. `git log --oneline -30` で直近を確認。HANDOFF はこのプロジェクト唯一の引き継ぎ媒体。

## いまどこにいるか（要約・2026-07-07 時点）
- 正しさ(SymPy moat)＋契約違反0 は堅い。「質の監査ループ」を Phase A（題材・LLMフリー）→ Phase B（翻訳後の自然さ・要LLM）で回し、**capability を多数開通＋図の自然さを実目視で修正**した。
- **本番 Gemini で完成度を再測定＝~72-75%**（代表14セル×Opus監査）。軸別: SymPy正しさ~95%✅／問題として意味が通る~88-90%✅／**図の自然さ~85%✅**／**題材忠実性~78-80%⚠️／文章の自然さ~75%⚠️**。
- ユーザー目標＝**他科目展開以外の全軸で85%（理想90%）**。未達は題材忠実性・文章の自然さの2軸。
- pytest **465**・契約違反0・生成不能form0。HEAD は `git log` で確認（作業ツリー clean）。**GEMINI_API_KEY は `.env` にあり利用可（無料枠）**。

### このセッションで完了した主な作業（履歴・§17.14-17.18）
- capability: g2_l46平行四辺形calc・**CongruenceFigureStructure**（合同/相似9レッスンの visual を2図形＋対応マークへ）・**SimilarityStructure**（相似/線分比/中点連結5レッスンの calc を実算出へ＝ARITH_FOREIGN 36→19）。
- C1: 翻訳プロンプトに**忠実性ブロック（捏造禁止）**＋新blueprint few-shot（本番Geminiで確率捏造の再発なしを確認）。
- **図の自然さ 5欠陥を修正（表示のみ・answer不変）**: 円周角ラベル衝突／確率tree重なり＋枝確率／おうぎ形が素の円／3D頂点ラベル＋隠れ辺破線／**グラフの縦横等スケール化**（`set_aspect("equal")`）。

## 🎯 あなたのタスク＝FunctionGeometryFusion の題材ズレ解消（ユーザー選択・完成度の最大レバー）
再測定で判明した**全体の天井＝残る2軸（題材忠実性・文章自然さ）**、その最大ドラッグがこれ。詳細は **§17.18**。
- **診断**: `FunctionGeometryFusionStructure` は form によらず**「2直線の交点＋座標軸との三角形の面積」を生成**するが、この題材が正しいのは **exam_l1（一次関数と図形の融合）だけ**。他10レッスン（g2_l19/20/21/22/23/24/26/27/28/30）は題材ズレ。例: g2_l21「傾きと切片」なのに交点+面積、g2_l28「1次関数の利用（ばね/水そう）」wp が交点+三角形面積。
- **正題材（レッスン別・要出し分け）**: 意味と式(評価)・変化の割合(Δy/Δx)・傾きと切片(読み取り)・式決定(傾き+1点)・ax+by=cのグラフ・グラフの書き方(単一直線)・変域(線分＋端点)・連立=2直線交点(面積は蛇足)・利用/速さ(実世界の線形場面)。
- **方針の候補（設計はあなたが判断）**: (a) FunctionGeometryFusion に `mode`/`context` パラメータを足し lesson 別に題材を出し分け、(b) 交点+面積は exam_l1・g2_l27 に限定、(c) g2_l28/l30 の wp は scenario_bank 連携で速さ/ばね等の場面を持たせ三角形面積の蛇足を外す。
- **既存 backlog `task_643ed872`（g2_l30 調査）と同根＝統合**。**別セッションで進行中の可能性あり**＝着手前に必ず `git log --oneline`/`git status` で成果を確認（重複作業回避）。
- 図は §17.17 で等スケール化済み＝**題材が直れば図も正題材に乗る**。

## 品質監査ループ／再測定の回し方（この体制を維持せよ）
- **評価原則（§17.0・ユーザー厳守）**: 数学的に検証できるものは決定論で。**意味的質（題材・自然さ）にはLLMを使う**が、**生成器と監査役は別モデルにして循環を避ける**（生成=Gemini/Haiku、監査=Opus=あなた）。
- **本番測定（Gemini・推奨）**: `scratchpad/gen_real.py` パターン＝`import apps.api.main`(.env ロード)→`SKIP_LLM_IN_TESTS` を立てず real `LLMTranslator` で `runner.run`→problem_text/explanation を実生成し Opus 監査。
  **⚠️ 無料枠のレート制限が測定を汚染する**（連続生成で途中から全tier失敗→テンプレフォールバック＝空解説＋素の質問文）。**セル間に ~12秒 sleep 必須**。フォールバックは品質失敗でなくレート制限の産物（間隔を空けて再試行すると高品質で成功）。
- **図の目視**: runner が SVG を `master_data/cache/diagrams/{seed}.svg` に保存。`cairosvg`/`rsvg-convert` で PNG 化して Read で見る（inspect レスポンスは SVG を落とす。visual_dsl は `mr.visual_dsl.elements`）。
- Haiku サブエージェント経路（offline）も可: `build_product_corpus.py --engine claude --dump`→Haikuが翻訳→`--ingest`→`verify_products.py`＋Opus監査。

## 厳守事項
- **moat 不変**: SymPy が計算した答え・数値・logic_steps は絶対に変えない。監査は「表示/題材/翻訳」を直すだけ。
- **回帰**: `SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/ -q`（現 **465** 維持）・契約違反0（`scripts/validate_form_blueprint_contract.py`）・生成不能form0（`test_declared_forms_have_generatable_levels`）。Python は必ず `.venv/bin/python`。
- **`master_data/mapping.json` は非標準のインライン配列整形**。`json.dump` で全体再整形しない（**レッスン範囲限定の Python 外科編集**＝該当 form 配列だけ json.loads→変換→6空白 indent で再emit・angle_range 等インライン配列は非破壊）。手本＝§17.14/17.15 の visual/calc 一括再配線スクリプト。
- **図形 re-wire の税**: atom 選択は lesson-level `required_tags`（OR支配）＋他form の空制約levelに目的atomを pin。per-level `blueprint_override`。slot の `constraints_override` は `atom_selector._build_atom_constraints` で**無視される**（polygon_type等はレッスン atom_constraints でしか制御不可）。
- runner 直呼び検証は `import apps.api.main` を先に（atom/verb registry 登録。さもないと `NoCompatibleAtomError`）。/inspect(TestClient) 経由が最も確実。
- **作業分担**: 設計・監査・レビューは Opus（あなた）、機械実装／翻訳は Haiku/Sonnet サブエージェント委譲可。ただし完了報告は鵜呑みにせず `git log/status`・`git diff`・検証再実行で実体確認。
- **サブタスク／マイルストーンごとに逐次コミット**（push はユーザー明示依頼まで禁止）。コミット末尾に必ず：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
- **マイルストーンごとに `docs/HANDOFF_2026-07-06.md` を更新・コミット**（§17 に追記）。双方向引き継ぎの最優先規律。複数アカウントを行き来しメモリ・履歴は非共有。

## その他の残タスク（§17.14-17.18・費用対効果順）
- 合同の対応部分calc（g2_l36/37）・関数式決定verb（g2_l25）・移動系renderer（g1_l38/39/40 の孤児 TransformShapeVerb＋before/after描画）・単一図形マークvisual（二等辺/平行四辺形等）・few-shot拡充（高トラフィックblueprint・要LLMクォータ）・**g1_l25 word_problem の恒常フォールバック調査**（場面なしの裸方程式＝WordProblem検証棄却の疑い）。

## 現在の git 状態
master・作業ツリークリーン・push なし。pytest **465**・契約違反0・生成不能form0。`reports/`・`tests/fixtures/reference_corpus/`・`master_data/cache/` は gitignore 済（中間生成物・再生成可能）。HEAD は `git log --oneline -1` で確認。
