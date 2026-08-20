"""数量を文字式で表す文章題（form=word_problem・C14 の「1小問・答えが式」クラスタ）。

`word_problem_linear.py`（方程式を立てて解く）と違い、ここは**解かない**——問われて
いるのは「数量の関係を x を使った式で表す」ことそのもの（誘導なし・1小問）。答えは
自由変数を含む式なので、frame の asked 語彙は `formulation`（`value` ではなく、
「立式」に最も近い語彙。WORD_PROBLEM_FRAME の asked_vocab は {formulation, value} の
みで `expression` は無い）。

## 新 solver ゼロ

数学（式の整理・約分）はすべて既存 solver に委ねる:
  - `math.simplify_notation`（`letter_expr.py`）: 数×文字の積を「数を前に×省略」で表す
    （g1_l12/l15 Lv1 の単項式）。
  - `math.evaluate_letter_expression`（`letter_expr.py`）: 一次式の同類項をまとめる
    （g1_l12 Lv2 の割引き＝定価の項と割引き分の項を1つにまとめる）。
  - `math.compute_monomial_expression`（`polynomial.py`）: 乗除混在の単項式を1つに
    まとめる（g1_l15 Lv2 の単位変換＝÷1000 を逆数の乗法に直して約分する）。

g1_l15 Lv3（3文字の差 xy − z）だけは「同類項をまとめる」がそもそも起きない（xy と z
は同類項ではない）。既存 solver は double-solve の検証にだけ使い（`evaluate_letter_
expression` で xy − z を独立に再計算）、MR に乗せる steps は recipe が「売上→利益」の
場面の言葉で自分の言葉を書く（solver の「同類項をまとめる」という誤った説明を生徒に
見せないため）。

## level_sep（「何を文字に置くか」ではなく「式の構造」で作る）

  - Lv1（g1_l12/g1_l15）: 単項式（数 × 1文字の積が1つ）。
  - Lv2（g1_l12）: 割合が係数に入る（定価の項 − 割引き分の項 → 分数係数の1項）。
  - Lv2（g1_l15）: 単位変換が係数に入る（÷1000 を逆数の乗法に直して約分）。
  - Lv3（g1_l15）: 多文字の差（x·y − z。同類項ではない2項の構成）。

## G-Q5t（答えの漏洩）対策

答えは自由変数を含む式＝display 全体一致でのみ検査されるが、**答え表示が場面文に
部分文字列として現れる**事故を構成時に防ぐ（過去に「答え 12x が本文の 12 と衝突」
という実バグがあった・letter_expr.py の `_leaks` をそのまま再利用）。有界リトライで
場面を引き直す。narration には数字を書かない（steps[:-1] の narration が hints の
素材になるため）。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import gcd
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
from engine.packs.math.recipes.letter_expr import (
    _NOTATION_LETTERS,
    _draw_distinct_from_pool,
    _leaks,
)
from engine.packs.math.recipes.scene_vocab import VocabStep, draw_vocab
from engine.packs.math.solvers.polynomial import _fmt_poly_display

RECIPE_NAME = "math.word_problem_expression"

_EXPR_CONCEPTS = [
    "letter_expr.word_problem_price_count_letter",
    "letter_expr.word_problem_discount",
    "letter_expr.word_problem_distance_letter",
    "letter_expr.word_problem_unit_convert",
    "letter_expr.word_problem_profit_multi_letter",
]

_MAX_ATTEMPTS = 200


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → 式」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExpressionFormulation:
    """式の構成結果。

    - `expr_str`: solver に渡す sympy 文字列（未整理でよい。solver 側で整理する）。
    - `setup_steps`: 場面の関係を読み取る手順（recipe 側の言葉。narration に数字なし）。
    - `solver_name` / `solver_args`: 整理を任せる既存 solver とその追加引数（mode 等）。
    - `use_solver_steps`: True なら solver の steps をそのまま最後に足す（solver の
      narration がそのまま正しい場面のみ）。False なら `final_narration` で1手だけ
      recipe 側の言葉に差し替える（xy − z のように「同類項をまとめる」が実際には
      起きない場面）。どちらでも最終的な答え（srepr/display）は solver の再計算値を
      使うので、double-solve の独立性そのものは変わらない。
    - `answer_unit`: 表示に付ける単位（多くは問題文が「xを使った式で表せ」とだけ
      問い、単位を明示的に求めていないので空。g1_l15 Lv2 だけ「何kmか」と単位変換
      そのものが論点なので km を付ける）。
    """

    expr_str: str
    setup_steps: list[Step]
    solver_name: str
    solver_args: tuple[object, ...]
    use_solver_steps: bool
    final_narration: str
    answer_unit: str
    # 答えの表示を場面の順で書きたいときだけ指定する（空なら solver の表示を使う）。
    answer_display: str = ""


def _relation_step(op: str, display: str, narration: str) -> Step:
    return Step(op=op, args=[], result_srepr=display, result_display=display, narration=narration)


def formulate_price_count_letter(*, price: str) -> ExpressionFormulation:
    """g1_l12 Lv1: 1つあたり price 円の品を x 個買う（代金 = price × x）。"""
    p = int(price)
    return ExpressionFormulation(
        expr_str=f"{p}*x",
        setup_steps=[
            _relation_step(
                "identify_relation",
                "1つあたりの値段 × 個数 = 代金",
                "1つあたりの値段に個数をかけると、代金になる。",
            ),
        ],
        solver_name="math.simplify_notation",
        solver_args=("product_basic",),
        use_solver_steps=True,
        final_narration="",
        answer_unit="",
    )


def formulate_discount(*, discount: str) -> ExpressionFormulation:
    """g1_l12 Lv2: 定価 a 円を discount 割引きで買う（代金 = a − a×discount/10）。"""
    d = int(discount)
    return ExpressionFormulation(
        expr_str=f"a - a*{d}/10",
        setup_steps=[
            _relation_step(
                "identify_relation",
                "定価 − 割引き額 = 代金",
                "定価から、割引きの割合の分だけ差し引いた代金を考える。",
            ),
        ],
        solver_name="math.evaluate_letter_expression",
        solver_args=("combine_linear",),
        use_solver_steps=True,
        final_narration="",
        answer_unit="",
    )


def formulate_distance_letter(*, speed: str, letter: str) -> ExpressionFormulation:
    """g1_l15 Lv1: 時速 speed km で letter 時間進む（道のり = speed × letter）。"""
    s = int(speed)
    return ExpressionFormulation(
        expr_str=f"{s}*{letter}",
        setup_steps=[
            _relation_step(
                "identify_relation",
                "速さ × 時間 = 道のり",
                "速さに時間をかけると、道のりになる。",
            ),
        ],
        solver_name="math.simplify_notation",
        solver_args=("product_basic",),
        use_solver_steps=True,
        final_narration="",
        answer_unit="",
    )


def formulate_unit_convert(*, speed: str, letter: str) -> ExpressionFormulation:
    """g1_l15 Lv2: 分速 speed m で letter 分進んだ道のりを km で表す（÷1000 が要る）。"""
    s = int(speed)
    return ExpressionFormulation(
        expr_str=f"{s}*{letter}/1000",
        setup_steps=[
            _relation_step(
                "identify_relation",
                "速さ × 時間 = 道のり(m)",
                "速さに時間をかけて、道のりをmで表す式をつくる。",
            ),
            _relation_step(
                "note_unit_conversion",
                "道のり(m) ÷ 1000 = 道のり(km)",
                "1kmは1000mなので、mの式を1000でわるとkmの式になる。",
            ),
        ],
        solver_name="math.compute_monomial_expression",
        solver_args=("mul_div_chain",),
        use_solver_steps=True,
        final_narration="",
        answer_unit="km",
    )


def formulate_profit_multi_letter(
    *, count_letter: str, price_letter: str, cost_letter: str
) -> ExpressionFormulation:
    """g1_l15 Lv3: count_letter 個仕入れ price_letter 円で全部売り、仕入れ総額 cost_letter 円。

    利益 = 売上(count_letter×price_letter) − 仕入れ総額(cost_letter)。この2項は同類項
    ではない（同じ文字の積ではない）ので、「同類項をまとめる」という説明は場面に合わ
    ない。solver は double-solve の独立検証にのみ使い、steps は場面の言葉で書く。
    """
    # **答えの表示は場面の順（売上 − 仕入）で書く。** sympy の正準順に任せると
    # 文字のアルファベット順に並び替えられて `-a + nx` になり、「売上から仕入れを
    # ひく」という場面の順序と逆になっていた。
    display = f"{count_letter}{price_letter} - {cost_letter}"
    return ExpressionFormulation(
        expr_str=f"{count_letter}*{price_letter} - {cost_letter}",
        setup_steps=[
            _relation_step(
                "compute_revenue",
                _fmt_poly_display(sympy.sympify(f"{count_letter}*{price_letter}")),
                "仕入れた個数と1個あたりの売り値をかけて、売り上げを求める式をつくる。",
            ),
        ],
        solver_name="math.evaluate_letter_expression",
        solver_args=("combine_linear",),
        use_solver_steps=False,
        final_narration="求めた売り上げから、仕入れにかかった総額をひいて、利益を表す式にする。",
        answer_unit="",
        answer_display=display,
    )


FORMULATION_BUILDERS: dict[str, Callable[..., ExpressionFormulation]] = {
    "price_count_letter": formulate_price_count_letter,
    "discount": formulate_discount,
    "distance_letter": formulate_distance_letter,
    "unit_convert": formulate_unit_convert,
    "profit_multi_letter": formulate_profit_multi_letter,
}


def solve_expression(kind: str, numbers: Mapping[str, str]) -> tuple[ExpressionFormulation, Solution]:
    """場面の数値/文字から「式を組む → 既存 solver で整理する」を1本で通す（checker と共有）。"""
    formulation = FORMULATION_BUILDERS[kind](**numbers)
    solver = REGISTRY.solver(formulation.solver_name)
    sol = cast(Solution, solver(formulation.expr_str, *formulation.solver_args))
    return formulation, sol


def build_answer(formulation: ExpressionFormulation, sol: Solution) -> SymbolicAnswer:
    assert isinstance(sol.answer, SymbolicAnswer)
    # 単位の前は空ける。答えが分数の式（`a/8`）だと詰めたときに `a/8km` となり、
    # km が分母に続いて読める（EVALUATION D-20 と同じ読めなさ）。
    unit = f" {formulation.answer_unit}" if formulation.answer_unit else ""
    body = formulation.answer_display or sol.answer.display
    return SymbolicAnswer(srepr=sol.answer.srepr, display=f"{body}{unit}")


def build_steps(formulation: ExpressionFormulation, sol: Solution) -> list[Step]:
    assert isinstance(sol.answer, SymbolicAnswer)
    if formulation.use_solver_steps:
        tail = list(sol.steps)
    else:
        tail = [
            Step(
                op="derive_expression",
                args=[],
                result_srepr=sol.answer.srepr,
                result_display=sol.answer.display,
                narration=formulation.final_narration,
            ),
        ]
    return [*formulation.setup_steps, *tail]


# ---------------------------------------------------------------------------
# 3層に割る（Relation / 語彙の抽選 / Scene）
#
# 割り方と理由は word_problem_linear.py の同じ節に書いてある（charter §3）。
#
# ## ★この module は「語彙が数の定義域を決める」場面が多い
# 値段は品物の相場に、速さは動作（歩く／走る／自転車）の相場に縛られている。
# だから**語彙を先に引き、その相場の中で数を引く**——5場面のうち4つがこの形で、
# `_VOCAB_FIRST` に並べてある（`discount` だけが「数 → 語彙」）。
# 相場は語彙と一緒に文字列で運ばれてくるので、Relation は `int(v["speed_lo"])` の
# ように受け取る（`scene_vocab.draw_vocab` の docstring 参照）。
#
# `price_count_letter` は品物と値段を**1回の抽選で**引く（相場の広い品物に偏って
# dup_rate が跳ねるのを防ぐため）。ここは分けられないので、語彙の手
# （`"priced"`）が数もいっしょに返し、Relation は引かずに受け取るだけにする。
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExpressionRelation:
    """関係（数と文字だけ）。**日本語を持たない。**

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（文字列で
    統一して持つ＝場面文に出ている数値も、g1_l15 Lv3 の文字の選び方も同じ扱いにする）。
    """

    numbers: dict[str, str]


@dataclass(frozen=True)
class ExpressionScene:
    """場面（日本語だけ）。数は引かず、引かれた数と語彙を受け取って文を組む。

    `slots` は題材（品名など、式の再計算には無関係で dup_key の variety のためだけに
    params に載せる）。
    """

    scenario: str
    ask: str
    kind: str
    slots: dict[str, str]


# ---------------------------------------------------------------------------
# 語彙の抽選（宣言だけ。日本語はここに書かない）
# ---------------------------------------------------------------------------
_SCENE_VOCAB: dict[str, tuple[VocabStep, ...]] = {
    # 品名・助数詞・値段を1回で引く（値段は品物の相場から 10円刻み）。
    "price_count_letter": (
        ("priced", "item_candidates", ("item", "counter", "price")),
    ),
    "discount": (("one", "item_candidates", ("item",)),),
    # `動作|下限|上限`。動作ごとに速さの相場が決まっている（歩く=時速3〜6km）。
    "distance_letter": (
        ("one", "motion_candidates", ("verb", "speed_lo", "speed_hi")),
    ),
    "unit_convert": (
        ("one", "motion_candidates", ("verb", "speed_lo", "speed_hi")),
    ),
    "profit_multi_letter": (("one", "item_candidates", ("item",)),),
}

# ★語彙を先に引く場面（割る前のコードの順番をそのまま残すためだけの宣言）。
# ここでは「語彙が数の定義域を決める」ので、順番に意味がある。
_VOCAB_FIRST = frozenset(
    {"price_count_letter", "distance_letter", "unit_convert", "profit_multi_letter"}
)


# ---------------------------------------------------------------------------
# Relation（数と文字だけ。日本語を1文字も持たない）
# ---------------------------------------------------------------------------
def _relation_price_count_letter(
    p: Mapping[str, Any], rng: Rng, v: Mapping[str, str]
) -> ExpressionRelation:
    """g1_l15 Lv1: 1つあたりの値段 × 個数。値段は語彙と1回で引かれている。"""
    return ExpressionRelation(numbers={"price": v["price"]})


def _relation_discount(
    p: Mapping[str, Any], rng: Rng, v: Mapping[str, str]
) -> ExpressionRelation:
    """g1_l15 Lv2: 定価 a 円の d 割引き。"""
    return ExpressionRelation(numbers={"discount": str(int(draw(p["discount_domain"], rng)))})


def _relation_distance_letter(
    p: Mapping[str, Any], rng: Rng, v: Mapping[str, str]
) -> ExpressionRelation:
    """g1_l15 Lv3: 時速 s km で t 時間。速さは動作の相場の中から引く。

    動作と速さを別々に引くと「時速9kmで歩く」「時速39kmで走る」が出る。
    人が歩くのは時速3〜6km、走るのは時速8〜15km で、動作ごとに範囲が決まっている。
    """
    speed = int(draw({"int_range": [int(v["speed_lo"]), int(v["speed_hi"])]}, rng))
    letter = str(draw(list(p["letter_candidates"]), rng))
    return ExpressionRelation(numbers={"speed": str(speed), "letter": letter})


# 単位変換（m→km）の答えの分母の上限。台帳の例「分速60m → 3a/50」が分母50なので、
# そこまでを教材の範囲とする。**速さの定義域は狭めない**（原則⓪: 壊れているのは答えの
# 大きさであって定義域の広さではない。分速106m だと `53a/500` になっていた＝D-31）。
# 動作ごとに速さを相場に縛った（語彙の手 `"one"` が相場を運ぶ）ぶん、上限を 100 に
# 緩める——分速70m（7a/100）は教材にある書き方。狭いままだと候補が10通りを切って
# dup_rate が跳ねる。
_MAX_UNIT_CONVERT_DENOMINATOR = 100


def _unit_convert_speeds(domain: Mapping[str, Any]) -> list[int]:
    """答えの分母（1000/gcd(速さ, 1000)）が上限内の速さだけ。"""
    lo, hi = (int(v) for v in cast("list[object]", domain["int_range"]))
    return [v for v in range(lo, hi + 1) if 1000 // gcd(v, 1000) <= _MAX_UNIT_CONVERT_DENOMINATOR]


def _relation_unit_convert(
    p: Mapping[str, Any], rng: Rng, v: Mapping[str, str]
) -> ExpressionRelation:
    """g1_l19 Lv2: 分速 s m で t 分＝何 km か（単位変換つき）。

    動作ごとの速さの相場と、答えの分母の上限の両方を満たす速さから引く。
    答えの分母を絞ったぶん、**文字の選び方**を軸に足して組み合わせを取り戻す
    （Lv1 と同じ手。原則①: 軸を増やす）。
    """
    speed = int(
        draw(
            {"int_set": _unit_convert_speeds(
                {"int_range": [int(v["speed_lo"]), int(v["speed_hi"])]}
            )},
            rng,
        )
    )
    letter = str(draw(list(p["letter_candidates"]), rng))
    return ExpressionRelation(numbers={"speed": str(speed), "letter": letter})


def _relation_profit_multi_letter(
    p: Mapping[str, Any], rng: Rng, v: Mapping[str, str]
) -> ExpressionRelation:
    """g1_l20 Lv2: 3つの文字で利益を表す（文字の選び方が軸）。"""
    count_letter, price_letter, cost_letter = _draw_distinct_from_pool(
        list(_NOTATION_LETTERS), 3, rng
    )
    return ExpressionRelation(
        numbers={
            "count_letter": count_letter,
            "price_letter": price_letter,
            "cost_letter": cost_letter,
        },
    )


RELATION_DRAWERS: dict[
    str, Callable[[Mapping[str, Any], Rng, Mapping[str, str]], ExpressionRelation]
] = {
    "price_count_letter": _relation_price_count_letter,
    "discount": _relation_discount,
    "distance_letter": _relation_distance_letter,
    "unit_convert": _relation_unit_convert,
    "profit_multi_letter": _relation_profit_multi_letter,
}


# ---------------------------------------------------------------------------
# Scene（日本語だけ。数は引かない＝この節に抽選は1つも無い）
# ---------------------------------------------------------------------------
def _scene_price_count_letter(
    n: Mapping[str, str], v: Mapping[str, str]
) -> ExpressionScene:
    item, counter = v["item"], v["counter"]
    return ExpressionScene(
        scenario=f"1{counter}{n['price']}円の{item}をx{counter}買う。",
        ask="代金を、xを使った式で表せ。",
        kind="price_count_letter",
        slots={"item": item, "counter": counter},
    )


def _scene_discount(n: Mapping[str, str], v: Mapping[str, str]) -> ExpressionScene:
    item = v["item"]
    return ExpressionScene(
        scenario=f"定価a円の{item}を、定価の{n['discount']}割引きで買う。",
        ask="代金を、aを使った式で表せ。",
        kind="discount",
        slots={"item": item},
    )


def _scene_distance_letter(n: Mapping[str, str], v: Mapping[str, str]) -> ExpressionScene:
    verb, letter = v["verb"], n["letter"]
    return ExpressionScene(
        scenario=f"時速{n['speed']}kmで{letter}時間{verb}。",
        ask=f"進む道のりを、{letter}を使った式で表せ。",
        kind="distance_letter",
        slots={"verb": verb},
    )


def _scene_unit_convert(n: Mapping[str, str], v: Mapping[str, str]) -> ExpressionScene:
    verb, letter = v["verb"], n["letter"]
    return ExpressionScene(
        scenario=f"分速{n['speed']}mで{letter}分間{verb}。",
        ask=f"進んだ道のりは何kmか、{letter}を使った式で表せ。",
        kind="unit_convert",
        slots={"verb": verb},
    )


def _scene_profit_multi_letter(
    n: Mapping[str, str], v: Mapping[str, str]
) -> ExpressionScene:
    item = v["item"]
    count_letter = n["count_letter"]
    price_letter = n["price_letter"]
    cost_letter = n["cost_letter"]
    return ExpressionScene(
        scenario=(
            f"ある{item}を{count_letter}個仕入れ、1個あたり{price_letter}円で"
            f"全部売った。仕入れ総額が{cost_letter}円である。"
        ),
        ask=f"全体の利益を、{count_letter}, {price_letter}, {cost_letter}を使った式で表せ。",
        kind="profit_multi_letter",
        slots={"item": item},
    )


SCENE_RENDERERS: dict[
    str, Callable[[Mapping[str, str], Mapping[str, str]], ExpressionScene]
] = {
    "price_count_letter": _scene_price_count_letter,
    "discount": _scene_discount,
    "distance_letter": _scene_distance_letter,
    "unit_convert": _scene_unit_convert,
    "profit_multi_letter": _scene_profit_multi_letter,
}


# ---------------------------------------------------------------------------
# G-SC3（骨格）— 関係が場面文に要求する言い方 / 禁じる言い方
# 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_PHRASES: dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]] = {
    # 単価 × 個数（文字は個数）。1つあたりの値段と買う数が要る。
    "price_count_letter": ((("円",), ("買う",)), ("割引き", "時速", "分速")),
    # 定価の d 割引き。割引きであることが要る。
    "discount": ((("定価",), ("割引き",)), ("時速", "分速", "仕入れ")),
    # 時速 × 時間（km）。時速と時間が要る。
    "distance_letter": ((("時速",), ("時間",)), ("分速", "割引き", "仕入れ")),
    # 分速 × 分 を km に直す。**分速**であることが要る（時速だと単位変換が無い）。
    "unit_convert": ((("分速",), ("分間",)), ("時速", "割引き", "仕入れ")),
    # 3つの文字で利益。仕入れと売りの両方が要る。
    "profit_multi_letter": ((("仕入れ",), ("売っ", "売り")), ("時速", "分速", "割引き")),
}


# ---------------------------------------------------------------------------
# G-SC5（場面の妥当性）— 書き方と理由は word_problem_linear.py の同じ節を見る。
RELATION_BOUNDS: dict[str, tuple[tuple[str, float, float], ...]] = {
    # 文字式の場面: 値段は3桁、割引きは1桁の割。
    "price_count_letter": (("price", 10, 1000),),
    "discount": (("discount", 1, 9),),
    # 時速は徒歩3km〜自動車60km、分速は徒歩50m〜自転車320m。
    "distance_letter": (("speed", 1, 60),),
    "unit_convert": (("speed", 30, 400),),
    # 3つの文字だけの場面（数は無い）。
    "profit_multi_letter": (),
}


def draw_scene(
    kind: str, p: Mapping[str, Any], rng: Rng
) -> tuple[ExpressionRelation, ExpressionScene]:
    """語彙（＋相場）→ 関係 → 場面文 の順に組む（`discount` だけ関係が先）。"""
    steps = _SCENE_VOCAB.get(kind, ())
    if kind in _VOCAB_FIRST:
        vocab = draw_vocab(steps, p, rng)
        relation = RELATION_DRAWERS[kind](p, rng, vocab)
    else:
        relation = RELATION_DRAWERS[kind](p, rng, {})
        vocab = draw_vocab(steps, p, rng)
    return relation, SCENE_RENDERERS[kind](relation.numbers, vocab)

# ---------------------------------------------------------------------------
# recipe（5セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_EXPR_CONCEPTS)
def word_problem_expression(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])

    relation: ExpressionRelation | None = None
    scene: ExpressionScene | None = None
    formulation: ExpressionFormulation | None = None
    sol: Solution | None = None
    for _ in range(_MAX_ATTEMPTS):
        cand_relation, cand_scene = draw_scene(kind, p, rng)
        candidate_formulation, candidate_sol = solve_expression(kind, cand_relation.numbers)
        assert isinstance(candidate_sol.answer, SymbolicAnswer)
        given_full = cand_scene.scenario + cand_scene.ask
        if not _leaks(candidate_sol.answer.display, given_full):
            relation, scene = cand_relation, cand_scene
            formulation, sol = candidate_formulation, candidate_sol
            break
    if relation is None or scene is None or formulation is None or sol is None:
        raise ValueError(f"非漏洩の場面を構成できず（scenario_kind={kind!r}）")

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="formulation",
        answer=build_answer(formulation, sol),
        steps=build_steps(formulation, sol),
        concept_tags=concept_tags,
        cause_tags=cause_tags,
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "scenario_kind": kind,
            # 場面文に出ている数値/文字だけ（答えは入れない）。checker はここから
            # 式を組み直し、同じ既存 solver で再計算する。
            "numbers": dict(relation.numbers),
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given={"scenario": scene.scenario},
        context_slots={**scene.slots, "ask_value": scene.ask},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


__all__ = [
    "ExpressionFormulation",
    "ExpressionScene",
    "FORMULATION_BUILDERS",
    "RECIPE_NAME",
    "build_answer",
    "build_steps",
    "solve_expression",
    "word_problem_expression",
]
