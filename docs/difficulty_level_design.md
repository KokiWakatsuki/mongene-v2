# 難易度レベル制 設計書

## 1. 背景と目的

### 根本的な問題

現在の難易度システムは `target_difficulty`（1〜100 の**連続値**）で管理されている。しかし、**問題の難易度は本質的に離散値**である。

ある（単元, 問題形式）の組み合わせで表現できる難易度のパターンは有限個しかない。たとえば「加法 × 計算問題」では：

```
表現できるパターン:
  パターンA: 同符号2項の加法
  パターンB: 異符号2項の加法
  パターンC: 異符号3項の加法

表現できないもの:
  「難易度28」「難易度30」の違い → どちらも同じパターンBに落ちる
```

連続値（1〜100）を使うと、**存在しない難易度を要求できてしまう**。結果として同じ問題が異なる難易度として出力されたり、意図しない範囲クランプが起きる。

LLM による事後評価（378 グループ）でもこれが確認された。

- 難易度の厳密な順序（Lv1 < Lv2 < Lv3）の達成率：**3.4%**（13/378）
- 主な失敗：全て同値 126件、順序逆転 33件

### 目的

現在の連続値スケールを**離散値（レベル制）**に変更する。

- 各（単元, 問題形式）が表現できるパターンの数だけレベルを定義する
- ユーザーは「存在するレベル」しか指定できない
- レベルごとに Blueprint/Atom/Verb の設定が対応するため、異なるレベルは必ず異なる問題になる
- 他教科への拡張でも同じ仕組みが使える（表現パターンを定義すればよい）

---

## 2. 新設計の概要

### コアコンセプト：難易度レベル制

```
現在:  target_difficulty（数値）→ delta_factors → Atom パラメータ（逆算）
新設:  level（Lv1〜LvN）→ 表現定義（直接参照）→ Atom/Blueprint 設定
```

各（lesson_id, form）の組み合わせに対して、`Lv1` から `LvN` まで **離散的な難易度レベル** を定義する。各レベルは、その難易度を実現するための Blueprint/Atom/Verb 設定を直接持つ。

### レベル定義の例

```json
"g1_l3": {
  "difficulty_levels": {
    "calculation": [
      {
        "lv": 1,
        "description": "同符号2項の加法（正の数のみ）",
        "atom_constraints": {
          "NumberAtom": {"allow_negative": false, "max_terms": 2, "max_value": 20}
        }
      },
      {
        "lv": 2,
        "description": "異符号2項の加法",
        "atom_constraints": {
          "NumberAtom": {"allow_negative": true, "max_terms": 2, "max_value": 50}
        }
      },
      {
        "lv": 3,
        "description": "異符号3項の加法",
        "atom_constraints": {
          "NumberAtom": {"allow_negative": true, "max_terms": 3, "max_value": 50}
        }
      }
    ]
  }
}
```

---

## 3. データモデルの変更

### 3-1. mapping.json への追加フィールド

```
既存フィールド（維持）:
  title, grade, large_unit, domain
  execute_blueprint, execute_blueprints, execute_blueprint_by_form
  required_tags, atom_constraints（ベース設定として残す）
  y_base（カリキュラム位置として残す ← 後述）

新規フィールド:
  difficulty_levels: {
    "<form>": [
      { lv, description, atom_constraints?, blueprint_override?, verb_config? }
    ]
  }
```

#### レベル定義フィールドの仕様

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `lv` | ✓ | 1始まりの整数。小さいほど易しい |
| `description` | ✓ | 人間が読める難易度の説明（LLM 生成・人間レビュー） |
| `atom_constraints` | | ベース設定へのパッチ（差分のみ記述） |
| `blueprint_override` | | このレベルで使用する Blueprint ID（省略時はベース設定を使用） |
| `verb_config` | | Verb への追加パラメータ |

> **設計方針**：`atom_constraints` は**差分（patch）**として扱う。ベース設定（mapping.json の既存 `atom_constraints`）に上書きマージされる。これにより全フィールドの重複定義を避ける。

### 3-2. GenerationRequest の変更

```python
# 現在
@dataclass
class GenerationRequest:
    target_difficulty: int   ← 廃止
    problem_form: str
    lesson_id: str

# 新設
@dataclass
class GenerationRequest:
    target_level: int        ← 新設（1〜N）
    problem_form: str
    lesson_id: str
```

### 3-3. MiddleRepresentation の変更

```python
# 現在
difficulty_score: float   ← 1〜100 の連続値

# 新設
difficulty_level: int     ← Lv番号（1〜N）
difficulty_score: float   ← UI表示用に導出（後述）。生成には使用しない
```

---

## 4. システムコンポーネントの変更

### 4-1. DifficultyReconciler（大幅縮小）

現在の役割：`target_difficulty → raw_score → delta_factors` への逆算

新しい役割：`target_level → difficulty_levels[form][lv]` の参照

```python
def get_level_config(
    lesson_mapping: dict,
    form: str,
    level: int,
) -> dict:
    """mapping.json から指定レベルの設定を返す。"""
    levels = lesson_mapping.get("difficulty_levels", {}).get(form, [])
    for lv_def in levels:
        if lv_def["lv"] == level:
            return lv_def
    raise NoCompatibleBlueprintError(f"{form} Lv{level} は定義されていません")
```

`delta_factors`（digit_penalty, step_depth, hint_reduction など）は**廃止**。

### 4-2. BlueprintRunner の変更

```python
# 現在：reconcile_difficulty で delta_factors を計算し Atom パラメータに反映
plan = reconcile_difficulty(target=request.target_difficulty, ...)
factors = plan.delta_factors
# ... digit_penalty を max_value に反映 ...
# ... step_depth を subquestion_strategy に反映 ...

# 新設：レベル設定を直接 atom_constraints にマージ
lv_config = get_level_config(mapping, request.problem_form, request.target_level)
atom_constraints = _merge_constraints(
    base=mapping.get("atom_constraints", {}),
    patch=lv_config.get("atom_constraints", {}),
)
```

### 4-3. GenerationRequest を生成するスクリプト

```python
# 現在（generate_1134_problems.py）
targets = _adaptive_targets(y_base, form)
# → {"min": [10, 8, 6], "mid": [18, 15, 12], "max": [27, 24, 21]}

# 新設
levels = get_available_levels(mapping, lesson_id, form)
# → [1, 2, 3]（定義されたレベル番号の一覧）
```

---

## 5. y_base の位置づけ（変更）

### 現在

`y_base` は生成ロジック（形式範囲の計算・delta_factors の基準）に使用されている。

### 新設

`y_base` は生成ロジックから**切り離し**、以下の用途のみに使用する。

| 用途 | 説明 |
|------|------|
| UI 表示用スコア導出 | `display_score = y_base + (lv / N) * form_range` |
| 単元間の難易度比較 | 「この問題は全体でどのあたりか」の表示 |
| フォールバック（後述） | `difficulty_levels` 未定義レッスンの暫定動作 |

---

## 6. レベル数について

### 設計方針

生成システムは `target_level`（Lv1〜LvN）を受け取り、指定されたレベルの問題を1問生成する。**min/mid/max という概念は生成システムには存在しない。**

min/mid/max は品質評価のために便宜的に使った呼び名であり（例：Lv1 を「min」、LvN を「max」と呼んで順序を確認する）、生成システムの制約ではない。

```
生成 API:  (lesson_id, form, target_level=2) → 問題
品質評価:  Lv1/中間Lv/LvN を生成して LLM に難易度順序を確認させる
           → これは評価手法の話であり、生成システムの設計制約ではない
```

レベル数 N は (lesson, form) ごとに異なってよい。N=2 のレッスンがあっても競合しない。

---

## 7. レベル定義の生成プロセス（LLM）

### 目的

378 通り（lesson, form）のレベル定義を LLM で自動生成し、人間がレビューする。

### LLM への入力

```
1. レッスン情報
   - lesson_id, title, large_unit, grade
   - supported_forms

2. 使用する Blueprint の仕様
   - blueprint_id, 制御可能な atom_constraints フィールド一覧

3. 使用する Atom の制御可能パラメータ
   - NumberAtom: allow_negative, max_value, max_terms, force_fraction ...
   - PolygonAtom: n_sides, polygon_type ...
   - など

4. 制約条件
   - この form（例: calculation）内で難易度を変える手段のみ提示すること
   - 他の form の特徴（文章題的要素など）を混入させないこと
   - 実装可能なパラメータのみ使用すること
```

### LLM の出力スキーマ

```json
{
  "lesson_id": "g1_l3",
  "form": "calculation",
  "levels": [
    {
      "lv": 1,
      "description": "...",
      "rationale": "なぜこれが Lv1 か（レビュー用）",
      "atom_constraints": { ... },
      "blueprint_override": null,
      "implementable": true,
      "implementation_note": ""
    }
  ],
  "unimplementable_reason": ""
}
```

`implementable: false` の場合：現在のシステムでは表現できないことを明示し、必要な拡張を `implementation_note` に記載。

### 人間レビューのフロー

```
LLM が 378 通りの定義を生成
    ↓
implementable: false の件をリストアップ → システム拡張の検討
    ↓
description / rationale を確認 → 教育的妥当性のチェック
    ↓
mapping.json に difficulty_levels として追加
```

---

## 8. Blueprint/Atom 仕様書の作成

### 課題（矛盾点②）

LLM がレベル定義を生成するには、各 Atom の制御可能パラメータを知る必要がある。現在この情報は Python コード（各 Atom クラスの `__init__` と `AtomConstraints`）に散在しており、LLM に渡せる形式がない。

### 必要な作業

各 Atom について以下を JSON/YAML で文書化する：

```json
{
  "atom": "NumberAtom",
  "controllable_params": {
    "allow_negative": {"type": "bool", "effect": "負の数を含むかどうか"},
    "max_value": {"type": "int", "effect": "数値の上限"},
    "max_terms": {"type": "int", "effect": "項の数の上限"},
    "force_fraction": {"type": "bool", "effect": "分数を強制するか"}
  }
}
```

これは **実装前に必要な前提作業**。

---

## 9. フォールバック（移行戦略）

既存レッスン（difficulty_levels 未定義）は現在の動作（y_base + delta_factors）で引き続き動作する。

```python
if "difficulty_levels" in mapping and form in mapping["difficulty_levels"]:
    # 新設計：レベル定義を使用
    lv_config = get_level_config(mapping, form, request.target_level)
    ...
else:
    # 旧設計：y_base + delta_factors（フォールバック）
    plan = reconcile_difficulty(target=request.target_difficulty, ...)
    ...
```

---

## 10. 未解決事項・要議論

| # | 課題 | 影響範囲 | 状態 |
|---|------|---------|------|
| ① | Atom 仕様書の作成（LLM 入力のため） | レベル定義生成の前提条件 | ✅ docs/atom_verb_spec.json |
| ② | `atom_constraints` の差分マージ仕様（深いネストの扱い） | BlueprintRunner | 未解決 |
| ③ | `max_terms` 等、現在 NumberAtom に存在しないパラメータの追加要否 | NumberAtom の拡張 | ✅ 不要（現行パラメータで十分） |
| ④ | `verb_config` の具体的な仕様（Verb が受け取れる追加パラメータ） | Verb 層の拡張 | ✅ atom_verb_spec.json に verb init_params を記載 |
| ⑤ | `difficulty_levels` 未定義 × `target_level` が指定された場合のエラー処理 | BlueprintRunner | 未解決 |

---

## 11. 入試対策問題の設計

### 位置づけ

既存レッスン（g1_l1〜g3_l60）は**単元別・概念習得**のための問題を生成する。
入試対策レッスン（exam_l1〜）は**複数単元融合・試験形式**の問題を生成する。

```
単元習得レッスン（LvN 到達）
       ↓ 前提
入試対策レッスン（複合問題）
```

### 入試対策レッスンの構造

```json
"exam_l1": {
  "title": "一次関数と図形の融合",
  "grade": 2,
  "large_unit": "入試対策",
  "domain": "入試対策",
  "required_tags": ["linear_function", "geometry"],
  "prerequisite_lessons": ["g2_l20", "g2_l21", "g1_l37"],
  "difficulty_levels": {
    "calculation": [
      {"lv": 1, "description": "交点座標を求める（連立方程式）"},
      {"lv": 2, "description": "三角形の面積を関数式から求める"},
      {"lv": 3, "description": "動点を含む面積変化の式を立てる"}
    ]
  }
}
```

### 既存レッスンとの違い

| | 既存レッスン | 入試対策レッスン |
|--|------------|----------------|
| 単元 | 単一 | 複数横断 |
| `required_tags` | 1〜2個 | 3個以上 |
| Blueprint | 単一 | FunctionGeometryFusion 等の複合 Blueprint |
| 前提 | なし | `prerequisite_lessons` で明示 |
| 難易度範囲 | 単元内で完結 | 全体的に高め（旧スケールで 75 相当〜） |

### 入試対策レッスンの洗い出し方針

実際の公立高校入試（都道府県別）の頻出パターンから逆引きで定義する。

```
頻出パターン例:
  - 一次関数と図形（面積・交点）
  - 二次関数と直線・放物線
  - 動点と面積の変化
  - 平行線と相似・合同の複合証明
  - 確率（樹形図・表）
  - 三平方定理と空間図形
  - データの活用（四分位・相関）
```

これらを `exam_l1〜` として定義する。レッスン数・問題タイプの詳細は別途決定。

---

## 12. 実装順序（案）

```
Phase 1: 前提作業 ✅ 完了 (2026-06-25)
  - ✅ Atom/Verb/Blueprint の制御可能パラメータを仕様書化 → docs/atom_verb_spec.json
      20 Atom / 13 Verb / 17 Blueprint のパラメータを網羅
  - ✅ NumberAtom 等の拡張要否を確認（現行パラメータで十分。max_terms は不要）

Phase 2: コア実装 ✅ 完了 (2026-06-25)
  - ✅ GenerationRequest に target_level を追加（target_difficulty と共存）
  - ✅ BlueprintRunner に新パスを追加（フォールバック維持）
  - ✅ get_level_config() 実装（blueprint_runner.py モジュールレベル）
  - ✅ atom_constraints 差分マージ実装（_merge_constraints: シャローマージ）
  - ✅ MiddleRepresentation に difficulty_level: Optional[int] を追加
  - ✅ ProblemGenerationRequest に target_level を追加、バリデーション追加
  - ✅ PrefetchCache キーに target_level を考慮
  - 253 テスト通過

Phase 3: レベル定義生成（既存 378 通り）
  - LLM で (lesson, form) ごとのレベル定義を生成
  - implementable: false の箇所を Atom 拡張で対応
  - mapping.json に difficulty_levels を追加

Phase 4: 入試対策レッスン定義
  - 頻出パターンから exam_l1〜 を洗い出し
  - mapping.json に追加
  - 必要な複合 Blueprint の実装・確認

Phase 5: 評価・検証
  - 新設計で問題再生成
  - LLM 難易度評価を再実行
  - 各レベルが異なる問題を生成できているか確認
```
