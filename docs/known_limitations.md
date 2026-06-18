# 既知の制限事項一覧（Phase 1〜6 + 追加実装後）

更新日: 2026-06-17（Phase 6 後追加実装含む）

---

## カテゴリ A. 設計書 §20 で MVP 外と宣言済み（実装不要）

- IRT/BKT による生徒個別最適化
- Datadog/Grafana 等の本格的監視
- ベクトル DB による動的 Few-Shot 検索
- 連続出題の多様性メトリック
- マルチテナント
- Atom バージョン管理（v2 継承）
- LLM-as-Judge

## カテゴリ B. 実 LLM 接続（解消済）

| 項目 | 状態 |
|:---|:---|
| Gemini API 実呼び出し | ✅ `gemini-flash-lite-latest` で 3 tier 動作確認済 |
| API キー形式 | ✅ AQ. キー対応 |
| google-genai 移行 | ✅ 2.8.0 移行済、deprecation 警告解消 |
| `thinking_budget` | ✅ §8.4 通り tier 別に設定 |
| モデル名 | ✅ `gemini-flash-lite-latest` 統一（無料枠で動作） |

**Free Tier の罠**:
- `gemini-2.5-flash` 等は `generate_content_free_tier_requests` メトリックで 20 RPD に制限
- `gemini-flash-lite-latest` は 1000 RPD / 15 RPM で安定動作
- 設計書 §8.4 の無料完結方針は維持される

## カテゴリ C. Phase 4 マスターデータ（LLM 版スクリプト整備済、再生成は任意）

| 項目 | 現状 | LLM 版 |
|:---|:---|:---|
| `mapping.json` 177 件 | 決定論版で 100% 動作 | `scripts/generate_master_data_llm.py --what mapping` で再生成可能（177 リクエスト ≒ 12 分）|
| `prerequisite_graph.yaml` | 決定論版 DAG 254 edges | `... --what prereq` |
| `scenarios.yaml` | 手書き 15 件 | `... --what scenarios` |
| `forbidden_words.txt` | ✅ LLM 生成 353 語 | 完了済 |
| `few_shot_seeds` | 手書き 3 ファイル | `... --what few_shot` |

## カテゴリ D. Phase 5 暫定フラグ（mapping 生成モード切替で対応）

| 項目 | 戻し方 |
|:---|:---|
| `dedup_disabled` / `is_clean_override.disabled` | `python scripts/generate_mapping.py --strict` で strict モード（lesson 別 is_clean + dedup 有効）に再生成 |
| Accuracy = Solvability 評価 | `scripts/run_full_coverage.py` で `verify_accuracy()` 呼び出しは既に実装済、実 LLM モードで自然に有効化 |

## カテゴリ E. Phase 5 残り 823 問サンプリング

| 項目 | 状態 |
|:---|:---|
| 必須カバレッジ 177 問 | ✅ 全 4 軸 100% |
| 形式バリエーション 300 問 | 未実施（scripts/run_full_coverage.py を拡張すれば可能） |
| 難易度バリエーション 300 問 | 未実施 |
| 入試レベル 200 問 | 未実施 |
| エッジケース 23 問 | 未実施 |

実 LLM で続けるなら `gemini-flash-lite-latest` の 1000 RPD で 1 日に処理可能。

## カテゴリ F〜J. 機能拡張・細部（解消済）

### F. Verb 細部
- ✅ ProveAlgebraicVerb / ProveGeometryVerb の `ProofOutput` 配線完了
- ✅ SubQuestionBuilder で proof 型 AnswerObject 出力
- 残: LocusVerb の condition_type 拡張、ConstructGeometryVerb の SymPy 作図計算

### G. Blueprint 複数 Verb 連結
- ✅ BasicDifferenceStructure に MeasureGeometryVerb(volume) 連結（§18.4 通り 3 Verb 構成）
- 他 Blueprint の追加 Verb は本格運用時に必要に応じて

### H. subquestion_strategy
- ✅ `single` / `incremental` / `guided` / `ladder` 全 4 戦略実装

### I. VisualBuilder
- ✅ `apps/api/src/visuals/builder.py` 実装、`BlueprintRunner._build_visual_dsl` 配線済
- Blueprint × 5 種 Visual で 11 関数

### J. API / CI / 非同期
- ✅ Pydantic / FastAPI / HTML UI / CI yaml
- ✅ §42 PrefetchCache 実装、`/problems/generate` で `BackgroundTasks` 経由で 2 問先読み

## カテゴリ K. 細部実装漏れ（解消済）

| 項目 | 状態 |
|:---|:---|
| 重複ハッシュの粒度分岐 | ✅ `problem_form == "proof"` のとき `operation_name` 列で hash |
| lesson 別 `is_clean_override` 細粒度 | ✅ `infer_clean_config()` で title から推論 |
| Atom メタ YAML | ✅ `scripts/generate_meta_yaml.py` で atoms/verbs/blueprints/visual_components の 4 ファイル生成 |
| git ハッシュ保存 | ✅ `git init` 完了、`MetadataSchema.git_commit` 配線 |
| ScenarioBank クラス | ✅ §25.2 実装、BlueprintRunner / LLMTranslator 配線済 |

---

## 残課題のサマリ

**実質的に残っているのは「やる気になればいつでもできる量的作業」のみ**:

1. Phase 5 残り 823 問の実行（時間問題のみ）
2. LocusVerb / ConstructGeometryVerb の細部肉付け（30〜60 分の作業）
3. 図形 SVG の視覚的検証（ブラウザでイテレーション）

これら以外の設計書記載項目は実装済または MVP 外として除外済。

## 復帰手順（実 LLM 本番モードへの切替）

```bash
# 1. 全 mapping を strict モードで再生成
PYTHONPATH=. python scripts/generate_mapping.py --strict
PYTHONPATH=. python scripts/generate_prerequisites.py

# 2. 必要に応じてマスターデータを LLM で再生成
PYTHONPATH=. SKIP_LLM_IN_TESTS=false python scripts/generate_master_data_llm.py --what all

# 3. 実 LLM で品質ゲート再確認
PYTHONPATH=. SKIP_LLM_IN_TESTS=false python scripts/run_full_coverage.py
```
