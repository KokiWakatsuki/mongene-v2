"""文字式まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

テンプレは TemplateContext の公開変数（given / sub_questions[].{label,asked,narrations}）
のみ参照できる。answer/params は属性として存在しないため参照不能（Q5 の構造防止）。
テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。

一次式の計算（g1_l17/l18）は arithmetic の `lf_calc_evaluate_v1`（"次の計算をせよ"）を共有する。
本モジュールは代入（g1_l16）など専用の文言を登録する。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l16.calculation Lv1/Lv2: 式に数を代入して式の値を求める
LF_SUBSTITUTE_VALUE_V1 = (
    "x = {{ given.input_value }} のとき、次の式の値を求めよ。\n{{ given.expression }}"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_substitute_value_v1", LF_SUBSTITUTE_VALUE_V1)


_register_all()


__all__ = ["LF_SUBSTITUTE_VALUE_V1"]
