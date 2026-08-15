"""四分位数・箱ひげ図まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g2_l55.calculation Lv1: 中央値（第2四分位数）
LF_MEDIAN_VALUE_V1 = "{{ given.expressions }}。"

# g2_l55.calculation Lv3: 第1/第3四分位数・四分位範囲
LF_QUARTILES_IQR_V1 = "{{ given.expressions }}。"

# g2_l56.calculation Lv1: 最小値・最大値・第1/第3四分位数
LF_FIVE_NUMBER_SUMMARY_V1 = "{{ given.expressions }}。"

# g2_l57.knowledge Lv1: 統計量が分布の何を表すか判別
LF_CLASSIFY_DISTRIBUTION_STATISTIC_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_median_value_v1", LF_MEDIAN_VALUE_V1)
    REGISTRY.register_template("lf_quartiles_iqr_v1", LF_QUARTILES_IQR_V1)
    REGISTRY.register_template("lf_five_number_summary_v1", LF_FIVE_NUMBER_SUMMARY_V1)
    REGISTRY.register_template(
        "lf_classify_distribution_statistic_v1", LF_CLASSIFY_DISTRIBUTION_STATISTIC_V1
    )


_register_all()


__all__ = [
    "LF_MEDIAN_VALUE_V1",
    "LF_QUARTILES_IQR_V1",
    "LF_FIVE_NUMBER_SUMMARY_V1",
    "LF_CLASSIFY_DISTRIBUTION_STATISTIC_V1",
]
