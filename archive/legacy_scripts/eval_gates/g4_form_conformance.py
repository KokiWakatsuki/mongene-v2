"""G4 形式適合 (form_conformance)

spec §3-G4: 形式別ヒューリスティック。判定語彙は `master_data/eval_lexicons.yaml` に外出し。
- knowledge: 「次の計算をしなさい」等の裸パターンを含んだら FAIL。定義/性質/正誤/用語/穴埋め等の
  マーカーを含むべき（無ければ FAIL）。
- proof: 「証明」＋構造マーカーを含むべき。裸の計算式のみ → FAIL。
- word_problem: 場面設定語彙を含むべき。裸の式のみ → FAIL。
- visual: visuals.problem_diagram_url が非null かつ 本文が図参照語を含む。
- calculation: 式を含み、物語語彙を含まない。

LLM は使わない。語彙マッチのみ（`master_data/eval_lexicons.yaml` を編集すれば拡張可能）。
"""
from __future__ import annotations

import re
from typing import Any

from scripts.eval_gates.common import GateResult, load_lexicons

GATE_ID = "G4"

_LATEX_EXPR_RE = re.compile(r"\$[^$]*\d[^$]*\$")


def _has_any(text: str, markers: list[str]) -> bool:
    return any(m in text for m in markers)


def _full_text(product: dict[str, Any]) -> str:
    content = product.get("content_problem_text", "") or ""
    prompts = [sq.get("prompt_text", "") or "" for sq in product.get("sub_questions", []) or []]
    explanations = [sq.get("explanation_text", "") or "" for sq in product.get("sub_questions", []) or []]
    return "\n".join([content, *prompts, *explanations])


def _check_knowledge(text: str, lex: dict[str, Any]) -> GateResult:
    cfg = lex.get("knowledge", {})
    forbidden = cfg.get("forbidden_patterns", [])
    required = cfg.get("required_markers", [])
    if _has_any(text, forbidden) and not _has_any(text, required):
        return GateResult(GATE_ID, "FAIL", f"knowledge 形式なのに裸の計算指示パターンを検出: {forbidden}")
    if not _has_any(text, required):
        return GateResult(GATE_ID, "FAIL", "knowledge 形式に必要なマーカー（定義/性質/正誤/用語等）が無い")
    return GateResult(GATE_ID, "PASS", "knowledge 形式のマーカーを検出")


def _check_proof(text: str, lex: dict[str, Any]) -> GateResult:
    cfg = lex.get("proof", {})
    required = cfg.get("required_markers", [])
    structure = cfg.get("structure_markers", [])
    if not _has_any(text, required):
        return GateResult(GATE_ID, "FAIL", "proof 形式なのに「証明」マーカーが無い")
    if not _has_any(text, structure):
        return GateResult(GATE_ID, "FAIL", "proof 形式なのに構造マーカー（仮定/結論/∴/合同/相似/∠/△等）が無い")
    return GateResult(GATE_ID, "PASS", "proof 形式の構造マーカーを検出")


def _check_word_problem(text: str, lex: dict[str, Any]) -> GateResult:
    cfg = lex.get("word_problem", {})
    scenario = cfg.get("scenario_markers", [])
    if not _has_any(text, scenario):
        return GateResult(GATE_ID, "FAIL", "word_problem 形式なのに場面設定語彙が無い（裸の式の可能性）")
    return GateResult(GATE_ID, "PASS", "word_problem 形式の場面設定語彙を検出")


def _check_visual(product: dict[str, Any], text: str, lex: dict[str, Any]) -> GateResult:
    cfg = lex.get("visual", {})
    reference_markers = cfg.get("reference_markers", [])
    visuals = product.get("visuals", {}) or {}
    diagram_url = visuals.get("problem_diagram_url")
    if not diagram_url:
        return GateResult(GATE_ID, "FAIL", "visual 形式なのに problem_diagram_url が空")
    if not _has_any(text, reference_markers):
        return GateResult(GATE_ID, "FAIL", "visual 形式なのに本文が図/グラフを参照していない")
    return GateResult(GATE_ID, "PASS", "visual 形式の図参照とURLを確認")


def _check_calculation(text: str, lex: dict[str, Any]) -> GateResult:
    word_cfg = lex.get("word_problem", {})
    scenario_markers = word_cfg.get("scenario_markers", [])
    has_expr = bool(_LATEX_EXPR_RE.search(text))
    has_scenario = _has_any(text, scenario_markers)
    if has_scenario:
        return GateResult(GATE_ID, "FAIL", "calculation 形式なのに物語語彙を含んでいる")
    if not has_expr:
        return GateResult(GATE_ID, "FAIL", "calculation 形式なのに数式を含んでいない")
    return GateResult(GATE_ID, "PASS", "calculation 形式として数式のみを確認")


_CHECKERS = {
    "knowledge": _check_knowledge,
    "proof": _check_proof,
    "word_problem": _check_word_problem,
    "calculation": _check_calculation,
}


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    problem_form = ground_truth.get("problem_form") or product.get("metadata", {}).get("problem_form")
    if not problem_form:
        return GateResult(GATE_ID, "N/A", "problem_form が特定できない")

    lex = load_lexicons()
    text = _full_text(product)

    if problem_form == "visual":
        return _check_visual(product, text, lex)

    checker = _CHECKERS.get(problem_form)
    if checker is None:
        return GateResult(GATE_ID, "N/A", f"未対応の problem_form: {problem_form}")
    return checker(text, lex)
