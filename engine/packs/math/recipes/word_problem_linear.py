"""1元1次方程式の利用（form=word_problem・C14 の「1文字」クラスタ）。

`word_problem.py`（連立＝2文字）で通した文章題の骨格を、1文字の方程式の利用に
横展開する module。数学そのものは既存 solver `math.solve_linear_equation`
（sympy.solve）に委ねる＝**新 solver ゼロ**。

## 1つの recipe で6セルを賄う設計

`math.compute_linear_equation` が g1_l21〜l27 の calculation セルを `mode` 1つで
賄っているのと同じ償却をする。ここでは params の `scenario_kind` が

  1. 場面の数値を answer-first で引く関数（`_SCENE_DRAWERS`）
  2. その数値から方程式を組む関数（`FORMULATION_BUILDERS`）

の対を選ぶ。level_sep は「場面の型 × solver の op 列（mode）× 小問数」で作る。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている数値そのもの（単価・総数・合計代金…）
で、答えは入っていない。checker は同じ `FORMULATION_BUILDERS` を通して立式し直し、
solver で解き直す。したがって G-Q1 が突き合わせるのは
「場面文の数値 → 立式 → 解」の連鎖であり、本文の数値と (1) の式のズレ・
(2) の値のズレはどちらも検出される。

## 求める量が x と違う場合（`answer_coeff`）

過不足の応用のように「文字は脚数だが問われるのは人数」という場面がある。
scene が `answer_coeff=(m, n)` を宣言すると、答えは m·x + n になる。checker も
同じ係数で解き直すので、この最後の一手も独立に再計算される。

## 候補トークンの「名前|助数詞」記法

ドメイン記法（§4.3.1）に「対の抽選」は無く、素の文字列配列＝一様選択しかない。
品名と助数詞は必ず対で決まる（ノート＝冊・画用紙＝枚）ので、`"ノート|冊"` の形で
1トークンに畳んで配列に置く。pack ローカルの規約（core は変更しない）。
"""
from __future__ import annotations

import math
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
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many

RECIPE_NAME = "math.word_problem_linear_equation"

_LINEAR_CONCEPTS = [
    "equation.word_problem_price_count",
    "equation.word_problem_price_count_diff",
    "equation.word_problem_surplus_shortage",
    "equation.word_problem_seat_shortage",
    "equation.word_problem_round_trip",
    "equation.word_problem_catch_up",
    "equation.word_problem_proportion_pair",
    "equation.word_problem_continued_ratio",
]

_X = sympy.Symbol("x")


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → 方程式」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LinearFormulation:
    """1元1次方程式の立式結果。

    - `eq`: 答えの機械表現（srepr で G-Q1 が突き合わせる）。sympy は
      `130*(12 - x)` を自動で展開・整理するので srepr は整理後の形になる。
      生徒に見せるのは未整理の `display` 側（式の意味が読める形）。
    - `equation_str`: solver `math.solve_linear_equation` に渡す "lhs=rhs"。
    - `mode`: solver の op 列（＝解き方の手順）。level_sep の一部。
    """

    eq: sympy.Eq
    display: str
    equation_str: str
    mode: str


def _formulate(lhs: str, rhs: str, display: str, mode: str) -> LinearFormulation:
    eq = sympy.Eq(sympy.sympify(lhs, rational=True), sympy.sympify(rhs, rational=True))
    return LinearFormulation(eq=eq, display=display, equation_str=f"{lhs}={rhs}", mode=mode)


def formulate_price_count(*, price_a: int, price_b: int, total: int, cost: int) -> LinearFormulation:
    """pa·x + pb·(k − x) = c（合わせて k 個・合計 c 円）。pa≠pb でないと x が消える。"""
    return _formulate(
        f"{price_a}*x + {price_b}*({total} - x)",
        f"{cost}",
        f"{price_a}x + {price_b}({total} - x) = {cost}",
        "word_linear",
    )


def formulate_price_count_diff(
    *, price_a: int, price_b: int, diff: int, cost: int
) -> LinearFormulation:
    """pa·x + pb·(x + d) = c（B は A より d 個多い）。"""
    return _formulate(
        f"{price_a}*x + {price_b}*(x + {diff})",
        f"{cost}",
        f"{price_a}x + {price_b}(x + {diff}) = {cost}",
        "word_linear",
    )


def formulate_surplus_shortage(
    *, per_a: int, surplus: int, per_b: int, shortage: int
) -> LinearFormulation:
    """a·x + s = b·x − t（同じ総数を2通りに表す＝両辺に文字）。"""
    return _formulate(
        f"{per_a}*x + {surplus}",
        f"{per_b}*x - {shortage}",
        f"{per_a}x + {surplus} = {per_b}x - {shortage}",
        "transpose_both",
    )


def formulate_seat_shortage(
    *, per_a: int, left_out: int, per_b: int, last_seat: int
) -> LinearFormulation:
    """a·x + r = b·(x − 1) + q（最後の1脚だけ q 人でちょうど埋まる）。"""
    return _formulate(
        f"{per_a}*x + {left_out}",
        f"{per_b}*(x - 1) + {last_seat}",
        f"{per_a}x + {left_out} = {per_b}(x - 1) + {last_seat}",
        "word_linear",
    )


def formulate_round_trip(
    *, speed_go: int, speed_back: int, total_time: int
) -> LinearFormulation:
    """x/a + x/b = t（往復の時間の和）。分母をはらってから解く。"""
    return _formulate(
        f"x/{speed_go} + x/{speed_back}",
        f"{total_time}",
        f"x/{speed_go} + x/{speed_back} = {total_time}",
        "clear_denominators_simple",
    )


def formulate_catch_up(
    *, speed_slow: int, head_start: int, speed_fast: int
) -> LinearFormulation:
    """vs·(x + d) = vf·x（先に出た側の道のり＝追いかける側の道のり）。"""
    return _formulate(
        f"{speed_slow}*(x + {head_start})",
        f"{speed_fast}*x",
        f"{speed_slow}(x + {head_start}) = {speed_fast}x",
        "expand_parens",
    )


def formulate_proportion_pair(
    *, count_a: int, price_a: int, count_b: int
) -> LinearFormulation:
    """a:p = b:x（対応する量の比）。表示は比例式・solver に渡すのはたすきがけ後の式。

    g1_l24.calculation と同じ「表示と solver 用の式が別物」の型。
    """
    return _formulate(
        f"{count_a}*x",
        f"{price_a}*{count_b}",
        f"{count_a}:{price_a} = {count_b}:x",
        "cross_multiply",
    )


def formulate_continued_ratio(
    *, ratio_1: int, ratio_2: int, ratio_3: int, total: int
) -> LinearFormulation:
    """r2:(r1+r2+r3) = x:N（連比の1つ分と全体の比）。問うのは真ん中の項。

    連比の各項の和は**場面文には出ていない**（読者が自分でたす数）。だから params は
    3項をそのまま持ち、和はここで導く——こうすると params の数値はすべて場面文に
    現れ、「本文の比を書き違えたら checker が落ちる」経路になる。
    ここが Lv2 との差（Lv2 は本文の2量をそのまま比に並べるだけ）。
    """
    ratio_total = ratio_1 + ratio_2 + ratio_3
    return _formulate(
        f"{ratio_total}*x",
        f"{ratio_2}*{total}",
        f"{ratio_2}:{ratio_total} = x:{total}",
        "cross_multiply",
    )


FORMULATION_BUILDERS: dict[str, Callable[..., LinearFormulation]] = {
    "price_count": formulate_price_count,
    "price_count_diff": formulate_price_count_diff,
    "surplus_shortage": formulate_surplus_shortage,
    "seat_shortage": formulate_seat_shortage,
    "round_trip": formulate_round_trip,
    "catch_up": formulate_catch_up,
    "proportion_pair": formulate_proportion_pair,
    "continued_ratio": formulate_continued_ratio,
}


# ---------------------------------------------------------------------------
# 場面の抽選（answer-first。解 x0 を先に引き、場面の数値を逆算する）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LinearScene:
    """場面文と、そこから立式に渡す数値。

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（params に
    そのまま載り、checker が同じ関数へ渡す）。`answer_coeff=(m, n)` は
    「求める量 = m·x + n」。`answer_unit` は答えの表示に付ける助数詞。
    """

    numbers: dict[str, int]
    scenario: str
    quantities: str
    ask_formulation: str
    ask_value: str
    # 「2通りに表せる量」の名前（立式の着眼点。解説の最初の一手に出す）。
    relation_label: str
    answer_coeff: tuple[int, int]
    answer_unit: str
    slots: dict[str, str]
    # 立式の前に1手要る場面だけが使う（連比の和を出す等）。(op, 表示, narration)。
    # None なら立式は従来どおり2手＝既存セルの steps は変わらない。
    prelude_step: tuple[str, str, str] | None = None


def _split_pair(token: str) -> tuple[str, str]:
    """"ノート|冊" → ("ノート", "冊")。"""
    left, _, right = str(token).partition("|")
    return left, right


def _draw_pair_token(candidates: list[Any], rng: Rng) -> tuple[str, str]:
    return _split_pair(str(draw(list(candidates), rng)))


def _draw_distinct(candidates: list[Any], rng: Rng, k: int) -> list[Any]:
    """候補配列から相異な k 個（文字列はドメイン記法外なので添字で引く）。"""
    idxs = draw_many({"int_range": [0, len(candidates) - 1], "distinct": ["value"]}, rng, k=k)
    return [candidates[int(i)] for i in idxs]


def _scene_price_count(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l25 Lv2: 2種類を合わせて k 個。片方の個数を x とおく。"""
    total = int(draw(p["total_domain"], rng))
    # x0 は 1..k-1（どちらの品も1個以上）。
    count_a = int(draw({"int_range": [2, total - 2]}, rng))
    price_a, price_b = (int(v) for v in draw_many(p["price_domain"], rng, k=2))
    tok_a, tok_b = _draw_distinct(list(p["item_candidates"]), rng, 2)
    item_a, counter = _split_pair(str(tok_a))
    item_b, _ = _split_pair(str(tok_b))
    cost = price_a * count_a + price_b * (total - count_a)
    return LinearScene(
        numbers={"price_a": price_a, "price_b": price_b, "total": total, "cost": cost},
        scenario=(
            f"1{counter}{price_a}円の{item_a}と1{counter}{price_b}円の{item_b}を"
            f"合わせて{total}{counter}買ったところ、代金の合計は{cost}円だった。"
        ),
        quantities=f"{item_a}を買った{counter}数を x {counter}とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{item_a}を買った{counter}数を求めよ。",
        relation_label="代金の合計",
        answer_coeff=(1, 0),
        answer_unit=counter,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter},
    )


def _scene_price_count_diff(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l25 Lv3: B は A より d 個多い（合計個数が与えられない＝読替が要る）。"""
    count_a = int(draw(p["count_domain"], rng))
    diff = int(draw(p["diff_domain"], rng))
    price_a, price_b = (int(v) for v in draw_many(p["price_domain"], rng, k=2))
    tok_a, tok_b = _draw_distinct(list(p["item_candidates"]), rng, 2)
    item_a, counter_a = _split_pair(str(tok_a))
    item_b, counter_b = _split_pair(str(tok_b))
    cost = price_a * count_a + price_b * (count_a + diff)
    return LinearScene(
        numbers={"price_a": price_a, "price_b": price_b, "diff": diff, "cost": cost},
        scenario=(
            f"ある店で、1{counter_a}{price_a}円の{item_a}と1{counter_b}{price_b}円の{item_b}を"
            f"買った。{item_b}は{item_a}より{diff}{counter_b}多く買い、"
            f"代金の合計は{cost}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{item_a}を買った{counter_a}数を求めよ。",
        relation_label="代金の合計",
        answer_coeff=(1, 0),
        answer_unit=counter_a,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter_a},
    )


def _scene_surplus_shortage(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l26 Lv2: a 枚ずつで s 枚余り、b 枚ずつで t 枚足りない。

    非退化: a<b（`step_domain` が正）でないと x が消える。t≥1 は
    t = (b−a)·x0 − s と `surplus_domain` の上限 < `people_domain` の下限で保証する
    （params のコメント参照）。
    """
    people = int(draw(p["people_domain"], rng))
    per_a = int(draw(p["per_domain"], rng))
    per_b = per_a + int(draw(p["step_domain"], rng))
    surplus = int(draw(p["surplus_domain"], rng))
    shortage = (per_b - per_a) * people - surplus
    person, _ = _draw_pair_token(list(p["person_candidates"]), rng)
    obj, obj_counter = _draw_pair_token(list(p["object_candidates"]), rng)
    return LinearScene(
        numbers={
            "per_a": per_a, "surplus": surplus, "per_b": per_b, "shortage": shortage,
        },
        scenario=(
            f"何人かの{person}に{obj}を配る。1人に{per_a}{obj_counter}ずつ配ると"
            f"{surplus}{obj_counter}余り、1人に{per_b}{obj_counter}ずつ配ると"
            f"{shortage}{obj_counter}足りない。"
        ),
        quantities=f"{person}の人数を x 人とする。",
        ask_formulation=(
            f"どちらの配り方でも{obj}の全部の{obj_counter}数は同じであることから、"
            "x についての方程式をつくれ。"
        ),
        ask_value=f"{person}の人数を求めよ。",
        relation_label=f"配る{obj}の全部の{obj_counter}数",
        answer_coeff=(1, 0),
        answer_unit="人",
        slots={"person": person, "object": obj, "counter": obj_counter},
    )


def _scene_seat_shortage(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l26 Lv3: 文字は脚数・問われるのは人数（`answer_coeff` を使う唯一の場面）。

    a 人ずつで r 人あふれ、b=a+1 人ずつだと最後の1脚だけ q 人でちょうど埋まる。
    総人数を2通りに表すと a·x + r = b·(x − 1) + q。r は逆算（r = x0 − a − 1 + q）で、
    params の下限（`seat_domain` の下限 > `per_domain` の上限）から r≥1 が保証される。
    """
    seats = int(draw(p["seat_domain"], rng))
    per_a = int(draw(p["per_domain"], rng))
    per_b = per_a + 1
    last_seat = int(draw({"int_range": [1, per_a]}, rng))
    left_out = seats - per_a - 1 + last_seat
    person, _ = _draw_pair_token(list(p["person_candidates"]), rng)
    return LinearScene(
        numbers={
            "per_a": per_a, "left_out": left_out, "per_b": per_b, "last_seat": last_seat,
        },
        scenario=(
            f"長いすに{person}を座らせる。1脚に{per_a}人ずつ座ると{left_out}人が座れず、"
            f"1脚に{per_b}人ずつ座ると最後の1脚だけ{last_seat}人になり、"
            f"いすはちょうど埋まった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{person}の人数を求めよ。",
        relation_label=f"{person}の全体の人数",
        # 求めるのは人数 = （1脚 a 人）×（脚数 x）＋（座れなかった r 人）。
        answer_coeff=(per_a, left_out),
        answer_unit="人",
        slots={"person": person, "counter": "人"},
    )


def _round_trip_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(行きの速さ, 帰りの速さ, 道のり) の候補列挙。

    t = d·(a+b)/(a·b) が `time_domain` の範囲の整数になる組だけを残す（構成時に
    「時間が整数＝場面として自然」を保証する。g3_l31 と同じ列挙パターン）。
    """
    speeds = [int(v) for v in p["speed_candidates"]]
    t_lo, t_hi = (int(v) for v in p["time_range"])
    d_max = int(p["distance_max"])
    out: list[tuple[int, int, int]] = []
    for a in speeds:
        for b in speeds:
            if a >= b:
                continue
            for d in range(1, d_max + 1):
                t = sympy.Rational(d * (a + b), a * b)
                if t.q == 1 and t_lo <= int(t) <= t_hi:
                    out.append((a, b, d))
    return out


def _scene_round_trip(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l27 Lv2: 行き a・帰り b の速さで往復、時間の和が t。"""
    cands = _round_trip_candidates(p)
    speed_go, speed_back, distance = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    total_time = int(sympy.Rational(distance * (speed_go + speed_back), speed_go * speed_back))
    start, goal = _split_pair(str(draw(list(p["place_candidates"]), rng)))
    return LinearScene(
        numbers={
            "speed_go": speed_go, "speed_back": speed_back, "total_time": total_time,
        },
        scenario=(
            f"{start}から{goal}まで、行きは時速{speed_go}km、帰りは同じ道を"
            f"時速{speed_back}kmの速さで進んだところ、進むのにかかった時間は"
            f"合わせて{total_time}時間だった。"
        ),
        quantities=f"{start}から{goal}までの道のりを x km とする。",
        ask_formulation="かかった時間の関係を、x を使った方程式で表せ。",
        ask_value=f"{start}から{goal}までの道のりを求めよ。",
        relation_label="進むのにかかった時間の合計",
        answer_coeff=(1, 0),
        answer_unit="km",
        slots={"start": start, "goal": goal, "counter": "km"},
    )


def _catch_up_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(遅い側の速さ, 何分後に出発, 追いつくまでの分) の候補列挙。

    速い側は vf = vs·(x0 + d)/x0 で逆算するので、これが `fast_speed_max` 以下の
    整数になる組だけを残す。
    """
    slows = [int(v) for v in p["slow_speed_candidates"]]
    heads = [int(v) for v in p["head_start_candidates"]]
    minutes = [int(v) for v in p["minutes_candidates"]]
    vf_max = int(p["fast_speed_max"])
    vf_min = int(p["fast_speed_min"])
    out: list[tuple[int, int, int]] = []
    for vs in slows:
        for d in heads:
            for x0 in minutes:
                vf = sympy.Rational(vs * (x0 + d), x0)
                # vf > vs（でないと追いつけない）かつ自転車として自然な速さの範囲。
                if vf.q == 1 and vs < int(vf) and vf_min <= int(vf) <= vf_max:
                    out.append((vs, d, x0))
    return out


def _scene_catch_up(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l27 Lv3: 先に出た側を追いかける（追いつくまでの時間を x とおく）。"""
    cands = _catch_up_candidates(p)
    speed_slow, head_start, minutes = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    speed_fast = int(sympy.Rational(speed_slow * (minutes + head_start), minutes))
    first, second = _split_pair(str(draw(list(p["person_pair_candidates"]), rng)))
    return LinearScene(
        numbers={
            "speed_slow": speed_slow, "head_start": head_start, "speed_fast": speed_fast,
        },
        scenario=(
            f"{first}は分速{speed_slow}mで家を出発し、その{head_start}分後に"
            f"{second}が分速{speed_fast}mの自転車で同じ道を追いかけた。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{second}が{first}に追いつくのは、{second}が出発してから何分後か求めよ。",
        relation_label="追いついたときに2人が進んだ道のり",
        answer_coeff=(1, 0),
        answer_unit="分",
        slots={"first": first, "second": second, "counter": "分"},
    )


def _proportion_pair_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(1つあたりの値段, 分かっている個数, 問われている個数) の候補列挙。

    answer-first: 単価 u を先に引き、a 個の値段 p = u·a と答え x = u·b を逆算する
    （割り切れない比例式が出ない）。a ≠ b でないと「同じ数を問う」退化になる。
    答え x が本文の数値（a, p, b）と一致する組は除く（定数答えセルの定石）。
    """
    units = [int(v) for v in p["unit_price_candidates"]]
    counts = [int(v) for v in p["count_candidates"]]
    out: list[tuple[int, int, int]] = []
    for unit in units:
        for count_a in counts:
            for count_b in counts:
                if count_a == count_b:
                    continue
                price_a, answer = unit * count_a, unit * count_b
                if answer in (count_a, price_a, count_b):
                    continue
                out.append((unit, count_a, count_b))
    return out


def _scene_proportion_pair(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l24 Lv2: a 個で p 円のとき b 個はいくらか（誘導あり・比例式を立てる）。"""
    cands = _proportion_pair_candidates(p)
    unit, count_a, count_b = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    item, counter = _draw_pair_token(list(p["item_candidates"]), rng)
    price_a = unit * count_a
    return LinearScene(
        numbers={"count_a": count_a, "price_a": price_a, "count_b": count_b},
        scenario=(
            f"同じ{item}を何{counter}か買う。{item}{count_a}{counter}の値段は{price_a}円である。"
        ),
        quantities=f"{item}{count_b}{counter}の値段を x 円とする。",
        ask_formulation=f"{count_a}{counter}と{count_b}{counter}の値段の比例式をつくれ。",
        ask_value=f"{item}{count_b}{counter}の値段を求めよ。",
        relation_label=f"{counter}数と値段の比",
        answer_coeff=(1, 0),
        answer_unit="円",
        slots={"item": item, "counter": counter},
    )


def _continued_ratio_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(連比の3項, 1つ分の個数) の候補列挙＝(r1, r2, r3, k)。

    問うのは真ん中の項（場面文の色の並び順で2番めのもの）。全体 N = k·(r1+r2+r3)
    が範囲内で、答え x = k·r2 が本文の数値（r1, r2, r3, N）と一致しない組だけ残す。
    連比は**既約**に限る（8:2:6 のような約せる比は教材として出さない）。
    """
    ratios = [int(v) for v in p["ratio_candidates"]]
    units = [int(v) for v in p["unit_candidates"]]
    lo, hi = (int(v) for v in p["total_range"])
    out: list[tuple[int, int, int, int]] = []
    for r1 in ratios:
        for r2 in ratios:
            for r3 in ratios:
                # 3項すべて同じだと比が意味を失う（1:1:1＝ただの等分）。
                if r1 == r2 == r3:
                    continue
                if math.gcd(r1, r2, r3) != 1:
                    continue
                ratio_total = r1 + r2 + r3
                for unit in units:
                    total, answer = unit * ratio_total, unit * r2
                    if not (lo <= total <= hi):
                        continue
                    if answer in (r1, r2, r3, total):
                        continue
                    out.append((r1, r2, r3, unit))
    return out


def _scene_continued_ratio(p: Mapping[str, Any], rng: Rng) -> LinearScene:
    """g1_l24 Lv3: 連比 r1:r2:r3 で全体 N のとき、真ん中の個数を求める（誘導なし）。

    Lv2 と違い、比例式に並べる「全体がいくつ分か」（r1+r2+r3）が本文に無い＝
    自分でたしてから立式する。立式の手数が1つ増えるのを `prelude_step` で表す。
    """
    cands = _continued_ratio_candidates(p)
    r1, r2, r3, unit = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    obj, counter = _draw_pair_token(list(p["object_candidates"]), rng)
    name_1, name_2, name_3 = str(
        draw(list(p["label_triple_candidates"]), rng)
    ).split("|")
    ratio_total = r1 + r2 + r3
    total = unit * ratio_total
    return LinearScene(
        numbers={"ratio_1": r1, "ratio_2": r2, "ratio_3": r3, "total": total},
        scenario=(
            f"{name_1}・{name_2}・{name_3}の{obj}の{counter}数の比は"
            f"{r1}:{r2}:{r3}で、全部で{total}{counter}ある。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{name_2}の{obj}の{counter}数を求めよ。",
        relation_label=f"{name_2}の{counter}数と全体の{counter}数の比",
        answer_coeff=(1, 0),
        answer_unit=counter,
        slots={"object": obj, "counter": counter, "label": name_2},
        prelude_step=(
            "sum_ratio_parts",
            f"全体は{ratio_total}",
            "連比の各項をたして、全体がいくつ分にあたるかを求める。",
        ),
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], LinearScene]] = {
    "price_count": _scene_price_count,
    "price_count_diff": _scene_price_count_diff,
    "surplus_shortage": _scene_surplus_shortage,
    "seat_shortage": _scene_seat_shortage,
    "round_trip": _scene_round_trip,
    "catch_up": _scene_catch_up,
    "proportion_pair": _scene_proportion_pair,
    "continued_ratio": _scene_continued_ratio,
}


# ---------------------------------------------------------------------------
# 求める量（m·x + n）— recipe と checker が共有
# ---------------------------------------------------------------------------
def apply_answer_coeff(x_value: sympy.Expr, coeff: tuple[int, int]) -> sympy.Expr:
    m, n = coeff
    return cast(sympy.Expr, sympy.Integer(m) * x_value + sympy.Integer(n))


def solve_scene(
    kind: str, numbers: Mapping[str, int], coeff: tuple[int, int]
) -> tuple[LinearFormulation, Solution, sympy.Expr]:
    """場面の数値から「立式 → x を解く → 求める量」を1本で通す（checker と共有）。

    x を解くのは既存 solver `math.solve_linear_equation`。最後の m·x+n だけこちらで
    合成する（solver は方程式を解くまでが仕事）。
    """
    formulation = FORMULATION_BUILDERS[kind](**numbers)
    solver = REGISTRY.solver("math.solve_linear_equation")
    sol = cast(Solution, solver(formulation.equation_str, formulation.mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    x_value = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    return formulation, sol, apply_answer_coeff(x_value, coeff)


# ---------------------------------------------------------------------------
# recipe（6セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_LINEAR_CONCEPTS)
def word_problem_linear_equation(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    scene = _SCENE_DRAWERS[kind](p, rng)
    formulation, sol, answer_value = solve_scene(kind, scene.numbers, scene.answer_coeff)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    formulation_steps = _formulation_steps(scene, formulation)
    value_sq = SubQuestionMR(
        label="(2)" if guided else "(1)",
        asked="value",
        answer=SymbolicAnswer(
            srepr=sympy.srepr(answer_value),
            display=f"{answer_value}{scene.answer_unit}",
        ),
        # 誘導なしのセルは (1) が無いので、立式の手順も value 側の模範解答に入れる
        # （でないと「解くところから始まる解説」になる）。誘導ありは (1) が持つ。
        steps=[
            *([] if guided else formulation_steps),
            *sol.steps,
            *_derive_steps(scene, answer_value),
        ],
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )
    sub_questions = [value_sq]
    if guided:
        sub_questions.insert(
            0,
            SubQuestionMR(
                label="(1)",
                asked="formulation",
                answer=SymbolicAnswer(
                    srepr=sympy.srepr(formulation.eq), display=formulation.display
                ),
                steps=formulation_steps,
                concept_tags=concept_tags,
                cause_tags=cause_tags,
            ),
        )

    given = {"scenario": scene.scenario}
    if guided:
        given["quantities"] = scene.quantities

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 場面文が読者に見せている数値だけ（答えは入れない）。checker はここから
            # 立式し直して解き直す。
            "scenario_kind": kind,
            # 誘導の有無（小問数）。checker はこれを見て返す Solution の数を決める
            # ＝MR の形をなぞらずに独立に決める（G-Q1 が数の不一致を検出できる）。
            "guided": guided,
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            "answer_coeff": [str(scene.answer_coeff[0]), str(scene.answer_coeff[1])],
            "answer_unit": scene.answer_unit,
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given=given,
        context_slots={
            **scene.slots,
            "ask_formulation": scene.ask_formulation,
            "ask_value": scene.ask_value,
        },
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


def _formulation_steps(scene: LinearScene, formulation: LinearFormulation) -> list[Step]:
    """(1) 立式の手順。narration には数値を書かない（hints に流れるので G-Q5t 対象）。

    `scene.prelude_step` がある場面（連比）は「立式の前にひと手」を先頭に足す。
    既定は None なので、既存の場面の steps は2手のまま変わらない。
    """
    prelude: list[Step] = []
    if scene.prelude_step is not None:
        op, display, narration = scene.prelude_step
        prelude.append(
            Step(
                op=op,
                args=[],
                result_srepr=sympy.srepr(_X),
                result_display=display,
                narration=narration,
            )
        )
    return [
        *prelude,
        Step(
            op="find_equal_relation",
            args=[],
            result_srepr=sympy.srepr(_X),
            result_display=scene.relation_label,
            narration="場面の中で、どちらの見方でも同じになる（等しくなっている）量に着目する。",
        ),
        Step(
            op="formulate_equation",
            args=[],
            result_srepr=sympy.srepr(formulation.eq),
            result_display=formulation.display,
            narration="その量を x を使って両辺に表し、方程式をつくる。",
        ),
    ]


def _derive_steps(scene: LinearScene, answer_value: sympy.Expr) -> list[Step]:
    """求める量が x と違う場面だけ足す最後の一手（m·x + n）。"""
    if scene.answer_coeff == (1, 0):
        return []
    return [
        Step(
            op="derive_asked_quantity",
            args=[],
            result_srepr=sympy.srepr(answer_value),
            result_display=f"{answer_value}{scene.answer_unit}",
            narration="求めた x をもとに、問われている量を計算する。",
        ),
    ]


__all__ = [
    "FORMULATION_BUILDERS",
    "LinearFormulation",
    "LinearScene",
    "RECIPE_NAME",
    "apply_answer_coeff",
    "solve_scene",
    "word_problem_linear_equation",
]
