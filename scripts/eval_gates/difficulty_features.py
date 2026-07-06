"""難易度特徴モジュール（LLM不使用）。

`docs/phase2_eval_gates_spec.md` §3-G6 / 親計画 §2.4 の特徴セットを実装する。
ground truth（`/problems/inspect` 相当の MR dict）だけから算出でき、product は不要。

フェーズ3の難易度Lv再設計でも同じ特徴セット・同じモジュールを再利用する前提
（二度手間にしない）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

# sympy_form / sympy_expr の文字列表現から検出するための簡易パターン
_SQRT_RE = re.compile(r"sqrt|√")
_PI_RE = re.compile(r"\bpi\b|π", re.IGNORECASE)
_FRACTION_RE = re.compile(r"/|Rational|\\d?frac")
_NEGATIVE_NUMBER_RE = re.compile(r"-\d")

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass
class DifficultyFeatures:
    """1問（ground truth の MR）から算出する構造難易度特徴ベクトル。"""

    step_count: int = 0
    max_abs_operand: float = 0.0
    has_sqrt: bool = False
    has_pi: bool = False
    has_fraction: bool = False
    has_negative: bool = False
    sub_question_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def composite_score(self) -> float:
        """合成難易度スコア。

        重み付けは「構造の複雑さ」を単調に反映することを目的とし、絶対値の
        大小そのものより step 数・特殊な数の有無を強く効かせる。
        フェーズ3で再設計する余地を残すため、ここでは単純な線形和とする。
        """
        score = 0.0
        score += self.step_count * 10.0
        score += self.sub_question_count * 5.0
        # 絶対値は桁数（log的な効き方）にして、単純な乱数ジッターに支配されないようにする
        score += min(self.max_abs_operand, 10_000) / 100.0
        if self.has_sqrt:
            score += 8.0
        if self.has_pi:
            score += 8.0
        if self.has_fraction:
            score += 6.0
        if self.has_negative:
            score += 3.0
        return score


def _iter_sympy_strings(ground_truth: dict[str, Any]) -> list[str]:
    """ground truth 内の sympy_form / sympy_expr 文字列をすべて集める。"""
    strings: list[str] = []
    for sq in ground_truth.get("sub_questions", []) or []:
        answer = sq.get("answer") or {}
        if answer.get("sympy_form"):
            strings.append(str(answer["sympy_form"]))
        for step in sq.get("logic_steps", []) or []:
            if step.get("sympy_expr"):
                strings.append(str(step["sympy_expr"]))
            for operand in step.get("operands", []) or []:
                strings.append(str(operand))
    return strings


def _max_abs_operand(ground_truth: dict[str, Any]) -> float:
    max_abs = 0.0
    for sq in ground_truth.get("sub_questions", []) or []:
        for step in sq.get("logic_steps", []) or []:
            for operand in step.get("operands", []) or []:
                for tok in _NUMBER_RE.findall(str(operand)):
                    try:
                        max_abs = max(max_abs, abs(float(tok)))
                    except ValueError:
                        continue
    return max_abs


def compute_difficulty_features(ground_truth: dict[str, Any]) -> DifficultyFeatures:
    """ground truth（`/problems/inspect` 相当の dict）から難易度特徴を算出する。

    LLM は使わない。sub_questions[].logic_steps / answer.sympy_form のみ参照。
    """
    sub_questions = ground_truth.get("sub_questions", []) or []
    step_count = sum(len(sq.get("logic_steps", []) or []) for sq in sub_questions)
    sub_question_count = len(sub_questions)

    all_strings = _iter_sympy_strings(ground_truth)
    joined = " ".join(all_strings)

    return DifficultyFeatures(
        step_count=step_count,
        max_abs_operand=_max_abs_operand(ground_truth),
        has_sqrt=bool(_SQRT_RE.search(joined)),
        has_pi=bool(_PI_RE.search(joined)),
        has_fraction=bool(_FRACTION_RE.search(joined)),
        has_negative=bool(_NEGATIVE_NUMBER_RE.search(joined)),
        sub_question_count=sub_question_count,
    )
