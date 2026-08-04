"""平方根の利用＋既存クラスタの取りこぼし（form=word_problem・C14）。

`word_problem_probability.py` と同じ骨格（場面文＋(誘導なら)複数小問）を、**新 solver
ゼロ**で4セルに広げる module。数学は既存 solver

  - `math.simplify_radical`（mode=find_side_from_area）… 平方因数を見つけて a√b に簡約
  - `math.represent_opposite_quantity`             … 反対の向きの量に反対の符号をつける
  - `math.factorize_integer`（mode=factorize_basic）… 素因数分解

にそのまま委ね、この module は「場面の抽選」と「solver の出力を場面の言葉で合成する」
ことだけをする。

## 1つの recipe で4セルを賄う設計

params の `scenario_kind` が

  1. 場面の数値を answer-first で引く関数（`_SCENE_BUILDERS`）
  2. その数値から solver を呼んで解く関数（`SOLVE_BUILDERS`）

の対を選ぶ。`SOLVE_BUILDERS` は recipe と checker が**同じ関数を呼ぶ**（独立性は
「checker は params の場面文の数値だけから solver を呼び直す」ところにあり、recipe
側の答えを信用しない）。

## 4セルの対応

  - g3_l23 Lv2 (`square_plot_approx`): 面積 S の正方形。(1)1辺を根号で表す
    (2)√a の近似値を使って小数第1位まで求める（誘導あり2小問）。
  - g3_l23 Lv3 (`rectangle_ratio_side`): 縦と横の比が 1:r の長方形の面積が S。
    縦の長さを根号で表す（誘導なし・「何を x に置くか」から自分で立式する）。
  - g1_l1 Lv1 (`signed_reference`): 基準を決めた場面で、反対の性質をもつ2量を
    符号つきの数で表す（誘導あり2小問）。
  - g1_l11 Lv2 (`square_multiplier`): N にできるだけ小さい自然数をかけて平方数に
    する。(1)素因数分解 (2)かける数（誘導あり2小問）。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている数値（面積・比・量の大きさ・対象の数）
そのもので、答え（1辺の長さ・符号つきの数・かける数）は入っていない。導出値は
`SOLVE_BUILDERS` 側で導く:

  - √a の近似値（1.41 等）は params に置かず、面積 S の平方因数を外に出して得た a
    から `_ROOT_APPROX_HUNDREDTHS`（定数表）で引き直す。checker は「S を読み違えて
    いたら近似値も違う」経路で解き直すことになる。
  - 素因数分解の指数は params に置かず、N から sympy.factorint で導く。

## narration に数字を書かない

solver の steps はいずれも数字を含まない narration を持つので、原則そのまま使う。
文章題として最初の一手（「面積の平方根が1辺」「比から面積の式を立てる」）が抜ける
場面だけ、値を `result_display` にのみ置いた Step をここで前置する。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from math import isqrt
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many

RECIPE_NAME = "math.word_problem_sqrt_misc"

_SQRT_MISC_CONCEPTS = [
    "radical.word_problem_square_plot_approx",
    "radical.word_problem_rectangle_ratio_side",
    "number.word_problem_signed_reference",
    "prime_factorization.word_problem_square_multiplier",
]

# 教科書が与える平方根の近似値（1/100 単位の整数で持つ。小数を sympy に文字列で
# 渡さないため＝`sympy.nsimplify("1.41")` 系の偽の閉形式を踏まないため）。
_ROOT_APPROX_HUNDREDTHS: dict[int, int] = {2: 141, 3: 173, 5: 224, 6: 245, 7: 265, 10: 316}

# 平方因数を持たない数（1 より大きい squarefree）。長方形セルの根号の中身に使う。
_SQUAREFREE = [
    n for n in range(2, 40) if all(n % (p * p) != 0 for p in range(2, int(n**0.5) + 1))
]


# ---------------------------------------------------------------------------
# 場面文（recipe が組む）と、そこから solver に渡す数値
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SqrtMiscScene:
    """場面文と、そこから solve に渡す数値・題材語。

    - `numbers`: `SOLVE_BUILDERS[kind]` の第1引数。**場面文に出ている数値だけ**。
    - `labels` : 同・第2引数。数値ではない題材語（符号の向きの名前・単位）で、
      solver の引数になるもの。params には numbers と別に載せる
      （`test_word_problem_params_faithfulness` は numbers だけを数値として検査する）。
    - `ask_texts`: 小問文（誘導なしは長さ1）。
    - `slots`: 題材（dup_key は params のみを見る＝context_slots は算入されない）。
    """

    numbers: dict[str, Any]
    scenario: str
    ask_texts: tuple[str, ...]
    labels: dict[str, str] = field(default_factory=dict)
    slots: dict[str, str] = field(default_factory=dict)


def _draw_index(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _split_tokens(token: str) -> list[str]:
    """"花だん|m" → ["花だん", "m"]。"""
    return str(token).split("|")


def _decompose_square_factor(n: int) -> tuple[int, int]:
    """n = k²·a（a は平方因数を持たない）の (k, a) を返す。"""
    k, a = 1, n
    p = 2
    while p * p <= a:
        while a % (p * p) == 0:
            a //= p * p
            k *= p
        p += 1
    return k, a


def _fmt_hundredths(value: int) -> str:
    """1/100 単位の整数を小数表示にする。例: 141->"1.41" / 490->"4.9" / 700->"7"。"""
    whole, frac = divmod(value, 100)
    if frac == 0:
        return str(whole)
    if frac % 10 == 0:
        return f"{whole}.{frac // 10}"
    return f"{whole}.{frac:02d}"


def _fmt_tenths(value: int) -> str:
    """1/10 単位の整数を「小数第1位まで」の表示にする。例: 71->"7.1" / 80->"8.0"。"""
    whole, frac = divmod(value, 10)
    return f"{whole}.{frac}"


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「場面の数値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_square_plot_approx(
    numbers: Mapping[str, Any], labels: Mapping[str, str]
) -> list[Solution]:
    """g3_l23 Lv2: 面積 S の正方形。(1)1辺を根号で表す (2)近似値で小数第1位まで。"""
    del labels
    area = int(numbers["area"])
    k, a = _decompose_square_factor(area)

    solver = REGISTRY.solver("math.simplify_radical")
    sol_side = cast(Solution, solver(f"sqrt({area})", "find_side_from_area"))
    assert isinstance(sol_side.answer, SymbolicAnswer)
    # 文章題としての最初の一手（面積 → 平方根）は solver が持っていないので前置する。
    setup = Step(
        op="express_side_as_square_root",
        args=[],
        result_srepr="",
        result_display=f"√{area}",
        narration="正方形の面積は1辺の長さを2乗した値だから、1辺の長さは面積の正の平方根で表せる。",
    )
    sol1 = Solution(answer=sol_side.answer, steps=[setup, *sol_side.steps])

    # (2) 近似値。k√a に「√a=近似値」をあてはめて 1/100 単位の整数で厳密に計算し、
    # 小数第2位を四捨五入する（引き分けになる組は場面の抽選側で除いてある）。
    hundredths = k * _ROOT_APPROX_HUNDREDTHS[a]
    tenths = (hundredths + 5) // 10
    approx_value = sympy.Rational(tenths, 10)
    sol2 = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(approx_value), display=_fmt_tenths(tenths)),
        steps=[
            Step(
                op="substitute_root_approximation",
                args=[],
                result_srepr="",
                result_display=_fmt_hundredths(hundredths),
                narration="根号のついた数を、与えられた近似の値におきかえてかけ算をする。",
            ),
            Step(
                op="round_to_first_decimal",
                args=[],
                result_srepr=sympy.srepr(approx_value),
                result_display=_fmt_tenths(tenths),
                narration="小数第2位を四捨五入して、小数第1位までの値にする。",
            ),
        ],
    )
    return [sol1, sol2]


def solve_rectangle_ratio_side(
    numbers: Mapping[str, Any], labels: Mapping[str, str]
) -> list[Solution]:
    """g3_l23 Lv3: 縦と横の比が 1:r・面積 S の長方形の縦の長さ（誘導なし）。"""
    del labels
    ratio = int(numbers["ratio"])
    area = int(numbers["area"])
    squared = area // ratio  # 縦を x とすると x·(r·x)=S ⇒ x² = S/r

    solver = REGISTRY.solver("math.simplify_radical")
    sol_side = cast(Solution, solver(f"sqrt({squared})", "find_side_from_area"))
    assert isinstance(sol_side.answer, SymbolicAnswer)
    steps = [
        Step(
            op="set_variable",
            args=[],
            result_srepr=sympy.srepr(sympy.Symbol("x")),
            result_display="x",
            narration="縦の長さを x とおき、比を使って横の長さを x の何倍かで表す。",
        ),
        Step(
            op="formulate_area_equation",
            args=[],
            result_srepr="",
            result_display=f"{ratio}x² = {area}",
            narration="縦と横の長さの積が面積になることから、面積の関係を式に表す。",
        ),
        Step(
            op="isolate_squared_side",
            args=[],
            result_srepr="",
            result_display=f"x² = {squared}",
            narration="両辺を比から出てきた数でわって、縦の長さの2乗の値を求める。",
        ),
        *sol_side.steps,
    ]
    return [Solution(answer=sol_side.answer, steps=steps)]


def solve_signed_reference(
    numbers: Mapping[str, Any], labels: Mapping[str, str]
) -> list[Solution]:
    """g1_l1 Lv1: 基準を決めた場面で反対の性質をもつ2量を符号つきの数で表す。"""
    positive_label = str(labels["positive_label"])
    negative_label = str(labels["negative_label"])
    unit = str(labels["unit"])
    solver = REGISTRY.solver("math.represent_opposite_quantity")

    solutions: list[Solution] = []
    for asked_label, key in ((positive_label, "magnitude_positive"), (negative_label, "magnitude_negative")):
        magnitude = int(numbers[key])
        sol = cast(Solution, solver(positive_label, asked_label, magnitude))
        # solver は「符号の判断」を2択（ChoiceAnswer）で持つ。文章題では asked=value
        # なので、solver が選んだ正解の符号つきの数をそのまま値の答えに写す。
        assert isinstance(sol.answer, ChoiceAnswer)
        value = sympy.Integer(int(sol.answer.correct))
        solutions.append(
            Solution(
                answer=SymbolicAnswer(
                    srepr=sympy.srepr(value), display=f"{sol.answer.correct}{unit}"
                ),
                steps=list(sol.steps),
            )
        )
    return solutions


def solve_square_multiplier(
    numbers: Mapping[str, Any], labels: Mapping[str, str]
) -> list[Solution]:
    """g1_l11 Lv2: (1)N を素因数分解 (2)平方数にするためにかける最小の自然数。"""
    del labels
    n = int(numbers["n"])
    solver = REGISTRY.solver("math.factorize_integer")
    sol_factor = cast(Solution, solver(n, "factorize_basic"))

    # 指数が奇数の素因数の積＝平方数にするためにかける最小の自然数（squarefree part）。
    multiplier = 1
    for prime, exponent in sorted(sympy.factorint(n).items()):
        if int(exponent) % 2 == 1:
            multiplier *= int(prime)
    value = sympy.Integer(multiplier)
    sol_multiplier = Solution(
        answer=SymbolicAnswer(srepr=sympy.srepr(value), display=str(multiplier)),
        steps=[
            Step(
                op="collect_odd_exponent_primes",
                args=[],
                result_srepr="",
                result_display="指数が奇数の素因数を選ぶ",
                narration="素因数分解した結果から、指数が奇数になっている素因数を選び出す。",
            ),
            Step(
                op="multiply_to_make_square",
                args=[],
                result_srepr=sympy.srepr(value),
                result_display=str(multiplier),
                narration=(
                    "選び出した素因数をすべてかけ合わせて、かける数を求める。"
                    "かけたあとはすべての素因数の指数が偶数になり、平方数になる。"
                ),
            ),
        ],
    )
    return [sol_factor, sol_multiplier]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Mapping[str, str]], list[Solution]]] = {
    "square_plot_approx": solve_square_plot_approx,
    "rectangle_ratio_side": solve_rectangle_ratio_side,
    "signed_reference": solve_signed_reference,
    "square_multiplier": solve_square_multiplier,
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ。数値を引いて場面文と numbers を組む）
# ---------------------------------------------------------------------------
@lru_cache(maxsize=None)
def _square_plot_candidates(area_max: int) -> tuple[int, ...]:
    """正方形の面積 S=k²a の候補列挙（k≥2・a は近似値表にある squarefree）。

    残す条件:
      - k≥2: k=1 だと1辺が √a そのもので、(2)の答えが問題文の近似値と一致してしまう
        （G-Q5t の実害）。
      - k·(近似値) の小数第2位が 5 でない: 四捨五入が引き分けになる組を除く。
      - 近似値から四捨五入した値が、真の値 k√a を四捨五入した値と一致する
        （与えられた近似値で計算した答えが実際の長さとずれないことを構成時に保証）。
        真の値の四捨五入は整数平方根で厳密に出す: 10k√a を四捨五入した値 t は
        t = (⌊2·10k√a⌋ + 1) // 2 ＝ (isqrt(400k²a) + 1) // 2（浮動小数点を使わない）。
    """
    out: list[int] = []
    for a, approx in sorted(_ROOT_APPROX_HUNDREDTHS.items()):
        k = 2
        while k * k * a <= area_max:
            hundredths = k * approx
            if hundredths % 10 != 5:
                tenths = (hundredths + 5) // 10
                true_tenths = (isqrt(400 * k * k * a) + 1) // 2
                if tenths == true_tenths:
                    out.append(k * k * a)
            k += 1
    return tuple(sorted(out))


def _scene_square_plot_approx(p: Mapping[str, Any], rng: Rng) -> SqrtMiscScene:
    cands = list(_square_plot_candidates(int(p["area_max"])))
    area = int(draw({"int_set": cands}, rng))
    _, a = _decompose_square_factor(area)
    subject, unit = _split_tokens(str(_draw_index(list(p["subject_candidates"]), rng)))
    approx_disp = _fmt_hundredths(_ROOT_APPROX_HUNDREDTHS[a])
    # 近似値（√a=…）も given.scenario に置く（G-Q5t の whitelist は mr.given だけを
    # 見るため、ask 側にしか出さない数値は whitelist されず偽陽性になる＝踏んだ罠）。
    scenario = (
        f"面積が{area}{unit}²の正方形の{subject}をつくる。"
        f"ただし、√{a}={approx_disp}として計算してよいものとする。"
    )
    ask_texts = (
        f"この正方形の{subject}の1辺の長さを、根号を使って表せ。",
        "その長さを、小数第一位まで求めよ。",
    )
    return SqrtMiscScene(
        numbers={"area": area},
        scenario=scenario,
        ask_texts=ask_texts,
        slots={"subject": subject, "unit": unit},
    )


@lru_cache(maxsize=None)
def _rectangle_ratio_candidates(
    ratios: tuple[int, ...], area_max: int
) -> tuple[tuple[int, int], ...]:
    """(比の値 r, 面積 S=r·k²a) の候補列挙。

    x²=S/r が平方数にならない（a>1）組だけを残す＝答えが必ず根号を含む。
    """
    out: list[tuple[int, int]] = []
    for ratio in ratios:
        for a in _SQUAREFREE:
            k = 1
            while ratio * k * k * a <= area_max:
                out.append((ratio, ratio * k * k * a))
                k += 1
    return tuple(sorted(set(out)))


def _scene_rectangle_ratio_side(p: Mapping[str, Any], rng: Rng) -> SqrtMiscScene:
    cands = _rectangle_ratio_candidates(
        tuple(int(v) for v in p["ratio_candidates"]), int(p["area_max"])
    )
    ratio, area = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    subject = str(_draw_index(list(p["subject_candidates"]), rng))
    scenario = (
        f"縦と横の長さの比が1：{ratio}である長方形の{subject}があり、"
        f"その面積は{area}m²である。"
    )
    ask_texts = (f"この{subject}の縦の長さを、根号を使って表せ。",)
    return SqrtMiscScene(
        numbers={"ratio": ratio, "area": area},
        scenario=scenario,
        ask_texts=ask_texts,
        slots={"subject": subject},
    )


# 反対の性質をもつ2量の場面（正の向き・負の向き・単位・場面文・小問文）。
# 向きの名前は solver `math.represent_opposite_quantity` が持つ組（_OPPOSITE_PAIRS）
# と一致していなければならない（solver 側が未知の向きを ValueError で弾く）。
# 大きさの候補は単位ごとに分ける（「3000点」のような不自然な量を作らないため）。
_SIGNED_SCENES: list[tuple[str, str, str, str, str, str]] = [
    (
        "収入", "支出", "円",
        "ある店では、1日のお金の出入りを、収支が0円のときを基準として、"
        "収入を正の数、支出を負の数で表して記録している。"
        "月曜日は{a}円の収入があり、火曜日は{b}円の支出があった。",
        "月曜日の記録を、符号を使って表せ。",
        "火曜日の記録を、符号を使って表せ。",
    ),
    (
        "得点", "失点", "点",
        "あるチームでは、1試合の得失点を、得失点が0点のときを基準として、"
        "得点を正の数、失点を負の数で表して記録している。"
        "前半に{a}点の得点があり、後半に{b}点の失点があった。",
        "前半の記録を、符号を使って表せ。",
        "後半の記録を、符号を使って表せ。",
    ),
    (
        "値上がり", "値下がり", "円",
        "ある品物の値段の変化を、変化がないときを基準として、"
        "値上がりを正の数、値下がりを負の数で表して記録している。"
        "先月は{a}円の値上がりがあり、今月は{b}円の値下がりがあった。",
        "先月の値段の変化を、符号を使って表せ。",
        "今月の値段の変化を、符号を使って表せ。",
    ),
    (
        "増加", "減少", "人",
        "ある町の人口の変化を、変化がないときを基準として、"
        "増加を正の数、減少を負の数で表して記録している。"
        "昨年は{a}人の増加があり、今年は{b}人の減少があった。",
        "昨年の人口の変化を、符号を使って表せ。",
        "今年の人口の変化を、符号を使って表せ。",
    ),
    (
        "北へ", "南へ", "km",
        "地点Oを基準（0km）とし、北へ進むことを正の数、南へ進むことを負の数で表す。"
        "地点Oから北へ{a}km進んだ地点をA、南へ{b}km進んだ地点をBとする。",
        "地点Aの位置を、符号を使って表せ。",
        "地点Bの位置を、符号を使って表せ。",
    ),
    (
        "東へ", "西へ", "km",
        "地点Oを基準（0km）とし、東へ進むことを正の数、西へ進むことを負の数で表す。"
        "地点Oから東へ{a}km進んだ地点をA、西へ{b}km進んだ地点をBとする。",
        "地点Aの位置を、符号を使って表せ。",
        "地点Bの位置を、符号を使って表せ。",
    ),
]

_SIGNED_MAGNITUDES: dict[str, list[int]] = {
    "円": list(range(100, 3001, 100)),
    "点": list(range(1, 16)),
    "人": list(range(10, 501, 10)),
    "km": list(range(2, 41)),
}


def _scene_signed_reference(p: Mapping[str, Any], rng: Rng) -> SqrtMiscScene:
    del p
    index = int(draw({"int_range": [0, len(_SIGNED_SCENES) - 1]}, rng))
    positive_label, negative_label, unit, scenario_fmt, ask_a, ask_b = _SIGNED_SCENES[index]
    magnitudes = draw_many(
        {"int_set": _SIGNED_MAGNITUDES[unit], "distinct": ["value"]}, rng, k=2
    )
    magnitude_a, magnitude_b = (int(v) for v in magnitudes)
    scenario = scenario_fmt.format(a=magnitude_a, b=magnitude_b)
    return SqrtMiscScene(
        numbers={"magnitude_positive": magnitude_a, "magnitude_negative": magnitude_b},
        scenario=scenario,
        ask_texts=(ask_a, ask_b),
        labels={
            "positive_label": positive_label,
            "negative_label": negative_label,
            "unit": unit,
        },
        slots={"positive_label": positive_label, "negative_label": negative_label},
    )


@lru_cache(maxsize=None)
def _square_multiplier_candidates(lo: int, hi: int, max_prime: int) -> tuple[int, ...]:
    """平方数化の対象数 N の候補列挙。

    残す条件:
      - 素因数が2種類以上・最大素因数が上限以下（中1配当の試し割りで届く範囲）。
      - 平方因数を持つ（指数≥2 の素因数がある）: 持たないと「かける数」が N 自身に
        なり、答えが問題文の数と一致する（G-Q5t の実害）。
      - 平方数でない: 平方数だと「かける数」が 1 に退化する。
      - 素因数分解の表示が NFKC 正規化で連結した数（"2³"→"23"）が N と一致しない
        （G-Q5t の偽陽性回避）。
    """
    out: list[int] = []
    for n in range(lo, hi + 1):
        factors = {int(k): int(v) for k, v in sympy.factorint(n).items()}
        if len(factors) < 2 or max(factors) > max_prime:
            continue
        if all(e % 2 == 0 for e in factors.values()):
            continue
        if not any(e >= 2 for e in factors.values()):
            continue
        tokens = [int(f"{pr}{e}") if e > 1 else pr for pr, e in factors.items()]
        if n in tokens:
            continue
        out.append(n)
    return tuple(out)


def _scene_square_multiplier(p: Mapping[str, Any], rng: Rng) -> SqrtMiscScene:
    lo, hi = (int(v) for v in p["n_range"])
    cands = list(_square_multiplier_candidates(lo, hi, int(p["max_prime"])))
    n = int(draw({"int_set": cands}, rng))
    scenario = (
        f"{n}にできるだけ小さい自然数をかけて、ある自然数の2乗（平方数）にしたい。"
    )
    ask_texts = (
        "まず、この数を素因数分解せよ。",
        "かける数のうち、もっとも小さい自然数を求めよ。",
    )
    return SqrtMiscScene(numbers={"n": n}, scenario=scenario, ask_texts=ask_texts)


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], SqrtMiscScene]] = {
    "square_plot_approx": _scene_square_plot_approx,
    "rectangle_ratio_side": _scene_rectangle_ratio_side,
    "signed_reference": _scene_signed_reference,
    "square_multiplier": _scene_square_multiplier,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_SQRT_MISC_CONCEPTS)
def word_problem_sqrt_misc(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_BUILDERS[kind](p, rng)
    solutions = SOLVE_BUILDERS[kind](scene.numbers, scene.labels)
    assert len(solutions) == len(scene.ask_texts)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})",
            asked="value",
            answer=sol.answer,
            steps=sol.steps,
            concept_tags=concept_tags,
            cause_tags=cause_tags,
        )
        for i, sol in enumerate(solutions)
    ]

    context_slots = dict(scene.slots)
    if len(scene.ask_texts) == 2:
        context_slots["ask_1"] = scene.ask_texts[0]
        context_slots["ask_2"] = scene.ask_texts[1]
    else:
        context_slots["ask_value"] = scene.ask_texts[0]

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 場面文が読者に見せている数値だけ（答えは入れない）。checker はここから
            # solver を呼び直す。
            "scenario_kind": kind,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            # solver に渡す題材語（数値ではない）。
            "labels": dict(scene.labels),
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given={"scenario": scene.scenario},
        context_slots=context_slots,
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "RECIPE_NAME",
    "SOLVE_BUILDERS",
    "SqrtMiscScene",
    "solve_rectangle_ratio_side",
    "solve_signed_reference",
    "solve_square_multiplier",
    "solve_square_plot_approx",
    "word_problem_sqrt_misc",
]
