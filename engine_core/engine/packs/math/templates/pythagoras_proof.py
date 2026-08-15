"""三平方の定理の証明／その逆の T1 テンプレート（form: proof・g3_l51 / g3_l52）。

問いの言い方は市販の問題集がこの型で書いているので、テンプレートで揺らさない
（`number_proof` / `conditional_proof` と同じ方針）。**Lv 差はテンプレートに出る**:
Lv3 は図の並べ方を問題文が与えて「面積を2通りに表して示せ」、Lv4 は図の設定を
生徒に委ねて「面積の考えを用いて証明せよ」と問う（台帳 example の言い方の転記）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l51 Lv3（誘導あり）: 並べ方も内側の図形の記号も問題文が与える。
PF_PYTHAGORAS_GUIDED_V1 = (
    "{{ given.premises }}。この図の面積を2通りに表して、"
    "{{ given.conclusion }} が成り立つことを示せ。"
)

# g3_l51 Lv4（誘導なし）: どの図でどう分けるかは生徒が立てる。
PF_PYTHAGORAS_OPEN_V1 = (
    "{{ given.premises }}について、{{ given.conclusion }} が成り立つことを、"
    "面積の考えを用いて証明せよ。図や補助線は自分で決めてよい。"
)

# g3_l52 Lv3（定理の逆）: 3辺の長さから、ある角が直角であることを説明する。
PF_PYTHAGORAS_CONVERSE_V1 = (
    "{{ given.premises }}。三平方の定理の逆を用いて、{{ given.conclusion }}ことを説明せよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("pf_pythagoras_guided_v1", PF_PYTHAGORAS_GUIDED_V1)
    REGISTRY.register_template("pf_pythagoras_open_v1", PF_PYTHAGORAS_OPEN_V1)
    REGISTRY.register_template("pf_pythagoras_converse_v1", PF_PYTHAGORAS_CONVERSE_V1)


_register_all()


__all__ = [
    "PF_PYTHAGORAS_CONVERSE_V1",
    "PF_PYTHAGORAS_GUIDED_V1",
    "PF_PYTHAGORAS_OPEN_V1",
]
