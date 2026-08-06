"""比例・反比例の **グラフ**（graph_table）T1 テンプレート登録（実装設計 §7・§7.2）。

テンプレは TemplateContext の公開変数（given / context_slots / sub_questions）のみ参照できる。
テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。

**テンプレートに数字を書かない**（G-Q5t の設計原則）: 問題文に出る数値をすべて given 由来に
すると、漏洩検査の whitelist（given から機械構築）が本文の数値を必ず覆う。数える語は
漢数字で書く（「二つ」「三本」）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g1_l30.graph_table Lv1: 座標平面上の点の座標を読む
# ---------------------------------------------------------------------------
PROPG_READ_COORDINATE_V1 = (
    "{{ given.situation_params }}。点Aの座標を、x座標とy座標を並べた形で答えよ。"
    "また、座標平面上に点Aをとれ。"
)

# ---------------------------------------------------------------------------
# g1_l30.graph_table Lv2: 対称な点を条件から座標平面に配置する
# ---------------------------------------------------------------------------
PROPG_REFLECT_POINT_V1 = (
    "{{ given.situation_params }}。点Bと点Cの座標をそれぞれ答え、"
    "三つの点を座標平面上に示せ。"
)

# ---------------------------------------------------------------------------
# g1_l31.graph_table Lv1: 比例のグラフから対応する値を読む
# ---------------------------------------------------------------------------
PROPG_READ_VALUE_V1 = "{{ given.situation_params }}を、グラフから読み取って答えよ。"

# ---------------------------------------------------------------------------
# g1_l31.graph_table Lv2: 式 y=ax のグラフをかく
# ---------------------------------------------------------------------------
PROPG_DRAW_GRAPH_V1 = (
    "比例の式 {{ given.expression }} のグラフを座標平面上にかけ。"
    "{{ given.situation_params }}を明示すること。"
)

# ---------------------------------------------------------------------------
# g1_l31.graph_table Lv3: 3本の比例のグラフを比べる
# ---------------------------------------------------------------------------
PROPG_COMPARE_GRAPHS_V1 = (
    "同じ座標平面上に、比例のグラフ {{ given.expression }} をかく。"
    "このうち、最も傾きが急なグラフと、右下がりのグラフの比例定数を、この順に答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l32.graph_table Lv1: 比例のグラフ上の格子点を読む（given は空）
# ---------------------------------------------------------------------------
PROPG_READ_LATTICE_V1 = (
    "座標平面上に、原点を通る直線のグラフがある。このグラフが通る格子点"
    "（x座標もy座標も整数である点）を、原点以外に一つ読み取り、その座標を答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l34.graph_table Lv1: 双曲線から対応する値を読む
# ---------------------------------------------------------------------------
PROPG_READ_HYPERBOLA_VALUE_V1 = (
    "反比例 {{ given.expression }} のグラフである双曲線がある。"
    "{{ given.situation_params }}を、グラフから読み取って答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l34.graph_table Lv2: 表から双曲線を2つの枝でかく
# ---------------------------------------------------------------------------
PROPG_DRAW_HYPERBOLA_V1 = (
    "反比例 {{ given.expression }} について、{{ given.data_table }} に対応する y の値を"
    "表にまとめ、それらの点を座標平面上にとって、双曲線を二つの枝でかけ。"
)

# ---------------------------------------------------------------------------
# g1_l34.graph_table Lv3: 3本の双曲線を比べる
# ---------------------------------------------------------------------------
PROPG_COMPARE_HYPERBOLAS_V1 = (
    "同じ座標平面上に、反比例のグラフ {{ given.expression }} をかく。"
    "このうち、第2象限と第4象限にあるグラフと、原点から最も離れて位置するグラフの"
    "比例定数を、この順に答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l35.graph_table Lv1: 双曲線上の格子点を読む（given は空）
# ---------------------------------------------------------------------------
PROPG_READ_LATTICE_HYPERBOLA_V1 = (
    "座標平面上に、反比例のグラフである双曲線がある。この曲線が通る格子点"
    "（x座標もy座標も整数である点）を一つ読み取り、その座標を答えよ。"
)

# ---------------------------------------------------------------------------
# g1_l36.graph_table Lv2: 場面の対応を表とグラフに表して読む
# ---------------------------------------------------------------------------
PROPG_SITUATION_GRAPH_V1 = (
    "{{ given.condition }}を求めたい。測った組を表にまとめ、"
    "座標平面上に点をとってグラフに表し、たずねられた深さをグラフから読み取れ。"
)

# ---------------------------------------------------------------------------
# g1_l36.graph_table Lv3: 2つの料金プランを1つのグラフで比べ交点を読む
# ---------------------------------------------------------------------------
PROPG_TWO_PLANS_GRAPH_V1 = (
    "{{ given.condition }}を、A社とB社について同じ座標平面上にグラフでかき、"
    "二つのグラフの交点の座標（料金が等しくなる枚数と、そのときの料金）を読み取れ。"
)


def _register_all() -> None:
    REGISTRY.register_template("propg_read_coordinate_v1", PROPG_READ_COORDINATE_V1)
    REGISTRY.register_template("propg_reflect_point_v1", PROPG_REFLECT_POINT_V1)
    REGISTRY.register_template("propg_read_value_v1", PROPG_READ_VALUE_V1)
    REGISTRY.register_template("propg_draw_graph_v1", PROPG_DRAW_GRAPH_V1)
    REGISTRY.register_template("propg_compare_graphs_v1", PROPG_COMPARE_GRAPHS_V1)
    REGISTRY.register_template("propg_read_lattice_v1", PROPG_READ_LATTICE_V1)
    REGISTRY.register_template(
        "propg_read_hyperbola_value_v1", PROPG_READ_HYPERBOLA_VALUE_V1
    )
    REGISTRY.register_template("propg_draw_hyperbola_v1", PROPG_DRAW_HYPERBOLA_V1)
    REGISTRY.register_template(
        "propg_compare_hyperbolas_v1", PROPG_COMPARE_HYPERBOLAS_V1
    )
    REGISTRY.register_template(
        "propg_read_lattice_hyperbola_v1", PROPG_READ_LATTICE_HYPERBOLA_V1
    )
    REGISTRY.register_template("propg_situation_graph_v1", PROPG_SITUATION_GRAPH_V1)
    REGISTRY.register_template("propg_two_plans_graph_v1", PROPG_TWO_PLANS_GRAPH_V1)


_register_all()


__all__ = [
    "PROPG_READ_COORDINATE_V1",
    "PROPG_REFLECT_POINT_V1",
    "PROPG_READ_VALUE_V1",
    "PROPG_DRAW_GRAPH_V1",
    "PROPG_COMPARE_GRAPHS_V1",
    "PROPG_READ_LATTICE_V1",
    "PROPG_READ_HYPERBOLA_VALUE_V1",
    "PROPG_DRAW_HYPERBOLA_V1",
    "PROPG_COMPARE_HYPERBOLAS_V1",
    "PROPG_READ_LATTICE_HYPERBOLA_V1",
    "PROPG_SITUATION_GRAPH_V1",
    "PROPG_TWO_PLANS_GRAPH_V1",
]
