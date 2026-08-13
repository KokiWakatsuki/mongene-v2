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
from engine.packs.math.recipes.word_problem_linear import _draw_pair_token
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
    return SymbolicAnswer(srepr=sol.answer.srepr, display=f"{sol.answer.display}{unit}")


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
# 場面の抽選（recipe 専用。checker は numbers から式を組み直すだけで RNG は引かない）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExpressionScene:
    """場面文と、そこから式を組む文字/数値。

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（文字列で
    統一して持つ＝場面文に出ている数値も、g1_l15 Lv3 の文字の選び方も同じ扱いにする）。
    `slots` は題材（品名など、式の再計算には無関係で dup_key の variety のためだけに
    params に載せる）。
    """

    numbers: dict[str, str]
    scenario: str
    ask: str
    kind: str
    slots: dict[str, str]


def _scene_price_count_letter(p: Mapping[str, Any], rng: Rng) -> ExpressionScene:
    price = int(draw(p["price_domain"], rng))
    item, counter = _draw_pair_token(list(p["item_candidates"]), rng)
    return ExpressionScene(
        numbers={"price": str(price)},
        scenario=f"1{counter}{price}円の{item}をx{counter}買う。",
        ask="代金を、xを使った式で表せ。",
        kind="price_count_letter",
        slots={"item": item, "counter": counter},
    )


def _scene_discount(p: Mapping[str, Any], rng: Rng) -> ExpressionScene:
    discount = int(draw(p["discount_domain"], rng))
    item = str(draw(list(p["item_candidates"]), rng))
    return ExpressionScene(
        numbers={"discount": str(discount)},
        scenario=f"定価a円の{item}を、定価の{discount}割引きで買う。",
        ask="代金を、aを使った式で表せ。",
        kind="discount",
        slots={"item": item},
    )


def _scene_distance_letter(p: Mapping[str, Any], rng: Rng) -> ExpressionScene:
    speed = int(draw(p["speed_domain"], rng))
    verb = str(draw(list(p["verb_candidates"]), rng))
    letter = str(draw(list(p["letter_candidates"]), rng))
    return ExpressionScene(
        numbers={"speed": str(speed), "letter": letter},
        scenario=f"時速{speed}kmで{letter}時間{verb}。",
        ask=f"進む道のりを、{letter}を使った式で表せ。",
        kind="distance_letter",
        slots={"verb": verb},
    )


# 単位変換（m→km）の答えの分母の上限。台帳の例「分速60m → 3a/50」が分母50なので、
# そこまでを教材の範囲とする。**速さの定義域は狭めない**（原則⓪: 壊れているのは答えの
# 大きさであって定義域の広さではない。分速106m だと `53a/500` になっていた＝D-31）。
_MAX_UNIT_CONVERT_DENOMINATOR = 50


def _unit_convert_speeds(domain: Mapping[str, Any]) -> list[int]:
    """答えの分母（1000/gcd(速さ, 1000)）が上限内の速さだけ。"""
    lo, hi = (int(v) for v in cast("list[object]", domain["int_range"]))
    return [v for v in range(lo, hi + 1) if 1000 // gcd(v, 1000) <= _MAX_UNIT_CONVERT_DENOMINATOR]


def _scene_unit_convert(p: Mapping[str, Any], rng: Rng) -> ExpressionScene:
    speed = int(draw({"int_set": _unit_convert_speeds(p["speed_domain"])}, rng))
    verb = str(draw(list(p["verb_candidates"]), rng))
    # 答えの分母を絞ったぶん、**文字の選び方**を軸に足して組み合わせを取り戻す
    # （Lv1 と同じ手。原則①: 軸を増やす）。
    letter = str(draw(list(p["letter_candidates"]), rng))
    return ExpressionScene(
        numbers={"speed": str(speed), "letter": letter},
        scenario=f"分速{speed}mで{letter}分間{verb}。",
        ask=f"進んだ道のりは何kmか、{letter}を使った式で表せ。",
        kind="unit_convert",
        slots={"verb": verb},
    )


def _scene_profit_multi_letter(p: Mapping[str, Any], rng: Rng) -> ExpressionScene:
    item = str(draw(list(p["item_candidates"]), rng))
    count_letter, price_letter, cost_letter = _draw_distinct_from_pool(
        list(_NOTATION_LETTERS), 3, rng
    )
    return ExpressionScene(
        numbers={
            "count_letter": count_letter,
            "price_letter": price_letter,
            "cost_letter": cost_letter,
        },
        scenario=(
            f"ある{item}を{count_letter}個仕入れ、1個あたり{price_letter}円で"
            f"全部売った。仕入れ総額が{cost_letter}円である。"
        ),
        ask=f"全体の利益を、{count_letter}, {price_letter}, {cost_letter}を使った式で表せ。",
        kind="profit_multi_letter",
        slots={"item": item},
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], ExpressionScene]] = {
    "price_count_letter": _scene_price_count_letter,
    "discount": _scene_discount,
    "distance_letter": _scene_distance_letter,
    "unit_convert": _scene_unit_convert,
    "profit_multi_letter": _scene_profit_multi_letter,
}


# ---------------------------------------------------------------------------
# recipe（5セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_EXPR_CONCEPTS)
def word_problem_expression(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    drawer = _SCENE_DRAWERS[kind]

    scene: ExpressionScene | None = None
    formulation: ExpressionFormulation | None = None
    sol: Solution | None = None
    for _ in range(_MAX_ATTEMPTS):
        candidate = drawer(p, rng)
        candidate_formulation, candidate_sol = solve_expression(kind, candidate.numbers)
        assert isinstance(candidate_sol.answer, SymbolicAnswer)
        given_full = candidate.scenario + candidate.ask
        if not _leaks(candidate_sol.answer.display, given_full):
            scene, formulation, sol = candidate, candidate_formulation, candidate_sol
            break
    if scene is None or formulation is None or sol is None:
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
            "numbers": dict(scene.numbers),
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
