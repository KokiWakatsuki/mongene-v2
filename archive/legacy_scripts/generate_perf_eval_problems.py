#!/usr/bin/env python3
"""性能評価用 問題生成スクリプト

全 (lesson_id, form, level) × 2問 を /problems/inspect 経由（LLM なし）で生成し、
reports/perf_eval/problems.jsonl に格納する。

使い方:
    python scripts/generate_perf_eval_problems.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_PATH = ROOT / "reports" / "perf_eval" / "problems.jsonl"
MAPPING_PATH = ROOT / "master_data" / "mapping.json"
PROBLEMS_PER_COMBO = 2


def build_combos(mapping: dict) -> list[tuple[str, str, int]]:
    """implementable な (lesson_id, form, level) の一覧を返す。"""
    combos = []
    for lid, m in mapping.items():
        for form, levels in m.get("difficulty_levels", {}).items():
            for lv_def in levels:
                if lv_def.get("implementable", True):
                    combos.append((lid, form, lv_def["lv"]))
    return sorted(combos)


def inspect_once(client, lesson_id: str, form: str, level: int) -> dict:
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": [lesson_id]},
        "problem_form": form,
        "target_level": level,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/inspect", json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def main() -> None:
    from fastapi.testclient import TestClient
    from apps.api.main import app

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    combos = build_combos(mapping)
    total = len(combos) * PROBLEMS_PER_COMBO
    print(f"生成対象: {len(combos)} 組み合わせ × {PROBLEMS_PER_COMBO}問 = {total} 件")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    client = TestClient(app)
    done = 0
    errors = 0
    t0 = time.time()

    with OUTPUT_PATH.open("w", encoding="utf-8") as fout:
        for i, (lid, form, level) in enumerate(combos):
            for trial in range(PROBLEMS_PER_COMBO):
                try:
                    result = inspect_once(client, lid, form, level)
                    record = {
                        "lesson_id": lid,
                        "form": form,
                        "level": level,
                        "trial": trial + 1,
                        "title": mapping[lid].get("title", ""),
                        "grade": mapping[lid].get("grade", 0),
                        "domain": mapping[lid].get("domain", ""),
                        "large_unit": mapping[lid].get("large_unit", ""),
                        "blueprint_id": result.get("blueprint_id", ""),
                        "difficulty_score": result.get("difficulty_score", 0),
                        "selected_tags": result.get("selected_tags", []),
                        "sampled_atoms": result.get("sampled_atoms", {}),
                        "sub_questions": result.get("sub_questions", []),
                        "seed": result.get("seed", 0),
                        "error": None,
                    }
                    done += 1
                except Exception as e:
                    record = {
                        "lesson_id": lid,
                        "form": form,
                        "level": level,
                        "trial": trial + 1,
                        "title": mapping[lid].get("title", ""),
                        "grade": mapping[lid].get("grade", 0),
                        "error": str(e),
                        "sub_questions": [],
                    }
                    errors += 1

                fout.write(json.dumps(record, ensure_ascii=False) + "\n")

            elapsed = time.time() - t0
            pct = (i + 1) / len(combos) * 100
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(combos) - i - 1) / rate if rate > 0 else 0
            print(
                f"\r  [{i+1}/{len(combos)}] {pct:.1f}%  ✅{done} ❌{errors}"
                f"  {elapsed:.0f}s elapsed  ETA {eta:.0f}s",
                end="",
                flush=True,
            )

    print()
    print(f"\n完了: ✅{done}件生成  ❌{errors}件エラー  → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
