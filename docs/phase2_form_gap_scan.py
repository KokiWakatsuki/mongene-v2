#!/usr/bin/env python3
"""フェーズ②: 確定入力仕様(input_spec) と 現行 mapping.json の対応ギャップを静的診断。

使い方: .venv/bin/python docs/phase2_form_gap_scan.py
出力: 全 (lesson × form) セルを4カテゴリに分類し、集計と per-cell 一覧を表示。
  - new_form   : spec の form がシステム語彙(5語)に存在しない = find_value/graph_table/construction
  - wire_only  : form はシステム語彙に在るが この単元の mapping.supported_forms に未割当(安い)
  - level_remap: 割当済だが spec の Lv 集合 ≠ mapping.difficulty_levels の lv 集合(中)
  - ok         : form も Lv 集合も一致

注: システムの問題形式語彙は現状 5 語のみ = {calculation, knowledge, proof, word_problem, visual}。
    新仕様7型のうち find_value/graph_table/construction は語彙自体が無い(旧 visual が3つに分裂)。
    → 決定: 「エンジンに7型語彙を教える」(visual を find_value/graph_table/construction に分割し
       blueprint/builder が form を尊重)。本スクリプトはその対応作業を費用対効果順に並べるための表。

LLM 不使用・決定論。mapping.json は読むだけ(書き換えない)。
"""
import json
import os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(BASE, "input_spec_2026-07-08.json")
MAPPING = os.path.join(os.path.dirname(BASE), "master_data", "mapping.json")

SYS_FORMS = {"calculation", "knowledge", "proof", "word_problem", "visual"}
NEW_FORMS = {"find_value", "graph_table", "construction"}


def classify():
    spec = json.loads(open(SPEC, encoding="utf-8").read())
    mp = json.load(open(MAPPING, encoding="utf-8"))
    cells = []
    for L in spec["lessons"]:
        lid = L["lesson_id"]
        M = mp.get(lid, {})
        msf = set(M.get("supported_forms", []))
        mlv = {fm: sorted(d.get("lv") for d in lst)
               for fm, lst in (M.get("difficulty_levels") or {}).items()}
        blueprint = M.get("execute_blueprint", "?")
        for f in L["forms"]:
            fm = f["form"]
            slv = sorted(lv["level"] for lv in f["levels"])
            if fm not in SYS_FORMS:
                cat = "new_form"
            elif fm not in msf:
                cat = "wire_only"
            elif slv != mlv.get(fm, []):
                cat = "level_remap"
            else:
                cat = "ok"
            cells.append(dict(lesson=lid, section=L["section"], form=fm,
                              spec_levels=slv, map_levels=mlv.get(fm, []),
                              blueprint=blueprint, category=cat))
    return cells


def main():
    cells = classify()
    cat = Counter(c["category"] for c in cells)
    print(f"総 form-cell: {len(cells)}")
    for k in ("ok", "wire_only", "level_remap", "new_form"):
        print(f"  {k:12s}: {cat.get(k,0)}")
    print("\n--- new_form の内訳(form × その単元の現行blueprint) ---")
    nf = Counter((c["form"], c["blueprint"]) for c in cells if c["category"] == "new_form")
    for (fm, bp), n in nf.most_common():
        print(f"  {n:3d}  {fm:12s} <- {bp}")
    # per-cell 一覧(new_form/wire_only を優先表示)
    print("\n--- new_form セル一覧(lesson form spec_levels blueprint) ---")
    for c in cells:
        if c["category"] == "new_form":
            print(f"  {c['lesson']:9s} {c['form']:12s} Lv{c['spec_levels']}  {c['blueprint']}")


if __name__ == "__main__":
    main()
