"""engine_tests 共通設定。

リポジトリルートを sys.path に載せ、`import engine.*` を解決する。
旧 pytest 設定（testpaths=tests, --cov=apps）とは独立に、
`pytest engine_tests --no-cov -o addopts=""` で実行する。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
