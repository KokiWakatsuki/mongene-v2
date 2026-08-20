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
from engine.packs.math.recipes.scene_vocab import (
    VocabStep,
    draw_index,
    draw_vocab,
)

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
    """g1_l36 Lv3: 1つの場面から**比例と反比例の両方**を立式して2つの量を求める。

    ★もとは「先に出た人を追いかける」場面で、遅い側の道のりが y = vs·x + vs·h
    ＝**中2「1次関数」**だった。中1 の比例・反比例では立てられない
    （2026-08-19 の外部評価で指摘。台帳 units.generated.yaml の example 自体が
    中2 の内容だった）。台帳 desc「複数量・グラフと絡む場面を自分で立式・場合分け
    して解く」のうち「複数量を自分で立式」を、中1 で習う2つの関係で満たす。

    場面は水そう（Lv2 と同じ題材だが、Lv2 は**どちらか一方**を見ぬいて誘導つきで
    解くのに対し、ここは**両方を自分で立てて**誘導なしで2つの量を答える）。

      満水の量 V = rate0 × minutes0            （比例の考えで全体量を出す）
      毎分 rate1 で入れるときの時間 = V / rate1  （割合と時間は反比例）
      毎分 rate0 で入れて minutes1 分後の量 = rate0 × minutes1（量は時間に比例）

    使う solver は Lv2 と同じ2本（新 solver ゼロ）。
    """
    rate0 = int(numbers["rate0"])
    minutes0 = int(numbers["minutes0"])
    rate1 = int(numbers["rate1"])
    minutes1 = int(numbers["minutes1"])

    capacity = sympy.Integer(rate0 * minutes0)
    time_sol = cast(
        Solution,
        REGISTRY.solver("math.evaluate_inverse_proportion")(capacity, rate1, "forward"),
    )
    amount_sol = cast(
        Solution,
        REGISTRY.solver("math.evaluate_direct_proportion")(
            sympy.Integer(rate0), minutes1, "basic"
        ),
    )
    assert isinstance(time_sol.answer, SymbolicAnswer)
    assert isinstance(amount_sol.answer, SymbolicAnswer)
    minutes = sympy.sympify(time_sol.answer.srepr)
    amount = sympy.sympify(amount_sol.answer.srepr)

    steps = [
        Step(
            op="find_capacity",
            args=[],
            result_srepr=sympy.srepr(capacity),
            result_display=f"満水の量は {sympy.sstr(capacity)}L",
            narration=(
                "はじめに与えられた割合と、満水までにかかる時間から、"
                "水そう全体の量を求める。"
            ),
        ),
        Step(
            op="use_inverse_relation",
            args=[],
            result_srepr=sympy.srepr(minutes),
            result_display=f"{sympy.sstr(minutes)}分",
            narration=(
                "全体の量が決まっているとき、毎分入れる量と満水までの時間は"
                "反比例する。その関係を使って、割合を変えたときの時間を求める。"
            ),
        ),
        Step(
            op="use_direct_relation",
            args=[],
            result_srepr=sympy.srepr(amount),
            result_display=f"{sympy.sstr(amount)}L",
            narration=(
                "入れる割合が決まっているとき、たまった水の量は時間に比例する。"
                "その関係を使って、たずねられた時間後の量を求める。"
            ),
        ),
    ]
    answer = SymbolicAnswer(
        srepr=sympy.srepr(sympy.Tuple(minutes, amount)),
        display=f"{sympy.sstr(minutes)}分、{sympy.sstr(amount)}L",
    )
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
# 3層に割る（Relation / 語彙の抽選 / Scene）
#
# 割り方と理由は word_problem_linear.py の同じ節に書いてある（charter §3）。
#
#   Relation  数の引き方・非退化条件・構成フラグ（`variant`）。日本語を出力に流さない
#   語彙の抽選 どのカタログからどう引くかの宣言だけ（`scene_vocab.draw_vocab`）
#   Scene     引かれた数と語彙から日本語を組む。`rng` を受け取らない
#
# この module の4場面はすべて「数 → 語彙」の順に引く（`judge_and_use` は
# `variant` を先に引くが、これも数と同じく Relation の仕事）。
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProportionFrequencyRelation:
    """関係（数と構成フラグだけ）。**日本語を持たない。**

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す辞書（params にそのまま載り、
    checker が同じ関数へ渡す）。`variant` は数値ではない構成フラグなので
    `numbers` には置けない（`numbers` の値は「本文に現れること」を contract テストが
    機械検査するため）。空なら params に載せない。
    """

    numbers: dict[str, Any]
    variant: str = ""


@dataclass(frozen=True)
class ProportionFrequencyScene:
    """場面（日本語だけ）。数は引かず、引かれた数と語彙を受け取って文を組む。

    `ask_texts` は小問文（誘導なしは長さ1）。`asked` は小問の asked
    （(1) が立式のセルだけ "formulation" が先頭に来る）。
    """

    scenario: str
    ask_texts: tuple[str, ...]
    asked: tuple[str, ...]
    slots: dict[str, str] = field(default_factory=dict)
    # 誘導ありで変数の設定を本文に出すセルだけが持つ（無い場合は空文字）。
    quantities: str = ""


# ---------------------------------------------------------------------------
# 語彙の抽選（宣言だけ。日本語はここに書かない）
# ---------------------------------------------------------------------------
_SCENE_VOCAB: dict[str, tuple[VocabStep, ...]] = {
    # 水そうの場面は題材トークンを持たない（水そうで固定）。
    "judge_and_use": (),
    "meet_two_motions": (("index", "vessel_candidates", ("vessel",)),),
    "experiment_frequency_predict": (("index", "item_candidates", ("item",)),),
    "defect_rate_estimate": (("index", "product_candidates", ("product",)),),
}


# ---------------------------------------------------------------------------
# Relation（数と構成フラグだけ。日本語を1文字も持たない）
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


def _relation_judge_and_use(p: Mapping[str, Any], rng: Rng) -> ProportionFrequencyRelation:
    """g1_l36 Lv2: 水そうの場面。比例か反比例かは seed で変わる（学習点そのもの）。

    「どちらの関係かを見ぬく」が Lv2 の学習点なので、`variant` を seed で振るのが
    本質（数値の大小ではなく**関係の型**が動く）。
    """
    variant = "inverse" if int(draw({"int_range": [0, 1]}, rng)) == 0 else "direct"
    if variant == "inverse":
        rate0, minutes0, rate1 = cast(
            "tuple[int, int, int]", draw_index(_inverse_tank_candidates(p), rng)
        )
        numbers: dict[str, Any] = {"rate0": rate0, "minutes0": minutes0, "rate1": rate1}
    else:
        rate0, minutes1 = cast(
            "tuple[int, int]", draw_index(_direct_tank_candidates(p), rng)
        )
        numbers = {"rate0": rate0, "minutes1": minutes1}
    return ProportionFrequencyRelation(numbers=numbers, variant=variant)


def _two_relation_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(はじめの割合 rate0, 満水までの分 minutes0, 変えた割合 rate1, たずねる分 minutes1)。

    満水の量 rate0·minutes0 が rate1 で割り切れる組だけを残す（答えが整数）。
    答え（時間・水の量）が本文のどの数値とも一致しない組だけを残す
    ——一致すると、問題を読まずに本文の数を書き写して当たってしまう。
    """
    rates = [int(v) for v in p["rate_candidates"]]
    lo, hi = (int(v) for v in p["minutes_range"])
    out: list[tuple[int, int, int, int]] = []
    for rate0 in rates:
        for minutes0 in range(lo, hi + 1):
            capacity = rate0 * minutes0
            for rate1 in rates:
                if rate1 == rate0 or capacity % rate1:
                    continue
                minutes = capacity // rate1
                if not lo <= minutes <= hi * 2:
                    continue
                for minutes1 in range(lo, minutes0 + 1):
                    # ★**満水になる時刻を超えて訊いてはいけない。** minutes1 を
                    # minutes0 と独立に引いていたので「毎分12Lで12分で満水（容量144L）」
                    # の水そうに「25分後の水の量は？」→ 300L という場面が出ていた
                    # （40seed 中 23件）。式としては解けるが場面が成り立たない
                    # ——**G-BT（逆翻訳）で読み手が見つけた**。数ごとの上下限
                    # （G-SC5）では捕まらない、数と数の関係の条件である。
                    amount = rate0 * minutes1
                    shown = {rate0, minutes0, rate1, minutes1}
                    if {minutes, amount} & shown:
                        continue
                    out.append((rate0, minutes0, rate1, minutes1))
    return out


def _relation_meet_two_motions(
    p: Mapping[str, Any], rng: Rng
) -> ProportionFrequencyRelation:
    """g1_l36 Lv3: 1つの場面から比例と反比例の両方を自分で立式する（誘導なし）。"""
    rate0, minutes0, rate1, minutes1 = cast(
        "tuple[int, int, int, int]", draw_index(_two_relation_candidates(p), rng)
    )
    return ProportionFrequencyRelation(
        numbers={
            "rate0": rate0,
            "minutes0": minutes0,
            "rate1": rate1,
            "minutes1": minutes1,
        },
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


def _relation_experiment_frequency_predict(
    p: Mapping[str, Any], rng: Rng
) -> ProportionFrequencyRelation:
    """g1_l59 Lv2: 実験の結果から相対度数を求め、確率とみなして予測する。"""
    total, occurred, future = cast(
        "tuple[int, int, int]", draw_index(_experiment_candidates(p), rng)
    )
    return ProportionFrequencyRelation(
        numbers={"total": total, "occurred": occurred, "future": future},
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


def _relation_defect_rate_estimate(
    p: Mapping[str, Any], rng: Rng
) -> ProportionFrequencyRelation:
    """g1_l59 Lv3: 抜き取り検査の結果から不良品の個数を予測する（誘導なし）。"""
    sample, defects, future = cast(
        "tuple[int, int, int]", draw_index(_defect_candidates(p), rng)
    )
    return ProportionFrequencyRelation(
        numbers={"sample": sample, "defects": defects, "future": future},
    )


RELATION_DRAWERS: dict[
    str, Callable[[Mapping[str, Any], Rng], ProportionFrequencyRelation]
] = {
    "judge_and_use": _relation_judge_and_use,
    "meet_two_motions": _relation_meet_two_motions,
    "experiment_frequency_predict": _relation_experiment_frequency_predict,
    "defect_rate_estimate": _relation_defect_rate_estimate,
}


# ---------------------------------------------------------------------------
# Scene（日本語だけ。数は引かない＝この節に抽選は1つも無い）
# ---------------------------------------------------------------------------
def _scene_judge_and_use(
    n: Mapping[str, Any], v: Mapping[str, str], variant: str = ""
) -> ProportionFrequencyScene:
    ask_formulation = "yはxに比例するか、反比例するかを答え、yをxの式で表せ。"
    if variant == "inverse":
        scenario = (
            f"毎分{n['rate0']}Lずつ水を入れると、"
            f"満水になるまで{n['minutes0']}分かかる水そうがある。"
        )
        quantities = (
            "この水そうに毎分xLずつ水を入れるとき、満水になるまでy分かかるとする。"
        )
        ask_value = f"毎分{n['rate1']}Lずつ水を入れると、何分で満水になるか求めよ。"
    else:
        scenario = f"空の水そうに、毎分{n['rate0']}Lの割合で水を入れる。"
        quantities = "水を入れ始めてからx分後の、水そうの中の水の量をyLとする。"
        ask_value = f"水を入れ始めてから{n['minutes1']}分後の水の量は何Lか求めよ。"
    return ProportionFrequencyScene(
        scenario=scenario,
        quantities=quantities,
        ask_texts=(ask_formulation, ask_value),
        asked=("formulation", "value"),
        # 題材トークンは無い（水そうで固定）。variant は params 直下に載るので
        # dup_key は inverse/direct を区別する（slots に重ねて置かない）。
        slots={},
    )


def _scene_meet_two_motions(
    n: Mapping[str, Any], v: Mapping[str, str], variant: str = ""
) -> ProportionFrequencyScene:
    vessel = v["vessel"]
    return ProportionFrequencyScene(
        scenario=(
            f"空の{vessel}に、毎分{n['rate0']}Lの割合で水を入れると"
            f"{n['minutes0']}分で満水になる。"
        ),
        ask_texts=(
            f"毎分{n['rate1']}Lの割合で入れると満水まで何分かかるか求めよ。"
            f"また、毎分{n['rate0']}Lの割合で入れ始めてから"
            f"{n['minutes1']}分後の水の量は何Lか求めよ。",
        ),
        asked=("value",),
        slots={"vessel": vessel},
    )


def _scene_experiment_frequency_predict(
    n: Mapping[str, Any], v: Mapping[str, str], variant: str = ""
) -> ProportionFrequencyScene:
    item = v["item"]
    return ProportionFrequencyScene(
        scenario=(
            f"ある{item}を{n['total']}回投げたところ、"
            f"表が出た回数は{n['occurred']}回であった。"
            f"この{item}を、さらに{n['future']}回投げるときのことを考える。"
        ),
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


def _scene_defect_rate_estimate(
    n: Mapping[str, Any], v: Mapping[str, str], variant: str = ""
) -> ProportionFrequencyScene:
    product = v["product"]
    return ProportionFrequencyScene(
        scenario=(
            f"ある工場で作られた{product}を無作為に{n['sample']}個検査したところ、"
            f"不良品が{n['defects']}個あった。この工場では、これから{product}をさらに"
            f"{n['future']}個作る予定である。"
        ),
        ask_texts=(
            (
                "そのうち、およそ何個の不良品が出ると予測されるか。"
                "見積もりの方針を自分で決めて求めよ。"
            ),
        ),
        asked=("value",),
        slots={"product": product},
    )


SCENE_RENDERERS: dict[
    str, Callable[[Mapping[str, Any], Mapping[str, str], str], ProportionFrequencyScene]
] = {
    "judge_and_use": _scene_judge_and_use,
    "meet_two_motions": _scene_meet_two_motions,
    "experiment_frequency_predict": _scene_experiment_frequency_predict,
    "defect_rate_estimate": _scene_defect_rate_estimate,
}


# ---------------------------------------------------------------------------
# G-SC3（骨格）— 関係が場面文に要求する言い方 / 禁じる言い方
# 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_PHRASES: dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]] = {
    # 比例か反比例かを見ぬく（枝で式が変わる）。水を入れる場面であることが要る。
    "judge_and_use": ((("水",), ("毎分",)), ("投げ", "検査")),
    # 1つの場面から比例と反比例の両方を立式する。満水になることが要る。
    "meet_two_motions": ((("毎分",), ("満水",)), ("投げ", "検査")),
    # 実験の相対度数を確率とみなす。**理論確率ではなく試行**であることが要る。
    "experiment_frequency_predict": ((("投げ",), ("回",)), ("毎分", "検査")),
    # 抜き取り検査の不良率。検査と不良品が要る。
    "defect_rate_estimate": ((("検査",), ("不良品",)), ("毎分", "投げ")),
}


# ---------------------------------------------------------------------------
# G-SC5（場面の妥当性）— 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_BOUNDS: dict[str, tuple[tuple[str, float, float], ...]] = {
    # 水そう: 毎分の割合は 1〜30L、時間は1時間まで。
    "judge_and_use": (
        ("rate0", 1, 30), ("rate1", 1, 30), ("minutes0", 1, 60), ("minutes1", 1, 60),
    ),
    "meet_two_motions": (
        ("rate0", 1, 30), ("rate1", 1, 30), ("minutes0", 1, 60), ("minutes1", 1, 60),
    ),
    # 試行: 回数は 5000 回まで（教材で数えられる大きさ）。
    "experiment_frequency_predict": (
        ("total", 10, 5000), ("occurred", 1, 5000), ("future", 10, 5000),
    ),
    # 抜き取り検査: 検査数は 5000 個、これから作るのは 10万個まで。
    # 不良品は**検査数の数%**（抜き取り検査として自然な範囲）なので 50 個までにする
    # ——500 にしていたら実物の最大 23 の20倍で、もう何も言っていなかった。
    "defect_rate_estimate": (
        ("sample", 10, 5000), ("defects", 1, 50), ("future", 100, 100000),
    ),
}


# ---------------------------------------------------------------------------
# G-SC5b（数と数の関係）— 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_ORDER: dict[str, tuple[tuple[str, str, str], ...]] = {
    # ★満水になる時刻を超えて訊いてはいけない（G-BT が見つけた欠陥）。
    "meet_two_motions": (("minutes1", "<=", "minutes0"),),
    # 変えたあとの割合は元と違う（同じなら問う意味が無い）。反比例の枝だけ rate1 がある。
    "judge_and_use": (("rate0", "!=", "rate1"),),
    # 起こった回数は試行回数より少ない。
    "experiment_frequency_predict": (("occurred", "<", "total"),),
    # 不良品は検査した個数より少ない。
    "defect_rate_estimate": (("defects", "<", "sample"),),
}


def draw_scene(
    kind: str, p: Mapping[str, Any], rng: Rng
) -> tuple[ProportionFrequencyRelation, ProportionFrequencyScene]:
    """関係 → 語彙 → 場面文 の順に組む。**この順番が RNG の消費順を決める。**"""
    relation = RELATION_DRAWERS[kind](p, rng)
    vocab = draw_vocab(_SCENE_VOCAB.get(kind, ()), p, rng)
    scene = SCENE_RENDERERS[kind](relation.numbers, vocab, relation.variant)
    return relation, scene
# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_PROPORTION_FREQUENCY_CONCEPTS)
def word_problem_proportion_frequency(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    relation, scene = draw_scene(kind, p, rng)
    # solve に渡すのは「本文の数値」＋（あれば）構成フラグ variant。
    solve_input: dict[str, Any] = dict(relation.numbers)
    if relation.variant:
        solve_input["variant"] = relation.variant
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
        "numbers": {k: str(v) for k, v in relation.numbers.items()},
        # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
        "slots": dict(scene.slots),
    }
    if relation.variant:
        params["variant"] = relation.variant

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
