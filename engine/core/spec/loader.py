"""FamilySpec ローダ（実装設計 §4.3）。

YAML を読み `SpecFamily`（pydantic, contracts.py 定義）へ変換する。ローダは
「YAML の素朴な構造 → 契約型」の機械的な組み立てのみを行い、意味検査は行わない
（意味検査は spec_lint.py の責務）。pydantic の ValidationError はそのまま
呼び出し元へ伝播させる（構造不正の検出はテストの一部）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from engine.core.contracts import SpecFamily, SpecLevel


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"FamilySpec のトップレベルは mapping であること: {path}")
    return data


def load_family_spec(path: str | Path) -> SpecFamily:
    """1 YAML ファイル（1 family）を読み `SpecFamily` に変換する。

    - `levels` は `dict[str, SpecLevel]`（キーは str(level)）。
    - `remedial.default_level` → `SpecFamily.remedial_default_level`。
    - `levels."<k>".text` は `{tier, template}` の dict のまま `SpecLevel.text` へ格納。
    - 各 `SpecLevel.level` はキーを int 化したもの。
    """
    path = Path(path)
    raw = _load_yaml(path)

    raw_levels: dict[str, Any] = raw.get("levels") or {}
    levels: dict[str, SpecLevel] = {}
    for key, block in raw_levels.items():
        key_str = str(key)
        block = dict(block or {})
        block["level"] = int(key_str)
        levels[key_str] = SpecLevel(**block)

    remedial = raw.get("remedial") or {}
    remedial_default_level = remedial.get("default_level")

    return SpecFamily(
        family=raw["family"],
        form=raw["form"],
        source_desc=raw.get("source_desc", ""),
        concepts_default=list(raw.get("concepts_default") or []),
        levels=levels,
        remedial_default_level=remedial_default_level,
    )


def load_family_dir(dir: str | Path) -> dict[str, SpecFamily]:
    """ディレクトリ内の `*.yaml` を全ロードし family 名 → SpecFamily の dict を返す。"""
    dir = Path(dir)
    result: dict[str, SpecFamily] = {}
    for path in sorted(dir.glob("*.yaml")):
        spec = load_family_spec(path)
        result[spec.family] = spec
    return result


__all__ = ["load_family_spec", "load_family_dir"]
