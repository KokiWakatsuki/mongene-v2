"""exam（入試対策・T1融合）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C13（exam 融合の T1 部）クラスタのうち、新しい数学ロジックを要さず既存 solver の
合成だけで構成できるセルを集約する（g3_l59/probability.py の資産を再利用）。
乱数は `engine.core.rng.draw` 以外で解釈しない。

【所在の但し書き】exam_l3（動点と面積変化）の6セルは、中身が既存の動点資産の
再利用そのものなので `recipes/motion.py` の末尾に置いてある（helper を持ち出さずに
済むほうが食い違いを作りにくい）。ここには exam_l1（一次関数と図形の融合）と
exam_l5/exam_l7 の単発セルがある。
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.recipes.letter_expr import _draw_named_figures
from engine.packs.math.visuals.graph import tick_labels_from_params


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# ---------------------------------------------------------------------------
# exam_l5.calculation Lv2: 場合の数から確率を計算処理する（既存 math.relative_frequency 再利用）
# ---------------------------------------------------------------------------
# 数え上げの場面。
#
# **場面を「起こりうる場合の数を決めつけないもの」にするだけでは足りなかった。**
# 決めつけないつもりでも、場面には必ず取りうる通り数がある。
#
#   「何人かの中から2人の委員を選ぶとき、起こりうる場合は全部で31通り」
#   → nC2 は 1, 3, 6, 10, 15, 21, 28, 36… で、**31 は存在しない**
#   → しかも「特定の1人がふくまれる場合」は n−1 通りに決まるのに 28 と書いていた
#
# 全体と該当の数を独立に引いていたのが原因。ここでは**場面の大きさ n を1つ引いて、
# 全体も該当もそこから計算する**。こうすると「その場面でありえない数」は原理的に出ない。
# 引数は n（と、場面が要る内訳）だけ。
_COUNT_SCENES: list[str] = [
    "lottery",   # n本のくじに当たり a 本。2本続けて引いて、当たりが出る
    "card",      # 1〜n の数字カードから2枚並べて2けたの整数。偶数になる
    "ball",      # 赤 r 個・白 w 個から続けて2個。同じ色になる
    "committee",  # n人から2人の委員。特定の1人がふくまれる
]


def _draw_count_scene(kind: str, rng: Rng) -> tuple[str, str, int, int]:
    """(場面文, 条件の言い方, 全体の通り数, 該当の通り数)。すべて場面の大きさから導く。

    **ありえる値だけにすると組が減るので、場面の中に軸を足して戻す。**
    最初に大きさ1つだけで書いたら dup_rate が 0.63 に跳ねた（閾 0.20）。
    定義域を広げて戻すのではなく（それをやると 31通り の問題に逆戻りする）、
    「聞く条件」を場面ごとに2通り用意して軸を増やした。
    """
    if kind == "lottery":
        n = int(draw({"int_range": [4, 10]}, rng))
        a = int(draw({"int_range": [1, n - 2]}, rng))
        item = str(draw(["くじ", "抽選券", "ふくびき券"], rng))
        total, miss = n * (n - 1), (n - a) * (n - a - 1)
        scene = f"当たりが{a}本ふくまれる{n}本の{item}から、続けて2本を引くとき、"
        if int(draw({"int_range": [0, 1]}, rng)):
            return scene, "当たりが少なくとも1本出る", total, total - miss
        return scene, "2本とも外れる", total, miss
    if kind == "card":
        n = int(draw({"int_range": [4, 9]}, rng))
        # 直前が「数字が1枚ずつ書かれた」なので、題材の語に「数字」を入れない
        # （「数字が1枚ずつ書かれた数字の書かれた紙」になった）。
        item = str(draw(["カード", "番号札", "紙", "タイル"], rng))
        # 一の位で決まる。1〜n の中の偶数は n//2 個、奇数は (n+1)//2 個。
        scene = (f"1から{n}までの数字が1枚ずつ書かれた{item}から2枚を選んで並べ、"
                 f"2けたの整数をつくるとき、")
        if int(draw({"int_range": [0, 1]}, rng)):
            return scene, "偶数になる", n * (n - 1), (n // 2) * (n - 1)
        return scene, "奇数になる", n * (n - 1), ((n + 1) // 2) * (n - 1)
    if kind == "ball":
        r = int(draw({"int_range": [2, 7]}, rng))
        w = int(draw({"int_range": [2, 7]}, rng))
        ca, cb = (str(x) for x in draw_many(
            {"int_range": [0, 5], "distinct": ["value"]}, rng, k=2))
        colors = ["赤", "白", "青", "黄", "緑", "黒"]
        ca, cb = colors[int(ca)], colors[int(cb)]
        n = r + w
        total, same = n * (n - 1), r * (r - 1) + w * (w - 1)
        scene = f"{ca}玉{r}個と{cb}玉{w}個が入った袋から、続けて2個の玉を取り出すとき、"
        if int(draw({"int_range": [0, 1]}, rng)):
            return scene, "2個とも同じ色になる", total, same
        return scene, "2個の色が異なる", total, total - same
    n = int(draw({"int_range": [5, 14]}, rng))  # committee
    role = str(draw(["委員", "係", "代表", "当番"], rng))
    scene = f"{n}人の中から2人の{role}を選ぶとき、"
    if int(draw({"int_range": [0, 1]}, rng)):
        return scene, "特定の1人がふくまれる", n * (n - 1) // 2, n - 1
    return scene, "特定の2人がともにふくまれる", n * (n - 1) // 2, 1

_EXAM_PROBABILITY_FROM_COUNTS_CONCEPTS = ["exam.probability_from_counts"]


@register_recipe(
    "math.exam_probability_from_counts", provides_concepts=_EXAM_PROBABILITY_FROM_COUNTS_CONCEPTS
)
def exam_probability_from_counts_recipe(ctx: CellContext, rng: Rng) -> MR:
    """場合の数(全体・該当)から確率を求める（exam_l5.calculation Lv2・answer-first）。

    **場面のない「ある試行で全部で164通り」は教材の問題になっていない。**
    数え上げた結果を確率に直す処理そのものが眼目のセルなので、数え上げは済んで
    いるものとして与えるが、その場面は具体的に書く（くじ・カード・玉）。
    """
    scene_index = int(draw({"int_set": list(range(len(_COUNT_SCENES)))}, rng))
    scene, cond, total, favorable = _draw_count_scene(_COUNT_SCENES[scene_index], rng)
    unit = "通り"

    # 確率は分数で答えるのが教材の作法（小数で答えるのは相対度数のほう）。
    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(favorable, total, False))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(favorable, total))

    statement = (
        f"{scene}起こりうる場合は全部で{total}{unit}あり、そのうち{cond}場合は"
        f"{favorable}{unit}であった。{cond}確率を求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": favorable, "total": total, "scene": scene},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_probability_from_counts"),
    )


# ---------------------------------------------------------------------------
# exam_l7.calculation Lv2: 相対度数・比率の計算処理（既存 math.relative_frequency 再利用）
# ---------------------------------------------------------------------------
# 標本調査の標本の大きさ（教科書はきりのよい人数で調べる）。
_SAMPLE_TOTALS = (20, 25, 40, 50, 80, 100, 125, 200, 250, 400, 500)


@lru_cache(maxsize=4)
def _sample_ratio_pairs(totals: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    """割合が小数第3位までで書き切れる (標本の大きさ, 賛成者数) の組。"""
    return tuple(
        (t, f) for t in totals for f in range(1, t) if (1000 * f) % t == 0
    )


def _draw_sample_ratio(p: Mapping[str, object], rng: Rng) -> tuple[int, int]:
    totals = tuple(int(v) for v in cast("list[int]", p.get("total_set") or _SAMPLE_TOTALS))
    cands = _sample_ratio_pairs(totals)
    return cands[int(draw({"int_set": list(range(len(cands)))}, rng))]


_EXAM_RELATIVE_FREQUENCY_CONCEPTS = ["exam.relative_frequency_ratio"]


@register_recipe("math.exam_relative_frequency", provides_concepts=_EXAM_RELATIVE_FREQUENCY_CONCEPTS)
def exam_relative_frequency_recipe(ctx: CellContext, rng: Rng) -> MR:
    """標本調査の賛成者数などから相対度数(割合)を求める（exam_l7.calculation Lv2・answer-first）。"""
    p = ctx.spec_level.params
    # 相対度数は小数で答えるのが教材の作法。標本の人数と賛成者数を独立に引いていたので
    # 「標本28人のうち27人 → 27/28」という、割合として使えない答えが出ていた（D-24）。
    # 標本の大きさはきりのよい人数にし、割合が小数で書き切れる組だけを引く。
    total, favorable = _draw_sample_ratio(p, rng)

    solver = REGISTRY.solver("math.relative_frequency")
    sol = cast(Solution, solver(favorable, total))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(sympy.Rational(favorable, total))

    statement = (
        f"ある調査で、標本{total}人のうち賛成した人が{favorable}人であった。"
        "賛成した人の相対度数(割合)を小数で求めよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"occurred": favorable, "total": total},
        given={"expressions": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_relative_frequency"),
    )


# ---------------------------------------------------------------------------
# exam_l7.find_value Lv3: 四分位数・範囲を求める（既存 math.quartiles_full_summary 再利用）
# ---------------------------------------------------------------------------
_EXAM_QUARTILES_FULL_SUMMARY_CONCEPTS = ["exam.quartiles_full_summary"]


@register_recipe(
    "math.exam_quartiles_full_summary", provides_concepts=_EXAM_QUARTILES_FULL_SUMMARY_CONCEPTS
)
def exam_quartiles_full_summary_recipe(ctx: CellContext, rng: Rng) -> MR:
    """データの第1〜第3四分位数・四分位範囲を求める（exam_l7.find_value Lv3・answer-first）。"""
    p = ctx.spec_level.params
    n = int(draw(p["n_domain"], rng))
    data = [int(v) for v in draw_many(p["value_domain"], rng, n)]

    solver = REGISTRY.solver("math.quartiles_full_summary")
    sol = cast(Solution, solver(data))
    assert isinstance(sol.answer, SymbolicAnswer)

    data_text = "、".join(str(v) for v in data)
    statement = (
        f"次の{n}個のデータについて、第1四分位数・第2四分位数(中央値)・第3四分位数、"
        f"および四分位範囲を求めよ。データ:{data_text}"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"data": data},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.exam_quartiles_full_summary"),
    )


# ===========================================================================
# exam_l1（入試融合・一次関数と図形の融合）— C13
#
# 面積はすべて solvers/exam_linear_figure.py の shoelace 公式で求める。
# 構成は answer-first：先に「答えになる交点の座標」を決め、そこを通るように
# 直線の切片を逆算する（実行時に交点が整数かを判定するのではなく、構成時に保証する）。
#
# 【漏洩の封じ方】本文に出るのは直線の傾き・切片（と面積の条件）だけなので、
# 答えの値（交点の座標・面積・逆算した係数）がそれらと一致する組は構成の段階で外す。
# G-Q5t の whitelist は given 由来なので、context_slots に置いた問いの数値は許可されない。
# ===========================================================================
_EXAM_L1_INTERSECTION_AREA_CONCEPTS = ["exam.linear_intersection_triangle_area"]
_EXAM_L1_COEFFICIENT_CONCEPTS = ["exam.linear_coefficient_from_area"]
_EXAM_L1_POSITION_CONCEPTS = ["exam.linear_line_through_triangle"]
_EXAM_L1_GUIDED_CONCEPTS = ["exam.linear_guided_intersection_area"]
_EXAM_L1_AREA_MULTIPLE_CONCEPTS = ["exam.linear_area_multiple_point"]


def _line_text(m: int, b: int) -> str:
    """直線の式を教科書表記で書く（y = mx + b・係数 1/-1 と 0 の扱いをそろえる）。"""
    if m == 1:
        term = "x"
    elif m == -1:
        term = "-x"
    else:
        term = f"{m}x"
    if b == 0:
        return f"y={term}"
    return f"y={term}{'+' if b > 0 else '-'}{abs(b)}"


def _exam_l1_sub(ctx: CellContext, *, label: str, asked: str, sol: Solution) -> SubQuestionMR:
    return SubQuestionMR(
        label=label, asked=asked, answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )


def _two_line_candidates(
    p: dict[str, Any], *, both_intercepts: bool
) -> list[tuple[int, int, int, int, int, int]]:
    """(m1, b1, m2, b2, px, py) の候補列挙。交点 (px, py) を先に決めて切片を逆算する。

    `both_intercepts=True` では2直線とも x 切片が整数になる組だけを残す
    （誘導ありの (2) で両方の切片を問うため）。False では2本目だけでよい。
    x 切片が整数 ⇔ 傾きが交点の y 座標を割り切る（q = px − py/m）。
    """
    out: list[tuple[int, int, int, int, int, int]] = []
    for px in p["px_candidates"]:
        for py in p["py_candidates"]:
            px_i, py_i = int(px), int(py)
            for m1 in p["slope_candidates"]:
                for m2 in p["slope_candidates"]:
                    m1_i, m2_i = int(m1), int(m2)
                    if m1_i == m2_i or m1_i == 0 or m2_i == 0:
                        continue
                    if py_i % m2_i:
                        continue
                    if both_intercepts and py_i % m1_i:
                        continue
                    b1 = py_i - m1_i * px_i
                    b2 = py_i - m2_i * px_i
                    q1 = px_i - py_i // m1_i
                    q2 = px_i - py_i // m2_i
                    if q1 == q2:
                        continue  # 三角形がつぶれる
                    if b1 == 0 or b2 == 0:
                        continue  # 切片 0 だと直線が原点を通り、三角形がつぶれる
                    out.append((m1_i, b1, m2_i, b2, px_i, py_i))
    return out


def _no_leak(answer_values: set[int], text_values: set[int]) -> bool:
    """答えの数値が本文の数値（と面積の単位 cm² 由来の 2）と重ならないか。"""
    return not (answer_values & (text_values | {2}))


@register_recipe(
    "math.exam_linear_intersection_area", provides_concepts=_EXAM_L1_INTERSECTION_AREA_CONCEPTS
)
def exam_linear_intersection_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """交点 → x 切片 → 三角形の面積、と多段で求める（exam_l1.find_value Lv3）。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    cands = [
        (m1, b1, m2, b2, px, py)
        for m1, b1, m2, b2, px, py in _two_line_candidates(p, both_intercepts=False)
        if _no_leak(
            {abs(px), abs(py), abs(px - py // m2) * abs(py) // 2},
            {abs(m1), abs(b1), abs(m2), abs(b2)},
        )
        # 面積が整数になる組だけ（分数の面積は入試の設問として不自然）
        and (abs(px - py // m2) * abs(py)) % 2 == 0
    ]
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    m1, b1, m2, b2, _px, _py = cands[idx]
    (v,) = _draw_named_figures([2], rng)
    lp, lq = v

    sol = cast(
        Solution, REGISTRY.solver("math.lines_intersection_and_triangle_area")(m1, b1, m2, b2, lp + lq)
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    (pt, area) = sympy.sympify(sol.answer.srepr)
    assert area > 0 and pt[1] != 0

    condition = (
        f"2直線 {_line_text(m1, b1)} と {_line_text(m2, b2)} の交点を{lp}、"
        f"{_line_text(m2, b2)} と x軸との交点を{lq}、原点をOとする。"
        f"交点{lp}の座標を求め、三角形O{lp}{lq}の面積を求めよ"
    )
    # ★**入試融合のセルは図が1枚も無かった。** 実物の入試問題は必ずグラフが
    # 添えてある。2直線と、交点・x切片・原点が収まる範囲で描く。
    pts = [str((0, b1)), str((0, b2)), str(tuple(int(v) for v in pt)),
           str((int(-b2 // m2), 0)), str((0, 0))]
    params = {
        "m1": m1, "b1": b1, "m2": m2, "b2": b2, "labels": lp + lq,
        "a": str(m1), "b": str(b1), "extra_lines": [[str(m2), str(b2)]],
        "pts": pts,
        # ★線に式を添える。線が2本あるだけで、どちらが本文のどの式か図から
        # 決まらなかった（2026-08-19 の外部評価で指摘）。
        "label_equations": True,
        # 点名は**原点と x 切片だけ**。交点 lp の座標は (1) の答えなので、
        # 図に名前を打つと答えを図が言ってしまう（交わる位置は線を引いた時点で
        # 見えているが、名前を添えるとどの点を指すかまで確定してしまう）。
        "label_pts": [str((0, 0)), str((int(-b2 // m2), 0))],
        "label_names": ["O", lq],
    }
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"condition": condition},
        sub_questions=[_exam_l1_sub(ctx, label="(1)", asked="value", sol=sol)],
        visual_plan=VisualPlan(
            style="grid", labels=tick_labels_from_params(params),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="line", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.exam_linear_intersection_area"),
    )


@register_recipe(
    "math.exam_linear_coefficient_from_area", provides_concepts=_EXAM_L1_COEFFICIENT_CONCEPTS
)
def exam_linear_coefficient_from_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形の面積の条件から、直線の傾きを逆算する（exam_l1.find_value Lv4）。

    answer-first: 先に答えになる傾き a と切片 b を決め、面積 b²/(2a) を計算して
    問いに載せる（実行時に整数かを判定するのではなく、構成時に整数を保証する）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    cands: list[tuple[int, int, int]] = []
    for a in p["slope_candidates"]:
        for b in p["intercept_candidates"]:
            a_i, b_i = int(a), int(b)
            if a_i <= 0 or b_i <= 0 or (b_i * b_i) % (2 * a_i):
                continue
            area = b_i * b_i // (2 * a_i)
            if area <= 0 or not _no_leak({a_i}, {b_i, area}):
                continue
            cands.append((a_i, b_i, area))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    a, b, area = cands[idx]
    (v,) = _draw_named_figures([2], rng)
    la, lb = v

    sol = cast(Solution, REGISTRY.solver("math.slope_from_triangle_area")(b, area))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sympy.sympify(sol.answer.srepr) == sympy.Integer(a), "逆算した傾きが構成と一致しない"

    condition = (
        f"直線 y=ax+{b} が x軸、y軸と交わる点をそれぞれ{la}、{lb}とする。"
        f"三角形O{la}{lb}の面積が{area}であるとき、正の数 a の値を求めよ。ただしOは原点とする"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"intercept": b, "area": area, "labels": la + lb},
        given={"condition": condition},
        sub_questions=[_exam_l1_sub(ctx, label="(1)", asked="value", sol=sol)],
        visual_plan=None,
        provenance=Provenance(recipe="math.exam_linear_coefficient_from_area"),
    )


@register_recipe(
    "math.exam_linear_line_through_triangle", provides_concepts=_EXAM_L1_POSITION_CONCEPTS
)
def exam_linear_line_through_triangle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """直線が三角形の内部を通るかどうかを、グラフから読み取る（exam_l1.graph_table Lv2）。

    候補の列挙では「通る」構成と「通らない」構成の**両方**を残す——片方しか出ないと
    図を見なくても答えられてしまう（＝退化）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    cands: list[tuple[int, int, tuple[tuple[int, int], ...], bool]] = []
    for m in p["slope_candidates"]:
        for b in p["intercept_candidates"]:
            m_i, b_i = int(m), int(b)
            if m_i == 0:
                continue
            for vx in p["vertex_x_candidates"]:
                for vy in p["vertex_y_candidates"]:
                    vx_i, vy_i = int(vx), int(vy)
                    # 直角三角形（原点側の頂点・x 軸方向・y 軸方向）で図を素直にする。
                    verts = ((vx_i, vy_i), (vx_i + int(p["leg"]), vy_i),
                             (vx_i, vy_i + int(p["leg"])))
                    diffs = [y - (m_i * x + b_i) for x, y in verts]
                    if any(d == 0 for d in diffs):
                        continue  # 頂点が直線上＝判定があいまい
                    passes = len({d > 0 for d in diffs}) == 2
                    cands.append((m_i, b_i, verts, passes))
    # 「通る」「通らない」がどちらも十分にあることを構成の段階で確かめる
    n_pass = sum(1 for c in cands if c[3])
    assert 0 < n_pass < len(cands), "判定が一方に偏っている（図を見ずに答えられる）"
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    m, b, verts, _passes = cands[idx]
    (v,) = _draw_named_figures([3], rng)
    l1, l2, l3 = v

    sol = cast(
        Solution, REGISTRY.solver("math.judge_line_through_triangle")(m, b, verts)
    )
    polygon_pts = [str(v) for v in verts]
    # 描画範囲は直線と三角形の両方が収まるように取る（直線は両軸との交点を含める）。
    line_pts = [str((0, b)), str((sympy.Rational(-b, m), 0))]
    params: dict[str, Any] = {
        "a": str(m), "b": str(b),
        "polygon_pts": polygon_pts,
        "pts": polygon_pts + line_pts,
        "labels": l1 + l2 + l3,
        # 三角形の頂点名と直線の式を図に書く。**どちらも本文がそのまま書いている**
        # 情報なので、図に出しても答え（内部を通るかどうか）は漏れない。
        "label_equations": True,
        "label_pts": polygon_pts,
        "label_names": [l1, l2, l3],
    }
    condition = (
        f"座標平面上に直線 {_line_text(m, b)} と、3点{l1}{verts[0]}、{l2}{verts[1]}、"
        f"{l3}{verts[2]}を頂点とする三角形{l1}{l2}{l3}がある。"
        f"この直線が三角形{l1}{l2}{l3}の内部を通るかどうかを、グラフから読み取って答えよ"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params=params,
        given={"condition": condition},
        sub_questions=[_exam_l1_sub(ctx, label="(1)", asked="read_position", sol=sol)],
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params(params),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="line", attrs={}),
                VisualElement(kind="polygon", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.exam_linear_line_through_triangle"),
    )


@register_recipe(
    "math.exam_linear_guided_triangle", provides_concepts=_EXAM_L1_GUIDED_CONCEPTS
)
def exam_linear_guided_triangle_recipe(ctx: CellContext, rng: Rng) -> MR:
    """誘導あり3小問（交点 → 2つの x 切片 → 三角形の面積）（exam_l1.word_problem Lv3）。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    cands = [
        (m1, b1, m2, b2, px, py)
        for m1, b1, m2, b2, px, py in _two_line_candidates(p, both_intercepts=True)
        if _no_leak(
            {abs(px), abs(py),
             abs((px - py // m1) - (px - py // m2)) * abs(py) // 2},
            {abs(m1), abs(b1), abs(m2), abs(b2)},
        )
        and (abs((px - py // m1) - (px - py // m2)) * abs(py)) % 2 == 0
    ]
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    m1, b1, m2, b2, _px, _py = cands[idx]
    (v,) = _draw_named_figures([3], rng)
    la, lb, lc = v

    pt_sol = cast(
        Solution, REGISTRY.solver("math.intersection_point_of_two_lines")(m1, b1, m2, b2)
    )
    int_sol = cast(
        Solution, REGISTRY.solver("math.x_intercepts_of_two_lines")(m1, b1, m2, b2)
    )
    area_sol = cast(
        Solution, REGISTRY.solver("math.triangle_area_from_two_lines")(m1, b1, m2, b2)
    )
    for s in (pt_sol, int_sol, area_sol):
        assert isinstance(s.answer, SymbolicAnswer)
    # 恒真: (3) の面積は、(1) の交点と (2) の2つの切片から底辺×高さでも出る。
    pt = sympy.sympify(pt_sol.answer.srepr)          # type: ignore[union-attr]
    q1, q2 = sympy.sympify(int_sol.answer.srepr)     # type: ignore[union-attr]
    area = sympy.sympify(area_sol.answer.srepr)      # type: ignore[union-attr]
    assert (area - sympy.Rational(1, 2) * abs(q1[0] - q2[0]) * abs(pt[1])).equals(0)

    scenario = (
        f"座標平面上に2直線 {_line_text(m1, b1)} と {_line_text(m2, b2)} がある。"
        f"この2直線の交点を{la}、{_line_text(m1, b1)} と x軸との交点を{lb}、"
        f"{_line_text(m2, b2)} と x軸との交点を{lc}とする。"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        # word_problem の不変条件: 本文に出ている数だけを numbers に置く
        # （傾き ±1 を候補から外してあるのは、"y=x+3" だと 1 が本文に現れないため）。
        params={"numbers": {"m1": m1, "b1": b1, "m2": m2, "b2": b2},
                "labels": la + lb + lc,
                # 図のための描画情報（本文に出る数だけ・答えの点は入れない）。
                "a": str(m1), "b": str(b1), "extra_lines": [[str(m2), str(b2)]],
                "pts": [str((0, b1)), str((0, b2)), str((0, 0)),
                        str((int(-b1 // m1), 0)), str((int(-b2 // m2), 0))],
                # 線に式を添える（点名は (1)(2) の答えなので付けない）。
                "label_equations": True},
        given={"scenario": scenario},
        context_slots={
            "ask_1": f"点{la}の座標を求めよ。",
            "ask_2": f"点{lb}、点{lc}の座標を求めよ。",
            "ask_3": f"三角形{la}{lb}{lc}の面積を求めよ。",
        },
        sub_questions=[
            _exam_l1_sub(ctx, label="(1)", asked="value", sol=pt_sol),
            _exam_l1_sub(ctx, label="(2)", asked="value", sol=int_sol),
            _exam_l1_sub(ctx, label="(3)", asked="value", sol=area_sol),
        ],
        visual_plan=VisualPlan(
            style="grid", labels=tick_labels_from_params(_grid_params(m1, b1, m2, b2)),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="line", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.exam_linear_guided_triangle"),
    )


def _grid_params(
    m1: object, b1: object, m2: object = None, b2: object = None
) -> dict[str, object]:
    """入試の座標セルの描画情報（直線1〜2本と、切片・原点が収まる範囲）。

    ★**答えの点は入れない。** 「面積が k 倍になる点 G を求めよ」の G を描いたら、
    答えを図に書いたことになる。描くのは本文が与えている直線と交点まで。
    """
    pts = [str((0, int(b1))), str((0, 0)), str((int(-int(b1) // int(m1)), 0))]
    out: dict[str, object] = {"a": str(m1), "b": str(b1)}
    if m2 is not None and b2 is not None:
        pts += [str((0, int(b2))), str((int(-int(b2) // int(m2)), 0))]
        out["extra_lines"] = [[str(m2), str(b2)]]
    out["pts"] = pts
    # ★線には式を添える（どちらの線がどの式か図から決まらなかった）。
    # **点名は付けない**——このセル群は交点や切片の座標そのものが答えなので、
    # 名前を打つと答えを図が言ってしまう。
    out["label_equations"] = True
    return out


@register_recipe(
    "math.exam_linear_area_multiple_point", provides_concepts=_EXAM_L1_AREA_MULTIPLE_CONCEPTS
)
def exam_linear_area_multiple_point_recipe(ctx: CellContext, rng: Rng) -> MR:
    """面積が k 倍になる x 軸上の点を自分で構成する（exam_l1.word_problem Lv4・誘導なし）。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    cands: list[tuple[int, int, int]] = []
    for m in p["slope_candidates"]:
        for b in p["intercept_candidates"]:
            for k in p["multiple_candidates"]:
                m_i, b_i, k_i = int(m), int(b), int(k)
                if m_i <= 0 or b_i <= 0 or k_i <= 1:
                    continue
                if (b_i * (k_i - 1)) % m_i:
                    continue  # 求める点の x 座標を整数にする
                # **直線と x 軸の交点も格子点にする。** 前は答えの点だけを見ていたので
                # 「y=6x+2 と x軸の交点」＝(-1/3, 0) という、図に取りにくい点が
                # 本文に出ていた（実物の入試問題の切片は整数）。
                if b_i % m_i:
                    continue
                cx = b_i * (k_i - 1) // m_i
                if cx <= 0 or not _no_leak({cx}, {m_i, b_i, k_i}):
                    continue
                cands.append((m_i, b_i, k_i))
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    m, b, k = cands[idx]
    (v,) = _draw_named_figures([3], rng)
    la, lb, lc = v

    sol = cast(
        Solution, REGISTRY.solver("math.point_on_x_axis_for_area_multiple")(m, b, k)
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    cpt = sympy.sympify(sol.answer.srepr)
    assert cpt[0] > 0 and cpt[1] == 0

    scenario = (
        f"座標平面上に直線 {_line_text(m, b)} があり、この直線と x軸、y軸との交点を"
        f"それぞれ{la}、{lb}とする。ただしOは原点とする。"
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"numbers": {"slope": m, "intercept": b, "multiple": k},
                "labels": la + lb + lc,
                **_grid_params(m, b),
                # ★x切片・y切片・原点は**答えではない**（答えは点 lc の座標）ので
                # 図に打つ。本文が名前を付けているのに図に無く、どの点を指して
                # いるのか分からなかった（2026-08-19 の外部評価の指摘）。
                "label_pts": [str((int(-b // m), 0)), str((0, int(b))), str((0, 0))],
                "label_names": [la, lb, "O"]},
        given={"scenario": scenario},
        context_slots={
            "ask_value": (
                f"x軸上の正の部分に点{lc}をとり、三角形{la}{lb}{lc}の面積が"
                f"三角形O{la}{lb}の面積の{k}倍になるようにしたい。"
                f"このときの点{lc}の座標を求めよ。"
            )
        },
        sub_questions=[_exam_l1_sub(ctx, label="(1)", asked="value", sol=sol)],
        # **点Gは描かない**（それが答え）。与えられた直線と2つの交点までを描く。
        visual_plan=VisualPlan(
            style="grid",
            labels=tick_labels_from_params(
                {**_grid_params(m, b), "label_names": [la, lb, "O"]}
            ),
            elements=[
                VisualElement(kind="grid", attrs={}),
                VisualElement(kind="axis", attrs={}),
                VisualElement(kind="line", attrs={}),
            ],
        ),
        provenance=Provenance(recipe="math.exam_linear_area_multiple_point"),
    )
