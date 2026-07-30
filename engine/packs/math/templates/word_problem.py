"""文章題（form=word_problem）の T1 テンプレート登録（実装設計 §7・§7.2）。

文章題のテンプレは3ブロック構成にする:
  1. `given.scenario`   場面（数量を含む）
  2. `given.quantities` 変数の設定（誘導の第一段）
  3. 小問文 (1)(2)      誘導の本体。品名は `context_slots` から差し込む

小問文を problem_text 側に置く理由: `render_text` が自動生成する prompts は
`f"{asked} を求めなさい。"`（＝"formulation を求めなさい。"）という機械的な文で、
誘導つき文章題では小問文そのものが問題の一部だから。core の prompts 生成規約は
既存 365 セルの golden に影響するので変えない（Open-Closed）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g2_l16.word_problem Lv2: 個数と代金の連立（誘導あり・(1)立式 →(2)個数）
# ---------------------------------------------------------------------------
WP_SYSTEM_PRICE_COUNT_V1 = (
    "{{ given.scenario }}{{ given.quantities }}\n"
    "(1) 個数と代金の関係を表す2つの式をつくれ。\n"
    "(2) {{ context_slots.item_a }}と{{ context_slots.item_b }}をそれぞれ何"
    "{{ context_slots.counter }}買ったか求めよ。"
)


# ---------------------------------------------------------------------------
# 1元1次方程式の利用（g1_l25/l26/l27）: 誘導あり／誘導なしの2枚で6セルを賄う。
#
# 小問文は場面ごとに変わる（「代金の関係を…」「枚数を2通りに表して…」）ので、
# 文言は recipe が `context_slots.ask_formulation` / `ask_value` に載せる。
# テンプレは「どこに何を置くか」だけを決める＝場面が増えてもテンプレは増えない。
# ---------------------------------------------------------------------------
WP_LINEAR_GUIDED_V1 = (
    "{{ given.scenario }}\n"
    "{{ given.quantities }}\n"
    "(1) {{ context_slots.ask_formulation }}\n"
    "(2) {{ context_slots.ask_value }}"
)

# 誘導なし（応用）: 変数の設定も小問の分割も与えず、求める量だけを問う。
WP_LINEAR_SOLO_V1 = "{{ given.scenario }}\n{{ context_slots.ask_value }}"


def _register_all() -> None:
    REGISTRY.register_template("wp_system_price_count_v1", WP_SYSTEM_PRICE_COUNT_V1)
    REGISTRY.register_template("wp_linear_guided_v1", WP_LINEAR_GUIDED_V1)
    REGISTRY.register_template("wp_linear_solo_v1", WP_LINEAR_SOLO_V1)


_register_all()

__all__ = ["WP_LINEAR_GUIDED_V1", "WP_LINEAR_SOLO_V1", "WP_SYSTEM_PRICE_COUNT_V1"]
