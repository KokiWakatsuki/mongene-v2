"""連立方程式の利用（form=word_problem・C14 の「2文字」クラスタ）。

`word_problem_linear.py`（1元1次）で通した骨格を、そのまま2文字＝連立に写した
module。数学そのものは既存 solver `math.intersection_of_two_lines` に委ねる
＝**新 solver ゼロ**（連立 2x2 は「2直線の交点」と同じ計算）。

## 1つの recipe で6セルを賄う設計

`word_problem_linear.py` と同じ償却。params の `scenario_kind` が

  1. 数を answer-first で引く関数（`RELATION_DRAWERS`）
  2. その数値から連立を組む関数（`FORMULATION_BUILDERS`）
  3. 引かれた数と語彙から日本語を組む関数（`SCENE_RENDERERS`）

の組を選ぶ。3つは互いを知らない（`draw_scene` が順に呼ぶ）。賄うのは g2_l17（速さ）・g2_l18（割合）の Lv2/Lv3/Lv4 の6セル。

## g2_l16 の `math.word_problem_price_count` を置き換えない理由

g2_l16 **Lv2** は同じ形をした専用 recipe を持っている（この form の初回縦串）。
あちらをこちらへ寄せると RNG 消費順が変わって golden の再承認が要る＝既存セルの
挙動を触ることになるので、Open-Closed に倣って**別 recipe として足す**。新しい
場面は今後こちらに集める（g2_l16 **Lv3**＝誘導なしの個数と代金は、既存 Lv2 に
触れずにこちらへ `price_count_diff` として足した）。

## level_sep（G6 の構造差）

同じ「連立の利用」でも、レベルごとに**文字を何に置くか**が違う:

  - g2_l17 Lv2: 文字＝道のり → 時間の式が分数係数（x/a + y/b = T）。誘導あり2小問。
  - g2_l17 Lv3: 文字＝時間 → 道のりの式が整数係数（a·x + b·y = D）。しかも問われる
    のは道のり＝解いた x, y から a·x, b·y を作る最後の一手が要る（`answer_map`）。
  - g2_l17 Lv4: 文字＝速さ → 和と差の2式（t1(x+y)=L, t2(x−y)=L）。出会い・追いつき
    という2つの場面を自分で式に翻訳する。
  - g2_l18 Lv2/Lv3/Lv4: 割合。増減（和と差）→ 混合（濃度の重みつき和）→ 濃度その
    ものを未知数に置く（重さが係数に回る）と、割合が式のどこに現れるかが動く。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている数値（速さ・道のり・時間・％・重さ）
そのもので、答えは入っていない。checker は同じ `FORMULATION_BUILDERS` を通して
立式し直し、solver で解き直し、`answer_map` で問われている量まで再計算する。
"""
from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
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
    draw_index,
    draw_vocab,
    split_pair,
)

RECIPE_NAME = "math.word_problem_system_equations"

_SYSTEM_CONCEPTS = [
    "simultaneous_equations.word_problem_price_count_diff",
    "simultaneous_equations.word_problem_distance_time",
    "simultaneous_equations.word_problem_time_split",
    "simultaneous_equations.word_problem_lap_meet_catch_up",
    "simultaneous_equations.word_problem_percent_change",
    "simultaneous_equations.word_problem_salt_mixture",
    "simultaneous_equations.word_problem_two_containers",
]

_X = sympy.Symbol("x")
_Y = sympy.Symbol("y")

# 「求める量 = m·x + n·y + c」の恒等写像（x, y そのものを答える場面）。
IDENTITY_ANSWER_MAP: tuple[tuple[int, int, int], tuple[int, int, int]] = (
    (1, 0, 0),
    (0, 1, 0),
)


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → 連立」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SystemFormulation:
    """連立の立式結果。

    - `eqs`: 答えの機械表現（G-Q1 が srepr で突き合わせる）。sympy は
      `6*(x + y)` を展開するので srepr は整理後の形になる。生徒に見せるのは
      未整理の `display_a` / `display_b` 側（立式の意味が読める形）。
    - `line_a` / `line_b`: solver `math.intersection_of_two_lines` に渡す
      (A, B, C) ＝ A·x + B·y = C。**sympy の数のまま**持つ（文字列にしない）:
      `sympy.nsimplify("1615")` は文字列を近似値として扱って
      `50*2**(314/427)*…` という偽の閉形式を返すことがあり（1〜4000 の整数で36件）、
      解が無理数になって黙って壊れる。params には載せない値なので、文字列化する
      理由もない。
    """

    eqs: sympy.Tuple
    display_a: str
    display_b: str
    line_a: tuple[sympy.Expr, sympy.Expr, sympy.Expr]
    line_b: tuple[sympy.Expr, sympy.Expr, sympy.Expr]
    method: str
    # 2つめの式が「立てたまま」では約せる場面だけ持つ、約したあとの表示。
    # ここがあると立式の手順が1つ増える（`_formulation_steps` が reduce_equation を足す）。
    display_b_reduced: str | None = None

    @property
    def display(self) -> str:
        tail = self.display_b_reduced or self.display_b
        return f"{self.display_a}、{tail}"


def _to_numbers(line: Sequence[Any]) -> tuple[sympy.Expr, sympy.Expr, sympy.Expr]:
    a, b, c = (cast(sympy.Expr, sympy.sympify(v)) for v in line)
    return a, b, c


def _eq_from_line(line: tuple[sympy.Expr, sympy.Expr, sympy.Expr]) -> sympy.Eq:
    a, b, c = line
    return sympy.Eq(a * _X + b * _Y, c)


def _system(
    line_a: Sequence[Any],
    line_b: Sequence[Any],
    display_a: str,
    display_b: str,
    method: str = "elimination",
    display_b_reduced: str | None = None,
) -> SystemFormulation:
    row_a, row_b = _to_numbers(line_a), _to_numbers(line_b)
    return SystemFormulation(
        eqs=sympy.Tuple(_eq_from_line(row_a), _eq_from_line(row_b)),
        display_a=display_a,
        display_b=display_b,
        line_a=row_a,
        line_b=row_b,
        method=method,
        display_b_reduced=display_b_reduced,
    )


def formulate_distance_time(
    *, speed_walk: int, speed_bike: int, distance: int, total_time: int
) -> SystemFormulation:
    """文字＝道のり。x + y = D（道のり）と x/a + y/b = T（時間）。

    非退化: a ≠ b（det = 1/b − 1/a）。歩きと自転車を別の候補列から引くので常に成り立つ。
    """
    return _system(
        (1, 1, distance),
        (sympy.Rational(1, speed_walk), sympy.Rational(1, speed_bike), total_time),
        f"x + y = {distance}",
        f"x/{speed_walk} + y/{speed_bike} = {total_time}",
    )


def formulate_time_split(
    *, speed_slow: int, speed_fast: int, total_time: int, distance: int
) -> SystemFormulation:
    """文字＝時間。x + y = T（時間）と a·x + b·y = D（道のり）。非退化: a ≠ b。"""
    return _system(
        (1, 1, total_time),
        (speed_slow, speed_fast, distance),
        f"x + y = {total_time}",
        f"{speed_slow}x + {speed_fast}y = {distance}",
    )


def formulate_lap_meet_catch_up(
    *, lap: int, meet_time: int, catch_up_time: int
) -> SystemFormulation:
    """文字＝速さ。t1(x+y) = L（反対向き＝和）と t2(x−y) = L（同じ向き＝差）。

    非退化: det = −2·t1·t2 ≠ 0（時間は正なので常に成り立つ）。
    """
    return _system(
        (meet_time, meet_time, lap),
        (catch_up_time, -catch_up_time, lap),
        f"{meet_time}(x + y) = {lap}",
        f"{catch_up_time}(x - y) = {lap}",
    )


def formulate_percent_change(
    *, total: int, rate_up: int, rate_down: int, net_change: int
) -> SystemFormulation:
    """x + y = N（もとの合計）と (p/100)x − (q/100)y = r（増減の差）。

    非退化: det = −(p + q)/100 ≠ 0（％は正なので常に成り立つ）。
    """
    return _system(
        (1, 1, total),
        (sympy.Rational(rate_up, 100), -sympy.Rational(rate_down, 100), net_change),
        f"x + y = {total}",
        f"{rate_up}x/100 - {rate_down}y/100 = {net_change}",
    )


def formulate_salt_mixture(
    *, weight: int, percent_a: int, percent_b: int, percent_mix: int
) -> SystemFormulation:
    """x + y = W（食塩水の重さ）と (a/100)x + (b/100)y = S（食塩の重さ）。

    食塩の重さ S は場面文に出ていない（読者に見えるのは混ぜたあとの濃度 c と重さ W）
    ので、ここで S = c·W/100 として導く。params が持つのは c と W だけになり、
    checker は「本文の c を読み違えていたら落ちる」経路で解き直すことになる。
    非退化: det = (b − a)/100 ≠ 0（濃度を相異に引く）。
    """
    salt = percent_mix * weight // 100
    return _system(
        (1, 1, weight),
        (sympy.Rational(percent_a, 100), sympy.Rational(percent_b, 100), salt),
        f"x + y = {weight}",
        f"{percent_a}x/100 + {percent_b}y/100 = {salt}",
    )


def formulate_two_containers(
    *, weight_a: int, weight_b: int, percent_mix: int, percent_half: int
) -> SystemFormulation:
    """文字＝濃度。(Wa/100)x + (Wb/100)y = S（全部混ぜた食塩）と x + y = 2q。

    ここも params が持つのは場面文に出ている濃度（全部混ぜた c と 100g ずつ混ぜた q）
    だけで、食塩の重さ S = c·(Wa+Wb)/100 と右辺 2q はここで導く。
    2つめは「A から 100g・B から 100g」なので 100x/100 + 100y/100 = q·200/100 と
    立ててから両辺の100を約して x + y = 2q になる。**この「約す」一手を残す**のは
    Lv3（混合）との構造差（fp）にもなるため: 約す前と後の両方を display に持つ。
    非退化: det = (Wa − Wb)/100 ≠ 0（重さを相異に引く）。
    """
    salt_all = percent_mix * (weight_a + weight_b) // 100
    percent_sum = 2 * percent_half
    return _system(
        (sympy.Rational(weight_a, 100), sympy.Rational(weight_b, 100), salt_all),
        (1, 1, percent_sum),
        f"{weight_a}x/100 + {weight_b}y/100 = {salt_all}",
        f"100x/100 + 100y/100 = {percent_half}×200/100",
        display_b_reduced=f"x + y = {percent_sum}",
    )


def formulate_price_count_diff(
    *, price_a: int, price_b: int, diff: int, total: int
) -> SystemFormulation:
    """g2_l16 Lv3（誘導なし）。文字＝個数。y − x = d（本数の差）と pa·x + pb·y = T（代金）。

    g2_l16 Lv2（`math.word_problem_price_count`）は「合計個数」が与えられる場面で
    x + y = N と立つのに対し、こちらは合計個数が与えられず「一方が d 個多い」という
    **差**の読替を経て y − x = d を自分で立てる（＝台帳 Lv3 desc「単位や条件の読替を
    経て自分で立式する」）。非退化: det = −(pa + pb) ≠ 0（単価は正）。
    """
    return _system(
        (-1, 1, diff),
        (price_a, price_b, total),
        f"y = x + {diff}",
        f"{price_a}x + {price_b}y = {total}",
    )


FORMULATION_BUILDERS: dict[str, Callable[..., SystemFormulation]] = {
    "price_count_diff": formulate_price_count_diff,
    "distance_time": formulate_distance_time,
    "time_split": formulate_time_split,
    "lap_meet_catch_up": formulate_lap_meet_catch_up,
    "percent_change": formulate_percent_change,
    "salt_mixture": formulate_salt_mixture,
    "two_containers": formulate_two_containers,
}


# ---------------------------------------------------------------------------
# 3層に割る（Relation / 語彙の抽選 / Scene）
#
# 割り方と理由は word_problem_linear.py の同じ節に書いてある（charter §3）。
#
#   Relation  数の引き方・非退化条件・答えの取り出し方（`answer_map`）
#             日本語を出力に流さない
#   語彙の抽選 どのカタログからどう引くかの宣言だけ（`scene_vocab.draw_vocab`）
#   Scene     引かれた数と語彙から日本語を組む。`rng` を受け取らない
#
# ## ★この module には引く順番の例外が1つある
# `price_count_diff` だけは**語彙を先に引いている**（品物の対 → 単価 → 個数 → 差）。
# 他の6つは「数 → 語彙」。同じ seed から同じ問題が出ることは golden が固定している
# ので、例外はそのまま残す（`_VOCAB_FIRST`）。新しい場面は「数 → 語彙」で書く。
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SystemRelation:
    """関係（数だけ）。**日本語を持たない。**

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（params に
    そのまま載り、checker が同じ関数へ渡す）。`answer_map` は「求める量 =
    m·x + n·y + c」を2つ分で、これも数だけで決まる。
    """

    numbers: dict[str, int]
    answer_map: tuple[tuple[int, int, int], tuple[int, int, int]]


@dataclass(frozen=True)
class SystemScene:
    """場面（日本語だけ）。数は引かず、引かれた数と語彙を受け取って文を組む。"""

    scenario: str
    # 誘導ありのときだけ本文に出す変数の設定（誘導なしは空文字）。
    quantities: str
    # 模範解答の第一手（値を含めない。hints に流れるので G-Q5t 対象）。
    variables_narration: str
    ask_formulation: str
    ask_value: str
    # 2つの式それぞれの着眼点（narration に使う＝値を含めない）。
    relation_labels: tuple[str, str]
    answer_labels: tuple[str, str]
    answer_units: tuple[str, str]
    slots: dict[str, str]


# ---------------------------------------------------------------------------
# 語彙の抽選（宣言だけ。日本語はここに書かない）
# ---------------------------------------------------------------------------
_SCENE_VOCAB: dict[str, tuple[VocabStep, ...]] = {
    "price_count_diff": (
        ("index", "item_pair_candidates", ("item_a", "counter_a", "item_b", "counter_b")),
    ),
    "distance_time": (
        ("index", "place_triple_candidates", ("place_a", "place_b", "place_c")),
    ),
    "time_split": (
        ("index", "place_candidates", ("start", "goal")),
    ),
    "lap_meet_catch_up": (
        ("index", "person_pair_candidates", ("name_fast", "name_slow")),
    ),
    # 割合の3場面は語彙を引かない（登場するのは生徒数・食塩水・容器 A/B だけ）。
    "percent_change": (),
    "salt_mixture": (),
    "two_containers": (),
}

# ★語彙を先に引く場面（割る前のコードの順番をそのまま残すためだけの宣言）。
_VOCAB_FIRST = frozenset({"price_count_diff"})


# ---------------------------------------------------------------------------
# Relation（数だけ。日本語を1文字も持たない）
# ---------------------------------------------------------------------------
def _relation_price_count_diff(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l16 Lv3: 個数と代金（合計個数は与えず「一方が d 個多い」で与える・誘導なし）。

    answer-first: 少ないほうの個数 a と差 d を先に引き、多いほうを a+d、合計代金を
    逆算する（端数の出ない綺麗な設定になる）。単価は相異に引く（同じでも det は
    0 にならないが、「2種類の品物」の場面として不自然なため）。
    """
    price_a, price_b = (
        int(v) for v in draw_many(p["price_domain"], rng, k=2)
    )
    count_a = int(draw(p["count_domain"], rng))
    diff = int(draw(p["diff_domain"], rng))
    total = price_a * count_a + price_b * (count_a + diff)
    return SystemRelation(
        numbers={
            "price_a": price_a,
            "price_b": price_b,
            "diff": diff,
            "total": total,
        },
        answer_map=IDENTITY_ANSWER_MAP,
    )


def _distance_time_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(歩きの速さ, 自転車の速さ, 歩いた時間, 自転車の時間) の候補列挙。

    区間ごとの時間を整数で持つので合計時間は自動で整数になる（分数係数でも端数が
    出ない）。そのうえで区間ごとの道のりに上限をかける——式としては解けても、
    「歩いて30km」のような場面は生徒が読む文章として成り立たないため。
    """
    walks = [int(v) for v in p["walk_speed_candidates"]]
    bikes = [int(v) for v in p["bike_speed_candidates"]]
    hour_lo, hour_hi = (int(v) for v in p["hours_range"])
    walk_max = int(p["walk_distance_max"])
    bike_max = int(p["bike_distance_max"])
    out: list[tuple[int, int, int, int]] = []
    for speed_walk in walks:
        for hours_walk in range(hour_lo, hour_hi + 1):
            if speed_walk * hours_walk > walk_max:
                continue
            for speed_bike in bikes:
                for hours_bike in range(hour_lo, hour_hi + 1):
                    if speed_bike * hours_bike > bike_max:
                        continue
                    out.append((speed_walk, speed_bike, hours_walk, hours_bike))
    return out


def _relation_distance_time(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l17 Lv2: 歩いた区間と走った区間。文字は道のり（時間の式が分数係数）。

    区間ごとの道のりは場面文に出す（`dist_walk` / `dist_bike`）ので、合計と一緒に
    numbers へ入れる——場面は数を引かないので、必要な数はここで全部そろえる。
    """
    cands = _distance_time_candidates(p)
    speed_walk, speed_bike, hours_walk, hours_bike = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    dist_walk = speed_walk * hours_walk
    dist_bike = speed_bike * hours_bike
    return SystemRelation(
        numbers={
            "speed_walk": speed_walk,
            "speed_bike": speed_bike,
            "distance": dist_walk + dist_bike,
            "total_time": hours_walk + hours_bike,
        },
        answer_map=IDENTITY_ANSWER_MAP,
    )


def _relation_time_split(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l17 Lv3: 途中から走る。文字は**時間**で、問われるのは**道のり**。

    文字を時間に置くと道のりの式が整数係数になり、答えを出すには最後に a·x, b·y を
    作る一手が要る（`answer_map`）。Lv2 と「何を文字に置くか」が逆になる＝構造差。

    歩きと走りで時間の範囲を分けているのは場面の自然さのため（「途中から走る」区間が
    歩いた区間より長いと通学の場面として読めない）。分速×分なので端数は出ない。
    """
    speed_walk = int(draw_index(list(p["walk_speed_candidates"]), rng))
    speed_run = int(draw_index(list(p["run_speed_candidates"]), rng))
    minutes_walk = int(draw(p["walk_minutes_domain"], rng))
    minutes_run = int(draw(p["run_minutes_domain"], rng))
    distance = speed_walk * minutes_walk + speed_run * minutes_run
    return SystemRelation(
        numbers={
            "speed_slow": speed_walk,
            "speed_fast": speed_run,
            "total_time": minutes_walk + minutes_run,
            "distance": distance,
        },
        # 求めるのは道のり＝（速さ）×（時間）。x, y そのものではない。
        answer_map=((speed_walk, 0, 0), (0, speed_run, 0)),
    )


def _lap_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(速い人の分速, 遅い人の分速, 1周の長さ) の候補列挙。

    反対向き（和）で t1 = L/(x+y) 分、同じ向き（差）で t2 = L/(x−y) 分。どちらも
    整数かつ自然な範囲に入る組だけを残す（構成時に場面の自然さを保証する）。
    """
    speeds = [int(v) for v in p["speed_candidates"]]
    laps = [int(v) for v in p["lap_candidates"]]
    meet_lo, meet_hi = (int(v) for v in p["meet_time_range"])
    catch_lo, catch_hi = (int(v) for v in p["catch_up_time_range"])
    out: list[tuple[int, int, int]] = []
    for fast in speeds:
        for slow in speeds:
            if fast <= slow:
                continue
            total, diff = fast + slow, fast - slow
            for lap in laps:
                if lap % total or lap % diff:
                    continue
                meet, catch = lap // total, lap // diff
                if not (meet_lo <= meet <= meet_hi and catch_lo <= catch <= catch_hi):
                    continue
                # 追いつくほうが必ず遅い（差 < 和）＝場面として自然。
                if catch <= meet:
                    continue
                out.append((fast, slow, lap))
    return out


def _relation_lap_meet_catch_up(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l17 Lv4: 池のまわりの出会いと追いつき。文字は速さ（和と差の2式）。"""
    cands = _lap_candidates(p)
    fast, slow, lap = cands[int(draw({"int_range": [0, len(cands) - 1]}, rng))]
    meet_time, catch_up_time = lap // (fast + slow), lap // (fast - slow)
    return SystemRelation(
        numbers={"lap": lap, "meet_time": meet_time, "catch_up_time": catch_up_time},
        answer_map=IDENTITY_ANSWER_MAP,
    )


def _percent_change_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(男子, 女子, 増加率, 減少率) の候補列挙。

    増えた人数 p·x/100・減った人数 q·y/100 がどちらも整数（人数が端数にならない）で、
    差 r = p·x/100 − q·y/100 が正の整数になる組だけを残す。
    """
    counts = [int(v) for v in p["count_candidates"]]
    ups = [int(v) for v in p["rate_up_candidates"]]
    downs = [int(v) for v in p["rate_down_candidates"]]
    net_max = int(p["net_change_max"])
    out: list[tuple[int, int, int, int]] = []
    for boys in counts:
        for girls in counts:
            for up in ups:
                if (up * boys) % 100:
                    continue
                for down in downs:
                    if (down * girls) % 100:
                        continue
                    net = up * boys // 100 - down * girls // 100
                    if 1 <= net <= net_max:
                        out.append((boys, girls, up, down))
    return out


def _relation_percent_change(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l18 Lv2: 男子が p% 増え女子が q% 減って全体で r 人増えた（誘導あり）。"""
    cands = _percent_change_candidates(p)
    boys, girls, rate_up, rate_down = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    net_change = rate_up * boys // 100 - rate_down * girls // 100
    return SystemRelation(
        numbers={
            "total": boys + girls,
            "rate_up": rate_up,
            "rate_down": rate_down,
            "net_change": net_change,
        },
        answer_map=IDENTITY_ANSWER_MAP,
    )


def _salt_mixture_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(薄い濃度, 濃い濃度, 薄いほうの重さ, 濃いほうの重さ) の候補列挙。

    混ぜたあとの濃度 c = (a·x + b·y)/(x + y) が整数で、食塩の重さ (a·x + b·y)/100 も
    整数になる組だけを残す（％も g も端数が出ない）。a < c < b は加重平均だから自動。
    """
    percents = [int(v) for v in p["percent_candidates"]]
    weights = [int(v) for v in p["weight_candidates"]]
    out: list[tuple[int, int, int, int]] = []
    for lo in percents:
        for hi in percents:
            if lo >= hi:
                continue
            for wa in weights:
                for wb in weights:
                    salt100 = lo * wa + hi * wb
                    if salt100 % (wa + wb) or salt100 % 100:
                        continue
                    out.append((lo, hi, wa, wb))
    return out


def _relation_salt_mixture(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l18 Lv3: a% と b% を混ぜて c% を W g つくる（誘導なし）。"""
    cands = _salt_mixture_candidates(p)
    percent_a, percent_b, weight_a, weight_b = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    weight = weight_a + weight_b
    salt100 = percent_a * weight_a + percent_b * weight_b
    percent_mix = salt100 // weight
    return SystemRelation(
        numbers={
            "weight": weight,
            "percent_a": percent_a,
            "percent_b": percent_b,
            "percent_mix": percent_mix,
        },
        answer_map=IDENTITY_ANSWER_MAP,
    )


def _two_containers_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int, int]]:
    """(容器Aの重さ, 容器Bの重さ, Aの濃度, Bの濃度) の候補列挙。

    全部混ぜた濃度 p = (Wa·a + Wb·b)/(Wa + Wb) と、100g ずつ混ぜた濃度
    q = (a + b)/2 がどちらも整数で、食塩の重さ p·(Wa+Wb)/100 も整数になる組だけ。
    """
    weights = [int(v) for v in p["weight_candidates"]]
    lo, hi = (int(v) for v in p["percent_range"])
    out: list[tuple[int, int, int, int]] = []
    for wa in weights:
        for wb in weights:
            if wa == wb:  # det = (Wa − Wb)/100 が 0 になる
                continue
            for pa in range(lo, hi + 1):
                for pb in range(lo, hi + 1):
                    if pa == pb or (pa + pb) % 2:
                        continue
                    salt100 = wa * pa + wb * pb
                    if salt100 % (wa + wb) or salt100 % 100:
                        continue
                    out.append((wa, wb, pa, pb))
    return out


def _relation_two_containers(p: Mapping[str, Any], rng: Rng) -> SystemRelation:
    """g2_l18 Lv4: 濃度そのものを未知数に置く（重さが係数に回る・誘導なし）。"""
    cands = _two_containers_candidates(p)
    weight_a, weight_b, percent_a, percent_b = cands[
        int(draw({"int_range": [0, len(cands) - 1]}, rng))
    ]
    percent_mix = (weight_a * percent_a + weight_b * percent_b) // (weight_a + weight_b)
    percent_half = (percent_a + percent_b) // 2
    return SystemRelation(
        numbers={
            "weight_a": weight_a,
            "weight_b": weight_b,
            "percent_mix": percent_mix,
            "percent_half": percent_half,
        },
        answer_map=IDENTITY_ANSWER_MAP,
    )


RELATION_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], SystemRelation]] = {
    "price_count_diff": _relation_price_count_diff,
    "distance_time": _relation_distance_time,
    "time_split": _relation_time_split,
    "lap_meet_catch_up": _relation_lap_meet_catch_up,
    "percent_change": _relation_percent_change,
    "salt_mixture": _relation_salt_mixture,
    "two_containers": _relation_two_containers,
}


# ---------------------------------------------------------------------------
# Scene（日本語だけ。数は引かない＝この節に抽選は1つも無い）
# ---------------------------------------------------------------------------
def _scene_price_count_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    item_a, counter_a = v["item_a"], v["counter_a"]
    item_b, counter_b = v["item_b"], v["counter_b"]
    return SystemScene(
        scenario=(
            f"{item_a}を何{counter_a}かと{item_b}を何{counter_b}か買った。"
            f"{item_a}1{counter_a}は{n['price_a']}円、"
            f"{item_b}1{counter_b}は{n['price_b']}円で、"
            f"買った数は{item_a}より{item_b}のほうが{n['diff']}{counter_b}多く、"
            f"代金の合計は{n['total']}円だった。"
        ),
        quantities="",
        variables_narration=(
            f"{item_a}の数を x {counter_a}、{item_b}の数を y {counter_b}とおく。"
        ),
        ask_formulation="",
        ask_value=f"{item_a}と{item_b}を買った数をそれぞれ求めよ。",
        relation_labels=("買った数の関係", "代金の合計の関係"),
        answer_labels=(f"{item_a}は", f"{item_b}は"),
        answer_units=(counter_a, counter_b),
        slots={"item_a": item_a, "item_b": item_b},
    )


def _scene_distance_time(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    place_a, place_b, place_c = v["place_a"], v["place_b"], v["place_c"]
    return SystemScene(
        scenario=(
            f"{place_a}から{place_b}を通って{place_c}まで行った。"
            f"{place_a}から{place_b}までは時速{n['speed_walk']}kmで歩き、"
            f"{place_b}から{place_c}までは時速{n['speed_bike']}kmの自転車で"
            f"進んだところ、"
            f"全体で{n['distance']}km進むのに{n['total_time']}時間かかった。"
        ),
        quantities="歩いた道のりを x km、自転車で進んだ道のりを y km とする。",
        variables_narration="歩いた道のりを x km、自転車で進んだ道のりを y km とおく。",
        ask_formulation="道のりと時間の関係を表す2つの式をつくれ。",
        ask_value="歩いた道のりと自転車で進んだ道のりをそれぞれ求めよ。",
        relation_labels=("道のりの関係", "かかった時間の関係"),
        answer_labels=("歩いた道のりは", "自転車で進んだ道のりは"),
        answer_units=("km", "km"),
        slots={"place_a": place_a, "place_b": place_b, "place_c": place_c},
    )


def _scene_time_split(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    start, goal = v["start"], v["goal"]
    return SystemScene(
        scenario=(
            f"{start}から{goal}まで行くのに、初めは分速{n['speed_slow']}mで歩き、"
            f"途中から分速{n['speed_fast']}mで走ったところ、{start}から{goal}まで"
            f"{n['distance']}mの道のりを{n['total_time']}分で着いた。"
        ),
        quantities="",
        variables_narration="歩いた時間を x 分、走った時間を y 分とおく。",
        ask_formulation="",
        ask_value="歩いた道のりと走った道のりはそれぞれ何mか求めよ。",
        relation_labels=("かかった時間の関係", "道のりの関係"),
        answer_labels=("歩いた道のりは", "走った道のりは"),
        answer_units=("m", "m"),
        slots={"start": start, "goal": goal},
    )


def _scene_lap_meet_catch_up(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    name_fast, name_slow = v["name_fast"], v["name_slow"]
    return SystemScene(
        scenario=(
            f"1周{n['lap']}mの池のまわりを、{name_fast}と{name_slow}が同じ地点から"
            f"同時に出発する。反対向きに進むと{n['meet_time']}分後に出会い、"
            f"同じ向きに進むと{name_fast}が{name_slow}に"
            f"{n['catch_up_time']}分後に追いつく。"
        ),
        quantities="",
        variables_narration=(
            f"{name_fast}の速さを分速 x m、{name_slow}の速さを分速 y m とおく。"
        ),
        ask_formulation="",
        ask_value=f"{name_fast}と{name_slow}の速さはそれぞれ分速何mか求めよ。",
        relation_labels=("反対向きに進んだときの道のりの関係", "同じ向きに進んだときの道のりの関係"),
        answer_labels=(f"{name_fast}の速さは分速", f"{name_slow}の速さは分速"),
        answer_units=("m", "m"),
        slots={"name_fast": name_fast, "name_slow": name_slow},
    )


def _scene_percent_change(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    return SystemScene(
        scenario=(
            f"ある中学校の昨年の生徒数は男女合わせて{n['total']}人だった。"
            f"今年は昨年に比べて男子が{n['rate_up']}%増え、"
            f"女子が{n['rate_down']}%減ったので、"
            f"全体で{n['net_change']}人増えた。"
        ),
        quantities="昨年の男子の人数を x 人、女子の人数を y 人とする。",
        variables_narration="昨年の男子の人数を x 人、女子の人数を y 人とおく。",
        ask_formulation="人数と増減の関係を表す2つの式をつくれ。",
        ask_value="昨年の男子と女子の人数をそれぞれ求めよ。",
        relation_labels=("昨年の人数の関係", "増減した人数の関係"),
        answer_labels=("昨年の男子は", "昨年の女子は"),
        answer_units=("人", "人"),
        slots={"counter": "人"},
    )


def _scene_salt_mixture(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    percent_a, percent_b = n["percent_a"], n["percent_b"]
    return SystemScene(
        scenario=(
            f"{percent_a}%の食塩水と{percent_b}%の食塩水を混ぜて、"
            f"{n['percent_mix']}%の食塩水を{n['weight']}gつくりたい。"
        ),
        quantities="",
        variables_narration=(
            f"{percent_a}%の食塩水を x g、{percent_b}%の食塩水を y g とおく。"
        ),
        ask_formulation="",
        ask_value="それぞれ何gずつ混ぜればよいか求めよ。",
        relation_labels=("食塩水の重さの関係", "溶けている食塩の重さの関係"),
        answer_labels=(f"{percent_a}%の食塩水は", f"{percent_b}%の食塩水は"),
        answer_units=("g", "g"),
        slots={"counter": "g"},
    )


def _scene_two_containers(n: Mapping[str, int], v: Mapping[str, str]) -> SystemScene:
    return SystemScene(
        scenario=(
            f"容器Aには濃度のわからない食塩水が{n['weight_a']}g、"
            f"容器Bには別の濃度の食塩水が{n['weight_b']}g入っている。"
            f"AとBをすべて混ぜると{n['percent_mix']}%の食塩水になり、"
            f"Aの食塩水100gとBの食塩水100gだけを混ぜると"
            f"{n['percent_half']}%の食塩水になる。"
        ),
        quantities="",
        variables_narration="容器Aの濃度を x %、容器Bの濃度を y %とおく。",
        ask_formulation="",
        ask_value="容器A、Bの食塩水の濃度をそれぞれ求めよ。",
        relation_labels=("すべて混ぜたときの食塩の重さの関係", "100gずつ混ぜたときの食塩の重さの関係"),
        answer_labels=("容器Aの濃度は", "容器Bの濃度は"),
        answer_units=("%", "%"),
        slots={"counter": "%"},
    )


SCENE_RENDERERS: dict[str, Callable[[Mapping[str, int], Mapping[str, str]], SystemScene]] = {
    "price_count_diff": _scene_price_count_diff,
    "distance_time": _scene_distance_time,
    "time_split": _scene_time_split,
    "lap_meet_catch_up": _scene_lap_meet_catch_up,
    "percent_change": _scene_percent_change,
    "salt_mixture": _scene_salt_mixture,
    "two_containers": _scene_two_containers,
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
    # 総数は与えず差で与える。**「合わせて」が出たら関係が違う。**
    "price_count_diff": ((("多く", "多い"),), ("合わせて", "あわせて", "全部で")),
    # 道のりを文字に置く（x + y = D, x/a + y/b = T）。2つの区間と合計が要る。
    "distance_time": ((("歩き", "歩いて"), ("自転車",)), ("ずつ配", "余り")),
    # 時間を文字に置く（x + y = T, ax + by = D）。歩きと走りの2区間が要る。
    "time_split": ((("歩き", "歩いて"), ("走った", "走り")), ("ずつ配", "余り")),
    # 出会いと追いつき（t1(x+y) = L, t2(x−y) = L）。両方の向きが要る。
    "lap_meet_catch_up": (
        (("反対向き",), ("同じ向き",), ("追いつく", "追いつき")),
        ("ずつ配", "合わせて"),
    ),
    # 増減（x + y = N, px/100 − qy/100 = r）。増える側と減る側の両方が要る。
    "percent_change": ((("増え",), ("減っ", "減り")), ("ずつ配", "余り")),
    # 混合（x + y = W, ax + by = cW）。混ぜることと食塩水が要る。
    "salt_mixture": ((("混ぜ",), ("食塩水",)), ("ずつ配", "余り", "増え")),
    # 濃度を文字に置く（Wa·x + Wb·y = p(Wa+Wb), x + y = 2q）。2つの容器が要る。
    "two_containers": ((("混ぜ",), ("容器",)), ("ずつ配", "余り", "増え")),
}


# ---------------------------------------------------------------------------
# G-SC5（場面の妥当性）— 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_BOUNDS: dict[str, tuple[tuple[str, float, float], ...]] = {
    "price_count_diff": (
        ("price_a", 10, 1000), ("price_b", 10, 1000),
        ("diff", 1, 20), ("total", 20, 10000),
    ),
    # 通学・遠出: 時速は徒歩3km〜自転車20km、道のりは50km・時間は半日まで。
    "distance_time": (
        ("speed_walk", 1, 8), ("speed_bike", 8, 25),
        ("distance", 2, 50), ("total_time", 1, 12),
    ),
    # 途中から走る: 分速は徒歩50m〜走り260m、道のりは5km・時間は1時間まで。
    "time_split": (
        ("speed_slow", 30, 120), ("speed_fast", 100, 300),
        ("distance", 100, 5000), ("total_time", 2, 60),
    ),
    # 池のまわり: 1周は5km まで、出会い・追いつきは2時間以内。
    "lap_meet_catch_up": (
        ("lap", 200, 5000), ("meet_time", 1, 60), ("catch_up_time", 2, 120),
    ),
    # 生徒数の増減: 学校の規模は2000人まで、増減率は2桁未満。
    "percent_change": (
        ("total", 20, 2000), ("rate_up", 1, 30), ("rate_down", 1, 30),
        ("net_change", 1, 100),
    ),
    # 食塩水: 濃度は 1〜30%、重さは 5kg まで。
    "salt_mixture": (
        ("percent_a", 1, 30), ("percent_b", 1, 30), ("percent_mix", 1, 30),
        ("weight", 50, 5000),
    ),
    "two_containers": (
        ("weight_a", 50, 5000), ("weight_b", 50, 5000),
        ("percent_mix", 1, 30), ("percent_half", 1, 30),
    ),
}


# ---------------------------------------------------------------------------
# G-SC5b（数と数の関係）— 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_ORDER: dict[str, tuple[tuple[str, str, str], ...]] = {
    "price_count_diff": (("price_a", "!=", "price_b"),),
    # 歩きより自転車が速い。
    "distance_time": (("speed_walk", "<", "speed_bike"),),
    # 歩きより走りが速い。
    "time_split": (("speed_slow", "<", "speed_fast"),),
    # 追いつくほうが出会うより遅い（差 < 和）。
    "lap_meet_catch_up": (("meet_time", "<", "catch_up_time"),),
    # 混ぜたあとの濃度は2つの濃度のあいだ（加重平均）。
    "salt_mixture": (
        ("percent_a", "<", "percent_mix"), ("percent_mix", "<", "percent_b"),
    ),
    # 重さが同じだと det が 0 になって解けない。
    "two_containers": (("weight_a", "!=", "weight_b"),),
}


def draw_scene(kind: str, p: Mapping[str, Any], rng: Rng) -> tuple[SystemRelation, SystemScene]:
    """関係 → 語彙 → 場面文 の順に組む（`_VOCAB_FIRST` の場面だけ語彙が先）。"""
    steps = _SCENE_VOCAB.get(kind, ())
    if kind in _VOCAB_FIRST:
        vocab = draw_vocab(steps, p, rng)
        relation = RELATION_DRAWERS[kind](p, rng)
    else:
        relation = RELATION_DRAWERS[kind](p, rng)
        vocab = draw_vocab(steps, p, rng)
    return relation, SCENE_RENDERERS[kind](relation.numbers, vocab)


# ---------------------------------------------------------------------------
# 求める量（m·x + n·y + c を2つ）— recipe と checker が共有
# ---------------------------------------------------------------------------
def apply_answer_map(
    pair: tuple[sympy.Expr, sympy.Expr],
    answer_map: tuple[tuple[int, int, int], tuple[int, int, int]],
) -> tuple[sympy.Expr, sympy.Expr]:
    x0, y0 = pair
    out: list[sympy.Expr] = []
    for m, n, c in answer_map:
        out.append(
            cast(
                sympy.Expr,
                sympy.Integer(m) * x0 + sympy.Integer(n) * y0 + sympy.Integer(c),
            )
        )
    return out[0], out[1]


def format_pair_answer(
    values: tuple[sympy.Expr, sympy.Expr],
    labels: tuple[str, str],
    units: tuple[str, str],
) -> str:
    """「歩いた道のりは6km、走った道のりは12km」の形に組む（recipe と checker で共有）。

    label は「…は」「…は分速」まで含める（「分速90m」のように単位が前に来る量が
    あるので、label と値のあいだに区切りを入れない）。
    """
    return "、".join(
        f"{label}{value}{unit}"
        for label, value, unit in zip(labels, values, units, strict=True)
    )


def solve_scene(
    kind: str,
    numbers: Mapping[str, int],
    answer_map: tuple[tuple[int, int, int], tuple[int, int, int]],
) -> tuple[SystemFormulation, Solution, tuple[sympy.Expr, sympy.Expr]]:
    """場面の数値から「立式 → 連立を解く → 求める量」を1本で通す（checker と共有）。"""
    formulation = FORMULATION_BUILDERS[kind](**numbers)
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(
        Solution, solver(formulation.line_a, formulation.line_b, formulation.method)
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    point = sympy.sympify(sol.answer.srepr)
    pair = (cast(sympy.Expr, point[0]), cast(sympy.Expr, point[1]))
    return formulation, sol, apply_answer_map(pair, answer_map)


# ---------------------------------------------------------------------------
# recipe（6セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_SYSTEM_CONCEPTS)
def word_problem_system_equations(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    relation, scene = draw_scene(kind, p, rng)
    formulation, sol, answer_values = solve_scene(kind, relation.numbers, relation.answer_map)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    formulation_steps = _formulation_steps(scene, formulation)
    derive_steps = _derive_steps(scene, relation.answer_map, answer_values)
    # 誘導なしのセルは (1) が無いので、立式の手順も value 側の模範解答に入れる
    # （でないと「解くところから始まる解説」になる）。
    value_steps = [
        *([] if guided else formulation_steps),
        *solving_steps(sol),
        *derive_steps,
    ]

    value_sq = SubQuestionMR(
        label="(2)" if guided else "(1)",
        asked="value",
        answer=SymbolicAnswer(
            srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            display=format_pair_answer(
                answer_values, scene.answer_labels, scene.answer_units
            ),
        ),
        steps=value_steps,
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
                    srepr=sympy.srepr(formulation.eqs), display=formulation.display
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
            "scenario_kind": kind,
            # 誘導の有無（小問数）。checker はこれを見て返す Solution の数を決める。
            "guided": guided,
            # 場面文が読者に見せている数値だけ（答えは入れない）。
            "numbers": {k: str(v) for k, v in relation.numbers.items()},
            "answer_map": [[str(v) for v in row] for row in relation.answer_map],
            "answer_labels": list(scene.answer_labels),
            "answer_units": list(scene.answer_units),
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


_INTERSECTION_DISPLAY = re.compile(r"^交点\s*\((.+),\s*(.+)\)$")

# 「交点」はグラフの言葉である。文章題では答えは2つの量であって座標ではない。
_GRAPH_WORDING = {
    "compute_y": (
        "求めた x をどちらかの式に代入し、y を求めて交点の座標にする。",
        "求めた値をもとの式に代入し、もう一方の文字の値も求める。",
    ),
    "back_substitute": (
        "求めた値をもとの式に代入し、もう一方の文字を求めて交点の座標にする。",
        "求めた値をもとの式に代入し、もう一方の文字の値も求める。",
    ),
    "equate_expressions": (
        "2つの直線の y を等しいとおき、x についての方程式をつくる。",
        "2つの式の y を等しいとおき、x についての方程式をつくる。",
    ),
}


def solving_steps(sol: Solution) -> list[Step]:
    """solver の steps を、文章題の言葉に直す。

    ## 最初の一手を落とす

    `math.intersection_of_two_lines` の先頭は `setup_system`＝「2つの**直線**を
    ax + by = c の形にそろえて連立方程式を立てる」で、result_display も
    `Eq(3*x/25 - y/25, 28)` という sympy の内部表示になる。文章題では立式は
    `_formulation_steps` が場面の言葉と未整理の式で見せているので、ここは重複な
    うえに語彙（直線）も表示も合わない。落とすのは表示だけで、答えは solver が
    出したものをそのまま使う（double-solve の独立性は変わらない）。

    ## ★「交点」を落とす

    solver は g2_l27（2直線の交点）と共有しているので、残りの手も
    「交点の座標にする」「交点 (350, 350)」というグラフの言葉で書かれている。
    **食塩水の混合量を交点と呼ぶのは端的に誤り**で、g2_l16／l17／l18 の
    57 小問に漏れていた（2026-08-19 の外部評価で指摘・実測）。

    直すのは narration と result_display だけで、**op は触らない**。op 列は
    level_sep と G-FP が見ているので、変えると別のセルの合否が動く。
    """
    steps = list(sol.steps)
    if steps and steps[0].op == "setup_system":
        steps = steps[1:]
    out: list[Step] = []
    for st in steps:
        narration = st.narration
        display = st.result_display
        pair = _GRAPH_WORDING.get(st.op)
        if pair and narration == pair[0]:
            narration = pair[1]
        m = _INTERSECTION_DISPLAY.match(display or "")
        if m:
            display = f"x = {m.group(1)}、y = {m.group(2)}"
        if narration != st.narration or display != st.result_display:
            st = st.model_copy(update={"narration": narration, "result_display": display})
        out.append(st)
    return out


def _formulation_steps(
    scene: SystemScene, formulation: SystemFormulation
) -> list[Step]:
    """立式の手順。narration には数値を書かない（hints に流れる＝G-Q5t 対象）。"""
    label_a, label_b = scene.relation_labels
    return [
        Step(
            op="set_variables",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(_X, _Y)),
            result_display="x, y",
            narration=scene.variables_narration,
        ),
        Step(
            op="formulate_first",
            args=[],
            result_srepr=sympy.srepr(formulation.eqs[0]),
            result_display=formulation.display_a,
            narration=f"{label_a}に着目して、1つめの式をつくる。",
        ),
        Step(
            op="formulate_second",
            args=[],
            result_srepr=sympy.srepr(formulation.eqs[1]),
            result_display=formulation.display_b,
            narration=f"{label_b}に着目して、2つめの式をつくる。",
        ),
        *(
            []
            if formulation.display_b_reduced is None
            else [
                Step(
                    op="reduce_equation",
                    args=[],
                    result_srepr=sympy.srepr(formulation.eqs[1]),
                    result_display=formulation.display_b_reduced,
                    narration="2つめの式は両辺を100でわれるので、簡単な形に直す。",
                )
            ]
        ),
    ]


def _derive_steps(
    scene: SystemScene,
    answer_map: tuple[tuple[int, int, int], tuple[int, int, int]],
    answer_values: tuple[sympy.Expr, sympy.Expr],
) -> list[Step]:
    """最後の一手——求めた値を、問題が聞いている量のことばに直す。

    ★以前は「求める量が x, y と違う場面」だけに足していた。x, y がそのまま
    答えになる場面では最後の手が「y = 5」で終わり、**解説が答えに届いて
    いなかった**（解説の末尾と解答欄の食い違い 94 件のうち 56 件が これ）。
    問題が聞いているのは y の値ではなく「皿は何枚か」なので、x・y のままでも
    言い直す一手が要る。

    ★**「無いか有るか」で分けてはいけない。** 最初はここを「どの場面でも同じ op を
    1つ足す」に直したが、それだと g2_l17 の Lv3（x, y がそのまま答え）と
    Lv4（x, y から別の量を出す）の手順が完全に一致し、level_sep と G-FP が落ちた
    （fp 衝突・実測）。**どちらの場面にも最後の一手はある。違うのはその中身**——
    x, y のままなら言い直すだけ、違う量なら計算してから言う。op 名でその差を残す。
    """
    if answer_map == IDENTITY_ANSWER_MAP:
        return [
            Step(
                op="state_answer_in_context",
                args=[],
                result_srepr=sympy.srepr(sympy.Tuple(*answer_values)),
                result_display=format_pair_answer(
                    answer_values, scene.answer_labels, scene.answer_units
                ),
                narration="求めた値を、問題が聞いている量のことばに直して答える。",
            ),
        ]
    return [
        Step(
            op="derive_asked_quantities",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            result_display=format_pair_answer(
                answer_values, scene.answer_labels, scene.answer_units
            ),
            narration="求めた x、y をもとに、問われている量を計算して答える。",
        ),
    ]


__all__ = [
    "FORMULATION_BUILDERS",
    "IDENTITY_ANSWER_MAP",
    "RECIPE_NAME",
    "SystemFormulation",
    "SystemScene",
    "apply_answer_map",
    "format_pair_answer",
    "solve_scene",
    "solving_steps",
    "word_problem_system_equations",
]
