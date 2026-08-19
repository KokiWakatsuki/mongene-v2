"""1次関数の利用（form=word_problem・C14 の「1次関数」クラスタ）。

`word_problem_linear.py`（1元1次方程式の利用）・`word_problem_system.py`（連立の利用）と
同じ骨格を、1次関数の利用（ばね・水そう・出会い）に横展開する module。数学そのものは
既存 solver に委ねる＝**新 solver ゼロ**:

  - `math.linear_expr_from_two_points`（g2_l25「2点から式を決定する」）
  - `math.linear_expr_from_slope_point`（g2_l24「傾きと1点から式を決定する」）
  - `math.evaluate_linear_at_x`（g2_l19 の代入計算）
  - `math.solve_linear_equation`（g1 一次方程式の解法。折れ線の第2区間で
    「y=target になる x」を解くのに再利用する）
  - `math.intersection_of_two_lines`（g2_l27/l30 の「2直線の交点」）

## 3つの scenario_kind（level_sep は「式がいくつに分かれるか・何を文字に置くか」）

  - `spring_two_point`（g2_l28 Lv2）: 2点から式を決め、代入して値を求める（1直線・
    誘導 (1)立式→(2)値 の2小問）。
  - `tank_piecewise`（g2_l28 Lv3）: 区間で式が変わる（折れ線）。誘導
    (1)第1区間の式→(2)第2区間の式→(3)目標の量になる時刻、の3小問。
  - `meeting_intersection`（g2_l30 Lv3）: 2直線の交点。誘導 (1)Aの式→(2)出会う時刻、
    の2小問。

  units.generated.yaml の g2_l30.word_problem Lv3 の market example には「2人の
  進むようすを1つのグラフにかけ」という中間小問があるが、本セルはこれを**落とす**。
  word_problem frame の asked_vocab は {formulation, value} のみで "draw" 系の語彙を
  持たない（engine/packs/math/frames.py の WORD_PROBLEM_FRAME 参照）ため、frame を
  変更しない限り GraphAnswer の小問を無検証にせず追加する経路が無い。frame/core の
  変更は本タスクのスコープ外なので、(1)Aの式→(2)出会う時刻 の2小問に絞る（詳細は
  family yaml の source_desc に明記。g3_l31.graph_table が表小問を落とした前例と同型）。

## params が持つのは「場面文に出ている数値」だけ

各 kind の `numbers` は given（scenario/quantities）または context_slots の
ask_formulation/ask_value に出ている数値そのもので、答えは入れない。checker は同じ
`solve_<kind>` 関数を通して立式し直し・解き直す。
"""
from __future__ import annotations

import math
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe, register_template
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.recipes.scene_vocab import split_pair

RECIPE_NAME = "math.word_problem_linear_function"

_LINEAR_FUNCTION_CONCEPTS = [
    "linear_function.word_problem_two_point_eval",
    "linear_function.word_problem_piecewise_tank",
    "linear_function.word_problem_meeting_intersection",
    # scenario_kind を足したら必ずここにも足す（recipe の provides_concepts に無いと
    # lint R6「レベルの概念集合が recipe 宣言の部分集合でない」で落ちる。
    # check_cell は通るので pytest まで回さないと気づかない）。
    "linear_function.word_problem_tank_race",
    "linear_function.word_problem_second_meeting",
]

_X = sympy.Symbol("x")
_Y = sympy.Symbol("y")


# ---------------------------------------------------------------------------
# テンプレート。(1)(2) の2小問は既存 wp_linear_guided_v1
# （engine/packs/math/templates/word_problem.py）をそのまま再利用する（自分の scene が
# 使うのは (1)(2)(3) の3小問の新形だけ）。既存テンプレファイル／登録済み __init__ 群は
# 触らず、ここで直接 register_template する（新規性は self-contained な新 pack ファイル
# に閉じる）。
# ---------------------------------------------------------------------------
WP_LINEAR_GUIDED3_V1 = (
    "{{ given.scenario }}\n"
    "{{ given.quantities }}\n"
    "(1) {{ context_slots.ask_formulation_1 }}\n"
    "(2) {{ context_slots.ask_formulation_2 }}\n"
    "(3) {{ context_slots.ask_value }}"
)
register_template("wp_linear_guided3_v1", WP_LINEAR_GUIDED3_V1)


def _format_linear_lhs(a: int, b: int) -> str:
    """a*x + b の方程式左辺の文字列（例 "3*x + 4", "5*x - 20", "3*x"）。"""
    if b == 0:
        return f"{a}*x"
    if b > 0:
        return f"{a}*x + {b}"
    return f"{a}*x - {-b}"


# ---------------------------------------------------------------------------
# spring_two_point（g2_l28 Lv2）: 2点から式を決め、代入して値を求める。
# ---------------------------------------------------------------------------
def solve_spring(x1: int, y1: int, x2: int, y2: int, x0: int) -> list[Solution]:
    """(1)2点から y=ax+b を決定→(2)x=x0 を代入して y を求める（recipe/checker 共有）。"""
    two_point = REGISTRY.solver("math.linear_expr_from_two_points")
    form_sol = cast(Solution, two_point((x1, y1), (x2, y2), "slope_then_intercept"))
    a = sympy.Rational(y2 - y1, x2 - x1)
    b = y1 - a * x1
    evaluate = REGISTRY.solver("math.evaluate_linear_at_x")
    value_sol = cast(Solution, evaluate(a, b, x0))
    return [form_sol, value_sol]


def _draw_spring(p: dict[str, Any], rng: Rng) -> tuple[dict[str, int], str]:
    """(numbers, ばねの種類) を answer-first で抽選する。

    傾き num/den は既約分数（整数を含む）。x = k・den・unit（unit はグラム単位）と
    置くことで、傾きが非整数の分数でも y=(num/den)x+b が常に整数になることを構成で
    保証する。答え y0 が given の数値（x1,y1,x2,y2,x0,b）と一致する組は弾く（有界リトライ）。
    """
    unit = int(p["weight_unit_gram"])
    k_lo, k_hi = (int(v) for v in p["weight_k_range"])
    for _ in range(500):
        den = int(draw(p["slope_den_candidates"], rng))
        num = int(draw(p["slope_num_candidates"], rng))
        if math.gcd(num, den) != 1:
            continue
        b = int(draw(p["intercept_domain"], rng))
        k1, k2 = draw_many({"int_range": [k_lo, k_hi], "distinct": ["value"]}, rng, k=2)
        k1, k2 = sorted((int(k1), int(k2)))
        k0 = int(draw({"int_range": [k_lo, k_hi]}, rng))
        if k0 in (k1, k2):
            continue
        x1, x2, x0 = k1 * den * unit, k2 * den * unit, k0 * den * unit
        y1 = num * k1 * unit + b
        y2 = num * k2 * unit + b
        y0 = num * k0 * unit + b
        if y0 in (x1, y1, x2, y2, x0, b):
            continue
        # **ばねが伸びすぎる組は外す。** 傾きと重さを無関係に引いていたので
        # 「自然長9cmのばねが60gで99cm」（11倍に伸びる）が出ていた。実物の
        # ばねの問題は 1g あたり 0.2〜1cm 伸び、全体で 60cm を超えない。
        # 1g あたりの伸びは 1/2cm まで（`y = x + 19` ＝1g で1cm 伸びるばねが
        # 出ていた。実物の教材のばねは 0.2〜0.5cm/g）。
        if 2 * num > den or max(y1, y2, y0) > int(p.get("max_length_cm", 60)):
            continue
        obj = str(draw(p["object_candidates"], rng))
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "x0": x0}, obj
    raise ValueError("spring construction: 500回試行しても条件を満たす組が見つからない")


def _build_spring_mr(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    numbers, obj = _draw_spring(p, rng)
    form_sol, value_sol = solve_spring(**numbers)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    assert isinstance(value_sol.answer, SymbolicAnswer)
    y0 = sympy.sympify(value_sol.answer.srepr)

    formulation_sq = SubQuestionMR(
        label="(1)",
        asked="formulation",
        answer=form_sol.answer,
        steps=form_sol.steps,
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )
    value_sq = SubQuestionMR(
        label="(2)",
        asked="value",
        answer=SymbolicAnswer(srepr=value_sol.answer.srepr, display=f"{y0}cm"),
        steps=value_sol.steps,
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )

    x1, y1, x2, y2, x0 = (numbers[k] for k in ("x1", "y1", "x2", "y2", "x0"))
    scenario = (
        f"ある{obj}に{x1}gのおもりをつるすと全体の長さが{y1}cmになり、"
        f"{x2}gのおもりをつるすと{y2}cmになった。"
    )
    quantities = f"{obj}の長さ y cm はおもりの重さ x g の1次関数であるとする。"

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "scenario_kind": "spring_two_point",
            "numbers": {k: str(v) for k, v in numbers.items()},
            "slots": {"object": obj},
        },
        given={"scenario": scenario, "quantities": quantities},
        context_slots={
            "object": obj,
            "ask_formulation": "y を x の式で表せ。",
            "ask_value": f"{x0}gのおもりをつるしたときの{obj}の長さを求めよ。",
        },
        sub_questions=[formulation_sq, value_sq],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
# tank_piecewise（g2_l28 Lv3）: 区間で式が変わる（折れ線）。
# ---------------------------------------------------------------------------
def solve_tank(t1: int, r1: int, r2: int, target: int) -> list[Solution]:
    """(1)第1区間の式→(2)第2区間の式→(3)y=target になる x を解く（recipe/checker 共有）。"""
    slope_point = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol1 = cast(Solution, slope_point(r1, (0, 0)))
    b2 = r1 * t1 - r2 * t1
    sol2 = cast(Solution, slope_point(r2, (t1, r1 * t1)))
    equation_str = f"{_format_linear_lhs(r2, b2)}={target}"
    solve_eq = REGISTRY.solver("math.solve_linear_equation")
    sol3 = cast(Solution, solve_eq(equation_str, "equality_multi"))
    return [sol1, sol2, sol3]


def _draw_tank(p: dict[str, Any], rng: Rng) -> tuple[dict[str, int], str, str]:
    """(numbers, 容器, 液体) を answer-first で抽選する。

    x0（目標の量になる時刻）を t1 より後（= extra 分後）に決め、target をそこから
    逆算する。これにより target は必ず第2区間に入る（構成時に保証・鉄則⑤）。
    """
    t1_lo, t1_hi = (int(v) for v in p["t1_range"])
    rate_lo, rate_hi = (int(v) for v in p["rate_range"])
    extra_lo, extra_hi = (int(v) for v in p["extra_minutes_range"])
    for _ in range(500):
        t1 = int(draw({"int_range": [t1_lo, t1_hi]}, rng))
        r1, r2 = draw_many({"int_range": [rate_lo, rate_hi], "distinct": ["value"]}, rng, k=2)
        r1, r2 = int(r1), int(r2)
        extra = int(draw({"int_range": [extra_lo, extra_hi]}, rng))
        x0 = t1 + extra
        target = r2 * extra + r1 * t1
        if target in (t1, r1, r2, x0):
            continue
        container, liquid = split_pair(str(draw(p["container_liquid_candidates"], rng)))
        return {"t1": t1, "r1": r1, "r2": r2, "target": target}, container, liquid
    raise ValueError("tank construction: 500回試行しても条件を満たす組が見つからない")


def _build_tank_mr(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    numbers, container, liquid = _draw_tank(p, rng)
    sol1, sol2, sol3 = solve_tank(**numbers)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    assert isinstance(sol3.answer, SymbolicAnswer)
    x0 = sympy.sympify(sol3.answer.srepr)

    sq1 = SubQuestionMR(
        label="(1)", asked="formulation", answer=sol1.answer, steps=sol1.steps,
        concept_tags=concept_tags, cause_tags=cause_tags,
    )
    sq2 = SubQuestionMR(
        label="(2)", asked="formulation", answer=sol2.answer, steps=sol2.steps,
        concept_tags=concept_tags, cause_tags=cause_tags,
    )
    sq3 = SubQuestionMR(
        label="(3)",
        asked="value",
        answer=SymbolicAnswer(srepr=sol3.answer.srepr, display=f"{x0}分後"),
        steps=sol3.steps,
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )

    t1, r1, r2, target = (numbers[k] for k in ("t1", "r1", "r2", "target"))
    scenario = (
        f"空の{container}に{liquid}を入れ始める。初めの{t1}分間は毎分{r1}Lで入れ、"
        f"その後は毎分{r2}Lで入れる。"
    )
    quantities = f"{container}に{liquid}を入れ始めてから x 分後の{liquid}の量を y Lとする。"

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "scenario_kind": "tank_piecewise",
            "numbers": {k: str(v) for k, v in numbers.items()},
            "slots": {"container": container, "liquid": liquid},
        },
        given={"scenario": scenario, "quantities": quantities},
        context_slots={
            "container": container,
            "liquid": liquid,
            "ask_formulation_1": f"0≦x≦{t1} のときの y を x の式で表せ。",
            "ask_formulation_2": f"x≧{t1} のときの y を x の式で表せ。",
            "ask_value": f"{liquid}の量が{target}Lになるのは、{liquid}を入れ始めてから何分後か求めよ。",
        },
        sub_questions=[sq1, sq2, sq3],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
# meeting_intersection（g2_l30 Lv3）: 2直線の交点（出会い）。
# ---------------------------------------------------------------------------
def solve_meeting(va: int, vb: int, distance: int) -> list[Solution]:
    """(1)Aの式 y=va・x →(2)Bの式を立ててから交点(出会う時刻)を解く（recipe/checker 共有）。

    A は出発地点から y=va・x（原点を通る）。B は distance 離れた地点から相手に向けて
    進むので y=distance−vb・x。既存 solver `math.intersection_of_two_lines` に
    A1x+B1y=C1 形（A: va・x−y=0／B: vb・x+y=distance）で渡して連立を解く。求めるのは
    出会う時刻（x）だけなので、道のり（y）を求める最後の一手は解説から落とす。
    """
    slope_point = REGISTRY.solver("math.linear_expr_from_slope_point")
    form_sol = cast(Solution, slope_point(va, (0, 0)))

    formulate_b_step = Step(
        op="formulate_line_b",
        args=[],
        result_srepr=sympy.srepr(
            sympy.Eq(_Y, sympy.Integer(distance) - sympy.Integer(vb) * _X)
        ),
        result_display=f"y = {distance} - {vb}x",
        narration="もう一方の人が出発地点から相手に向かって進むようすを、道のりの式で表す。",
    )
    intersection = REGISTRY.solver("math.intersection_of_two_lines")
    inter_sol = cast(Solution, intersection((va, -1, 0), (vb, 1, distance), "substitute"))
    assert isinstance(inter_sol.answer, SymbolicAnswer)
    point = sympy.sympify(inter_sol.answer.srepr)
    x0 = cast(sympy.Expr, point[0])

    value_sol = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(x0), display=f"{x0}分後"),
        # 出会う時刻(x)を求めるところまでで打ち切る（道のり y を求める最後の一手は
        # 本問では問われないので落とす。word_problem_system.solving_steps と同型の trim）。
        steps=[formulate_b_step, *inter_sol.steps[:2]],
    )
    return [form_sol, value_sol]


def _draw_meeting(p: dict[str, Any], rng: Rng) -> tuple[dict[str, int], str, str, str, str]:
    """(numbers, 地点A, 地点B, 人物A, 人物B) を answer-first で抽選する。

    出会う時刻(meet_time)を先に引き、そこから距離(distance)を逆算する。
    """
    # **速さは候補集合（5m 刻み）から引く。** 前は整数域から引いていたので
    # 「毎分71m」「毎分62m」が出て、逆算した道のりも 1208m と端数になっていた。
    speeds = [int(v) for v in p["speed_set"]]
    time_lo, time_hi = (int(v) for v in p["meet_time_range"])
    distance_max = int(p["distance_max"])
    for _ in range(500):
        va, vb = draw_many({"int_set": speeds, "distinct": ["value"]}, rng, k=2)
        va, vb = int(va), int(vb)
        meet_time = int(draw({"int_range": [time_lo, time_hi]}, rng))
        distance = meet_time * (va + vb)
        if distance > distance_max:
            continue
        if meet_time in (va, vb, distance):
            continue
        place_a, place_b = split_pair(str(draw(p["place_pair_candidates"], rng)))
        name_a, name_b = split_pair(str(draw(p["person_pair_candidates"], rng)))
        return {"va": va, "vb": vb, "distance": distance}, place_a, place_b, name_a, name_b
    raise ValueError("meeting construction: 500回試行しても条件を満たす組が見つからない")


def _build_meeting_mr(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    numbers, place_a, place_b, name_a, name_b = _draw_meeting(p, rng)
    form_sol, value_sol = solve_meeting(**numbers)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    formulation_sq = SubQuestionMR(
        label="(1)", asked="formulation", answer=form_sol.answer, steps=form_sol.steps,
        concept_tags=concept_tags, cause_tags=cause_tags,
    )
    value_sq = SubQuestionMR(
        label="(2)", asked="value", answer=value_sol.answer, steps=value_sol.steps,
        concept_tags=concept_tags, cause_tags=cause_tags,
    )

    va, vb, distance = numbers["va"], numbers["vb"], numbers["distance"]
    scenario = (
        f"{name_a}と{name_b}は{distance}mはなれた{place_a}と{place_b}にいる。"
        f"{name_a}は{place_a}を出発して{place_b}へ毎分{va}mで、"
        f"{name_b}は{name_a}と同時に{place_b}を出発して{place_a}へ毎分{vb}mで進む。"
    )
    quantities = "出発してから x 分後とする。"

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "scenario_kind": "meeting_intersection",
            "numbers": {k: str(v) for k, v in numbers.items()},
            "slots": {
                "place_a": place_a, "place_b": place_b,
                "name_a": name_a, "name_b": name_b,
            },
        },
        given={"scenario": scenario, "quantities": quantities},
        context_slots={
            "place_a": place_a,
            "place_b": place_b,
            "name_a": name_a,
            "name_b": name_b,
            "ask_formulation": (
                f"{name_a}について、出発してから x 分後の{place_a}からの道のり y m を式で表せ。"
            ),
            "ask_value": "2人が出会うのは出発してから何分後か求めよ。",
        },
        sub_questions=[formulation_sq, value_sq],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
# recipe（3セル共通。scenario_kind が level_sep を作る）

# ---------------------------------------------------------------------------
# tank_race（g2_l28.word_problem Lv4）: 減る水そうと増える水そうが等しくなるとき
#
# 台帳 example: 満水 C L の水そうを A さんが一定の割合で m 分後に空にし、同時に
# 別の空の水そうへ B さんが毎分 r L 入れる。2つの量が等しくなる時刻とそのときの量。
# 減る側は y = C − (C/m)x、増える側は y = r·x の2直線なので、既存 solver
# `math.intersection_of_two_lines` の交点そのもの＝新しい数学は要らない。
# 誘導なし1小問で、時刻と量の2つを自分で順に出す。
# ---------------------------------------------------------------------------
def solve_tank_race(capacity: int, empty_minutes: int, fill_rate: int) -> list[Solution]:
    """(等しくなる時刻, そのときの量) を1つの Solution で返す（recipe/checker 共有）。"""
    if capacity <= 0 or empty_minutes <= 0 or fill_rate <= 0:
        raise ValueError("容量・時間・割合は正であること")
    if capacity % empty_minutes:
        raise ValueError("抜く割合が整数にならない")
    drain = capacity // empty_minutes
    intersection = REGISTRY.solver("math.intersection_of_two_lines")
    # 減る側: drain·x + y = capacity ／ 増える側: −fill_rate·x + y = 0
    sol = cast(
        Solution,
        intersection((drain, 1, capacity), (-fill_rate, 1, 0), "elimination"),
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    point = sympy.sympify(sol.answer.srepr)
    t, amount = cast(sympy.Expr, point[0]), cast(sympy.Expr, point[1])
    if t <= 0 or amount <= 0 or t >= empty_minutes:
        raise ValueError(f"等しくなる時刻が場面の中に無い: {t}")
    # 恒真: その時刻に両方の量が一致する。
    if not sympy.simplify((capacity - drain * t) - amount) == 0:
        raise ValueError("2つの水そうの量が一致しない")

    drain_step = Step(
        op="find_drain_rate",
        args=[],
        result_srepr=sympy.srepr(sympy.Integer(drain)),
        result_display=f"毎分{drain}L",
        narration="満水の量を空になるまでの時間でわって、水を抜く割合を求める。",
    )
    formulate_step = Step(
        op="formulate_two_lines",
        args=[],
        result_srepr="",
        # **括弧は「その手で得たもの」。** 指示の言い直しで、式が1つも出ていなかった。
        result_display=(
            f"減る側 y = {capacity} - {drain}x、増える側 y = {fill_rate}x"
        ),
        narration="減っていく水そうと増えていく水そうの量を、それぞれ経過した時間の式で表す。",
    )
    answer = SymbolicAnswer(
        srepr=sympy.srepr(sympy.Tuple(t, amount)),
        display=f"{t}分後、そのときの水の量は{amount}L",
    )
    return [Solution(answer=answer, steps=[drain_step, formulate_step, *sol.steps])]


def _draw_tank_race(p: dict[str, Any], rng: Rng) -> tuple[dict[str, int], str, str]:
    """(numbers, A の名前, B の名前)。

    【組合せ数】(容量, 空になるまでの分, 入れる割合) を列挙してから引く。等しくなる
    時刻と量がともに整数になる組だけを残す。名前の組が乗る。

    【退化・漏洩の封じ方】答え（時刻・量）が本文の数値（容量・分・割合）と一致する組は
    外す。抜く割合と入れる割合が同じだと「ちょうど半分で出会う」自明な場面になるので
    これも外す。
    """
    cands: list[tuple[int, int, int]] = []
    for cap in p["capacity_candidates"]:
        c = int(cap)
        for minutes in p["minutes_candidates"]:
            m = int(minutes)
            if m >= c or c % m:
                continue
            drain = c // m
            for rate in p["rate_candidates"]:
                r = int(rate)
                if r == drain:
                    continue  # 半分で出会う自明な場面
                if (c % (drain + r)) or ((c * r) % (drain + r)):
                    continue  # 時刻・量がともに整数になる組だけ
                t = c // (drain + r)
                amount = c * r // (drain + r)
                if {t, amount} & {c, m, r, drain}:
                    continue
                cands.append((c, m, r))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    capacity, minutes, rate = cands[idx]
    name_a, name_b = split_pair(str(draw(list(p["person_pair_candidates"]), rng)))
    return (
        {"capacity": capacity, "empty_minutes": minutes, "fill_rate": rate},
        name_a,
        name_b,
    )


def _build_tank_race_mr(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    numbers, name_a, name_b = _draw_tank_race(p, rng)
    (sol,) = solve_tank_race(**numbers)
    cap, minutes, rate = (
        numbers["capacity"], numbers["empty_minutes"], numbers["fill_rate"]
    )
    scenario = (
        f"満水で{cap}Lの水そうがある。{name_a}さんは一定の割合で水を抜き、"
        f"{minutes}分後に空にした。同時に、別の空の水そうに{name_b}さんが"
        f"毎分{rate}Lの割合で水を入れ始めた。"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "scenario_kind": "tank_race",
            "numbers": {k: str(v) for k, v in numbers.items()},
            "slots": {"name_a": name_a, "name_b": name_b},
        },
        given={"scenario": scenario},
        context_slots={
            "name_a": name_a, "name_b": name_b,
            "ask_value": (
                "2つの水そうの水の量が等しくなるのは水を入れ始めてから何分後か、"
                "また、そのときの水の量を求めよ。"
            ),
        },
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
                concept_tags=list(
                    ctx.spec_level.concept_tags or ctx.spec_family.concepts_default
                ),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
# second_meeting（g2_l30.word_problem Lv4）: 折り返す人と2回目に出会う時刻
#
# 台帳 example の数値（1800m・毎分90m・毎分60m・6分後）は、2回目の出会いの時刻が
# 48分になる一方で相手が36分で着いてしまい、場面として成立しない。ここでは
# 「1回目が往路に収まり、2回目が復路で、しかも相手が着く前に起きる」組だけを
# 構成の段階で列挙して引く（solver 側でも同じ条件を検算する）。
# ---------------------------------------------------------------------------
def solve_second_meeting(
    distance: int, speed_a: int, speed_b: int, head_start: int
) -> list[Solution]:
    """2回目に出会う時刻（recipe/checker 共有）。"""
    solver = REGISTRY.solver("math.solve_second_meeting_time")
    return [cast(Solution, solver(distance, speed_a, speed_b, head_start))]


def _draw_second_meeting(p: dict[str, Any], rng: Rng) -> tuple[dict[str, int], str, str, str, str]:
    """(numbers, 地点A, 地点B, 人物A, 人物B)。

    【組合せ数】(距離, 速い側, 遅い側, 出発の差) を列挙してから引く。2回目の時刻が
    整数になり、場面として成立する組だけを残す（既定で千通りを超える）。
    地点と人物の組がさらに乗る。
    """
    solver = REGISTRY.solver("math.solve_second_meeting_time")
    cands: list[tuple[int, int, int, int]] = []
    for dist in p["distance_candidates"]:
        d = int(dist)
        for va in p["fast_speed_candidates"]:
            a = int(va)
            for vb in p["slow_speed_candidates"]:
                b = int(vb)
                if b >= a:
                    continue
                for h in p["head_start_candidates"]:
                    hs = int(h)
                    try:
                        sol = cast(Solution, solver(d, a, b, hs))
                    except ValueError:
                        continue
                    assert isinstance(sol.answer, SymbolicAnswer)
                    t = sympy.sympify(sol.answer.srepr)
                    if t.q != 1:
                        continue  # 時刻が整数になる組だけ
                    if int(t) in (d, a, b, hs):
                        continue  # 答えが本文の数値と一致する組は外す
                    cands.append((d, a, b, hs))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    distance, speed_a, speed_b, head_start = cands[idx]
    place_a, place_b = split_pair(str(draw(list(p["place_pair_candidates"]), rng)))
    name_a, name_b = split_pair(str(draw(list(p["person_pair_candidates"]), rng)))
    return (
        {
            "distance": distance, "speed_a": speed_a,
            "speed_b": speed_b, "head_start": head_start,
        },
        place_a, place_b, name_a, name_b,
    )


def _build_second_meeting_mr(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    numbers, place_a, place_b, name_a, name_b = _draw_second_meeting(p, rng)
    (sol,) = solve_second_meeting(**numbers)
    d, va, vb, h = (
        numbers["distance"], numbers["speed_a"], numbers["speed_b"], numbers["head_start"]
    )
    scenario = (
        f"{place_a}と{place_b}は{d}mはなれている。"
        f"{name_a}さんは{place_a}を出発して{place_b}へ毎分{va}mで進み、"
        f"{place_b}に着くとすぐ折り返して同じ速さで{place_a}へもどる。"
        f"{name_b}さんは{name_a}さんが出発してから{h}分後に{place_b}を出発し、"
        f"毎分{vb}mで{place_a}へ進む。"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "scenario_kind": "second_meeting",
            "numbers": {k: str(v) for k, v in numbers.items()},
            "slots": {
                "place_a": place_a, "place_b": place_b,
                "name_a": name_a, "name_b": name_b,
            },
        },
        given={"scenario": scenario},
        context_slots={
            "place_a": place_a, "place_b": place_b,
            "name_a": name_a, "name_b": name_b,
            "ask_value": (
                f"2人が2回目に出会うのは{name_a}さんが出発してから何分後か求めよ。"
            ),
        },
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
                concept_tags=list(
                    ctx.spec_level.concept_tags or ctx.spec_family.concepts_default
                ),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


# ---------------------------------------------------------------------------
_BUILDERS = {
    "spring_two_point": _build_spring_mr,
    "tank_piecewise": _build_tank_mr,
    "meeting_intersection": _build_meeting_mr,
    "tank_race": _build_tank_race_mr,
    "second_meeting": _build_second_meeting_mr,
}


@register_recipe(RECIPE_NAME, provides_concepts=_LINEAR_FUNCTION_CONCEPTS)
def word_problem_linear_function(ctx: CellContext, rng: Rng) -> MR:
    kind = str(ctx.spec_level.params["scenario_kind"])
    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"未知の scenario_kind: {kind!r}")
    return builder(ctx, rng)


__all__ = [
    "RECIPE_NAME",
    "solve_meeting",
    "solve_spring",
    "solve_tank",
    "solve_tank_race",
    "solve_second_meeting",
    "word_problem_linear_function",
]
