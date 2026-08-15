"""テスト全体の前処理。

`SKIP_LLM_IN_TESTS=true` を強制し、Gemini API 実呼び出しを抑制する。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _ensure_skip_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKIP_LLM_IN_TESTS", "true")
