#!/usr/bin/env python3
"""mapping.json のフォーム別 Blueprint 設定を一括更新する。

変更内容:
  1. knowledge form を持つ全レッスン:
     - execute_blueprint_by_form.knowledge = KnowledgeBaseStructure
     - 各 knowledge level に blueprint_params.knowledge_hint = description (未設定の場合)

  2. g1_l12〜l19 の文字式レッスン:
     - required_tags = ["polynomial"]
     - atom_constraints.PolynomialAtom = {max_degree: 1, num_variables: 1, max_coefficient: 6}

  3. g1_l11 の素因数分解:
     - required_tags = ["number"] (polynomial を除去)

  4. word_problem form を持つ全レッスン（方程式系のみ）:
     - execute_blueprint_by_form.word_problem = WordProblemStructure
       ※ EquationAtom が使えるレッスン（linear_equation タグ設定済み）のみ
       他は現状維持（BasicCalculationStructure）

使い方:
    python scripts/update_mapping_forms.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / "master_data" / "mapping.json"

# g1_l12〜l19: 文字の式レッスン
POLYNOMIAL_LESSONS = {
    "g1_l12", "g1_l13", "g1_l14", "g1_l15", "g1_l16",
    "g1_l17", "g1_l18", "g1_l19",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="変更内容を表示するだけで保存しない")
    args = parser.parse_args()

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    knowledge_updated = 0
    polynomial_updated = 0
    word_problem_updated = 0

    for lid, lesson in mapping.items():
        dl = lesson.get("difficulty_levels", {})

        # --- 1. knowledge form ---
        if "knowledge" in dl:
            bp_by_form = lesson.setdefault("execute_blueprint_by_form", {})
            if bp_by_form.get("knowledge") != "KnowledgeBaseStructure":
                bp_by_form["knowledge"] = "KnowledgeBaseStructure"
                knowledge_updated += 1

            for lv in dl["knowledge"]:
                bp_params = lv.setdefault("blueprint_params", {})
                if "knowledge_hint" not in bp_params:
                    desc = lv.get("description", "次の問いに答えなさい")
                    bp_params["knowledge_hint"] = desc

        # --- 2. g1_l12〜l19: 文字式 required_tags + atom_constraints ---
        if lid in POLYNOMIAL_LESSONS:
            lesson["required_tags"] = ["polynomial"]
            ac = lesson.setdefault("atom_constraints", {})
            pa = ac.setdefault("PolynomialAtom", {})
            pa.setdefault("max_degree", 1)
            pa.setdefault("num_variables", 1)
            pa.setdefault("max_coefficient", 6)
            polynomial_updated += 1
            print(f"  [poly] {lid}: required_tags=[polynomial], PolynomialAtom max_degree=1")

        # --- 3. g1_l11: 素因数分解 required_tags から polynomial を除去 ---
        if lid == "g1_l11":
            tags = lesson.get("required_tags", [])
            if "polynomial" in tags:
                lesson["required_tags"] = [t for t in tags if t != "polynomial"]
                print(f"  [g1_l11] required_tags: polynomial を除去 → {lesson['required_tags']}")

        # --- 4. word_problem: 方程式系レッスンに WordProblemStructure を設定 ---
        if "word_problem" in dl:
            req_tags = lesson.get("required_tags", [])
            bp_by_form = lesson.setdefault("execute_blueprint_by_form", {})
            # linear_equation タグがあるレッスンは WordProblemStructure を使う
            if "linear_equation" in req_tags and "word_problem" not in bp_by_form:
                bp_by_form["word_problem"] = "WordProblemStructure"
                word_problem_updated += 1
                print(f"  [wp] {lid}: word_problem → WordProblemStructure")

    print(f"\n変更サマリー:")
    print(f"  knowledge form 設定: {knowledge_updated} レッスン (全 knowledge level に knowledge_hint も設定)")
    print(f"  polynomial required_tags: {polynomial_updated} レッスン")
    print(f"  word_problem → WordProblemStructure: {word_problem_updated} レッスン")

    if args.dry_run:
        print("\n[DRY RUN] 保存しません")
        return

    MAPPING_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n保存完了: {MAPPING_PATH}")


if __name__ == "__main__":
    main()
