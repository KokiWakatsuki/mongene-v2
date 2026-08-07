"""動点（正方形の辺上を動く点）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は正方形の1辺 s・速さ v・経過時間 t を answer-first で構成し、独立ソルバ
math.solve_moving_point_area（`engine/packs/math/solvers/motion.py`）で三角形 APD の
面積を再計算する（double-solve）。visual は不要（座標幾何の数式のみで完結）。

C3（g3_l31.find_value・2次方程式の利用「動点」）クラスタ。乱数は
`engine.core.rng.draw` 以外で解釈しない。
"""
from __future__ import annotations

from typing import Any, cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_distinct_points
from engine.packs.math.visuals.graph import render_segment_solution_svg, tick_labels_from_params

_MOTION_CONCEPTS = [
    "motion.area_single_segment",
    "motion.area_two_segment",
]

_AREA_TIME_GRAPH_CONCEPTS = [
    "motion.area_time_graph_segment",
]

_WP_TWO_POINTS_CONCEPTS = [
    "motion.word_problem_two_points_area",
]

_WP_ALL_TIMES_CONCEPTS = [
    "motion.word_problem_area_all_times",
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


@register_recipe("math.solve_moving_point_area", provides_concepts=_MOTION_CONCEPTS)
def solve_moving_point_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """正方形の辺上を動く点 P による三角形 APD の面積を求める MR を組む（C3 g3_l31.find_value）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "single_segment":
        s, v, t, condition = _construct_single_segment(rng)
    elif mode == "two_segment":
        s, v, t, condition = _construct_two_segment(rng)
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.solve_moving_point_area")
    sol = cast(Solution, solver(s, v, t, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 独立に構成した s,v,t から shoelace 公式で再計算した面積と一致する（.equals で
    # 堅牢にゼロ判定）。
    expected = _expected_area(s, v, t, mode)
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: s={s},v={v},t={t},mode={mode} の面積 {expected} != {sol.answer.srepr}"
    )
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={"s": s, "v": v, "t": t, "mode": mode},
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.solve_moving_point_area"),
    )


def _expected_area(s: int, v: int, t: int, mode: str) -> sympy.Rational:
    """独立検証用: shoelace 公式を素直に展開した式で面積を再計算する。"""
    s_v, d = sympy.Integer(s), sympy.Integer(v) * sympy.Integer(t)
    if mode == "single_segment":
        px, py = d, sympy.Integer(0)
    else:
        px, py = s_v, d - s_v
    ax, ay, dx, dy = sympy.Integer(0), sympy.Integer(0), sympy.Integer(0), s_v
    return sympy.Rational(1, 2) * sympy.Abs(ax * (py - dy) + px * (dy - ay) + dx * (ay - py))


def _construct_single_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv2: 点 P が辺 AB 上（1区間）にあるときの構成。

    速さ v・経過時間 t を先に決め AP の長さ p=v·t を求め、1辺 s は p より大きい偶数
    （面積 p·s/2 を整数にするため・鉄則⑤: 構成時に整数解を保証）に絞って引く。
    """
    v = int(draw({"int_range": [1, 5]}, rng))
    t = int(draw({"int_range": [2, 10]}, rng))
    p = v * t
    s_cands = [x for x in range(p + 2, p + 42) if x % 2 == 0]
    s = int(draw({"int_set": s_cands}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDで、点PはAを出発し辺AB上を毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


def _construct_two_segment(rng: Rng) -> tuple[int, int, int, str]:
    """g3_l31.find_value Lv3: 点 P が A→B→C の2区間目（辺 BC 上）にあるときの構成。

    1辺 s は偶数（面積 s²/2 を整数にするため）に限定し、速さ v から経過距離
    d=v·t が s<d<2s（確実に2区間目）となる t の範囲を計算し、その範囲から引く
    （鉄則⑤: 実行時の場合分け判定ではなく構成時に区間を保証）。
    """
    s = int(draw({"int_set": list(range(6, 41, 2))}, rng))
    v = int(draw({"int_range": [1, 4]}, rng))
    t_lo = s // v + 1
    t_hi = (2 * s - 1) // v
    t = int(draw({"int_range": [t_lo, t_hi]}, rng))
    condition = (
        f"1辺が {s}cm の正方形ABCDの辺上を、点PがA→B→Cの順に毎秒{v}cmで動く。"
        f"出発してから{t}秒後の三角形APDの面積を求めよ"
    )
    return s, v, t, condition


@register_recipe("math.draw_area_time_graph_segment", provides_concepts=_AREA_TIME_GRAPH_CONCEPTS)
def draw_area_time_graph_segment(ctx: CellContext, rng: Rng) -> MR:
    """動点がつくる三角形の面積を、時間 x の関数のグラフ（線分）としてかく（g3_l31.graph_table Lv2）。

    正方形の1辺 s・速さ v で点 P が辺上を動く間、面積 y は時間 x の1次関数
    y=(s·v/2)x（切片 0・底辺 s 固定／高さ=v·x）になる。変域は x∈[0, t_end]（t_end=s/v＝P が
    向かいの頂点に達する時刻）で、両端とも到達の瞬間を含む＝閉区間。
    答えは GraphAnswer（両端点の特徴集合）。独立ソルバ math.solve_moving_point_area
    （shoelace 公式・find_value 側と共有）で両端の面積を再計算し、式 y=(s·v/2)x の値と
    一致することを assert する（幾何の導出と式変形の2経路で検証）。
    端点特徴・描画・checker は g2_l23.graph_table の既存部品
    （math.draw_segment_features / render_segment_solution_svg /
    math.draw_area_time_graph_segment.double_solve）をそのまま再利用する。

    図は時間 x 秒と面積 y cm² という**単位の違う2量**のグラフなので、座標平面ではなく
    量-量グラフとして描く（params の grid_mode="quantity"＝第1象限のみ・軸ごとに独立な
    切りのよい目盛間隔。y は最大 s²/2 まで伸びるため 1 刻みでは方眼が潰れる）。
    """
    p = ctx.spec_level.params
    s, v, t_end, labels_txt, condition = _construct_graph_segment(p, rng)

    area_solver = REGISTRY.solver("math.solve_moving_point_area")
    lo_sol = cast(Solution, area_solver(s, v, 0, "single_segment"))
    hi_sol = cast(Solution, area_solver(s, v, t_end, "single_segment"))
    assert isinstance(lo_sol.answer, SymbolicAnswer)
    assert isinstance(hi_sol.answer, SymbolicAnswer)
    y_lo_geom = sympy.sympify(lo_sol.answer.srepr)
    y_hi_geom = sympy.sympify(hi_sol.answer.srepr)

    a_s = sympy.Rational(s * v, 2)
    b_s = sympy.Integer(0)
    x_lo_s, x_hi_s = sympy.Integer(0), sympy.Integer(t_end)
    y_lo, y_hi = a_s * x_lo_s + b_s, a_s * x_hi_s + b_s
    assert (y_lo - y_lo_geom).equals(0) and (y_hi - y_hi_geom).equals(0), (
        f"面積の式 y=(s·v/2)x と shoelace 再計算が不一致: s={s}, v={v}, t_end={t_end}"
    )

    features_solver = REGISTRY.solver("math.draw_segment_features")
    sol = cast(Solution, features_solver(a_s, b_s, x_lo_s, x_hi_s, True, True))
    assert isinstance(sol.answer, GraphAnswer)

    params: dict[str, Any] = {
        "a": str(a_s), "b": str(b_s),
        "seg_x_lo": str(x_lo_s), "seg_x_hi": str(x_hi_s),
        "closed_lo": True, "closed_hi": True,
        "pts": [str((x_lo_s, y_lo)), str((x_hi_s, y_hi))],
        # 時間-面積のグラフ＝量-量グラフとして描く（visuals/graph.py の opt-in モード）
        "grid_mode": "quantity",
        # 場面の構成値と点名（dup_key は params のみを見るため、実際に振っている
        # 自由度はすべて params に残す＝多様性を測定に反映させる）
        "side": s, "speed": v, "t_end": t_end, "labels": labels_txt,
    }
    solution_svg = render_segment_solution_svg(params)
    answer = GraphAnswer(features=sol.answer.features, solution_svg_ref=solution_svg)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="draw_segment",
        answer=answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    visual_plan = VisualPlan(
        style="grid",
        labels=tick_labels_from_params(params),
        elements=[VisualElement(kind="grid", attrs={}), VisualElement(kind="axis", attrs={})],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.draw_area_time_graph_segment"),
    )


def _construct_graph_segment(
    p: dict[str, Any], rng: Rng
) -> tuple[int, int, int, str, str]:
    """速さ v と到達時刻 t_end を先に引き、1辺 s=v·t_end を逆算して場面を構成する。

    s を約数条件で絞る代わりに **s を v·t_end から作る**ことで、t_end=s/v が整数
    （＝変域の右端が目盛にのる）ことを構成時に保証する（鉄則②）。面積 s²/2 を整数に
    保つため s は偶数＝v·t_end が偶数になる組だけを候補にする（鉄則⑤）。
    点名は正方形の4頂点＋動点の5つを相異に引く（surface の自由度＝dup 分散。
    session29 の教訓により params にも残す）。
    """
    side_max = int(p["side_max"])
    pairs = [
        (int(v), int(t))
        for v in p["speed_candidates"]
        for t in p["t_end_candidates"]
        if (int(v) * int(t)) % 2 == 0 and int(v) * int(t) <= side_max
    ]
    idx = int(draw({"int_set": list(range(len(pairs)))}, rng))
    v, t_end = pairs[idx]
    s = v * t_end

    la, lb, lc, ld, lp = _draw_distinct_points(5, rng)
    condition = (
        f"1辺が{s}cmの正方形{la}{lb}{lc}{ld}で、点{lp}は{la}を出発し、"
        f"辺{la}{lb}上を毎秒{v}cmの速さで{lb}まで動く。出発してからの時間をx秒、"
        f"三角形{la}{lp}{ld}の面積をy cm²とするとき、xが0から{t_end}まで変化する"
        f"ときのxとyの関係を表すグラフをかけ"
    )
    return s, v, t_end, la + lb + lc + ld + lp, condition


# ---------------------------------------------------------------------------
# g3_l31.word_problem Lv3 / Lv4（2次方程式の利用・動点）
#
# form=word_problem の frame は given ∈ {scenario, quantities}・asked ∈ {formulation,
# value}。テンプレは既存の wp_linear_guided_v1（誘導あり2小問）/ wp_linear_solo_v1
# （誘導なし1小問）をそのまま使う（場面文と小問文は context_slots から差し込む規約）。
#
# 【params に何を置いたか】word_problem の params 忠実性契約
# （engine_tests/contract/test_word_problem_params_faithfulness.py）に従い、
# `numbers` には**本文に現れる数**（正方形の1辺・速さ・与えられた面積）だけを置く。
# 答え（時刻・面積の式）と導出値（区間の境界 s/v など）は params に置かず、
# checker は numbers だけから solver を呼び直して解き直す。
# 点名は dup の自由度なので params に残す（session29 の教訓）。
# ---------------------------------------------------------------------------
# 面積の単位 "cm²" の右肩の 2 は、G-Q5t の数値トークン抽出では本文の数値 `2` として
# 読まれる（BRIEF の失敗パターン#2 と同じ構造）。したがって答えが 2 になる構成は
# 必ず漏洩と判定されるので、構成の段階で外す。
_AREA_UNIT_TOKEN = 2


def _wp_numbers(side: int, speed: int, area: int) -> dict[str, str]:
    return {"side": str(side), "speed": str(speed), "area": str(area)}


def _wp_sub(
    ctx: CellContext, *, label: str, asked: str, sol: Solution
) -> SubQuestionMR:
    return SubQuestionMR(
        label=label,
        asked=asked,
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )


@register_recipe(
    "math.word_problem_moving_points_area", provides_concepts=_WP_TWO_POINTS_CONCEPTS
)
def word_problem_moving_points_area_recipe(ctx: CellContext, rng: Rng) -> MR:
    """2点が直交2辺を同時に動く動点の文章題（g3_l31.word_problem Lv3・誘導あり2小問）。

    台帳 example どおり、点 P は辺 AB 上・点 Q は辺 AD 上を同じ速さで同時に動く。
    直角をはさむ2辺がともに v·x になるので、三角形 APQ の面積は x の**2次式**
    （＝2次方程式の利用として成立する。P だけが動く三角形 APD は1次式にしかならない）。
      (1) 面積を x の式で表せ（asked=formulation）
      (2) 面積が与えられた値になるのは何秒後か（asked=value・2次方程式を解く）

    answer-first: 先に「答えになる時刻 t0」と速さ v を引いて面積 area=(v²/2)t0² を
    決め、正方形の1辺 s は v·t0 より大きい値から引く（＝t0 の時点で P・Q が
    まだ辺の上にいることを構成時に保証する。実行時の場合分け判定にしない）。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    s, v, area, labels_txt, scenario, quantities, ask_f, ask_v = _construct_two_points(p, rng)

    expr_sol = cast(Solution, REGISTRY.solver("math.express_moving_points_area")(v))
    time_sol = cast(Solution, REGISTRY.solver("math.solve_moving_points_area_time")(v, area))
    assert isinstance(expr_sol.answer, SymbolicAnswer)
    assert isinstance(time_sol.answer, SymbolicAnswer)
    # 恒真: (1) の式に (2) の時刻を代入すると、本文で与えた面積に戻る。
    x = sympy.Symbol("x")
    expr = sympy.sympify(expr_sol.answer.srepr)
    t0 = sympy.sympify(time_sol.answer.srepr)
    assert (expr.subs(x, t0) - sympy.Integer(area)).equals(0), (
        f"(1) の式と (2) の時刻が整合しない: {expr} at {t0} != {area}"
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"numbers": _wp_numbers(s, v, area), "labels": labels_txt},
        given={"scenario": scenario, "quantities": quantities},
        context_slots={"ask_formulation": ask_f, "ask_value": ask_v},
        sub_questions=[
            _wp_sub(ctx, label="(1)", asked="formulation", sol=expr_sol),
            _wp_sub(ctx, label="(2)", asked="value", sol=time_sol),
        ],
        visual_plan=None,
        provenance=Provenance(recipe="math.word_problem_moving_points_area"),
    )


def _construct_two_points(
    p: dict[str, Any], rng: Rng
) -> tuple[int, int, int, str, str, str, str, str]:
    """(1辺, 速さ, 面積, 点名, 場面文, 変数設定文, 小問1文, 小問2文)。

    【組合せ数】(速さ, 答えの時刻) の組を列挙してから 1辺を引く。速さ4通り×時刻9通りの
    うち v·t0 が偶数になる組（面積が整数）が約26通り、1辺は v·t0 より大きい偶数を20通り
    ⇒ 約520通り（閾の250通りを超える）。点名は dup_key に効くのでさらに広い。
    """
    pairs = [
        (int(v), int(t))
        for v in p["speed_candidates"]
        for t in p["answer_time_candidates"]
        # 面積 (v²/2)t² が整数になる組だけ（構成時に整数を保証する＝鉄則⑤）
        if (int(v) * int(t)) % 2 == 0
        # 答えの時刻が本文の数値と一致すると「答えが本文に出ている」状態になる。
        # 特に 2 は本文の "cm²" から数値トークンとして抽出されるので必ず外す
        # （BRIEF の失敗パターン#2 と同じ構造）。
        and int(t) not in (_AREA_UNIT_TOKEN, int(v))
    ]
    idx = int(draw({"int_set": list(range(len(pairs)))}, rng))
    v, t0 = pairs[idx]
    area = (v * t0) ** 2 // 2
    reach = v * t0
    # 1辺は v·t0 より大きい偶数（＝t0 の時点で P・Q がまだ辺の上にいる）。
    s_cands = [
        x
        for x in range(reach + 2, reach + 2 + 2 * int(p["side_choices"]), 2)
        if x != t0
    ]
    s = int(draw({"int_set": s_cands}, rng))
    assert t0 != area, "答えの時刻が本文の面積と一致している"

    la, lb, lc, ld, lp, lq = _draw_distinct_points(6, rng)
    scenario = (
        f"1辺が{s}cmの正方形{la}{lb}{lc}{ld}で、点{lp}は{la}を出発して辺{la}{lb}上を"
        f"{lb}まで毎秒{v}cmの速さで動き、点{lq}は同時に{la}を出発して辺{la}{ld}上を"
        f"{ld}まで毎秒{v}cmの速さで動く。"
    )
    quantities = (
        f"点{lp}、点{lq}が出発してからx秒後について、次の問いに答えよ。"
    )
    ask_f = f"三角形{la}{lp}{lq}の面積をy cm²として、yをxの式で表せ。"
    ask_v = f"三角形{la}{lp}{lq}の面積が{area}cm²になるのは何秒後か求めよ。"
    return s, v, area, la + lb + lc + ld + lp + lq, scenario, quantities, ask_f, ask_v


@register_recipe(
    "math.word_problem_moving_point_all_times", provides_concepts=_WP_ALL_TIMES_CONCEPTS
)
def word_problem_moving_point_all_times_recipe(ctx: CellContext, rng: Rng) -> MR:
    """3辺を渡る動点・面積が与えられた値になる時刻をすべて求める（g3_l31.word_problem Lv4）。

    誘導なし1小問。区間ごとに面積の式が変わる（増加 → 一定 → 減少）ので、
    答えは2つあり、第3区間を見落とすと落とす＝場合分けが答えに効く。
    経路を台帳 example の A→B→C から A→B→C→D に延ばした理由は
    solvers/motion.py の当該ソルバの docstring を参照。
    """
    p = cast("dict[str, Any]", ctx.spec_level.params)
    s, v, area, labels_txt, scenario, ask_v = _construct_all_times(p, rng)

    sol = cast(
        Solution, REGISTRY.solver("math.solve_moving_point_area_all_times")(s, v, area)
    )
    assert isinstance(sol.answer, SymbolicAnswer)
    times = sympy.sympify(sol.answer.srepr)
    assert len(times) == 2 and times[0] < times[1], f"答えが2つにならない: {times}"

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"numbers": _wp_numbers(s, v, area), "labels": labels_txt},
        given={"scenario": scenario},
        context_slots={"ask_value": ask_v},
        sub_questions=[_wp_sub(ctx, label="(1)", asked="value", sol=sol)],
        visual_plan=None,
        provenance=Provenance(recipe="math.word_problem_moving_point_all_times"),
    )


def _construct_all_times(p: dict[str, Any], rng: Rng) -> tuple[int, int, int, str, str, str]:
    """(1辺, 速さ, 面積, 点名, 場面文, 小問文)。

    【組合せ数】1辺は偶数10通り、速さは 3s が割り切れる約数（区間の境界と答えが
    整数になる）、答えの時刻 t1 は第1区間の内側から。組は列挙してから引くので
    実効で数百通り。点名 6 文字ぶんの自由度がさらに乗る。

    答えは t1 と t3 = 3s/v − t1 の2つ。t1 を第1区間 (0, s/v) の内側に取れば
    t3 は必ず第3区間 (2s/v, 3s/v) の内側に入る（対称性）。
    """
    triples: list[tuple[int, int, int]] = []
    for s in p["side_candidates"]:
        s_i = int(s)
        for v in p["speed_candidates"]:
            v_i = int(v)
            if (3 * s_i) % v_i or s_i % v_i:
                continue  # 区間の境界 s/v・2s/v・3s/v を整数にする
            for t1 in range(1, s_i // v_i):
                if (s_i * v_i * t1) % 2:
                    continue  # 面積を整数にする
                area = s_i * v_i * t1 // 2
                if area >= s_i**2 // 2:
                    continue  # 一定区間の面積以上だと増減する区間に解が立たない
                t3 = 3 * s_i // v_i - t1
                # 答えの時刻が本文の数値（1辺・速さ・面積）や "cm²" 由来の 2 と
                # 一致すると G-Q5t が漏洩と判定する。構成の段階で外す。
                if {t1, t3} & {s_i, v_i, area, _AREA_UNIT_TOKEN}:
                    continue
                triples.append((s_i, v_i, area))
    idx = int(draw({"int_set": list(range(len(triples)))}, rng))
    s, v, area = triples[idx]

    la, lb, lc, ld, lp = _draw_distinct_points(5, rng)
    scenario = (
        f"1辺が{s}cmの正方形{la}{lb}{lc}{ld}の周上を、点{lp}が{la}を出発して"
        f"{la}→{lb}→{lc}→{ld}の順に毎秒{v}cmの速さで{ld}まで動く。"
    )
    ask_v = (
        f"点{lp}が出発してからx秒後の三角形{la}{lp}{ld}の面積が{area}cm²になるのは"
        f"何秒後か、すべて求めよ。"
    )
    return s, v, area, la + lb + lc + ld + lp, scenario, ask_v


# ---------------------------------------------------------------------------
# g3_l38.word_problem Lv4: グラフを構成してから時刻をすべて求める（誘導なし・融合）
#
# 【なぜ word_problem で作図の小問を持つのか】台帳 example は「x と y の関係を
# グラフに表し、面積が S cm² になる時刻をすべて求めよ」＝場面文を読んで自分で区間に
# 分け、グラフを構成してから答えるところまでが一続きの問い。graph_table 側に置くと
# 場面文（scenario）が使えないので、word_problem の asked に `draw_graph` を足した
# （frames.py の当該コメント参照）。以前このセルが「作図小問を含むため対象外」と
# されていたのは、この frame 制約が理由だった。
#
# 【g3_l31.word_problem Lv4 との差】数の核（面積が S になる時刻）は共有するが、
# こちらは**グラフの構成そのものが採点対象**（折れ点4つ）で、asked も op 列も違う。
# 経路が A→B→C→D なのは両者に共通（2区間だと答えが1つに潰れる＝退化。
# solvers/motion.py の `solve_moving_point_area_all_times` の docstring 参照）。
# ---------------------------------------------------------------------------
_WP_GRAPH_AND_TIMES_CONCEPTS = [
    "quadratic_function.word_problem_area_graph_and_times",
]


@register_recipe(
    "math.word_problem_area_graph_and_times",
    provides_concepts=_WP_GRAPH_AND_TIMES_CONCEPTS,
)
def word_problem_area_graph_and_times_recipe(ctx: CellContext, rng: Rng) -> MR:
    """面積のグラフをかき、指定の面積になる時刻をすべて求める（g3_l38.word_problem Lv4）。"""
    p = cast("dict[str, Any]", ctx.spec_level.params)
    s, v, area, labels_txt, scenario, ask = _construct_graph_and_times(p, rng)

    graph_sol = cast(
        Solution, REGISTRY.solver("math.draw_three_interval_area_graph_features")(s, v)
    )
    times_sol = cast(
        Solution, REGISTRY.solver("math.solve_moving_point_area_all_times")(s, v, area)
    )
    assert isinstance(graph_sol.answer, GraphAnswer)
    assert isinstance(times_sol.answer, SymbolicAnswer)
    # 恒真: 答えの時刻はどちらもグラフの折れ点の間（増加区間・減少区間）にある。
    breaks = [sympy.sympify(f.srepr) for f in graph_sol.answer.features]
    t_lo, t_mid1, t_mid2, t_hi = (b[0] for b in breaks)
    t1, t3 = sympy.sympify(times_sol.answer.srepr)
    assert t_lo < t1 < t_mid1 and t_mid2 < t3 < t_hi, (
        f"答えの時刻が増加区間・減少区間の内側にない: {t1}, {t3}"
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"numbers": _wp_numbers(s, v, area), "labels": labels_txt},
        given={"scenario": scenario},
        context_slots={"ask_value": ask},
        sub_questions=[
            _wp_sub(ctx, label="(1)", asked="draw_graph", sol=graph_sol),
            _wp_sub(ctx, label="(2)", asked="value", sol=times_sol),
        ],
        visual_plan=None,
        provenance=Provenance(recipe="math.word_problem_area_graph_and_times"),
    )


def _construct_graph_and_times(
    p: dict[str, Any], rng: Rng
) -> tuple[int, int, int, str, str, str]:
    """(1辺, 速さ, 面積, 点名, 場面文, 問い)。

    g3_l31 Lv4 と同型の列挙だが、こちらは**グラフの折れ点も答え**なので漏洩の条件が
    厳しい。折れ点は (0,0)・(s/v, s²/2)・(2s/v, s²/2)・(3s/v, 0) で、この時刻と
    面積のどれかが本文の数値と一致すると G-Q5t が落ちる。
    G-Q5t の whitelist は given（＝場面文）由来なので 1辺 s と速さ v は許可されるが、
    面積は問い（context_slots）にあるため許可されない。したがって
    「折れ点の値・答えの時刻」が面積と一致する組と、本文の "cm²" 由来の 2 と
    一致する組（速さが 2 のときを除く）を構成の段階で外す。
    g3_l31 側の候補列挙（`_construct_all_times`）はこの制約を持たないので共有しない
    ——共有すると既に検証済みの g3_l31 の出力まで変わってしまう。
    """
    triples: list[tuple[int, int, int]] = []
    for side in p["side_candidates"]:
        s_i = int(side)
        for speed in p["speed_candidates"]:
            v_i = int(speed)
            if (3 * s_i) % v_i or s_i % v_i:
                continue
            for t1 in range(1, s_i // v_i):
                if (s_i * v_i * t1) % 2:
                    continue
                area_i = s_i * v_i * t1 // 2
                if area_i >= s_i**2 // 2:
                    continue
                t3 = 3 * s_i // v_i - t1
                # 答えとして本文に現れうる値の全体（グラフの折れ点＋答えの時刻）。
                answer_values = {
                    0, s_i // v_i, 2 * s_i // v_i, 3 * s_i // v_i,
                    s_i**2 // 2, t1, t3,
                }
                forbidden = {area_i}
                if v_i != _AREA_UNIT_TOKEN and s_i != _AREA_UNIT_TOKEN:
                    forbidden.add(_AREA_UNIT_TOKEN)  # 本文の "cm²" 由来の 2
                if answer_values & forbidden:
                    continue
                triples.append((s_i, v_i, area_i))
    idx = int(draw({"int_set": list(range(len(triples)))}, rng))
    s, v, area = triples[idx]
    la, lb, lc, ld, lp = _draw_distinct_points(5, rng)
    labels_txt = la + lb + lc + ld + lp
    scenario = (
        f"1辺が{s}cmの正方形{la}{lb}{lc}{ld}の周上を、点{lp}が{la}を出発して"
        f"{la}→{lb}→{lc}→{ld}の順に毎秒{v}cmの速さで{ld}まで動く。"
        f"点{lp}が動き始めてからx秒後の三角形{la}{lp}{ld}の面積をy cm²とする。"
    )
    ask = (
        f"xとyの関係をグラフに表し、面積が{area}cm²になる時刻をすべて求めよ。"
    )
    return s, v, area, labels_txt, scenario, ask


__all__ = [
    "solve_moving_point_area_recipe",
    "draw_area_time_graph_segment",
    "word_problem_moving_points_area_recipe",
    "word_problem_moving_point_all_times_recipe",
    "word_problem_area_graph_and_times_recipe",
]
