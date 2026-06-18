# mongene-v2

中学数学問題自動生成システム（5 層アーキテクチャ）。詳細設計は `docs/implementation_plan.md`、残課題は `docs/known_limitations.md` を参照。

## 1 コマンドで起動

```bash
make up      # 初回は venv 作成 + 依存インストールも自動
```

起動後にブラウザで以下を開く：
- **http://localhost:8000/** — メイン UI（学年・単元・難易度を選んで問題生成）
- **http://localhost:8000/docs** — Swagger UI（API スキーマ・試し打ち）

実 LLM 接続を有効にするには `.env` の `GEMINI_API_KEY` を設定。未設定でも UI は起動するが、`/problems/generate` 時にエラー（モックを使うには `SKIP_LLM_IN_TESTS=true make up`）。

## 停止・再起動・状態確認

```bash
make down      # 停止
make restart   # 再起動
make status    # 状態確認
make logs      # ログ追跡
```

## テスト

```bash
SKIP_LLM_IN_TESTS=true .venv/bin/pytest tests/
```

## 構成

```
apps/api/        # FastAPI バックエンド + HTML UI（Vanilla + KaTeX）
master_data/     # 177 lesson カタログ + Atom/Verb/Blueprint メタ
scripts/         # マスターデータ生成・品質ゲート・SVG スナップショット
tests/           # pytest 227 件
reports/         # 品質ゲート結果 + 視覚スナップショット
docs/            # 設計書・既知の制限事項
```
