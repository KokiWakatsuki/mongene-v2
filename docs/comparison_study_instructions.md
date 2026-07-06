# 比較調査指示書：mongene-v2 生成問題 vs 実際の教材

## 調査の目的

`mongene-v2`（中学数学問題自動生成システム）が生成する問題が、
実際の教材・問題集と比較して**妥当な構造**を持っているかを調査する。

**LLM は使用しない。** `/problems/inspect` エンドポイントで得られる LaTeX 式・Atom 情報・
SymPy 答えだけで構造比較を行う。日本語の自然さは評価対象外。

評価観点：
1. **構造の妥当性**：選ばれた Atom/Blueprint が単元の数学的内容を正しく表現しているか
2. **問題形式の妥当性**：その単元に不適切な形式（supported_forms）が含まれていないか
3. **難易度レンジの妥当性**：min/mid/max で問題の複雑さが実際に変化しているか
4. **数学的正確性**：SymPy の答えが正しいか

---

## システムの前提知識

### 起動方法
```bash
cd /Users/koki/workspace/mongene-v2
make up   # サーバ起動（起動済みなら不要）
make down # サーバ停止
```

### 主要エンドポイント

**単元一覧（全 177 件）**
```
GET http://127.0.0.1:8000/problems/lessons
```
返り値の各エントリに `lesson_id`, `title`, `grade`, `large_unit`, `supported_forms`, `y_base` が含まれる。

**難易度レンジ確認**
```
GET http://127.0.0.1:8000/problems/difficulty-range/{lesson_id}?form={form}
→ { "min_difficulty": N, "max_difficulty": M }
```

**構造確認（LLM なし・即時返却）← 今回の調査で使う唯一のエンドポイント**
```
POST http://127.0.0.1:8000/problems/inspect
{
  "curriculum": {"grade": 3, "lesson_ids": ["g3_l1"]},
  "problem_form": "calculation",
  "target_difficulty": 35,
  "unlearned_lesson_ids": []
}
```

inspect の返り値で確認する主要フィールド：
- `selected_blueprint` : 使用された Blueprint 名
- `sampled_atoms` : 選ばれた Atom の型とタグ
- `sub_questions[].prompt_hint` : LaTeX 式を含む問題文（構造を示す）
- `sub_questions[].answer.text_form` : 答え（LaTeX or 数値）
- `sub_questions[].answer.sympy_form` : SymPy 形式の答え（正確性確認用）

### lesson_id の形式
`g{grade}_l{lesson_number}` 例: `g3_l1`, `g1_l22`

### 問題形式（5種類）
| form | 定義 |
|:---|:---|
| knowledge | 定義・用語・条件の確認（計算なし） |
| calculation | 式・数値が与えられ計算するだけ |
| visual | 図・グラフから情報を読み取って立式 |
| word_problem | 自然言語から変数抽出・立式 |
| proof | 論理構成を記述 |

---

## 調査対象

**全 177 小単元 × 各単元の全 supported_forms × 難易度 3 段階（min/mid/max）**

合計約 950 ケース。inspect のみなので LLM rate limit は無関係、数分で処理可能。

### 難易度 3 段階の計算方法
```python
r = requests.get(f'http://127.0.0.1:8000/problems/difficulty-range/{lesson_id}?form={form}')
lo = r.json()['min_difficulty']
hi = r.json()['max_difficulty']
mid = (lo + hi) // 2
difficulties = [lo, mid, hi]
```

---

## 調査手順

### Step 1: 全単元・全形式・3難易度を一括 inspect

```python
import requests, json

# 1. 単元一覧取得
lessons = requests.get('http://127.0.0.1:8000/problems/lessons').json()['lessons']

results = []
for lesson in lessons:
    lid = lesson['lesson_id']
    grade = lesson['grade']
    for form in lesson['supported_forms']:
        # 難易度レンジ取得
        r = requests.get(
            f'http://127.0.0.1:8000/problems/difficulty-range/{lid}',
            params={'form': form}
        )
        lo = r.json()['min_difficulty']
        hi = r.json()['max_difficulty']
        mid = (lo + hi) // 2

        for level, diff in [('min', lo), ('mid', mid), ('max', hi)]:
            r2 = requests.post('http://127.0.0.1:8000/problems/inspect', json={
                'curriculum': {'grade': grade, 'lesson_ids': [lid]},
                'problem_form': form,
                'target_difficulty': diff,
                'unlearned_lesson_ids': []
            }, timeout=30)

            entry = {
                'lesson_id': lid,
                'title': lesson['title'],
                'large_unit': lesson['large_unit'],
                'grade': grade,
                'form': form,
                'level': level,
                'difficulty': diff,
            }
            if r2.status_code == 200:
                data = r2.json()
                entry['blueprint'] = data.get('selected_blueprint', '?')
                entry['atoms'] = [a.get('type', '?') for a in data.get('sampled_atoms', {}).values()]
                entry['sub_questions'] = [
                    {
                        'prompt_hint': sq['prompt_hint'],
                        'answer': sq['answer']['text_form'],
                    }
                    for sq in data.get('sub_questions', [])
                ]
                entry['ok'] = True
            else:
                entry['ok'] = False
                entry['error'] = r2.text[:200]

            results.append(entry)

# 結果を保存
with open('reports/inspect_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'{len(results)} ケース処理完了')
```

### Step 2: 参考サイトから例題収集

各単元のタイトルで Exa 検索し、実際の教材の問題構造を収集する。

```
# 検索クエリのパターン
"中学{grade}年 {large_unit} {title_keyword} 例題"
"中学{grade}年 {large_unit} {title_keyword} 問題 site:jmqfs.net"
```

参考サイト：
| サイト | URL |
|:---|:---|
| 無料問題集 | https://jmqfs.net |
| 学図 QR 教材 | https://r7-sugaku.gakuto-plus.jp |
| chu-su- | https://jhs-math.komaro.net |
| 高校入試難問 | https://hokkaimath.jp |

### Step 3: 構造比較・評価

各ケースについて以下を判定する：

```
## {title}（{lesson_id}）/ 形式: {form} / 難易度: {difficulty}（{level}）

**生成された構造**
- Blueprint: {blueprint}
- 選ばれた Atom: {atoms}
- 問題文（LaTeX）: {prompt_hint}
- 答え: {answer}

**参考教材の例題**
- 出典: {url}
- 問題: {example}

**評価**
| 観点 | 評価 |
|:---|:---:|
| 構造の妥当性（Atom/Blueprint が単元内容を正しく表現しているか） | ✅/⚠️/❌ |
| 問題形式の妥当性（この単元にこの form は適切か） | ✅/⚠️/❌ |
| 難易度の変化（min→mid→max で複雑さが変わっているか） | ✅/⚠️/❌ |
| 数学的正確性（答えが正しいか） | ✅/❌ |
```

---

## 検出対象の問題パターン

以下のような問題を見つけることがこの調査の主目的：

| 問題パターン | 例 |
|:---|:---|
| 不適切な Atom 選択 | 二次関数単元なのに一次関数 Atom が選ばれている |
| 不適切な問題形式 | 証明問題が含まれるべきでない単元に proof が設定されている |
| 難易度レンジの硬直 | min と max で問題の複雑さが変わらない |
| 単元と無関係な演算 | 多項式の乗法単元なのに整数の足し算が生成される |
| 答えが数学的に誤り | SymPy 答えが正しくない |
| サポートされない形式 | 特定の単元で visual や proof が不自然に割り当てられている |

---

## 出力形式

調査結果を以下のファイルに保存する：

- `reports/inspect_results.json` : 全ケースの raw データ（Step 1 で自動生成）
- `reports/comparison_study.md` : 人間が読む評価レポート

レポートのサマリーテーブル形式：

```markdown
# 比較調査レポート

## サマリー

| lesson_id | タイトル | 形式 | 構造妥当性 | 形式妥当性 | 難易度変化 | 正確性 | 問題点 |
|:---|:---|:---|:---:|:---:|:---:|:---:|:---|
| g3_l1 | 単項式と多項式の乗法 | calculation | ✅ | ✅ | ⚠️ | ✅ | min/mid/max で多項式の係数しか変わらない |
| ... | | | | | | | |

## 問題あり一覧（❌/⚠️ のケースのみ）
...

## 詳細結果
...
```

---

## 評価基準の定義

### 構造の妥当性
- ✅ 選ばれた Atom と Blueprint がその単元の数学的内容を正しく表現している
  - 例: 「二次方程式」単元 → `EquationAtom(degree=2)` + `SolveEquationStructure`
  - 例: 「一次関数のグラフ」単元 → `LinearFuncAtom` + `FunctionGeometryFusionStructure`
- ⚠️ 内容は関連しているが、参考教材と比べて単純すぎる・複雑すぎる
- ❌ 単元と無関係な Atom が選ばれている
  - 例: 「多項式の乗法」単元 → `NumberAtom` + 整数の足し算

### 問題形式の妥当性
- ✅ その単元で本来出る問題形式と一致している
- ⚠️ 技術的には可能だが、教材では見られない形式
- ❌ その単元に存在しない問題形式が supported_forms に含まれている

### 難易度の変化
- ✅ min/mid/max で使われる数値・式の複雑さ・手数が明確に変化している
- ⚠️ 変化はあるが小さい（例: 係数が 2 倍になるだけ）
- ❌ min と max で構造的な差がない（同じ形の問題）

### 数学的正確性
- ✅ `answer.sympy_form` が数学的に正しい
- ❌ 答えが誤っている、または None

---

## 重要な注意事項

1. **inspect は LLM を使わない**：rate limit なし、全 950 ケースを数分で処理できる
2. **同一問題の繰り返し**：seed が時刻ベースなので同じ lesson_id でも毎回異なる問題が生成される
3. **証明問題（proof 形式）**：`prompt_hint` は「証明しなさい」のみ、答えは「△ABC ≡ △DEF」形式。構造確認は blueprint と atom で判断する
4. **難易度 max の上限**：単一単元では約 40〜74。75 以上は複数単元の組み合わせが必要
5. **サーバが起動していること**：`make up` で起動後、`http://127.0.0.1:8000/docs` でエンドポイントを確認できる

---

## 既知の修正済み問題点

- `BasicCalculationStructure` + `required_tags=["polynomial"]` → `PolynomialAtom` が正しく選ばれる（修正済み）
- `SolveEquationStructure` 新設により方程式単元で `EquationAtom` が正しく選ばれる（修正済み）
- 答えの LaTeX 表示：整数はそのまま、分数・根号は LaTeX で表示（修正済み）
