"""LLM 翻訳なし・フォールバック問題テキスト生成（§35.4）"""
from __future__ import annotations

import random
import sympy

from apps.api.src.core.representation.middle_representation import MiddleRepresentation


def template_fallback_text(mr: MiddleRepresentation) -> str:
    """LLM なしでも読める問題テキストを生成する（フォーム対応版）。

    problem_form に応じて出力形式を変える：
    - calculation / visual: 計算式そのまま（従来動作）
    - knowledge: 4択形式の知識確認問題
    - word_problem: 簡単な文脈を追加した文章題
    - proof: 証明問題形式
    """
    form = mr.problem_form

    if form == "knowledge":
        return _knowledge_fallback(mr)
    if form == "word_problem":
        return _word_problem_fallback(mr)
    if form == "proof":
        return _proof_fallback(mr)
    # calculation / visual / その他
    return _calculation_fallback(mr)


# ─── 計算問題（基本） ─────────────────────────────────────────────
def _calculation_fallback(mr: MiddleRepresentation) -> str:
    lines: list[str] = []
    for sq in mr.sub_questions:
        label = f"{sq.label} " if sq.label else ""
        lines.append(f"{label}{sq.prompt_hint}")
        try:
            if sq.answer.sympy_form is not None:
                ans_latex = sympy.latex(sq.answer.sympy_form)
                lines.append(f"  答え: ${ans_latex}$")
            else:
                lines.append(f"  答え: {sq.answer.text_form}")
        except Exception:
            lines.append(f"  答え: {sq.answer.text_form}")
    return "\n".join(lines)


# ─── 知識問題（4択） ──────────────────────────────────────────────
def _knowledge_fallback(mr: MiddleRepresentation) -> str:
    """知識問題のフォールバック: knowledge_hint があればそれを問いとして出力する。"""
    if not mr.sub_questions:
        return _calculation_fallback(mr)

    sq = mr.sub_questions[0]

    # knowledge 型: extras.knowledge_hint を問いとして使う
    if sq.answer.type == "knowledge":
        hint = (sq.answer.extras or {}).get("knowledge_hint") or sq.prompt_hint
        return f"{hint}\n  答え: （概念・用語の説明）"

    correct = sq.answer.sympy_form

    # 答えが数値の場合は数値4択を生成
    if correct is not None and correct.is_number:
        try:
            val = int(correct)
            # 正解の周辺に3つの誤答を生成
            rng = random.Random(mr.seed)
            distractors: list[int] = []
            offsets = rng.sample([-3, -2, -1, 1, 2, 3, 5, -5, 10, -10], 3)
            for d in offsets:
                distractors.append(val + d)
            choices = [val] + distractors
            rng.shuffle(choices)
            label_map = dict(zip(["ア", "イ", "ウ", "エ"], choices))
            answer_label = next(k for k, v in label_map.items() if v == val)

            lines = ["次のうち、正しい計算結果はどれか。"]
            # 元の式をプロンプトヒントから抽出
            if "$" in sq.prompt_hint:
                expr_part = sq.prompt_hint.split("\n")[-1] if "\n" in sq.prompt_hint else sq.prompt_hint
                lines.append(f"計算式: {expr_part}")
            for lbl, v in label_map.items():
                lines.append(f"  {lbl}. {v}")
            lines.append(f"  答え: {answer_label}")
            return "\n".join(lines)
        except Exception:
            pass

    # 数値でない場合（式・証明結果など）：「正しいものを選べ」形式
    tags_str = "・".join(mr.selected_tags[:2]) if mr.selected_tags else "数学"
    lines = [f"次の{tags_str}に関する記述のうち、正しいものはどれか。"]
    hint = sq.prompt_hint.replace("次の計算をしなさい", "").replace("次の", "").strip()
    if hint:
        lines.append(f"  ア. {hint} は成り立つ。")
        lines.append(f"  イ. {hint} は成り立たない。")
        lines.append(f"  ウ. 条件が不足している。")
        lines.append(f"  エ. 上のいずれでもない。")
    else:
        lines.append("  ア. 常に成り立つ。")
        lines.append("  イ. 成り立たない場合がある。")
        lines.append("  ウ. 定義による。")
        lines.append("  エ. 上のいずれでもない。")
    lines.append("  答え: ア")
    return "\n".join(lines)


# ─── 文章題 ──────────────────────────────────────────────────────
_STORY_TEMPLATES = [
    "ある数 $x$ を求めなさい。",
    "次の問いに答えなさい。",
    "条件を満たす値を求めなさい。",
]


def _word_problem_fallback(mr: MiddleRepresentation) -> str:
    """計算結果を使った簡単な文章題形式に変換する。"""
    if not mr.sub_questions:
        return _calculation_fallback(mr)

    sq = mr.sub_questions[0]
    rng = random.Random(mr.seed)
    intro = rng.choice(_STORY_TEMPLATES)
    lines = [intro, sq.prompt_hint]
    try:
        if sq.answer.sympy_form is not None:
            ans_latex = sympy.latex(sq.answer.sympy_form)
            lines.append(f"  答え: ${ans_latex}$")
        else:
            lines.append(f"  答え: {sq.answer.text_form}")
    except Exception:
        lines.append(f"  答え: {sq.answer.text_form}")
    return "\n".join(lines)


# ─── 証明問題 ─────────────────────────────────────────────────────
def _proof_fallback(mr: MiddleRepresentation) -> str:
    """証明問題形式で出力する。"""
    if not mr.sub_questions:
        return _calculation_fallback(mr)

    import json as _json
    sq = mr.sub_questions[0]
    proof_output = sq.answer.extras.get("proof_output") if sq.answer.extras else None

    if proof_output is None:
        # operands から proof_output を探す
        for step in sq.logic_steps:
            for op in step.operands:
                if isinstance(op, str) and op.startswith("{"):
                    try:
                        proof_output = _json.loads(op)
                        break
                    except Exception:
                        pass
            if proof_output:
                break

    if proof_output:
        to_prove = proof_output.get("to_prove", "図形の合同または相似")
        lines = [f"次のことを証明しなさい。", f"  {to_prove}"]
        for step_info in proof_output.get("steps", []):
            lines.append(f"  {step_info.get('step_number', '')}. {step_info.get('statement', '')}（{step_info.get('reason', '')}）")
        conclusion = proof_output.get("conclusion", "")
        if conclusion:
            lines.append(f"  結論: {conclusion}")
        return "\n".join(lines)

    # フォールバック
    hint = sq.prompt_hint or "図形の性質"
    return f"次のことを証明しなさい。\n  {hint}"
