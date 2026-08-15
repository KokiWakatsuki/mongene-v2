"""form/blueprint 契約検証スクリプト（LLMフリー・可視化用・非破壊）

master_data/mapping.json の全 lesson について、宣言された supported_forms の
各 form ごとに BlueprintRunner.run() と同じ候補選択ロジックで bp_id 群を求め、
その form を supported_forms に持つ blueprint が候補に1つも無いケース
（= 静かな calculation フォールバックが起きるケース）を「違反」として収集する。

このスクリプトはオフラインの検査専用であり、違反があってもアプリを落とさない。
デフォルトでは違反件数に関わらず終了コード 0（可視化用途）。
`--strict` を指定した場合のみ、違反 > 0 で終了コード 1 を返す。

使い方:
    .venv/bin/python scripts/validate_form_blueprint_contract.py
    .venv/bin/python scripts/validate_form_blueprint_contract.py --json
    .venv/bin/python scripts/validate_form_blueprint_contract.py --strict
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"

ALL_FORMS = ["word_problem", "calculation", "proof", "knowledge", "visual"]


def _candidate_bp_ids(lesson_mapping: Dict[str, Any], form: str) -> List[str]:
    """BlueprintRunner.run() と同じ候補選択ロジックで bp_id 群を返す（フィルタ前）。"""
    bp_by_form = lesson_mapping.get("execute_blueprint_by_form", {})
    if form in bp_by_form:
        return [bp_by_form[form]]

    blueprints_list = lesson_mapping.get("execute_blueprints")
    if blueprints_list and isinstance(blueprints_list, list) and len(blueprints_list) > 1:
        return list(blueprints_list)

    bp_id = lesson_mapping.get(
        "execute_blueprint", blueprints_list[0] if blueprints_list else "BasicCalculationStructure"
    )
    return [bp_id]


def _level_override_bp_ids(lesson_mapping: Dict[str, Any], form: str) -> List[str]:
    """difficulty_levels[form] の blueprint_override が指定する bp_id 群（あれば）。"""
    levels = lesson_mapping.get("difficulty_levels", {}).get(form, [])
    overrides = []
    for lv_def in levels:
        override = lv_def.get("blueprint_override")
        if override:
            overrides.append(override)
    return overrides


def validate_contract() -> Dict[str, Any]:
    """全 lesson × supported_forms を走査し、違反を収集する。

    戻り値:
        {
            "total_declared": int,
            "total_violations": int,
            "by_form": {form: {"declared": int, "violations": int}},
            "violations": [{"lesson_id": ..., "form": ..., "candidate_bp_ids": [...]}],
        }
    """
    from apps.api.src.blueprints.registry import load_blueprint

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    by_form: Dict[str, Dict[str, int]] = {f: {"declared": 0, "violations": 0} for f in ALL_FORMS}
    violations: List[Dict[str, Any]] = []
    total_declared = 0

    # blueprint_id -> supported_forms のロード結果をキャッシュ（同じ bp_id を何度もロードしない）
    bp_cache: Dict[str, List[str]] = {}

    def _supported_forms(bp_id: str) -> List[str]:
        if bp_id not in bp_cache:
            try:
                bp = load_blueprint(bp_id)
                bp_cache[bp_id] = list(bp.supported_forms)
            except Exception as e:
                # 未登録 blueprint 等。空リスト扱い（= どの form も満たさない）にして違反として拾う。
                bp_cache[bp_id] = []
        return bp_cache[bp_id]

    for lesson_id, lesson_mapping in mapping.items():
        supported_forms = lesson_mapping.get("supported_forms", [])
        for form in supported_forms:
            total_declared += 1
            if form not in by_form:
                by_form[form] = {"declared": 0, "violations": 0}
            by_form[form]["declared"] += 1

            candidate_ids = _candidate_bp_ids(lesson_mapping, form)
            candidate_ids = candidate_ids + [
                bp_id for bp_id in _level_override_bp_ids(lesson_mapping, form)
                if bp_id not in candidate_ids
            ]

            ok = any(form in _supported_forms(bp_id) for bp_id in candidate_ids)
            if not ok:
                by_form[form]["violations"] += 1
                violations.append(
                    {
                        "lesson_id": lesson_id,
                        "form": form,
                        "candidate_bp_ids": candidate_ids,
                    }
                )

    total_violations = len(violations)
    return {
        "total_declared": total_declared,
        "total_violations": total_violations,
        "by_form": by_form,
        "violations": violations,
    }


def _print_human(result: Dict[str, Any]) -> None:
    print("=== form/blueprint 契約検証 ===")
    print(f"宣言ペア総数: {result['total_declared']}")
    print(f"違反ペア総数: {result['total_violations']}")
    print()
    print("form別集計 (宣言数 / 違反数):")
    for form, stats in sorted(result["by_form"].items()):
        if stats["declared"] == 0:
            continue
        print(f"  {form:14s}: {stats['declared']:4d} / {stats['violations']:4d}")
    print()
    if result["violations"]:
        print("違反一覧 (lesson_id, form, candidate_bp_ids):")
        for v in result["violations"]:
            print(f"  {v['lesson_id']:12s} {v['form']:14s} {v['candidate_bp_ids']}")
    else:
        print("違反なし。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="機械可読な JSON で出力する")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="違反が1件でもあれば終了コード1を返す（デフォルトは常に0で可視化専用）",
    )
    args = parser.parse_args()

    result = validate_contract()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)

    if args.strict and result["total_violations"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
