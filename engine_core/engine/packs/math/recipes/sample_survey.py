"""標本調査まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C11（データ・統計）クラスタのうち g3_l57〜g3_l60 の非 visual セル群に対応する recipe を
集約する。乱数は `engine.core.rng.draw`/`draw_many` 以外で解釈しない。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# g3_l59.calculation Lv1: 標本比率・比例式による推定値
# ---------------------------------------------------------------------------
_SAMPLE_RATIO_ESTIMATE_CONCEPTS = ["sample_survey.ratio_estimate"]
_SAMPLE_RATIO_SCENARIOS = [
    ("標本の大きさが{s}で、そのうち当たりが{c}個であった。母集団{n}個の中に含まれる当たりのおよその個数を、比例式を使って求めよ", "個"),
    ("無作為に抽出した{s}個の製品のうち、不良品が{c}個あった。製品{n}個の中に含まれる不良品のおよその個数を、比例式を使って求めよ", "個"),
    ("池から無作為に{s}匹の魚をすくったところ、体長10cm以上の魚が{c}匹いた。この池にいる魚{n}匹のうち体長10cm以上の魚のおよその数を、比例式を使って求めよ", "匹"),
]


@register_recipe("math.sample_ratio_estimate", provides_concepts=_SAMPLE_RATIO_ESTIMATE_CONCEPTS)
def sample_ratio_estimate_recipe(ctx: CellContext, rng: Rng) -> MR:
    """標本比率から母集団に含まれるおよその個数を推定する（g3_l59.calculation Lv1・answer-first）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_range": [0, len(_SAMPLE_RATIO_SCENARIOS) - 1]}, rng))
    template, _unit = _SAMPLE_RATIO_SCENARIOS[idx]
    s = int(draw(p["sample_size_domain"], rng))
    c = int(draw({"int_range": [1, s - 1]}, rng))
    k = int(draw(p["multiplier_domain"], rng))
    n = s * k

    solver = REGISTRY.solver("math.sample_ratio_estimate")
    sol = cast(Solution, solver(s, c, n))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = template.format(s=s, c=c, n=n)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"sample_size": s, "sample_count": c, "population_size": n, "scenario_index": idx},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.sample_ratio_estimate"),
    )


# ---------------------------------------------------------------------------
# g3_l60.calculation Lv2: 比例式で母集団の大きさ x を解く
# ---------------------------------------------------------------------------
_SAMPLE_RATIO_SOLVE_POPULATION_CONCEPTS = ["sample_survey.solve_population_size"]
_SOLVE_POPULATION_SCENARIOS = [
    "無作為に取り出した標本の大きさが{s}で、そのうち目的のものが{c}個であった。"
    "母集団の大きさを x として、母集団に含まれる目的のもののおよその個数が{e}であることから "
    "x を、比例式を使って求めよ",
    # **標識再捕獲は手順が決まっている。** 前はこう書いていた——
    #   「{s}匹に印をつけてもどした。数日後に調べたところ、印のついたコイが{c}匹、
    #     印のついたコイをふくむ湖のコイのおよその総数が{e}匹と推定されている」
    # 総数が推定済みだと書いてあるのに総数を求めさせていて、しかも後日何匹捕まえたかが
    # 書かれていない。求める式（x = s·e/c）に対応する手順に書き直す。
    "湖にいるコイの数を調べるため、{s}匹のコイを捕まえて印をつけて湖にもどした。数日後に"
    "同じ湖で{e}匹のコイを捕まえたところ、そのうち印のついたコイは{c}匹であった。"
    "湖にいるコイの総数を x として、この関係を比例式で表し x を求めよ",
]


@register_recipe(
    "math.sample_ratio_solve_population", provides_concepts=_SAMPLE_RATIO_SOLVE_POPULATION_CONCEPTS
)
def sample_ratio_solve_population_recipe(ctx: CellContext, rng: Rng) -> MR:
    """標本比率と推定個数から母集団の大きさ x を比例式で解く（g3_l60.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_range": [0, len(_SOLVE_POPULATION_SCENARIOS) - 1]}, rng))
    template = _SOLVE_POPULATION_SCENARIOS[idx]
    if idx == 1:
        # 標識再捕獲の場面は数の大きさが決まっている（印をつけるのは数十匹、
        # 後日捕まえるのも数十匹、そのうち印つきは数匹）。標本調査の一般の場面と
        # 同じ定義域を使うと「後日 10908 匹捕まえた」になる。
        s = int(draw({"int_set": [40, 50, 60, 80, 100, 120]}, rng))
        c = int(draw({"int_set": [3, 4, 5, 6, 8, 10]}, rng))
        k = int(draw({"int_set": [8, 10, 12, 15, 20]}, rng))
    else:
        s = int(draw(p["sample_size_domain"], rng))
        c = int(draw({"int_range": [1, s - 1]}, rng))
        k = int(draw(p["multiplier_domain"], rng))
    e = c * k

    solver = REGISTRY.solver("math.sample_ratio_solve_population")
    sol = cast(Solution, solver(s, c, e))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = template.format(s=s, c=c, e=e)

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"sample_size": s, "sample_count": c, "known_estimate": e, "scenario_index": idx},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.sample_ratio_solve_population"),
    )


# ---------------------------------------------------------------------------
# g3_l57.knowledge Lv2: 全数調査/標本調査のどちらが適切か判別する
# ---------------------------------------------------------------------------
_JUDGE_APPROPRIATE_SURVEY_METHOD_CONCEPTS = ["survey_method.judge_appropriate"]
_SURVEY_METHOD_SCENARIOS: list[tuple[str, bool]] = [
    ("ある工場で作られる{n}個の缶詰の品質を調べたい。すべての缶詰を開けて調べることはできない", True),
    ("{n}本の電池の寿命を検査したい。検査すると電池が使えなくなってしまう", True),
    # 「{n}世帯の中から一部を選んで」と書くと、本文が答えを言ってしまう
    # （しかも視聴率の母集団は全国の世帯であって 240 世帯ではない）。
    ("ある地域の{n}世帯を対象に、テレビ番組の視聴率を調べたい", True),
    ("学校で{n}人の生徒全員に身体測定を行いたい", False),
    ("国勢調査として、{n}世帯すべての世帯構成を調べたい", False),
    ("あるクラス{n}人全員の今月の出席日数を、出席簿を見て調べたい", False),
]


@register_recipe(
    "math.judge_appropriate_survey_method", provides_concepts=_JUDGE_APPROPRIATE_SURVEY_METHOD_CONCEPTS
)
def judge_appropriate_survey_method_recipe(ctx: CellContext, rng: Rng) -> MR:
    """場面から全数調査/標本調査のどちらが適切かを判別する（g3_l57.knowledge Lv2・answer-first）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_range": [0, len(_SURVEY_METHOD_SCENARIOS) - 1]}, rng))
    template, needs_sample = _SURVEY_METHOD_SCENARIOS[idx]
    n = int(draw(p["n_domain"], rng))
    scenario = template.format(n=n)

    solver = REGISTRY.solver("math.judge_appropriate_survey_method")
    sol = cast(Solution, solver(needs_sample))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = f"{scenario}。この調査は全数調査と標本調査のどちらで行うのが適切か、理由とともに答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"scenario_index": idx, "n": n, "needs_sample": str(needs_sample)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_appropriate_survey_method"),
    )


# ---------------------------------------------------------------------------
# g3_l58.knowledge Lv2: 抽出方法に偏りがあるかを判別する
# ---------------------------------------------------------------------------
_JUDGE_SAMPLING_BIAS_CONCEPTS = ["sampling.judge_bias"]
_SAMPLING_BIAS_SCENARIOS: list[tuple[str, bool]] = [
    ("{n}人の全校生徒の意見を調べるのに、野球部に所属する生徒だけにアンケートをとった", True),
    ("ある市の住民{n}人の意見を調べるのに、平日の昼間に商店街で聞き取り調査をした", True),
    ("{n}人の生徒の意見を調べるのに、図書館を利用している生徒だけに聞いた", True),
    ("{n}人の住民の意見を調べるのに、乱数表を使って住民全体から無作為に選んで聞いた", False),
    ("{n}個の製品から、抽選機を使って無作為に製品を選んで検査した", False),
    ("{n}人の生徒の中から、出席番号にもとづいて作った乱数で無作為に選んで調査した", False),
]


@register_recipe("math.judge_sampling_bias", provides_concepts=_JUDGE_SAMPLING_BIAS_CONCEPTS)
def judge_sampling_bias_recipe(ctx: CellContext, rng: Rng) -> MR:
    """抽出方法に偏りが生じるかどうかを判別する（g3_l58.knowledge Lv2・answer-first）。"""
    p = ctx.spec_level.params
    idx = int(draw({"int_range": [0, len(_SAMPLING_BIAS_SCENARIOS) - 1]}, rng))
    template, is_biased = _SAMPLING_BIAS_SCENARIOS[idx]
    n = int(draw(p["n_domain"], rng))
    scenario = template.format(n=n)

    solver = REGISTRY.solver("math.judge_sampling_bias")
    sol = cast(Solution, solver(is_biased))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = f"{scenario}。この標本の選び方は、母集団の様子を調べる方法として適切か、理由とともに答えよ"

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"scenario_index": idx, "n": n, "is_biased": str(is_biased)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_sampling_bias"),
    )


# ---------------------------------------------------------------------------
# g3_l59.knowledge Lv1: 標本比率≒母比率とみなせる理由の説明
# ---------------------------------------------------------------------------
_EXPLAIN_SAMPLE_RATIO_RATIONALE_CONCEPTS = ["sample_survey.ratio_rationale"]


@register_recipe(
    "math.explain_sample_ratio_rationale", provides_concepts=_EXPLAIN_SAMPLE_RATIO_RATIONALE_CONCEPTS
)
def explain_sample_ratio_rationale_recipe(ctx: CellContext, rng: Rng) -> MR:
    """標本比率を母比率のおよその値とみなしてよい理由を説明する（g3_l59.knowledge Lv1・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(p["number_domain"], rng))
    # 何を調べるかも振る（標本比率の説明は、調べる内容まで書くのが実物）。
    what = str(draw(["不良品の割合", "賛成する人の割合", "当たりの割合",
                     "ある特徴をもつものの割合", "合格するものの割合"], rng))
    # 標本の大きさを教材の粒度に絞った分、調べる対象で広さを戻す
    # （実物の説明も、必ず何を調べる標本かを添えている）。
    target = str(draw(
        ["ある工場の製品", "ある地域の世帯", "ある学校の生徒", "ある池の魚",
         "ある農園のみかん", "ある店の来客", "ある市の住民", "ある倉庫の在庫",
         "ある会社の社員", "ある図書館の蔵書", "ある牧場の牛", "ある森の木",
         "ある工場の部品", "ある病院の患者", "あるイベントの参加者", "ある団体の会員"], rng))
    statement = (
        f"{target}の{what}を調べるため、大きさ{n}の標本を無作為に抽出した。"
        "標本の中の割合(標本比率)を母集団全体の割合(母比率)のおよその値と"
        "みなしてよいのはなぜか、その考え方を説明せよ"
    )

    solver = REGISTRY.solver("math.explain_sample_ratio_rationale")
    sol = cast(Solution, solver(None))
    assert isinstance(sol.answer, ChoiceAnswer)

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
            # **surface をそのまま params に載せる。** 載せないと dup_key から
            # 見えず、題材の軸を足しても重複率が下がらない（今日2度踏んだ）。
        params={"n": n, "statement": statement},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.explain_sample_ratio_rationale"),
    )
