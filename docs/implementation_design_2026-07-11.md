# Education OS 問題供給エンジン 実装設計書 v1.0（ドラフト）

- 作成: 2026-07-11 ／ 対応要件: `docs/requirements_2026-07-11.html` v2.1（F/Q/N/D 番号は同書を参照）
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
| **H2** | 「難易度＝構造の段」「重複」「類題」の操作的定義がない | Lvが数値ジッターに退化・重複測定不能 | **構造シグネチャ（structure signature）**を一級市民に。Q3=レベル間で署名が異なる／重複=署名+正規化パラメータ一致／variant A=署名固定・B=署名固定文脈差替・C=署名変更概念固定、を**同一機構で**定義 | §4.4 |
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

class SubQuestionMR(BaseModel):
    label: str                       # "(1)"
    asked: str                       # 問う対象（frame語彙: "slope" 等）
    answer_srepr: str
    answer_display: str
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
    sub_questions: list[SubQuestionMR]
    visual_plan: VisualPlan | None   # frame が要求する場合のみ非None
    provenance: Provenance           # recipe名+版, spec版, git_commit

class Problem(BaseModel):           # API 出力（要件 §4.2 と一致）
    problem_ref: str                 # sha256(provenance + seed + render_keys)
    problem_text: str
    visual_svg: str | None
    sub_questions: list[SubQuestionOut]  # answer/steps/explanation/hints を分離部品で
    meta: Meta                       # 座標, purpose, seed, signature, concept/cause tags, 再現情報
```

**再現の定義（F-2, H8）**: `problem_ref` から MR は完全再構成できる（座標+seed+版）。テキストは render cache のキーが meta に入り、キャッシュ参照で同一文が返る。キャッシュ消失時は「MR は同一・文面は再翻訳」となることを仕様として明記（T1 はキャッシュ不要で完全決定論）。

### 4.3 FamilySpec（著作の単位・YAML）— H1 の解決

**1ファイル = 1 (unit × form)**。レベルはその中に列挙。**スペックに書けるのは「選択と参照と定数」だけ**で、ロジック（条件分岐・計算・ループ）は書けない。ロジックが必要になったら pack に recipe/checker を追加して名前で参照する（それが Open-Closed の追加単位）。

```yaml
# curriculum/math/families/g2_l25.find_value.yaml
family: math.g2_l25.find_value
form: find_value
concepts_default: [linear_function.expression]     # 全小問デフォルトの概念タグ
levels:
  "2":                                             # band絶対Lv（疎で良い）
    signature: lf_expr_from_slope_and_point        # ★family内で一意（§4.4）
    recipe: math.linear_from_slope_point           # ★登録済み構成関数の名前
    params:                                        # recipe への引数（定数のみ）
      slope_domain: {int_range: [-4, 4], exclude: [0]}
      point_domain: {lattice: {x: [-5, 5], y: [-8, 8]}}
    given: [slope, point]                          # frame 語彙（§6.3）で「与えるもの」
    asked: [expression]                            # 「問うもの」
    visual: none                                   # none | required | optional
    text: {tier: T1, template: lf_expr_slope_point_v1}
    hints: [steps_prefix]                          # ヒント生成方式（登録名）
    cause_tags: [lf.confused_with_proportional, lf.sign_error]
  "3":
    signature: lf_expr_from_two_points             # ★Lv2と構造が違う＝署名が違う
    recipe: math.linear_from_two_points
    params: { point_domain: {lattice: {x: [-6, 6], y: [-9, 9]}, distinct_x: true} }
    given: [point_a, point_b]
    asked: [expression]
    visual: optional
    text: {tier: T1, template: lf_expr_two_points_v1}
    hints: [steps_prefix]
    cause_tags: [lf.slope_formula_error]
remedial:                                          # この family が戻り先として使われる時の既定
  default_level: 1
```

`spec_lint`（§8.1）が強制する規則:
- R1: 未登録の recipe / template / checker 名 → エラー
- R2: 同一 family 内で signature 重複 → エラー（H2/Q3 の前提）
- R3: params に許されるのは JSON スカラー・配列・**ドメイン記法**（`int_range` 等の登録済み語彙）のみ
- R4: concepts / cause_tags は curriculum に実在する ID のみ
- R5: form と frame の整合（asked/given が frame 語彙に含まれる、visual が frame の許容と矛盾しない）

### 4.4 構造シグネチャ — H2 の解決（Q3・重複・類題の統一機構）

- **定義**: `signature` = 「問題の構造」の名前。同一署名 ⇔ given/asked の型・解法列・小問構成が同型。recipe が MR に刻印し、スペックの宣言と一致することをゲートが検証する。
- **正規化パラメータ**: recipe は `params` の**正規形**（順序・符号・スケールの正規化）を定義する。`dup_key = sha256(signature + normalize(params))`。
- これにより:
  - **Q3（難易度分離）** = family 内でレベル間の署名が相異（spec_lint R2 で静的保証）
  - **重複（F-3/D-1）** = dup_key 一致。重複率 = 100 seed 中の dup_key 衝突率
  - **variant A** = 同一署名・同一 recipe・パラメータ再抽選（dup_key が変わるまで）
  - **variant B** = 同一署名・文脈スロット（T1 テンプレートの題材変数）のみ差替
  - **variant C** = 同一 concepts・別署名（family 内の別レベル or 別 family から解決）
  - **avoid** = dup_key の除外リスト

---

## 5. コアパイプライン（`core/pipeline.py`）

```python
def generate(req: GenerateRequest) -> Problem | Unsupported:
    # 1) 解決: curriculum → family spec → level block。無ければ理由コードで拒否（F-5）
    ctx: CellContext = resolve(req)          # 失敗: unit_not_found / form_not_supported / ...
    # remedial は cause_id → curriculum の静的対応 → 別セルの ctx に解決してから同じ道を通る

    # 2) 乱数: これ以外の乱数源は全リポジトリで禁止（H8, ruff カスタムルールで検査）
    seed = req.seed if req.seed is not None else issue_seed()
    rng = derive_rng(ctx.family, ctx.level, seed)

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

- **CellContext** は resolve() だけが作れる不変オブジェクトで、`family / form / frame / level / purpose / spec / curriculum` を保持。**全下流関数の第一引数**（H7）。
- **capabilities()** = curriculum×families を走査し「スペックが存在し `spec check` 済み」のセル一覧を返す。`not_implemented` はここに出ないことで F-5/F-6 が整合。

### 5.3 乱数とキャッシュの規律（H8）

- `derive_rng(family, level, seed)` = SHA256 ベースの独立ストリーム。attempt が必要な場合は `rng.spawn(k)`。
- `random.*` / `numpy.random.*` の直接使用は ruff ルール（`engine/` 配下）で CI 禁止。
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
    a = rng.pick(domain_int(p["slope_domain"]))          # 傾き
    b = rng.pick(range(-8, 9))                           # 切片
    x1, x2 = rng.pick_distinct(domain(p["point_domain"], axis="x"), k=2)
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
- 旧 verb 33種をここへ移設（署名は `solve(*args) -> Solution(answer_srepr, steps)` に統一）。
- Q1 ゲート = 「recipe の意図した答え」と「solver の再計算」の srepr 一致。**LLM はこの経路に存在しない**（数学パックの V1 宣言）。

### 6.3 frame = form の実装（Q2 の機械化）

7型それぞれに Frame を定義（`packs/math/frames.py`）。Frame は**語彙と制約**を宣言し、ゲートが MR を検査する:

| form | given に許されるもの | asked | visual | 備考 |
|---|---|---|---|---|
| calculation | 式そのもの | 計算結果 | **禁止** | 立式なし |
| knowledge | 用語・定義の文脈 | 用語/真偽/選択 | 禁止（M0） | |
| find_value | 図形/条件/点/式の係数 | 値・式 | optional/required | 立式あり・場面は数学的 |
| construction | 作図条件 | 作図手順+模範図 | required | M2 |
| graph_table | データ/式 | グラフ・表を「かく/読む」 | required | 模範解答図+特徴点（要件D-3） |
| proof | 前提と結論 | 証明記述 | optional | |
| word_problem | 現実場面（T3必須） | 立式+解 | optional | 2階層（大枠+小問） |

Frame 適合ゲート（Q2）= MR.given/asked のキーが frame 語彙に含まれ、visual 宣言が frame の許容内であること。**「calculation なのに図が付く」は型レベルで作れない**（frame.visual=forbidden なら render_visual は呼ばれない）。

### 6.4 visual（図）

- 旧 renderer（SVG/2D/3D/グラフ）を `packs/math/visuals/` へ移設。
- **ラベル whitelist 方式**（Q5, 旧 builder.py:855 の答え漏洩の恒久対策）: 図に描いてよい文字列は `visual_plan.labels` に**明示列挙されたもののみ**。`visual_plan` は MR.given からしか作れないヘルパで構築（asked 系の値はコンパイル時に入らない）。ゲートは SVG 内テキストが whitelist の部分集合であることを検査。

---

## 7. テキストレンダリング3層 — H3 の解決

| 層 | 方式 | 対象 form（目安） | コスト/決定論 |
|---|---|---|---|
| **T1** | Jinja2 テンプレート＋整形フィルタ（分数・単位・敬体） | calculation, knowledge, find_value, graph_table, construction | ¥0・完全決定論 |
| **T2** | T1 出力を LLM で1回磨く。**数値・固有名詞の保存を diff ゲートで検証**、失敗時は T1 を出す | find_value の一部（M1〜） | 低・キャッシュ |
| **T3** | MR→LLM 翻訳（既存プロンプト資産を移設）。leak/grounding/忠実性ゲート必須 | word_problem, proof | 中・キャッシュ必須 |

- **M0 は T1 のみ実装**。これで縦串単元の大半の form が LLM ゼロで動く＝「生成精度の証明」を最速・最安・最も再現可能な形で行える（G1 先行の狙いと一致）。
- テンプレートは `packs/math/templates/` に versioned ID で登録（`lf_expr_two_points_v1`）。文面変更=新版=golden 再承認。
- **7.4 ヒント**: `hints: [steps_prefix]` = steps の narration を前から k 個開示する方式を既定とする（k=1..len-1）。テンプレ独自ヒントも登録可。全ヒントは Q5 leak ゲートを通る。

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
| G-Q1 | mr | double-solve 一致（srepr） | Q1 |
| G-Q2 | mr | frame 適合（given/asked/visual） | Q2 |
| G-Q7 | mr | concept/cause タグ非空・実在 | Q7 |
| G-Q5t | text | 漏洩: answer_display/srepr 由来の値が本文・ヒントに**解答として**出ない。除外規則=given 由来の数値・式中係数・軸目盛（whitelist は MR.given から機械構築） | Q5 |
| G-T3 | text | T3のみ: grounding（given の数値が本文に全部ある）・小問数一致・捏造禁止（既存資産の移設） | Q4/Q6 |
| G-Q5v | visual | SVG 内テキスト ⊆ visual_plan.labels | Q5 |
| G-STY | text | スタイル lint: 通貨=円・離散量に分数禁止・敬体統一 等（登録制） | Q6(決定論分) |

### 8.3 評価プログラム（`eval/` — すべて CLI・JSON レポート・終了コードで CI 連携）

```
eval/coverage_scan.py   : capabilities 全セル × S seeds を生成。生成不能0・ゲート素通り0 を検証（N-5）
                          → nightly CI。レポート: セル×合否×失敗ゲート内訳
eval/dup_rate.py        : セルごとに 100 seeds → dup_key 衝突率 ≤ 0.20（D-1 仮値）
eval/level_sep.py       : family ごとにレベル間署名相異（静的）＋ per-level パラメータ規模の単調性（宣言メトリクスがある場合）
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
F-2 再現／F-3 重複率／F-5 明示拒否／F-9 部品分離（hints に answer 文字列が不在）／F-16 図の form 従属・whitelist／Q1 double-solve／Q2 frame／Q3 署名相異／Q7 タグ実在。

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

新しい構造が必要なセル（既存 recipe で書けない）だけが pack への**コード追加**になる。追加は recipe/solver/template 単位＝ Open-Closed（F-19）で、既存スペックの diff は 0 行。

---

## 11. M0 実装計画（金の縦串・〜2026/08 上旬）

前提決定: 縦串単元 = **D-4 で確定させる（推奨: g2 一次関数クラスタ or g1 一次方程式クラスタ）**。以下は「一次関数」を仮置き。

| # | タスク | 内容 | 完了条件（機械検証） | 依存 |
|---|---|---|---|---|
| 0 | 本書確定 | ユーザーレビュー・D-2 暫定粒度と D-4 の決定 | 本書 v1.0 確定コミット | — |
| 1 | core 骨格 | contracts / rng / registry / Unsupported / CellContext | unit テスト green・mypy strict 通過 | 0 |
| 2 | spec 基盤 | FamilySpec スキーマ・ローダ・spec_lint | lint の R1〜R5 各々に fail テストがある | 1 |
| 3 | curriculum 変換 | input_spec_2026-07-08.json → units.yaml 変換スクリプト（単元・概念初版・誤答要因は縦串単元のみ手書き） | curriculum_lint green・縦串単元の要因→戻り先が引ける | 2 |
| 4 | パイプライン | pipeline / gates 枠組み / derive_rng / T1 レンダラ | contract テスト（Unsupported 全コード）green | 1,2 |
| 5 | 数学パック最小 | frames(7型宣言・実装は縦串分)・solver 移設（縦串に必要な 3〜5 verb）・recipe 2〜4 本・T1 テンプレ | double-solve property テスト 200seed green | 4 |
| 6 | ゲート実装 | G-SIG/Q1/Q2/Q7/Q5t/STY（T3 系は M1） | ゲートごとに「わざと壊す」fail テスト | 5 |
| 7 | 制作ツール | spec preview / check / approve・golden 機構 | 縦串 1 セルを preview→approve できる | 6 |
| 8 | **縦串制作** | 縦串単元の全 form×全 level×purpose(base/remedial) のスペック制作 | **全セル DoD 達成**（§10）＝ coverage_scan green | 7 |
| 9 | eval 一式 | coverage_scan / dup_rate / level_sep / retry_stats / dashboard | nightly CI が回りレポートが出る | 8 |
| 10 | 図（縦串分） | visuals 移設＋whitelist 方式（find_value/graph_table 分） | G-Q5v fail テスト・golden に SVG 含む | 8 |
| 11 | 採点フィクスチャ | steps 粒度の JSON フィクスチャを舛田側と交換 | integration テスト green（D-2 合意反映） | 8 |
| 12 | API ラッパ | FastAPI /generate /capabilities | contract テスト green | 8 |

**M0 出口 = 要件 §10 M0 DoD**: 縦串単元の全セルが Q ゲート合格・F-1/2/3/5/9 動作・dashboard で全セル緑。
**T3（word_problem）が縦串単元に含まれる場合**: M0 では T1 の暫定文（数学的場面文）で出し、T3 化は M1 冒頭タスクとする（LLM 依存を M0 のクリティカルパスから外す）。

---

## 12. 既存資産の移設マップ

| 旧（apps/api） | 新 | 方法 |
|---|---|---|
| verb 33種（SymPy 演算） | `packs/math/solvers/` | 署名を `Solution(answer_srepr, steps)` に揃えて移設。縦串に要る分から |
| atom 21種 | `packs/math/parts/` | recipe が使う値オブジェクトとして（タグ選択機構は recipe 内の domain 記法に置換） |
| ゲート（leak/grounding/is_clean/退化） | `core/verify/`・G-T3 | ロジック流用・枠組みは新 |
| 翻訳プロンプト（忠実性ブロック・few-shot） | `core/render/t3_translate.py` | M1 で移設 |
| SVG renderer 群 | `packs/math/visuals/` | whitelist 方式を被せて移設 |
| input_spec_2026-07-08.json | `curriculum/math/units.yaml`＋families の下書き材料 | タスク3 の変換スクリプト（元 JSON は正として維持） |
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

*Education OS 問題供給エンジン 実装設計書 v1.0（ドラフト・2026-07-11）。要件定義書 v2.1 の F/Q/N/D と §1 の H1〜H8 を参照キーとして実装・レビューを行うこと。*
