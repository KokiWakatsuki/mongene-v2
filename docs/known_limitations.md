# 既知の制限事項一覧（Phase 1〜5 実装時点）

本ドキュメントは `docs/implementation_plan.md` の設計と、Phase 1〜5 の実装の差分を一元的に記録する。
各項目は「設計書のどこに対応するか」「現状の代替実装」「本格運用時の戻し方」を明示する。

更新日: 2026-06-17

---

## カテゴリ A. 設計書 §20 で MVP 外と宣言済み（実装不要）

| 項目 | 設計書参照 |
|:---|:---|
| IRT/BKT による生徒個別最適化 | §20.1 |
| Datadog/Grafana 等の本格的監視 | §20.2 |
| ベクトル DB による動的 Few-Shot 検索 | §20.3 |
| 連続出題の多様性メトリック（N-gram Jaccard 等） | §20.4 |
| マルチテナント（学校・塾ごとカスタム mapping） | §20.5 |
| Atom バージョン管理（v2 継承） | §20.6 |
| LLM-as-Judge | §14.3 で棄却 |

これらは設計時点で除外宣言済み。**実装していなくて正しい**。

---

## カテゴリ B. 実 LLM 接続関連（環境制約）

| 項目 | 設計書参照 | 現状 | 戻し方 |
|:---|:---|:---|:---|
| Gemini API 実呼び出し | §29, §40 | `call_gemini()` で 3 tier 全て疎通確認済（2026-06-17、AQ. キー使用） | テスト時は `SKIP_LLM_IN_TESTS=true` モック維持。実生成時は false |
| Gemini モデル名 | §8.4 | 設計書の `gemini-3-flash` / `gemini-3.1-flash-lite` は実在しない。`gemini-2.5-flash` / `gemini-flash-lite-latest` に差し替え済 | Gemini 3 系リリース後に `.env` 更新 |
| API キー形式 | §8.4 | AQ. 形式（Auth key）に変更済。旧 `AIza` Standard key は 2026-06-19 から制限開始、2026-09 完全廃止 | 移行完了済 |
| Free Tier モデル制約 | — | AQ. キーで `gemini-flash-latest` / `gemini-2.0-flash` 系は 429 quota。`gemini-2.5-flash` と `gemini-flash-lite-latest` のみ動作 | Paid プラン契約で全モデル開放 |
| `thinking_budget` パラメータ | §40 | `GenerationConfig` に渡していない（古い SDK での AttributeError 防止） | `google-genai` 移行後に対応 |
| `google-generativeai` パッケージ | §40 | deprecated 警告。動作はする | `google-genai` への移行 |
| 多段モデルフォールバック | §29.4, §12.3 | コードは実装済み・3 tier 単体動作確認済。連続失敗時のエスカレーションパスは未実証 | 実運用で観測 |
| §35.4 テンプレ展開フォールバック | §35.4 | 実装済み・決定論モードでは到達しない | LLM 障害発生時に自然発火 |

---

## カテゴリ C. Phase 4 マスターデータ（LLM 生成 → 決定論代用）

| 項目 | 設計書参照 | 現状 | 戻し方 |
|:---|:---|:---|:---|
| `mapping.json` 177 件 | §21.1 | キーワード regex + §24 y_base ルールで決定論生成 | `scripts/generate_mapping.py` を §21.1 LLM プロンプト呼び出しに差し替え |
| `prerequisite_graph.yaml` | §21.2 | キーワード推論で DAG 構築 | §21.2 LLM プロンプトで再生成 |
| `scenarios.yaml` 15 件 | §25.4 | 手書きテンプレ | §25.4 プロンプトで 15 個再生成 |
| `few_shot_seeds/*.yaml` | §21.3 | 手書き 3 ファイル（合計 5 例） | §21.3 で 50〜100 件まで拡張 |
| `forbidden_words.txt` | §21.4 | 手書き 20 語程度 | §21.4 で 200〜500 語に拡張 |
| SequencePatternStructure 振り分け | §17.4 #11 | キーワード推論精度の問題で 0 件（規則性 lesson が他 Blueprint に流れる） | キーワード優先順位の見直しまたは LLM 再生成 |

---

## カテゴリ D. Phase 5 で導入した暫定フラグ

実 LLM が無い決定論モードで品質ゲート 100% を達成するための一時設定。

| 項目 | 場所 | 理由 | 戻し方 |
|:---|:---|:---|:---|
| `dedup_disabled: True` | 全 mapping エントリ | LLM モック応答が一意のため、同一 hash が重複と判定され生成が阻害 | 実 LLM 接続後に削除 |
| `is_clean_override: {disabled: True}` | 全 mapping エントリ | モック応答 + 一部 Atom の sympy_expr で `is_clean()` が常に False に近く、リトライ枯渇 | 実 LLM 接続後に `max_denominator_digits: 3, max_radicand: 1000` 等に再設定（§12.3） |
| Accuracy = Solvability で評価 | `scripts/run_full_coverage.py` | モック応答からの数式逆抽出が無意味 | §12.5 通り `extracted_text → regex 抽出 → sympy.simplify(extracted - answer) == 0` を有効化 |

---

## カテゴリ E. Phase 5 品質ゲート 1000 問のうち未実施 823 問

§35.1 サンプリング基準のうち、実施したのは「必須カバレッジ 177 問」のみ。

| 項目 | 必要数 | 状態 |
|:---|---:|:---|
| 必須カバレッジ（全 lesson × デフォルト form × 中央難易度） | 177 | ✅ 実施・全 4 軸 100% |
| 形式バリエーション（全 lesson × 全 supported_forms × 中央難易度） | 300 | ❌ 未実施 |
| 難易度バリエーション（主要 30 lesson × 1 form × 難易度 1/30/60/90） | 300 | ❌ 未実施 |
| 入試レベル（難易度 80〜100 で複合単元 lesson 組合せ） | 200 | ❌ 未実施 |
| エッジケース（unlearned_tags で連鎖排除発動パターン） | 23 | ❌ 未実施 |

---

## カテゴリ F. Atom / Verb の機能省略

| 項目 | 設計書参照 | 現状 |
|:---|:---|:---|
| LocusVerb の条件タイプ | §18.2 | `equidistant` のみ。`点と直線等距離`等は未実装 |
| ConstructGeometryVerb | §18.2 | 手順を `List[Dict]` で返すが、各手順の SymPy 計算は未実装（ラベルのみ） |
| ProveAlgebraicVerb / ProveGeometryVerb | §26 | `ProofOutput` 構造を設計通りに組むが、`AnswerObject.extras["proof_output"]` への配線は未完成 |
| AnalyzeDataVerb の histogram/boxplot メトリック | §18.2 | 数値メトリック (`mean/median/mode/q1/q3/iqr`) のみ。VisualDSL 出力なし |
| CalculateProbabilityVerb の condition 解析 | §18.2 | 簡易（`favorable` 引数または `event_descriptors` の長さ）。自然文 condition 解析は未実装 |
| EstimatePopulationVerb の警告ログ | §18.2 | `sample_size >= 30` 推奨だがログ出力なし |

---

## カテゴリ G. Blueprint の簡略化

| 項目 | 設計書参照 | 現状 |
|:---|:---|:---|
| 各 Blueprint の `verb_invocations` 数 | §18.4 | **1 つだけ**の最小実装。複数 Verb を連結する DAG は未実装 |
| BasicDifferenceStructure | §18.4 | `CutoutVerb` のみ。設計では `MeasureGeometryVerb(measure_type="volume")` も含む |
| `subquestion_strategy.guided` / `ladder` | §27.1 | 未実装。`single` / `incremental` のみ |
| ProofStructure の `AnswerObject.type="proof"` 出力 | §26 | LogicStep には記録するが、AnswerObject への配線は未完成 |

---

## カテゴリ H. 描画・図形周り

| 項目 | 設計書参照 | 現状 |
|:---|:---|:---|
| `3D_Renderer` の隠線処理 | §18.3 | `dashed` フラグ依存。複雑な立体の自動判定は未実装 |
| `2D_Geometry_Renderer` の `arrow_marker` | §18.3 | constructor 引数はあるが描画ロジック未配線 |
| 図形 SVG の視覚的検証 | §17.3 | テストは `<svg` を含むかのみ。人間レビューや diff 比較は未実施 |
| VisualBuilder（Verb → VisualDSL 自動組み立て） | §37 `_build_visual_dsl` | 未実装。`BlueprintRunner._build_visual_dsl` は常に `None` を返す |

---

## カテゴリ I. API / CI / 非同期（Phase 6 で実装済み）

| 項目 | 設計書参照 | 現状 |
|:---|:---|:---|
| Pydantic API モデル | §31 | ✅ `apps/api/src/domains/problems/schemas.py` |
| FastAPI ルーター | §15.4 Phase 6 | ✅ `apps/api/main.py` + `domains/problems/router.py` + `domains/teachers/router.py` |
| HTML UI（KaTeX） | §35.2 | ✅ `apps/api/templates/index.html`（学年/単元/形式/難易度/未習熟入力）|
| GitHub Actions CI yaml | §32 | ✅ `.github/workflows/test.yml` |
| バックグラウンド非同期生成（PrefetchCache） | §42 | ❌ 未実装。ローカル単一ユーザー UI では当面不要 |

---

## カテゴリ J. 設計書記載で実装漏れの細部

| 項目 | 設計書参照 | 現状 |
|:---|:---|:---|
| 重複排除のハッシュ粒度分岐 | §12.6 | 一律 SubQuestion.answer + LogicStep.sympy_expr。証明問題は本来 `operation_name` 列で判定 |
| lesson 別 `is_clean_override` の細粒度設定 | §35.5 | 全 lesson 一律 disabled |
| AtomSelector の `accepted_tags` 空時の警告 | §38.2 | 動作はするがログ無し |
| Atom 採択メタデータ（git コミットハッシュ） | §14.1 | 未配線 |
| §25.2 ScenarioBank クラス | §25.2 | 未実装（scenarios.yaml は読み込み専用） |
| §16.1.1〜16.1.4 atoms.yaml / verbs.yaml 等のメタ YAML | §16 | 未生成（コード内に直接定義） |

---

## 復帰戦略のロードマップ

短期（Phase 6 内で対応）:
- Pydantic モデル・FastAPI ルーター・HTML UI・CI yaml 整備
- 非同期生成 PrefetchCache

中期（実 LLM 接続後）:
- `dedup_disabled` / `is_clean_override.disabled` を全 mapping から外す
- §29 プロンプトを実 Gemini で実行し、Accuracy 検証を §12.5 通りに有効化
- §35.1 の残り 823 問サンプリング実施

長期（Phase 7 以降・本格運用）:
- カテゴリ F・G の Verb/Blueprint 細部
- VisualBuilder と図形自動配置
- §16 メタ YAML 化
- §20 Future Work の取り込み判断
