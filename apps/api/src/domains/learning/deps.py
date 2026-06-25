"""学習ループ用の共有依存（AdaptiveStore / 前提グラフ / mapping）。

既存コードのスタイルに合わせ、モジュールグローバルのシングルトンで提供する。
DB パスは環境変数 `ADAPTIVE_DB_PATH` で上書き可能（テストで一時 DB を差し込むため）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from apps.api.src.core.curriculum.prerequisite_loader import (
    PrerequisiteGraph,
    get_default_prerequisite_graph,
)
from apps.api.src.core.store.adaptive_store import AdaptiveStore
from apps.api.src.domains.problems.router import _load_mapping

_DEFAULT_DB = "master_data/cache/adaptive.db"
_store: Optional[AdaptiveStore] = None


def get_store() -> AdaptiveStore:
    global _store
    if _store is None:
        _store = AdaptiveStore(db_path=os.environ.get("ADAPTIVE_DB_PATH", _DEFAULT_DB))
    return _store


def reset_store_for_tests(db_path: str) -> AdaptiveStore:
    """テスト用に一時 DB へストアを差し替える。"""
    global _store
    if _store is not None:
        _store.close()
    _store = AdaptiveStore(db_path=db_path)
    return _store


def get_graph() -> PrerequisiteGraph:
    return get_default_prerequisite_graph()


def get_mapping() -> Dict[str, Any]:
    return _load_mapping()
