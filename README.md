# mongene-v2

中学数学問題自動生成システム（5層アーキテクチャ）。

詳細設計は `docs/implementation_plan.md` を参照。

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## テスト

```bash
SKIP_LLM_IN_TESTS=true pytest tests/ -v
```

## API 起動（Phase 6 完了後）

```bash
uvicorn apps.api.main:app --reload --port 8000
```
