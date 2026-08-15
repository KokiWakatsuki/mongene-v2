"""翻訳済み product に generate-then-verify（受理/棄却ゲート）をオフライン適用する（LLMフリー）。

`docs/HANDOFF_2026-07-06.md` §16（generate-then-verify 反転）/§17.8-17.10（打開策4）の実装。
ランタイム（gemini 経路 `LLMTranslator.translate`）は翻訳直後に「解答漏洩」「数値接地」を
検証して棄却→次 tier するが、**オフライン監査経路（`build_product_corpus.py --engine claude`）は
この検証をバイパス**していた（Phase B で判明）。本スクリプトは同じ共有検証コア
（`leakage.find_problem_answer_leak` / `grounding.find_missing_required_numbers`）を
product コーパスへ適用し、各セルを PASS / FAIL(理由) で判定・集計する。

これにより (1) Phase B 監査が「検証済み品質」を測れる、(2) 棄却されるべき翻訳（答え漏洩・
入力数値の欠落＝捏造/乖離）を機械的に特定できる。moat 不変（テキストを検査するだけ）。

使い方:
    .venv/bin/python scripts/verify_products.py                 # product/claude を検証
    .venv/bin/python scripts/verify_products.py --engine gemini # product/gemini を検証
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.core.evaluation.grounding import find_missing_required_numbers  # noqa: E402
from apps.api.src.core.evaluation.leakage import find_problem_answer_leak  # noqa: E402

GT_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth"


def _duck_mr_from_gt(gt: Dict[str, Any]) -> SimpleNamespace:
    """GT JSON を検証器が期待する duck-typed MR に変換する。"""
    sub_questions: List[SimpleNamespace] = []
    for sq in gt.get("sub_questions", []) or []:
        ans = sq.get("answer") or {}
        answer_obj = SimpleNamespace(
            sympy_form=ans.get("sympy_form"),
            text_form=ans.get("text_form"),
        )
        steps = [
            SimpleNamespace(
                sympy_expr=st.get("sympy_expr"),
                operands=st.get("operands", []) or [],
                operation_name=st.get("operation_name", ""),
            )
            for st in (sq.get("logic_steps", []) or [])
        ]
        sub_questions.append(SimpleNamespace(answer=answer_obj, logic_steps=steps))
    return SimpleNamespace(
        sub_questions=sub_questions,
        problem_form=gt.get("_problem_form") or gt.get("problem_form"),
    )


def verify_product(product: Dict[str, Any], gt: Dict[str, Any]) -> Dict[str, Any]:
    """1 セルを検証。{"pass": bool, "leak": [...], "grounding_missing": [...]} を返す。"""
    mr = _duck_mr_from_gt(gt)
    problem_text = product.get("content_problem_text", "") or ""
    sub_prompt_texts = [
        (sq.get("prompt_text") or "") for sq in (product.get("sub_questions", []) or [])
    ]
    leak = find_problem_answer_leak(problem_text, sub_prompt_texts, mr, numeric_only=True)
    # 数値接地はランタイムと同様 word_problem のみ
    grounding_missing: List[str] = []
    if getattr(mr, "problem_form", None) == "word_problem":
        grounding_missing = find_missing_required_numbers(problem_text, sub_prompt_texts, mr)
    return {
        "pass": not leak and not grounding_missing,
        "leak": leak,
        "grounding_missing": grounding_missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="claude")
    parser.add_argument("--write", action="store_true", help="product JSON に _verify を書き戻す")
    args = parser.parse_args()

    product_dir = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "product" / args.engine
    files = sorted(p for p in product_dir.glob("*.json") if not p.name.startswith("_"))
    if not files:
        print(f"product が見つかりません: {product_dir}")
        return

    n_pass = 0
    fails: List[str] = []
    for f in files:
        product = json.loads(f.read_text(encoding="utf-8"))
        gt_path = GT_DIR / f.name
        if not gt_path.exists():
            continue
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
        result = verify_product(product, gt)
        if args.write:
            product["_verify"] = result
            f.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
        if result["pass"]:
            n_pass += 1
        else:
            reasons = []
            if result["leak"]:
                reasons.append(f"漏洩={result['leak']}")
            if result["grounding_missing"]:
                reasons.append(f"数値欠落={result['grounding_missing']}")
            fails.append(f"  {f.stem}: {' / '.join(reasons)}")

    total = n_pass + len(fails)
    print(f"検証: PASS {n_pass}/{total}（{100*n_pass//max(1,total)}%）")
    if fails:
        print("=== FAIL（棄却対象） ===")
        print("\n".join(fails))


if __name__ == "__main__":
    main()
