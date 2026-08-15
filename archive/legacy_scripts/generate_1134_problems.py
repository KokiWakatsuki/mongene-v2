"""
1134問生成スクリプト
forms_research.csv の 378 (lesson_id, form) × 3難易度 = 1134 問を生成し
reports/generated_problems.jsonl に保存する。
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
import importlib
import json
import pkgutil
import tempfile
import traceback
from pathlib import Path

# ===== Atom 登録（import 順に依存あり）=====
import apps.api.src.atoms.noun as _noun_pkg
import apps.api.src.atoms.verb as _verb_pkg

for _, _name, _ in pkgutil.iter_modules(_noun_pkg.__path__):
    importlib.import_module(f"apps.api.src.atoms.noun.{_name}")
for _, _name, _ in pkgutil.iter_modules(_verb_pkg.__path__):
    importlib.import_module(f"apps.api.src.atoms.verb.{_name}")

from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.exceptions import NoCompatibleBlueprintError
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest

# ===== 設定 =====
OUTPUT_PATH = Path("reports/generated_problems.jsonl")
MAPPING_PATH = Path("master_data/mapping.json")
CSV_PATH = Path("reports/forms_research.csv")

from apps.api.src.core.runner.difficulty_reconciler import get_form_range_from_y_base


def _adaptive_targets(y_base: int, form: str) -> dict[str, list[int]]:
    """レッスン・フォームの有効難易度範囲 [lo, hi] を使って min/mid/max を設定する。"""
    lo, hi = get_form_range_from_y_base(y_base, form)
    span = max(1, hi - lo)
    min_t = lo
    mid_t = lo + span // 3
    max_t = lo + 2 * span // 3
    # fallback リストは各ターゲット付近の値を降順に
    return {
        "min": [min_t, max(1, min_t - 2), max(1, min_t - 4)],
        "mid": [mid_t, max(min_t, mid_t - 3), max(min_t, mid_t - 6)],
        "max": [max_t, max(mid_t, max_t - 3), max(mid_t, max_t - 6), mid_t],
    }


def make_runner(tmp_dir: str) -> BlueprintRunner:
    return BlueprintRunner(
        dedup=DuplicationGuard(db_path=f"{tmp_dir}/dedup.db"),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=10,
    )


def generate_one(
    runner: BlueprintRunner,
    lesson_id: str,
    form: str,
    difficulty_label: str,
    lesson_mapping: dict,
) -> dict:
    """1問を生成して結果dictを返す。失敗時は error フィールドを持つ。"""
    y_base = int(lesson_mapping.get("y_base", 5))
    targets = _adaptive_targets(y_base, form)[difficulty_label]

    for target in targets:
        try:
            req = GenerationRequest(
                target_difficulty=target,
                problem_form=form,
                lesson_id=lesson_id,
            )
            result = runner.run(req, lesson_mapping)
            mr = result.middle_representation
            return {
                "lesson_id": lesson_id,
                "title": lesson_mapping.get("title", ""),
                "large_unit": lesson_mapping.get("large_unit", ""),
                "grade": lesson_mapping.get("grade", 0),
                "form": form,
                "difficulty_label": difficulty_label,
                "difficulty_target": target,
                "difficulty_score": mr.difficulty_score,
                "blueprint_id": mr.blueprint_id,
                "problem_text": result.problem_text,
                "sub_question_texts": result.sub_question_texts,
                "explanation_text": result.explanation_text,
                "status": "ok",
            }
        except NoCompatibleBlueprintError as e:
            continue  # 次の（低い）難易度で再試行
        except Exception as e:
            return {
                "lesson_id": lesson_id,
                "form": form,
                "difficulty_label": difficulty_label,
                "difficulty_target": target,
                "status": "error",
                "error": str(e),
            }

    return {
        "lesson_id": lesson_id,
        "form": form,
        "difficulty_label": difficulty_label,
        "difficulty_target": targets[-1],
        "status": "error",
        "error": "全ての難易度候補で NoCompatibleBlueprintError",
    }


def main() -> None:
    # mapping 読み込み
    with open(MAPPING_PATH) as f:
        mapping: dict = json.load(f)

    # CSV から 378 (lesson_id, form) を取得
    form_cols = ["calculation", "word_problem", "proof", "knowledge", "visual"]
    combinations: list[tuple[str, str]] = []
    with open(CSV_PATH) as f:
        for row in csv.DictReader(f):
            for form in form_cols:
                if row[form] == "1":
                    combinations.append((row["lesson_id"], form))

    total = len(combinations) * 3
    print(f"生成対象: {len(combinations)} combinations × 3 難易度 = {total} 問")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ok = 0
    error = 0
    written = 0

    # 既存の結果をスキップするためのキー集合
    done_keys: set[tuple[str, str, str]] = set()
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    done_keys.add((rec["lesson_id"], rec["form"], rec["difficulty_label"]))
                except Exception:
                    pass
        print(f"  既存 {len(done_keys)} 件をスキップ")

    with tempfile.TemporaryDirectory() as tmp:
        runner = make_runner(tmp)

        with open(OUTPUT_PATH, "a") as out_f:
            for i, (lesson_id, form) in enumerate(combinations):
                if lesson_id not in mapping:
                    print(f"  [SKIP] {lesson_id} not in mapping")
                    continue

                lesson_map = mapping[lesson_id]

                for diff_label in ["min", "mid", "max"]:
                    key = (lesson_id, form, diff_label)
                    if key in done_keys:
                        continue

                    n = written + len(done_keys) + 1
                    if n % 50 == 0 or n <= 5:
                        print(f"[{n}/{total}] {lesson_id} {form} {diff_label}")

                    record = generate_one(runner, lesson_id, form, diff_label, lesson_map)
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_f.flush()
                    written += 1

                    if record["status"] == "ok":
                        ok += 1
                    else:
                        error += 1
                        print(f"  [ERR] {lesson_id} {form} {diff_label}: {record.get('error','')[:80]}")

    print(f"\n=== 完了: OK={ok}, ERR={error}, 合計={ok+error} ===")
    print(f"出力: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
