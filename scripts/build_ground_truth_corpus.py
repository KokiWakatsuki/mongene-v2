"""ground truth コーパス構築スクリプト（LLMフリー）。

`docs/phase2_eval_gates_spec.md` §2b-1 / `docs/rework_plan_2026-07-06.md` §フェーズ2 の実装。

`master_data/mapping.json` の全 lesson × 全 supported_forms を走査し、各 (lesson, form) について
難易度 min/mid/max の3レベルで `/problems/inspect` 相当（LLM翻訳前の SymPy 生データ）を生成し、
`tests/fixtures/reference_corpus/ground_truth/{lesson}_{form}_{level}.json` に保存する。

**LLM は一切呼ばない**（SKIP_LLM_IN_TESTS=true を強制）。

使い方:
    SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/build_ground_truth_corpus.py
    SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/build_ground_truth_corpus.py --lesson g1_l1 --form word_problem
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

# LLM を絶対に呼ばないことをこのスクリプトの前提として強制する。
os.environ["SKIP_LLM_IN_TESTS"] = "true"

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
CORPUS_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth"

LEVEL_LABELS = ("min", "mid", "max")


def _pick_levels(lesson_mapping: dict[str, Any], form: str) -> dict[str, int]:
    """(lesson, form) の difficulty_levels から min/mid/max に対応する lv 番号を選ぶ。

    lv が1つしか無い場合は min=mid=max=そのlv とする（呼び出し側で単調性 N/A 扱いにできるよう
    そのまま記録する）。
    """
    difficulty_levels = lesson_mapping.get("difficulty_levels", {}) or {}
    levels = difficulty_levels.get(form)
    if levels:
        lv_list = sorted({lv["lv"] for lv in levels if "lv" in lv})
    else:
        lv_list = [1]

    if not lv_list:
        lv_list = [1]

    lo = lv_list[0]
    hi = lv_list[-1]
    mid = lv_list[len(lv_list) // 2]
    return {"min": lo, "mid": mid, "max": hi}


def _inspect(client, lesson_id: str, lesson_mapping: dict[str, Any], form: str, level: int) -> dict[str, Any]:
    payload = {
        "curriculum": {"grade": lesson_mapping["grade"], "lesson_ids": [lesson_id]},
        "problem_form": form,
        "target_level": level,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/inspect", json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"inspect failed status={r.status_code} body={r.text[:500]}")
    return r.json()


def build_corpus(
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
    out_dir: Path = CORPUS_DIR,
) -> dict[str, Any]:
    """全 (lesson, form, level) を走査して ground truth JSON を書き出す。

    戻り値: {"generated": [...], "failed": [...]} のサマリ。
    """
    assert os.environ.get("SKIP_LLM_IN_TESTS", "").lower() in ("1", "true", "yes"), (
        "build_ground_truth_corpus は LLM フリーが前提。SKIP_LLM_IN_TESTS が有効になっていません。"
    )

    # import はここで行う（SKIP_LLM_IN_TESTS を先に環境変数へ設定した後にする必要があるため）
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    lesson_ids = sorted(mapping.keys())
    if lesson_filter:
        lesson_ids = [lid for lid in lesson_ids if lid == lesson_filter]

    for lesson_id in lesson_ids:
        lesson_mapping = mapping[lesson_id]
        forms = lesson_mapping.get("supported_forms", []) or []
        if form_filter:
            forms = [f for f in forms if f == form_filter]

        for form in forms:
            levels = _pick_levels(lesson_mapping, form)
            for level_label in LEVEL_LABELS:
                level_num = levels[level_label]
                key = f"{lesson_id}_{form}_{level_label}"
                try:
                    data = _inspect(client, lesson_id, lesson_mapping, form, level_num)
                    data["_difficulty_label"] = level_label
                    data["_target_level"] = level_num
                    data["_lesson_id"] = lesson_id
                    data["_problem_form"] = form
                    out_path = out_dir / f"{key}.json"
                    out_path.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    generated.append(
                        {
                            "lesson_id": lesson_id,
                            "form": form,
                            "level_label": level_label,
                            "target_level": level_num,
                            "path": str(out_path.relative_to(REPO_ROOT)),
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - 失敗は握りつぶさず記録して続行
                    failed.append(
                        {
                            "lesson_id": lesson_id,
                            "form": form,
                            "level_label": level_label,
                            "target_level": level_num,
                            "error": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc(),
                        }
                    )

    return {"generated": generated, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", default=None, help="この lesson_id だけ生成する（デバッグ用）")
    parser.add_argument("--form", default=None, help="この problem_form だけ生成する（デバッグ用）")
    parser.add_argument(
        "--out-dir",
        default=str(CORPUS_DIR),
        help="出力先ディレクトリ（デフォルト: tests/fixtures/reference_corpus/ground_truth）",
    )
    args = parser.parse_args()

    summary = build_corpus(
        lesson_filter=args.lesson,
        form_filter=args.form,
        out_dir=Path(args.out_dir),
    )

    n_gen = len(summary["generated"])
    n_fail = len(summary["failed"])
    print(f"生成成功: {n_gen} / 失敗: {n_fail}")

    if summary["failed"]:
        print("\n--- 失敗一覧 ---")
        for f in summary["failed"]:
            print(f"  {f['lesson_id']} / {f['form']} / {f['level_label']}(lv={f['target_level']}): {f['error']}")

    # 失敗ログをJSONでも保存（run_gates.py やレポートから参照できるように）
    fail_log_path = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth_build_failures.json"
    fail_log_path.parent.mkdir(parents=True, exist_ok=True)
    fail_log_path.write_text(
        json.dumps(summary["failed"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n失敗ログ: {fail_log_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
