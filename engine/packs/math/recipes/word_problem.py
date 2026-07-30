"""文章題（form=word_problem）の recipe（構成的生成・answer-first。実装設計 §6.1）。

**この form の初回縦串**。台帳（docs/goal_spec_2026-07-12.md §3.4）は word_problem を
「T3 翻訳基盤（I2）が要る100セル」として凍結していたが、場面文そのものは T1
テンプレートで決定論的に書ける（既存の g3_l31.graph_table の given.condition が
既に動点の場面文を出している）。凍結の実体は **誘導つき多段小問** を検証できない
ことだけであり、それは G-Q1 の「全小問 double-solve」化で解けた。この module は
その最初の実証（g2_l16.word_problem Lv2）。

文章題の骨格（この form で横展開するときの型）:
  - `given.scenario`   場面（数量を含む散文）— G-GND で本文出現が検査される
  - `given.quantities` 変数の設定（「x 個」「y 本」…）＝誘導の第一段
  - `context_slots`    題材スロット（品名・助数詞）。テンプレが小問文を組むのに使う
  - 小問は (1) 立式 formulation → (2) 値 value の2段。両方が double-solve される
数学そのものは既存 solver に委ねる（新 solver ゼロ）。ここが薄いままである限り、
文章題の横展開は「場面文と小問文を書く」作業に落ちる。
"""
from __future__ import annotations

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

_SYSTEM_PRICE_COUNT_CONCEPTS = [
    "simultaneous_equations.word_problem_price_count",
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# 立式の表示形（display）。x + y = 10 / 90x + 60y = 720 の形に整える。
# ---------------------------------------------------------------------------
def _format_count_equation(total: int) -> str:
    return f"x + y = {total}"


def _format_cost_equation(price_a: int, price_b: int, cost: int) -> str:
    return f"{price_a}x + {price_b}y = {cost}"


def build_price_count_equations(
    total: int, price_a: int, price_b: int, cost: int
) -> tuple[sympy.Tuple, str]:
    """個数の式・代金の式（Eq の組）と、その表示形を作る。

    checker からも呼ぶ（recipe と checker で「同じ係数から同じ式」が出ることを
    G-Q1 が突き合わせる＝本文の数値と (1) の式のズレを検出する）。
    """
    x, y = sympy.symbols("x y")
    eq_count = sympy.Eq(x + y, sympy.Integer(total))
    eq_cost = sympy.Eq(sympy.Integer(price_a) * x + sympy.Integer(price_b) * y, sympy.Integer(cost))
    display = f"{_format_count_equation(total)}、{_format_cost_equation(price_a, price_b, cost)}"
    return sympy.Tuple(eq_count, eq_cost), display


# ---------------------------------------------------------------------------
# math.word_problem_price_count（g2_l16.word_problem Lv2 用）
# 誘導あり: (1) 2量2式を立てる → (2) それを解いて個数を求める。
# ---------------------------------------------------------------------------
@register_recipe(
    "math.word_problem_price_count", provides_concepts=_SYSTEM_PRICE_COUNT_CONCEPTS
)
def word_problem_price_count(ctx: CellContext, rng: Rng) -> MR:
    """個数と代金の連立の利用（answer-first・誘導つき2段小問）。

    買った個数 (a, b) と単価 (pa, pb) を先に引き、総数 a+b と合計代金 pa·a+pb·b を
    逆算する（答えから場面を作る＝端数の出ない綺麗な設定になる）。単価は相異に引く:
    pa = pb だと代金の式が個数の式の定数倍になり解が定まらない（det = pb - pa = 0）。
    答え (a, b) は既存 solver `math.intersection_of_two_lines` で連立を解き直して
    一致を確認する（新 solver ゼロ）。
    """
    p = ctx.spec_level.params
    count_a = int(draw(p["count_domain"], rng))
    count_b = int(draw(p["count_domain"], rng))
    price_a, price_b = (int(v) for v in draw_many(p["price_domain"], rng, k=2))
    item_a, item_b = _draw_distinct_items(list(p["item_candidates"]), rng)

    total = count_a + count_b
    cost = price_a * count_a + price_b * count_b

    line_count = (1, 1, total)
    line_cost = (price_a, price_b, cost)
    solver = REGISTRY.solver("math.intersection_of_two_lines")
    sol = cast(Solution, solver(line_count, line_cost, "elimination"))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.Tuple(sympy.Integer(count_a), sympy.Integer(count_b))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成解 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    equations, eq_display = build_price_count_equations(total, price_a, price_b, cost)

    scenario = (
        f"1個{price_a}円の{item_a}と1個{price_b}円の{item_b}を合わせて{total}個買ったところ、"
        f"代金の合計は{cost}円だった。"
    )
    quantities = f"{item_a}の個数を x 個、{item_b}の個数を y 個とする。"

    sub_questions = [
        SubQuestionMR(
            label="(1)",
            asked="formulation",
            answer=SymbolicAnswer(srepr=sympy.srepr(equations), display=eq_display),
            steps=_formulation_steps(item_a, item_b, total, price_a, price_b, cost),
            concept_tags=_effective_concept_tags(ctx),
            cause_tags=_effective_cause_tags(ctx),
        ),
        SubQuestionMR(
            label="(2)",
            asked="value",
            answer=sol.answer,
            steps=_solve_steps(total, price_a, price_b, cost, count_a, count_b),
            concept_tags=_effective_concept_tags(ctx),
            cause_tags=_effective_cause_tags(ctx),
        ),
    ]

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            # 係数の行（total / cost は場面文の数値そのもの）。checker はここから
            # 独立に立式し直し・解き直す。答え (a,b) は params に置かない。
            "line_count": [str(c) for c in line_count],
            "line_cost": [str(c) for c in line_cost],
            "method": "elimination",
            # 題材（dup_key は params のみを見るのでここに載せる。context_slots は
            # dup_key に算入されない＝品名差が重複判定に効かなくなるため）。
            "item_a": item_a,
            "item_b": item_b,
        },
        given={"scenario": scenario, "quantities": quantities},
        context_slots={"item_a": item_a, "item_b": item_b, "counter": "個"},
        sub_questions=sub_questions,
        visual_plan=None,
        provenance=Provenance(recipe="math.word_problem_price_count"),
    )


def _draw_distinct_items(candidates: list[Any], rng: Rng) -> tuple[str, str]:
    """品名候補から相異な2つを引く（文字列は draw のドメイン記法外なので添字で引く）。"""
    idx_a, idx_b = draw_many(
        {"int_range": [0, len(candidates) - 1], "distinct": ["value"]}, rng, k=2
    )
    return str(candidates[int(idx_a)]), str(candidates[int(idx_b)])


def _formulation_steps(
    item_a: str, item_b: str, total: int, price_a: int, price_b: int, cost: int
) -> list[Step]:
    """(1) 立式の手順。

    narration には値を書かない（narration だけが hints に流れるので、値を書くと
    G-Q5t の漏洩検査に当たる）。値は result_display 側に置く——こちらは explanation
    （模範解答）にだけ現れ、hints には出ない。
    """
    x, y = sympy.symbols("x y")
    eq_count = sympy.Eq(x + y, sympy.Integer(total))
    eq_cost = sympy.Eq(sympy.Integer(price_a) * x + sympy.Integer(price_b) * y, sympy.Integer(cost))
    return [
        Step(
            op="set_variables",
            args=[item_a, item_b],
            result_srepr=sympy.srepr(sympy.Tuple(x, y)),
            result_display="x, y",
            narration=f"{item_a}の個数を x、{item_b}の個数を y とおく。",
        ),
        Step(
            op="formulate_count",
            args=[],
            result_srepr=sympy.srepr(eq_count),
            result_display=_format_count_equation(total),
            narration="個数の関係から、x と y の和が合わせて買った個数に等しいという式をつくる。",
        ),
        Step(
            op="formulate_cost",
            args=[],
            result_srepr=sympy.srepr(eq_cost),
            result_display=_format_cost_equation(price_a, price_b, cost),
            narration="代金の関係から、それぞれの単価と個数の積の和が代金の合計に等しいという式をつくる。",
        ),
    ]


def _solve_steps(
    total: int, price_a: int, price_b: int, cost: int, count_a: int, count_b: int
) -> list[Step]:
    """(2) 加減法で解く手順。

    個数の式を x の単価倍して x の係数をそろえ、代金の式と辺々引いて x を消去する
    （残るのは (pb − pa)·y = cost − pa·total）。narration は値を含めない（hints へ流れる）。
    """
    x, y = sympy.symbols("x y")
    scaled = sympy.Eq(
        sympy.Integer(price_a) * x + sympy.Integer(price_a) * y, sympy.Integer(price_a * total)
    )
    return [
        Step(
            op="scale_count_equation",
            args=[],
            result_srepr=sympy.srepr(scaled),
            result_display=_format_cost_equation(price_a, price_a, price_a * total),
            narration="個数の式の両辺を x の単価だけ倍して、x の係数を代金の式とそろえる。",
        ),
        Step(
            op="eliminate_and_solve",
            args=[],
            result_srepr=sympy.srepr(sympy.Eq(y, sympy.Integer(count_b))),
            result_display=f"y = {count_b}",
            narration="辺々を引いて x を消去し、残った y の値を求める。",
        ),
        Step(
            op="back_substitute",
            args=[],
            result_srepr=sympy.srepr(sympy.Eq(x, sympy.Integer(count_a))),
            result_display=f"x = {count_a}",
            narration="求めた y を個数の式に代入して、x の値を求める。",
        ),
    ]


__all__ = ["build_price_count_equations", "word_problem_price_count"]
