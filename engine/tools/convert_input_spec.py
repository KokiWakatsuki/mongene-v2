"""input_spec_2026-07-08.json → units.generated.yaml 変換（Task3 / 実装設計 §12・N-6）。

**正の分界（N-6）**:
- 本スクリプトが生成する `units.generated.yaml`（単元タクソノミー: 単元×form×level と
  desc/example/market_ref）の正は元 JSON。手で編集しない（再生成で上書きされる）。
- 概念・誤答要因・前提DAG・fact の正は手書きの concepts.yaml / error_causes.yaml /
  prerequisites.yaml / facts.yaml（二重編集の禁止）。

使い方:
    python -m engine.tools.convert_input_spec
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "docs" / "input_spec_2026-07-08.json"
_DST = _ROOT / "engine" / "curriculum" / "math" / "units.generated.yaml"


def convert(src: Path = _SRC) -> dict[str, Any]:
    data = json.loads(src.read_text(encoding="utf-8"))
    forms_taxonomy: list[str] = data["forms_taxonomy"]
    difficulty_bands: list[str] = data["difficulty_bands"]

    units: dict[str, Any] = {}
    for lesson in data["lessons"]:
        uid = lesson["lesson_id"]
        forms_out: dict[str, Any] = {}
        for f in lesson.get("forms", []):
            levels_out: dict[str, Any] = {}
            for lv in f.get("levels", []):
                levels_out[str(lv["level"])] = {
                    "band": lv.get("band", ""),
                    "desc": lv.get("desc", ""),
                    "example": lv.get("example", ""),
                    "market_ref": lv.get("market_ref", ""),
                }
            forms_out[f["form"]] = {
                "rationale": f.get("rationale", ""),
                "levels": levels_out,
            }
        units[uid] = {
            "title": lesson.get("title", ""),
            "section": lesson.get("section", ""),
            "unit_flag": lesson.get("unit_flag", "ok"),
            "notes": lesson.get("notes", ""),
            "forms": forms_out,
        }

    return {
        "subject": "math",
        "source": "docs/input_spec_2026-07-08.json",
        "forms_taxonomy": forms_taxonomy,
        "difficulty_bands": difficulty_bands,
        "units": units,
    }


def main() -> None:
    out = convert()
    _DST.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# 自動生成ファイル（正 = docs/input_spec_2026-07-08.json）。手で編集しないこと。\n"
        "# 再生成: python -m engine.tools.convert_input_spec\n"
    )
    with _DST.open("w", encoding="utf-8") as fp:
        fp.write(header)
        yaml.safe_dump(out, fp, allow_unicode=True, sort_keys=True, width=200)
    print(f"wrote {_DST} ({len(out['units'])} units)")


if __name__ == "__main__":
    main()
