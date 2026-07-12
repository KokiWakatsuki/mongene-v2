"""多項式（式の計算）まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

Jinja2 文字列を `registry.register_template(name, src)` で登録する。テンプレは
TemplateContext の公開変数（given / context_slots / sub_questions[].{label,asked,
narrations}）のみ参照できる。answer/params は属性として存在しないため構文的に
参照不能（Q5 の構造防止）。

テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g2_l2.calculation Lv1/Lv2: 同類項をまとめる（C2 クラスタ初セル）
# ---------------------------------------------------------------------------
LF_COMBINE_LIKE_TERMS_V1 = "次の式の同類項をまとめよ。\n{{ given.expression }}"


def _register_all() -> None:
    REGISTRY.register_template("lf_combine_like_terms_v1", LF_COMBINE_LIKE_TERMS_V1)


_register_all()


__all__ = [
    "LF_COMBINE_LIKE_TERMS_V1",
]
