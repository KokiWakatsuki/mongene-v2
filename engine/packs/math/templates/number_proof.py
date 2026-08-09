"""文字式による数の性質の説明の T1 テンプレート（form: proof）。

問いの言い方は市販の問題集がこの型で書いているので、テンプレートで揺らさない
（`plane_geometry.PF_GEOMETRY_PROOF_V1` と同じ方針）。**Lv 差はテンプレートに出る**:
誘導ありは「書き出し」を鍵かっこで与え、誘導なしは命題だけを与える。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# Lv2（誘導あり）: 文字のおき方と、式を書き出すところまでを問題文が与える。
PF_NUMBER_PROPERTY_GUIDED_V1 = (
    "{{ given.conclusion }}。このことを、次の書き出しに続けて説明せよ。"
    "「{{ given.premises }}」"
)

# Lv3（誘導なし）: 何を文字でおくかも自分で決める。
PF_NUMBER_PROPERTY_OPEN_V1 = "{{ given.conclusion }}。このことを、文字を使って説明せよ。"


def _register_all() -> None:
    REGISTRY.register_template(
        "pf_number_property_guided_v1", PF_NUMBER_PROPERTY_GUIDED_V1
    )
    REGISTRY.register_template("pf_number_property_open_v1", PF_NUMBER_PROPERTY_OPEN_V1)


_register_all()


__all__ = ["PF_NUMBER_PROPERTY_GUIDED_V1", "PF_NUMBER_PROPERTY_OPEN_V1"]
