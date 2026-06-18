"""target_difficulty と y_base の調整（難易度設計 implementation_plan.md 抜本的改修版）

Raw Score モデル（§ implementation_plan.md）:
  raw_score = large_unit(100-900) + lesson(0-400) + form(0-800)
             + hint(−100〜+300) + steps(0-500) + digits(0-300)
             + unit_mix(0-500) + subquestion(0-600)
  RAW_MIN = 100, RAW_MAX = 4300
  Difficulty (1-100) = 1 + 99 * (raw - RAW_MIN) / (RAW_MAX - RAW_MIN)

reconcile_difficulty の役割:
  - target (1-100) を raw_target に逆算
  - raw_y_base（大単元+小単元のベーススコア）と form_bonus を差し引いた raw_delta を計算
  - raw_delta を各 delta_factors に分配
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from apps.api.src.core.abc.blueprint import BlueprintDefinition
from apps.api.src.core.difficulty.base_difficulty import RAW_MIN, normalize, denormalize

# 全 delta_factors を含む Raw Score の最大値
RAW_MAX_FULL = 4300  # implementation_plan.md の理論最大値

# 問題形式ボーナス（Raw Score 加算値）
FORM_RAW_BONUS: Dict[str, int] = {
    "calculation": 0,      # 計算問題: ボーナスなし
    "word_problem": 400,   # 文章題: 読解・設定の複雑さ
    "proof": 800,          # 証明: 論理的推論の要求
}

# 問題形式が必ず加算するため、最低難易度は form_bonus 込みの正規化値になる
# → UI スライダーの min/max に使う
def get_form_range(raw_y_base: int, problem_form: str) -> Tuple[int, int]:
    """(min_difficulty_1_100, max_difficulty_1_100) を返す"""
    form_bonus = FORM_RAW_BONUS.get(problem_form, 0)
    base_raw = raw_y_base + form_bonus
    # 最小: ベーススコアのみ（追加ファクターゼロ）
    # 最大: ベース + 全ファクター最大（steps+digits+unit_mix）
    max_delta_raw = 500 + 300 + 500  # step(500) + digit(300) + unit_mix(500)
    lo = normalize(base_raw)
    hi = normalize(min(RAW_MAX_FULL, base_raw + max_delta_raw))
    return lo, hi

# 後方互換: 旧 y_base (1-100 スケール) から get_form_range を呼ぶ
def get_form_range_from_y_base(y_base: int, problem_form: str) -> Tuple[int, int]:
    """y_base (1-100) → raw_y_base に変換して get_form_range を呼ぶ（後方互換）"""
    raw_y_base = denormalize(y_base)
    return get_form_range(raw_y_base, problem_form)


DELTA_MAX = 15  # 後方互換用（旧コード参照箇所のため残す）


@dataclass
class DifficultyPlan:
    blueprint: BlueprintDefinition
    computed_difficulty: int
    delta_factors: Dict[str, int] = field(default_factory=dict)
    unsatisfiable: bool = False
    reason: Optional[str] = None


def reconcile_difficulty(
    target: int,
    y_base: int,
    blueprint: BlueprintDefinition,
    problem_form: str,
) -> DifficultyPlan:
    """target (1-100) と y_base (1-100) からデルタを計算し BlueprintPlan を返す。

    Raw Score モデル:
      raw_y_base = denormalize(y_base)
      form_bonus = FORM_RAW_BONUS[problem_form]
      raw_base = raw_y_base + form_bonus
      raw_target = denormalize(target)
      raw_delta = raw_target - raw_base  ← 各 delta_factors に分配
    """
    raw_y_base = denormalize(y_base)
    form_bonus = FORM_RAW_BONUS.get(problem_form, 0)
    raw_base = raw_y_base + form_bonus
    raw_target = denormalize(target)
    raw_delta = raw_target - raw_base

    lo, hi = get_form_range(raw_y_base, problem_form)

    # target が範囲外の場合はクランプ
    if target < lo:
        computed = lo
        raw_delta = 0
        unsatisfiable = False
        reason = None
    elif target > hi:
        computed = hi
        raw_delta = denormalize(hi) - raw_base
        unsatisfiable = (target - hi > 10)
        reason = f"target={target} が {problem_form} の最大 {hi} を超過" if unsatisfiable else None
    else:
        computed = target
        unsatisfiable = False
        reason = None

    factors = _distribute_raw_delta(raw_delta, problem_form)
    blueprint = _apply_step_depth(blueprint, factors)

    return DifficultyPlan(
        blueprint=blueprint,
        computed_difficulty=computed,
        delta_factors=factors,
        unsatisfiable=unsatisfiable,
        reason=reason,
    )


def _distribute_raw_delta(raw_delta: int, problem_form: str) -> Dict[str, int]:
    """raw_delta を implementation_plan.md の delta_factors に分配する。

    分配順序（Raw Score 単位）:
      1. digit_penalty: +100/段階（最大 300 = 3段階）
      2. step_depth:    +100/手（最大 500 = 5手）
      3. unit_mix_bonus: +500（複合単元化、一括）
      4. hint_reduction: −100〜+300（形式に応じた図の有無）
    """
    factors: Dict[str, int] = {}

    # 問題形式固有のベースファクター（ raw_delta にはすでに form_bonus 分が引かれている）
    if problem_form == "calculation":
        factors["hint_reduction"] = -100  # 図あり → 易しめ
    elif problem_form == "word_problem":
        factors["hint_reduction"] = 300   # 図なし文章 → 難しめ
    elif problem_form == "proof":
        factors["proof_complexity"] = 800  # 証明の複雑さ（form_bonus として処理済み）

    remaining = max(0, raw_delta)

    # digit_penalty (100 単位, 最大 3 段階 = 300)
    dp = min(remaining // 100, 3)
    if dp > 0:
        factors["digit_penalty"] = dp
        remaining -= dp * 100

    # step_depth (100 単位, 最大 5 手 = 500)
    sd = min(remaining // 100, 5)
    if sd > 0:
        factors["step_depth"] = sd
        remaining -= sd * 100

    # unit_mix_bonus (500 一括)
    if remaining >= 500:
        factors["unit_mix_bonus"] = 500
        remaining -= 500

    return factors


def _apply_step_depth(
    blueprint: BlueprintDefinition,
    factors: Dict[str, int],
) -> BlueprintDefinition:
    """step_depth に応じて subquestion_strategy.target_count を増やす"""
    _no_depth = {"ProofStructure", "ConstructionStructure", "BasicCalculationStructure"}
    sd = factors.get("step_depth", 0)
    if sd > 0 and blueprint.subquestion_strategy is not None \
            and blueprint.blueprint_id not in _no_depth:
        enhanced = copy.deepcopy(blueprint)
        old = enhanced.subquestion_strategy.target_count
        enhanced.subquestion_strategy.target_count = min(old + sd // 2, 5)
        return enhanced
    return blueprint
