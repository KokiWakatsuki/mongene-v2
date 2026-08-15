"""確率まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l59.calculation Lv1: さいころの相対度数
LF_PROBABILITY_RELATIVE_FREQ_G1_V1 = "{{ given.expressions }}。"

# g2_l51.find_value Lv2: 相対度数から確率を推定する
LF_PROBABILITY_RELATIVE_FREQ_G2_V1 = "{{ given.condition }}。"

# g2_l51/l52.find_value Lv1: 硬貨・1個のさいころの条件付き確率
LF_PROBABILITY_SINGLE_DIE_V1 = "{{ given.condition }}。"

# g2_l52.find_value Lv3: 2個のさいころの和・積条件
LF_PROBABILITY_TWO_DICE_V1 = "{{ given.condition }}。"

# g2_l53.find_value Lv2: 役職を順に選ぶ確率
LF_PROBABILITY_ORDERED_SELECTION_V1 = "{{ given.condition }}。"

# g2_l53.find_value Lv3: 玉を同時に取り出す確率
LF_PROBABILITY_COMBINATION_SELECTION_V1 = "{{ given.condition }}。"

# g2_l54.find_value Lv2/Lv3: 余事象・少なくとも1つ起こる確率
LF_PROBABILITY_COMPLEMENT_V1 = "{{ given.condition }}。"

# g1_l59.knowledge Lv2 / g2_l51.knowledge Lv2: 判別・解釈型
LF_PROBABILITY_JUDGE_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_probability_relative_freq_g1_v1", LF_PROBABILITY_RELATIVE_FREQ_G1_V1)
    REGISTRY.register_template("lf_probability_relative_freq_g2_v1", LF_PROBABILITY_RELATIVE_FREQ_G2_V1)
    REGISTRY.register_template("lf_probability_single_die_v1", LF_PROBABILITY_SINGLE_DIE_V1)
    REGISTRY.register_template("lf_probability_two_dice_v1", LF_PROBABILITY_TWO_DICE_V1)
    REGISTRY.register_template(
        "lf_probability_ordered_selection_v1", LF_PROBABILITY_ORDERED_SELECTION_V1
    )
    REGISTRY.register_template(
        "lf_probability_combination_selection_v1", LF_PROBABILITY_COMBINATION_SELECTION_V1
    )
    REGISTRY.register_template("lf_probability_complement_v1", LF_PROBABILITY_COMPLEMENT_V1)
    REGISTRY.register_template("lf_probability_judge_v1", LF_PROBABILITY_JUDGE_V1)


_register_all()


__all__ = [
    "LF_PROBABILITY_RELATIVE_FREQ_G1_V1",
    "LF_PROBABILITY_RELATIVE_FREQ_G2_V1",
    "LF_PROBABILITY_SINGLE_DIE_V1",
    "LF_PROBABILITY_TWO_DICE_V1",
    "LF_PROBABILITY_ORDERED_SELECTION_V1",
    "LF_PROBABILITY_COMBINATION_SELECTION_V1",
    "LF_PROBABILITY_COMPLEMENT_V1",
    "LF_PROBABILITY_JUDGE_V1",
]
