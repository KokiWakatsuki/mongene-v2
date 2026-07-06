"""G7 レンダリング健全性 (render_sanity)

spec §3-G7:
- content_problem_text＋explanation の LaTeX: `$...$` が均衡し、`$$` `\\[` `\\]`（ブロック数式）
  を使っていないこと。使用で FAIL。
- 各 `$...$` の中括弧均衡＋既知コマンド範囲チェック（フルKaTeX検証は任意。最低限の構文チェックを必須）。
- visual 形式: 図URL/SVG が非空かつ整形式XML（xml.etree でパース可能）であること。

LLM は使わない。文字列走査・XML パースのみ。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Optional
from urllib.parse import unquote

from scripts.eval_gates.common import GateResult

GATE_ID = "G7"

_BLOCK_MATH_PATTERNS = [r"\$\$", r"\\\[", r"\\\]"]

# 既知の LaTeX コマンドのみを許可する簡易チェック（フルKaTeX検証はしない）
_KNOWN_COMMAND_RE = re.compile(
    r"\\(?:frac|dfrac|tfrac|sqrt|left|right|times|cdot|div|pm|mp|leq|geq|neq|approx|"
    r"circ|angle|triangle|overline|vec|sum|int|infty|pi|theta|alpha|beta|gamma|"
    r"text|mathrm|mathbf|displaystyle|,|;|!|quad|qquad|degree)\b"
)
_UNKNOWN_COMMAND_RE = re.compile(r"\\([a-zA-Z]+)")


def _full_text(product: dict[str, Any]) -> str:
    content = product.get("content_problem_text", "") or ""
    explanations = [
        sq.get("explanation_text", "") or "" for sq in product.get("sub_questions", []) or []
    ]
    return "\n".join([content, *explanations])


def _check_block_math_unused(text: str) -> list[str]:
    hits = []
    for pattern in _BLOCK_MATH_PATTERNS:
        if re.search(pattern, text):
            hits.append(pattern)
    return hits


def _check_dollar_balance(text: str) -> Optional[str]:
    # $$ を先に除去した上で $ の数が偶数か確認（すでに _check_block_math_unused で検出済みだが独立チェック）
    dollar_count = text.count("$")
    if dollar_count % 2 != 0:
        return f"$ の数が奇数（不均衡）: {dollar_count}個"
    return None


def _check_brace_balance(expr: str) -> Optional[str]:
    depth = 0
    for ch in expr:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return f"中括弧が不均衡（閉じ括弧が先行）: '{expr}'"
    if depth != 0:
        return f"中括弧が不均衡（{depth}個未閉じ）: '{expr}'"
    return None


def _check_known_commands(expr: str) -> list[str]:
    unknown = []
    for m in _UNKNOWN_COMMAND_RE.finditer(expr):
        full = m.group(0)
        if not _KNOWN_COMMAND_RE.match(full):
            unknown.append(full)
    return unknown


def _check_latex(text: str) -> GateResult | None:
    block_hits = _check_block_math_unused(text)
    if block_hits:
        return GateResult(GATE_ID, "FAIL", f"ブロック数式記法を使用している（禁止）: {block_hits}")

    balance_issue = _check_dollar_balance(text)
    if balance_issue:
        return GateResult(GATE_ID, "FAIL", balance_issue)

    inline_exprs = re.findall(r"\$([^$]*)\$", text)
    for expr in inline_exprs:
        brace_issue = _check_brace_balance(expr)
        if brace_issue:
            return GateResult(GATE_ID, "FAIL", brace_issue)
        unknown_cmds = _check_known_commands(expr)
        if unknown_cmds:
            return GateResult(
                GATE_ID,
                "FAIL",
                f"未知のLaTeXコマンドを検出: {unknown_cmds} (式: '{expr}')",
            )
    return None


def _is_well_formed_xml(svg_or_url: str) -> bool:
    candidate = svg_or_url.strip()
    if candidate.startswith("data:image/svg+xml"):
        # data URL の場合は中身を取り出す
        if "," in candidate:
            payload = candidate.split(",", 1)[1]
            candidate = unquote(payload)
    if not candidate.lstrip().startswith("<"):
        # URL（http://... や /static/...）の場合、中身を検証できないので形式のみチェック
        return bool(candidate)
    try:
        ET.fromstring(candidate)
        return True
    except ET.ParseError:
        return False


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    text = _full_text(product)
    latex_result = _check_latex(text)
    if latex_result is not None:
        return latex_result

    problem_form = ground_truth.get("problem_form") or product.get("metadata", {}).get("problem_form")
    if problem_form == "visual":
        visuals = product.get("visuals", {}) or {}
        diagram_url = visuals.get("problem_diagram_url")
        if not diagram_url:
            return GateResult(GATE_ID, "FAIL", "visual 形式なのに problem_diagram_url が空")
        if not _is_well_formed_xml(diagram_url):
            return GateResult(GATE_ID, "FAIL", "problem_diagram_url の SVG が整形式XMLでない")

    return GateResult(GATE_ID, "PASS", "LaTeX構文・(visualなら)SVGの健全性を確認")
