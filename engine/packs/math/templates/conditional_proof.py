"""仮定と結論の証明・反例による否定の T1 テンプレート（form: proof・g2_l38）。

問いの言い方は市販の問題集がこの型で書いているので、テンプレートで揺らさない
（`number_proof` と同じ方針）。**Lv 差はテンプレートに出る**: Lv2 は文字のおき方を
問題文が与えて「証明せよ」で閉じ、Lv3 は命題だけを与えて「正しいかどうかを判断し、
正しければ証明を、正しくなければ反例を示せ」と問う（台帳 example の言い方の転記）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# Lv2（誘導あり）: 何をどう文字でおくかを問題文が与える。
PF_CONDITIONAL_GUIDED_V1 = "「{{ given.conclusion }}」ことを、{{ given.premises }}証明せよ。"

# Lv3（誘導なし）: 真偽の判断そのものが問い。
PF_CONDITIONAL_JUDGE_V1 = (
    "「{{ given.conclusion }}」という命題が正しいかどうかを判断し、"
    "正しければ証明を、正しくなければ反例を示せ。"
)


def _register_all() -> None:
    REGISTRY.register_template("pf_conditional_guided_v1", PF_CONDITIONAL_GUIDED_V1)
    REGISTRY.register_template("pf_conditional_judge_v1", PF_CONDITIONAL_JUDGE_V1)


_register_all()


__all__ = ["PF_CONDITIONAL_GUIDED_V1", "PF_CONDITIONAL_JUDGE_V1"]
