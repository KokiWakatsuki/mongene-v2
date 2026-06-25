"""習熟状況 → target_difficulty(1-100) の写像（個別最適化の中核）。

設計（敵対的レビューの指摘を反映）:
  * 能力は Raw Score 尺度（base_difficulty.normalize/denormalize）で扱い、IRT の項目難易度 b の代理に raw を使う。
  * ZPD（発達の最近接領域）: 正答率が目標(0.7)より高ければ難しく、低ければ易しく。
    raw_target = raw_y_base + ZPD_GAIN * (recent_accuracy - TARGET_SUCCESS)
  * difficulty_reconciler は範囲外を黙ってクランプするため、送信前に form_range の [lo, hi] に明示クリップする。
  * 「習得」は recent_accuracy >= 0.8 を要求する（mastery 側）。このとき offset >= ZPD_GAIN*(0.8-0.7) > 0 となり
    難易度は必ず基準(raw_y_base)以上 → 習得判定は実質的に基準難易度以上での成績で行われる
    （= 練習相 ZPD と 習得確認相 を単一ストリームで両立させる簡易版）。
  * コールドスタート（履歴ゼロ）は lesson の基準難易度から開始する。
"""
from __future__ import annotations

from typing import Optional

from apps.api.src.core.difficulty.base_difficulty import normalize
from apps.api.src.core.runner.difficulty_reconciler import get_form_range_from_y_base
from apps.api.src.core.store.models import MasteryState

ZPD_GAIN = 900          # Raw Score 単位 / (正答率差 1.0 あたり)
TARGET_SUCCESS = 0.7    # 狙う正答率（ZPD の中心）


def recent_accuracy(state: MasteryState) -> Optional[float]:
    """直近ウィンドウの正答率。履歴が無ければ None（コールドスタート）。"""
    if not state.recent_window:
        return None
    return sum(1 for x in state.recent_window if x) / len(state.recent_window)


def target_difficulty_for(
    y_base: int,
    raw_y_base: int,
    problem_form: str,
    state: MasteryState,
) -> int:
    """この生徒・この lesson・この形式で次に出す target_difficulty(1-100) を決める。"""
    acc = recent_accuracy(state)
    if acc is None:
        raw_target = raw_y_base
    else:
        raw_target = raw_y_base + ZPD_GAIN * (acc - TARGET_SUCCESS)

    target = normalize(int(round(raw_target)))
    lo, hi = get_form_range_from_y_base(y_base, problem_form)
    return max(lo, min(hi, target))
