"""決定論ゲート全走査スクリプト（フェーズ2 §2b-1 / §2b-2）。

- **G6（難易度レベル健全性）**: `master_data/mapping.json` を直接走査する。
  - G6-b（レベル非崩壊）: 生成不要・静的データ解析。全 385 (lesson,form) を即時判定できる。
  - G6-a（制約適合）: 各 (lesson, form, Lv) を `target_level=Lv` で複数 seed `/inspect` 生成し、
    宣言した atom_constraints が実際に反映されているか判定する（LLMは呼ばない）。
- **G1/G2/G3/G4/G5/G7（1:1ゲート）**: `tests/fixtures/reference_corpus/product/` に対応する
  product JSON があれば走らせる（無ければそのキーはスキップし、レポートに「product無し」件数として記録）。

**LLM は一切呼ばない**。G6-a の生成は `/problems/inspect`（SKIP_LLM_IN_TESTS=true 相当）のみ使う。

使い方:
    .venv/bin/python scripts/run_gates.py
    .venv/bin/python scripts/run_gates.py --out reports/gate_report.md
    .venv/bin/python scripts/run_gates.py --skip-g6a   # G6-aの生成をスキップ（高速・G6-bのみ）
    .venv/bin/python scripts/run_gates.py --seeds 10   # G6-aのseed数を変更（デフォルト5）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
GROUND_TRUTH_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth"
PRODUCT_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "product"
DEFAULT_REPORT_PATH = REPO_ROOT / "reports" / "gate_report.md"

DEFAULT_G6A_SEEDS = 5

# ground truth ファイル名: {lesson}_{form}_{level}.json（1:1ゲート用コーパスの命名規則）
_GT_FILENAME_RE = re.compile(r"^(?P<lesson>.+)_(?P<form>word_problem|calculation|proof|knowledge|visual)_(?P<level>min|mid|max)\.json$")

ONE_TO_ONE_GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G7")


def _import_gates():
    from scripts.eval_gates import g1_answer_leakage, g2_number_consistency, g3_answer_correctness
    from scripts.eval_gates import g4_form_conformance, g5_syllabus_range, g7_render_sanity

    return {
        "G1": g1_answer_leakage.check,
        "G2": g2_number_consistency.check,
        "G3": g3_answer_correctness.check,
        "G4": g4_form_conformance.check,
        "G5": g5_syllabus_range.check,
        "G7": g7_render_sanity.check,
    }


def load_mapping(path: Path = MAPPING_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# G6-b: レベル非崩壊（生成不要・mapping.json 静的解析）
# ---------------------------------------------------------------------------


DEFAULT_G6B_SAMPLES = 6


def run_g6b_distinctness(
    mapping: dict[str, Any],
    client: Optional[Any] = None,
    n_samples: int = DEFAULT_G6B_SAMPLES,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """全 (lesson, form) について G6-b を評価する。難易度レベル未定義の (lesson,form) は N/A。

    `client` が渡されれば生成ベース判定（静的シグネチャ重複候補のみ `/inspect` で複数回生成し
    フィンガープリントを比較）。渡されなければ静的シグネチャのみのフォールバック判定になる。
    """
    from scripts.eval_gates.g6_difficulty_level_soundness import check_distinctness

    sample_fn = None
    if client is not None:
        def sample_fn(lesson_id: str, form: str, lv: int) -> dict[str, Any]:
            grade = mapping[lesson_id].get("grade", 1)
            return _inspect_once(client, lesson_id, grade, form, lv)

    results: list[dict[str, Any]] = []
    lesson_ids = sorted(mapping.keys())
    if lesson_filter:
        lesson_ids = [lid for lid in lesson_ids if lid == lesson_filter]

    for lesson_id in lesson_ids:
        lesson_mapping = mapping[lesson_id]
        forms = lesson_mapping.get("supported_forms", []) or []
        if form_filter:
            forms = [f for f in forms if f == form_filter]
        difficulty_levels = lesson_mapping.get("difficulty_levels", {}) or {}
        for form in forms:
            level_defs = difficulty_levels.get(form, []) or []
            gate_result = check_distinctness(lesson_id, form, level_defs, sample_fn=sample_fn, n_samples=n_samples)
            results.append(
                {
                    "lesson_id": lesson_id,
                    "form": form,
                    "verdict": gate_result.verdict,
                    "reason": gate_result.reason,
                    "details": gate_result.details,
                }
            )
    return results


# ---------------------------------------------------------------------------
# G6-a: 制約適合（生成あり・LLMフリー、/inspect 複数seed）
# ---------------------------------------------------------------------------


def _make_inspect_client():
    """SKIP_LLM_IN_TESTS=true を強制した状態で TestClient を作る。"""
    os.environ["SKIP_LLM_IN_TESTS"] = "true"
    from fastapi.testclient import TestClient
    from apps.api.main import app

    return TestClient(app)


def _inspect_once(
    client, lesson_id: str, grade: int, form: str, level: int, seed: Optional[int] = None
) -> dict[str, Any]:
    payload = {
        "curriculum": {"grade": grade, "lesson_ids": [lesson_id]},
        "problem_form": form,
        "target_level": level,
        "unlearned_lesson_ids": [],
    }
    if seed is not None:
        payload["seed"] = seed
    r = client.post("/problems/inspect", json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"inspect failed status={r.status_code} body={r.text[:300]}")
    return r.json()


def run_g6a_conformance(
    mapping: dict[str, Any],
    n_seeds: int = DEFAULT_G6A_SEEDS,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
    client: Optional[Any] = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """全 (lesson, form, Lv) を複数seedで /inspect 生成し G6-a を評価する。

    戻り値: (results, generation_failures)
    """
    from scripts.eval_gates.g6_difficulty_level_soundness import check_conformance

    if client is None:
        client = _make_inspect_client()

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    lesson_ids = sorted(mapping.keys())
    if lesson_filter:
        lesson_ids = [lid for lid in lesson_ids if lid == lesson_filter]

    for lesson_id in lesson_ids:
        lesson_mapping = mapping[lesson_id]
        grade = lesson_mapping.get("grade", 1)
        forms = lesson_mapping.get("supported_forms", []) or []
        if form_filter:
            forms = [f for f in forms if f == form_filter]
        difficulty_levels = lesson_mapping.get("difficulty_levels", {}) or {}
        base_atom_constraints = lesson_mapping.get("atom_constraints", {}) or {}

        for form in forms:
            level_defs = difficulty_levels.get(form, []) or []
            for lv_def in level_defs:
                lv = lv_def.get("lv")
                samples: list[dict[str, Any]] = []
                gen_error: Optional[str] = None
                for seed_idx in range(n_seeds):
                    try:
                        data = _inspect_once(client, lesson_id, grade, form, lv)
                        samples.append(data)
                    except Exception as exc:  # noqa: BLE001 - 失敗は記録して続行
                        gen_error = f"{type(exc).__name__}: {exc}"
                        failures.append(
                            {
                                "lesson_id": lesson_id,
                                "form": form,
                                "level_label": f"Lv{lv}",
                                "target_level": lv,
                                "error": gen_error,
                            }
                        )
                        # 同じ(lesson,form,lv)で毎回失敗する可能性が高いので、
                        # 最初の失敗で残りseedを打ち切ってよい（実装不可等は決定論的に落ちるため）。
                        break

                gate_result = check_conformance(
                    lesson_id, form, lv, lv_def, base_atom_constraints, samples
                )
                results.append(
                    {
                        "lesson_id": lesson_id,
                        "form": form,
                        "lv": lv,
                        "verdict": gate_result.verdict,
                        "reason": gate_result.reason,
                        "details": gate_result.details,
                        "n_samples": len(samples),
                        "generation_error": gen_error if not samples else None,
                    }
                )

    return results, failures


# ---------------------------------------------------------------------------
# 1:1ゲート（G1/G2/G3/G4/G5/G7、product 必要）
# ---------------------------------------------------------------------------


def load_ground_truth_corpus(corpus_dir: Path = GROUND_TRUTH_DIR) -> dict[tuple[str, str], dict[str, Any]]:
    """`{lesson}_{form}_{level}.json` を読み、`{(lesson, form): {level: data}}` に整理する。"""
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    if not corpus_dir.exists():
        return {}
    for path in sorted(corpus_dir.glob("*.json")):
        m = _GT_FILENAME_RE.match(path.name)
        if not m:
            continue  # ground_truth_build_failures.json 等は無視
        lesson = m.group("lesson")
        form = m.group("form")
        level = m.group("level")
        data = json.loads(path.read_text(encoding="utf-8"))
        grouped[(lesson, form)][level] = data
    return grouped


def load_product_corpus(product_dir: Path = PRODUCT_DIR) -> dict[tuple[str, str], dict[str, Any]]:
    """product 側コーパス（あれば）を同じキー構造で読む。無ければ空 dict。"""
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    if not product_dir.exists():
        return {}
    for path in sorted(product_dir.glob("*.json")):
        m = _GT_FILENAME_RE.match(path.name)
        if not m:
            continue
        lesson = m.group("lesson")
        form = m.group("form")
        level = m.group("level")
        data = json.loads(path.read_text(encoding="utf-8"))
        grouped[(lesson, form)][level] = data
    return grouped


def run_one_to_one_gates(
    ground_truth_grouped: dict[tuple[str, str], dict[str, Any]],
    product_grouped: dict[tuple[str, str], dict[str, Any]],
    gate_fns: dict[str, Any],
) -> list[dict[str, Any]]:
    """product が存在するキーだけ G1/G2/G3/G4/G5/G7 を走らせる。"""
    results: list[dict[str, Any]] = []
    for (lesson, form), gt_levels in sorted(ground_truth_grouped.items()):
        product_levels = product_grouped.get((lesson, form), {})
        for level in ("min", "mid", "max"):
            gt = gt_levels.get(level)
            product = product_levels.get(level)
            if gt is None:
                continue
            if product is None:
                results.append(
                    {
                        "lesson_id": lesson,
                        "form": form,
                        "level": level,
                        "product_available": False,
                        "gates": {},
                    }
                )
                continue
            gate_verdicts = {}
            for gate_id, fn in gate_fns.items():
                result = fn(product, gt)
                gate_verdicts[gate_id] = {"verdict": result.verdict, "reason": result.reason}
            results.append(
                {
                    "lesson_id": lesson,
                    "form": form,
                    "level": level,
                    "product_available": True,
                    "gates": gate_verdicts,
                }
            )
    return results


def _build_generation_failure_summary() -> list[dict[str, Any]]:
    fail_log = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth_build_failures.json"
    if not fail_log.exists():
        return []
    return json.loads(fail_log.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# レポート出力
# ---------------------------------------------------------------------------


def render_report(
    g6b_results: list[dict[str, Any]],
    g6a_results: list[dict[str, Any]],
    g6a_failures: list[dict[str, Any]],
    one_to_one_results: list[dict[str, Any]],
    generation_failures: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# 決定論ゲート走査レポート（フェーズ2 run_gates.py）")
    lines.append("")
    lines.append("LLM は一切使用していません。G6 は `master_data/mapping.json` の静的解析（G6-b）と")
    lines.append("`/problems/inspect`（SKIP_LLM_IN_TESTS=true、G6-a）のみで走ります。")
    lines.append("")

    # --- G6-b レベル非崩壊 ---
    lines.append("## G6-b レベル非崩壊（distinctness、生成不要・静的データ解析）")
    lines.append("")
    total = len(g6b_results)
    pass_count = sum(1 for r in g6b_results if r["verdict"] == "PASS")
    fail_count = sum(1 for r in g6b_results if r["verdict"] == "FAIL")
    na_count = sum(1 for r in g6b_results if r["verdict"] == "N/A")
    lines.append(f"- 対象 (lesson, form) 件数: {total}")
    lines.append(f"- PASS（全Lv相異）: {pass_count}")
    lines.append(f"- FAIL（Lv定義が崩壊）: {fail_count}")
    lines.append(f"- N/A（Lv未定義 or Lv1個のみ）: {na_count}")
    lines.append("")

    lines.append("### form別内訳")
    lines.append("")
    lines.append("| form | total | PASS | FAIL | N/A |")
    lines.append("|---|---|---|---|---|")
    by_form: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in g6b_results:
        by_form[r["form"]].append(r)
    for form, rows in sorted(by_form.items()):
        t = len(rows)
        p = sum(1 for r in rows if r["verdict"] == "PASS")
        f = sum(1 for r in rows if r["verdict"] == "FAIL")
        n = sum(1 for r in rows if r["verdict"] == "N/A")
        lines.append(f"| {form} | {t} | {p} | {f} | {n} |")
    lines.append("")

    lines.append("### G6-b FAIL 一覧（レベル定義が崩壊した lesson, form）")
    lines.append("")
    fails = [r for r in g6b_results if r["verdict"] == "FAIL"]
    if not fails:
        lines.append("(なし)")
    else:
        lines.append("| lesson_id | form | reason |")
        lines.append("|---|---|---|")
        for r in fails:
            lines.append(f"| {r['lesson_id']} | {r['form']} | {r['reason']} |")
    lines.append("")

    # --- G6-a 制約適合 ---
    lines.append("## G6-a 制約適合（conformance、複数seed生成・LLMゼロ）")
    lines.append("")
    total_a = len(g6a_results)
    pass_a = sum(1 for r in g6a_results if r["verdict"] == "PASS")
    fail_a = sum(1 for r in g6a_results if r["verdict"] == "FAIL")
    na_a = sum(1 for r in g6a_results if r["verdict"] == "N/A")
    lines.append(f"- 対象 (lesson, form, Lv) 件数: {total_a}")
    lines.append(f"- PASS: {pass_a}")
    lines.append(f"- FAIL（宣言制約がランナーに効いていない実バグ）: {fail_a}")
    lines.append(f"- N/A（観測不能 or 生成失敗）: {na_a}")
    lines.append("")

    lines.append("### G6-a FAIL 一覧（制約違反 = 実バグ候補）")
    lines.append("")
    fails_a = [r for r in g6a_results if r["verdict"] == "FAIL"]
    if not fails_a:
        lines.append("(なし)")
    else:
        lines.append("| lesson_id | form | Lv | reason |")
        lines.append("|---|---|---|---|")
        for r in fails_a:
            lines.append(f"| {r['lesson_id']} | {r['form']} | {r['lv']} | {r['reason']} |")
    lines.append("")

    lines.append("### G6-a 生成失敗一覧（NoCompatibleBlueprintError 等）")
    lines.append("")
    lines.append(f"- 失敗件数: {len(g6a_failures)}")
    lines.append("")
    if g6a_failures:
        lines.append("| lesson_id | form | level | error |")
        lines.append("|---|---|---|---|")
        for f in g6a_failures:
            err = f.get("error", "").replace("\n", " ")
            lines.append(f"| {f['lesson_id']} | {f['form']} | {f['level_label']} | {err} |")
    lines.append("")

    # --- 1:1 ゲート ---
    lines.append("## G1/G2/G3/G4/G5/G7（1:1ゲート、product 必要）")
    lines.append("")
    with_product = [r for r in one_to_one_results if r["product_available"]]
    without_product = [r for r in one_to_one_results if not r["product_available"]]
    lines.append(f"- product あり: {len(with_product)} 件")
    lines.append(f"- product なし（今回はスキップ・2b-2で生成予定）: {len(without_product)} 件")
    lines.append("")
    if with_product:
        lines.append("### 形式別・ゲート別 通過率マトリクス")
        lines.append("")
        lines.append("| form | " + " | ".join(ONE_TO_ONE_GATE_IDS) + " |")
        lines.append("|---|" + "---|" * len(ONE_TO_ONE_GATE_IDS))
        by_form_11: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in with_product:
            by_form_11[r["form"]].append(r)
        for form, rows in sorted(by_form_11.items()):
            cells = []
            for gate_id in ONE_TO_ONE_GATE_IDS:
                verdicts = [row["gates"].get(gate_id, {}).get("verdict") for row in rows]
                applicable = [v for v in verdicts if v not in (None, "N/A")]
                p = sum(1 for v in applicable if v == "PASS")
                t = len(applicable)
                cells.append(f"{p}/{t}" if t else "N/A")
            lines.append(f"| {form} | " + " | ".join(cells) + " |")
        lines.append("")
    else:
        lines.append("(product コーパスが無いため今回は集計なし。2b-2 で `tests/fixtures/reference_corpus/product/` を作れば自動的にこのセクションが埋まる)")
        lines.append("")

    # --- ground truth 生成失敗一覧（1:1ゲート用コーパス側） ---
    lines.append("## ground truth 生成の失敗一覧（1:1ゲート用コーパス）")
    lines.append("")
    lines.append(f"- 失敗件数: {len(generation_failures)}")
    lines.append("")
    if generation_failures:
        lines.append("| lesson_id | form | level | error |")
        lines.append("|---|---|---|---|")
        for f in generation_failures:
            err = f.get("error", "").replace("\n", " ")
            lines.append(f"| {f['lesson_id']} | {f['form']} | {f['level_label']} | {err} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", default=str(MAPPING_PATH))
    parser.add_argument("--ground-truth-dir", default=str(GROUND_TRUTH_DIR))
    parser.add_argument("--product-dir", default=str(PRODUCT_DIR))
    parser.add_argument("--out", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--seeds", type=int, default=DEFAULT_G6A_SEEDS, help="G6-a の seed 数")
    parser.add_argument(
        "--g6b-samples", type=int, default=DEFAULT_G6B_SAMPLES, help="G6-b 生成ベース判定の1Lvあたり生成回数"
    )
    parser.add_argument("--skip-g6a", action="store_true", help="G6-a（生成あり）をスキップし G6-bのみ走らせる")
    parser.add_argument(
        "--skip-g6b-generation",
        action="store_true",
        help="G6-b の生成ベース判定をスキップし静的シグネチャのみで判定する（旧挙動・高速）",
    )
    parser.add_argument("--lesson", default=None, help="この lesson_id だけ G6-a/G6-b を走らせる（デバッグ用）")
    parser.add_argument("--form", default=None, help="この problem_form だけ G6-a/G6-b を走らせる（デバッグ用）")
    args = parser.parse_args()

    gate_fns = _import_gates()
    mapping = load_mapping(Path(args.mapping))

    # G6-a と G6-b の生成ベース判定は同じ TestClient を使い回す（プロセス起動コストを1回に）。
    shared_client = None
    if not args.skip_g6a or not args.skip_g6b_generation:
        shared_client = _make_inspect_client()

    g6b_client = None if args.skip_g6b_generation else shared_client
    g6b_results = run_g6b_distinctness(
        mapping,
        client=g6b_client,
        n_samples=args.g6b_samples,
        lesson_filter=args.lesson,
        form_filter=args.form,
    )

    if args.skip_g6a:
        g6a_results: list[dict[str, Any]] = []
        g6a_failures: list[dict[str, Any]] = []
    else:
        g6a_results, g6a_failures = run_g6a_conformance(
            mapping, n_seeds=args.seeds, lesson_filter=args.lesson, form_filter=args.form, client=shared_client
        )

    ground_truth_grouped = load_ground_truth_corpus(Path(args.ground_truth_dir))
    product_grouped = load_product_corpus(Path(args.product_dir))
    one_to_one_results = run_one_to_one_gates(ground_truth_grouped, product_grouped, gate_fns)
    generation_failures = _build_generation_failure_summary()

    report = render_report(g6b_results, g6a_results, g6a_failures, one_to_one_results, generation_failures)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    total_b = len(g6b_results)
    pass_b = sum(1 for r in g6b_results if r["verdict"] == "PASS")
    fail_b = sum(1 for r in g6b_results if r["verdict"] == "FAIL")
    print(f"G6-b: {pass_b}/{total_b} PASS, {fail_b} FAIL（崩壊）")
    if not args.skip_g6a:
        total_a = len(g6a_results)
        pass_a = sum(1 for r in g6a_results if r["verdict"] == "PASS")
        fail_a = sum(1 for r in g6a_results if r["verdict"] == "FAIL")
        print(f"G6-a: {pass_a}/{total_a} PASS, {fail_a} FAIL（制約違反）, 生成失敗 {len(g6a_failures)} 件")
    print(f"レポート: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
