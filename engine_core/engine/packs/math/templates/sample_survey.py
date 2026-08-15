"""標本調査まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l59.calculation Lv1: 標本比率・比例式による推定値
LF_SAMPLE_RATIO_ESTIMATE_V1 = "{{ given.expressions }}。"

# g3_l60.calculation Lv2: 比例式で母集団の大きさ x を解く
LF_SAMPLE_RATIO_SOLVE_POPULATION_V1 = "{{ given.expressions }}。"

# g3_l57.knowledge Lv2: 全数調査/標本調査の判別
LF_JUDGE_APPROPRIATE_SURVEY_METHOD_V1 = "{{ given.statement }}。"

# g3_l58.knowledge Lv2: 抽出方法の偏りの判別
LF_JUDGE_SAMPLING_BIAS_V1 = "{{ given.statement }}。"

# g3_l59.knowledge Lv1: 標本比率≒母比率の考え方の説明
LF_EXPLAIN_SAMPLE_RATIO_RATIONALE_V1 = "{{ given.statement }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_sample_ratio_estimate_v1", LF_SAMPLE_RATIO_ESTIMATE_V1)
    REGISTRY.register_template(
        "lf_sample_ratio_solve_population_v1", LF_SAMPLE_RATIO_SOLVE_POPULATION_V1
    )
    REGISTRY.register_template(
        "lf_judge_appropriate_survey_method_v1", LF_JUDGE_APPROPRIATE_SURVEY_METHOD_V1
    )
    REGISTRY.register_template("lf_judge_sampling_bias_v1", LF_JUDGE_SAMPLING_BIAS_V1)
    REGISTRY.register_template(
        "lf_explain_sample_ratio_rationale_v1", LF_EXPLAIN_SAMPLE_RATIO_RATIONALE_V1
    )


_register_all()


__all__ = [
    "LF_SAMPLE_RATIO_ESTIMATE_V1",
    "LF_SAMPLE_RATIO_SOLVE_POPULATION_V1",
    "LF_JUDGE_APPROPRIATE_SURVEY_METHOD_V1",
    "LF_JUDGE_SAMPLING_BIAS_V1",
    "LF_EXPLAIN_SAMPLE_RATIO_RATIONALE_V1",
]
