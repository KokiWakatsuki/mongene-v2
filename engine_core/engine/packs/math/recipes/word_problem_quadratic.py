"""2次方程式の利用（form=word_problem・C14 の「2次方程式」クラスタ）。

`word_problem_linear.py`（1元1次）・`word_problem_system.py`（連立）で通した骨格を、
2次方程式の利用に横展開する module。数学そのものは既存 solver `math.solve_quadratic`
（sympy.solve）に委ねる＝**新 solver ゼロ**。mode は g3_l29.calculation /
g3_l30.calculation / g3_l30.find_value がすでに使っている
`solve_product_form` / `solve_product_form_positive_root`
（g3_l30.calculation の source_desc に「word_problem のような解の吟味は別セル
C14 送り」と明記されている＝ここがその受け皿）。

## 1つの recipe で4セルを賄う設計

`word_problem_linear.py` と同じ償却。params の `scenario_kind` が

  1. 場面の数値を answer-first で引く関数（`_SCENE_DRAWERS`）
  2. その数値から2次方程式を組む関数（`FORMULATION_BUILDERS`）

の対を選ぶ。賄うのは g3_l29（数に関する問題）・g3_l30（図形に関する問題）の
Lv2/Lv3 × 2 unit = 4セル。

## 「不適解の吟味」が全セル共通の核

2次方程式は解が2つ出るが、場面（正の整数・正の長さ）にふさわしいのはそのうち
1つだけ。4つの場面すべてで「2つの解の積が負」になるよう answer-first で構成する
（負の解と正の解が必ず1つずつ生じる）ため、solver の mode は常に
`solve_product_form_positive_root`（正の解のみを答えとする）。これは
math.solve_quadratic に既存の mode（g3_l30.find_value と共有）。

## level_sep（G6 の構造差）

  - g3_l29 Lv2 (`consecutive_integers`): 文字＝小さい方の整数。x(x+1)=p 型
    （積は場面文の唯一の数値）。誘導あり2小問。答えは (x, x+1) の**2つ**の整数
    （「文字＝答えの一部」で、もう一方は x+1 の合成が要る）。
  - g3_l29 Lv3 (`square_relation`): 文字＝その数自身。x²=nx+m 型（積の形ではない
    ＝ g3_l29 Lv2 と式の見た目が違う）。誘導なし1小問。答えは x そのもの。
  - g3_l30 Lv2 (`rectangle_area`): 文字＝縦の長さ。x(x+d)=k 型（g3_l29 Lv2 と同じ
    「積の形」だが d は場面ごとに変わる＝ g3_l29 Lv2 の c=1 固定と違う）。誘導あり
    2小問。答えは縦の長さ（x そのもの・合成なし）。
  - g3_l30 Lv3 (`square_cut`): 文字＝短く/長くする量。(s-x)(s+x)=k 型（差の平方＝
    他の3つと式の系統が違う）。誘導なし1小問。答えは x そのもの。

## params が持つのは「場面文に出ている数値」だけ

`params["numbers"]` は場面文が読者に見せている数値（積・倍率・差・面積・1辺の
長さ）そのもので、答えは入っていない。checker は同じ `FORMULATION_BUILDERS` を
通して立式し直し、solver で解き直す。
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
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

RECIPE_NAME = "math.word_problem_quadratic"

_QUAD_WORD_CONCEPTS = [
    "quadratic.word_problem_consecutive_integers",
    "quadratic.word_problem_number_relation",
    "quadratic.word_problem_rectangle_area",
    "quadratic.word_problem_square_cut",
]

_X = sympy.Symbol("x")

# 全4場面が共有する solver mode（2つの解のうち正の解だけを答えとする・g3_l30.find_value
# と同じ既存 mode）。「不適解の吟味」がこのクラスタの核＝常にこの mode を使う。
_POSITIVE_ROOT_MODE = "solve_product_form_positive_root"


# ---------------------------------------------------------------------------
# 立式（recipe と checker が共有する「場面の数値 → 2次方程式」の単一の真実）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuadFormulation:
    """2次方程式の立式結果。

    - `eq`: 答えの機械表現（srepr で G-Q1 が突き合わせる）。
    - `equation_str`: solver `math.solve_quadratic` に渡す "lhs=rhs"。
    - `mode`: solver の op 列（常に `_POSITIVE_ROOT_MODE`）。
    """

    eq: sympy.Eq
    display: str
    equation_str: str
    mode: str


def _formulate(lhs: str, rhs: str, display: str) -> QuadFormulation:
    eq = sympy.Eq(sympy.sympify(lhs, rational=True), sympy.sympify(rhs, rational=True))
    return QuadFormulation(
        eq=eq, display=display, equation_str=f"{lhs}={rhs}", mode=_POSITIVE_ROOT_MODE
    )


def formulate_consecutive_integers(*, product: int, gap: int = 1) -> QuadFormulation:
    """x(x+g)=p（小さい方の整数を x とする）。g=1 は連続する整数、g=2 は連続する偶数・奇数。"""
    return _formulate(f"x*(x+{gap})", f"{product}", f"x(x + {gap}) = {product}")


def formulate_square_relation(*, multiplier: int, diff: int) -> QuadFormulation:
    """x² = n·x + m（この数を2乗した数は、もとの数の n 倍より m 大きい）。"""
    return _formulate(
        "x**2", f"({multiplier})*x+({diff})", f"x² = {multiplier}x + {diff}"
    )


def formulate_rectangle_area(*, diff: int, area: int) -> QuadFormulation:
    """x(x+d)=k（縦 x・横 x+d・面積 k）。"""
    return _formulate(f"x*(x+{diff})", f"{area}", f"x(x + {diff}) = {area}")


def formulate_square_cut(*, side: int, area: int) -> QuadFormulation:
    """(s−x)(s+x)=k（1辺 s の正方形を縦 x 短く・横 x 長くした長方形の面積 k）。"""
    return _formulate(
        f"({side}-x)*({side}+x)", f"{area}", f"({side} - x)({side} + x) = {area}"
    )


FORMULATION_BUILDERS: dict[str, Callable[..., QuadFormulation]] = {
    "consecutive_integers": formulate_consecutive_integers,
    "square_relation": formulate_square_relation,
    "rectangle_area": formulate_rectangle_area,
    "square_cut": formulate_square_cut,
}


# ---------------------------------------------------------------------------
# 場面の抽選（answer-first。正の解 x0 を先に引き、場面の数値を逆算する）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QuadScene:
    """場面文と、そこから立式に渡す数値。

    `numbers` は `FORMULATION_BUILDERS[kind]` のキーワード引数そのもの（params に
    そのまま載り、checker が同じ関数へ渡す）。`answer_coeffs` は「求める量 = m·x0+n」
    を1つ（値のみ）または2つ（例: 連続する2整数）持つ。1つなら display は
    `answer_units[0]` を付けるだけ、2つなら `answer_labels` で組む
    （word_problem_linear / word_problem_system の書式をそれぞれ踏襲）。
    """

    numbers: dict[str, int]
    scenario: str
    quantities: str
    ask_formulation: str
    ask_value: str
    # 「2通りに表せる量」の名前（立式の着眼点。解説の最初の一手に出す）。
    relation_label: str
    answer_coeffs: tuple[tuple[int, int], ...]
    answer_labels: tuple[str, ...]
    answer_units: tuple[str, ...]
    slots: dict[str, str]


def _index_domain(n: int) -> dict[str, list[int]]:
    return {"int_range": [0, n - 1]}


def _scene_consecutive_integers(p: Mapping[str, Any], rng: Rng) -> QuadScene:
    """g3_l29 Lv2: 連続する2つの正の整数・偶数・奇数の積が p（誘導あり）。

    **積 p は教科書の大きさ（x0 ≤ small_max）に収める。** 以前は x0 を 3〜700 まで
    引いていて「2数の積は132860である → 364と365」が出ていた。これは dup_rate を
    通すためだけの定義域拡大で、YAML にその旨のコメントまで残っていた。
    軸は「整数・偶数・奇数」の3通り（どれも教科書にある形で、立式は x(x+1) と
    x(x+2) に分かれる）に置きかえ、それでも足りないぶんは `dup_rate_max` で
    問題空間の狭さとして宣言する（FIXES.md の原則1→3）。
    """
    kind = str(draw(["integers", "even", "odd"], rng))
    x0_max = int(p["small_max"])
    if kind == "integers":
        cands = list(range(2, x0_max + 1))
        gap, noun = 1, "正の整数"
    elif kind == "even":
        cands = list(range(2, x0_max + 1, 2))
        gap, noun = 2, "正の偶数"
    else:
        cands = list(range(3, x0_max + 1, 2))
        gap, noun = 2, "正の奇数"
    x0 = cands[int(draw(_index_domain(len(cands)), rng))]
    product = x0 * (x0 + gap)
    return QuadScene(
        numbers={"product": product, "gap": gap},
        scenario=f"連続する2つの{noun}がある。この2数の積は{product}である。",
        quantities="小さい方の数を x とする。",
        ask_formulation="2数の積の関係を、x を使った方程式で表せ。",
        ask_value="この2つの数を求めよ。",
        relation_label="2つの数の積",
        answer_coeffs=((1, 0), (1, gap)),
        answer_labels=("小さい方の数は", "大きい方の数は"),
        answer_units=("", ""),
        slots={},
    )


def _square_relation_candidates(p: Mapping[str, Any]) -> list[tuple[int, int]]:
    """(倍率 n, もとの数の n 倍より大きい分 m) の候補列挙。

    answer-first: 正の整数解 x0 を先に決め、m = x0² − n·x0（>0）から逆算する
    （x²−nx−m=0・g3_l29 Lv3）。x0 > n の範囲だけを残せば m は常に正になる。
    判別式 n²+4m は m>0 で常に正、2解の積は −m<0 なので正の解はちょうど1つ。
    """
    multipliers = [int(v) for v in p["multiplier_candidates"]]
    x0_max = int(p["small_max"])
    # **本文に出る m に上限を置く**（EVALUATION D-31。x0 の定義域だけを見ていたので
    # 「もとの数の5倍より1554大きい」が出ていた。教科書は「3倍より10大きい」のように
    # 2桁でとる）。x0 の定義域は狭めない＝原則⓪「答えの大きさで測る」。
    diff_max = int(p["diff_max"])
    out: list[tuple[int, int]] = []
    for n in multipliers:
        for x0 in range(n + 1, x0_max + 1):
            m = x0 * x0 - n * x0
            if m <= diff_max:
                out.append((n, m))
    return out


# 同じ関係 x² = n·x + m の言い方（原則①: m を絞ったぶんの組み合わせを軸で取り戻す）。
_SQUARE_RELATION_PHRASINGS = ("larger", "subtract", "sum")


def _scene_square_relation(p: Mapping[str, Any], rng: Rng) -> QuadScene:
    """g3_l29 Lv3: ある正の整数を2乗した数が、もとの数の n 倍より m 大きい（誘導なし）。"""
    cands = _square_relation_candidates(p)
    n, m = cands[int(draw(_index_domain(len(cands)), rng))]
    phrasing = str(draw(list(_SQUARE_RELATION_PHRASINGS), rng))
    relation = {
        "larger": f"この数を2乗した数は、もとの数の{n}倍より{m}大きい。",
        "subtract": f"この数を2乗した数から、もとの数の{n}倍をひくと{m}になる。",
        "sum": f"この数を2乗した数は、もとの数の{n}倍と{m}の和に等しい。",
    }[phrasing]
    return QuadScene(
        numbers={"multiplier": n, "diff": m},
        scenario=f"ある正の整数がある。{relation}",
        quantities="",
        ask_formulation="",
        ask_value="この整数を求めよ。",
        relation_label="2乗した数ともとの数をもとにした数",
        answer_coeffs=((1, 0),),
        answer_labels=("",),
        answer_units=("",),
        # 言い方は場面の違いなので params に記録する（dup_key は params だけを見る）。
        slots={"phrasing": phrasing},
    )


# **cm² で語れる題材だけにする。** 「面積が312cm²の畑」「456cm²の花だん」が出ていた
# （畑・花だんは m² で測る大きさ）。紙・板・カード・写真は cm² が自然。
_RECTANGLE_SCENES = [
    # ★2026-08-18: 「横が縦より10cm長い長方形の写真、面積75cm²」→ 縦5cm×横15cm。
    # **1:3 の写真は実在しない**（L判は 2:3）。紙・板・カード・布は 1:3 でも成り立つ。
    "長方形", "長方形の紙", "長方形の板", "長方形のカード", "長方形の布",
    "長方形のシール", "長方形のタイル", "長方形の布",
]


def _scene_rectangle_area(p: Mapping[str, Any], rng: Rng) -> QuadScene:
    """g3_l30 Lv2: 横が縦より d cm 長い長方形の面積が k（誘導あり）。

    縦と差は教科書の大きさに収める（以前は縦40cm・面積2200cm² まで出ていた）。
    狭めたぶんは場面の軸で稼ぐ（FIXES.md の原則1・2）。
    """
    height = int(draw(p["height_domain"], rng))
    diff = int(draw(p["diff_domain"], rng))
    area = height * (height + diff)
    scene = str(draw(_RECTANGLE_SCENES, rng))
    return QuadScene(
        numbers={"diff": diff, "area": area},
        scenario=f"横が縦より{diff}cm長い{scene}がある。その面積は{area}cm²である。",
        quantities="縦の長さを x cm とする。",
        ask_formulation="面積の関係を、x を使った方程式で表せ。",
        ask_value="縦の長さを求めよ。",
        relation_label="長方形の面積",
        answer_coeffs=((1, 0),),
        answer_labels=("",),
        answer_units=("cm",),
        # 題材は params の "slots" に入る（numbers は立式の引数そのものなので混ぜられない）。
        slots={"scene": scene},
    )


def _square_cut_candidates(p: Mapping[str, Any]) -> list[tuple[int, int, int]]:
    """(1辺 s, 短く/長くする量 x0, 変形後の面積) の候補列挙（差の平方 s²−x0²）。

    x0 < s（縦の長さが正）を保証する組だけを残す。
    """
    # 1辺はきりのいい数の集合から（37cm・23cm のような半端な正方形を避ける）。
    sides = [int(v) for v in p["side_set"]]
    x_lo, x_hi = (int(v) for v in p["shrink_range"])
    out: list[tuple[int, int, int]] = []
    for s in sides:
        for x0 in range(x_lo, min(x_hi, s - 1) + 1):
            out.append((s, x0, s * s - x0 * x0))
    return out


def _scene_square_cut(p: Mapping[str, Any], rng: Rng) -> QuadScene:
    """g3_l30 Lv3: 1辺 s の正方形を縦 x 短く・横 x 長くした長方形の面積が k（誘導なし）。"""
    cands = _square_cut_candidates(p)
    side, _, area = cands[int(draw(_index_domain(len(cands)), rng))]
    return QuadScene(
        numbers={"side": side, "area": area},
        scenario=(
            f"1辺が{side}cmの正方形がある。縦を x cm 短くし、横を x cm 長くして"
            f"長方形をつくったところ、面積が{area}cm²になった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value="x の値を求めよ。",
        relation_label="変形後の長方形の面積",
        answer_coeffs=((1, 0),),
        answer_labels=("",),
        answer_units=("cm",),
        slots={},
    )


_SCENE_DRAWERS: dict[str, Callable[[Mapping[str, Any], Rng], QuadScene]] = {
    "consecutive_integers": _scene_consecutive_integers,
    "square_relation": _scene_square_relation,
    "rectangle_area": _scene_rectangle_area,
    "square_cut": _scene_square_cut,
}


# ---------------------------------------------------------------------------
# 求める量（m·x0 + n を1つまたは2つ）— recipe と checker が共有
# ---------------------------------------------------------------------------
def apply_answer_coeffs(
    root: sympy.Expr, coeffs: tuple[tuple[int, int], ...]
) -> tuple[sympy.Expr, ...]:
    return tuple(
        cast(sympy.Expr, sympy.Integer(m) * root + sympy.Integer(n)) for m, n in coeffs
    )


def format_answer(
    values: tuple[sympy.Expr, ...], labels: tuple[str, ...], units: tuple[str, ...]
) -> str:
    """1つの値なら「{値}{単位}」、2つなら「{ラベル}{値}{単位}」を「、」で繋ぐ。"""
    if len(values) == 1:
        return f"{values[0]}{units[0]}"
    return "、".join(
        f"{label}{value}{unit}"
        for label, value, unit in zip(labels, values, units, strict=True)
    )


def solve_scene(
    kind: str, numbers: Mapping[str, int], coeffs: tuple[tuple[int, int], ...]
) -> tuple[QuadFormulation, Solution, tuple[sympy.Expr, ...]]:
    """場面の数値から「立式 → 正の解を解く → 求める量」を1本で通す（checker と共有）。"""
    formulation = FORMULATION_BUILDERS[kind](**numbers)
    solver = REGISTRY.solver("math.solve_quadratic")
    sol = cast(Solution, solver(formulation.equation_str, formulation.mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    root = cast(sympy.Expr, sympy.sympify(sol.answer.srepr))
    return formulation, sol, apply_answer_coeffs(root, coeffs)


# ---------------------------------------------------------------------------
# recipe（4セル共通。scenario_kind と guided が level_sep を作る）
# ---------------------------------------------------------------------------
@register_recipe(RECIPE_NAME, provides_concepts=_QUAD_WORD_CONCEPTS)
def word_problem_quadratic(ctx: CellContext, rng: Rng) -> MR:
    p = ctx.spec_level.params
    kind = str(p["scenario_kind"])
    guided = bool(p["guided"])
    scene = _SCENE_DRAWERS[kind](p, rng)
    formulation, sol, answer_values = solve_scene(kind, scene.numbers, scene.answer_coeffs)

    concept_tags = list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)
    cause_tags = list(ctx.spec_level.cause_tags)

    formulation_steps = _formulation_steps(scene, formulation)
    value_sq = SubQuestionMR(
        label="(2)" if guided else "(1)",
        asked="value",
        answer=SymbolicAnswer(
            srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            display=format_answer(answer_values, scene.answer_labels, scene.answer_units),
        ),
        # 誘導なしのセルは (1) が無いので、立式の手順も value 側の模範解答に入れる
        # （でないと「解くところから始まる解説」になる）。誘導ありは (1) が持つ。
        steps=[
            *([] if guided else formulation_steps),
            *sol.steps,
            *_derive_steps(scene, answer_values),
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
            "answer_coeffs": [[str(m), str(n)] for m, n in scene.answer_coeffs],
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


def _formulation_steps(scene: QuadScene, formulation: QuadFormulation) -> list[Step]:
    """(1) 立式の手順。narration には数値を書かない（hints に流れるので G-Q5t 対象）。"""
    return [
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


def _derive_steps(scene: QuadScene, answer_values: tuple[sympy.Expr, ...]) -> list[Step]:
    """求める量が x そのものと違う場面だけ足す最後の一手（複数量への合成）。"""
    if scene.answer_coeffs == ((1, 0),):
        return []
    return [
        Step(
            op="derive_asked_quantity",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*answer_values)),
            result_display=format_answer(
                answer_values, scene.answer_labels, scene.answer_units
            ),
            narration="求めた x をもとに、問われている量を計算する。",
        ),
    ]


__all__ = [
    "FORMULATION_BUILDERS",
    "QuadFormulation",
    "QuadScene",
    "RECIPE_NAME",
    "apply_answer_coeffs",
    "format_answer",
    "solve_scene",
    "word_problem_quadratic",
]
