"""「明らかに違う問題」を、family YAML から**静的に**数える。

生成を回さずに数えられる。要るのは「どの列挙が話を変える軸で、どれが中身の
差し替えか」の判断だけで、それは**設計が記録していない**（params の名前の慣習で
しか見分けられない）。だからここで名前の規約として明文化する。

  型の軸    `*_set`（concept_set を除く）・`term_kinds`
            場面・命題の型・図形・証明法など、**話の骨格が変わる**もの
  中身      `*_candidates`・`*_range`・`*_domain`・`*_pool`・`concept_set`
            速さ・品物・人名・色・文字・数値の範囲。骨格は変わらない

実行: PYTHONPATH=engine_core .venv/bin/python records/work/count_types_static.py
"""
from __future__ import annotations

import glob
from collections import Counter, defaultdict

import yaml

_NOT_A_TYPE_AXIS = {"concept_set"}


def is_type_axis(name: str) -> bool:
    if name in _NOT_A_TYPE_AXIS:
        return False
    return name.endswith("_set") or name == "term_kinds"


def main() -> None:
    per_cell: dict[str, int] = {}
    axes_used: Counter[str] = Counter()
    detail: dict[str, list[str]] = defaultdict(list)

    for path in sorted(glob.glob("engine_core/engine/curriculum/math/families/*.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        family = doc.get("family", path)
        unit_form = family.removeprefix("math.")
        for lv, spec in (doc.get("levels") or {}).items():
            n = 1
            names: list[str] = []
            for k, v in (spec.get("params") or {}).items():
                if isinstance(v, list) and len(v) > 1 and is_type_axis(k):
                    n *= len(v)
                    names.append(f"{k}({len(v)})")
                    axes_used[k] += 1
            cell = f"{unit_form}.Lv{lv}"
            per_cell[cell] = n
            detail[cell] = names

    total_cells = len(per_cell)
    total_types = sum(per_cell.values())
    multi = {c: n for c, n in per_cell.items() if n > 1}

    print(f"セル {total_cells} 個")
    print(f"**明らかに違う問題 {total_types} 個**（型の軸の直積を、全セルで足したもの）")
    print(f"  うち 型が1つだけのセル: {total_cells - len(multi)}")
    print(f"      型が複数あるセル  : {len(multi)}")
    print("\n--- 使われている型の軸 ---")
    for name, c in axes_used.most_common():
        print(f"  {c:3d} セル  {name}")
    print("\n--- 型が多いセル 上位20 ---")
    for cell, n in sorted(multi.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  {n:4d}  {cell}   {'・'.join(detail[cell])}")


if __name__ == "__main__":
    main()
