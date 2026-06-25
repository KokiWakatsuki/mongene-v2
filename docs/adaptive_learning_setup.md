# 個別最適化・完全習得学習ループ — セットアップ & 体験ガイド

`feat/adaptive-learning` ブランチで動く、採点→習熟更新→次単元・難易度決定→出題 の閉ループ（MVP）を
ローカルで試す手順。

## 0. 前提

- Python **3.12 以上**（`pyproject.toml` の `requires-python>=3.12`。`Makefile` は `python3.13` を使用）
- ブランチ: `feat/adaptive-learning`（`git switch feat/adaptive-learning`）

## 1. セットアップ

### A. Makefile を使う（python3.13 がある場合）

```bash
make up      # 初回は venv 作成 + 依存インストール + サーバ起動
```

### B. 手動（python3.13 が無い / 別バージョンを使う場合）

```bash
python3.12 -m venv .venv          # or python3.13
.venv/bin/pip install -e ".[dev]"
```

> 補足: 開発機に 3.12/3.13 が無い場合、依存を直接入れて `PYTHONPATH` で起動も可能:
> `python3 -m venv .venv && .venv/bin/pip install sympy fastapi "uvicorn[standard]" pydantic google-genai svgwrite matplotlib networkx pyyaml python-dotenv`
> 起動時に `PYTHONPATH=.` を付ける。

## 2. 環境変数（`.env`）

`.env.example` をコピーして編集:

```bash
cp .env.example .env
```

| 変数 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | **実問題生成に必須** | Google AI Studio で取得 (https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL_LITE` / `_STANDARD` / `_REASONING` | 任意 | モデルティア。既定のままで可（無料枠は `gemini-flash-lite-latest` 推奨） |
| `SKIP_LLM_IN_TESTS` | 任意 | `true` で **LLMをモック化**（キー不要・即時・無料。問題文は仮テキスト、数値と採点は正しい） |
| `ADAPTIVE_DB_PATH` | 任意 | 学習者状態 SQLite の場所（既定 `master_data/cache/adaptive.db`） |

> ⚠️ Gemini 無料枠は厳しめ（`gemini-flash-lite-latest`=約1000 RPD、`gemini-2.5-flash`=約20 RPD）。
> 実生成は 1問あたり 30〜60秒。**ループの動作確認だけなら下記「モードB」が速くて無料**。

## 3. 起動

```bash
# モードA: 実LLM（自然な問題文。GEMINI_API_KEY 必須）
make up
#   または手動:
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000

# モードB: モック（キー不要・即時・無料。問題文は仮、採点ロジックは本物）
SKIP_LLM_IN_TESTS=true .venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

## 4. UI で試す

ブラウザで開く:

- **http://localhost:8000/learn** ← ★ 個別最適化・完全習得ループの体験UI（今回の新規）
- http://localhost:8000/ — 既存の手動問題ジェネレータ（学年・単元・難易度を選んで生成）
- http://localhost:8000/docs — Swagger（`/students`, `/learning/next`, `/learning/submit` を試打ち）

### /learn の使い方

1. 学年を選んで「新しい生徒で開始」（生徒IDが採番され、ブラウザに保存される）
2. 「▶ 次の問題を出す」→ 前提を満たす最浅の未習得単元が、生徒の習熟度に応じた難易度で出題される
3. 解答を入力 →「採点する」→ ○×と正答、習熟度バーが更新される
   - **正答が続くと難易度が上がり**、**直近正答率80%＋連続3問＋計5問以上で「習得」** → 次の単元がアンロック
   - 誤答すると連続正答がリセットされ、難易度は易しくなる
4. 下部「習熟状況」に単元ごとの習得/学習中が一覧表示される

## 5. API を直接叩く例

```bash
SID=$(curl -s -X POST localhost:8000/students -H 'Content-Type: application/json' -d '{"grade":1}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
# 次の問題（problem.sub_questions[].answer.sympy_form が正答）
curl -s -X POST localhost:8000/learning/next -H 'Content-Type: application/json' -d "{\"student_id\":\"$SID\"}"
# 採点（answers は [{label, answer}]）
curl -s -X POST localhost:8000/learning/submit -H 'Content-Type: application/json' \
  -d "{\"student_id\":\"$SID\",\"problem_id\":\"...\",\"answers\":[{\"label\":\"(1)\",\"answer\":\"16\"}]}"
# 習熟サマリ
curl -s localhost:8000/students/$SID/mastery
```

## 6. テスト

```bash
SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/
# 303 passed / coverage 84%
```

## 現状の範囲（MVP）と今後

- **対象**: `calculation` 形式・`numeric`/`expression` 解答の lesson（外部依存ゼロ・自動採点）
- **未対応（後続ブランチ）**: 誤答時の前提診断(DAG逆探索) / ScoGene手書き採点(経路B) / BKT / IRT較正 / knowledge・visual・proof形式 / 間隔反復
- 採点で `route_b_needed: true` が返る問題（proof等）は、将来 ScoGene 連携（経路B）で採点する想定
