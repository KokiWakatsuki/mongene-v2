"""等式・不等式で数量関係を表す文章題（form=word_problem・C14「関係を表す」クラスタ）。

`word_problem_linear.py` / `word_problem_system.py`（文字を使って解く）とは違い、
ここは g1_l19（等式の作り方）・g1_l20（不等式の作り方）の word_problem＝
「解かずに、関係を等式／不等式として表す」1小問セルを賄う。台帳の example が
どちらも「…を等式（不等式）で表せ。」で終わり、値を求める小問がないため、
sub_questions は常に asked="formulation" の1個だけになる。

## 新 solver ゼロ

値を求めないので、そもそも「解く」処理が要らない。数学的な仕事は
`sympy.Eq` / `sympy.Le` / `sympy.Gt` / `sympy.Lt` で関係を組み立てるだけ
（`word_problem_linear.py` の (1) 立式ステップが solver を呼ばずに `sympy.Eq` を
直接組んでいるのと同じ型）。recipe と checker はどちらも同じ
`FORMULATION_BUILDERS[kind](**numbers)` を呼んで関係を組み直す＝二重化。

## G-Q1（double-solve）が relational を扱えるかの実験結果

`_answers_match`（quality_gates.py）は `SymbolicAnswer.srepr` の文字列比較でしか
ない。`sympy.Eq/Le/Lt/Gt` はどれも srepr が決定的（同じ式なら同じ文字列）なので、
Eq 以外の relational でも core を変更せずにそのまま通る（実験で確認済み）。

Lv2（不等式・両辺に文字）は2つの不等式を同時に表す（`bound < 式 < 式`）。
`sympy.And(Gt, Lt)` は sympy が引数を正準順序に並べ替えるため実は srepr も
安定していたが、`sympy.Tuple(Gt, Lt)`（本文の記述順＝「20より大きく、かつ…未満」の
順）の方が構成の意図が読みやすいためこちらを採用する（brief 推奨）。

## G-Q5t（答えの漏洩）

答え（関係式）は必ず自由変数 x を含む「式」なので、`_gate_q5t` は個々の数値では
なく「答えの display 全体が problem_text/hints に部分文字列で現れるか」だけを見る
（quality_gates.py の `_expr_has_free_symbol` 分岐）。display は `"4x=500"` のような
機械的な式表記で、problem_text は日本語の散文なので原理的に一致しない。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.word_problem_linear import _draw_pair_token, _draw_priced_item

RECIPE_NAME = "math.word_problem_relation"

_RELATION_CONCEPTS = [
    "equality.word_problem_equality_simple",
    "equality.word_problem_equality_both_sides",
    "inequality.word_problem_simple",
    "inequality.word_problem_both_sides",
]

_X = sympy.Symbol("x")


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → 関係式」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RelationFormulation:
    """等式／不等式の立式結果。

    - `relation`: 答えの機械表現（srepr で G-Q1 が突き合わせる）。`sympy.Eq` /
      `sympy.Le` は1本の関係、Lv2 の不等式（両辺に文字＋2条件）だけ
      `sympy.Tuple(Gt, Lt)`（本文の記述順）を使う。
    - `display`: 生徒に見せる表示形（未整理・本文の言葉の順）。
    - `sides`: Lv2（両辺に文字）だけが持つ「先に別々に表す2つの数量」の表示。
      Lv1 は片辺が定数なので分けて表す段が無く `None`。これが `_formulation_steps` の
      分岐＝**op 列の相異**になる（fp が Lv 間で分かれる＝level_sep の構造差）。
    """

    relation: sympy.Basic
    display: str
    sides: tuple[str, str] | None = None


def formulate_equality_simple(*, count: int, total: int) -> RelationFormulation:
    """count·x = total（片辺が定数＝Lv1）。"""
    return RelationFormulation(
        relation=sympy.Eq(sympy.Integer(count) * _X, sympy.Integer(total)),
        display=f"{count}x = {total}",
    )


def formulate_equality_both_sides(*, mult: int, add_a: int, add_b: int) -> RelationFormulation:
    """mult·x + add_a = x + add_b（両辺に文字＝Lv2）。"""
    return RelationFormulation(
        relation=sympy.Eq(
            sympy.Integer(mult) * _X + sympy.Integer(add_a), _X + sympy.Integer(add_b)
        ),
        display=f"{mult}x + {add_a} = x + {add_b}",
        sides=(f"{mult}x + {add_a}", f"x + {add_b}"),
    )


def formulate_inequality_simple(*, count: int, total: int) -> RelationFormulation:
    """count·x ≦ total（片辺が定数＝Lv1）。"""
    return RelationFormulation(
        relation=sympy.Le(sympy.Integer(count) * _X, sympy.Integer(total)),
        display=f"{count}x ≦ {total}",
    )


def formulate_inequality_both_sides(
    *, mult: int, sub: int, bound: int, add: int
) -> RelationFormulation:
    """bound < mult·x − sub かつ mult·x − sub < x + add（両辺に文字＋2条件＝Lv2）。

    答え（srepr で突き合わせる機械表現）は本文の記述順に組んだ
    `Tuple(Gt(…, bound), Lt(…, x + add))`。表示は教科書流の連鎖不等号
    `bound < 式 < 式` にまとめる（1ステップ=1行の契約に合わせる）。
    """
    lhs = sympy.Integer(mult) * _X - sympy.Integer(sub)
    rhs = _X + sympy.Integer(add)
    return RelationFormulation(
        relation=sympy.Tuple(sympy.Gt(lhs, sympy.Integer(bound)), sympy.Lt(lhs, rhs)),
        display=f"{bound} < {mult}x - {sub} < x + {add}",
        sides=(f"{mult}x - {sub}", f"x + {add}"),
    )


FORMULATION_BUILDERS: dict[str, Callable[..., RelationFormulation]] = {
    "equality_price_count": formulate_equality_simple,
    "equality_both_sides": formulate_equality_both_sides,
    "inequality_price_count": formulate_inequality_simple,
    "inequality_both_sides": formulate_inequality_both_sides,
}


# ---------------------------------------------------------------------------
# 場面の抽選（params の numbers は「場面文に出ている数値」だけ）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RelationScene:
    numbers: dict[str, int]
    scenario: str
    ask: str
    # 「場面の中で比べられている／等しくなっている数量」の一言（narration には使わず
    # result_display にだけ載せる＝ G-Q5t は steps[:-1] の narration しか見ないので
    # ここに具体的な言葉を置いても漏洩検査の対象にならない）。
    relation_label: str
    slots: dict[str, str]


def _scene_equality_price_count(p: Mapping[str, Any], rng: Rng) -> RelationScene:
    """g1_l19 Lv1: 1個 x 円の品を count 個買って total 円でちょうど払えた。"""
    count = int(draw(p["count_domain"], rng))
    # x0（単価）は場面文には出ない（x で表されるため）。total を answer-first で
    # 逆算するためだけに引く。**値段は品物ごとの相場から 10円刻みで引く**——前は
    # 20〜300 の整数だったので「7本買って1624円ちょうど払えた」＝1本232円の
    # ボールペンになっていた。
    item, counter, price = _draw_priced_item(list(p["item_candidates"]), rng)
    total = price * count
    return RelationScene(
        numbers={"count": count, "total": total},
        scenario=(
            f"1{counter} x 円の{item}を{count}{counter}買って、"
            f"{total}円出したところちょうど払えた。"
        ),
        ask="この関係を等式で表せ。",
        relation_label="代金の合計",
        slots={"item": item, "counter": counter},
    )


def _scene_equality_both_sides(p: Mapping[str, Any], rng: Rng) -> RelationScene:
    """g1_l19 Lv2: x を mult 倍して add_a を加えた数 = x に add_b を加えた数。"""
    mult = int(draw(p["mult_domain"], rng))
    add_a = int(draw(p["add_domain"], rng))
    add_b = int(draw(p["add_domain"], rng))
    return RelationScene(
        numbers={"mult": mult, "add_a": add_a, "add_b": add_b},
        scenario=(
            f"ある数 x を{mult}倍して{add_a}を加えた数が、"
            f"x に{add_b}を加えた数に等しい。"
        ),
        ask="この関係を等式で表せ。",
        relation_label="2通りに表した数の関係",
        slots={},
    )


def _scene_inequality_price_count(p: Mapping[str, Any], rng: Rng) -> RelationScene:
    """g1_l20 Lv1: 1個 x 円の品を count 個買った代金が total 円以下。"""
    count = int(draw(p["count_domain"], rng))
    # **予算は 100円刻みで、しかも品物の相場に合わせる。** 前は 100〜3000 の整数を
    # 個数と無関係に引いていて「代金が1153円以下であった」（端数）や「おにぎりを
    # 8個買った代金が400円以下」（1個50円のおにぎり）が出ていた。実物の「〜円以下」
    # は区切りのいい額で、しかも暗に想定している単価が場面としてありうる。
    # 相場の単価 × 個数を 100円単位に切り上げ、余裕分（0〜300円）を足す。
    item, counter, price = _draw_priced_item(list(p["item_candidates"]), rng)
    margin = int(draw(list(range(0, 4)), rng))
    total = -(-price * count // 100) * 100 + margin * 100
    return RelationScene(
        numbers={"count": count, "total": total},
        scenario=(
            f"1{counter} x 円の{item}を{count}{counter}買ったときの代金が、"
            f"{total}円以下であった。"
        ),
        ask="この関係を不等式で表せ。",
        relation_label="代金の合計",
        slots={"item": item, "counter": counter},
    )


def _scene_inequality_both_sides(p: Mapping[str, Any], rng: Rng) -> RelationScene:
    """g1_l20 Lv2: x を mult 倍して sub を引いた数が bound より大きく、x に add を
    加えた数未満である。
    """
    # **満たす数が実際に存在する組だけを残す。** 前は4つを独立に引いていたので
    # 「32 < 3x - 2 < x + 4」（x > 34/3 かつ x < 3 ＝ 解なし）が出ていた。
    # 「ある数 x」と言っておいて、そんな数が1つも無いのは場面として成り立たない。
    # bound < mult·x - sub < x + add の解は (bound+sub)/mult < x < (add+sub)/(mult-1)。
    for _ in range(200):
        mult = int(draw(p["mult_domain"], rng))
        sub = int(draw(p["sub_domain"], rng))
        bound = int(draw(p["bound_domain"], rng))
        add = int(draw(p["add_domain"], rng))
        lo = (bound + sub) / mult
        hi = (add + sub) / (mult - 1)
        if hi - lo >= 1:  # 整数解が少なくとも1つ入る幅
            break
    else:
        raise ValueError("_scene_inequality_both_sides: 解が存在する組を構成できず")
    return RelationScene(
        numbers={"mult": mult, "sub": sub, "bound": bound, "add": add},
        scenario=(
            f"ある数 x を{mult}倍して{sub}を引いた数が、"
            f"{bound} より大きく、かつ x に{add}を加えた数未満である。"
        ),
        ask="この関係を不等式で表せ。",
        relation_label="2通りに表した数の関係",
        slots={},
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], RelationScene]] = {
    "equality_price_count": _scene_equality_price_count,
    "equality_both_sides": _scene_equality_both_sides,
    "inequality_price_count": _scene_inequality_price_count,
    "inequality_both_sides": _scene_inequality_both_sides,
}


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_RELATION_CONCEPTS)
def word_problem_relation(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    scene = _SCENE_DRAWERS[kind](p, rng)
    formulation = FORMULATION_BUILDERS[kind](**scene.numbers)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    value_sq = SubQuestionMR(
        label="(1)",
        asked="formulation",
        answer=SymbolicAnswer(
            srepr=sympy.srepr(formulation.relation), display=formulation.display
        ),
        steps=_formulation_steps(scene, formulation),
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
            # 場面文が読者に見せている数値だけ（答えは入れない）。checker はここから
            # 立式し直す。
            "numbers": {k: str(v) for k, v in scene.numbers.items()},
            # 題材（dup_key は params のみを見る＝context_slots は算入されない）。
            "slots": dict(scene.slots),
        },
        given={"scenario": scene.scenario},
        context_slots={**scene.slots, "ask_value": scene.ask},
        sub_questions=[value_sq],
        visual_plan=None,
        provenance=Provenance(recipe=RECIPE_NAME),
    )


def _formulation_steps(scene: RelationScene, formulation: RelationFormulation) -> list[Step]:
    """立式の手順。narration には数値を書かない（hints は steps[:-1] の narration
    だけを使うので、最後の1手の result_display に答えの式を置ける）。

    Lv1（片辺が定数）は「関係に着目する → 式にする」の2手。Lv2（両辺に文字）は
    比べる数量が両方とも x の式になるので、**それぞれを別々に式で表してから結ぶ**
    3手になる。これは学習内容そのものの差（Lv2 の難しさは「両辺を別々に立てて
    から結ぶ」ところにある）であると同時に、fp（op 列）を Lv 間で分ける役目も持つ
    ＝レベルが構造を変えていることの機械的な保証（P-1 回帰の防止）。
    """
    if formulation.sides is None:
        return [
            Step(
                op="find_relation",
                args=[],
                result_srepr=sympy.srepr(_X),
                result_display=scene.relation_label,
                narration="場面の中で、比べられている、または等しくなっている数量に着目する。",
            ),
            Step(
                op="formulate_relation",
                args=[],
                result_srepr=sympy.srepr(formulation.relation),
                result_display=formulation.display,
                narration="その数量を x を使った式で表し、等式または不等式をつくる。",
            ),
        ]
    first, second = formulation.sides
    return [
        Step(
            op="express_first_quantity",
            args=[],
            result_srepr="",
            result_display=first,
            narration="比べられている数量のうち、一方を x を使った式で表す。",
        ),
        Step(
            op="express_second_quantity",
            args=[],
            result_srepr="",
            result_display=second,
            narration="もう一方の数量も、同じように x を使った式で表す。",
        ),
        Step(
            op="formulate_relation",
            args=[],
            result_srepr=sympy.srepr(formulation.relation),
            result_display=formulation.display,
            narration="表した式どうしを、場面が示す大小や等しさのとおりに等号・不等号で結ぶ。",
        ),
    ]


__all__ = [
    "FORMULATION_BUILDERS",
    "RECIPE_NAME",
    "RelationFormulation",
    "RelationScene",
    "word_problem_relation",
]
