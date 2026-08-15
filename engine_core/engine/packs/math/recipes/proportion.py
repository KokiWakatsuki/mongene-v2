"""比例・反比例まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

C4（g1 関数・比例と反比例）クラスタの非 visual セル群（g1_l28/l29/l33）。乱数は
`engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8）。構成した値は独立ソルバ
（`engine.packs.math.solvers.proportion`）で再計算し、答えの一致を確認する（double-solve）。

- `math.evaluate_direct_proportion`（g1_l29.calculation Lv1/Lv2）
- `math.evaluate_inverse_proportion`（g1_l33.calculation Lv1/Lv2）
- `math.judge_functional_relation`（g1_l28.knowledge Lv2）
- `math.judge_direct_proportion_table`（g1_l29.knowledge Lv2）
- `math.judge_inverse_proportion_table`（g1_l33.knowledge Lv2）

narration には数字を書かない（鉄則⑦）。knowledge（asked=choice）の答えは ASCII 数字を
含めない（鉄則①）: 判別型セルの ChoiceAnswer は「〜といえる／〜とはいえない」のみで、
比例定数の値そのものは選択肢に含めない設計にする。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    ChoiceAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.core.verify.answer_size import answer_is_too_big, limits_for
from engine.packs.math.recipes.polynomial import _domain_candidates
from engine.packs.math.solvers.arithmetic import fmt_number


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# 式の表示は solver 側の実装を**そのまま使う**。ここに同じものを2つ持っていたので、
# 片方だけ直しても問題文は変わらなかった（`y = -62/5/x` が残った）。
from engine.packs.math.solvers.proportion import (  # noqa: E402
    _format_direct_proportion_expr as _fmt_direct_proportion_display,
)
from engine.packs.math.solvers.proportion import (  # noqa: E402
    _format_inverse_proportion_expr as _fmt_inverse_proportion_display,
)


# ---------------------------------------------------------------------------
# math.evaluate_direct_proportion（g1_l29.calculation Lv1/Lv2）
# y=ax に x=x0 を代入して y を求める。
# ---------------------------------------------------------------------------
_EVALUATE_DIRECT_PROPORTION_CONCEPTS = [
    "direct_proportion.evaluate_at_x",
]


@register_recipe("math.evaluate_direct_proportion", provides_concepts=_EVALUATE_DIRECT_PROPORTION_CONCEPTS)
def evaluate_direct_proportion(ctx: CellContext, rng: Rng) -> MR:
    """比例 y=ax に x=x0 を代入して y を求める（answer-first・calculation）。

    比例定数 a(≠0)・代入する x0(≠0) を選び、独立ソルバ `math.evaluate_direct_proportion`
    で y=a*x0 を再計算する（代入するだけなので構成＝解が自明に一致）。mode（Lv1="basic"／
    Lv2="signed"）は spec_level.params で指定し、solver 側の op 列を変える＝level_sep。
    答えは1つの数値 y（asked=value）。図は無し（calculation frame visual=none）。
    """
    p = ctx.spec_level.params
    mode = str(p["mode"])
    a = draw(p["slope_domain"], rng)
    x0 = draw(p["x_domain"], rng)

    a_s, x_s = sympy.nsimplify(a), sympy.nsimplify(x0)
    y_expected = a_s * x_s

    solver = REGISTRY.solver("math.evaluate_direct_proportion")
    sol = cast(Solution, solver(a_s, x_s, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(y_expected), (
        f"double-solve 不一致: recipe が構成した y {y_expected} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"a": str(a_s), "x0": str(x_s), "mode": mode},
        given={
            "expression": _fmt_direct_proportion_display(a_s),
            "input_value": f"x = {fmt_number(x_s)}",
        },
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_direct_proportion"),
    )


# ---------------------------------------------------------------------------
# math.evaluate_inverse_proportion（g1_l33.calculation Lv1/Lv2）
# y=a/x に x=x0 を代入して y を求める（forward）、または y=y0 から x を逆算する（backward）。
# ---------------------------------------------------------------------------
_EVALUATE_INVERSE_PROPORTION_CONCEPTS = [
    "inverse_proportion.evaluate_at_x",
    "inverse_proportion.solve_for_x",
]

# 答えが大きすぎたら引き直す回数（`pythagorean_find_value.py` と同じ考え）。
_ANSWER_SIZE_REDRAWS = 40


@register_recipe(
    "math.evaluate_inverse_proportion", provides_concepts=_EVALUATE_INVERSE_PROPORTION_CONCEPTS
)
def evaluate_inverse_proportion(ctx: CellContext, rng: Rng) -> MR:
    """反比例 y=a/x の値を求める（answer-first・calculation）。

    mode="forward"（Lv1）: 比例定数 a(≠0)・代入する x0(≠0) を選び、y=a/x0 を計算する。
    mode="backward"（Lv2）: 比例定数 a(≠0・負や分数を含む)・既知の y0(≠0) を選び、x=a/y0
    を逆に解いて求める。どちらも独立ソルバ `math.evaluate_inverse_proportion` で再計算する。
    答えは1つの数値（asked=value）。図は無し。
    """
    p = ctx.spec_level.params
    mode = str(p["mode"])
    if mode not in ("forward", "backward"):
        raise ValueError(f"未知の mode: {mode!r}")

    # **答えが約分できない大きな分数になる組は引き直す**（定義域はそのまま）。
    # 比例定数は約数の多い数（12の倍数中心）を並べてあるのに、x は −10〜10 を独立に
    # 引いていたので `y = 240/x` に `x = 7` が当たって `240/7` が出ていた。
    # 反比例の値を求める問題の答えが「240/7」では、割り算をした形にならない。
    limits = limits_for(ctx.spec_level)
    a = known = None
    for attempt in range(_ANSWER_SIZE_REDRAWS):
        attempt_rng = rng.spawn(attempt) if attempt else rng
        a = draw(p["slope_domain"], attempt_rng)
        known = draw(p["known_domain"], attempt_rng)
        if not answer_is_too_big(str(sympy.nsimplify(a) / sympy.nsimplify(known)), limits):
            break
    a_s, k_s = sympy.nsimplify(a), sympy.nsimplify(known)
    # forward: y=a/x0 を求める。backward: y0=a/x を x について解く（x=a/y0）。
    # どちらも同じ式変形 a/known になる（比例定数と既知値の役割が入れ替わるだけ）。
    result_expected = a_s / k_s

    solver = REGISTRY.solver("math.evaluate_inverse_proportion")
    sol = cast(Solution, solver(a_s, k_s, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(result_expected), (
        f"double-solve 不一致: recipe が構成した値 {result_expected} != solver 再計算 {sol.answer.srepr}"
    )

    expression = _fmt_inverse_proportion_display(a_s)
    if mode == "forward":
        given = {"expression": expression, "input_value": f"x = {fmt_number(k_s)}"}
    else:
        given = {"expression": expression, "input_value": f"y = {fmt_number(k_s)}"}

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"a": str(a_s), "known": str(k_s), "mode": mode},
        given=given,
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_inverse_proportion"),
    )


# ---------------------------------------------------------------------------
# math.judge_functional_relation（g1_l28.knowledge Lv2）
# 場面（2量の関係）が「yはxの関数」といえるかを判別する（answer-first・verify型）。
# ---------------------------------------------------------------------------
_JUDGE_FUNCTIONAL_RELATION_CONCEPTS = [
    "function.judge_functional_relation",
]

# (場面の説明テンプレ, is_functional) の対応表。テンプレは {n} に下限値等の数量を埋める
# 1スロットを持ち、dup 分散（surface の variety）に使う。x を決めても y が一意に決まらない
# 場面（体重等）は is_functional=False。
# (場面の説明テンプレ, is_functional, {n} の候補, {o} の候補)。
#
# **前は「1辺の長さが{n}cmより長い正方形」「{n}歳より年上の人」と書いていた。**
# なぜ 34 なのか、なぜ 63 歳なのかに理由が無い。判定は場面の構造だけで決まり、
# n の値は答えに一切関係しない——**重複率を通すためだけに文へ差し込んだ数**だった。
# 実物は「人の年齢 x 歳と、その人の体重 y kg」と書く。
#
# 直し方は「数を消す」ではなく「**意味のある数量に替える**」。
# 1個◯円・高さ◯cm・満水◯L はどれも場面が本当に持っている量で、
# 値が変わっても問いは壊れない。足りない広さは題材（{o}）で戻す。
_FUNCTIONAL_SCENARIO_TEMPLATES: list[tuple[str, bool, tuple[int, ...], tuple[str, ...]]] = [
    ("1辺の長さがx cmである{o}の周の長さy cm", True, (),
     ("正方形", "正三角形", "正五角形", "正六角形", "正八角形", "ひし形")),
    ("1辺の長さがx cmである{o}", True, (),
     ("正方形の面積y cm²", "立方体の体積y cm³", "立方体の表面積y cm²",
      "正方形の対角線の長さy cm", "正三角形の周の長さy cm")),
    ("半径がx cmである{o}", True, (),
     ("円の面積y cm²", "円の周の長さy cm", "球の表面積y cm²", "球の体積y cm³")),
    ("時速{n}kmでx時間走ったときの、進む道のりy km", True,
     (30, 40, 45, 50, 60, 70, 80, 90), ()),
    ("正x角形の{o}", True, (),
     ("内角の和y度", "対角線の本数y本", "辺の数y本", "外角の和y度")),
    ("面積がx cm²である長方形の、{o}", False, (),
     ("縦の長さy cm", "横の長さy cm", "周の長さy cm")),
    ("ある町のx月の、{o}", False, (),
     ("平均気温y℃", "降水量y mm", "日照時間y時間")),
    ("高さが{n}cmで決まっている三角形の、底辺の長さをx cmとするときの面積y cm²", True,
     tuple(range(2, 21)), ()),
    ("横の長さが{n}cmで決まっている長方形の、縦の長さをx cmとするときの面積y cm²", True,
     tuple(range(2, 21)), ()),
    ("1個{n}円の{o}をx個買ったときの、代金y円", True,
     tuple(range(30, 301, 10)),
     ("えん筆", "ノート", "消しゴム", "みかん", "りんご", "画用紙", "クリップ")),
    ("満水が{n}Lの水そうに毎分x Lずつ水を入れるときの、満水になるまでの時間y分", True,
     tuple(range(20, 201, 10)), ()),
    ("{n}kmの道のりを時速x kmで進むときの、かかる時間y時間", True,
     tuple(range(20, 301, 10)), ()),
    ("面積が{n}cm²である長方形の、縦の長さをx cmとするときの横の長さy cm", True,
     (12, 18, 24, 36, 48, 60, 72, 96), ()),
    ("x円の{o}を買って{n}円札で払ったときの、おつりy円", True,
     (1000, 2000, 5000), ("本", "おかし", "文ぼう具", "ケーキ")),
    ("自然数xの{o}", True, (),
     ("約数の個数y個", "正の平方根y", "2倍の数y", "各位の数の和y")),
    ("人の年齢をx歳とするときの、その人の{o}", False, (),
     ("体重y kg", "身長y cm", "1か月の読書時間y時間", "通学時間y分")),
    ("人の身長をx cmとするときの、その人の{o}", False, (),
     ("体重y kg", "座高y cm", "1日の歩数y歩")),
    ("ある日の最高気温をx℃とするときの、その日の{o}", False, (),
     ("最低気温y℃", "降水量y mm", "湿度y％")),
    ("{o}をx人とするときの、そのうち眼鏡をかけている人数y人", False, (),
     ("クラスの人数", "部活動の人数", "会場にいる人数")),
]


@register_recipe(
    "math.judge_functional_relation", provides_concepts=_JUDGE_FUNCTIONAL_RELATION_CONCEPTS
)
def judge_functional_relation(ctx: CellContext, rng: Rng) -> MR:
    """2量の関係が関数関係かを判別する（answer-first・knowledge verify型）。

    場面（2量の関係の説明文テンプレ）を answer-first で1つ選び、数量スロット n を引いて
    surface を分散する。場面ごとに is_functional が固定されている（判定自体は場面の構造
    だけで決まり、n の値は無関係）。独立ソルバ `math.judge_functional_relation` が
    is_functional フラグだけから再判定する（double-solve）。答えは ChoiceAnswer
    （数字トークンなし）。図なし。
    """
    idx = int(draw({"int_range": [0, len(_FUNCTIONAL_SCENARIO_TEMPLATES) - 1]}, rng))
    template, is_functional, n_cands, o_cands = _FUNCTIONAL_SCENARIO_TEMPLATES[idx]
    n = int(draw({"int_set": list(n_cands)}, rng)) if n_cands else 0
    o = str(draw(list(o_cands), rng)) if o_cands else ""
    statement = template.format(n=n, o=o)

    solver = REGISTRY.solver("math.judge_functional_relation")
    sol = cast(Solution, solver(is_functional))
    assert isinstance(sol.answer, ChoiceAnswer)
    expected = "yはxの関数であるといえる" if is_functional else "yはxの関数であるとはいえない"
    assert sol.answer.correct == expected, (
        f"double-solve 不一致: 構成 is_functional={is_functional}（{expected}）"
        f" != solver 判定 {sol.answer.correct}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        # 題材も載せる（載せないと dup_key から見えず、軸を増やしても重複率が下がらない）。
        params={"scenario_index": idx, "n": n, "item": o,
                "is_functional": str(is_functional)},
        given={"statement": statement},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.judge_functional_relation"),
    )


# ---------------------------------------------------------------------------
# math.judge_direct_proportion_table（g1_l29.knowledge Lv2）
# 表(x,yの対応)が比例かを判別する（answer-first・verify型）。
# ---------------------------------------------------------------------------
_JUDGE_DIRECT_PROPORTION_TABLE_CONCEPTS = [
    "direct_proportion.judge_table",
]


def _fmt_table(xs: list[sympy.Expr], ys: list[sympy.Expr]) -> str:
    x_row = "　".join(fmt_number(v) for v in xs)
    y_row = "　".join(fmt_number(v) for v in ys)
    return f"x：{x_row}\ny：{y_row}"


@register_recipe(
    "math.judge_direct_proportion_table", provides_concepts=_JUDGE_DIRECT_PROPORTION_TABLE_CONCEPTS
)
def judge_direct_proportion_table(ctx: CellContext, rng: Rng) -> MR:
    """表のx,yの対応が比例かを判別する（answer-first・knowledge verify型）。

    answer-first: is_proportional を先に決める。真なら比例定数 a(≠0)・x の値4つ(相異・非0)
    から y=a*x の表を作る。偽なら同じ表を作った後、1箇所の y の値を(商がずれるように)
    改変して商 y/x が一定でなくする。独立ソルバ `math.judge_direct_proportion_table` が
    x,y の数値列だけから商 y/x の一定性で再判定する（double-solve）。答えは ChoiceAnswer
    （「比例するといえる」／「比例するとはいえない」・digit-free＝鉄則①。比例定数の値
    そのものは選択肢に含めない）。図なし。
    """
    p = ctx.spec_level.params
    is_proportional = bool(int(draw({"int_set": [0, 1]}, rng)))
    a = sympy.nsimplify(draw(p["slope_domain"], rng))
    x_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["x_domain"])) if v != 0]
    # distinct な4つの x を集合サンプリングで確保する（重複時は再抽選）。
    xs_set: set[int] = set()
    for _ in range(200):
        v = int(draw({"int_set": x_cands}, rng))
        xs_set.add(v)
        if len(xs_set) >= 4:
            break
    xs = sorted(xs_set)[:4]
    xs_s = [sympy.Integer(v) for v in xs]
    ys_s = [a * x for x in xs_s]

    if not is_proportional:
        # 1箇所の y をずらして商 y/x を不一致にする（0にはしない・他の y と重複させない）。
        delta = sympy.nsimplify(draw(p["perturb_domain"], rng))
        idx = int(draw({"int_range": [0, len(ys_s) - 1]}, rng))
        perturbed = ys_s[idx] + delta * xs_s[idx]
        if perturbed == 0:
            perturbed = perturbed + xs_s[idx]
        ys_s[idx] = perturbed

    solver = REGISTRY.solver("math.judge_direct_proportion_table")
    sol = cast(Solution, solver([str(v) for v in xs_s], [str(v) for v in ys_s]))
    assert isinstance(sol.answer, ChoiceAnswer)
    ratios = [ys_s[i] / xs_s[i] for i in range(len(xs_s))]
    expected_proportional = all(r == ratios[0] for r in ratios)
    assert expected_proportional == is_proportional, (
        f"double-solve 不一致: 構成 is_proportional={is_proportional} "
        f"!= 実際の商一定性={expected_proportional}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "xs": [str(v) for v in xs_s],
            "ys": [str(v) for v in ys_s],
            "is_proportional": str(is_proportional),
        },
        given={"statement": _fmt_table(xs_s, ys_s)},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.judge_direct_proportion_table"),
    )


# ---------------------------------------------------------------------------
# math.judge_inverse_proportion_table（g1_l33.knowledge Lv2）
# 表(x,yの対応)が反比例かを判別する（answer-first・verify型）。
# ---------------------------------------------------------------------------
_JUDGE_INVERSE_PROPORTION_TABLE_CONCEPTS = [
    "inverse_proportion.judge_table",
]


@register_recipe(
    "math.judge_inverse_proportion_table",
    provides_concepts=_JUDGE_INVERSE_PROPORTION_TABLE_CONCEPTS,
)
def judge_inverse_proportion_table(ctx: CellContext, rng: Rng) -> MR:
    """表のx,yの対応が反比例かを判別する（answer-first・knowledge verify型）。

    構成順序（鉄則⑤: 退化はドメインで防ぐ・実行時分岐にしない）: まず相異な正の整数 x を
    4つ選び、それらの最小公倍数 L に整数倍率 m(≧1) をかけて比例定数 a=m·L とする。すると
    a はすべての x で必ず割り切れ、y=a/x が常に整数になる（約数探索の実行時分岐が不要）。
    is_inverse を先に決め、偽の場合だけ1箇所の y をずらして積 xy が一定でなくする。独立ソルバ
    `math.judge_inverse_proportion_table` が x,y の数値列だけから積 xy の一定性で再判定する
    （double-solve）。答えは ChoiceAnswer（digit-free・鉄則①）。図なし。
    """
    p = ctx.spec_level.params
    is_inverse = bool(int(draw({"int_set": [0, 1]}, rng)))
    x_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["x_domain"])) if v != 0]

    xs_set: set[int] = set()
    for _ in range(200):
        v = int(draw({"int_set": x_cands}, rng))
        xs_set.add(v)
        if len(xs_set) >= 4:
            break
    xs = sorted(xs_set)[:4]
    lcm_x = 1
    for v in xs:
        lcm_x = sympy.ilcm(lcm_x, v)
    multiplier = int(draw(p["multiplier_domain"], rng))  # ≧1
    a_s = sympy.Integer(lcm_x * multiplier)

    xs_s = [sympy.Integer(v) for v in xs]
    ys_s = [a_s / x for x in xs_s]

    if not is_inverse:
        delta = sympy.nsimplify(draw(p["perturb_domain"], rng))
        idx = int(draw({"int_range": [0, len(ys_s) - 1]}, rng))
        perturbed = ys_s[idx] + delta
        if perturbed == 0:
            perturbed = perturbed + 1
        ys_s[idx] = perturbed

    solver = REGISTRY.solver("math.judge_inverse_proportion_table")
    sol = cast(Solution, solver([str(v) for v in xs_s], [str(v) for v in ys_s]))
    assert isinstance(sol.answer, ChoiceAnswer)
    products = [xs_s[i] * ys_s[i] for i in range(len(xs_s))]
    expected_inverse = all(pr == products[0] for pr in products)
    assert expected_inverse == is_inverse, (
        f"double-solve 不一致: 構成 is_inverse={is_inverse} != 実際の積一定性={expected_inverse}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="choice",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={
            "xs": [str(v) for v in xs_s],
            "ys": [str(v) for v in ys_s],
            "is_inverse": str(is_inverse),
        },
        given={"statement": _fmt_table(xs_s, ys_s)},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.judge_inverse_proportion_table"),
    )


# ---------------------------------------------------------------------------
# math.solve_direct_proportion_from_point（g1_l32.find_value Lv1/Lv2）
# 比例が通る1点 (x0,y0) から比例定数 a=y0/x0 を求め、式 y=ax を決める。
# ---------------------------------------------------------------------------
_SOLVE_DIRECT_PROPORTION_FROM_POINT_CONCEPTS = ["direct_proportion.solve_from_point"]


@register_recipe(
    "math.solve_direct_proportion_from_point",
    provides_concepts=_SOLVE_DIRECT_PROPORTION_FROM_POINT_CONCEPTS,
)
def solve_direct_proportion_from_point_recipe(ctx: CellContext, rng: Rng) -> MR:
    """比例が通る1点から比例定数を求め、式 y=ax を決める（answer-first・find_value）。

    mode="integer"（Lv1）: x0(≠0) と整数倍率 k(≠0) を選び y0=k*x0 とする（a=k は整数）。
    mode="fraction"（Lv2）: x0(≥2) と非0の余り r(0<r<x0) を選び y0=k*x0+r とする
    （a=y0/x0 は必ず既約分数になり、割り切れる退化を構成的に排除する＝鉄則⑤）。
    独立ソルバ `math.solve_direct_proportion_from_point` で式を再計算する（double-solve）。
    答えは式 y=ax（asked=expression）。図は無し。
    """
    p = ctx.spec_level.params
    mode = str(p["mode"])
    multiplier_cands = _domain_candidates(cast("dict[str, object]", p["multiplier_domain"]))
    if mode == "integer":
        x0 = int(draw(p["x_domain"], rng))
        k = int(draw({"int_set": [v for v in multiplier_cands if v != 0]}, rng))
        y0 = k * x0
    else:  # fraction
        x0 = int(draw(p["x_fraction_domain"], rng))
        k = int(draw({"int_set": multiplier_cands}, rng))
        r = int(draw({"int_range": [1, x0 - 1]}, rng))
        y0 = k * x0 + r

    x0_s, y0_s = sympy.Integer(x0), sympy.Integer(y0)
    a_expected = y0_s / x0_s

    solver = REGISTRY.solver("math.solve_direct_proportion_from_point")
    sol = cast(Solution, solver(x0_s, y0_s, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(a_expected * sympy.Symbol("x")), (
        f"double-solve 不一致: 構成 a={a_expected} != solver 再計算 {sol.answer.srepr}"
    )

    statement = f"yはxに比例し、x={fmt_number(x0_s)}のときy={fmt_number(y0_s)}である。yをxの式で表せ"

    sub_question = SubQuestionMR(
        label="(1)", asked="expression", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"x0": str(x0_s), "y0": str(y0_s), "mode": mode},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.solve_direct_proportion_from_point"),
    )


# ---------------------------------------------------------------------------
# math.solve_inverse_proportion_from_point（g1_l35.find_value Lv1/Lv2）
# 反比例が通る1点 (x0,y0) から比例定数 a=x0*y0 を求め、式 y=a/x を決める。
# ---------------------------------------------------------------------------
_SOLVE_INVERSE_PROPORTION_FROM_POINT_CONCEPTS = ["inverse_proportion.solve_from_point"]


@register_recipe(
    "math.solve_inverse_proportion_from_point",
    provides_concepts=_SOLVE_INVERSE_PROPORTION_FROM_POINT_CONCEPTS,
)
def solve_inverse_proportion_from_point_recipe(ctx: CellContext, rng: Rng) -> MR:
    """反比例が通る1点から比例定数を求め、式 y=a/x を決める（answer-first・find_value）。

    mode="basic"（Lv1）: 正の x0・y0(いずれも≠0)を選び a=x0*y0 とする。
    mode="signed"（Lv2）: x0・y0 の少なくとも一方に負の値を許し、符号確認の1手順を増やす
    （level_sep）。独立ソルバ `math.solve_inverse_proportion_from_point` で式を再計算する
    （double-solve）。答えは式 y=a/x（asked=expression）。図は無し。
    """
    p = ctx.spec_level.params
    mode = str(p["mode"])
    domain_key = "xy_domain" if mode == "basic" else "xy_signed_domain"
    xy_cands = [v for v in _domain_candidates(cast("dict[str, object]", p[domain_key])) if v != 0]
    x0 = int(draw({"int_set": xy_cands}, rng))
    y0 = int(draw({"int_set": xy_cands}, rng))

    x0_s, y0_s = sympy.Integer(x0), sympy.Integer(y0)
    a_expected = x0_s * y0_s

    solver = REGISTRY.solver("math.solve_inverse_proportion_from_point")
    sol = cast(Solution, solver(x0_s, y0_s, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert sol.answer.srepr == sympy.srepr(a_expected / sympy.Symbol("x")), (
        f"double-solve 不一致: 構成 a={a_expected} != solver 再計算 {sol.answer.srepr}"
    )

    statement = f"yはxに反比例し、x={fmt_number(x0_s)}のときy={fmt_number(y0_s)}である。yをxの式で表せ"

    sub_question = SubQuestionMR(
        label="(1)", asked="expression", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"x0": str(x0_s), "y0": str(y0_s), "mode": mode},
        given={"condition": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.solve_inverse_proportion_from_point"),
    )


# ---------------------------------------------------------------------------
# math.judge_proportion_graph_direction（g1_l31.knowledge Lv1）
# ---------------------------------------------------------------------------
_JUDGE_PROPORTION_GRAPH_DIRECTION_CONCEPTS = ["proportion.judge_graph_direction"]


@register_recipe(
    "math.judge_proportion_graph_direction",
    provides_concepts=_JUDGE_PROPORTION_GRAPH_DIRECTION_CONCEPTS,
)
def judge_proportion_graph_direction_recipe(ctx: CellContext, rng: Rng) -> MR:
    """比例定数の符号から比例グラフの向きを判別する（answer-first・knowledge判別型）。"""
    p = ctx.spec_level.params
    is_a_positive = bool(int(draw({"int_set": [0, 1]}, rng)))
    a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]
    a = int(draw({"int_set": [v for v in a_cands if (v > 0) == is_a_positive]}, rng))

    solver = REGISTRY.solver("math.judge_proportion_graph_direction")
    sol = cast(Solution, solver(is_a_positive))
    assert isinstance(sol.answer, ChoiceAnswer)

    statement = (
        f"比例y={fmt_number(sympy.Integer(a))}xのグラフについて、次の文の正誤を答えよ。"
        "「a<0のとき、グラフは右上がりの直線になる。」また、比例のグラフは必ずどんな点を通るか答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"a": a, "is_a_positive": str(is_a_positive)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_proportion_graph_direction"),
    )


# ---------------------------------------------------------------------------
# math.judge_hyperbola_quadrants（g1_l34.knowledge Lv1）
# ---------------------------------------------------------------------------
_JUDGE_HYPERBOLA_QUADRANTS_CONCEPTS = ["inverse_proportion.judge_hyperbola_quadrants"]


@register_recipe(
    "math.judge_hyperbola_quadrants", provides_concepts=_JUDGE_HYPERBOLA_QUADRANTS_CONCEPTS
)
def judge_hyperbola_quadrants_recipe(ctx: CellContext, rng: Rng) -> MR:
    """比例定数の符号から双曲線がどの象限にあるかを判別する（answer-first・knowledge判別型）。"""
    p = ctx.spec_level.params
    is_a_positive = bool(int(draw({"int_set": [0, 1]}, rng)))
    a_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["a_domain"])) if v != 0]
    a = int(draw({"int_set": [v for v in a_cands if (v > 0) == is_a_positive]}, rng))

    solver = REGISTRY.solver("math.judge_hyperbola_quadrants")
    sol = cast(Solution, solver(is_a_positive))
    assert isinstance(sol.answer, ChoiceAnswer)

    # 前の問題文は「次の文の正誤を答えよ。『a>0のとき、双曲線は第1象限と第3象限に
    # ある。』」だった。**問いと答えが食い違っていた**——正誤を問うているのに、
    # 選択肢は「右上と左下の部分にある（…）」という場所の記述で、正/誤ではない。
    # しかも a の値（負のこともある）と、引用文の「a>0のとき」が噛み合っていない。
    # 「象限」も中学の教科書に無い用語（高校で扱う）。問いを答えの形に合わせた。
    statement = (
        f"反比例y={fmt_number(sympy.Integer(a))}/xのグラフである双曲線は、"
        "座標平面の右上と左下の部分と、左上と右下の部分の、どちらにあるか答えよ。"
        "また、双曲線はx軸・y軸と交わるかどうかも答えよ"
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="choice", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"a": a, "is_a_positive": str(is_a_positive)},
        given={"statement": statement}, sub_questions=[sub_question], visual_plan=None,
        provenance=Provenance(recipe="math.judge_hyperbola_quadrants"),
    )


__all__ = [
    "evaluate_direct_proportion",
    "evaluate_inverse_proportion",
    "judge_functional_relation",
    "judge_direct_proportion_table",
    "judge_inverse_proportion_table",
    "solve_direct_proportion_from_point_recipe",
    "solve_inverse_proportion_from_point_recipe",
    "judge_proportion_graph_direction_recipe",
    "judge_hyperbola_quadrants_recipe",
]
