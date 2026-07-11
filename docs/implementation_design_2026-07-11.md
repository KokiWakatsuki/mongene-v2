# Education OS 問題供給エンジン 実装設計書 v1.1（ドラフト）

- 作成: 2026-07-11（v1.1: 実装者視点レビューの高10件・中12件を反映） ／ 対応要件: `docs/requirements_2026-07-11.html` v2.1（F/Q/N/D 番号は同書を参照）
- 対象読者: 実装者（人間・Claude Code とも）。**この文書の通りに実装すれば M0（金の縦串）に到達する**ことを目標に書く。
- スコープ: **G1（基礎情報生成）のみ**（要件 §3.1）。G2・問題バンク・セット組成（F-13）・final（F-10）は拡張点だけ定義し実装しない。
- 名称: システム全体= **Education OS**。本書の対象はその Layer 1 の**問題供給エンジン**（旧名モンジェネ。リポジトリ名 mongene-v2 は当面維持=D-6）。

---

## 0. この文書の使い方

1. 実装は §11 のタスク順に行う。**各タスクは「完了条件」が機械検証可能**（テストが通る・CLIが動く）。
2. 全ての実装判断はこの文書が根拠。曖昧さを見つけたら実装せず、本書を先に修正する（曖昧なまま書いたコードが過去の失敗の温床）。
3. テストコード・評価プログラムは「後で書く」ものではなく §11 の各タスクに**先行または同梱**されている。

---

## 1. 理論の穴 — なぜ「要件は正しいのに実装できなかった」のか

要件定義書は「何を満たすべきか」を定めたが、過去の実装は次の **8つの穴**（要件と実装の間の未定義領域）に落ちた。本書の §3〜§10 はこの穴を塞ぐ実装機構の定義である。

| # | 穴 | 過去に起きたこと | 本書の解決機構 | 定義箇所 |
|---|---|---|---|---|
| **H1** | 「宣言的スペック」と「コード」の境界が未定義 | blueprint=Pythonクラスに全てが流れ込み、セルごとの意図の置き場が消えた | **FamilySpec（YAML）が書けるもの・書けないものの厳密な文法**＋recipe（登録済み構成関数）への名前参照。境界は `spec_lint` が機械強制 | §4.3, §8.1 |
| **H2** | 「難易度＝構造の段」「重複」「類題」の操作的定義がない | Lvが数値ジッターに退化・重複測定不能 | **構造シグネチャ（宣言）＋計算指紋 fp（MRから機械導出）**。Q3=レベル間で署名が異なり fp も相異／重複=署名+正規化パラメータ一致（fp 系で二重測定）／variant A/B/C も同一機構で定義。宣言だけでは嘘をつけるため fp が実体に接地する | §4.4 |
| **H3** | 全問題を LLM 翻訳に通す前提 | calculation にまで忠実性リスクとコストを負い、Q6 が全セルのボトルネックに | **テキスト描画の3層化**: T1=決定論テンプレート（LLMゼロ・大半のformをカバー）／T2=テンプレ+磨き／T3=LLM翻訳+検証。LLMは T3 のみ | §7 |
| **H4** | 生成＝拒絶サンプリング（リトライ50回） | 制約が強いセルは生成失敗・seed汚染・性能劣化 | **構成的生成（answer-first）を標準パターン化**: 綺麗な答えを先に決めて問題を逆算する。リトライは原則禁止（有界例外のみ・統計記録） | §6.1 |
| **H5** | 「正しい」の保証が生成経路と同一 | 生成コードのバグ＝答えのバグ（検出不能） | **double-solve**: recipe が構成した答えと、独立ソルバが問題パラメータから再計算した答えの一致を Q1 ゲートとする | §6.2 |
| **H6** | セルの完成判定が人の目・実装者の自己申告 | 「動いた」で先に進み、後で破綻発覚 | **セルDoD の機械化**: schema✓ smoke✓ ゲート✓ golden承認✓ 重複率✓ レベル分離✓ を CI が強制。ダッシュボードで全セル進捗を可視化 | §8, §10 |
| **H7** | 意図（form/purpose/level）の伝搬がコーディング規約頼み | 図が form を無視・答えが図に漏れた | **型で強制**: 全段の関数が `CellContext` を必須引数に取る。visual は「frame が要求を宣言した場合のみ」パイプラインが呼ぶ（各実装の if 文ではなく骨格が保証） | §5 |
| **H8** | 再現性の設計がない | seed が時刻ベース・LLM出力が毎回変わり、バグ再現も監査も回帰も不能 | **RNG 規律**（`derive_rng(family, level, seed)` 以外の乱数禁止）＋**レンダリングキャッシュ**（T2/T3 の出力を key=(mr_hash, template_version, model) で保存し problem_ref に含める） | §5.3 |

> 過去実装の資産（SymPy ソルバ・atom 部品・ゲート・翻訳プロンプト）は捨てない。§12 の移設マップに従って新構造に移す。

---

## 2. 技術方針

| 項目 | 決定 | 理由 |
|---|---|---|
| 言語 | Python 3.12（既存 .venv 継続） | SymPy 資産・チームスキル |
| 型・契約 | pydantic v2 で全データ契約を定義。`mypy --strict` を CI に | H7（型で意図を運ぶ） |
| API | FastAPI（既存）。ただし M0 は**ライブラリ+CLI ファースト**、API は薄いラッパ | 検証・制作ツールが先。API は最後に被せる |
| スペック | YAML（JSON Schema で検証） | 教育者可読・diff 可能・コードとの境界が明確（H1） |
| テンプレート | Jinja2（sandbox・フィルタは登録制） | T1 の決定論性 |
| LLM | T3 翻訳=Gemini（既存キー）/監査=Claude。すべてアダプタ経由＋キャッシュ必須 | N-3・H8 |
| テスト | pytest（既存465本は旧系のまま維持）＋新系 `engine_tests/` | 並行構築（D-6） |
| 配置 | 同一リポジトリに新トップレベル `engine/` を作り並行構築。旧 `apps/api` は当面触らない | D-6 推奨案 |

---

## 3. リポジトリ構造（新設分）

```
engine/
  core/                     # 科目非依存カーネル（数学を import してはならない）
    contracts.py            #   Request / Problem / MR / Unsupported / CellContext（pydantic）
    pipeline.py             #   generate() 本体（§5）
    rng.py                  #   derive_rng / 乱数規律
    registry.py             #   recipe / template / checker / frame の登録機構
    spec/                   #   FamilySpec ローダ・JSON Schema・spec_lint
    render/
      t1_template.py        #   Jinja2 決定論レンダラ＋数値整形フィルタ
      t2_polish.py          #   磨きアダプタ（M1）
      t3_translate.py       #   LLM翻訳アダプタ＋忠実性ゲート（M1）
      cache.py              #   レンダリングキャッシュ（H8）
    verify/
      gates.py              #   ゲート枠組み（登録制・全滅時 Unsupported）
      leak.py               #   Q5 漏洩検査（除外規則つき）
  packs/
    math/
      frames.py             #   7型 form → Frame 定義（§6.3）
      recipes/              #   構成的ジェネレータ（answer-first）
      solvers/              #   独立再計算ソルバ（旧 verb 33種の移設先）
      parts/                #   題材部品（旧 atom 21種の移設先）
      checkers/             #   form適合・スタイルlint（通貨=円 等）
      templates/            #   T1 テキストテンプレート
      visuals/              #   図ビルダ（旧 renderer 移設）
  curriculum/
    math/
      units.yaml            #   単元・概念・誤答要因・前提関係（input_spec から変換生成）
      families/             #   FamilySpec 置き場: g2_l25.find_value.yaml 等
  eval/                     #   評価プログラム群（§8.2）
  tools/                    #   spec CLI（draft/preview/check）・進捗ダッシュボード
engine_tests/
  unit/  golden/  contract/
```

**依存の向きの規律**（import-linter で CI 強制）: `core` → 何にも依存しない（packs/curriculum を import 禁止）。`packs/math` → core のみ。`eval`/`tools` → 両方可。

---

## 4. データ契約（すべて pydantic で `core/contracts.py` に定義）

### 4.1 Request / Unsupported

```python
class GenerateRequest(BaseModel):
    subject: str                  # "math"
    unit: str                     # "g2_l25"
    form: str                     # "find_value"（語彙の正=curriculum）
    level: int                    # band絶対値 1..4
    purpose: Purpose = "base"     # base | remedial | variant（final はM2）
    seed: int | None = None       # None → エンジンが採番し必ず応答に含める
    options: GenerateOptions = GenerateOptions()

class GenerateOptions(BaseModel):
    cause_id: str | None = None            # remedial 用
    target_concepts: list[str] = []        # 概念絞り込み
    variant_of: VariantRef | None = None   # {problem_ref, mode: "A"|"B"|"C"}
    avoid: list[str] = []                  # problem_ref のリスト

class Unsupported(BaseModel):
    code: Literal[
        "unit_not_found", "form_not_supported", "level_not_supported",
        "purpose_not_supported", "cause_not_found",
        "verification_exhausted",   # F-14: ゲート全滅
        "supply_exhausted",         # avoid/variant の再抽選が有界内で尽きた（§5.3）
        "not_implemented",          # スペック未制作（capabilities に出ない）
    ]
    detail: str
```

### 4.2 MR（中間表現）と Problem

```python
class Step(BaseModel):
    op: str                    # ソルバ演算名（例 "solve_linear_eq"）
    args: list[str]            # 入力（表示可能形）
    result_srepr: str          # sympy srepr（機械厳密形＝moat）
    result_display: str        # 表示形（例 "x = 3"）
    narration: str             # 「なぜこの計算か」1文（T1/T3・ヒントの素材）

class SymbolicAnswer(BaseModel):     # 数値・式（calculation / find_value / word_problem）
    srepr: str                       # sympy srepr（moat）
    display: str

class ChoiceAnswer(BaseModel):       # knowledge（用語・真偽・選択）
    correct: str
    distractors: list[str]           # 妨害選択肢（recipe が構成）
    fact_id: str                     # 検証の根拠（curriculum の fact テーブル ID。§6.2）

class GraphAnswer(BaseModel):        # graph_table「かく」・construction
    features: list[Feature]          # 検証可能な特徴点（通る点・切片・傾き 等）
    solution_svg_ref: str            # 模範解答図（問題図とは別部品。§6.4）

AnswerPayload = SymbolicAnswer | ChoiceAnswer | GraphAnswer   # form により直和で拡張（H4 の form 差の受け皿）

class SubQuestionMR(BaseModel):
    label: str                       # "(1)"
    asked: str                       # 問う対象（frame語彙 §6.3）
    answer: AnswerPayload
    steps: list[Step]                # 採点粒度: 式変形1ステップ=1要素（D-2暫定）
    concept_tags: list[str]          # curriculum の概念ID（必須・非空）
    cause_tags: list[str]            # この問題で検証できる誤答要因ID

class MR(BaseModel):
    signature: str                   # 構造シグネチャ（§4.4）
    family: str                      # "math.g2_l25.find_value"
    level: int
    purpose: Purpose
    seed: int
    params: dict[str, Any]           # recipe が構成した具体値（正規化可能であること）
    given: dict[str, str]            # 問題文に出す「与えるもの」（表示形）
    context_slots: dict[str, str] = {}  # variant B の題材スロット（人名・場面等）。dup_key に算入しない
                                        # （D-1 の同値定義: 文脈だけ違う問題は「実質重複」とみなす）
    sub_questions: list[SubQuestionMR]
    visual_plan: VisualPlan | None   # frame が要求する場合のみ非None
    provenance: Provenance           # recipe名+版, spec版, git_commit

class SubQuestionOut(BaseModel):    # フィールド名は要件 §4.2 に一致（contract テストで検証）
    label: str
    prompt_text: str                 # 小問の問い
    answer: AnswerPayload
    solution_steps: list[Step]
    explanation: str                 # M0 方式: steps の narration+result_display を決定論テンプレで結合（§7）
    hints: list[str]                 # steps_prefix。steps<2 のセルはテンプレ定義ヒント必須（lint R7）
    concept_tags: list[str]
    cause_tags: list[str]

class Problem(BaseModel):           # API 出力（要件 §4.2 と一致）
    problem_ref: str                 # sha256(provenance + seed + render_keys)
    problem_text: str
    visual_svg: str | None           # 問題図のみ（模範解答図は AnswerPayload 側＝開示制御に従う）
    sub_questions: list[SubQuestionOut]
    meta: Meta                       # 要求座標＋解決先座標(remedial時), purpose, seed, signature, tags, 再現情報
```

**再現の定義（F-2, H8）**: `problem_ref` から MR は完全再構成できる（座標+seed+版）。テキストは render cache のキーが meta に入り、キャッシュ参照で同一文が返る。キャッシュ消失時は「MR は同一・文面は再翻訳」となることを仕様として明記（T1 はキャッシュ不要で完全決定論）。

### 4.3 FamilySpec（著作の単位・YAML）— H1 の解決

**1ファイル = 1 (unit × form)**。レベルはその中に列挙。**スペックに書けるのは「選択と参照と定数」だけ**で、ロジック（条件分岐・計算・ループ）は書けない。ロジックが必要になったら pack に recipe/checker を追加して名前で参照する（それが Open-Closed の追加単位）。

```yaml
# curriculum/math/families/g2_l25.find_value.yaml
family: math.g2_l25.find_value
form: find_value
source_desc: |                                     # ★input_spec の desc/example の転記（必須=R8。preview に併記）
  2点の座標から1次関数の式を求める。Lv2=2点から傾きを計算し代入で切片。
  Lv3=連立方程式で係数決定・分数傾きを含む。
concepts_default: [linear_function.expression_from_points]
levels:
  "2":                                             # band絶対Lv（疎で良い）
    signature: lf_expr_two_points_basic            # ★family内で一意（§4.4）
    recipe: math.linear_from_two_points            # ★登録済み構成関数の名前
    params:                                        # recipe への引数（§4.3.1 のドメイン記法のみ）
      method: slope_then_intercept                 # 傾き→代入（解法列＝署名の実体）
      slope_domain: {int_range: [-4, 4], exclude: [0]}
      point_domain: {lattice: {x: {int_range: [-5, 5]}, y: {int_range: [-8, 8]}}, distinct: [x]}
    given: [point_a, point_b]                      # frame 語彙（§6.3）で「与えるもの」
    asked: [expression]                            # 「問うもの」
    visual: none                                   # none | required | optional
    text: {tier: T1, template: lf_expr_two_points_v1}
    hints: [steps_prefix]                          # ヒント生成方式（登録名）
    cause_tags: [lf.slope_formula_error, lf.substitution_error]
  "3":
    signature: lf_expr_two_points_simultaneous     # ★同じ given でも解法列と数域が変わる＝別構造
    recipe: math.linear_from_two_points
    params:
      method: simultaneous                         # 連立で係数決定（steps の op 列が Lv2 と異なる）
      slope_domain: {frac_range: {num: [-5, 5], den: [2, 3]}}   # 分数傾き
      point_domain: {lattice: {x: {int_range: [-6, 6]}, y: {int_range: [-9, 9]}}, distinct: [x]}
    given: [point_a, point_b]
    asked: [expression]
    visual: optional
    text: {tier: T1, template: lf_expr_two_points_v1}
    hints: [steps_prefix]
    cause_tags: [lf.simultaneous_setup_error]
remedial:                                          # この family が戻り先として使われる時の既定 level
  default_level: 2                                 # （curriculum の対応表が level を省略した場合のみ使用。§5.2）
```

> **この例自体が教訓**: v1.0 ドラフトでは Lv2 を「傾きと1点から」と書いていたが、input_spec の正では g2_l25 は「2点から式」であり、傾き+1点は **g2_l24 の題材**（＝Q4 題材ズレ）。記入例すら座標の正（source_desc）との突合を要する——これが R6/R8 を lint にする理由である。また Lv2/Lv3 が**同じ given** でも解法列（steps の op 列）と数域で別構造になる好例＝署名は given の型だけでなく解法列を含む。

`spec_lint`（§8.1）が強制する規則:
- R1: 未登録の recipe / template / checker 名 → エラー
- R2: 同一 family 内で signature 重複 → エラー（H2/Q3 の前提）
- R3: params に許されるのは JSON スカラー・配列・**ドメイン記法**（`int_range` 等の登録済み語彙）のみ
- R4: concepts / cause_tags は curriculum に実在する ID のみ
- R5: form と frame の整合（asked/given が frame 語彙に含まれる、visual が frame の許容と矛盾しない）
- R6: **題材ズレの静的検出**——recipe は登録時に「提供できる概念タグ集合」を宣言し、セルの concepts がその部分集合であることを検査（過去最大の失敗モード「recipe を違うセルに配線」の再発防止）
- R7: hints が steps_prefix のみで、そのレベルの steps 期待長が 2 未満になり得る場合はテンプレ定義ヒントを必須化（F-1 全部品非空の保証）
- R8: source_desc（input_spec の desc/example の転記）必須。preview HTML に生成物と併記され、検収者が「セル定義 vs 生成物」を並べて確認する

### 4.3.1 ドメイン記法 v1（閉じた語彙・H1 の境界線そのもの）

params に書けるのは JSON スカラー・配列・下表の登録済みドメイン記法のみ。**新語彙の追加は core registry へのコード追加**（＝レビュー対象。スペック側で発明してはならない）。

| 語彙 | schema | 意味論 |
|---|---|---|
| `{int_range: [a, b]}` | 整数2要素・a≤b | a..b の一様整数（両端含む） |
| `{int_set: [v, ...]}` | 整数配列・非空 | 集合からの一様選択 |
| `{frac_range: {num: [a,b], den: [c,d]}}` | 各 int_range | 既約分数 num/den の一様生成（den∉{0,±1}） |
| `{lattice: {x: <domain>, y: <domain>}}` | 軸ごとに上記ドメイン | 格子点の一様生成 |
| 修飾子 `exclude: [v, ...]` | 値の配列 | 生成値から除外。除外後に空なら `spec check` が失敗 |
| 修飾子 `distinct: [axis, ...]` | 軸名の配列 | 複数抽選時に当該軸の値の相異を保証 |

- **消費 API**: `core.rng.draw(domain_spec, rng) -> value`／複数は `draw_many(domain_spec, rng, k)`。**recipe はこの API 以外でドメインを解釈してはならない**（ruff ルールで検査）。
- spec_lint R3 ＝ この schema への適合検査、と定義する。M0 はこの6語彙で開始し、不足は registry 追加で拡張。

### 4.4 構造シグネチャ — H2 の解決（Q3・重複・類題の統一機構）

- **定義**: `signature` = 「問題の構造」の名前。同一署名 ⇔ given/asked の型・解法列・小問構成が同型。recipe が MR に刻印し、スペックの宣言と一致することをゲートが検証する。
- **正規化パラメータ**: recipe は `params` の**正規形**（順序・符号・スケールの正規化）を定義する。`dup_key = sha256(signature + normalize(params))`。
- これにより:
  - **Q3（難易度分離）** = family 内でレベル間の署名が相異（spec_lint R2 で静的保証）＋下記 fp で実体検証
  - **重複（F-3/D-1）** = dup_key 一致。重複率 = 100 seed 中の dup_key 衝突率
  - **variant A** = 同一署名・同一 recipe・パラメータ再抽選（dup_key が変わるまで。有界10回→supply_exhausted）
  - **variant B** = 同一署名・`context_slots`（題材変数）のみ差替（dup_key は不変＝文脈差は実質重複としない設計）
  - **variant C** = 同一 concepts・別署名（family 内の別レベル or 別 family から解決）
  - **avoid** = dup_key の除外リスト（有界10回→supply_exhausted）

**計算指紋（fingerprint）による接地 — 「宣言の嘘」を防ぐ（H2 の完結）**:
署名はスペックと recipe の自己申告であり、一致検査（G-SIG）だけでは「Lv2 と Lv3 に実質同構造の問題を出しつつ別名の署名を貼る」ことを検出できない（過去の失敗「Lv が構造を変えない」の抽象化再発）。そこで **MR から機械導出する計算指紋** `fp(MR) = (given/asked の型ベクトル, steps の op 列, 小問数)` を導入する。steps は独立ソルバ由来なので recipe 側で偽装しにくい。強制は3点:
1. **G-FP（動的ゲート）**: 同一 signature の生成物は全 seed で fp が安定（署名⇔構造の対応が実在する）
2. **eval/level_sep（必須検査）**: family 内の異なる signature 間で fp が相異（＝レベルが実際に構造を変えている）
3. **eval/dup_rate（2系統測定）**: dup_key 系に加え fp 系でも測定し、別署名を貼った実質同一構造を可視化する

---

## 5. コアパイプライン（`core/pipeline.py`）

```python
def generate(req: GenerateRequest) -> Problem | Unsupported:
    # 1) 解決: curriculum → family spec → level block。無ければ理由コードで拒否（F-5）
    ctx: CellContext = resolve(req)          # 失敗: unit_not_found / form_not_supported / ...
    # remedial は cause_id → curriculum の静的対応 → 別セルの ctx に解決してから同じ道を通る

    # 2) 乱数: これ以外の乱数源は全リポジトリで禁止（H8, ruff カスタムルールで検査）
    seed = req.seed if req.seed is not None else issue_seed()
    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)   # purpose 込み（base と variant が同じ列を引かない）

    # 3) 構成的生成（リトライなしが原則。§6.1）
    mr = REGISTRY.recipe(ctx.spec.recipe).construct(ctx, rng)

    # 4) 決定論ゲート（登録制・順序固定。1つでも fail → verification_exhausted で返す。
    #    ※有界リトライは recipe が宣言した場合のみ最大3回、eval が統計を記録）
    run_gates(mr, ctx, stage="mr")           # Q1 double-solve / Q2 frame / Q7 tags / signature一致

    # 5) テキスト（§7）→ 6) テキスト後ゲート → 7) 図 → 8) 図後ゲート
    text = render_text(mr, ctx)              # T1/T2/T3（tier はスペック宣言）
    run_gates(text, ctx, stage="text")       # Q5 leak / T3のみ grounding・fidelity
    svg  = render_visual(mr, ctx)            # ctx.frame.visual が要求する時だけ骨格が呼ぶ（H7）
    run_gates(svg, ctx, stage="visual")      # Q5 図内漏洩（ラベルwhitelist方式 §6.4）

    # 9) 組み立て（ヒントは steps から派生 §7.4）
    return assemble_problem(mr, text, svg, ctx)
```

- **CellContext** は resolve() だけが作れる不変オブジェクト: `family / form / frame(FrameProtocol) / level / purpose / spec_level（level ブロック）/ spec_family（family メタ: concepts_default, source_desc 等）/ curriculum_view（そのセルが参照してよい概念・要因辞書の部分ビュー）`。**全下流関数の第一引数**（H7）。frame の実体は pack にあるが、core は `FrameProtocol`（given_vocab / asked_vocab / visual 許容 / 幾何規則）にのみ依存する（§3 の依存規律と両立）。`VisualPlan / Provenance / Meta / Solution / Rng / Feature` も contracts.py に定義する（フィールドは §4 の記載が正）。
- **供給源の抽象（F-21/F-22/N-2 の拡張点）**: 手順 3)〜8) は `Supplier` インターフェース（`supply(ctx, seed) -> Problem`）の一実装「生成器」として実装する。M1 のプール（事前生成した検証済み Problem の即時取り出し＝授業内 ≤3秒 の実現手段）と将来の問題バンクは Supplier の別実装として差し込む。**M0 では生成器のみ実装するが、pipeline はこの一段を最初から持つ**（M1 での骨格改修を防ぐ）。
- **capabilities()** = curriculum×families を走査し「スペックが存在し `spec check` 済み」のセル一覧を返す。`not_implemented` はここに出ないことで F-5/F-6 が整合。

### 5.2 remedial の解決（F-7 の実装）

units.yaml の誤答要因 schema:

```yaml
error_causes:
  - id: lf.confused_with_proportional
    label: "比例と混同した"                          # 生徒UIの選択肢文言（ホストが表示）
    target_concepts: [proportional.definition]
    remediation: {unit: g1_l36, form: find_value, level: 1}   # 戻り先座標（静的対応・送り側が唯一の決定者）
```

- 解決アルゴリズム: `cause_id → curriculum の remediation 座標 → その座標で resolve → 以降は通常経路`。
- 着地 level の決定者は **curriculum の対応表（送り側）が唯一**。family 側の `remedial.default_level` は対応表が level を省略した場合の既定値に過ぎない（決定者の二重化を禁止）。
- **meta は requested（元リクエスト座標）と resolved（解決先座標）の両方を持つ**（ホストは resolved で進捗管理できる）。
- ゲート拡張 **G-Q7r**: remedial 時、解決先セルの concept_tags ⊇ 要因の target_concepts（F-7 の受け入れ基準の機械化）。
- エラー: 要因 ID 不在 → `cause_not_found`／対応表の座標が capabilities に無い → `not_implemented`（curriculum_lint が静的にも検査）。
- **remedial の DoD** = 縦串単元の全要因について generate が成功し G-Q7r を通ること（新規スペックを書く作業ではなく、curriculum の対応表整備＋検証。§11 タスク9 に含む）。

### 5.3 乱数とキャッシュの規律（H8）

- `derive_rng(family, level, purpose, seed)` = SHA256 ベースの独立ストリーム。attempt が必要な場合は `rng.spawn(k)`。
- `random.*` / `numpy.random.*` の直接使用は ruff ルール（`engine/` 配下）で CI 禁止。**このルール自体にも fail テストを置く**（違反コードを検出できることの回帰）。
- `issue_seed()` は OS エントロピー（`secrets`）による採番で、乱数禁止規律の**登録された唯一の例外**。
- variant A / avoid の再抽選は**有界（最大10回）**とし、枯渇時は `Unsupported(supply_exhausted)`（§6.1「リトライ原則禁止」の明示的例外として宣言）。
- T2/T3 の LLM 出力は `render/cache.py`（SQLite）に `key=(mr_hash, template_or_prompt_version, model_id)` で保存。golden テストはキャッシュ込みでコミットする。

---

## 6. 数学パック

### 6.1 recipe = 構成的生成（answer-first）— H4 の解決

recipe は「答え（または綺麗な中核値）を先に決め、問題を逆算する」**登録済み関数**。

```python
@register_recipe("math.linear_from_two_points")
def linear_from_two_points(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec.params
    # 1) 綺麗な答えを先に構成（answer-first）: 整数傾き・整数切片を先に選ぶ
    a = draw(p["slope_domain"], rng)                     # 傾き（§4.3.1 の消費API以外での解釈は禁止）
    b = draw({"int_range": [-8, 8]}, rng)                # 切片
    (x1, _), (x2, _) = draw_many(p["point_domain"], rng, k=2)   # distinct:[x] は記法側が保証
    pts = [(x1, a*x1 + b), (x2, a*x2 + b)]              # 直線上の格子点を逆算 → 制約は構成で恒真
    # 2) 独立ソルバで解き logic_steps を得る（構成値は使わない！→ §6.2 double-solve）
    sol = SOLVERS.linear_expr_from_points(pts)           # SymPy: 連立で a,b を再導出
    assert_eq(sol.expr, sympify(f"{a}*x + {b}"))         # 不一致は recipe のバグ = 即例外
    return build_mr(signature="lf_expr_from_two_points", params={"a": a, "b": b, "pts": pts},
                    given=fmt_points(pts), asked=["expression"], steps=sol.steps, ctx=ctx)
```

**標準パターン集**（recipes/ に基底ヘルパとして用意。新規 recipe はこれらの組合せで書く）:
1. **answer-first**: 解→係数を逆算（方程式・関数・図形の計量）
2. **factor-first**: 因数→展開して問題に（因数分解・展開）
3. **lattice/図形制約**: 格子点・整数辺・実在条件（三角不等式等）を構成で保証
4. **有界リトライ**（例外）: 構成で保証しきれない希な条件のみ `@bounded_retry(3)` を宣言。eval が発動率を記録し、5% 超はスペック不合格

### 6.2 solver = 独立再計算（Q1 double-solve）— H5 の解決

- `packs/math/solvers/` は**問題パラメータだけ**から答えと steps を導く（recipe の構成値を見ない）。
- 旧 verb 33種をここへ移設（署名は `solve(*args) -> Solution(answer, steps)` に統一）。
- Q1 ゲート = 「recipe の意図した答え」と「solver の再計算」の一致。**LLM はこの経路に存在しない**（数学パックの V1 宣言）。

**form 別の Q1 保証水準（正直な宣言・要件 §8③ と整合）**:

| form | Q1 の検証方式 | 水準 |
|---|---|---|
| calculation / find_value / word_problem | double-solve（srepr 一致） | V1 |
| knowledge | 答えの根拠は curriculum の **fact テーブル**（`facts.yaml`: id・命題・真偽・出典単元）。recipe＝fact からの選択＋妨害選択肢の構成、Q1 ゲート＝fact_id 照合 | **V2**（数学でも knowledge は V1 にならない——これを隠さない） |
| graph_table「かく」 | double-solve の対象＝**特徴点集合の一致**（solver が式・データから特徴点を独立再導出し、GraphAnswer.features と照合）。模範解答図は特徴点から描画 | V1′ |

**double-solve の限界（明示）**: double-solve が守るのは Q1（答えの正しさ）のみ。「MR と問題文の意味的一致」（傾きを切片とラベリングする類のバグ）は守れない——それは G-GND（grounding・全 tier 必須 §7）＋preview 検収＋audit の責務。

### 6.3 frame = form の実装（Q2 の機械化）

7型それぞれに Frame を定義（`packs/math/frames.py`）。Frame は**語彙（実列挙）と制約**を宣言し、ゲートが MR を検査する。語彙は**開いている**——不足時は frames.py への追加＝Open-Closed の単位（PR レビュー対象）:

| form | given_vocab（初版） | asked_vocab（初版） | visual | Answer型 |
|---|---|---|---|---|
| calculation | expression, equation | value, simplified_expr, solution | **禁止** | Symbolic |
| knowledge | statement, term_context | term, true_false, choice | 禁止（M0） | Choice |
| find_value | point_a, point_b, slope, intercept, expression_coeffs, condition, figure_spec | value, expression, coordinate, rate_of_change, domain_range, intersection, area | optional / required | Symbolic |
| graph_table | expression, data_table, situation_params | draw_graph, read_point, read_intersection, read_table, complete_table | required | Graph（かく）/ Symbolic（読む） |
| word_problem | scenario（T3）, quantities | formulation, value | optional | Symbolic |
| proof（M1） | premises, conclusion | proof_text | optional | （M1で定義） |
| construction（M2） | construction_conditions | construction_steps | required | Graph |

初版語彙は縦串候補（g2 一次関数クラスタの実セル: knowledge/calculation/find_value/graph_table/word_problem）を賄う想定で列挙した。不足が出たら frames.py に追加する（スペック側で発明しない）。

Frame 適合ゲート（Q2）= MR.given/asked のキーが frame 語彙に含まれ、visual 宣言が frame の許容内であること。**「calculation なのに図が付く」は骨格＋実行時ゲートの二重で作れない**（frame.visual=forbidden なら pipeline が render_visual を呼ばず、G-Q2 が visual_plan 非 None を拒否する）。

### 6.4 visual（図）

- 旧 renderer（SVG/2D/3D/グラフ）を `packs/math/visuals/` へ移設。
- **ラベル whitelist 方式**（Q5, 旧 builder.py:855 の答え漏洩の恒久対策）: 図に描いてよい文字列は `visual_plan.labels` に**明示列挙されたもののみ**。`visual_plan` は MR.given からしか作れないヘルパで構築（asked 系の値はコンパイル時に入らない）。ゲートは SVG 内テキストが whitelist の部分集合であることを検査。
- **問題図と解答図の分離**: `Problem.visual_svg`＝問題図（whitelist 検査対象）。模範解答図は `GraphAnswer.solution_svg_ref`＝**定義上答えを含む**ので whitelist 対象外だが、answer 部品側に置かれるためホストの開示制御に従う（F-9 と両立）。
- **幾何的リーク規則（Q5 の非文字列版）**: 要件 F-16 の漏洩定義は「解かずに答えが読み取れる」であり、文字列 whitelist では幾何リーク（交点を問うのに方眼上に2直線が描かれ交点が読める等）を防げない。visual_plan は描画要素（grid・目盛・直線・点）も宣言し、**frame が「asked と両立しない描画要素」の禁止規則を持つ**（例: asked=intersection ⇒ 方眼＋両直線の同時描画禁止、目盛なしスケッチ様式を強制）。M0 は縦串の find_value/graph_table 分の規則のみ定義。
- **紙適合（N-4）**: SVG は色のみで情報を伝えない（線種・ラベルで区別）。checker がモノクロ変換検査を行う（§11 タスク8 の完了条件）。

---

## 7. テキストレンダリング3層 — H3 の解決

| 層 | 方式 | 対象 form（目安） | コスト/決定論 |
|---|---|---|---|
| **T1** | Jinja2 テンプレート＋整形フィルタ（分数・単位・敬体） | calculation, knowledge, find_value, graph_table, construction | ¥0・完全決定論 |
| **T2** | T1 出力を LLM で1回磨く。**数値・固有名詞の保存を diff ゲートで検証**、失敗時は T1 を出す | find_value の一部（M1〜） | 低・キャッシュ |
| **T3** | MR→LLM 翻訳（既存プロンプト資産を移設）。leak/grounding/忠実性ゲート必須 | word_problem, proof | 中・キャッシュ必須 |

- **M0 は T1 のみ実装**。これで縦串単元の大半の form が LLM ゼロで動く＝「生成精度の証明」を最速・最安・最も再現可能な形で行える（G1 先行の狙いと一致）。
- テンプレートは `packs/math/templates/` に versioned ID で登録（`lf_expr_two_points_v1`）。文面変更=新版=golden 再承認。

**7.2 TemplateContext（テンプレートが参照できるもの＝契約）**
- 公開: `given（表示形）/ context_slots / sub_questions[].label / sub_questions[].asked / steps[].narration`。
- **非公開: answer・srepr・params**——テンプレートから答えが構文的に書けない＝Q5 を構造で防ぐ。
- 整形フィルタは登録制: `num`（負数括弧）/ `frac`（既約・帯分数禁止）/ `pt`（座標表記）/ `unit`（単位付与）。小問は小問別テンプレート（`prompt_text` を小問ごとに生成）。

**7.3 explanation（解説）の M0 方式**
- steps の `narration + result_display` を接続詞テンプレートで結合する**決定論生成**（LLM 不使用）。要件 §4.2「steps に忠実な翻訳」の最小実装。T3 セルの解説 LLM 化は M1（ゲート付き）。

**7.4 ヒント**: `hints: [steps_prefix]` = steps の narration を前から k 個開示（k=1..len-1）。steps<2 になり得るレベルはテンプレ定義ヒント必須（lint R7）。全ヒントは Q5 leak ゲートを通る。

**7.5 G-GND（grounding・全 tier 必須）**
- 検査: given の全表示値が problem_text に出現・小問数一致。**T1 にも必須適用**（テンプレートのラベリングミス＝「傾きを切片と書く」類を検出する唯一の決定論ゲート）。T3 はさらに捏造禁止・忠実性検査を追加（旧 G-T3 を G-GND[全tier]＋G-T3[T3のみ] に分割）。

---

## 8. 検証ゲートと評価プログラム

### 8.1 静的検査（コミット時・CI: 秒オーダー）

| ツール | 内容 |
|---|---|
| `spec_lint` | §4.3 R1〜R5。全 FamilySpec を検査 |
| `curriculum_lint` | 概念/要因/戻り先座標の参照整合・DAG 非循環 |
| import-linter / ruff / mypy --strict | 依存方向（§3）・乱数規律（§5.3）・型 |

### 8.2 動的ゲート（generate 内; §5 の run_gates）

| ゲート | 段 | 検査 | 要件 |
|---|---|---|---|
| G-SIG | mr | MR.signature == spec.signature | H2 |
| G-FP | mr | 計算指紋 fp の安定性（同一署名⇔同一 fp。§4.4） | Q3/H2 |
| G-Q1 | mr | double-solve 一致（form 別水準 §6.2: srepr／fact_id／特徴点集合） | Q1 |
| G-Q2 | mr | frame 適合（given/asked が語彙内・visual が許容内） | Q2 |
| G-Q7 | mr | concept/cause タグ非空・実在。**G-Q7r**: remedial 時は解決先の concept_tags ⊇ 要因の target_concepts | Q7/F-7 |
| G-Q5t | text | 漏洩: answer 由来の値が本文・ヒントに**解答として**出ない。除外規則=given 由来の数値・式中係数・軸目盛（whitelist は MR.given から機械構築） | Q5 |
| G-GND | text | grounding（**全 tier 必須**）: given の全表示値が本文に出現・小問数一致 | Q4/Q6 |
| G-T3 | text | T3 のみ追加: 捏造禁止・忠実性（既存資産の移設） | Q4/Q6 |
| G-Q5v | visual | SVG 内テキスト ⊆ visual_plan.labels ＋ 幾何的リーク規則（§6.4） | Q5 |
| G-STY | text | スタイル lint: 通貨=円・離散量に分数禁止・敬体統一 等（登録制） | Q6(決定論分) |

### 8.3 評価プログラム（`eval/` — すべて CLI・JSON レポート・終了コードで CI 連携）

```
eval/coverage_scan.py   : capabilities 全セル × S seeds を生成。生成不能0・ゲート素通り0 を検証（N-5）
                          → nightly CI。レポート: セル×合否×失敗ゲート内訳
eval/dup_rate.py        : セルごとに 100 seeds → dup_key 衝突率 ≤ 0.20（D-1 仮値）。
                          fp ベースの第2系統で「別署名を貼った実質同一構造」も測定（§4.4）
eval/level_sep.py       : family ごとに (a)レベル間署名相異[静的] (b)署名間の fp 相異[必須] (c)宣言メトリクスの単調性[任意]
eval/retry_stats.py     : bounded_retry 発動率 ≤ 5%／構成失敗の分布
eval/audit_runner.py    : Q4/Q6 の LLM 監査（V3）。セルごとに n=3 サンプル → ルーブリック
                          （題材忠実性: input_spec の desc/example と照合／自然さ 5段階）
                          → JSONL、seed 付きで再現可能。リリース前ゲート（PR ごとには走らせない）
eval/cost_meter.py      : tier 別 LLM トークン→円換算。1問コストの実測（N-3, D-1）
eval/dashboard.py       : 全セルの DoD 状態を1枚の HTML に（未着手/制作中/golden待ち/合格）— H6
```

### 8.4 CI マトリクス

| タイミング | 実行 |
|---|---|
| PR | 静的検査（8.1）＋ unit ＋ 変更 family の golden ＋ 変更 family の smoke（全level×20seed×全ゲート） |
| nightly | coverage_scan（全セル×5seed）＋ dup_rate ＋ retry_stats ＋ cost_meter |
| リリース（M節目） | audit_runner 全セル ＋ dup_rate 100seed 完全版 |

---

## 9. テスト戦略（`engine_tests/`）

### 9.1 種別と置き場所

| 種別 | 対象 | 例 |
|---|---|---|
| unit | core の各機構・recipe・checker | 下記 9.2 |
| **golden** | セルごとの固定 seed スナップショット | seed={1,2,3} の Problem 全文（text/svg/answers/hints/meta）を YAML 保存。**承認 = 制作フローの一部**（§10）。差分= 再承認要求 |
| property | recipe の不変条件 | 200 seeds: params∈domain・double-solve 一致・dup_key 分布 |
| contract | API スキーマ・Unsupported 全コード・capabilities 整合 | capabilities の全セルが generate 成功／未実装セルが not_implemented |
| integration | 採点エンジンとの結合（D-2） | steps 粒度のフィクスチャ交換テスト（舛田側リポジトリと共有する JSON フィクスチャ） |

### 9.2 テストコード例（実装時はこの粒度で書く）

```python
# engine_tests/unit/test_double_solve.py
@pytest.mark.parametrize("seed", range(200))
def test_linear_from_two_points_double_solve(seed):
    ctx = make_ctx("math.g2_l25.find_value", level=3)
    mr = REGISTRY.recipe(ctx.spec.recipe).construct(ctx, derive_rng(ctx.family, 3, seed))
    sol = SOLVERS.linear_expr_from_points(mr.params["pts"])   # 独立再計算
    assert sol.answer_srepr == mr.sub_questions[0].answer_srepr

# engine_tests/unit/test_frame_conformance.py
def test_calculation_frame_forbids_visual():
    with pytest.raises(FrameViolation):
        build_mr(..., form="calculation", visual_plan=some_plan)   # 型レベルで作れないことの回帰

# engine_tests/contract/test_unsupported.py
def test_unknown_form_is_rejected_not_substituted():
    res = generate(GenerateRequest(subject="math", unit="g2_l25", form="proof", level=2))
    assert isinstance(res, Unsupported) and res.code == "form_not_supported"
```

**テストが守る不変条件の一覧**（このリストがテスト実装のチェックリスト）:
F-2 再現／F-3 重複率（dup_key・fp の2系統）／F-5 明示拒否（**全** Unsupported コードの発火テスト）／F-9 部品分離（hints・problem_text に answer 由来文字列が不在）／F-16 図の form 従属・whitelist・幾何規則／N-4 モノクロ印刷で情報が保たれる／Q1 double-solve（form 別水準 §6.2）／Q2 frame 語彙／Q3 署名相異＋fp 接地（G-FP）／Q4 G-GND（**T1 含む全 tier**）／Q7 タグ実在＋G-Q7r（remedial 一致）／variant A・avoid の有界性（枯渇→supply_exhausted）／RNG 規律 ruff ルール自体の fail テスト／API フィールド名の要件 §4.2 一致（contract）。

---

## 10. セル制作ワークフロー — H6 の解決（約1,000セルのスケール手段）

```
tools/spec draft <unit> <form>     # input_spec のセル（desc/example/market_ref）と登録済み
                                   # recipe/template 一覧を材料に、LLM が FamilySpec を下書き
tools/spec preview <family> [--seeds 5]
                                   # 全レベル×5seed の問題を1枚の HTML に描画（文+図+答+ヒント）
                                   # → 人間（教育者含む）がここで検収する。過去に無かった高速フィードバック
tools/spec check <family>          # spec_lint + smoke(全level×20seed×全ゲート) + dup_rate(簡易)
tools/spec approve <family>        # golden(seed 1..3) を生成し承認保存 → コミット可能に
```

**セルの Definition of Done（機械判定・dashboard 表示）**:
`schema✓ → lint✓ → smoke✓ → preview検収✓（承認記録） → golden✓ → dup_rate✓ → level_sep✓ →（バッチで）audit✓`

**golden・承認の運用**:
- `spec approve` は `curriculum/math/families/<family>.approval.yaml`（承認者・日時・preview 内容ハッシュ）を書き、golden は `engine_tests/golden/<family>/seed_N.yaml`（seed 1..3 の Problem 全文: text/svg/answers/hints/meta）に保存。
- preview HTML は **source_desc（セル定義）と生成物を併記**し、**同 family の全レベルを並置表示**する（難易度の壁の検収は最終的に人の目——見せ方を強制する）。非エンジニア（教育者）がブラウザだけで検収できる。
- **RNG 消費順は契約**: recipe 内の draw 順の変更は breaking change であり、当該 family の golden 全再承認を要する（`spec approve --diff` が新旧を並置）。テンプレ版数アップも同様。

新しい構造が必要なセル（既存 recipe で書けない）だけが pack への**コード追加**になる。追加は recipe/solver/template 単位＝ Open-Closed（F-19）で、既存スペックの diff は 0 行。

---

## 11. M0 実装計画（金の縦串・〜2026/08 上旬）

前提決定（D-4）: 縦串 = **1 lesson＋その remedial 戻り先 1〜2 lesson（計10セル前後）**に絞る。クラスタ全体（例: g2 一次関数 11 lesson・38セル）は M1 の初手であって M0 ではない——「1つの完全な見本」（要件 §10 の規律）と recipe 2〜4本の見積もりに整合する規模はこれ。**word_problem セルを含まない構成を優先**（M0 は T1 のみのため。含める場合は要件 M0 の Q4/Q6 を「V4=preview 検収で暫定合格・V3 監査水準は M1」と明文改訂した上で行う——暗黙の緩和はしない）。推奨: **g2_l25（2点から1次関数の式）＋戻り先 g2_l24・g1_l36**。

| # | タスク | 内容 | 完了条件（機械検証） | 依存 |
|---|---|---|---|---|
| 0 | 本書確定 | ユーザーレビュー・D-2 暫定粒度と D-4 の決定 | 本書 v1.0 確定コミット | — |
| 1 | core 骨格 | contracts / rng / registry / Unsupported / CellContext | unit テスト green・mypy strict 通過 | 0 |
| 2 | spec 基盤 | FamilySpec スキーマ・ローダ・spec_lint | lint の R1〜R5 各々に fail テストがある | 1 |
| 3 | curriculum 変換 | input_spec_2026-07-08.json → units.yaml 変換スクリプト（単元・概念初版・誤答要因は縦串単元のみ手書き） | curriculum_lint green・縦串単元の要因→戻り先が引ける | 2 |
| 4 | パイプライン | pipeline / gates 枠組み / derive_rng / T1 レンダラ | contract テスト（Unsupported 全コード）green | 1,2 |
| 5 | 数学パック最小 | frames(7型宣言・実装は縦串分)・solver 移設（縦串に必要な 3〜5 verb）・recipe 2〜4 本・T1 テンプレ | double-solve property テスト 200seed green | 4 |
| 6 | ゲート実装 | G-SIG/Q1/Q2/Q7/Q5t/STY（T3 系は M1） | ゲートごとに「わざと壊す」fail テスト | 5 |
| 7 | 制作ツール | spec preview / check / approve・golden 機構（check は簡易 dup_rate を内蔵） | 縦串 1 セルを preview→approve できる | 6 |
| 8 | 図（縦串分） | visuals 移設＋whitelist＋幾何的リーク規則＋モノクロ検査（find_value/graph_table 分）。**縦串制作より先**（縦串の DoD が図を要求するため） | G-Q5v・幾何規則の fail テスト・モノクロ checker green | 6 |
| 9 | **縦串制作** | 縦串（1 lesson＋戻り先・約10セル）の全 form×level×purpose(base/remedial) 制作＋curriculum の誤答要因対応表 | **全セル DoD**（§10）＋ **remedial DoD**（§5.2）＝ coverage_scan green | 7,8 |
| 10 | eval 一式 | coverage_scan / dup_rate（2系統） / level_sep（fp 必須） / retry_stats。dashboard は `spec check` の一覧出力で代替（HTML 化は M1） | nightly CI が回りレポートが出る | 9 |
| — | **M1 へ送る** | FastAPI ラッパ／採点フィクスチャの実装（**D-2 のスキーマ合意だけは M0 中に文書で行う**）／T2・T3／dashboard HTML／プール（Supplier 差し込み） | — | — |

**M0 出口 = 要件 §10 M0 DoD**: 縦串の全セルが Q ゲート合格（Q4/Q6 は V4=preview 検収の暫定合格・V3 監査水準は M1——要件 §10 M0 行に明記済み）・F-1/2/3/5/9 動作・`spec check` 一覧で全セル緑。
**タスク1〜7 は極力並行**（1-2, 4 は 1 の後すぐ分岐可）。設計の未定義を実装中に発見したら、コードでなく**本書を先に直す**（§0）。

---

## 12. 既存資産の移設マップ

| 旧（apps/api） | 新 | 方法 |
|---|---|---|
| verb 33種（SymPy 演算） | `packs/math/solvers/` | 署名を `Solution(answer_srepr, steps)` に揃えて移設。縦串に要る分から |
| atom 21種 | `packs/math/parts/` | recipe が使う値オブジェクトとして（タグ選択機構は recipe 内の domain 記法に置換） |
| ゲート（leak/grounding/is_clean/退化） | `core/verify/`・G-T3 | ロジック流用・枠組みは新 |
| 翻訳プロンプト（忠実性ブロック・few-shot） | `core/render/t3_translate.py` | M1 で移設 |
| SVG renderer 群 | `packs/math/visuals/` | whitelist 方式を被せて移設 |
| input_spec_2026-07-08.json | `curriculum/math/units.yaml`＋families の下書き材料 | タスク3 の変換スクリプト。**正の分界（N-6）**: 変換で生成される部分の正=元 JSON／拡張部分（知識グラフ・誤答要因・fact テーブル）の正=units.yaml（二重編集の禁止） |
| mapping.json / 27 blueprint | 使わない（参照資料） | 能力の再実装は recipe 単位で必要分のみ |
| 旧 pytest 465 | そのまま維持 | 旧系を壊さない監視として。新系は engine_tests/ |

---

## 13. リスクと未決依存

| リスク | 兆候 | 手当て |
|---|---|---|
| YAML スペックの表現力不足で recipe が乱造される | 1セル=1recipe 化（再利用ゼロ） | recipe 追加 PR に「既存 recipe で書けない理由」欄を必須化。M0 終了時に recipe 数/セル数比をレビュー（目標 ≤ 0.3） |
| 縦串単元の選定遅れ | タスク8 に入れない | D-4 を本書レビューと同時に決める |
| 採点粒度の手戻り | D-2 合意が M0 後にずれる | §4.2 の暫定粒度で進め、steps は追加分解可能な構造（op 単位）にしておく |
| T1 の文が硬い | preview 検収での指摘多発 | M1 の T2（磨き）で吸収。M0 では「不自然でないこと」を合格線に（Q6 満点は M1 以降） |
| 監査コスト | audit_runner の LLM 費 | セル当たり n=3・リリース時のみ。nightly は決定論 eval だけ |

---

*Education OS 問題供給エンジン 実装設計書 v1.1（ドラフト・2026-07-11）。要件定義書 v2.1 の F/Q/N/D と §1 の H1〜H8 を参照キーとして実装・レビューを行うこと。v1.1: 実装者視点レビュー（重要度高10件: 記入例の題材ズレ是正・ドメイン記法DSL定義・frame語彙実列挙・TemplateContext/explanation/context_slots・remedial解決§5.2・計算指紋fp・AnswerPayload直和とform別Q1水準・M0 DoD検証水準の明文化・R6題材ズレ静的検出・M0スコープ/タスク再編、ほか中12件）を反映。*
