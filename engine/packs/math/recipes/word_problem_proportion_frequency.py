"""比例・反比例の利用 ＋ 相対度数としての確率（form=word_problem・C14 の4セル）。

`word_problem_proportion.py`（g1_l29/g1_l33）で通した骨格を、**総合利用**の2レッスン
（g1_l36「比例・反比例を利用して身のまわりの問題を解く」・g1_l59「多数の観察や多数回
の試行によって得られる確率の意味」）に横展開する module。数学は既存 solver に委ねる
＝**新 solver ゼロ**。

## なぜこの2レッスンが1つの recipe に入るか

g1_l59 の「見積もった確率から回数を予測する」は、**相対度数 p を比例定数とする比例
y = p·x の評価**そのものである（`math.evaluate_direct_proportion`）。したがって
g1_l36（比例・反比例の利用）と g1_l59（相対度数としての確率）は
「場面から比例定数を決める → その式に目標値をあてはめる」という同じ2段構造を共有する。
1 recipe で4セルを賄えるのはこの共有のためで、こじつけの相乗りではない。

## 4セルの対応（すべて既存 solver）

  - g1_l36 Lv2 (`judge_and_use`): 水そうの場面を1つ引き、**比例か反比例かは seed で
    変わる**（`variant`）。誘導あり2小問 (1)立式 (2)値。
      * variant="inverse": 「毎分 r0 L で満水まで m0 分」→ 積 r0·m0 が一定
        （`math.solve_inverse_proportion_from_point`）→ `math.evaluate_inverse_proportion`
      * variant="direct":  「毎分 r0 L の割合で入れる」＝点 (1, r0)
        （`math.solve_direct_proportion_from_point`）→ `math.evaluate_direct_proportion`
    「どちらの関係かを見ぬく」が Lv2 の学習点なので、variant を seed で振るのが本質
    （数値の大小ではなく**関係の型**が動く）。
  - g1_l36 Lv3 (`meet_two_motions`): 先に出た人を追いかける場面。追いかけた側が出発
    してから x 分後の「2人それぞれの家からの道のり」を2つの直線とみて、
    `math.intersection_of_two_lines`（method="substitute"＝2式の y を等値）で交点を
    求め、その x 座標＝追いつくまでの時間を答える。g1_l27.word_problem Lv3 の同種
    場面とは経路が違う（あちらは `math.solve_linear_equation` で1本の方程式を解く／
    こちらは2つの関係をグラフ上で比較して交点を読む＝g1_l36 の「複数の関係を1つの
    グラフ上で比較し交点等を読む」）。
  - g1_l59 Lv2 (`experiment_frequency_predict`): 実験（キャップ投げ）の結果から
    相対度数を求め、それを確率の見積もりとみなし、これから投げる回数での予測回数を
    求める。誘導あり2小問。`math.relative_frequency` →
    `math.evaluate_direct_proportion`（相対度数を比例定数とみる）。
  - g1_l59 Lv3 (`defect_rate_estimate`): 抜き取り検査の不良品数から不良率を見積もり、
    これから作る個数での不良品数を予測する。誘導なし1小問（相対度数は答えに現れない
    中間量になり、自分で「割合を求める→かける」を構成する）。solver は Lv2 と同じ2本。

## 実験データから確率を「見積もる」＝理論確率ではない

g1_l59 は「多数回の試行によって得られる確率＝相対度数」の単元なので、場面は必ず
**実験（試行回数と起こった回数）**として与え、理論確率（1/2 等）は一切使わない。
答えが一意に定まるよう、候補列挙の時点で

  - Lv2: 相対度数が**小数で正確に表せる**組（p·1000 が整数）だけを残す
    （「四捨五入して…位まで」という丸めの指示に頼らずに答えが一意に定まる）
  - Lv3: 予測個数 defects·future/sample が**整数**になる組だけを残す

に絞る。

## params が持つのは「本文に出ている数値」だけ

`params["numbers"]` は場面文（given.scenario / given.quantities）または小問文
（context_slots）に現れている数値だけで、答え（式・値・相対度数）は入っていない。
checker は `SOLVE_BUILDERS`（recipe と共有）でその数値から solver を呼び直す。
`variant` は数値ではない構成フラグなので `numbers` ではなく params 直下に置く
（`numbers` の値は「本文に現れること」を contract テストが機械検査するため）。

## narration に数字を書かない

`meet_two_motions` / `experiment_frequency_predict` / `defect_rate_estimate` は
solver を合成するので、solver 自身の steps をそのまま見せると語彙がズレる
（「比例定数」「2つの直線の y を等しいとおき」）。この3つは合成後の意味に沿った
steps をここで組み直す（値は result_display のみ）。`judge_and_use` は比例・反比例
そのものの場面なので既存 solver の steps をそのまま使う。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

RECIPE_NAME = "math.word_problem_proportion_frequency"

_PROPORTION_FREQUENCY_CONCEPTS = [
    "proportion.word_problem_judge_and_use",
    "proportion.word_problem_meet_two_motions",
    "probability.word_problem_relative_frequency_predict",
    "probability.word_problem_defect_rate_estimate",
]


# ---------------------------------------------------------------------------
# 表示ヘルパ
# ---------------------------------------------------------------------------
def _decimal_display(p: sympy.Rational) -> str:
    """相対度数を「正確な小数」として表示する（候補列挙で p·1000 は整数）。

    float を経由すると 0.30000000000000004 のような誤差表示になるため、整数演算
    だけで小数文字列を組む。
    """
    scaled = sympy.Rational(p) * 1000
    if scaled.q != 1:
        raise ValueError(f"小数で正確に表せない相対度数: {p}")
    whole, frac = divmod(int(scaled), 1000)
    if frac == 0:
        return str(whole)
    return f"{whole}." + f"{frac:03d}".rstrip("0")


# ---------------------------------------------------------------------------
# 場面（recipe が組む）と、そこから solver に渡す数値
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProportionFrequencyScene:
    """場面文と、そこから solve に渡す数値。

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す辞書（params にそのまま載り、
    checker が同じ関数へ渡す）。`ask_texts` は小問文（誘導なしは長さ1）。
    `asked` は小問の asked（(1) が立式のセルだけ "formulation" が先頭に来る）。
    """

    numbers: dict[str, Any]
    scenario: str
    ask_texts: tuple[str, ...]
    asked: tuple[str, ...]
    slots: dict[str, str] = field(default_factory=dict)
    # 誘導ありで変数の設定を本文に出すセルだけが持つ（無い場合は空文字）。
    quantities: str = ""
    # 数値ではない構成フラグ（numbers に置けない）。空なら params に載せない。
    variant: str = ""


def _draw_index(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _split_pair(token: str) -> tuple[str, str]:
    """"姉|妹" → ("姉", "妹")。"""
    left, _, right = str(token).partition("|")
    return left, right


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「場面の数値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_judge_and_use(numbers: Mapping[str, Any]) -> list[Solution]:
    """g1_l36 Lv2: 水そうの場面が比例か反比例かを見ぬき、式を立てて値を求める。

    `variant` が "inverse"（満水までの時間）か "direct"（x 分後の水の量）かで
    呼ぶ solver の対が変わる。どちらも既存 solver 2本の直列。
    """
    variant = str(numbers["variant"])
    rate0 = int(numbers["rate0"])
    if variant == "inverse":
        minutes0 = int(numbers["minutes0"])
        rate1 = int(numbers["rate1"])
        form_sol = cast(
            Solution,
            REGISTRY.solver("math.solve_inverse_proportion_from_point")(rate0, minutes0, "basic"),
        )
        a = sympy.Integer(rate0 * minutes0)
        eval_sol = cast(
            Solution, REGISTRY.solver("math.evaluate_inverse_proportion")(a, rate1, "forward")
        )
        label, unit = "反比例する", "分"
    elif variant == "direct":
        minutes1 = int(numbers["minutes1"])
        form_sol = cast(
            Solution,
            REGISTRY.solver("math.solve_direct_proportion_from_point")(1, rate0, "integer"),
        )
        a = sympy.Integer(rate0)
        eval_sol = cast(
            Solution, REGISTRY.solver("math.evaluate_direct_proportion")(a, minutes1, "basic")
        )
        label, unit = "比例する", "L"
    else:
        raise ValueError(f"未知の variant: {variant!r}")
    assert isinstance(form_sol.answer, SymbolicAnswer)
    assert isinstance(eval_sol.answer, SymbolicAnswer)

    # (1) の答えは式だが、この Lv の学習点は「比例か反比例かを見ぬくこと」なので
    # 判別の語を表示に含める（機械表現 srepr は式そのままで、G-Q1 の突き合わせは
    # 式で行われる）。
    formulation = Solution(
        answer=SymbolicAnswer(
            srepr=form_sol.answer.srepr, display=f"{label}、{form_sol.answer.display}"
        ),
        steps=form_sol.steps,
    )
    value = Solution(
        answer=SymbolicAnswer(
            srepr=eval_sol.answer.srepr, display=f"{eval_sol.answer.display}{unit}"
        ),
        steps=eval_sol.steps,
    )
    return [formulation, value]


def solve_meet_two_motions(numbers: Mapping[str, Any]) -> list[Solution]:
    """g1_l36 Lv3: 2人の「時間と道のり」の関係を直線とみて交点の x 座標を求める。

    速い側 y = vf·x（＝ vf·x − y = 0）、遅い側 y = vs·(x + h)（＝ vs·x − y = −vs·h）を
    `math.intersection_of_two_lines` に渡す。答えは交点の x 座標（追いつくまでの分）。
    """
    speed_slow = int(numbers["speed_slow"])
    head_start = int(numbers["head_start"])
    speed_fast = int(numbers["speed_fast"])
    sol = cast(
        Solution,
        REGISTRY.solver("math.intersection_of_two_lines")(
            (speed_fast, -1, 0),
            (speed_slow, -1, -speed_slow * head_start),
            "substitute",
        ),
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    point = sympy.sympify(sol.answer.srepr)
    minutes = cast(sympy.Expr, point[0])

    steps = [
        Step(
            op="form_expression",
            args=[],
            result_srepr="",
            result_display="2人それぞれについて、時間と道のりの関係を式に表す",
            narration=(
                "追いかけた側が出発してからの時間をxとおき、"
                "2人それぞれの家からの道のりyを、xの式で表す。"
            ),
        ),
        Step(
            op="equate_expressions",
            args=[],
            result_srepr="",
            result_display="2つの関係のグラフの交点を求める",
            narration=(
                "2つの関係を同じ座標平面上のグラフとみて、"
                "道のりが等しくなる点、つまり交点を求める。"
            ),
        ),
        Step(
            op="read_x_coordinate",
            args=[],
            result_srepr=sympy.srepr(minutes),
            result_display=f"{minutes}分後",
            narration="交点のx座標が、追いついたときの時間を表している。",
        ),
    ]
    answer = SymbolicAnswer(srepr=sympy.srepr(minutes), display=f"{minutes}分後")
    return [Solution(answer=answer, steps=steps)]


def _relative_frequency(occurred: int, total: int) -> sympy.Rational:
    """既存 solver `math.relative_frequency` に委ねて相対度数を求める。"""
    sol = cast(Solution, REGISTRY.solver("math.relative_frequency")(occurred, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Rational, sympy.sympify(sol.answer.srepr))


def _predict_count(p: sympy.Rational, future: int) -> sympy.Expr:
    """相対度数 p を比例定数とみて y = p·x に future をあてはめる（既存 solver）。

    solver に渡すのは sympy の Rational（文字列を渡すと `nsimplify` が偽の閉形式を
    返す罠がある＝鉄則②）。
    """
    sol = cast(Solution, REGISTRY.solver("math.evaluate_direct_proportion")(p, future, "basic"))
    assert isinstance(sol.answer, SymbolicAnswer)
    return cast(sympy.Expr, sympy.sympify(sol.answer.srepr))


def solve_experiment_frequency_predict(numbers: Mapping[str, Any]) -> list[Solution]:
    """g1_l59 Lv2: 実験の相対度数を確率とみなし、予測回数を求める（誘導あり2小問）。"""
    total = int(numbers["total"])
    occurred = int(numbers["occurred"])
    future = int(numbers["future"])
    p = _relative_frequency(occurred, total)
    predicted = _predict_count(p, future)
    p_display = _decimal_display(p)

    frequency_steps = [
        Step(
            op="divide_occurred_by_total",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=p_display,
            narration="表が出た回数を、投げた回数の合計でわって相対度数を求める。",
        ),
        Step(
            op="regard_as_probability",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=p_display,
            narration=(
                "投げた回数がじゅうぶんに多いので、この相対度数は一定の値に近づいたと"
                "みなせる。その値を、表が出る確率の見積もりとする。"
            ),
        ),
    ]
    predict_steps = [
        Step(
            op="regard_as_constant_rate",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=p_display,
            narration="見積もった確率を、投げる回数と表が出る回数を結ぶ一定の割合とみる。",
        ),
        Step(
            op="evaluate",
            args=[],
            result_srepr=sympy.srepr(predicted),
            result_display=f"{predicted}回",
            narration="その割合に、これから投げる回数をかけて、表が出る回数を予測する。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(p), display=p_display),
            steps=frequency_steps,
        ),
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(predicted), display=f"{predicted}回"),
            steps=predict_steps,
        ),
    ]


def solve_defect_rate_estimate(numbers: Mapping[str, Any]) -> list[Solution]:
    """g1_l59 Lv3: 抜き取り検査の結果から不良率を見積もり、不良品の個数を予測する。"""
    sample = int(numbers["sample"])
    defects = int(numbers["defects"])
    future = int(numbers["future"])
    p = _relative_frequency(defects, sample)
    predicted = _predict_count(p, future)

    steps = [
        Step(
            op="divide_occurred_by_total",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=f"{p}",
            narration="不良品だった個数を、検査した個数でわって、不良品の割合を求める。",
        ),
        Step(
            op="regard_as_probability",
            args=[],
            result_srepr=sympy.srepr(p),
            result_display=f"{p}",
            narration=(
                "検査した個数がじゅうぶんに多いので、この割合を、"
                "不良品が出る確率の見積もりとして使う。"
            ),
        ),
        Step(
            op="evaluate",
            args=[],
            result_srepr=sympy.srepr(predicted),
            result_display=f"{predicted}個",
            narration="見積もった割合に、これから作る個数をかけて、不良品の個数を予測する。",
        ),
    ]
    return [
        Solution(
            answer=SymbolicAnswer(srepr=sympy.srepr(predicted), display=f"{predicted}個"),
            steps=steps,
        )
    ]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "judge_and_use": solve_judge_and_use,
    "meet_two_motions": solve_meet_two_motions,
    "experiment_frequency_predict": solve_experiment_frequency_predict,
    "defect_rate_estimate": solve_defect_rate_estimate,
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ。数値を引いて場面文と numbers を組む）
# ---------------------------------------------------------------------------
def _inverse_tank_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(毎分 r0 L, 満水まで m0 分, 変えたあとの毎分 r1 L) の候補列挙。

    容量 V=r0·m0 が r1 で割り切れ（答えが分数になるのを避ける）、答え V/r1 が本文の
    どの数値とも一致しない（G-Q5t の漏洩誤検出を構成時に潰す）組だけを残す。
    r1≠r0（同じ割合なら問いが退化する）。
    """
    rates = [int(v) for v in p["rate_candidates"]]
    m_lo, m_hi = (int(v) for v in p["minutes_range"])
    out: list[tuple[int, int, int]] = []
    for r0 in rates:
        for m0 in range(m_lo, m_hi + 1):
            volume = r0 * m0
            for r1 in rates:
                if r1 == r0 or volume % r1:
                    continue
                answer = volume // r1
                if answer in (r0, m0, r1) or answer < 2:
                    continue
                out.append((r0, m0, r1))
    return out


def _direct_tank_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(毎分 r0 L, 経過 m1 分) の候補列挙。

    答え r0·m1 が本文のどの数値とも一致しない組だけを残す（m1=1 は「毎分…」と
    同じ問いになる退化なので除く）。
    """
    rates = [int(v) for v in p["rate_candidates"]]
    m_lo, m_hi = (int(v) for v in p["minutes_range"])
    out: list[tuple[int, int]] = []
    for r0 in rates:
        for m1 in range(max(2, m_lo), m_hi + 1):
            answer = r0 * m1
            if answer in (r0, m1):
                continue
            out.append((r0, m1))
    return out


def _scene_judge_and_use(p: Mapping[str, Any], rng: Rng) -> ProportionFrequencyScene:
    """g1_l36 Lv2: 水そうの場面。比例か反比例かは seed で変わる（学習点そのもの）。"""
    variant = "inverse" if int(draw({"int_range": [0, 1]}, rng)) == 0 else "direct"
    ask_formulation = "yはxに比例するか、反比例するかを答え、yをxの式で表せ。"
    if variant == "inverse":
        rate0, minutes0, rate1 = cast(
            "tuple[int, int, int]", _draw_index(_inverse_tank_candidates(p), rng)
        )
        numbers: dict[str, Any] = {"rate0": rate0, "minutes0": minutes0, "rate1": rate1}
        scenario = (
            f"毎分{rate0}Lずつ水を入れると、満水になるまで{minutes0}分かかる水そうがある。"
        )
        quantities = "この水そうに毎分xLずつ水を入れるとき、満水になるまでy分かかるとする。"
        ask_value = f"毎分{rate1}Lずつ水を入れると、何分で満水になるか求めよ。"
    else:
        rate0, minutes1 = cast("tuple[int, int]", _draw_index(_direct_tank_candidates(p), rng))
        numbers = {"rate0": rate0, "minutes1": minutes1}
        scenario = f"空の水そうに、毎分{rate0}Lの割合で水を入れる。"
        quantities = "水を入れ始めてからx分後の、水そうの中の水の量をyLとする。"
        ask_value = f"水を入れ始めてから{minutes1}分後の水の量は何Lか求めよ。"
    return ProportionFrequencyScene(
        numbers=numbers,
        scenario=scenario,
        quantities=quantities,
        ask_texts=(ask_formulation, ask_value),
        asked=("formulation", "value"),
        # 題材トークンは無い（水そうで固定）。variant は params 直下に載るので
        # dup_key は inverse/direct を区別する（slots に重ねて置かない）。
        slots={},
        variant=variant,
    )


def _meet_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(遅い側の分速 vs, 何分後に追いかけたか h, 速い側の分速 vf) の候補列挙。

    追いつくまでの時間 t = vs·h/(vf − vs) が整数になり、かつ本文の数値
    （vs・h・vf）のどれとも一致しない組だけを残す（G-Q5t の漏洩誤検出を構成時に
    潰す）。t が極端に大きい場面（何十分も追いつかない）は除く。
    """
    slows = [int(v) for v in p["slow_speed_candidates"]]
    fasts = [int(v) for v in p["fast_speed_candidates"]]
    heads = [int(v) for v in p["head_start_candidates"]]
    t_lo, t_hi = (int(v) for v in p["minutes_range"])
    out: list[tuple[int, int, int]] = []
    for vs in slows:
        for vf in fasts:
            if vf <= vs:
                continue
            for h in heads:
                t = sympy.Rational(vs * h, vf - vs)
                if t.q != 1:
                    continue
                minutes = int(t)
                if not (t_lo <= minutes <= t_hi):
                    continue
                if minutes in (vs, vf, h):
                    continue
                out.append((vs, h, vf))
    return out


def _scene_meet_two_motions(p: Mapping[str, Any], rng: Rng) -> ProportionFrequencyScene:
    """g1_l36 Lv3: 先に出た人を追いかける場面（2つの関係をグラフで比較する）。"""
    speed_slow, head_start, speed_fast = cast(
        "tuple[int, int, int]", _draw_index(_meet_candidates(p), rng)
    )
    first, second = _split_pair(str(_draw_index(list(p["person_pair_candidates"]), rng)))
    scenario = (
        f"{first}は分速{speed_slow}mで家を出発した。その{head_start}分後、"
        f"{second}が分速{speed_fast}mで同じ道を追いかけた。"
        f"{second}が出発してからx分後の、{first}と{second}それぞれの家からの道のりを考える。"
    )
    ask_value = (
        "2人の関係をそれぞれ式に表して同じ座標平面上のグラフとみたとき、"
        f"{second}が{first}に追いつくのは、{second}が出発してから何分後か求めよ。"
    )
    return ProportionFrequencyScene(
        numbers={
            "speed_slow": speed_slow,
            "head_start": head_start,
            "speed_fast": speed_fast,
        },
        scenario=scenario,
        ask_texts=(ask_value,),
        asked=("value",),
        slots={"first": first, "second": second},
    )


def _experiment_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(投げた回数 total, 表が出た回数 occurred, これから投げる回数 future) の候補列挙。

    相対度数 occurred/total が**小数で正確に表せる**（p·1000 が整数）・予測回数
    p·future が整数・どちらも本文の数値と一致しない組だけを残す。「四捨五入して
    …位まで」という丸めの指示を本文に置かずに答えが一意に定まる。
    """
    totals = [int(v) for v in p["total_candidates"]]
    futures = [int(v) for v in p["future_candidates"]]
    lo, hi = (sympy.Rational(str(v)) for v in p["ratio_range"])
    out: list[tuple[int, int, int]] = []
    for total in totals:
        for occurred in range(1, total):
            ratio = sympy.Rational(occurred, total)
            if not (lo <= ratio <= hi):
                continue
            if (ratio * 1000).q != 1:
                continue
            for future in futures:
                predicted = ratio * future
                if predicted.q != 1:
                    continue
                if int(predicted) in (total, occurred, future):
                    continue
                out.append((total, occurred, future))
    return out


def _scene_experiment_frequency_predict(
    p: Mapping[str, Any], rng: Rng
) -> ProportionFrequencyScene:
    """g1_l59 Lv2: 実験の結果から相対度数を求め、確率とみなして予測する。"""
    total, occurred, future = cast(
        "tuple[int, int, int]", _draw_index(_experiment_candidates(p), rng)
    )
    item = str(_draw_index(list(p["item_candidates"]), rng))
    scenario = (
        f"ある{item}を{total}回投げたところ、表が出た回数は{occurred}回であった。"
        f"この{item}を、さらに{future}回投げるときのことを考える。"
    )
    return ProportionFrequencyScene(
        numbers={"total": total, "occurred": occurred, "future": future},
        scenario=scenario,
        ask_texts=(
            (
                "表が出た相対度数を小数で求め、この結果から、表が出る確率はおよそいくつと"
                "見積もられるか答えよ。"
            ),
            f"この{item}をさらに投げるとき、表はおよそ何回出ると予測されるか求めよ。",
        ),
        asked=("value", "value"),
        slots={"item": item},
    )


def _defect_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(検査した個数 sample, 不良品の個数 defects, これから作る個数 future) の候補列挙。

    予測個数 defects·future/sample が整数になり、本文の数値と一致しない組だけを
    残す。不良率は数 % 以下（抜き取り検査として自然な範囲）に抑える。
    """
    samples = [int(v) for v in p["sample_candidates"]]
    futures = [int(v) for v in p["future_candidates"]]
    d_lo, d_hi = (int(v) for v in p["defect_range"])
    max_rate = sympy.Rational(str(p["max_defect_rate"]))
    out: list[tuple[int, int, int]] = []
    for sample in samples:
        for defects in range(d_lo, d_hi + 1):
            ratio = sympy.Rational(defects, sample)
            if ratio > max_rate:
                continue
            for future in futures:
                predicted = ratio * future
                if predicted.q != 1:
                    continue
                if int(predicted) in (sample, defects, future) or int(predicted) < 2:
                    continue
                out.append((sample, defects, future))
    return out


def _scene_defect_rate_estimate(p: Mapping[str, Any], rng: Rng) -> ProportionFrequencyScene:
    """g1_l59 Lv3: 抜き取り検査の結果から不良品の個数を予測する（誘導なし）。"""
    sample, defects, future = cast(
        "tuple[int, int, int]", _draw_index(_defect_candidates(p), rng)
    )
    product = str(_draw_index(list(p["product_candidates"]), rng))
    scenario = (
        f"ある工場で作られた{product}を無作為に{sample}個検査したところ、"
        f"不良品が{defects}個あった。この工場では、これから{product}をさらに"
        f"{future}個作る予定である。"
    )
    return ProportionFrequencyScene(
        numbers={"sample": sample, "defects": defects, "future": future},
        scenario=scenario,
        ask_texts=(
            (
                "そのうち、およそ何個の不良品が出ると予測されるか。"
                "見積もりの方針を自分で決めて求めよ。"
            ),
        ),
        asked=("value",),
        slots={"product": product},
    )


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], ProportionFrequencyScene]] = {
    "judge_and_use": _scene_judge_and_use,
    "meet_two_motions": _scene_meet_two_motions,
    "experiment_frequency_predict": _scene_experiment_frequency_predict,
    "defect_rate_estimate": _scene_defect_rate_estimate,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_PROPORTION_FREQUENCY_CONCEPTS)
def word_problem_proportion_frequency(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_BUILDERS[kind](p, rng)
    # solve に渡すのは「本文の数値」＋（あれば）構成フラグ variant。
    solve_input: dict[str, Any] = dict(scene.numbers)
    if scene.variant:
        solve_input["variant"] = scene.variant
    solutions = SOLVE_BUILDERS[kind](solve_input)
    assert len(solutions) == len(scene.ask_texts) == len(scene.asked)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})",
            asked=scene.asked[i],
            answer=sol.answer,
            steps=sol.steps,
            concept_tags=concept_tags,
            cause_tags=cause_tags,
        )
        for i, sol in enumerate(solutions)
    ]

    given = {"scenario": scene.scenario}
    if scene.quantities:
        given["quantities"] = scene.quantities

    context_slots = dict(scene.slots)
    if len(scene.ask_texts) == 2 and scene.asked[0] == "formulation":
        context_slots["ask_formulation"] = scene.ask_texts[0]
        context_slots["ask_value"] = scene.ask_texts[1]
    elif len(scene.ask_texts) == 2:
        context_slots["ask_1"] = scene.ask_texts[0]
        context_slots["ask_2"] = scene.ask_texts[1]
    else:
        context_slots["ask_value"] = scene.ask_texts[0]

    params: dict[str, Any] = {
        # 本文に出ている数値だけ（答えは入れない）。checker はここから solver を
        # 呼び直す。variant は数値ではない構成フラグなので numbers の外に置く。
        "scenario_kind": kind,
        "numbers": {k: str(v) for k, v in scene.numbers.items()},
        # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
        "slots": dict(scene.slots),
    }
    if scene.variant:
        params["variant"] = scene.variant

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given=given,
        context_slots=context_slots,
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "ProportionFrequencyScene",
    "SOLVE_BUILDERS",
    "solve_judge_and_use",
    "solve_meet_two_motions",
    "solve_experiment_frequency_predict",
    "solve_defect_rate_estimate",
    "word_problem_proportion_frequency",
]
