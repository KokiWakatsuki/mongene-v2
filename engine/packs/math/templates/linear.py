"""一次関数まわりの T1 テンプレート登録（実装設計 §7・§7.2）。

Jinja2 文字列を `registry.register_template(name, src)` で登録する。テンプレは
TemplateContext の公開変数（given / context_slots / sub_questions[].label / .asked /
.narrations）のみ参照できる。answer/srepr/params は属性として存在しないため
構文的に参照不能（Q5 の構造防止）。

テンプレ名は FamilySpec の `text.template` と一致させる（spec_lint R1 が検査）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# ---------------------------------------------------------------------------
# g2_l25.find_value: 2点から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_TWO_POINTS_V1 = (
    "2点 {{ given.point_a }} と {{ given.point_b }} を通る直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l24.find_value Lv1: 傾きと1点から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_SLOPE_POINT_V1 = (
    "傾きが {{ given.slope }} で、点 {{ given.point_a }} を通る直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l24.find_value Lv3: 平行条件から式を求める
# ---------------------------------------------------------------------------
LF_EXPR_PARALLEL_V1 = (
    "点 {{ given.point_a }} を通り、直線 {{ given.condition }} に平行な直線の式を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l25.graph_table Lv2: グラフ上の2格子点を読む
# ---------------------------------------------------------------------------
GRAPH_READ_TWO_POINTS_V1 = (
    "グラフ上の直線が通る2つの格子点の座標を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l21.graph_table Lv1: グラフから傾きと切片を読む（横展開#4）
# given は空（式は提示せず図のみ）。answer/params は参照不能なので数値は本文に出ない。
# ---------------------------------------------------------------------------
GRAPH_READ_SLOPE_INTERCEPT_V1 = (
    "座標平面にかかれた直線のグラフから、この直線の傾きと切片を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l26.calculation Lv1: ax+by=c を y=… に変形する（横展開#5・最初の calculation セル）
# ---------------------------------------------------------------------------
LF_SOLVE_FOR_Y_V1 = (
    "2元1次方程式 {{ given.equation }} を、y について解いた式（y = … の形）に変形せよ。"
)


# ---------------------------------------------------------------------------
# g2_l19.calculation Lv1: y=ax+b に x を代入して y を求める（横展開#6）
# ---------------------------------------------------------------------------
LF_EVALUATE_AT_X_V1 = (
    "1次関数 {{ given.expression }} について、{{ given.input_value }} のときの y の値を求めよ。"
)


# ---------------------------------------------------------------------------
# g2_l22.calculation Lv1: グラフが通る点を代入で求める（横展開#7・answer=coordinate）
# ---------------------------------------------------------------------------
LF_POINT_ON_LINE_V1 = (
    "1次関数 {{ given.expression }} のグラフが通る点のうち、"
    "x 座標が {{ given.input_value }} である点の座標を求めよ。"
)


# ---------------------------------------------------------------------------
# g2_l22.graph_table Lv1: y=ax+b のグラフをかく（横展開#8・「かく」capability）
# 問題図＝空の方眼。答えは GraphAnswer（特徴点）＋模範解答図。
# ---------------------------------------------------------------------------
LF_DRAW_GRAPH_V1 = (
    "1次関数 {{ given.expression }} のグラフを、座標平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l22.graph_table Lv3: 分数の傾きのグラフを格子点を通るようにかく（P1/C5）
# 傾き・切片は given.expression の係数由来で whitelist（両符号化）。
# ---------------------------------------------------------------------------
LF_DRAW_GRAPH_FRACTION_V1 = (
    "1次関数 {{ given.expression }} のグラフを、通る格子点を利用して"
    "正確に座標平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l26.graph_table Lv1: ax+by=c を変形してグラフをかく（横展開#9・「かく」流用）
# ---------------------------------------------------------------------------
LF_DRAW_FROM_EQUATION_V1 = (
    "2元1次方程式 {{ given.equation }} のグラフを、y=… の形に変形してから座標平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l27.graph_table Lv1: 2直線をかき交点をグラフから読む（横展開#10）
# 「2直線」ではなく「2本の直線」: 助数詞「本」は G-Q5t 除外対象で先頭 "2" が答え座標と
# 衝突する偽陽性を避ける（数値答えセルの定石）。
# ---------------------------------------------------------------------------
LF_READ_INTERSECTION_V1 = (
    "2本の直線 {{ given.line_a }} と {{ given.line_b }} を同じ座標平面にかき、"
    "その交点の座標を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l30.graph_table Lv2: ダイヤグラム（時間-道のり）の2直線の交点を読む（P1/C5）
# 式は既知として与え、グラフ読解のみを問う（立式は word_problem l30）。
# 「2つの直線」: 助数詞「つ」は G-Q5t 除外対象で先頭 "2" が答え座標と衝突する偽陽性を避ける。
# ---------------------------------------------------------------------------
LF_READ_DIAGRAM_INTERSECTION_V1 = (
    "AさんとBさんが動くようすを、出発してからの時間 x とP地点からの道のり y の関係で表す。"
    "Aさんの進むようすは {{ given.line_a }}、Bさんの進むようすは {{ given.line_b }} である。"
    "この2つの直線を同じ座標平面にかき、2つの直線が交わる点の座標"
    "（2人が同じ地点にいる時間と、そのときの道のり）を読み取れ。"
)


# ---------------------------------------------------------------------------
# g2_l26.graph_table Lv2: 切片法で2元1次方程式をかき、特殊直線 x=k / y=k もかく（P1/C5）
# 式は given（equation / equation2）で提示＝答えの交点値は given 係数由来で whitelist。
# ---------------------------------------------------------------------------
LF_DRAW_SPECIAL_LINES_V1 = (
    "2元1次方程式 {{ given.equation }} のグラフを、x 軸・y 軸との交点を利用して"
    "座標平面にかけ。また、方程式 {{ given.equation2 }} のグラフも同じ平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l28.graph_table Lv2: 対応表からグラフ（直線）をかく（P1/C5）
# 表の数値は given.data_table（whitelist 対象）。答えの傾き・切片は表から読み取れる。
# ---------------------------------------------------------------------------
LF_DRAW_FROM_TABLE_V1 = (
    "次の表は、x と y の関係を表したものである。"
    "この関係を表すグラフ（直線）を座標平面にかけ。\n{{ given.data_table }}"
)


# ---------------------------------------------------------------------------
# g2_l23.graph_table Lv2: 変域つき1次関数を端点の開閉を区別して線分でかく（P1/C5）
# 変域の不等号（given.x_domain の ≦/<）が端点の開閉を表す。答えの端点値は given 係数由来。
# ---------------------------------------------------------------------------
LF_DRAW_SEGMENT_V1 = (
    "1次関数 {{ given.expression }}（{{ given.x_domain }}）のグラフを、"
    "両端の点をふくむ・ふくまないがわかるように線分で座標平面にかけ。"
)


# ---------------------------------------------------------------------------
# g2_l11.calculation Lv1: 連立方程式を加減法で解く（横展開#11・連立クラスタ）
# ---------------------------------------------------------------------------
LF_SOLVE_SYSTEM_ELIM_V1 = (
    "次の連立方程式を加減法で解け。\n{{ given.equation_a }} , {{ given.equation_b }}"
)

# g2_l10.calculation Lv1: 2元1次方程式の左辺に (x,y) を代入して左辺の値を求める（P1/C2）
LF_SUBSTITUTE_INTO_EQUATION_V1 = (
    "2元1次方程式 {{ given.equation }} の左辺に {{ given.candidate }} を代入して、"
    "左辺の値を求めよ。"
)

# g2_l13.calculation Lv1/Lv2: 連立方程式を代入法で解く（横展開#12）
LF_SOLVE_SYSTEM_SUBST_V1 = (
    "次の連立方程式を代入法で解け。\n{{ given.equation_a }} , {{ given.equation_b }}"
)

# g2_l14.calculation Lv2/Lv3: いろいろな連立方程式（かっこ／分数の前処理・横展開#14）
LF_SOLVE_SYSTEM_VARIOUS_V1 = (
    "次の連立方程式を解け。\n{{ given.equation_a }} , {{ given.equation_b }}"
)

# g2_l15.calculation Lv2: A=B=C 形の等式を連立に組み替えて解く（横展開#15）
LF_SOLVE_SYSTEM_ABC_V1 = "次の等式を満たす x, y を求めよ。\n{{ given.equation }}"

# g2_l21.knowledge Lv1: グラフの向き（傾きの符号）を単一選択で問う（横展開#16・knowledge 初）
# 選択肢はテンプレ本文に固定（答えの向き語は ChoiceAnswer 側・本文にはどちらも並記＝漏洩でない）。
LF_KNOWLEDGE_SLOPE_DIRECTION_V1 = (
    "1次関数 {{ given.statement }} のグラフは、右上がりと右下がりのどちらですか。"
)

# g2_l21.knowledge Lv2: 傾き・切片の符号からグラフのようすを判別・適用（P1/C5）
# 4分類の選択肢は本文に固定並記（テキスト選択肢答えは G-Q5t 素通り・§7.7）。
LF_KNOWLEDGE_CLASSIFY_LINE_SIGNS_V1 = (
    "1次関数 {{ given.statement }} のグラフのようすとして正しいものを、次のア〜エから選べ。"
    "ア 右上がりで、y 軸の正の部分で y 軸と交わる "
    "イ 右上がりで、y 軸の負の部分で y 軸と交わる "
    "ウ 右下がりで、y 軸の正の部分で y 軸と交わる "
    "エ 右下がりで、y 軸の負の部分で y 軸と交わる"
)

# g2_l23.knowledge Lv1: 変域の端点がグラフにふくまれるか（横展開#17・knowledge 償却実証）
LF_KNOWLEDGE_RANGE_ENDPOINT_V1 = (
    "{{ given.statement }}、変域の端の点はグラフにふくまれますか、ふくまれませんか。"
)

# g2_l10.knowledge Lv2: 連立方程式の組(x,y)が解かを判定（横展開#18・knowledge 横展開）
LF_KNOWLEDGE_VERIFY_SOLUTION_V1 = (
    "連立方程式 {{ given.statement }} について、{{ given.term_context }} の組は"
    "この連立方程式の解といえますか、いえませんか。"
)

# g2_l19.knowledge Lv2: 与式が1次関数か判別（横展開#19・knowledge verify型）
# 選択肢（1次関数である/でない）は ChoiceAnswer 側。式は given.statement（given 由来）。
LF_KNOWLEDGE_CLASSIFY_LINEAR_V1 = (
    "式 {{ given.statement }} は、y が x の1次関数であるといえますか、いえませんか。"
)

# g2_l21.calculation Lv1: 傾き=変化の割合の数値計算（横展開#20・P1/C5）
LF_LINEAR_SLOPE_AS_RATE_V1 = (
    "1次関数 {{ given.expression }} について、x が1増加したときの y の増加量を求めよ。"
)

# g2_l19.knowledge Lv1: 係数・定数項が傾き/切片のどちらか（横展開#21・P1/C5）
# 選択肢（傾き/切片）はテンプレ本文に固定並記（テキスト選択肢答えは G-Q5t 素通り）。
LF_KNOWLEDGE_COEFFICIENT_ROLE_V1 = (
    "1次関数 {{ given.statement }} について、{{ given.term_context }}が表すものは、"
    "傾きと切片のどちらですか。"
)

# g2_l26.knowledge Lv1: 2元1次方程式の解の集合は直線（横展開#23・P1/C5）
LF_KNOWLEDGE_EQUATION_SOLUTION_SET_V1 = (
    "2元1次方程式 {{ given.statement }} の解を座標とする点をすべて集めると、どのような図形に"
    "なりますか。次のア〜ウから選べ。ア 直線 イ 放物線 ウ 1つの点"
)

# g2_l27.knowledge Lv1: 連立の解は2直線の交点（横展開#24・P1/C5）
LF_KNOWLEDGE_SYSTEM_INTERSECTION_V1 = (
    "連立方程式 {{ given.statement }} の解は、2つの式が表す2つの直線のどこにあたりますか。"
    "次のア〜ウから選べ。ア 2つの直線の交点 イ 2つの直線の傾き ウ 2つの直線とy軸との交点"
)

# g2_l20.knowledge Lv1: 変化の割合はつねに一定で傾きに等しい（横展開#22・P1/C5）
# 選択肢は本文に固定並記（テキスト選択肢答えは G-Q5t 素通り・全選択肢の提示は漏洩でない §7.7）。
# 表示順は T1 preview 用。実際の出題では ChoiceAnswer の correct/distractors をホストがシャッフルする。
LF_KNOWLEDGE_RATE_CONSTANT_V1 = (
    "1次関数 {{ given.statement }} の変化の割合について、正しく説明しているものを"
    "次のア〜ウから選べ。"
    "ア 変化の割合はつねに一定で、傾きに等しい "
    "イ 変化の割合は x の値によって変わる "
    "ウ 変化の割合は切片に等しい"
)


# ---------------------------------------------------------------------------
# g2_l20.find_value Lv1: 2点から変化の割合を求める（横展開の第1セル）
# ---------------------------------------------------------------------------
LF_RATE_OF_CHANGE_V1 = (
    "2点 {{ given.point_a }} と {{ given.point_b }} を通る1次関数について、変化の割合を求めよ。"
)

# g2_l29.find_value Lv3: 面積の式から目標面積となる時刻を逆算する（P1/C5）
# 面積の式は given.expression、区間は given.x_domain、目標は given.condition（すべて whitelist）。
LF_SOLVE_TIME_FROM_AREA_V1 = (
    "動点が辺上を動くとき、三角形の面積 y cm² と時間 x 秒の関係が {{ given.expression }} で表され、"
    "この区間は {{ given.x_domain }} である。この区間で{{ given.condition }}時刻 x を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l27.find_value Lv2/Lv3: 2直線の交点の座標（横展開の第2セル・両レベル共用）
# ---------------------------------------------------------------------------
LF_INTERSECTION_V1 = (
    # 「2直線」ではなく「2つの直線」: 助数詞「つ」は G-Q5t 漏洩スキャンの除外対象で、
    # 先頭の "2" が答え座標の数値と衝突する偽陽性を避ける（graph_table と同種）。
    "2つの直線 {{ given.line_a }} と {{ given.line_b }} の交点の座標を求めよ。"
)

# g2_l30.find_value Lv2: ダイヤグラムの2直線を連立し交点=出会いの時刻・道のりを求める（P1/C5）
# 式は既知として与え、連立して交点を計算する（intersection recipe 再利用）。
LF_INTERSECTION_DIAGRAM_V1 = (
    "AさんとBさんが動くようすを、出発してからの時間 x とP地点からの道のり y の関係で表すと、"
    "Aさんは {{ given.line_a }}、Bさんは {{ given.line_b }} である。"
    "2人が同じ地点にいる（2つの直線が交わる）ときの時間 x と道のり y を求めよ。"
)

# ---------------------------------------------------------------------------
# g2_l23.find_value: 変域とグラフの端点（横展開#3）
# Lv2=順方向（関数+x変域→y変域）／Lv3=逆算（x変域+y変域+符号→式）
# ---------------------------------------------------------------------------
LF_Y_RANGE_V1 = (
    "1次関数 {{ given.expression }} について、"
    "x の変域が {{ given.x_domain }} のときの y の変域を求めよ。"
)
LF_EXPR_FROM_RANGE_V1 = (
    "1次関数 y = ax + b について、x の変域が {{ given.x_domain }} のとき "
    "y の変域が {{ given.y_range }} であった。{{ given.condition }}、この1次関数の式を求めよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_expr_two_points_v1", LF_EXPR_TWO_POINTS_V1)
    REGISTRY.register_template("lf_expr_slope_point_v1", LF_EXPR_SLOPE_POINT_V1)
    REGISTRY.register_template("lf_expr_parallel_v1", LF_EXPR_PARALLEL_V1)
    REGISTRY.register_template("graph_read_two_points_v1", GRAPH_READ_TWO_POINTS_V1)
    REGISTRY.register_template("graph_read_slope_intercept_v1", GRAPH_READ_SLOPE_INTERCEPT_V1)
    REGISTRY.register_template("lf_solve_for_y_v1", LF_SOLVE_FOR_Y_V1)
    REGISTRY.register_template("lf_evaluate_at_x_v1", LF_EVALUATE_AT_X_V1)
    REGISTRY.register_template("lf_point_on_line_v1", LF_POINT_ON_LINE_V1)
    REGISTRY.register_template("lf_draw_graph_v1", LF_DRAW_GRAPH_V1)
    REGISTRY.register_template("lf_draw_graph_fraction_v1", LF_DRAW_GRAPH_FRACTION_V1)
    REGISTRY.register_template("lf_draw_from_equation_v1", LF_DRAW_FROM_EQUATION_V1)
    REGISTRY.register_template("lf_read_intersection_v1", LF_READ_INTERSECTION_V1)
    REGISTRY.register_template(
        "lf_read_diagram_intersection_v1", LF_READ_DIAGRAM_INTERSECTION_V1
    )
    REGISTRY.register_template("lf_draw_special_lines_v1", LF_DRAW_SPECIAL_LINES_V1)
    REGISTRY.register_template("lf_draw_from_table_v1", LF_DRAW_FROM_TABLE_V1)
    REGISTRY.register_template("lf_draw_segment_v1", LF_DRAW_SEGMENT_V1)
    REGISTRY.register_template("lf_solve_system_elim_v1", LF_SOLVE_SYSTEM_ELIM_V1)
    REGISTRY.register_template(
        "lf_substitute_into_equation_v1", LF_SUBSTITUTE_INTO_EQUATION_V1
    )
    REGISTRY.register_template("lf_solve_system_subst_v1", LF_SOLVE_SYSTEM_SUBST_V1)
    REGISTRY.register_template("lf_solve_system_various_v1", LF_SOLVE_SYSTEM_VARIOUS_V1)
    REGISTRY.register_template("lf_solve_system_abc_v1", LF_SOLVE_SYSTEM_ABC_V1)
    REGISTRY.register_template(
        "lf_knowledge_slope_direction_v1", LF_KNOWLEDGE_SLOPE_DIRECTION_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_classify_line_signs_v1", LF_KNOWLEDGE_CLASSIFY_LINE_SIGNS_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_range_endpoint_v1", LF_KNOWLEDGE_RANGE_ENDPOINT_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_verify_solution_v1", LF_KNOWLEDGE_VERIFY_SOLUTION_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_classify_linear_v1", LF_KNOWLEDGE_CLASSIFY_LINEAR_V1
    )
    REGISTRY.register_template(
        "lf_linear_slope_as_rate_v1", LF_LINEAR_SLOPE_AS_RATE_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_coefficient_role_v1", LF_KNOWLEDGE_COEFFICIENT_ROLE_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_rate_constant_v1", LF_KNOWLEDGE_RATE_CONSTANT_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_equation_solution_set_v1", LF_KNOWLEDGE_EQUATION_SOLUTION_SET_V1
    )
    REGISTRY.register_template(
        "lf_knowledge_system_intersection_v1", LF_KNOWLEDGE_SYSTEM_INTERSECTION_V1
    )
    REGISTRY.register_template("lf_rate_of_change_v1", LF_RATE_OF_CHANGE_V1)
    REGISTRY.register_template("lf_solve_time_from_area_v1", LF_SOLVE_TIME_FROM_AREA_V1)
    REGISTRY.register_template("lf_intersection_v1", LF_INTERSECTION_V1)
    REGISTRY.register_template("lf_intersection_diagram_v1", LF_INTERSECTION_DIAGRAM_V1)
    REGISTRY.register_template("lf_y_range_v1", LF_Y_RANGE_V1)
    REGISTRY.register_template("lf_expr_from_range_v1", LF_EXPR_FROM_RANGE_V1)


_register_all()


__all__ = [
    "LF_EXPR_TWO_POINTS_V1",
    "LF_EXPR_SLOPE_POINT_V1",
    "LF_EXPR_PARALLEL_V1",
    "GRAPH_READ_TWO_POINTS_V1",
    "GRAPH_READ_SLOPE_INTERCEPT_V1",
    "LF_SOLVE_FOR_Y_V1",
    "LF_EVALUATE_AT_X_V1",
    "LF_POINT_ON_LINE_V1",
    "LF_DRAW_GRAPH_V1",
    "LF_DRAW_GRAPH_FRACTION_V1",
    "LF_DRAW_FROM_EQUATION_V1",
    "LF_READ_INTERSECTION_V1",
    "LF_READ_DIAGRAM_INTERSECTION_V1",
    "LF_DRAW_SPECIAL_LINES_V1",
    "LF_DRAW_FROM_TABLE_V1",
    "LF_DRAW_SEGMENT_V1",
    "LF_SOLVE_SYSTEM_ELIM_V1",
    "LF_SUBSTITUTE_INTO_EQUATION_V1",
    "LF_SOLVE_SYSTEM_SUBST_V1",
    "LF_SOLVE_SYSTEM_VARIOUS_V1",
    "LF_SOLVE_SYSTEM_ABC_V1",
    "LF_KNOWLEDGE_SLOPE_DIRECTION_V1",
    "LF_KNOWLEDGE_CLASSIFY_LINE_SIGNS_V1",
    "LF_KNOWLEDGE_RANGE_ENDPOINT_V1",
    "LF_KNOWLEDGE_VERIFY_SOLUTION_V1",
    "LF_KNOWLEDGE_CLASSIFY_LINEAR_V1",
    "LF_LINEAR_SLOPE_AS_RATE_V1",
    "LF_KNOWLEDGE_COEFFICIENT_ROLE_V1",
    "LF_KNOWLEDGE_RATE_CONSTANT_V1",
    "LF_KNOWLEDGE_EQUATION_SOLUTION_SET_V1",
    "LF_KNOWLEDGE_SYSTEM_INTERSECTION_V1",
    "LF_RATE_OF_CHANGE_V1",
    "LF_SOLVE_TIME_FROM_AREA_V1",
    "LF_INTERSECTION_V1",
    "LF_INTERSECTION_DIAGRAM_V1",
    "LF_Y_RANGE_V1",
    "LF_EXPR_FROM_RANGE_V1",
]
