"""ゴール仕様（docs/goal_spec_2026-07-12.md）の進捗を実測する CLI。

- 分母 = `curriculum/math/units.generated.yaml` の全セル（疎な有効組み合わせの正・仕様 §2）
- 分子 = `capabilities()`（spec check 済みで生成可能なセル）
- 分類 = 仕様 §3.4 の capability 16 グループ（C1〜C16）。**分類規則の変更は文書と同時に**（§3.7）。

未分類セルが 1 つでもあれば exit 1 で当該セルを列挙する（台帳の網羅性を機械検証し、
「分類から漏れたセル＝取りこぼし」を構造的に防ぐ。units.generated.yaml に新 section が
増えたときは本分類とゴール仕様 §3.4 を意識的に更新することを強制する）。

`engine.tools` は core/packs/curriculum を「読むだけ」の利用者（実装設計 §3 の依存規律）。

使い方:
  python -m engine.tools.goal_progress          # 表形式
  python -m engine.tools.goal_progress --json   # JSON（CI 連携用）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from engine.bootstrap import bootstrap
from engine.core.pipeline import capabilities

_UNITS_PATH = Path(__file__).resolve().parents[1] / "curriculum" / "math" / "units.generated.yaml"

# ゴール仕様 §3.4 の表示名（ID は表の C1〜C16 と一致させる）
_GROUP_LABELS: dict[str, str] = {
    "C1": "g1 数と式（正負・文字式・一次方程式）",
    "C2": "g2 数と式（式の計算・連立）",
    "C3": "g3 数と式（多項式・平方根・二次方程式）",
    "C4": "g1 比例・反比例",
    "C5": "g2 一次関数",
    "C6": "g3 二次関数 y=ax²",
    "C7": "g1 平面図形（作図以外）",
    "C8": "g1 空間図形",
    "C9": "g2 図形（平行と合同・三角形と四角形）",
    "C10": "g3 図形（相似・円・三平方）",
    "C11": "データ・統計（g1 分布＋g2 箱ひげ＋g3 標本）",
    "C12": "確率（g1＋g2）",
    "C13": "exam 融合の T1 部",
    "C14": "word_problem 全学年（T3）",
    "C15": "proof 全学年（T3）",
    "C16": "construction（g1 作図・M2）",
}


def _grade(unit_id: str) -> str:
    m = re.match(r"([a-z]+\d*)_", unit_id)
    if m is None:  # pragma: no cover - units.generated.yaml の ID 形式が壊れた場合のみ
        raise ValueError(f"単元 ID の形式が不正: {unit_id!r}")
    return m.group(1)


def classify(unit_id: str, section: str, form: str) -> str | None:
    """セル (unit, section, form) を仕様 §3.4 の C グループへ分類する。

    form が横断形式（word_problem/proof/construction）ならそれが優先。それ以外（T1）は
    学年 × クラスタ（section）。分類できない場合は None（呼び出し側が異常として扱う）。
    """
    if form == "word_problem":
        return "C14"
    if form == "proof":
        return "C15"
    if form == "construction":
        return "C16"
    g = _grade(unit_id)
    if g == "exam":
        return "C13"
    s = section
    if g == "g1":
        if "数と式" in s:
            return "C1"
        if "関数" in s:
            return "C4"
        if "平面図形" in s:
            return "C7"
        if "空間図形" in s:
            return "C8"
        if "データ" in s:
            return "C11" if "分布" in s else "C12"
    if g == "g2":
        if "数と式" in s:
            return "C2"
        if "関数" in s:
            return "C5"
        if "図形" in s:
            return "C9"
        if "確率" in s:
            return "C12"
        if "データ" in s:
            return "C11"
    if g == "g3":
        if "数と式" in s:
            return "C3"
        if "関数" in s:
            return "C6"
        if "図形" in s:
            return "C10"
        if "データ" in s:
            return "C11"
    return None


def build_report() -> dict[str, Any]:
    """進捗レポートを構築する（分母=units.generated.yaml・分子=capabilities()）。"""
    units_doc = yaml.safe_load(_UNITS_PATH.read_text(encoding="utf-8"))
    units: dict[str, Any] = units_doc["units"]
    bootstrap()
    covered_cells = {(c.unit, c.form, c.level) for c in capabilities()}

    group_stats: dict[str, dict[str, int]] = {
        gid: {"covered": 0, "total": 0} for gid in _GROUP_LABELS
    }
    grade_stats: dict[str, dict[str, int]] = {}
    unmapped: list[str] = []
    total = 0
    covered = 0

    for unit_id, unit in units.items():
        section = str(unit.get("section", ""))
        grade = _grade(unit_id)
        gstat = grade_stats.setdefault(grade, {"covered": 0, "total": 0})
        for form, form_def in (unit.get("forms") or {}).items():
            for level_key in form_def.get("levels") or {}:
                level = int(level_key)
                is_covered = (unit_id, form, level) in covered_cells
                total += 1
                covered += is_covered
                gstat["total"] += 1
                gstat["covered"] += is_covered
                gid = classify(unit_id, section, form)
                if gid is None:
                    unmapped.append(f"{unit_id}.{form}.Lv{level} (section={section})")
                    continue
                group_stats[gid]["total"] += 1
                group_stats[gid]["covered"] += is_covered

    groups = [
        {
            "id": gid,
            "label": _GROUP_LABELS[gid],
            "covered": st["covered"],
            "total": st["total"],
        }
        for gid, st in sorted(group_stats.items(), key=lambda kv: int(kv[0][1:]))
    ]
    return {
        "total": total,
        "covered": covered,
        "percent": round(covered / total * 100, 1) if total else 0.0,
        "groups": groups,
        "grades": grade_stats,
        "unmapped": unmapped,
    }


def _format_table(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=== ゴール進捗（docs/goal_spec_2026-07-12.md §3）===")
    for g in report["groups"]:
        pct = g["covered"] / g["total"] * 100 if g["total"] else 0.0
        lines.append(
            f"  {g['id']:<4} {g['label']:<28} {g['covered']:>3}/{g['total']:<3} ({pct:>4.0f}%)"
        )
    lines.append(
        f"  {'合計':<33} {report['covered']:>3}/{report['total']:<3} ({report['percent']:>4.1f}%)"
    )
    grade_parts = [
        f"{g} {st['covered']}/{st['total']}" for g, st in sorted(report["grades"].items())
    ]
    lines.append("  学年別: " + "  ".join(grade_parts))
    if report["unmapped"]:
        lines.append("")
        lines.append("★未分類セル（ゴール仕様 §3.4 の分類とツールの同時更新が必要）:")
        for cell in report["unmapped"]:
            lines.append(f"  ✗ {cell}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ゴール仕様の進捗実測（被覆/総数をグループ別に出力）")
    parser.add_argument("--json", action="store_true", help="JSON で出力（CI 連携用）")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_format_table(report))
    return 1 if report["unmapped"] else 0


if __name__ == "__main__":
    sys.exit(main())
