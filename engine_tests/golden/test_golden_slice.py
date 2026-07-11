"""golden 回帰テスト（実装設計 §9.1・§10・Task7）。

`spec approve` で `engine_tests/golden/<family>/<family>_lv<level>_seed<seed>.yaml` に
保存された Problem 全文と、同 seed で再生成した Problem が一致することを検査する。

golden が1件も無ければ（= まだ何も approve されていない）テストは収集されず
実質 no-op になる（pytest.mark.skipif で family 単位にスキップする形にすると
コレクション時点でファイル一覧に依存するため、ここではモジュール読み込み時に
golden ディレクトリを走査してパラメータ化し、0件なら1個の skip テストを出す）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Problem, Unsupported
from engine.core.pipeline import generate

_GOLDEN_ROOT = Path(__file__).resolve().parent


def _iter_golden_files() -> list[Path]:
    if not _GOLDEN_ROOT.exists():
        return []
    files: list[Path] = []
    for family_dir in sorted(_GOLDEN_ROOT.iterdir()):
        if not family_dir.is_dir():
            continue
        for f in sorted(family_dir.glob("*.yaml")):
            if f.name == "approval.yaml":
                continue
            files.append(f)
    return files


_GOLDEN_FILES = _iter_golden_files()


@pytest.fixture(autouse=True)
def _engine() -> None:
    bootstrap()


def _unit_from_family(family_name: str) -> str:
    parts = family_name.split(".", 2)
    if len(parts) != 3:
        raise ValueError(f"family 名の形式が不正: {family_name!r}")
    return parts[1]


if not _GOLDEN_FILES:
    def test_no_golden_yet() -> None:
        pytest.skip("golden 未保存（spec approve 実行後に本テストが有効化される）")
else:
    @pytest.mark.parametrize("golden_path", _GOLDEN_FILES, ids=[f.stem for f in _GOLDEN_FILES])
    def test_golden_regression(golden_path: Path) -> None:
        golden: dict[str, Any] = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
        meta = golden["meta"]
        resolved = meta["resolved"]
        seed = meta["seed"]

        req = GenerateRequest(
            subject=resolved["subject"],
            unit=resolved["unit"],
            form=resolved["form"],
            level=resolved["level"],
            seed=seed,
        )
        result = generate(req)
        assert isinstance(result, Problem), (
            f"{golden_path.name}: 再生成が Unsupported になった: "
            f"{getattr(result, 'code', '?')} {getattr(result, 'detail', '')}"
        )
        new_dump = result.model_dump(mode="json")
        assert new_dump == golden, (
            f"{golden_path.name}: golden と再生成結果が不一致（RNG消費順/テンプレ変更の可能性。"
            f"意図的変更なら spec approve で再承認すること）"
        )
