"""標本調査まわりの独立再計算ソルバ群（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（標本の大きさ・個数・母集団の大きさ・bool 判定）から
答えと steps を導く（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。
乱数は引かない。

C11（データ・統計）クラスタのうち g3_l57〜g3_l60（標本調査）の非 visual セルを扱う:
  - `math.sample_ratio_estimate`: g3_l59.calculation Lv1（標本比率→母集団の個数の推定）
  - `math.sample_ratio_solve_population`: g3_l60.calculation Lv2（比例式で母集団の大きさを解く）
  - `math.judge_appropriate_survey_method`: g3_l57.knowledge Lv2（全数調査/標本調査の判別）
  - `math.judge_sampling_bias`: g3_l58.knowledge Lv2（偏りの有無の判別）
  - `math.explain_sample_ratio_rationale`: g3_l59.knowledge Lv1（標本比率≒母比率の考え方の説明）
（g3_l57/l58 knowledge Lv1 は既存 `math.term_recall` ハブに domain 追加で対応。）

narration には数字を書かない（"0" は "=0" の whitelist のみ許可）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


# ---------------------------------------------------------------------------
# g3_l59.calculation Lv1: 標本比率・比例式による推定値
# ---------------------------------------------------------------------------
@register_solver("math.sample_ratio_estimate")
def sample_ratio_estimate(sample_size: object, sample_count: object, population_size: object) -> Solution:
    """標本の比率から母集団に含まれるおよその個数を推定する（g3_l59.calculation Lv1）。

    標本の大きさ・標本内の該当個数・母集団の大きさだけから計算する（double-solve）。
    答えは単一値の SymbolicAnswer。
    """
    s = sympy.Integer(int(str(sample_size)))
    c = sympy.Integer(int(str(sample_count)))
    n = sympy.Integer(int(str(population_size)))
    estimate = n * c / s
    disp = sympy.sstr(estimate)
    srepr = sympy.srepr(estimate)
    steps = [
        Step(
            op="form_ratio_equation",
            args=[],
            result_srepr="",
            result_display=f"{sympy.sstr(c)} : {sympy.sstr(s)} = x : {sympy.sstr(n)}",
            narration="標本での該当する個数の割合が、母集団全体でもおよそ等しいとみて比例式をつくる。",
        ),
        Step(
            op="solve_for_estimate",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="比例式を解き、母集団に含まれるおよその個数を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l60.calculation Lv2: 比例式で母集団の大きさ x を解く
# ---------------------------------------------------------------------------
@register_solver("math.sample_ratio_solve_population")
def sample_ratio_solve_population(sample_size: object, sample_count: object, known_estimate: object) -> Solution:
    """標本比率と推定個数から母集団の大きさ x を比例式で解く（g3_l60.calculation Lv2）。

    標本の大きさ・標本内の該当個数・母集団に含まれる該当個数の推定値だけから計算する
    （double-solve）。答えは単一値の SymbolicAnswer。
    """
    s = sympy.Integer(int(str(sample_size)))
    c = sympy.Integer(int(str(sample_count)))
    e = sympy.Integer(int(str(known_estimate)))
    x = e * s / c
    disp = sympy.sstr(x)
    srepr = sympy.srepr(x)
    steps = [
        Step(
            op="form_ratio_equation_for_x",
            args=[],
            result_srepr="",
            result_display=f"{sympy.sstr(c)} : {sympy.sstr(s)} = {sympy.sstr(e)} : x",
            narration="標本での該当する個数の割合が、母集団全体でもおよそ等しいとみて、"
            "母集団の大きさ x を含む比例式をつくる。",
        ),
        Step(
            op="solve_for_x",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="比例式を解き、母集団の大きさ x を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l57.knowledge Lv2: 全数調査/標本調査のどちらが適切か判別する
# ---------------------------------------------------------------------------
@register_solver("math.judge_appropriate_survey_method")
def judge_appropriate_survey_method(needs_sample: object) -> Solution:
    """場面から全数調査/標本調査のどちらが適切かを判別する（g3_l57.knowledge Lv2）。

    needs_sample（bool 相当）だけから判定する（具体的な場面文は recipe が構成する
    surface であり double-solve）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    truthy = str(needs_sample).lower() in ("true", "1")
    correct = "標本調査で行うのが適切" if truthy else "全数調査で行うのが適切"
    other = "全数調査で行うのが適切" if truthy else "標本調査で行うのが適切"
    steps = [
        Step(
            op="check_feasibility",
            args=[],
            result_srepr=("needs_sample" if truthy else "needs_census"),
            result_display=("全部を調べるのは難しい" if truthy else "全部を調べられる"),
            narration="対象すべてを調べることが、手間や対象の性質から現実的に可能かどうかを調べる。",
        ),
        Step(
            op="judge_appropriate_survey_method",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="全部を調べるのが難しい・不要な場合は標本調査、そうでない場合は全数調査が適切と判断する。",
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct, distractors=[other], fact_id="survey_method.judge_appropriate",
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l58.knowledge Lv2: 抽出方法に偏りがあるかを判別する
# ---------------------------------------------------------------------------
@register_solver("math.judge_sampling_bias")
def judge_sampling_bias(is_biased: object) -> Solution:
    """抽出方法に偏りが生じるかどうかを判別する（g3_l58.knowledge Lv2）。

    is_biased（bool 相当）だけから判定する（具体的な場面文は recipe が構成する surface
    であり double-solve）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    truthy = str(is_biased).lower() in ("true", "1")
    correct = "偏りが生じやすく、適切とはいえない" if truthy else "偏りが生じにくく、適切といえる"
    other = "偏りが生じにくく、適切といえる" if truthy else "偏りが生じやすく、適切とはいえない"
    steps = [
        Step(
            op="check_random_coverage",
            args=[],
            result_srepr=("biased" if truthy else "unbiased"),
            result_display=("同じ機会にならない" if truthy else "同じ機会になる"),
            narration="母集団に含まれるすべての対象が、同じ機会で選ばれる方法になっているかを調べる。",
        ),
        Step(
            op="judge_sampling_bias",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="一部の対象だけが選ばれやすい方法になっていれば偏りが生じ、適切とはいえないと判断する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="sampling.judge_bias")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g3_l59.knowledge Lv1: 標本比率≒母比率とみなせる理由の説明
# ---------------------------------------------------------------------------
@register_solver("math.explain_sample_ratio_rationale")
def explain_sample_ratio_rationale(dummy: object) -> Solution:
    """標本比率を母比率のおよその値とみなしてよい理由を説明する（g3_l59.knowledge Lv1）。

    説明対象は固定（無作為抽出の性質にもとづく恒真の説明）なので引数は使わず一意に定まる
    （double-solve・恒真）。答えは ChoiceAnswer。narration に数字は書かない。
    """
    correct = "無作為に抽出すれば、標本は母集団の縮図とみなせるから"
    distractors = [
        "標本の大きさを大きくすれば、必ず母比率と完全に一致するから",
        "調査する人が経験にもとづいて選べば、母集団の様子を最も正しく表せるから",
    ]
    steps = [
        Step(
            op="explain_sample_ratio_rationale",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="無作為に抽出された標本は、母集団のようすを偏りなく反映した縮図とみなせることを確認する。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=distractors, fact_id="sample_survey.ratio_rationale")
    return Solution(answer=answer, steps=steps)
