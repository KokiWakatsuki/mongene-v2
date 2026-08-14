"""関数 y=ax² の利用（form=word_problem・C14 の「y=ax²」クラスタ）。

`word_problem_linear_function.py`（1次関数の利用）と同じ骨格を y=ax² に横展開する
module。数学そのものは既存 solver に委ねる＝**新 solver ゼロ**:

  - `math.evaluate_quadratic_function`（g3_l32.calculation）: y=ax² に x を代入して y。
  - `math.solve_direct_proportion_from_point`（g1_l32.find_value）: 通る1点から比例定数。
    t=x² とみれば「y は t に比例する」so 1点 (x0², y0) から a=y0/x0² が求まる
    ＝この solver がそのまま使える（比例定数を求める算術は solver 側が持つ）。
  - `math.solve_quadratic`（C3 の2次方程式ソルバ・mode=solve_product_form_positive_root）:
    ax²=k を解いて**正の解のみ**を採る（時間・長さの吟味つき）。
  - `math.solve_quadratic_motion_area`（g3_l38.find_value）: 正方形の周上を動く点 P に
    よる三角形 ABP の面積。
  - `math.linear_expr_from_slope_point`（g2_l24）: 傾きと1点から y の式を組み立てる。

## 1つの recipe で4セルを賄う設計

params の `scenario_kind` が (1) 場面の数値を answer-first で引く関数（`_SCENE_BUILDERS`）
と (2) その数値から solver を呼んで解く関数（`SOLVE_BUILDERS`）の対を選ぶ。
`SOLVE_BUILDERS` は recipe と checker が**同じ関数を呼ぶ**（word_problem_probability と
同じ設計）: 独立性は「checker は params の場面文の数値だけから solver を呼び直す」
ところにあり、recipe 側の答えを信用しない。

## 4セルの対応と level_sep（「何を文字に置くか」「手数と概念」を動かす）

  - g3_l32 Lv2 (`given_equation`): 式 y=ax² が**本文で与えられる**。(1) 代入して距離
    （順算） (2) 距離から時刻（ax²=k を解く逆算）。誘導あり2小問・両方 value。
  - g3_l36 Lv2 (`braking_distance`): 式が**与えられない**。(1) 1点から比例定数を決めて
    y を x の式で表す（asked=formulation） (2) その式に代入して値（asked=value）。
    ＝ g3_l32 Lv2 に対して「立式」という段が1つ増える。
  - g3_l36 Lv3 (`free_fall_inverse`): 誘導なし1小問。立式（比例定数の決定）も逆算
    （ax²=k を解く）も**解答の中で自分で構成**する（小問による分割が無い）。
  - g3_l38 Lv3 (`moving_point_area`): 動点。区間で式が変わるので (1)(2) とも
    asked=formulation（0≦x≦t1 と t1≦x≦t2 の2本の式）。文字に置くのは「経過時間」で、
    求めるのは値ではなく**区間ごとの関数そのもの**＝他の3セルと問われるものが違う。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文・小問文が読者に見せている数値（比例定数・秒数・距離・
速さ・正方形の1辺）そのもので、比例定数 a（g3_l36）や答えは入っていない。
checker は同じ `SOLVE_BUILDERS` を通して solver を呼び直し、独立に再計算する。

## narration の語彙

`math.solve_direct_proportion_from_point` / `math.solve_quadratic` /
`math.linear_expr_from_slope_point` の steps は、それぞれ「比例 y=ax」「2次方程式の
因数分解」「傾きと切片」の語彙で書かれており、y=ax² の利用・動点の面積という題材と
ズレる。この3つを使う小問は**合成後の意味に沿って steps をここで組み直す**
（値は result_display にのみ置き、narration には数字を書かない）。
`math.evaluate_quadratic_function` の steps だけは題材とズレないのでそのまま使う。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
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
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_distinct_points

RECIPE_NAME = "math.word_problem_quadratic_function"

_QUADRATIC_FUNCTION_WP_CONCEPTS = [
    "quadratic_function.word_problem_given_equation",
    "quadratic_function.word_problem_determine_then_evaluate",
    "quadratic_function.word_problem_determine_then_inverse",
    "quadratic_function.word_problem_moving_point_area",
]

_X = sympy.Symbol("x")


# ---------------------------------------------------------------------------
# テンプレート
#
# 誘導なし（g3_l36 Lv3）は既存 `wp_linear_solo_v1`（scenario + ask_value）をそのまま
# 使う。誘導ありの3セルは「scenario + quantities（変数の設定）+ (1)(2)」の形で、
# 既存の `wp_linear_guided_v1` は小問スロット名が ask_formulation/ask_value に固定で
# 「(1)(2) とも value」「(1)(2) とも formulation」の並びを表せない。共有ファイル
# （templates/word_problem.py）を触らずに済むよう、word_problem_linear_function.py の
# 前例にならってここで直接 register_template する。
# ---------------------------------------------------------------------------
WP_QUADRATIC_FUNCTION_GUIDED_V1 = (
    "{{ given.scenario }}\n"
    "{{ given.quantities }}\n"
    "(1) {{ context_slots.ask_1 }}\n"
    "(2) {{ context_slots.ask_2 }}"
)
register_template("wp_quadratic_function_guided_v1", WP_QUADRATIC_FUNCTION_GUIDED_V1)


# ---------------------------------------------------------------------------
# 共通ヘルパ
# ---------------------------------------------------------------------------
def _ints(numbers: Mapping[str, Any], *keys: str) -> tuple[int, ...]:
    """params の numbers（checker には文字列で届く）を int にそろえる。

    `sympy.nsimplify(文字列)` は偽の閉形式を返すことがあるため、文字列は必ず int で
    受け直してから sympy に渡す（既知の罠）。
    """
    return tuple(int(str(numbers[k])) for k in keys)


def _format_quadratic_expr(a: sympy.Expr) -> str:
    """y=ax² の表示（分数の比例定数はかっこでくくって係数を確定させる）。"""
    if a == 1:
        return "y = x²"
    if a == -1:
        return "y = -x²"
    if getattr(a, "is_Integer", False):
        return f"y = {a}x²"
    return f"y = ({a})x²"


def _coefficient_from_point(x0: int, y0: int) -> sympy.Rational:
    """「y は x の2乗に比例」の場面で、通る1点 (x0, y0) から比例定数 a=y0/x0² を求める。

    t=x² とおけば「比例 y=at が点 (x0², y0) を通る」ことに等しいので、既存 solver
    `math.solve_direct_proportion_from_point` にそのまま委ねる（新 solver ゼロ）。
    mode は a が整数かどうかで決まる（約分の一手が要るか＝solver 側の level_sep）。
    """
    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    t0 = x0 * x0
    mode = "integer" if y0 % t0 == 0 else "fraction"
    sol = cast(Solution, solver(t0, y0, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    expr = sympy.sympify(sol.answer.srepr)  # a*x（比例の式）
    return cast(sympy.Rational, expr.coeff(_X))


def _formulate_steps(a: sympy.Rational) -> list[Step]:
    """「2乗に比例」から式 y=ax² を決めるまでの手順（narration に数字を書かない）。"""
    expr = a * _X**2
    return [
        Step(
            op="set_up_proportion_equation",
            args=[],
            result_srepr="",
            # この手で得たのは「式の形」。値が入るのは次の手（a を求める）。
            result_display="y = ax²",
            narration=(
                "y は x の2乗に比例するから、比例定数を a とおいて y=ax² と表し、"
                "与えられている x と y の値を代入する。"
            ),
        ),
        Step(
            op="solve_for_coefficient",
            args=[],
            result_srepr=sympy.srepr(a),
            result_display=f"a = {a}",
            narration="代入してできた式を a について解いて、比例定数を求める。",
        ),
        Step(
            op="form_expression",
            args=[],
            result_srepr=sympy.srepr(expr),
            result_display=_format_quadratic_expr(a),
            narration="求めた比例定数を y=ax² にもどして、y を x の式で表す。",
        ),
    ]


def _formulation_solution(a: sympy.Rational) -> Solution:
    """asked=formulation の小問（答えは式 y=ax² そのもの）。"""
    expr = a * _X**2
    return Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(expr), display=_format_quadratic_expr(a)
        ),
        steps=_formulate_steps(a),
    )


def _solve_time_from_distance(
    a: sympy.Rational, target: int, lead_steps: tuple[Step, ...] = ()
) -> Solution:
    """ax²=target を解いて「何秒後か」を求める（正の解のみを採る）。

    solver は `math.solve_quadratic`（mode=solve_product_form_positive_root。
    g3_l30.find_value と共有の既存 mode）。solver の steps は因数分解の語彙なので、
    ここでは「距離の式に値をあてはめる→平方根の考え方で解く→正の解を選ぶ」に
    組み直す（narration に数字を書かない）。
    """
    solver = REGISTRY.solver("math.solve_quadratic")
    sol = cast(Solution, solver(f"({sympy.sstr(a)})*x**2={target}", "solve_product_form_positive_root"))
    assert isinstance(sol.answer, SymbolicAnswer)
    root = sympy.sympify(sol.answer.srepr)
    display = f"{root}秒後"
    steps = [
        *lead_steps,
        Step(
            op="set_up_equation",
            args=[],
            result_srepr="",
            result_display=f"{sympy.sstr(a)}x² = {target}",
            narration="求める時刻を x とみて、距離を表す式に、与えられている距離をあてはめて方程式をつくる。",
        ),
        Step(
            op="solve_for_x",
            args=[],
            result_srepr="",
            result_display=f"x² = {sympy.sstr(sympy.Rational(target) / a)}",
            narration="両辺を x の2乗にかかっている数でわり、平方根の考え方で x を求める。",
        ),
        Step(
            op="select_positive_root",
            args=[],
            result_srepr=sol.answer.srepr,
            result_display=display,
            narration="時刻は正の数だから、求めた解のうち正の解を選ぶ。",
        ),
    ]
    return Solution(
        answer=SymbolicAnswer(srepr=sol.answer.srepr, display=display), steps=steps
    )


# ---------------------------------------------------------------------------
# solve（recipe と checker が共有する「場面の数値 → solver → 答え」の単一の真実）
# ---------------------------------------------------------------------------
def solve_given_equation(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l32 Lv2: y=ax² が与えられる。(1) 代入して距離 (2) 距離から時刻。"""
    a, x0, target = _ints(numbers, "a", "x0", "target")
    evaluate = REGISTRY.solver("math.evaluate_quadratic_function")
    sol_eval = cast(Solution, evaluate(a, x0))
    assert isinstance(sol_eval.answer, SymbolicAnswer)
    distance = sympy.sympify(sol_eval.answer.srepr)
    # steps は既存 solver のまま（「x に代入する」「2乗を計算して比例定数をかける」で
    # 題材とズレない）。単位だけ場面に合わせて付け直す。
    value_sol = Solution(
        answer=SymbolicAnswer(srepr=sol_eval.answer.srepr, display=f"{distance}m"),
        steps=sol_eval.steps,
    )
    time_sol = _solve_time_from_distance(cast(sympy.Rational, sympy.Integer(a)), target)
    return [value_sol, time_sol]


def solve_braking_distance(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l36 Lv2: (1) 1点から比例定数を決めて立式 (2) その式に代入して値。"""
    x0, y0, x1 = _ints(numbers, "x0", "y0", "x1")
    a = _coefficient_from_point(x0, y0)
    form_sol = _formulation_solution(a)
    evaluate = REGISTRY.solver("math.evaluate_quadratic_function")
    sol_eval = cast(Solution, evaluate(a, x1))
    assert isinstance(sol_eval.answer, SymbolicAnswer)
    distance = sympy.sympify(sol_eval.answer.srepr)
    value_sol = Solution(
        answer=SymbolicAnswer(srepr=sol_eval.answer.srepr, display=f"{distance}m"),
        steps=sol_eval.steps,
    )
    return [form_sol, value_sol]


def solve_free_fall_inverse(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l36 Lv3: 誘導なし。立式（比例定数の決定）から逆算まで1小問で構成する。"""
    x0, y0, target = _ints(numbers, "x0", "y0", "target")
    a = _coefficient_from_point(x0, y0)
    return [_solve_time_from_distance(a, target, tuple(_formulate_steps(a)))]


def solve_moving_point_area(numbers: Mapping[str, Any]) -> list[Solution]:
    """g3_l38 Lv3: 正方形 ABCD の周上を B→C→D と動く点 P。区間ごとに y を x の式で表す。

    面積そのものは既存 solver `math.solve_quadratic_motion_area`（A=(0,0), B=(s,0),
    C=(s,s), D=(0,s) に固定し、道のり d から三角形 ABP の面積を返す）に委ねる。
    ここがやるのは「その面積を x（経過時間）の関数として書き直す」ところだけ:

      - 辺BC上（0≦x≦t1）: 面積は道のりに比例し、x=0（P=B）で 0。よって原点を通る
        直線で、傾きは x=1 秒後の面積そのもの（solver に d=v を渡して得る）。
      - 辺CD上（t1≦x≦t2）: 底辺 AB も高さも変わらないので面積は一定。その値は
        solver に区間内の道のり（d=s+v ＝ t1+1 秒後）を渡して得る。

    式そのものの組み立ては既存 solver `math.linear_expr_from_slope_point`（傾きと1点
    →式）に委ねる＝新 solver ゼロ。steps は面積の語彙に組み直す。
    """
    s, v = _ints(numbers, "s", "v")
    t1 = s // v
    area = REGISTRY.solver("math.solve_quadratic_motion_area")
    # x=1 秒後（P は辺BC上）の面積 ＝ 1秒あたりの面積の増え方 ＝ 第1区間の傾き
    sol_probe_1 = cast(Solution, area(s, v, "single_segment"))
    assert isinstance(sol_probe_1.answer, SymbolicAnswer)
    slope = sympy.sympify(sol_probe_1.answer.srepr)
    # x=t1+1 秒後（P は辺CD上・道のり d=s+v）の面積 ＝ 第2区間で一定の面積
    sol_probe_2 = cast(Solution, area(s, s + v, "case_split"))
    assert isinstance(sol_probe_2.answer, SymbolicAnswer)
    constant = sympy.sympify(sol_probe_2.answer.srepr)

    line = REGISTRY.solver("math.linear_expr_from_slope_point")
    sol_first = cast(Solution, line(slope, (0, 0)))
    sol_second = cast(Solution, line(0, (t1, constant)))
    assert isinstance(sol_first.answer, SymbolicAnswer)
    assert isinstance(sol_second.answer, SymbolicAnswer)

    first_steps = [
        Step(
            op="locate_point_p",
            args=[],
            result_srepr="",
            # 点名は場面ごとに振るので、steps は点名に依存しない言い方にする。
            result_display="動いた道のりを x で表す",
            narration="点が最初の辺の上にある間は、速さと経過時間から、動いた道のりを x を使って表す。",
        ),
        Step(
            op="express_area_on_first_side",
            args=[],
            result_srepr=sol_first.answer.srepr,
            result_display=sol_first.answer.display,
            narration=(
                "三角形の底辺を正方形の1つの辺とみると、高さは動いた道のりに等しいから、"
                "面積を x の式で表す。"
            ),
        ),
    ]
    second_steps = [
        Step(
            op="determine_which_segment",
            args=[],
            result_srepr="",
            result_display="次の辺の上",
            narration="点が次の辺の上に移ったあと、三角形の底辺と高さがどうなるかを確かめる。",
        ),
        Step(
            op="express_constant_area",
            args=[],
            result_srepr=sol_second.answer.srepr,
            result_display=sol_second.answer.display,
            narration=(
                "この区間では高さが正方形の1つの辺の長さのまま変わらないので、"
                "面積は x によらず一定の値になる。"
            ),
        ),
    ]
    return [
        Solution(answer=sol_first.answer, steps=first_steps),
        Solution(answer=sol_second.answer, steps=second_steps),
    ]


SOLVE_BUILDERS: dict[str, Callable[[Mapping[str, Any]], list[Solution]]] = {
    "given_equation": solve_given_equation,
    "braking_distance": solve_braking_distance,
    "free_fall_inverse": solve_free_fall_inverse,
    "moving_point_area": solve_moving_point_area,
}

# 小問の asked（family yaml の asked と一致させる。checker は使わない）。
ASKED_KINDS: dict[str, tuple[str, ...]] = {
    "given_equation": ("value", "value"),
    "braking_distance": ("formulation", "value"),
    "free_fall_inverse": ("value",),
    "moving_point_area": ("formulation", "formulation"),
}


# ---------------------------------------------------------------------------
# 場面の抽選（recipe 側のみ。answer-first で候補を列挙してから1つ引く）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuadraticFunctionScene:
    """場面文と、そこから solve に渡す数値。

    `numbers` は `SOLVE_BUILDERS[kind]` にそのまま渡す辞書（params にそのまま載り、
    checker が同じ関数へ渡す）。`quantities` が空文字なら given に載せない
    （誘導なしの1小問セル）。
    """

    numbers: dict[str, Any]
    scenario: str
    quantities: str
    ask_texts: tuple[str, ...]
    slots: dict[str, str]


def _pick(candidates: list[Any], rng: Rng) -> Any:
    if not candidates:
        raise ValueError("候補が空（params の範囲が狭すぎる）")
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _given_equation_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(比例定数 a, 代入する秒数 x0, 求める時刻 t) の候補列挙（answer-first）。

    答えは (1) a·x0²（距離） と (2) t（時刻）。小問文にしか出ない数値（x0・目標距離
    a·t²）は G-Q5t の whitelist（mr.given だけを見る）に載らないので、どちらの答えも
    それらと一致しない組だけを残す（一致すると漏洩の偽陽性で拒否される＝既知の罠）。
    """
    a_cands = [int(v) for v in p["a_candidates"]]
    x_lo, x_hi = (int(v) for v in p["x0_range"])
    t_lo, t_hi = (int(v) for v in p["root_range"])
    out: list[tuple[int, int, int]] = []
    for a in a_cands:
        for x0 in range(x_lo, x_hi + 1):
            for t in range(t_lo, t_hi + 1):
                if t == x0:
                    continue
                target = a * t * t
                distance = a * x0 * x0
                if distance in (x0, target) or t in (x0, target):
                    continue
                out.append((a, x0, t))
    return out


def _scene_given_equation(p: Mapping[str, Any], rng: Rng) -> QuadraticFunctionScene:
    a, x0, t = _pick(_given_equation_candidates(p), rng)
    target = a * t * t
    obj = str(draw(p["object_candidates"], rng))
    scenario = f"ある斜面で{obj}を転がす実験をした。"
    quantities = (
        f"転がり始めてから x 秒間に{obj}が進む距離を y m とすると、"
        f"y = {a}x² の関係が成り立つという。"
    )
    ask_texts = (
        f"{x0}秒間に進む距離を求めよ。",
        f"進んだ距離が{target}mになるのは、転がり始めてから何秒後か求めよ。",
    )
    return QuadraticFunctionScene(
        numbers={"a": a, "x0": x0, "target": target},
        scenario=scenario,
        quantities=quantities,
        ask_texts=ask_texts,
        slots={"object": obj},
    )


def _braking_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(基準の速さ x0, そのときの停止距離 y0, 予測する速さ x1) の候補列挙。

    比例定数が単位分数 1/den になるよう y0 = x0²/den から逆算する（表示 y=(1/den)x²
    が読みやすい）。x1 は x0 の整数倍にとり、停止距離 y1 = k²·y0 が整数になることを
    構成で保証する。y1（答え）は小問文にしか出ない x1 と一致しない組だけ残す
    （G-Q5t の whitelist は mr.given だけを見るため＝既知の罠）。
    """
    speeds = [int(v) for v in p["speed_candidates"]]
    dens = [int(v) for v in p["denominator_candidates"]]
    ratios = [int(v) for v in p["ratio_candidates"]]
    y0_lo, y0_hi = (int(v) for v in p["stop_distance_range"])
    max_speed = int(p["max_speed"])
    out: list[tuple[int, int, int]] = []
    for x0 in speeds:
        for den in dens:
            if (x0 * x0) % den != 0:
                continue
            y0 = x0 * x0 // den
            if not (y0_lo <= y0 <= y0_hi):
                continue
            for k in ratios:
                x1 = k * x0
                if x1 > max_speed:
                    continue
                y1 = k * k * y0
                if y1 in (x0, y0, x1):
                    continue
                out.append((x0, y0, x1))
    return out


def _scene_braking_distance(p: Mapping[str, Any], rng: Rng) -> QuadraticFunctionScene:
    x0, y0, x1 = _pick(_braking_candidates(p), rng)
    vehicle = str(draw(p["vehicle_candidates"], rng))
    scenario = (
        "車がブレーキをかけてから止まるまでに進む距離を停止距離という。"
        f"ある{vehicle}は、速さが{x0}km/hのとき停止距離が{y0}mであった。"
    )
    quantities = "停止距離 y m は、ブレーキをかけたときの速さ x km/h の2乗に比例するものとする。"
    ask_texts = (
        "y を x の式で表せ。",
        f"速さが{x1}km/hのときの停止距離を求めよ。",
    )
    return QuadraticFunctionScene(
        numbers={"x0": x0, "y0": y0, "x1": x1},
        scenario=scenario,
        quantities=quantities,
        ask_texts=ask_texts,
        slots={"vehicle": vehicle},
    )


def _free_fall_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(基準の秒数 x0, そのときの落下距離 y0, 求める時刻 t) の候補列挙（answer-first）。

    落下距離 target = a·t²（a=y0/x0²）が整数になる組だけを残す。答え t は小問文に
    しか出ない target と一致してはならない（G-Q5t の偽陽性＝既知の罠）。

    比例定数 a は `coefficient_candidates` に載っている値だけを許す。落下運動の
    比例定数は現実にはおよそ 5（重力加速度の半分）で、a=1 や a=12 の「1秒で1m しか
    落ちない物体」は場面として不自然になる。y0 を単独の範囲で振ると x0=2 のときに
    そういう組が入るので、a を明示して y0 = a·x0² から逆算する。
    """
    x0_cands = [int(v) for v in p["x0_candidates"]]
    a_cands = [int(v) for v in p["coefficient_candidates"]]
    t_lo, t_hi = (int(v) for v in p["root_range"])
    out: list[tuple[int, int, int]] = []
    for x0 in x0_cands:
        for a in a_cands:
            y0 = a * x0 * x0
            for t in range(t_lo, t_hi + 1):
                if t <= x0:
                    continue
                num = y0 * t * t
                if num % (x0 * x0) != 0:
                    continue
                target = num // (x0 * x0)
                if t in (x0, y0, target) or target in (x0, y0):
                    continue
                out.append((x0, y0, t))
    return out


def _scene_free_fall_inverse(p: Mapping[str, Any], rng: Rng) -> QuadraticFunctionScene:
    """g3_l36 Lv3: 誘導なしの落下運動。落とす物を surface として振る。

    数値の自由度は (x0, a, t) の3軸しかないので、答えに影響しない「落とす物」を
    slots に振って dup を分散させる（初稿は slots が空で実測 dup_rate 0.53）。
    """
    x0, y0, t = _pick(_free_fall_candidates(p), rng)
    target = y0 * t * t // (x0 * x0)
    obj = str(draw(p["object_candidates"], rng))
    scenario = (
        f"高いところから{obj}を静かに落とすとき、落ち始めてから x 秒間に落下する距離 y m は、"
        f"x の2乗に比例する。この{obj}は{x0}秒間に{y0}m落下した。"
    )
    ask_texts = (f"落下距離が{target}mになるのは、落ち始めてから何秒後か求めよ。",)
    return QuadraticFunctionScene(
        numbers={"x0": x0, "y0": y0, "target": target},
        scenario=scenario,
        quantities="",
        ask_texts=ask_texts,
        slots={"object": obj},
    )


def _moving_point_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(正方形の1辺 s, 速さ v) の候補列挙。

    s は偶数（辺CD上の一定面積 s²/2 が整数になる）、v は s の約数（区間の境界
    t1=s/v・t2=2s/v が整数になる）、t1 は `min_first_interval` 以上（辺BC上の区間が
    1秒より十分に長い＝傾きを 1 秒後の面積として取り出せる）。第2区間の答え（一定の
    面積 s²/2）が小問文にしか出ない t1・t2 と一致する組は除く（G-Q5t の偽陽性回避）。
    """
    sides = [int(v) for v in p["side_candidates"]]
    min_t1 = int(p["min_first_interval"])
    out: list[tuple[int, int]] = []
    for s in sides:
        if s % 2 != 0:
            continue
        for v in range(1, s):
            if s % v != 0:
                continue
            t1 = s // v
            if t1 < min_t1:
                continue
            constant = s * s // 2
            if constant in (t1, 2 * t1):
                continue
            out.append((s, v))
    return out


def _scene_moving_point_area(p: Mapping[str, Any], rng: Rng) -> QuadraticFunctionScene:
    """g3_l38 Lv3: 動点。点名を振って surface の variety を確保する。

    振れる数値の自由度は (1辺 s, 速さ v) の組だけで 31 通りしかなく、これだけだと
    実測 dup_rate 0.71（閾値 0.20 の3倍超）だった。点名は答え（y の式）に一切
    影響しない surface なので、正方形の4頂点＋動点の5点を相異なる文字から引いて
    params に入れる（P(16,5)=524160・g3_l31.graph_table と同じ手当て）。
    """
    s, speed = _pick(_moving_point_candidates(p), rng)
    t1, t2 = s // speed, 2 * (s // speed)
    a, b, c, d, pt = _draw_distinct_points(5, rng)
    scenario = (
        f"1辺が{s}cmの正方形{a}{b}{c}{d}がある。点{pt}は頂点{b}を出発し、"
        f"辺{b}{c}、辺{c}{d}の上を毎秒{speed}cmの速さで{d}まで動く。"
    )
    quantities = f"出発してから x 秒後の三角形{a}{b}{pt}の面積を y cm²とする。"
    ask_texts = (
        f"0≦x≦{t1} のとき、y を x の式で表せ。",
        f"{t1}≦x≦{t2} のとき、y を x の式で表せ。",
    )
    return QuadraticFunctionScene(
        numbers={"s": s, "v": speed},
        scenario=scenario,
        quantities=quantities,
        ask_texts=ask_texts,
        slots={"vertices": f"{a}{b}{c}{d}", "moving_point": pt},
    )


_SCENE_BUILDERS: dict[str, Callable[[Mapping[str, Any], Rng], QuadraticFunctionScene]] = {
    "given_equation": _scene_given_equation,
    "braking_distance": _scene_braking_distance,
    "free_fall_inverse": _scene_free_fall_inverse,
    "moving_point_area": _scene_moving_point_area,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_QUADRATIC_FUNCTION_WP_CONCEPTS)
def word_problem_quadratic_function(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_BUILDERS[kind](p, rng)
    solutions = SOLVE_BUILDERS[kind](scene.numbers)
    asked_kinds = ASKED_KINDS[kind]
    assert len(solutions) == len(scene.ask_texts) == len(asked_kinds)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_questions = [
        SubQuestionMR(
            label=f"({i + 1})",
            asked=asked_kinds[i],
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
            # 場面文・小問文が読者に見せている数値だけ（比例定数 a や答えは入れない）。
            # checker はここから solver を呼び直す。
            "scenario_kind": kind,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given=given,
        context_slots=context_slots,
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "ASKED_KINDS",
    "RECIPE_NAME",
    "SOLVE_BUILDERS",
    "QuadraticFunctionScene",
    "solve_braking_distance",
    "solve_free_fall_inverse",
    "solve_given_equation",
    "solve_moving_point_area",
    "word_problem_quadratic_function",
]
