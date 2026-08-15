"""C8 g1 空間図形クラスタ（g1_l47/l48/l53 の knowledge）の T1 テンプレート（§7）。

用語想起（g1_l47/l48/l49/l50 Lv1）は既存の `lf_term_recall_v1` を共有するため、
ここには判別型（Lv2）と公式想起（g1_l53 Lv1）の文言だけを登録する。
テンプレは given のみ参照する（answer/params は参照不能＝Q5 の構造防止）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l47.knowledge Lv2: 多面体についての主張の正誤を判別する
SP_POLYHEDRON_CLAIM_V1 = (
    "次のことがらは正しいですか、誤りですか。\n{{ given.statement }}。"
)
# g1_l48.knowledge Lv2: 直方体の 辺と辺／辺と面 の位置関係を判別する
SP_POSITION_RELATION_V1 = "{{ given.statement }}を、次の中から1つ選べ。"
# g1_l53.knowledge Lv1: 球の表面積・体積の公式を想起する
SP_SPHERE_FORMULA_V1 = "{{ given.statement }}として正しいものを1つ選べ。"


def _register_all() -> None:
    REGISTRY.register_template("sp_polyhedron_claim_v1", SP_POLYHEDRON_CLAIM_V1)
    REGISTRY.register_template("sp_position_relation_v1", SP_POSITION_RELATION_V1)
    REGISTRY.register_template("sp_sphere_formula_v1", SP_SPHERE_FORMULA_V1)


_register_all()


__all__ = [
    "SP_POLYHEDRON_CLAIM_V1",
    "SP_POSITION_RELATION_V1",
    "SP_SPHERE_FORMULA_V1",
]
