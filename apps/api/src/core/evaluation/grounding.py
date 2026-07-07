"""数値接地の検証コア（LLMフリー・evaluator = verifier）。

word_problem（文章題）の翻訳が、MR の**必要入力数値を実際に使っている**かを
検査する（HANDOFF §8.4「物語が MR と乖離・捏造」の "乖離"＝入力数値を落とす/変える
欠陥を捕捉）。オフライン評価ゲート G2（数値整合）と同じ「必要入力数値」定義を用いる。

- moat 不変: SymPy の数値は変えない。text が入力数値を含むか検査するだけ。
- LLM は使わない。数値正規化（`number_normalize`）による決定論突合のみ。

**保守設計（誤棄却回避）— word_problem のハード棄却に耐える安全な部分集合のみ対象**:
- **整数 operand のみ**。分数/小数（`1/2`→「半分」）や記号式（`3√2`）は自然文で
  言語化・表記ゆれが起きやすく誤棄却するため対象外（オフライン G2 が拾う）。
- **絶対値（大きさ）で照合**。正負の数の文章題は符号を方向語で表す（例
  `(-30)×(-7)` を「30個ずつ7回減らす」）ため、符号付き完全一致だと faithful な翻訳を
  誤棄却する。MR operand の整数**大きさの集合**が問題文の整数大きさ集合に含まれるかを見る。
- **値 0 は対象外**（「0 を明示しない自然文」を誤棄却しうる）。
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Iterable, List, Optional, Set

from apps.api.src.core.evaluation.number_normalize import (
    _to_fraction,
    dedupe_preserve_order,
    extract_numbers,
    normalize_math_text,
)


def _integer_magnitude(value: str) -> Optional[int]:
    """value が非ゼロ整数なら abs をint で返す。分数/小数/記号式/0 は None。"""
    frac = _to_fraction(normalize_math_text(str(value)))
    if frac is None or frac == 0:
        return None
    if frac.denominator != 1:  # 分数・小数は対象外
        return None
    return abs(int(frac))


def required_integer_magnitudes_from_mr(mr: Any) -> List[int]:
    """MR の全 logic_steps[].operands のうち「非ゼロ整数」の絶対値集合（順序保持）。"""
    mags: List[int] = []
    for sq in getattr(mr, "sub_questions", []) or []:
        for step in getattr(sq, "logic_steps", []) or []:
            for operand in getattr(step, "operands", []) or []:
                mag = _integer_magnitude(operand)
                if mag is not None:
                    mags.append(mag)
    # 重複除去（順序保持）
    seen: Set[int] = set()
    out: List[int] = []
    for m in mags:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _text_integer_magnitudes(text: str) -> Set[int]:
    mags: Set[int] = set()
    for tok in extract_numbers(text):
        frac = _to_fraction(tok)
        if frac is not None and frac.denominator == 1:
            mags.add(abs(int(frac)))
    return mags


def find_missing_required_numbers(
    problem_text: str,
    sub_prompt_texts: Optional[Iterable[str]],
    mr: Any,
) -> List[str]:
    """問題文（＋小問プロンプト）に現れない必要入力数値（整数の大きさ）のリストを返す。

    非空なら「文章題が MR の入力数値を落とした/変えた（乖離）」＝棄却対象。
    符号は方向語で表されうるため絶対値で照合する。
    """
    parts: List[str] = [problem_text or ""]
    if sub_prompt_texts:
        parts.extend(t or "" for t in sub_prompt_texts)
    full_text = "\n".join(parts)

    present = _text_integer_magnitudes(full_text)
    required = required_integer_magnitudes_from_mr(mr)
    return [str(m) for m in required if m not in present]
