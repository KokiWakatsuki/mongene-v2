"""度数分布・代表値まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l54.calculation Lv1: 階級値・度数の合計
LF_FREQUENCY_TABLE_VALUE_V1 = "{{ given.expressions }}。"

# g1_l55.calculation Lv1: 1階級の相対度数
LF_RELATIVE_FREQUENCY_STATS_SINGLE_V1 = "{{ given.expressions }}。"

# g1_l55.calculation Lv2: 2集団の相対度数比較
LF_COMPARE_RELATIVE_FREQUENCY_V1 = "{{ given.expressions }}。"

# g1_l56.calculation Lv1: 累積度数
LF_CUMULATIVE_FREQUENCY_VALUE_V1 = "{{ given.expressions }}。"

# g1_l56.calculation Lv2: 累積相対度数・以上の割合
LF_CUMULATIVE_RELATIVE_FREQUENCY_AND_COMPLEMENT_V1 = "{{ given.expressions }}。"

# g1_l57.calculation Lv1: 生データの平均値・中央値・最頻値
LF_REPRESENTATIVE_VALUES_RAW_V1 = "{{ given.expressions }}。"

# g1_l57.calculation Lv2: 度数分布表からの平均値
LF_MEAN_FROM_GROUPED_TABLE_V1 = "{{ given.expressions }}。"

# g1_l57.knowledge Lv2: 代表値の使い分け判別
LF_JUDGE_APPROPRIATE_REPRESENTATIVE_VALUE_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_frequency_table_value_v1", LF_FREQUENCY_TABLE_VALUE_V1)
    REGISTRY.register_template(
        "lf_relative_frequency_stats_single_v1", LF_RELATIVE_FREQUENCY_STATS_SINGLE_V1
    )
    REGISTRY.register_template("lf_compare_relative_frequency_v1", LF_COMPARE_RELATIVE_FREQUENCY_V1)
    REGISTRY.register_template("lf_cumulative_frequency_value_v1", LF_CUMULATIVE_FREQUENCY_VALUE_V1)
    REGISTRY.register_template(
        "lf_cumulative_relative_frequency_and_complement_v1",
        LF_CUMULATIVE_RELATIVE_FREQUENCY_AND_COMPLEMENT_V1,
    )
    REGISTRY.register_template("lf_representative_values_raw_v1", LF_REPRESENTATIVE_VALUES_RAW_V1)
    REGISTRY.register_template("lf_mean_from_grouped_table_v1", LF_MEAN_FROM_GROUPED_TABLE_V1)
    REGISTRY.register_template(
        "lf_judge_appropriate_representative_value_v1",
        LF_JUDGE_APPROPRIATE_REPRESENTATIVE_VALUE_V1,
    )


_register_all()


__all__ = [
    "LF_FREQUENCY_TABLE_VALUE_V1",
    "LF_RELATIVE_FREQUENCY_STATS_SINGLE_V1",
    "LF_COMPARE_RELATIVE_FREQUENCY_V1",
    "LF_CUMULATIVE_FREQUENCY_VALUE_V1",
    "LF_CUMULATIVE_RELATIVE_FREQUENCY_AND_COMPLEMENT_V1",
    "LF_REPRESENTATIVE_VALUES_RAW_V1",
    "LF_MEAN_FROM_GROUPED_TABLE_V1",
    "LF_JUDGE_APPROPRIATE_REPRESENTATIVE_VALUE_V1",
]
