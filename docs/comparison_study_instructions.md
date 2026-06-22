# 比較調査指示書：mongene-v2 生成問題 vs 実際の教材

## 調査の目的

`mongene-v2`（中学数学問題自動生成システム）が生成する問題が、  
実際の教材・問題集と比較して**妥当な問題**を生成しているかを調査する。

評価観点：
1. **内容の妥当性**：その単元で本来出るべき概念・操作が問題に含まれているか
2. **難易度の妥当性**：指定難易度に対して問題の複雑さが一致しているか（できる範囲で）
3. **参考サイトとの類似度**：外観・形式・問題パターンが教材と似ているか

---

## システムの前提知識

### 起動方法
```bash
cd /Users/koki/workspace/mongene-v2
make up   # サーバ起動
make down # サーバ停止
```

### API エンドポイント

**中間表現確認（LLM なし・即座に返却）**
```bash
POST http://127.0.0.1:8000/problems/inspect
{
  "curriculum": {"grade": 3, "lesson_ids": ["g3_l1"]},
  "problem_form": "calculation",
  "target_difficulty": 35,
  "unlearned_lesson_ids": []
}
```

**問題生成（実 LLM 使用・30〜60秒）**
```bash
POST http://127.0.0.1:8000/problems/generate
{同上}
```

**難易度レンジ確認**
```bash
GET http://127.0.0.1:8000/problems/difficulty-range/{lesson_id}?form={form}
```

**単元一覧**
```bash
GET http://127.0.0.1:8000/problems/lessons
```

### lesson_id の形式
`g{grade}_l{lesson_number}` 例: `g3_l1`, `g1_l5`

### 問題形式（5種類）
| form | 定義 | Raw Score ボーナス |
|:---|:---|---:|
| knowledge | 定義・用語・条件の確認（計算なし） | -100 |
| calculation | 式・数値が与えられ計算するだけ | 0 |
| visual | 図・グラフから情報を読み取って立式 | +200 |
| word_problem | 自然言語から変数抽出・立式 | +400 |
| proof | 論理構成を記述 | +800 |

---

## 調査対象（23 大単元 × 形式 × 難易度3段階）

**大単元一覧と利用可能な形式・難易度レンジ**

| 学年 | 大単元 | 形式 | 難易度レンジ（最小-最大） |
|:---|:---|:---|:---|
| 中1 | 正の数・負の数 | calculation, knowledge | calc: 1-27, know: 1-25 |
| 中1 | 文字の式 | calculation, knowledge | calc: 2-28, know: 1-26 |
| 中1 | 一次方程式 | calculation, visual, word_problem | calc: 5-31, vis: 10-36, wp: 14-40 |
| 中1 | 比例と反比例 | visual, word_problem | vis: 11-37, wp: 15-41 |
| 中1 | 平面図形 | visual, word_problem | vis: 12-38, wp: 16-42 |
| 中1 | 空間図形 | visual, word_problem | vis: 13-39, wp: 17-43 |
| 中1 | データの分布と統計的探究 | calculation, knowledge, word_problem | calc: 3-29, wp: 12-38 |
| 中1 | ことがらの起こりやすさ | calculation, knowledge, word_problem | calc: 3-29, wp: 12-38 |
| 中2 | 式の計算 | calculation | calc: 9-35 |
| 中2 | 連立方程式 | calculation, knowledge, word_problem | calc: 10-36, wp: 19-45 |
| 中2 | 1次関数 | calculation, visual, word_problem | calc: 12-38, vis: 17-43, wp: 21-47 |
| 中2 | 平行と合同 | proof, visual | proof: 29-55, vis: 15-41 |
| 中2 | 三角形と四角形 | proof, visual, word_problem | proof: 31-57, wp: 21-47 |
| 中2 | 確率 | calculation, knowledge, word_problem | calc: 9-35, wp: 18-44 |
| 中2 | データの分布の比較 | calculation, knowledge, visual, word_problem | calc: 7-33, vis: 12-38 |
| 中3 | 多項式 | calculation | calc: 14-40 |
| 中3 | 平方根 | calculation | calc: 14-40 |
| 中3 | 2次方程式 | calculation, knowledge, word_problem | calc: 15-41, wp: 24-50 |
| 中3 | 関数 y=ax² | calculation, visual, word_problem | calc: 13-39, vis: 18-44 |
| 中3 | 相似な図形 | proof, visual, word_problem | proof: 42-68, vis: 23-49 |
| 中3 | 円 | proof, visual, word_problem | proof: 44-70, vis: 25-51 |
| 中3 | 三平方の定理 | visual, word_problem | vis: 24-50, wp: 33-59 |
| 中3 | 標本調査 | knowledge, word_problem | know: 10-36, wp: 19-45 |

**難易度3段階の指定方法**（各形式の レンジ で min/mid/max を計算）
- `min` = レンジの最小値
- `mid` = (最小 + 最大) / 2（四捨五入）
- `max` = レンジの最大値

---

## 参考サイト（問題収集先）

以下のサイトから Exa の `web_search_exa` / `web_fetch_exa` ツールで収集する。

| サイト | URL | 特徴 |
|:---|:---|:---|
| 無料問題集 | https://jmqfs.net | 単元別・解答付き |
| 学図 QR 教材 | https://r7-sugaku.gakuto-plus.jp | 教科書準拠・例題付き |
| 高校入試難問 | https://hokkaimath.jp | 難問・良問集 |
| chu-su- | https://jhs-math.komaro.net | 単元別解説付き |

**検索クエリのパターン**
```
例: "中学3年 多項式 単項式と多項式の乗法 計算 例題"
例: "中学2年 一次関数 グラフ 問題 基礎"
例: "中学3年 三平方の定理 応用問題 site:jmqfs.net"
```

---

## 調査手順

### Step 1: 代表 lesson_id の特定

各大単元から代表的な lesson_id を選ぶ（基礎・標準・応用各 1 件）。

```python
import requests

# 単元一覧取得
lessons = requests.get('http://127.0.0.1:8000/problems/lessons').json()['lessons']

# 大単元でフィルタ
target_lu = "多項式"
target_grade = 3
filtered = [l for l in lessons 
            if l['large_unit'] == target_lu and l['grade'] == target_grade]
# → lesson_id, y_base, supported_forms が確認できる
```

### Step 2: 難易度レンジ確認

```python
r = requests.get(f'http://127.0.0.1:8000/problems/difficulty-range/{lesson_id}?form={form}')
data = r.json()
lo, hi = data['min_difficulty'], data['max_difficulty']
mid = (lo + hi) // 2
difficulties = [lo, mid, hi]  # 最小・中間・最大
```

### Step 3: 問題生成（中間表現で内容確認）

LLM は rate limit があるため、**まず inspect で SymPy 計算を確認**する。

```python
for diff in difficulties:
    r = requests.post('http://127.0.0.1:8000/problems/inspect', json={
        "curriculum": {"grade": grade, "lesson_ids": [lesson_id]},
        "problem_form": form,
        "target_difficulty": diff,
        "unlearned_lesson_ids": []
    }, timeout=30)
    mr = r.json()
    # mr['sampled_atoms'], mr['sub_questions'] を確認
```

**LLM 生成（rate limit 許容量内で行う）**
```python
r = requests.post('http://127.0.0.1:8000/problems/generate', json={...}, timeout=300)
# rate limit: gemini-flash-lite-latest 1000 RPD / 15 RPM
# 1 問生成に約 30〜60 秒
```

### Step 4: 参考サイトから例題収集

```python
# Exa 検索
# from mcp__claude_ai_Exa__web_search_exa を使用
# query: f"中学{grade}年 {large_unit} {form_ja} 例題 問題"

# 難易度3段階の収集クエリ例:
# 基礎: "中学3年 多項式 乗法除法 基礎問題 簡単"
# 標準: "中学3年 多項式 乗法除法 練習問題"
# 応用: "中学3年 多項式 乗法除法 応用問題 難しい"
```

### Step 5: 比較評価

各ケースについて以下を記録：

```
## 大単元: {large_unit}（中{grade}年）
### 形式: {form} / 難易度: {difficulty}（{level}）

**生成された中間表現（SymPy）**
- Blueprint: {blueprint_id}
- 選ばれた Atom: {atom_type}
- 計算式: {operands}
- 答え: {sympy_form}
- prompt_hint: {prompt_hint}

**LLM 翻訳後の問題文（生成できた場合）**
{problem_text}

**参考サイトの例題**
- 出典: {url}
- 問題: {example_problem}

**評価**
| 観点 | 評価 | 詳細 |
|:---|:---|:---|
| 内容妥当性 | ✅/⚠️/❌ | この単元で扱うべき概念が問題に含まれているか |
| 難易度妥当性 | ✅/⚠️/❌ | 指定難易度({difficulty})に対して適切な複雑さか |
| 教材との類似度 | ✅/⚠️/❌ | 外観・形式・パターンが教材と似ているか |
| 数学的正確性 | ✅/❌ | SymPy 答えが数学的に正しいか |

**問題点・改善提案**
{notes}
```

---

## 優先順位（rate limit を考慮した実施順序）

**Phase 1（最重要、まず実施）**：中間表現のみで内容妥当性を確認
- 全 23 大単元 × 主要形式 × 3難易度 = 約 70 ケースを inspect で確認
- 所要時間: 約 30 分（LLM 不使用）

**Phase 2（次に実施）**：代表ケースのみ LLM 生成
- 問題がある大単元・形式を優先
- 1 日の rate limit（1000 RPD）を考慮して 20〜30 件に絞る

**Phase 3（最後に実施）**：参考サイトとの対照
- Phase 1/2 で問題が見つかった単元を優先的に検索

---

## 出力形式

調査結果を `/Users/koki/workspace/mongene-v2/reports/comparison_study.md` に保存する。

サマリーテーブル形式：

```markdown
# 比較調査レポート

## サマリー

| 大単元 | 形式 | 難易度最小 | 難易度中間 | 難易度最大 | 内容妥当性 | 難易度妥当性 |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| 多項式（中3） | calculation | ✅ | ✅ | ⚠️ | ✅ | ⚠️ |
| ... | ... | ... | ... | ... | ... | ... |

## 詳細結果
...
```

---

## 評価基準の定義

### 内容妥当性
- ✅ その単元で扱う概念・演算が正しく問題に組み込まれている
- ⚠️ 概念は正しいが問題の設定や文脈が不自然
- ❌ その単元と無関係な計算が生成されている（例: 多項式単元で整数の足し算）

### 難易度妥当性（できる範囲で評価）
- ✅ 指定難易度に対して問題の複雑さ・手数が適切
- ⚠️ やや易しすぎる or 難しすぎる
- ❌ 指定難易度と大きく乖離（例: 難易度40の問題が小学生レベル）

### 教材との類似度
- ✅ 同じ問題タイプ・形式・パターン
- ⚠️ 概念は同じだが、パラメータ・設定が不自然（数値が大きすぎ等）
- ❌ 教材では見られない形式

### 数学的正確性
- ✅ sympy_form が正しい
- ❌ 答えが数学的に誤っている

---

## 重要な注意事項

1. **rate limit**: `gemini-flash-lite-latest` は 1000 RPD / 15 RPM。LLM 生成は間隔を空ける。
2. **inspect は rate limit なし**: 内容確認は `/problems/inspect` を優先的に使う。
3. **同一問題の繰り返し**: seed が時刻ベースなので再生成すれば別の問題になる。
4. **形式の制約**: 各大単元で利用可能な形式は決まっている（上記テーブル参照）。
5. **g3_l1 の例**: 「単項式と多項式の乗法・除法」は `calculation` 形式で `PolynomialAtom` が選ばれ、多項式の加減算が生成される（修正済み）。

---

## 既知の問題点（調査前に把握しておく事項）

- BasicCalculationStructure は `required_tags` によって Atom を選ぶため、lesson によって生成される問題タイプが変わる
- 難易度 max は単一単元では約 40〜74 の範囲（75 以上は複数単元の組み合わせが必要）
- LLM が問題文を生成する際、`$$..$$` を使うと表示が崩れる場合がある（プロンプトで禁止済み）
- 証明問題（proof 形式）は論理ステップの "骨格" のみ生成され、自然な証明文は LLM に依存
