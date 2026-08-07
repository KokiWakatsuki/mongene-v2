"""箱ひげ図（graph_table）の T1 テンプレート登録（実装設計 §7・§7.2）。

**テンプレートに数字を書かない**（G-Q5t の設計原則）。序数は漢数字で書く
（"第3四分位数" と書くと、答えの値 "3" と衝突して漏洩が誤検出される）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g2_l56.graph_table Lv1: 箱ひげ図から二つの値を読む
BP_READ_BOX_PLOT_V1 = (
    "{{ given.situation_params }}がある。この箱ひげ図から、"
    "{{ given.condition }}を読み取れ。"
)

# g2_l56.graph_table Lv3: データから5数要約を求め箱ひげ図をかく
BP_DRAW_BOX_PLOT_V1 = (
    "次のデータについて、最小値・第一四分位数・中央値・第三四分位数・最大値を求め、"
    "それをもとに数直線の上に箱ひげ図を正確にかけ。データ: {{ given.data_table }}"
)

# g2_l57.graph_table Lv1: 2本の箱ひげ図から中央値と範囲を読む
BP_READ_TWO_BOX_PLOTS_V1 = (
    "{{ given.situation_params }}がある。AとBそれぞれについて、"
    "中央値と範囲を箱ひげ図から読み取れ。"
)

# g2_l57.graph_table Lv3: 2本の箱ひげ図の四分位範囲を比べる
BP_COMPARE_TWO_BOX_PLOTS_IQR_V1 = (
    "{{ given.situation_params }}がある。AとBそれぞれの四分位範囲を求め、"
    "散らばりの違いとしてその差を答えよ。"
)


# g2_l57.word_problem Lv2: 誘導あり・中央値と範囲を比べる（2小問）
WP_BOX_PLOT_COMPARE_V1 = (
    "{{ given.scenario }}がある。"
    "(1) 中央値が大きいのはA、Bのどちらか、記号で答えよ。"
    "(2) 範囲が大きいのはA、Bのどちらか、記号で答えよ。"
    "また、その違いから読み取れる散らばりのようすを説明せよ。"
)

# g2_l57.word_problem Lv3: 誘導なし・複数の観点から傾向の主張の当否を判断する
WP_BOX_PLOT_TREND_V1 = (
    "{{ given.scenario }}がある。{{ given.quantities }}がいえるかどうかを、"
    "中央値・四分位数など複数の観点を選び、根拠とともに判断して"
    "「いえる」「いえない」で答えよ。"
)

# g2_l57.word_problem Lv4: 誘導なし・支持する根拠と反論の両方を挙げて批判的に判断する
WP_BOX_PLOT_STABILITY_V1 = (
    "{{ given.scenario }}がある。{{ given.quantities }}が妥当かどうかを、"
    "この主張を支持する根拠と、反論となる根拠の両方を自分で挙げたうえで批判的に判断し、"
    "「妥当である」「妥当でない」で答えよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("wp_box_plot_compare_v1", WP_BOX_PLOT_COMPARE_V1)
    REGISTRY.register_template("wp_box_plot_trend_v1", WP_BOX_PLOT_TREND_V1)
    REGISTRY.register_template("wp_box_plot_stability_v1", WP_BOX_PLOT_STABILITY_V1)
    REGISTRY.register_template("bp_read_box_plot_v1", BP_READ_BOX_PLOT_V1)
    REGISTRY.register_template("bp_draw_box_plot_v1", BP_DRAW_BOX_PLOT_V1)
    REGISTRY.register_template("bp_read_two_box_plots_v1", BP_READ_TWO_BOX_PLOTS_V1)
    REGISTRY.register_template(
        "bp_compare_two_box_plots_iqr_v1", BP_COMPARE_TWO_BOX_PLOTS_IQR_V1
    )


_register_all()


__all__ = [
    "BP_READ_BOX_PLOT_V1",
    "BP_DRAW_BOX_PLOT_V1",
    "BP_READ_TWO_BOX_PLOTS_V1",
    "BP_COMPARE_TWO_BOX_PLOTS_IQR_V1",
    "WP_BOX_PLOT_COMPARE_V1",
    "WP_BOX_PLOT_TREND_V1",
    "WP_BOX_PLOT_STABILITY_V1",
]
