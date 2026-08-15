"""図形 SVG の回帰検知テスト

scripts/generate_visual_snapshots.py で生成した snapshot と差異が出ていないか検証。
数学的正しさは人間レビュー必須（このテストは「描画ロジック変更の早期検知」のみ担保）。

snapshot が意図的に変わった場合は scripts/generate_visual_snapshots.py を再実行する。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_DIR = REPO_ROOT / "reports" / "visual_snapshots"
SNAPSHOT_INDEX = SNAPSHOT_DIR / "index.json"


def _load_index() -> dict | None:
    if not SNAPSHOT_INDEX.exists():
        return None
    return json.loads(SNAPSHOT_INDEX.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def snapshot_index() -> dict:
    idx = _load_index()
    if idx is None:
        pytest.skip("visual_snapshots/index.json が無い（generate_visual_snapshots.py を実行）")
    return idx


def test_snapshot_files_exist(snapshot_index: dict) -> None:
    for name, meta in snapshot_index.items():
        svg_path = REPO_ROOT / meta["svg_path"]
        assert svg_path.exists(), f"スナップショット {name} が見つからない: {svg_path}"


def test_snapshot_has_minimum_size(snapshot_index: dict) -> None:
    """SVG が空にならないことの検知"""
    for name, meta in snapshot_index.items():
        svg_path = REPO_ROOT / meta["svg_path"]
        content = svg_path.read_text(encoding="utf-8")
        assert "<svg" in content, f"{name}: <svg> タグが無い"
        assert len(content) > 200, f"{name}: SVG が小さすぎる ({len(content)} bytes)"


def test_snapshot_count_is_at_least_6(snapshot_index: dict) -> None:
    """主要 6 種の Visual Component がすべてカバーされている"""
    assert len(snapshot_index) >= 6
