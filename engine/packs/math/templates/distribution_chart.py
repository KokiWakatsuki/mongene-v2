"""分布のグラフ（graph_table）の T1 テンプレート登録（実装設計 §7・§7.2）。

given のキーごとに1つ（レベルごとではない）。問題文は given の文そのもの＝
G-Q5t の whitelist（given 由来の数値）と本文の数値が一致し、図から読ませる値だけが
本文に出ない、という関係を保つ。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# 「読む」セル（場面と階級の作り方だけを述べ、度数は図からしか読めない）
DF_SITUATION_V1 = "{{ given.situation_params }}。"

# 「かく」セル（生データ・度数分布表を本文に載せる）
DF_DATA_TABLE_V1 = "{{ given.data_table }}。"

# 2つの分布を重ねたグラフを読む条件つきのセル
DF_CONDITION_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("df_situation_v1", DF_SITUATION_V1)
    REGISTRY.register_template("df_data_table_v1", DF_DATA_TABLE_V1)
    REGISTRY.register_template("df_condition_v1", DF_CONDITION_V1)


_register_all()


__all__ = ["DF_SITUATION_V1", "DF_DATA_TABLE_V1", "DF_CONDITION_V1"]
