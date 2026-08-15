# システム欠陥修正 指示書（実装者：Sonnet 向け）

作成日: 2026-07-06
作成者: 調査担当（Opus + 3体調査エージェント）

---

## 0. この指示書の目的とスコープ

中学数学問題生成システムの生成精度が低い（LLM評価で A=26%, B=37%、特に B は
knowledge=0%, word_problem=9.5%, visual=38%, proof=35%）。原因を3層に切り分けた結果、
**層2（中間表現→LLMの配線切れ）と層3（中間表現そのもののバグ）がシステム側の実欠陥**である。

本指示書は **層2・層3 の修正**を対象とする。
**層1（評価パイプラインのズレ）は本指示書の対象外**（別途対応）。

### 前提知識：システムは3段パイプライン
1. **①計算骨格生成**: Blueprint + Atom(Noun) + Verb が SymPy で計算し `MiddleRepresentation`(MR) を作る
2. **②LLM翻訳**: `LLMTranslator.translate()` が MR を自然言語の問題文・解説に翻訳（Gemini）
3. **③図レンダリング**: `_render_visual()` が `visual_dsl` を SVG 化

`/problems/inspect` は ① の直後（LLM翻訳前の生データ）を返す。
`/problems/generate` は ①②③ を通した最終問題を返す。

### 診断の詳細
`/Users/koki/.claude/projects/-Users-koki-workspace-mongene-v2/memory/project_precision_root_cause.md`
（メモリ）に3層診断の全文がある。適宜参照すること。

---

## 1. 全体の作業原則（厳守）

- **既存の256テストを壊さないこと**。各タスク後に `python -m pytest tests/ -q` を実行し全通過を確認。
- **拡張性を守る**。過去の修正で `blueprint_params` 機構等が確立している。ハードコードで個別レッスンを
  握り潰す修正は避け、仕組みで直す。
- **SymPy が計算した数値・答えは絶対に変更しない**（システムの根本契約）。
- 修正ごとにコミットを分ける。コミットメッセージ末尾に指定の Co-Authored-By を付ける。
- 変更後、`master_data/mapping.json` を触った場合は `python scripts/verify_mapping.py`（あれば）で整合確認。

---

## 2. タスク一覧（優先度順）

### T1【層2・最優先・低コスト高効果】answer.extras を LLM プロンプトに配線する

**現状の欠陥**:
`apps/api/src/core/llm/translator.py` の `_mr_to_yaml()`（276〜298行付近）が、各 sub_question を
YAML 化する際 `answer.type / sympy_form / text_form` の3フィールドしか転送しておらず、
**`answer.extras` を破棄している**。このため proof の `proof_output`（仮定→結論の構造）が
LLM に一切届かない。`_extract_final_answer()`（subquestion_builder.py:158-177）が
`type="proof", extras={"proof_output": ...}` を正しく作っているのに、下流で捨てられている。

**修正**:
`_mr_to_yaml()` の sub_questions を組み立てる dict に `extras` を含める。ただし extras が空でない
場合のみ含める（calculation では空なので冗長を避ける）。例:
```python
"answer": {
    "type": sq.answer.type,
    "sympy_form": str(sq.answer.sympy_form),
    "text_form": sq.answer.text_form,
    **({"extras": sq.answer.extras} if sq.answer.extras else {}),
},
```
extras 内の proof_output は dict（given/to_prove/steps/conclusion）なので YAML に素直に載る。

**検証**:
`SKIP_LLM_IN_TESTS` を外した状態で proof レッスン（例 g2_l32）を `/generate` し、
問題文に「仮定」「結論」「証明」構造が反映されるか確認（LLMはClaude Code CLIでの手動確認で可）。
最低限、`_mr_to_yaml` の出力に proof_output が含まれることを単体で確認する。

---

### T2【層2】LLM翻訳プロンプトに visual / knowledge のフォーム指示を追加する

**現状の欠陥**:
`apps/api/src/core/llm/prompts.py` の `PROBLEM_TRANSLATION_PROMPT`（14〜18行の「問題形式の厳守」節）に、
`calculation` / `word_problem` / `proof` の指示しかなく、**`visual` と `knowledge` の指示が欠落**している。
`problem_form` は MR 経由で LLM に渡っている（translator.py:283）ので、プロンプトに指示を足せば LLM が従える。

**修正**:
「問題形式の厳守」節に以下2形式を追記する（文言は既存トーンに合わせて調整可）:
- `visual`（図・グラフを使う問題）: 中間表現データの `visual_dsl`（図の要素・座標・図形）を前提に、
  「右の図のように」「図を見て」等で図を参照する問題文にする。図がある前提で問う。
- `knowledge`（知識・概念確認）: 用語の定義・性質・正誤判定・具体例を問う。穴埋めや一問一答形式にし、
  計算問題にしない。答えは概念・用語であり数値ではない。

**注意**: `visual` 指示を活かすには、`_mr_to_yaml` が `visual_dsl` の要約を LLM に渡す必要がある。
現状 `_mr_to_yaml` は visual_dsl を渡していない。T5 と連動して visual_dsl の要点（図形種別・寸法・座標）を
YAML に含める拡張を検討すること（図の全 DSL は冗長なので render_type と主要 elements のラベルのみで可）。

**補足（PROOF_TRANSLATION_PROMPT について）**:
`prompts.py:111` に `PROOF_TRANSLATION_PROMPT` が定義済みだが**どこからも呼ばれていない死にコード**。
T1 で extras を配線すれば `PROBLEM_TRANSLATION_PROMPT` 単体で proof を処理できるため、
**この専用プロンプトは無理に接続しなくてよい**。将来 proof 品質が不足する場合の選択肢として残す。
判断に迷ったら T1 の効果を先に測ってから決めること。

---

### T3【層3・本物のバグ】knowledge の答え型を作り直す（B=0% の真因）

**現状の欠陥**:
`apps/api/src/atoms/verb/knowledge_check_verb.py`（27-35行）が、`NumberAtom.value`（整数）を
`sympy_expr` に入れて返している。理由はコメント通り「E評価（重複なし）を通すため answer を問題ごとに
変える」ハック。結果、`subquestion_builder.py:179-184` の汎用分岐で `AnswerObject(type="numeric")` になり、
**「〜について説明しなさい」という問いに「9」「8」等の無意味な整数が答え**として付く（型が構造的に矛盾）。
`AnswerObject.type`（middle_representation.py:22）は `numeric/expression/proof/set/graph` のみで、
knowledge 用の型が存在しない。

**修正方針**（設計判断を含むため方針を示す。実装詳細は実装者の裁量）:

1. `AnswerObject.type` の Literal に `"knowledge"` を追加
   （`apps/api/src/core/representation/middle_representation.py:22`）。

2. `KnowledgeCheckVerb.solve()` を、数値ではなく**概念的な答え**を返すよう変更。
   `operation_name="knowledge_check"` は維持（`_augment_prompt_hint` が計算式を足さないため）。
   answer の text_form には「その概念の要点／定義／正誤」を入れる。sympy_form は None で可。

3. `subquestion_builder.py:_extract_final_answer` に `knowledge_check` 用の分岐を追加し、
   `AnswerObject(type="knowledge", sympy_form=None, text_form=..., extras={...})` を返す。
   proof の分岐（158行）の隣に足すのが自然。

4. **E評価（重複なし）の担保方法を、数値ハックから「問いの多様性」へ移す**:
   現状は同一レッスン同一レベルで2問生成すると両方「（同じdescription）について説明しなさい」で
   問い自体が同一になりやすい。KnowledgeBaseStructure（`apps/api/src/blueprints/knowledge_base.py`）が、
   同一レッスンでも異なる下位概念・異なる問い方（定義を答える／具体例を挙げる／正誤を判定する）を
   サンプルできるようにする。これにより2問が自然に異なり、E評価を正当に通す。
   実装の一案: mapping.json の knowledge レベルに複数の `knowledge_hint` 候補を持たせ、seed でサンプル。

**検証**:
- knowledge レッスン（例 g1_l1, g1_l11）を `/inspect` し、answer.type が "knowledge" で
  text_form が概念テキストになっていること。
- 同一レッスン同一レベルで2回生成し、問いが異なること（E評価が通る）。
- pytest 全通過（AnswerObject の型追加でスキーマ検証が壊れないか要確認、
  `apps/api/src/domains/problems/schemas.py` と `router.py` の answer シリアライズ箇所も見ること）。

---

### T4【層3】visual 非対応 blueprint の割当を修正する

**現状の欠陥**:
visual 形式のレッスン71件が「visual_dsl を実質生成しない blueprint」に割り当てられている。
特に `BasicCalculationStructure`（13件: g1_l2, g1_l29, g1_l30, g1_l31, g1_l32, g1_l34, g1_l35 等）は
ただの整数計算で、図の要素を一切持たない。LLM は数値変更禁止のため後段でも図を作れない。

**重要な判定基準**:
「supported_forms に visual があるか」だけで判定してはいけない。真の基準は
**「その blueprint が `visual_dsl` を生成するか（＝ `visual_slot.component_type` が `NullRenderer` でないか）」**。
例えば `BasicGeometryMeasurementStructure`（33件）は幾何測定なので図を持つ可能性がある。要確認。

**作業手順**:
1. visual 形式の全レッスンについて、割り当てられた blueprint の `visual_slot.component_type` を洗い出す。
   NullRenderer（＝図なし）の blueprint が visual に割り当てられているレッスンをリスト化する。
   （`/inspect` の結果や blueprint 定義を直接読んで判定。スクリプトを書いてよい。）
2. 図なし blueprint が割り当てられた visual レッスンについて、いずれかで対処:
   - (a) 図を生成できる適切な blueprint に `execute_blueprint_by_form.visual` を張り替える
   - (b) そのレッスンで visual 形式が本当に不要なら、difficulty_levels から visual を外す
   - (c) 該当概念に visual blueprint が存在しないなら、新規 blueprint 作成を検討（別タスク化してよい）
3. 判断はレッスンの内容次第。例: g1_l30「座標の概念」なら座標平面を描く visual blueprint が本来必要。
   g1_l2「数直線と絶対値」なら数直線を描く必要がある。

**検証**:
修正後、visual レッスンを `/inspect` して visual_dsl が非 None（component_type != NullRenderer）に
なっていること。全 visual レッスンで図データが生成されることを確認するスクリプトを作ると良い。

---

### T5【層2・T1と連動】construction（作図）の手順構造を配線する

**現状の欠陥**:
`apps/api/src/atoms/verb/construct_geometry_verb.py`（79-86行付近）が作図手順 `steps` を JSON で
operands に埋め込むが、`subquestion_builder.py:158` の特別扱いは `prove_` プレフィックスのみ。
`construct_*` は汎用分岐に落ち、答えが数式化され、手順構造は問題文プロンプトに届かない。

**修正**:
`_extract_final_answer`（subquestion_builder.py:152-184）に `construct_` 用の分岐を追加。
proof の分岐（158-177行）と同様に、operands から JSON をパースして
`AnswerObject(type=..., extras={"construction_steps": ...})` を作る。
T1 で extras が配線済みなら、これで作図手順が LLM に届く。
answer.type は既存の Literal に収まる形（"expression" 等）を使うか、必要なら "construction" を追加検討。

**検証**: construction レッスンを `/inspect` し、作図手順が extras に入ること。

---

### T6【層3・優先度中】A評価（単元適合）: tag/atom 選択のレッスン整合

**現状の欠陥**:
A評価（そのレッスンの概念を使っているか）が26%と低い。原因の一つは selected_tags / atom 選択が
レッスンの単元と噛み合っていないこと。例: knowledge レッスンの tag が全件
`fraction/integer/number` 固定（本来はそのレッスンの概念タグであるべき）。

**修正方針**:
- レッスンごとに `required_tags` / `atom_constraints` がその単元の概念を正しく表しているか点検。
  過去に g1 文字式で `required_tags=["polynomial"]` に直した実績がある（[[project-form-blueprint-fixes]]参照）。
- 三平方の定理レッスンなら `pythagorean`、円周角なら `inscribed_angle` 等、単元固有タグが
  selected_tags に現れる構成になっているか確認。
- これは個別レッスン単位の地道な作業。T1〜T5 を先に済ませ、A評価の真スコアを見てから範囲を絞ると効率的。

---

## 3. 推奨実施順序

1. **T1**（extras配線）… 最優先。proof が即改善。低コスト。
2. **T2**（visual/knowledgeプロンプト指示）… T1と同じ prompts/translator 領域。
3. **T3**（knowledge答え型）… B=0%の真因。やや大きいが効果大。
4. **T5**（construction配線）… T1の延長。
5. **T4**（visual blueprint割当）… mapping中心の作業。
6. **T6**（tag整合）… 最後。真スコアを見てから。

各タスク完了ごとに pytest 全通過を確認し、コミットを分けること。

---

## 4. 参考ファイル早見

| 目的 | パス |
|---|---|
| MR/AnswerObject 定義 | `apps/api/src/core/representation/middle_representation.py` |
| extras破棄箇所(T1) | `apps/api/src/core/llm/translator.py`（`_mr_to_yaml` 276-298） |
| LLMプロンプト(T2) | `apps/api/src/core/llm/prompts.py`（14-18, 111-124） |
| answer決定(T3,T5) | `apps/api/src/core/runner/subquestion_builder.py`（`_extract_final_answer` 152-184） |
| knowledge数値答え源(T3) | `apps/api/src/atoms/verb/knowledge_check_verb.py`（27-35） |
| knowledge blueprint(T3) | `apps/api/src/blueprints/knowledge_base.py` |
| construction verb(T5) | `apps/api/src/atoms/verb/construct_geometry_verb.py` |
| blueprint登録 | `apps/api/src/blueprints/registry.py` |
| レッスン定義 | `master_data/mapping.json` |
| APIスキーマ | `apps/api/src/domains/problems/schemas.py`, `router.py` |
| 動作確認 | `/problems/inspect`（LLM前）, `/problems/generate`（LLM後） |

## 5. 注意点・落とし穴

- `AnswerObject.type` に新値を足す場合、シリアライズ箇所（router.py の inspect/generate レスポンス、
  schemas.py の Pydantic モデル、fallback.py）が新 type を扱えるか必ず確認。テストが落ちる箇所。
- `SKIP_LLM_IN_TESTS=true` ではLLMがスタブ応答になる。プロンプト変更(T2)の実効果はスタブでは見えないので、
  Claude Code CLI 等で手動翻訳して確認するか、`_mr_to_yaml` の出力（LLMへの入力）を直接検証する。
- knowledge の E評価担保（T3-4）は設計判断。数値ハックを消すと、問いの多様性を別途担保しないと
  E評価が下がる。問いのバリエーション生成を必ずセットで実装すること。
