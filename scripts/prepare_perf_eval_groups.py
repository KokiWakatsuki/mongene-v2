#!/usr/bin/env python3
"""性能評価 グルーピング前処理スクリプト

reports/perf_eval/problems.jsonl → reports/perf_eval/groups.json
(lesson_id, form) ペアごとにまとめ、評価エージェントが読みやすい形にする。

使い方:
    python scripts/prepare_perf_eval_groups.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBLEMS_PATH = ROOT / "reports" / "perf_eval" / "problems.jsonl"
GROUPS_PATH = ROOT / "reports" / "perf_eval" / "groups.json"
MAPPING_PATH = ROOT / "master_data" / "mapping.json"


def summarize_problem(rec: dict) -> dict:
    """問題レコードから評価に必要な最小情報を抽出する。"""
    sqs = []
    for sq in rec.get("sub_questions", []):
        sqs.append({
            "label": sq.get("label", ""),
            "prompt_hint": sq.get("prompt_hint", "")[:200],
            "answer": {
                "text_form": sq.get("answer", {}).get("text_form", ""),
                "type": sq.get("answer", {}).get("type", ""),
            },
        })
    # Atom の型だけ抽出（詳細な次元は省略）
    atoms = {
        slot: info.get("atom_type", "")
        for slot, info in rec.get("sampled_atoms", {}).items()
    }
    return {
        "trial": rec.get("trial", 1),
        "seed": rec.get("seed", 0),
        "blueprint_id": rec.get("blueprint_id", ""),
        "selected_tags": rec.get("selected_tags", []),
        "atom_types": atoms,
        "sub_questions": sqs,
    }


def main() -> None:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    records = [
        json.loads(l)
        for l in PROBLEMS_PATH.read_text(encoding="utf-8").splitlines()
    ]

    # (lesson_id, form) → level → [trials]
    raw: dict = defaultdict(lambda: defaultdict(list))
    for rec in records:
        lid = rec["lesson_id"]
        form = rec["form"]
        level = rec["level"]
        raw[(lid, form)][level].append(rec)

    groups = []
    for (lid, form), level_map in sorted(raw.items()):
        m = mapping.get(lid, {})
        # difficulty_levels からレベルの description を取得
        lv_descs = {
            lv_def["lv"]: lv_def.get("description", "")
            for lv_def in m.get("difficulty_levels", {}).get(form, [])
        }

        levels_out = []
        for level, recs in sorted(level_map.items()):
            successes = [r for r in recs if not r.get("error")]
            errors = [r for r in recs if r.get("error")]
            levels_out.append({
                "level": level,
                "description": lv_descs.get(level, ""),
                "problems": [summarize_problem(r) for r in successes],
                "generation_errors": [r.get("error", "") for r in errors],
            })

        groups.append({
            "lesson_id": lid,
            "form": form,
            "title": m.get("title", ""),
            "grade": m.get("grade", 0),
            "domain": m.get("domain", ""),
            "large_unit": m.get("large_unit", ""),
            "execute_blueprint": m.get("execute_blueprint", ""),
            "levels": levels_out,
        })

    GROUPS_PATH.write_text(
        json.dumps(groups, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total_groups = len(groups)
    total_probs = sum(
        len(lv["problems"])
        for g in groups
        for lv in g["levels"]
    )
    total_errs = sum(
        len(lv["generation_errors"])
        for g in groups
        for lv in g["levels"]
    )
    print(f"グループ数: {total_groups}")
    print(f"成功問題数: {total_probs}")
    print(f"エラー数: {total_errs}")
    print(f"→ {GROUPS_PATH}")


if __name__ == "__main__":
    main()
