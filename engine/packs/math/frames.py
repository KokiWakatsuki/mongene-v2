"""数学パックの frame 定義（form の実装・実装設計 §6.3）。

7 form（knowledge / calculation / find_value / graph_table / word_problem /
proof / construction）それぞれについて `FrameProtocol` を満たす Frame を宣言し、
`register_frame` で登録する。ここでの語彙は §6.3 の表「初版」列を frozenset で
実列挙したもの。proof / construction は M0/M1 対象外のため語彙とコメントのみ
宣言し、ロジックは他 form と同様に一般化された `check_mr` に委ねる。

core（`engine.core.*`）は変更しない。math を import してよいのは pack 側のみ。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.core.contracts import MR, VisualReq
from engine.core.registry import register_frame

# ---------------------------------------------------------------------------
# §6.4 幾何的リーク規則: asked → 禁止される描画要素種別名の写像
# ---------------------------------------------------------------------------
# M0 で具体化するのは find_value / graph_table のみ。他 form は空集合。
_FORBIDDEN_BY_ASKED: dict[str, frozenset[str]] = {
    # find_value: 交点を問うのに方眼＋両直線が同時に描かれていると解かずに読めてしまう
    "intersection": frozenset({"grid_with_both_lines"}),
    # graph_table: 読む対象そのものを図に先出ししてはならない
    "read_intersection": frozenset({"grid_with_both_lines"}),
    # draw_segment（g2_l23 Lv2・かく）: 問題図は空の方眼で禁止要素なし（明示登録）
    "draw_segment": frozenset(),
    # draw_graph（word_problem の融合セル・g3_l38 Lv4）: 場面文だけを与え、問題図は
    # 出さない（生徒が座標軸から自分で構成する）。禁止要素なしを明示登録する
    # ——暗黙に「制約なし」で通すのではなく、意図として書き残すため。
    "draw_graph": frozenset(),
    "read_point": frozenset({"labeled_answer_point"}),
    # 傾き・切片を読む題材でも、答えの点/注記を図に先出ししない
    "read_slope_intercept": frozenset({"labeled_answer_point"}),
    "read_table": frozenset({"completed_table"}),
    "complete_table": frozenset({"completed_table"}),
    # 平行移動/回転移動/対称移動（かく・g1_l38〜l40）: 問題図は移動前の多角形のみ、
    # 移動後の多角形（答え）を先出ししてはならない
    "draw_transformed_polygon": frozenset({"transformed_polygon"}),
    # 箱ひげ図（C11 g2_l56/g2_l57）:
    #   read_box_plot … 読む対象＝箱ひげ図そのものなので図に描いてよい。ただし
    #     5数要約の「値」を図中に注記してはならない（数直線の目もりから読ませる）。
    #   draw_box_plot … 問題図は数直線と目もりだけ。箱ひげ（＝答え）の先出し禁止。
    "read_box_plot": frozenset({"labeled_box_plot_value"}),
    "draw_box_plot": frozenset({"box_plot"}),
}


@dataclass
class Frame:
    """`FrameProtocol` の pack 側実装（全 form 共通の汎用実装）。"""

    form: str
    given_vocab: frozenset[str]
    asked_vocab: frozenset[str]
    visual: VisualReq
    # asked → 追加で禁止する描画要素種別名（このインスタンス固有の拡張分）
    _forbidden_by_asked: dict[str, frozenset[str]] = field(default_factory=dict)

    def check_mr(self, mr: MR) -> tuple[bool, str]:
        """MR が frame 語彙・制約に適合するか（Q2）。"""
        if mr.family.split(".")[-1] != self.form and not mr.family.endswith(f".{self.form}"):
            # family の末尾セグメントが form と一致しない場合でも致命ではないため
            # ここでは判定に使わない（family の命名規約は recipe 側の責務）。
            pass

        unknown_given = [k for k in mr.given.keys() if k not in self.given_vocab]
        if unknown_given:
            return False, f"given_vocab 外のキー: {unknown_given}"

        if not mr.sub_questions:
            return False, "sub_questions が空"

        for sq in mr.sub_questions:
            if sq.asked not in self.asked_vocab:
                return False, f"asked_vocab 外の asked: {sq.asked!r}"

        # visual 宣言との整合（forbidden/none は visual_plan が None であること、
        # required は非 None、optional は自由）
        if self.visual == "none":
            if mr.visual_plan is not None:
                return False, "visual=none の frame に visual_plan が付与されている"
        elif self.visual == "required":
            if mr.visual_plan is None:
                return False, "visual=required の frame に visual_plan が無い"
        # optional は制約なし

        return True, ""

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        """asked と両立しない描画要素の種別（幾何的リーク規則 §6.4）。"""
        result: frozenset[str] = frozenset()
        for a in asked:
            result |= self._forbidden_by_asked.get(a, frozenset())
        return result


# ---------------------------------------------------------------------------
# 7 form の宣言（§6.3 表）
# ---------------------------------------------------------------------------

# calculation: 式・方程式を与え、値/簡約式/解を問う。図は禁止。
CALCULATION_FRAME = Frame(
    form="calculation",
    given_vocab=frozenset({
        "expression", "equation",
        "input_value",  # 横展開#6: 代入する x の値（g2_l19 y=ax+b に x を代入）
        "equation_a", "equation_b",  # 横展開#11: 連立方程式2式（g2_l11 加減法）
        "candidate",  # P1/C2: 代入する (x,y) の組（g2_l10 左辺の値を求める）
        "target_variable",  # P1/C2: 等式を「解く文字」（g2_l9 等式変形）
        "expressions",  # P1/C2: 数の性質を表す複数の式と場面（g2_l7 偶数・奇数の式）
        "sig_figs",  # C1: 科学的記数法で丸める有効数字の桁数（g1_l60 a×10ⁿ Lv2）
    }),
    asked_vocab=frozenset({
        "value", "simplified_expr", "solution",
        "coordinate",  # 横展開#7: 代入して通過点の座標を求める（g2_l22）
        "degree",  # P1/C2: 単項式・多項式の次数を答える（g2_l1）
        "expression",  # P1/C2: 等式を指定文字について解いた式（g2_l9）
    }),
    visual="none",
)

# knowledge: 命題・用語文脈を与え、用語/真偽/選択を問う。図は禁止（M0）。
# Answer型: ChoiceAnswer（fact テーブル照合・V2 水準。§6.2 参照）
KNOWLEDGE_FRAME = Frame(
    form="knowledge",
    given_vocab=frozenset({"statement", "term_context"}),
    asked_vocab=frozenset({"term", "true_false", "choice"}),
    visual="none",
)

# find_value: 座標・傾き・切片・係数・条件・図形仕様を与え、値/式/座標/変化の割合/
# 定義域値域/交点/面積を問う。図は optional/required（asked により §6.4 の禁止規則が動く）。
FIND_VALUE_FRAME = Frame(
    form="find_value",
    given_vocab=frozenset({
        "point_a", "point_b", "slope", "intercept", "expression_coeffs",
        "condition", "figure_spec",
        "line_a", "line_b",  # 横展開: 2直線の交点（g2_l27）で2本の直線式を与える
        "expression", "x_domain", "y_range",  # 横展開: 変域とグラフの端点（g2_l23）
    }),
    asked_vocab=frozenset({
        "value", "expression", "coordinate", "rate_of_change",
        "domain_range", "intersection", "area",
    }),
    visual="optional",
    _forbidden_by_asked={
        "intersection": _FORBIDDEN_BY_ASKED["intersection"],
    },
)

# graph_table: 式・データ表・状況パラメータを与え、かく/読むを問う。図は required。
# Answer型: 「かく」= GraphAnswer / 「読む」= SymbolicAnswer（§6.2 V1'）
GRAPH_TABLE_FRAME = Frame(
    form="graph_table",
    given_vocab=frozenset({
        "expression", "data_table", "situation_params",
        "equation",  # 横展開#9: 2元1次方程式 ax+by=c を変形してかく（g2_l26）
        "equation2",  # P1/C5: 特殊直線 x=k / y=k を追加で与える（g2_l26 Lv2）
        "x_domain",  # P1/C5: 変域つきグラフを線分でかく（g2_l23 Lv2）
        # C3 g3_l31: 動点の場面（文章で与える状況）から面積の時間変化をグラフにかく。
        # find_value 側と同じキー名を使う（同じ題材・同じ与え方を form 間で揃える）。
        "condition",
        "line_a", "line_b",  # 横展開#10: 2直線をかき交点を読む（g2_l27 graph）
        # C7 g1平面図形（横展開#94）: 移動前の多角形（Lv1=方眼上の説明文/Lv2=座標つき説明文）
        # ＋移動の指定。Lv1/Lv2 でキー名を分ける（level_sep・G-FP: 同一 family 内で
        # 同じ solver を使い回すため、given_types の相異だけで fp を分離する）。
        "polygon_points", "polygon_coordinates", "move_spec",
    }),
    asked_vocab=frozenset({
        "draw_graph", "read_point", "read_intersection", "read_table", "complete_table",
        "read_slope_intercept",  # 横展開#4: グラフから傾き・切片を読む（g2_l21）
        "draw_segment",  # P1/C5: 端点の開閉を区別して線分をかく（g2_l23 Lv2）
        "draw_transformed_polygon",  # C7 g1平面図形: 平行移動/回転移動/対称移動をかく
        # C11 箱ひげ図（g2_l56/g2_l57）: 箱ひげ図を読む／データから求めてかく
        "read_box_plot", "draw_box_plot",
    }),
    visual="required",
    _forbidden_by_asked={
        "read_intersection": _FORBIDDEN_BY_ASKED["read_intersection"],
        "read_point": _FORBIDDEN_BY_ASKED["read_point"],
        "read_slope_intercept": _FORBIDDEN_BY_ASKED["read_slope_intercept"],
        "read_table": _FORBIDDEN_BY_ASKED["read_table"],
        "complete_table": _FORBIDDEN_BY_ASKED["complete_table"],
        "draw_segment": _FORBIDDEN_BY_ASKED["draw_segment"],
        "draw_transformed_polygon": _FORBIDDEN_BY_ASKED["draw_transformed_polygon"],
        "read_box_plot": _FORBIDDEN_BY_ASKED["read_box_plot"],
        "draw_box_plot": _FORBIDDEN_BY_ASKED["draw_box_plot"],
    },
)

# word_problem: 場面（T3）・数量を与え、立式/値を問う。図は optional。
# word_problem に `draw_graph` を入れる理由（2026-08-07）:
# 中学の文章題には「関係をグラフに表し、そのうえで値を求めよ」という融合問題があり
# （g3_l38 Lv4・g2_l29 Lv4 の台帳 example がまさにこれ）、場面文を読んで自分で
# 区間に分け、グラフを構成してから答えるところまでが一続きの問いになっている。
# これを graph_table 側に置くと場面文（scenario/quantities）が使えず、
# word_problem 側で asked を封じると台帳の example を実装できない。
# フレームの分担は「文章題か図の問題か」であって「図をかかせるか否か」ではないので、
# word_problem（visual=optional）に作図の asked を1つ足す。
# 問題図に答えのグラフを先出ししないことは _FORBIDDEN_BY_ASKED で graph_table と
# 同じ規約に揃える。
WORD_PROBLEM_FRAME = Frame(
    form="word_problem",
    given_vocab=frozenset({"scenario", "quantities"}),
    asked_vocab=frozenset({"formulation", "value", "draw_graph"}),
    visual="optional",
    _forbidden_by_asked={"draw_graph": _FORBIDDEN_BY_ASKED["draw_graph"]},
)

# proof（M1 対象・M0 は宣言のみ）: 前提・結論を与え、証明文を問う。
# visual: optional / Answer型: （M1 で定義。現状は宣言のみで実装対象外）
PROOF_FRAME = Frame(
    form="proof",
    given_vocab=frozenset({"premises", "conclusion"}),
    asked_vocab=frozenset({"proof_text"}),
    visual="optional",
)

# construction（M2 対象・M0 は宣言のみ）: 作図条件を与え、作図手順を問う。
# visual: required / Answer型: GraphAnswer
CONSTRUCTION_FRAME = Frame(
    form="construction",
    given_vocab=frozenset({"construction_conditions"}),
    asked_vocab=frozenset({"construction_steps"}),
    visual="required",
)


def _register_all() -> None:
    for f in (
        CALCULATION_FRAME,
        KNOWLEDGE_FRAME,
        FIND_VALUE_FRAME,
        GRAPH_TABLE_FRAME,
        WORD_PROBLEM_FRAME,
        PROOF_FRAME,
        CONSTRUCTION_FRAME,
    ):
        register_frame(f)


_register_all()


__all__ = [
    "Frame",
    "CALCULATION_FRAME",
    "KNOWLEDGE_FRAME",
    "FIND_VALUE_FRAME",
    "GRAPH_TABLE_FRAME",
    "WORD_PROBLEM_FRAME",
    "PROOF_FRAME",
    "CONSTRUCTION_FRAME",
]
