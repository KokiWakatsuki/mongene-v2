"""1元1次方程式の利用（form=word_problem・C14 の「1文字」クラスタ）。

`word_problem.py`（連立＝2文字）で通した文章題の骨格を、1文字の方程式の利用に
横展開する module。数学そのものは既存 solver `math.solve_linear_equation`
（sympy.solve）に委ねる＝**新 solver ゼロ**。

## 1つの recipe で6セルを賄う設計

`math.compute_linear_equation` が g1_l21〜l27 の calculation セルを `mode` 1つで
賄っているのと同じ償却をする。ここでは params の `scenario_kind` が

  1. 数を answer-first で引く関数（`RELATION_DRAWERS`）
  2. その数値から方程式を組む関数（`FORMULATION_BUILDERS`）
  3. 引かれた数と語彙から日本語を組む関数（`SCENE_RENDERERS`）

の組を選ぶ。3つは互いを知らない（`draw_scene` が順に呼ぶ）。level_sep は「場面の型 × solver の op 列（mode）× 小問数」で作る。

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
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
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
from engine.packs.math.recipes.scene_vocab import (
    VocabStep,
    draw_vocab,
    split_pair,
)
from engine.packs.math.recipes.scenes import (
    ROLES_DIFF,
    ROLES_GAP,
    ROLES_LESS,
    ROLES_TOTAL,
    SCENES,
    draw_scene_spec,
)

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


def formulate_price_count_gap(
    *, price_a: int, price_b: int, total: int, gap: int
) -> LinearFormulation:
    """pa·x − pb·(k − x) = D（合わせて k 個で、A の代金が B より D 円多い）。

    合わせて k 個という与え方は `formulate_price_count` と同じで、**合計でなく差**を
    与える（作業3 で足した式）。x = (D + pb·k)/(pa + pb) なので pa+pb ≠ 0 で必ず解ける。
    """
    return _formulate(
        f"{price_a}*x - {price_b}*({total} - x)",
        f"{gap}",
        f"{price_a}x - {price_b}({total} - x) = {gap}",
        "word_linear",
    )


def formulate_price_count_less(
    *, price_a: int, price_b: int, diff: int, cost: int
) -> LinearFormulation:
    """pa·x + pb·(x − d) = c（B は A より d 個**少ない**）。

    `formulate_price_count_diff`（d 個多い）の裏（作業3 で足した式）。
    x > d でないと B の個数が 0 以下になるので、関係の側で保証する。
    """
    return _formulate(
        f"{price_a}*x + {price_b}*(x - {diff})",
        f"{cost}",
        f"{price_a}x + {price_b}(x - {diff}) = {cost}",
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
    # 式の軸（`params["form"]`）で選ぶもの。鍵は form の名前（作業3）。
    "price_count_gap": formulate_price_count_gap,
    "price_count_less": formulate_price_count_less,
    "price_count_diff": formulate_price_count_diff,
    "surplus_shortage": formulate_surplus_shortage,
    "seat_shortage": formulate_seat_shortage,
    "round_trip": formulate_round_trip,
    "catch_up": formulate_catch_up,
    "proportion_pair": formulate_proportion_pair,
    "continued_ratio": formulate_continued_ratio,
}


# ---------------------------------------------------------------------------
# 3層に割る（Relation / 語彙の抽選 / Scene）
#
# ## なぜ割るか
# 場面（日本語）と関係（数の引き方）が1つの関数に同居していると、場面を1つ足すたびに
# 数の抽選と非退化条件を書き写すことになり、式の型と場面が1対1に貼りついたままになる。
# 割ると「1つの関係に何通りもの場面を乗せる」ができる（記録 records/docs の charter §3）。
#
# ## 層の境目（この3つは互いを知らない）
#   Relation  数の引き方・非退化条件・答えの逆算。**日本語を1文字も持たない**
#   語彙の抽選 どのカタログからどう引くかの宣言だけ。日本語を書かない
#   Scene     日本語だけ。**数を引かない**（引かれた数と語彙を受け取って文を組む）
#
# ## ★引く順番は変えられない
# 同じ seed から同じ問題が出ることは golden が固定している。層に割るときに
# `draw` の呼ばれる順番が変わると RNG の消費が変わり、**構造だけ変えたつもりで
# 中身も変わる**。この module の8場面はすべて「数 → 語彙」の順に引いていたので、
# 呼び出し側も `_relation_*` → `draw_vocab` → `_scene_*` の順にしてある
# （順番を測った道具: records/work/scan_scene_draw_order.py）。
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LinearRelation:
    """関係（数だけ）。**日本語を持たない。**

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（params に
    そのまま載り、checker が同じ関数へ渡す）。`answer_coeff=(m, n)` は
    「求める量 = m·x + n」で、これも数だけで決まる。
    """

    numbers: dict[str, int]
    answer_coeff: tuple[int, int]


@dataclass(frozen=True)
class LinearScene:
    """場面（日本語だけ）。数は引かず、引かれた数と語彙を受け取って文を組む。

    `answer_unit` は答えの表示に付ける助数詞（日本語なのでここ）。
    `prelude_step` は立式の前に1手要る場面だけが使う（連比の和を出す等）。
    None なら立式は従来どおり2手＝既存セルの steps は変わらない。
    """

    scenario: str
    quantities: str
    ask_formulation: str
    ask_value: str
    # 「2通りに表せる量」の名前（立式の着眼点。解説の最初の一手に出す）。
    relation_label: str
    answer_unit: str
    slots: dict[str, str]
    prelude_step: tuple[str, str, str] | None = None














# ---------------------------------------------------------------------------
# 語彙の抽選（宣言だけ。日本語はここに書かない）
# ---------------------------------------------------------------------------

_SCENE_VOCAB: dict[str, tuple[VocabStep, ...]] = {
    # `"_"` は「`|` で割った並びの都合で出るが使わない」位置。
    "price_count": (
        ("distinct2", "item_candidates", ("item_a", "counter_a", "item_b", "_")),
    ),
    "price_count_diff": (
        ("distinct2", "item_candidates", ("item_a", "counter_a", "item_b", "counter_b")),
    ),
    "surplus_shortage": (
        ("one", "person_candidates", ("person", "_")),
        ("one", "object_candidates", ("object", "object_counter")),
    ),
    "seat_shortage": (
        ("one", "person_candidates", ("person", "_")),
    ),
    "round_trip": (
        ("one", "place_candidates", ("start", "goal")),
    ),
    "catch_up": (
        ("one", "person_pair_candidates", ("first", "second")),
    ),
    "proportion_pair": (
        ("one", "item_candidates", ("item", "counter")),
    ),
    "continued_ratio": (
        ("one", "object_candidates", ("object", "counter")),
        ("one", "label_triple_candidates", ("name_1", "name_2", "name_3")),
    ),
}





# ---------------------------------------------------------------------------
# Relation（数だけ。日本語を1文字も持たない）
# ---------------------------------------------------------------------------
def _draw_rates(
    limits: Mapping[str, Any], p: Mapping[str, Any], rng: Rng
) -> tuple[int, int]:
    """1つあたりの値段を2つ引く。場面が相場を持っていればそれに従う。

    - `rate_pairs`: **(高い|安い) の対を1回で引く**。大人と子どもの料金のように
      2つの値が独立でない場面のため（別々に引くと「大人2500円・中学生2000円」の
      ように差が小さく、区分を分ける意味が無くなる）。並び順は入れ替えて、
      どちらが x になるかを散らす。
    - `rate`: ドメイン記法。相異に2つ引く。
    - どちらも無ければ YAML の既定。
    """
    pairs = limits.get("rate_pairs")
    if pairs:
        tokens = list(pairs)
        high, low = (int(v) for v in split_pair(
            str(tokens[int(draw({"int_range": [0, len(tokens) - 1]}, rng))])
        ))
        return (high, low) if int(draw({"int_range": [0, 1]}, rng)) else (low, high)
    return tuple(  # type: ignore[return-value]
        int(v) for v in draw_many(limits.get("rate", p["price_domain"]), rng, k=2)
    )


def _relation_price_count(
    p: Mapping[str, Any], rng: Rng, limits: Mapping[str, Any] = MappingProxyType({}),
    form: str = "",
) -> LinearRelation:
    """g1_l25 Lv2: 2種類を合わせて k 個。片方の個数を x とおく。

    `limits` は**場面が持っている相場**（入園料は数百円〜千円台、切手は実在する額面）。
    渡されなければ YAML の既定を使う。数の引き方は関係の仕事だが、
    **どの範囲がありえるかは場面が知っている**（`scenes.SceneSpec.limits`）。
    """
    total = int(draw(p["total_domain"], rng))
    # x0 は 1..k-1（どちらの品も1個以上）。
    count_a = int(draw({"int_range": [2, total - 2]}, rng))
    price_a, price_b = _draw_rates(limits, p, rng)
    if form == "price_count_gap":
        # ★差を与える式（pa·x − pb·(k − x) = D）は **D > 0** でないと場面が成り立たない。
        # D > 0 ⟺ x0 > pb·k/(pa+pb) なので、**高いほうを A に置いて**（そうしないと
        # 単価が大きく離れたとき x0 の範囲が空になる）x0 をその範囲から引き直す。
        price_a, price_b = max(price_a, price_b), min(price_a, price_b)
        lo = price_b * total // (price_a + price_b) + 1
        count_a = int(draw({"int_range": [max(2, lo), total - 2]}, rng))
        gap = price_a * count_a - price_b * (total - count_a)
        return LinearRelation(
            numbers={"price_a": price_a, "price_b": price_b,
                     "total": total, "gap": gap},
            answer_coeff=(1, 0),
        )
    cost = price_a * count_a + price_b * (total - count_a)
    return LinearRelation(
        numbers={"price_a": price_a, "price_b": price_b, "total": total, "cost": cost},
        answer_coeff=(1, 0),
    )


def _relation_price_count_diff(
    p: Mapping[str, Any], rng: Rng, limits: Mapping[str, Any] = MappingProxyType({}),
    form: str = "",
) -> LinearRelation:
    """g1_l25 Lv3: B は A より d 個多い（合計個数が与えられない＝読替が要る）。"""
    count_a = int(draw(p["count_domain"], rng))
    diff = int(draw(p["diff_domain"], rng))
    price_a, price_b = _draw_rates(limits, p, rng)
    if form == "price_count_less":
        # ★「d 個少ない」式（pa·x + pb·(x − d) = c）は **x0 > d** でないと B の個数が
        # 0 以下になる。d を x0 より小さい範囲から引き直す（定義域は狭めず、
        # 引く順番で保証する）。
        diff = int(draw({"int_range": [1, count_a - 1]}, rng))
        cost = price_a * count_a + price_b * (count_a - diff)
        return LinearRelation(
            numbers={"price_a": price_a, "price_b": price_b,
                     "diff": diff, "cost": cost},
            answer_coeff=(1, 0),
        )
    cost = price_a * count_a + price_b * (count_a + diff)
    return LinearRelation(
        numbers={"price_a": price_a, "price_b": price_b, "diff": diff, "cost": cost},
        answer_coeff=(1, 0),
    )


def _relation_surplus_shortage(p: Mapping[str, Any], rng: Rng) -> LinearRelation:
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
    return LinearRelation(
        numbers={
            "per_a": per_a, "surplus": surplus, "per_b": per_b, "shortage": shortage,
        },
        answer_coeff=(1, 0),
    )


def _relation_seat_shortage(p: Mapping[str, Any], rng: Rng) -> LinearRelation:
    """g1_l26 Lv3: 文字は脚数・問われるのは人数（`answer_coeff` を使う唯一の関係）。

    a 人ずつで r 人あふれ、b=a+1 人ずつだと最後の1脚だけ q 人でちょうど埋まる。
    総人数を2通りに表すと a·x + r = b·(x − 1) + q。r は逆算（r = x0 − a − 1 + q）で、
    params の下限（`seat_domain` の下限 > `per_domain` の上限）から r≥1 が保証される。
    """
    seats = int(draw(p["seat_domain"], rng))
    per_a = int(draw(p["per_domain"], rng))
    per_b = per_a + 1
    last_seat = int(draw({"int_range": [1, per_a]}, rng))
    left_out = seats - per_a - 1 + last_seat
    return LinearRelation(
        numbers={
            "per_a": per_a, "left_out": left_out, "per_b": per_b, "last_seat": last_seat,
        },
        # 求めるのは人数 = （1脚 a 人）×（脚数 x）＋（座れなかった r 人）。
        answer_coeff=(per_a, left_out),
    )


# 行き先ごとの「ありうる片道の道のり」の上限（km）。
#
# ★**表はここ1つだけ。** 前は往復の平均の速さ（g1_l27 Lv3）の中だけにこの表があり、
# 同じ「家から公園まで」を使う往復の方程式（g1_l27 Lv2）には歯止めが無かった。
# G-WK の読み手が「家から公園まで片道12km・歩いて3時間」を見つけて分かった。
# **同じ規約を2か所に書くと、片方を直しても消えない。**
_PLACE_NEAR = {"家|駅", "学校|図書館", "家|公園", "学校|体育館", "家|市役所",
               "家|スーパー", "学校|駅", "家|図書館", "家|コンビニ", "学校|公園"}
_PLACE_FAR = {"キャンプ場|山頂", "宿|展望台", "町|となり町", "駅|空港",
              "ふもと|山小屋", "港|島", "家|温泉"}


def place_distance_max(start: str, goal: str) -> int:
    """その2地点のあいだにありうる片道の道のり（km）の上限。"""
    key = f"{start}|{goal}"
    return 5 if key in _PLACE_NEAR else (30 if key in _PLACE_FAR else 15)


def _round_trip_candidates(
    p: Mapping[str, Any], d_max_override: int | None = None
) -> list[tuple[int, int, int]]:
    """(行きの速さ, 帰りの速さ, 道のり) の候補列挙。

    t = d·(a+b)/(a·b) が `time_domain` の範囲の整数になる組だけを残す（構成時に
    「時間が整数＝場面として自然」を保証する。g3_l31 と同じ列挙パターン）。
    """
    speeds = [int(v) for v in p["speed_candidates"]]
    t_lo, t_hi = (int(v) for v in p["time_range"])
    d_max = int(p["distance_max"]) if d_max_override is None else d_max_override
    out: list[tuple[int, int, int]] = []
    # **往復の速さの比に上限を置く。** 「行きは時速3km、帰りは時速15km」＝
    # 同じ人が同じ道を5倍の速さで帰る場面はありえない（実物は 2〜3倍まで）。
    ratio_max = float(p.get("speed_ratio_max", 1e9))
    for a in speeds:
        for b in speeds:
            if a >= b or b > ratio_max * a:
                continue
            for d in range(1, d_max + 1):
                t = sympy.Rational(d * (a + b), a * b)
                if t.q == 1 and t_lo <= int(t) <= t_hi:
                    out.append((a, b, d))
    return out


def _relation_round_trip(
    p: Mapping[str, Any], rng: Rng, limits: Mapping[str, Any] | None = None
) -> LinearRelation:
    """g1_l27 Lv2: 行き a・帰り b の速さで往復、時間の和が t。

    `limits["distance_max"]` は**行き先が決めた**片道の上限（`place_distance_max`）。
    ★場面を先に引いてから数を引くのは、入園料が数百円台であるのと同じ理由——
    **語が数の定義域を決める場面が実在する**。
    """
    cands = _round_trip_candidates(p, (limits or {}).get("distance_max"))
    speed_go, speed_back, distance = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    total_time = int(sympy.Rational(distance * (speed_go + speed_back), speed_go * speed_back))
    return LinearRelation(
        numbers={
            "speed_go": speed_go, "speed_back": speed_back, "total_time": total_time,
        },
        answer_coeff=(1, 0),
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
                # **さらに 5m 刻み。** 前は整数でありさえすればよかったので
                # 「分速184mの自転車」「分速165m」「分速175m」のような端数が出ていた。
                # 実物の教材の速さは分速 150m・200m・240m のような区切りのいい数。
                if vf.q == 1 and vs < int(vf) and vf_min <= int(vf) <= vf_max and int(vf) % 5 == 0:
                    out.append((vs, d, x0))
    return out


def _relation_catch_up(p: Mapping[str, Any], rng: Rng) -> LinearRelation:
    """g1_l27 Lv3: 先に出た側を追いかける（追いつくまでの時間を x とおく）。"""
    cands = _catch_up_candidates(p)
    speed_slow, head_start, minutes = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    speed_fast = int(sympy.Rational(speed_slow * (minutes + head_start), minutes))
    return LinearRelation(
        numbers={
            "speed_slow": speed_slow, "head_start": head_start, "speed_fast": speed_fast,
        },
        answer_coeff=(1, 0),
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


def _relation_proportion_pair(p: Mapping[str, Any], rng: Rng) -> LinearRelation:
    """g1_l24 Lv2: a 個で p 円のとき b 個はいくらか（誘導あり・比例式を立てる）。"""
    cands = _proportion_pair_candidates(p)
    unit, count_a, count_b = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    price_a = unit * count_a
    return LinearRelation(
        numbers={"count_a": count_a, "price_a": price_a, "count_b": count_b},
        answer_coeff=(1, 0),
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


def _relation_continued_ratio(p: Mapping[str, Any], rng: Rng) -> LinearRelation:
    """g1_l24 Lv3: 連比 r1:r2:r3 で全体 N のとき、真ん中の個数を求める（誘導なし）。"""
    cands = _continued_ratio_candidates(p)
    r1, r2, r3, unit = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    total = unit * (r1 + r2 + r3)
    return LinearRelation(
        numbers={"ratio_1": r1, "ratio_2": r2, "ratio_3": r3, "total": total},
        answer_coeff=(1, 0),
    )


RELATION_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], LinearRelation]] = {
    "price_count": _relation_price_count,
    "price_count_diff": _relation_price_count_diff,
    "surplus_shortage": _relation_surplus_shortage,
    "seat_shortage": _relation_seat_shortage,
    "round_trip": _relation_round_trip,
    "catch_up": _relation_catch_up,
    "proportion_pair": _relation_proportion_pair,
    "continued_ratio": _relation_continued_ratio,
}


# ---------------------------------------------------------------------------
# Scene（日本語だけ。数は引かない＝この節に `draw` は1つも無い）
#
# 受け取るのは `n`（Relation が引いた数）と `v`（宣言どおりに引かれた語彙）だけ。
# ここに数の抽選や非退化条件を書くと層が混ざる——**書くのは文だけ**。
# ---------------------------------------------------------------------------
def _scene_price_count(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    item_a, item_b, counter = v["item_a"], v["item_b"], v["counter_a"]
    return LinearScene(
        scenario=(
            f"1{counter}{n['price_a']}円の{item_a}と1{counter}{n['price_b']}円の{item_b}を"
            f"合わせて{n['total']}{counter}買ったところ、代金の合計は{n['cost']}円だった。"
        ),
        quantities=f"{item_a}を買った{counter}数を x {counter}とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{item_a}を買った{counter}数を求めよ。",
        relation_label="代金の合計",
        answer_unit=counter,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter},
    )


def _scene_price_count_diff(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    item_a, counter_a = v["item_a"], v["counter_a"]
    item_b, counter_b = v["item_b"], v["counter_b"]
    return LinearScene(
        scenario=(
            f"ある店で、1{counter_a}{n['price_a']}円の{item_a}と"
            f"1{counter_b}{n['price_b']}円の{item_b}を"
            f"買った。{item_b}は{item_a}より{n['diff']}{counter_b}多く買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{item_a}を買った{counter_a}数を求めよ。",
        relation_label="代金の合計",
        answer_unit=counter_a,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter_a},
    )


def _scene_surplus_shortage(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    person, obj, obj_counter = v["person"], v["object"], v["object_counter"]
    return LinearScene(
        scenario=(
            f"何人かの{person}に{obj}を配る。1人に{n['per_a']}{obj_counter}ずつ配ると"
            f"{n['surplus']}{obj_counter}余り、1人に{n['per_b']}{obj_counter}ずつ配ると"
            f"{n['shortage']}{obj_counter}足りない。"
        ),
        quantities=f"{person}の人数を x 人とする。",
        ask_formulation=(
            f"どちらの配り方でも{obj}の全部の{obj_counter}数は同じであることから、"
            "x についての方程式をつくれ。"
        ),
        ask_value=f"{person}の人数を求めよ。",
        relation_label=f"配る{obj}の全部の{obj_counter}数",
        answer_unit="人",
        slots={"person": person, "object": obj, "counter": obj_counter},
    )


def _scene_seat_shortage(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    person = v["person"]
    return LinearScene(
        scenario=(
            f"長いすに{person}を座らせる。1脚に{n['per_a']}人ずつ座ると"
            f"{n['left_out']}人が座れず、"
            f"1脚に{n['per_b']}人ずつ座ると最後の1脚だけ{n['last_seat']}人になり、"
            f"いすはちょうど埋まった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{person}の人数を求めよ。",
        relation_label=f"{person}の全体の人数",
        answer_unit="人",
        slots={"person": person, "counter": "人"},
    )


def _scene_round_trip(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    start, goal = v["start"], v["goal"]
    speed_go, speed_back = n["speed_go"], n["speed_back"]
    return LinearScene(
        scenario=(
            f"{start}から{goal}まで、行きは{_travel_means(speed_go)}時速{speed_go}km、"
            f"帰りは同じ道を{_travel_means(speed_back)}時速{speed_back}kmの速さで"
            f"進んだところ、進むのにかかった時間は合わせて{n['total_time']}時間だった。"
        ),
        quantities=f"{start}から{goal}までの道のりを x km とする。",
        ask_formulation="かかった時間の関係を、x を使った方程式で表せ。",
        ask_value=f"{start}から{goal}までの道のりを求めよ。",
        relation_label="進むのにかかった時間の合計",
        answer_unit="km",
        slots={"start": start, "goal": goal, "counter": "km"},
    )


def _scene_catch_up(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    first, second = v["first"], v["second"]
    return LinearScene(
        scenario=(
            f"{first}は分速{n['speed_slow']}mで家を出発し、その{n['head_start']}分後に"
            f"{second}が分速{n['speed_fast']}mの自転車で同じ道を追いかけた。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{second}が{first}に追いつくのは、{second}が出発してから何分後か求めよ。",
        relation_label="追いついたときに2人が進んだ道のり",
        answer_unit="分",
        slots={"first": first, "second": second, "counter": "分"},
    )


def _scene_proportion_pair(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    item, counter = v["item"], v["counter"]
    count_a, count_b = n["count_a"], n["count_b"]
    return LinearScene(
        scenario=(
            f"同じ{item}を何{counter}か買う。"
            f"{item}{count_a}{counter}の値段は{n['price_a']}円である。"
        ),
        quantities=f"{item}{count_b}{counter}の値段を x 円とする。",
        ask_formulation=f"{count_a}{counter}と{count_b}{counter}の値段の比例式をつくれ。",
        ask_value=f"{item}{count_b}{counter}の値段を求めよ。",
        relation_label=f"{counter}数と値段の比",
        answer_unit="円",
        slots={"item": item, "counter": counter},
    )


def _scene_continued_ratio(n: Mapping[str, int], v: Mapping[str, str]) -> LinearScene:
    """Lv2 と違い、比例式に並べる「全体がいくつ分か」（r1+r2+r3）が本文に無い＝
    自分でたしてから立式する。立式の手数が1つ増えるのを `prelude_step` で表す。
    """
    obj, counter = v["object"], v["counter"]
    name_1, name_2, name_3 = v["name_1"], v["name_2"], v["name_3"]
    r1, r2, r3 = n["ratio_1"], n["ratio_2"], n["ratio_3"]
    return LinearScene(
        scenario=(
            f"{name_1}・{name_2}・{name_3}の{obj}の{counter}数の比は"
            f"{r1}:{r2}:{r3}で、全部で{n['total']}{counter}ある。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{name_2}の{obj}の{counter}数を求めよ。",
        relation_label=f"{name_2}の{counter}数と全体の{counter}数の比",
        answer_unit=counter,
        slots={"object": obj, "counter": counter, "label": name_2},
        prelude_step=(
            "sum_ratio_parts",
            f"全体は{r1 + r2 + r3}",
            "連比の各項をたして、全体がいくつ分にあたるかを求める。",
        ),
    )


SCENE_RENDERERS: dict[str, Callable[[Mapping[str, int], Mapping[str, str]], LinearScene]] = {
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
# G-SC3（骨格）— 関係が場面文に要求する言い方 / 禁じる言い方
#
# 場面を足すときに壊れるのは「日本語だけが違う問題」ではなく、**日本語が関係と
# 食い違う問題**である。実際に7回のセッションを生き延びた欠陥がこれで、
# g3_l37 は「2等分」と書いてあるのに解いているのは等積だった。どのゲートも通る。
#
# ここは**関係の側の不変**を書く（テンプレートの文字づかいではない）。
#   requires: 並びのそれぞれについて、**どれか1つ**が場面文に出ていること
#   forbids : 出ていてはいけない語（別の関係の言い方）
#
# 判定は records/work/check_scene_skeleton.py が全セル×seed で回す。
RELATION_PHRASES: dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]] = {
    # 総数が与えられている（ax + b(N−x) = T）。「1人に…ずつ」は別の関係。
    "price_count": ((("合わせて", "あわせて", "全部で"),), ("ずつ配", "ずつ座")),
    # 総数は同じで**合計でなく差**を与える（ax − b(N−x) = D・作業3 で足した式）。
    "price_count_gap": (
        (("合わせて", "あわせて", "全部で"), ("多かった", "多い")),
        ("ずつ配", "ずつ座"),
    ),
    # 「d 個少ない」（ax + b(x − d) = T・作業3 で足した式）。
    # **「多く」が出たら式が違う。**
    "price_count_less": (
        (("少なく", "少ない"),), ("合わせて", "あわせて", "全部で", "多く"),
    ),
    # 総数は与えず差で与える（ax + b(x+d) = T）。**「合わせて」が出たら関係が違う。**
    "price_count_diff": ((("多く", "多い"),), ("合わせて", "あわせて", "全部で")),
    # 同じ総数を2通りに配る（ax + s = bx − t）。余りと不足の両方が要る。
    "surplus_shortage": (
        (("ずつ配",), ("余り", "あまり"), ("足りない", "たりない")),
        ("合わせて", "あわせて"),
    ),
    # 最後の1脚だけ端数（ax + r = b(x−1) + q）。座れない人が出ることが要る。
    "seat_shortage": ((("ずつ座",), ("座れず", "すわれず")), ("合わせて", "あわせて")),
    # 往復（d/a + d/b = t）。行きと帰りの両方と、時間の合計が要る。
    "round_trip": (
        (("行き",), ("帰り",), ("合わせて", "あわせて", "合計")),
        ("追いかけ", "ずつ配", "ずつ座"),
    ),
    # 追いつき（vs(x+d) = vf·x）。先に出ることと追いかけることが要る。
    "catch_up": ((("分後",), ("追いかけ",)), ("合わせて", "ずつ配", "ずつ座")),
    # 比例式（a:p = b:x）。個数と値段の対応が要る。
    "proportion_pair": ((("値段",),), ("合わせて", "ずつ配", "余り")),
    # 連比（r1:r2:r3 で全体 N）。比と全体の両方が要る。
    "continued_ratio": ((("比は", "比が"), ("全部で", "合わせて")), ("ずつ配", "余り")),
}


# ---------------------------------------------------------------------------
# G-SC5（場面の妥当性）— 引いた数が、場面として成り立つ大きさか
#
# 「式としては解けるが、場面としてありえない」問題が実際に出ていた（斜面432m・
# 円周角231°・歩いて30km）。**これは読解でしか捕まらない**と思われていたが、
# 数の上下限は宣言できる。
#
# ★**わざと二重にする。** 上下限は候補列挙（`*_candidates`）とは別の原理で書く
# ——列挙のほうを緩めたときに、ここが鳴るのが目的である（double-solve と同じ考え）。
# 値は records/work/measure_relation_numbers.py で**実物を数え上げてから**決めた
# （思いつきで書かない。語尾や単位で同じ失敗をしている）。
#
# 判定は records/work/check_scene_plausible.py が全セル×seed で回す。
RELATION_BOUNDS: dict[str, tuple[tuple[str, float, float], ...]] = {
    # 1つあたり × 個数 = 合計。**場面が相場を持つので幅が要る**（買い物は数十円、
    # 入園料は数百円〜千円台、会費は数千円）。上限は「場面としてありえる限界」で、
    # 場面ごとの狭い相場は `scenes.SceneSpec.limits` が持つ（作業3）。
    "price_count": (
        ("price_a", 10, 3500), ("price_b", 10, 3500),
        ("total", 2, 40), ("cost", 20, 50000),
    ),
    "price_count_diff": (
        ("price_a", 10, 5000), ("price_b", 10, 5000),
        ("diff", 1, 20), ("cost", 20, 100000), ("total", 20, 100000),
    ),
    # 作業3 で足した式。差を与えるほうは `gap`（代金の差）が本文に出る。
    # 乗るのは買い物と切手だけ（相場は数十〜数百円）なので、上限はそこに合わせる
    # ——広いままだと実物の10倍以上あって何も言わない宣言になる。
    "price_count_gap": (
        ("price_a", 10, 1000), ("price_b", 10, 1000),
        ("total", 2, 40), ("gap", 1, 5000),
    ),
    "price_count_less": (
        ("price_a", 10, 1000), ("price_b", 10, 1000),
        ("diff", 1, 20), ("cost", 20, 20000),
    ),
    # 配る場面: 1人あたりは1桁、余り・不足は2桁まで（人数は答えなので入らない）。
    "surplus_shortage": (
        ("per_a", 1, 9), ("per_b", 2, 12), ("surplus", 1, 30), ("shortage", 1, 60),
    ),
    "seat_shortage": (
        ("per_a", 1, 9), ("per_b", 2, 10), ("last_seat", 1, 9), ("left_out", 1, 60),
    ),
    # 往復: 時速は徒歩3km〜自動車60km、合計時間は1日に収まる。
    "round_trip": (
        ("speed_go", 1, 60), ("speed_back", 1, 60), ("total_time", 1, 12),
    ),
    # 追いつき: 分速は徒歩50m〜自転車300m、先に出るのは30分まで。
    "catch_up": (
        ("speed_slow", 30, 150), ("speed_fast", 60, 400), ("head_start", 1, 30),
    ),
    # 比例式: 個数は2桁、値段は4桁まで。
    "proportion_pair": (
        ("count_a", 1, 30), ("count_b", 1, 30), ("price_a", 10, 5000),
    ),
    # 連比: 各項は1桁、全体は3桁まで。
    "continued_ratio": (
        ("ratio_1", 1, 9), ("ratio_2", 1, 9), ("ratio_3", 1, 9), ("total", 10, 999),
    ),
}


# ---------------------------------------------------------------------------
# G-SC5b（数と数の関係）— 片方の数だけを見ても分からない条件
#
# ★**上下限だけでは足りない**。G-BT（逆翻訳）で読み手が見つけた欠陥は
# 「毎分12Lで12分で満水（容量144L）の水そうに、25分後の水の量は？」だった。
# どの数も上下限の中に収まっているのに、**数と数の関係**が場面を壊している。
# 見つかった型は機械検査に1つ足す——以後は自動で捕まる（charter §1 段階4）。
#
# 書き方: (左の数, 演算, 右の数)。演算は "<" "<=" "!=" 。
# 名前が無い枝では見ない（`rate1` は反比例の枝にだけある）。
# 判定は records/work/check_scene_plausible.py が回す。
RELATION_ORDER: dict[str, tuple[tuple[str, str, str], ...]] = {
    # 単価が同じだと x が消える（1次方程式として成り立たない）。
    "price_count": (("price_a", "!=", "price_b"),),
    "price_count_diff": (("price_a", "!=", "price_b"),),
    # 1人あたりが増えないと x が消える。
    "surplus_shortage": (("per_a", "<", "per_b"),),
    "seat_shortage": (("per_a", "<", "per_b"), ("last_seat", "<=", "per_a")),
    # 行きより帰りが速い（同じ速さなら往復の意味が無い）。
    "round_trip": (("speed_go", "<", "speed_back"),),
    # 追いかける側が速くないと追いつけない。
    "catch_up": (("speed_slow", "<", "speed_fast"),),
    # 同じ個数を問うと退化する。
    "proportion_pair": (("count_a", "!=", "count_b"),),
    # 差を与える式は「A の代金のほうが多い」＝高いほうを A に置く（そうしないと
    # 差が負になり、場面が成り立たない）。
    "price_count_gap": (("price_b", "<", "price_a"),),
    "price_count_less": (("price_a", "!=", "price_b"),),
}


# ---------------------------------------------------------------------------
# 場面の置き場につなぐ（作業3）
#
# `scenes.py` に置いた場面は**役割の型**で関係に乗る。ここではその対応だけを書く。
# 場面を1つ足すときに触るのは `scenes.py` だけ——この表も式も checker も動かない。
#
#   ax + b(N − x) = T   合わせて N 個      ROLES_TOTAL
#   ax + b(x + d) = T   B は A より d 多い  ROLES_DIFF
#
# 役割の型を持たない関係（配る・往復・追いつき・比例式・連比）は、これまでどおり
# この module の `SCENE_RENDERERS` が書く（場面が1つしかない）。
_RELATION_ROLES: dict[str, tuple[str, ...]] = {
    "price_count": ROLES_TOTAL,
    "price_count_diff": ROLES_DIFF,
}

# 式の軸（作業3）。1つの関係に式が2通り以上あるとき、その名前を並べる。
# 名前は `FORMULATION_BUILDERS` の鍵と同じで、`params["form"]` に載る
# （★載せないと dup_key に効かない）。
_RELATION_FORMS: dict[str, tuple[str, ...]] = {
    "price_count": ("", "price_count_gap"),
    "price_count_diff": ("", "price_count_less"),
}
# 式ごとの役割の型（場面の書き手を選ぶ鍵）。"" は関係の既定。
_FORM_ROLES: dict[str, tuple[str, ...]] = {
    "price_count_gap": ROLES_GAP,
    "price_count_less": ROLES_LESS,
}
# **語彙を先に引く関係**と、引いた語から数の上限を作る関数。
# 語が数の定義域を決める場面が実在する（家から公園まで 12km は成り立たない）。
_VOCAB_FIRST: dict[str, Callable[[Mapping[str, str]], dict[str, Any]]] = {
    "round_trip": lambda v: {
        "distance_max": place_distance_max(v["start"], v["goal"])
    },
}


def draw_scene(
    kind: str,
    p: Mapping[str, Any],
    rng: Rng,
    allow_formulas: Sequence[str] = (),
    allow_scenes: Sequence[str] = (),
) -> tuple[LinearRelation, LinearScene, str, str]:
    """場面選び → 関係 → 語彙 → 場面文 の順に組む。

    **この順番が RNG の消費順を決める。** 場面が数の相場を持っているので、
    場面を先に引く。

    3つめ・4つめの戻り値は場面の名前と式の名前（どちらも params に載る
    ＝`dup_key` の軸になる）。
    """
    roles = _RELATION_ROLES.get(kind)
    if roles is None:
        if kind in _VOCAB_FIRST:
            # **語が数の定義域を決める関係**は、語彙を先に引く（順番が変わる）。
            vocab = draw_vocab(_SCENE_VOCAB.get(kind, ()), p, rng)
            relation = RELATION_DRAWERS[kind](p, rng, _VOCAB_FIRST[kind](vocab))
        else:
            relation = RELATION_DRAWERS[kind](p, rng)
            vocab = draw_vocab(_SCENE_VOCAB.get(kind, ()), p, rng)
        return relation, SCENE_RENDERERS[kind](relation.numbers, vocab), "", ""
    # ★場面を**先に**引く。場面が数の相場を持っているため（入園料に買い物の
    # 40〜160円を使うと「大人1人130円の入園料」になる）。
    # 式を引く（1つの関係に式が2通り以上あるとき）。役割の型が変わるので、
    # 乗れる場面もここで決まる。
    forms = _RELATION_FORMS.get(kind, ("",))
    if allow_formulas:
        # 既定の式（"" ）は `FORMULATION_BUILDERS` の鍵が関係の名前なので、
        # 設計書ではその名前で呼ぶ（`price_count`）。
        forms = tuple(f for f in forms if (f or kind) in allow_formulas)
        if not forms:
            raise ValueError(
                f"設計書が選んだ数式が関係 {kind!r} に無い: {list(allow_formulas)}"
            )
    form = str(draw(list(forms), rng)) if len(forms) > 1 else forms[0]
    if form:
        roles = _FORM_ROLES[form]
    spec = draw_scene_spec(roles, rng, allow_scenes)
    relation = RELATION_DRAWERS[kind](p, rng, spec.limits, form)
    vocab = draw_vocab(spec.vocab, p, rng)
    text = spec.render[roles](relation.numbers, vocab)
    return relation, LinearScene(
        scenario=text.scenario,
        quantities=text.quantities,
        ask_formulation=text.ask_formulation,
        ask_value=text.ask_value,
        relation_label=text.relation_label,
        answer_unit=text.answer_unit,
        slots=dict(text.slots),
    ), spec.id, form


# ---------------------------------------------------------------------------
# 求める量（m·x + n）— recipe と checker が共有
# ---------------------------------------------------------------------------
def apply_answer_coeff(x_value: sympy.Expr, coeff: tuple[int, int]) -> sympy.Expr:
    m, n = coeff
    return cast(sympy.Expr, sympy.Integer(m) * x_value + sympy.Integer(n))


def solve_scene(
    kind: str, numbers: Mapping[str, int], coeff: tuple[int, int], form: str = ""
) -> tuple[LinearFormulation, Solution, sympy.Expr]:
    """場面の数値から「立式 → x を解く → 求める量」を1本で通す（checker と共有）。

    x を解くのは既存 solver `math.solve_linear_equation`。最後の m·x+n だけこちらで
    合成する（solver は方程式を解くまでが仕事）。
    """
    # `form` があればそれで式を選ぶ（1つの関係に式が2通り以上ある＝作業3）。
    formulation = FORMULATION_BUILDERS[form or kind](**numbers)
    solver = REGISTRY.solver("math.solve_linear_equation")
    sol = cast(Solution, solver(formulation.equation_str, formulation.mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    x_value = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    return formulation, sol, apply_answer_coeff(x_value, coeff)


# ---------------------------------------------------------------------------
# recipe（6セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(
    RECIPE_NAME,
    provides_concepts=_LINEAR_CONCEPTS,
    # 棚（設計書の `formulas` / `scenes` が選べる名前）。
    # 数式は `FORMULATION_BUILDERS` の鍵、文型は `SCENES` の id と同じ。
    provides_formulas=sorted(FORMULATION_BUILDERS),
    provides_scenes=[s.id for s in SCENES],
)
def word_problem_linear_equation(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    relation, scene, scene_id, form = draw_scene(
        kind, p, rng, ctx.spec_level.formulas, ctx.spec_level.scenes
    )
    formulation, sol, answer_value = solve_scene(
        kind, relation.numbers, relation.answer_coeff, form
    )

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
            *_derive_steps(scene, relation.answer_coeff, answer_value),
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
            "numbers": {k: str(v) for k, v in relation.numbers.items()},
            "answer_coeff": [
                str(relation.answer_coeff[0]), str(relation.answer_coeff[1]),
            ],
            "answer_unit": scene.answer_unit,
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
            # ★場面の名前も params に載せる。**載せないと場面を5倍にしても
            # dup は1ミリも下がらない**（dup_key は params だけを見る）。
            **({"scene": scene_id} if scene_id else {}),
            **({"form": form} if form else {}),
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


def _derive_steps(scene: LinearScene, answer_coeff: tuple[int, int],
                  answer_value: sympy.Expr) -> list[Step]:
    """求める量が x と違う関係だけ足す最後の一手（m·x + n）。

    `answer_coeff` は Relation が持つ（数だけで決まる）ので、場面から取らずに渡す。
    """
    if answer_coeff == (1, 0):
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


# ---------------------------------------------------------------------------
# g1_l27.word_problem Lv4: 往復の道のりと平均の速さ（誘導なし・融合）
#
# 台帳 Lv4 は「問題をつくれ」＝作問そのものを問う設問で、M0 の答えの型に落ちない。
# 設定は engine が固定し、**誘導なしで2つの量を自分で順に出す**形に落とす。
# 逸脱の理由と「平均の速さだけを問わない理由」は
# solvers/equation.py の `solve_round_trip_average_speed` の docstring を参照。
#
# 共通 recipe（`word_problem_linear_equation`）は「x を解いて m·x+n を答える」型で
# 答えが1つしか返せないため、答えが (道のり, 平均の速さ) の対になるこのセルは
# 独立した recipe にする（6セル共通の枠組みには手を入れない＝Open-Closed）。
# ---------------------------------------------------------------------------
_ROUND_TRIP_AVG_RECIPE = "math.word_problem_round_trip_average_speed"
_ROUND_TRIP_AVG_CONCEPTS = ["equation.word_problem_round_trip_average_speed"]


@register_recipe(_ROUND_TRIP_AVG_RECIPE, provides_concepts=_ROUND_TRIP_AVG_CONCEPTS)
def word_problem_round_trip_average_speed(ctx: CellContext, rng: Rng) -> MR:
    """往復の片道の道のりと平均の速さを求める（g1_l27.word_problem Lv4・誘導なし1小問）。"""
    p = ctx.spec_level.params
    speed_go, speed_back, total_time, start, goal = _draw_round_trip_average_scene(p, rng)

    solver = REGISTRY.solver("math.solve_round_trip_average_speed")
    sol = cast(Solution, solver(speed_go, speed_back, total_time))
    assert isinstance(sol.answer, SymbolicAnswer)
    distance, average = sympy.sympify(sol.answer.srepr)
    # 恒真: 行き・帰りにかかる時間の和が、本文の往復の時間に戻る。
    assert (
        sympy.Rational(distance, speed_go) + sympy.Rational(distance, speed_back) - total_time
    ).equals(0), "往復の時間が本文の値に戻らない"

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 本文に出ている数値だけ（答えの道のり・平均の速さは置かない）。
            "numbers": {
                "speed_go": str(speed_go),
                "speed_back": str(speed_back),
                "total_time": str(total_time),
            },
            "slots": {"start": start, "goal": goal},
        },
        given={
            "scenario": (
                f"{start}から{goal}まで、行きは{_travel_means(speed_go)}時速{speed_go}km、"
                f"帰りは同じ道を{_travel_means(speed_back)}時速{speed_back}kmの速さで"
                f"進んだところ、往復にかかった時間は"
                f"{total_time}時間だった。"
            )
        },
        context_slots={
            "start": start,
            "goal": goal,
            "ask_value": (
                f"{start}から{goal}までの片道の道のりと、往復の平均の速さを求めよ。"
            ),
        },
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked="value",
                answer=sol.answer,
                steps=sol.steps,
                concept_tags=list(
                    ctx.spec_level.concept_tags or ctx.spec_family.concepts_default
                ),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=None,
        provenance=Provenance(recipe=_ROUND_TRIP_AVG_RECIPE),
    )


def _travel_means(speed: int) -> str:
    """時速から移動の手段を決める。

    ★**手段を書かないと場面が壊れる。** 「行きは時速6km、帰りは時速18km」と
    書くと、時速18km（分速300m＝全力走）を歩きのまま続けることになる。
    速さが変わるなら、何で移動したのかを本文に書く。
    """
    if speed <= 6:
        return "歩いて"
    if speed <= 20:
        return "自転車で"
    return "車で"


def _draw_round_trip_average_scene(
    p: Mapping[str, Any], rng: Rng
) -> tuple[int, int, int, str, str]:
    """(行きの速さ, 帰りの速さ, 往復の時間, 出発地, 目的地)。

    【組合せ数】(a, b) は平均の速さ 2ab/(a+b) が整数になる組だけ、往復の時間 t は
    片道の道のりが整数になるものだけを列挙してから引く。地名10通りが乗る。

    【退化と漏洩の封じ方】
      - a == b だと往復が2区間に分かれない（時間の和が x/a + x/a に潰れる）ので除く
      - 答え（片道の道のり・平均の速さ）が本文の数値（速さ2つ・往復の時間）と
        一致する組は外す（本文を読むだけで答えが当たってしまう／G-Q5t の漏洩）
    """
    speeds = [int(v) for v in p["speed_candidates"]]
    t_lo, t_hi = (int(v) for v in p["time_range"])
    cands: list[tuple[int, int, int]] = []
    # **往復の速さの比に上限を置く。** 「行きは時速3km、帰りは時速15km」＝
    # 同じ人が同じ道を5倍の速さで帰る場面はありえない（実物は 2〜3倍まで）。
    ratio_max = float(p.get("speed_ratio_max", 1e9))
    for a in speeds:
        for b in speeds:
            if a >= b or b > ratio_max * a:
                continue
            avg = sympy.Rational(2 * a * b, a + b)
            if avg.q != 1:
                continue  # 平均の速さが整数になる組だけ（場面として自然）
            for t in range(t_lo, t_hi + 1):
                # 片道の道のり d は d/a + d/b = t の解＝t·a·b/(a+b)
                d = sympy.Rational(t * a * b, a + b)
                if d.q != 1:
                    continue
                if {int(d), int(avg)} & {a, b, t}:
                    continue  # 答えが本文の数値と一致する組は外す
                cands.append((a, b, t))
    # **場所に対して道のりがありうる組だけにする。**（表は `place_distance_max`）
    start, goal = split_pair(str(draw(list(p["place_candidates"]), rng)))
    d_max = place_distance_max(start, goal)
    ok = [(a, b, t_) for a, b, t_ in cands
          if int(sympy.Rational(t_ * a * b, a + b)) <= d_max]
    idx = int(draw({"int_set": list(range(len(ok)))}, rng))
    a, b, t = ok[idx]
    return a, b, t, start, goal


__all__ = [
    "FORMULATION_BUILDERS",
    "LinearFormulation",
    "LinearScene",
    "RECIPE_NAME",
    "apply_answer_coeff",
    "solve_scene",
    "word_problem_linear_equation",
    "word_problem_round_trip_average_speed",
]
