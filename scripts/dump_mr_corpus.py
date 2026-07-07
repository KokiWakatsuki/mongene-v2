"""全 lesson×form×lv の MR（LLM翻訳前の生データ）をダンプする（LLMフリー）。

`docs/HANDOFF_2026-07-06.md` §17.4 Phase A step1 の実装。質の監査ループ（題材忠実性）の
入口。全 1516 生成可能セルを pinned seed で `/problems/inspect` し、題材一致判定に必要な
要約だけを 1 行 1 セルの JSONL に落とす。**LLM は一切呼ばない**（SKIP_LLM_IN_TESTS=true 強制）。

各行のスキーマ:
    {lesson, title, large_unit, domain, grade, form, lv, lv_description,
     declared_blueprint, blueprint_id, selected_tags,
     sampled_atoms: {name: {type, dims}}, operation_names: [...],
     answers: [sympy_form...], prompt_hints: [...], difficulty_score,
     error?: str}

出力: `reports/mr_dump/mr_corpus.jsonl`（gitignore 済み・ローカル生成物）。

使い方:
    SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/dump_mr_corpus.py
    SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/dump_mr_corpus.py --lesson g1_l33
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

os.environ["SKIP_LLM_IN_TESTS"] = "true"

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus_seed import pinned_seed  # noqa: E402

MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
OUT_DIR = REPO_ROOT / "reports" / "mr_dump"
OUT_PATH = OUT_DIR / "mr_corpus.jsonl"


def _iter_cells(mapping: dict[str, Any], lesson_filter: Optional[str], form_filter: Optional[str]):
    """(lesson_id, lesson_mapping, form, lv, lv_description) を implementable=true のみ列挙する。"""
    for lesson_id in sorted(mapping.keys()):
        if lesson_filter and lesson_id != lesson_filter:
            continue
        lm = mapping[lesson_id]
        forms = lm.get("supported_forms", []) or []
        dl = lm.get("difficulty_levels", {}) or {}
        for form in forms:
            if form_filter and form != form_filter:
                continue
            levels = dl.get(form) or []
            impl = [lv for lv in levels if lv.get("implementable", True)]
            if not impl:
                # form は宣言されているが明示レベルが無い → lv=1 単発として扱う
                yield lesson_id, lm, form, 1, ""
                continue
            for lv in impl:
                yield lesson_id, lm, form, lv.get("lv", 1), lv.get("description", "")


def _summarize_atoms(sampled_atoms: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(sampled_atoms, dict):
        return out
    for name, atom in sampled_atoms.items():
        if not isinstance(atom, dict):
            out[name] = {"type": None, "dims": atom}
            continue
        out[name] = {
            "type": atom.get("atom_type"),
            "dims": atom.get("dimensions_cm", {}),
        }
    return out


def _summarize(mr: dict[str, Any]) -> dict[str, Any]:
    """`/inspect` レスポンスから題材監査に要る要約だけを抜き出す。"""
    ops: list[str] = []
    answers: list[Any] = []
    hints: list[str] = []
    for sq in mr.get("sub_questions", []) or []:
        hint = sq.get("prompt_hint")
        if hint:
            hints.append(hint)
        ans = sq.get("answer") or {}
        answers.append(ans.get("sympy_form"))
        for step in sq.get("logic_steps", []) or []:
            op = step.get("operation_name")
            if op:
                ops.append(op)
    return {
        "blueprint_id": mr.get("blueprint_id"),
        "selected_tags": mr.get("selected_tags", []),
        "sampled_atoms": _summarize_atoms(mr.get("sampled_atoms", {})),
        "operation_names": ops,
        "answers": answers,
        "prompt_hints": hints,
        "difficulty_score": mr.get("difficulty_score"),
    }


def _inspect(client, lesson_id: str, lm: dict[str, Any], form: str, level: int, seed: int) -> dict[str, Any]:
    payload = {
        "curriculum": {"grade": lm["grade"], "lesson_ids": [lesson_id]},
        "problem_form": form,
        "target_level": level,
        "unlearned_lesson_ids": [],
        "seed": seed,
    }
    r = client.post("/problems/inspect", json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"inspect status={r.status_code} body={r.text[:400]}")
    return r.json()


def build_dump(lesson_filter=None, form_filter=None, out_path: Path = OUT_PATH) -> dict[str, int]:
    assert os.environ.get("SKIP_LLM_IN_TESTS", "").lower() in ("1", "true", "yes"), (
        "dump_mr_corpus は LLM フリーが前提。SKIP_LLM_IN_TESTS が有効になっていません。"
    )
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))

    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_err = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for lesson_id, lm, form, lv, lv_desc in _iter_cells(mapping, lesson_filter, form_filter):
            # pinned_seed は level_label 文字列を取る。lv 番号を安定ラベル化して衝突を避ける。
            seed = pinned_seed(lesson_id, form, f"lv{lv}")
            row: dict[str, Any] = {
                "lesson": lesson_id,
                "title": lm.get("title"),
                "large_unit": lm.get("large_unit"),
                "domain": lm.get("domain"),
                "grade": lm.get("grade"),
                "form": form,
                "lv": lv,
                "lv_description": lv_desc,
                "declared_blueprint": (lm.get("execute_blueprint_by_form", {}) or {}).get(form)
                or lm.get("execute_blueprint"),
                "seed": seed,
            }
            try:
                mr = _inspect(client, lesson_id, lm, form, lv, seed)
                row.update(_summarize(mr))
                n_ok += 1
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"
                row["traceback"] = traceback.format_exc()[-800:]
                n_err += 1
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"ok": n_ok, "error": n_err}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", default=None, help="この lesson_id だけダンプ（デバッグ用）")
    parser.add_argument("--form", default=None, help="この problem_form だけダンプ（デバッグ用）")
    parser.add_argument("--out", default=str(OUT_PATH), help="出力 JSONL パス")
    args = parser.parse_args()

    out_path = Path(args.out)
    summary = build_dump(args.lesson, args.form, out_path)
    print(f"ダンプ完了: OK={summary['ok']} / ERROR={summary['error']}")
    try:
        print(f"出力: {out_path.relative_to(REPO_ROOT)}")
    except ValueError:
        print(f"出力: {out_path}")


if __name__ == "__main__":
    main()
