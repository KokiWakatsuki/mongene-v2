"""平行線と線分の比の定理・その逆・中点連結定理まわりの recipe

（構成的生成・answer-first。実装設計 §6.1）。

C10（g3 図形・相似・円・三平方）クラスタのうち g3_l42/l43/l44 の非 visual
find_value セル群に対応する recipe を集約する。定理・その逆・中点連結定理の
想起は既存 `math.recall_rule` ハブに topic を追加して対応するため、ここには
含まれない。
"""
from __future__ import annotations

from typing import cast

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
from engine.core.rng import Rng, draw
from engine.packs.math.recipes.letter_expr import _draw_distinct_lines, _draw_named_figures
from engine.packs.math.visuals.similarity_figure import (
    midpoint_connector_svg,
    three_parallels_svg,
    triangle_with_parallel_svg,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _segment_lengths(
    rng: Rng, *, part_max: int, side_max: int
) -> tuple[int, int, int, int]:
    """DE∥BC の三角形で (AD, DB, DE, BC)。BC = DE·(AD+DB)/AD が整数になる組だけ。

    **答えが整数になる組を列挙してから引く。** 3辺を独立に引いていたため
    「AQ=32cm, QJ=68cm, QP=159cm のとき JH=10370/111」のような、教材にならない
    答えが出ていた。教科書は「AD=4cm, DB=6cm, DE=6cm のとき BC=15cm」のように、
    比が割り切れる組をとる。狭めたぶんは点名の軸で稼ぐ（FIXES.md の原則1・2）。
    """
    cands: list[tuple[int, int, int, int]] = []
    for ad in range(2, part_max + 1):
        for db in range(2, part_max + 1):
            ab = ad + db
            if db > 3 * ad or ad > 3 * db:
                continue  # 分ける比が極端だと図が細長くなりすぎる
            for de in range(2, side_max + 1):
                if de > 2 * ab:
                    continue  # DE が AB に比べて長すぎると三角形が退化に近づく
                if (de * ab) % ad:
                    continue
                bc = de * ab // ad
                if bc > side_max or bc in {ad, db, de}:
                    continue  # 答えが本文に出る数と一致する組は外す（G-Q5t）
                cands.append((ad, db, de, bc))
    if not cands:
        raise ValueError("_segment_lengths: 有効な組が無い")
    idx = int(draw({"int_set": list(range(len(cands)))}, rng))
    return cands[idx]


# ---------------------------------------------------------------------------
# g3_l42.find_value Lv2: DE∥BC のとき AD,DB,DE から辺BCの長さを求める
# ---------------------------------------------------------------------------
_PARALLEL_SEGMENT_RATIO_LENGTH_CONCEPTS = ["parallel_segment.ratio_length"]


@register_recipe(
    "math.parallel_segment_ratio_length", provides_concepts=_PARALLEL_SEGMENT_RATIO_LENGTH_CONCEPTS
)
def parallel_segment_ratio_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """DE∥BC のとき、AD,DB,DE から辺BCの長さを求める（g3_l42.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    ad, db, de, _bc = _segment_lengths(
        rng, part_max=int(p["part_max"]), side_max=int(p["side_max"])
    )

    solver = REGISTRY.solver("math.parallel_segment_ratio_length")
    sol = cast(Solution, solver(ad, db, de, pa + pb + pc + pd + pe))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図の三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}があり、"
        f"{pd}{pe}∥{pb}{pc}である。{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pd}{pe}={de}cm "
        f"のとき、辺{pb}{pc}の長さを求めよ"
    )
    # ★**点が辺のどこにあるかは図で示す。** 文で「辺AB, AC上に点D, Eがあり」と
    # 述べるだけだと、読み手が配置を組み立て直すことになる。内分の比は与えられた
    # 長さのとおりに取るので、図と本文が食い違わない。
    figure_svg = triangle_with_parallel_svg(
        pa, pb, pc, pd, pe, float(ad) / (float(ad) + float(db)),
        side_labels=[(pa, pd, f"{ad}cm"), (pd, pb, f"{db}cm"), (pd, pe, f"{de}cm")],
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "de": de, "labels": pa + pb + pc + pd + pe},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{ad}cm", f"{db}cm", f"{de}cm", pa, pb, pc, pd, pe],
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.parallel_segment_ratio_length"),
    )


# ---------------------------------------------------------------------------
# g3_l43.find_value Lv2: AD:DBとAE:ECの比を比べてDE∥BCといえるかを確かめる
# ---------------------------------------------------------------------------
_JUDGE_PARALLEL_FROM_RATIO_CONCEPTS = ["parallel_segment.judge_from_ratio"]

# 三角形の1辺として図に描ける長さの上限（cm）。定義域は広いまま、
# 組み上がった線分の長さで測って引き直す。
_MAX_SEGMENT_LENGTH = 120


@register_recipe(
    "math.judge_parallel_from_ratio", provides_concepts=_JUDGE_PARALLEL_FROM_RATIO_CONCEPTS
)
def judge_parallel_from_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """AD:DBとAE:ECの比を比べて、DE∥BCといえるかを確かめる

    （g3_l43.find_value Lv2・answer-first）。is_parallel(bool)で、比が一致する
    構成か、片方をずらして一致しない構成かを切り替える。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    is_parallel = bool(draw([True, False], rng))
    expected = "平行である" if is_parallel else "平行ではない"
    for _ in range(200):
        ad = int(draw(p["length_domain"], rng))
        db = int(draw(p["length_domain"], rng))
        scale = int(draw(p["scale_domain"], rng))
        ae, ec = ad * scale, db * scale
        if not is_parallel:
            delta = int(draw(p["delta_domain"], rng))
            ec += delta
        # 線分の長さなので正でなければならない（deltaが負のとき0以下になりうる）。
        # 図に描ける大きさに収めるため、いちばん長い線分の上限でも引き直す。
        # **2辺（AB と AC）の長さの比が3倍を超える図は避ける。**
        # 前は各線分の上限しか見ておらず「FG=14cm・FH=114cm」（8倍）のような、
        # 紙に描けない細長い三角形が出ていた。
        ab, ac = ad + db, ae + ec
        if ec <= 0 or max(ad, db, ae, ec) > _MAX_SEGMENT_LENGTH:
            continue
        if max(ab, ac) > 3 * min(ab, ac):
            continue
        solver = REGISTRY.solver("math.judge_parallel_from_ratio")
        sol = cast(Solution, solver(ad, db, ae, ec, pa + pb + pc + pd + pe))
        assert isinstance(sol.answer, SymbolicAnswer)
        if sol.answer.display == expected:
            break
    else:
        raise ValueError("judge_parallel_from_ratio_recipe: 有効な比の組を構成できず")

    statement = (
        f"下の図の三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}がある。"
        f"{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pa}{pe}={ae}cm, {pe}{pc}={ec}cm であるとき、"
        f"{pd}{pe}と{pb}{pc}が平行であるかどうかを、比を調べて答えよ"
    )
    # **平行の印は出さない。** これは平行かどうかを調べる問題なので、
    # 図で平行だと決めつけてはいけない（答えを図に書いたことになる）。
    # **2辺の内分の比を別々に渡す。** 平行の印を消すだけでは足りなかった。
    # 前は両辺を同じ比で内分していたので、答えが「平行ではない」ときでも
    # DE と BC のなす角が 0.0°（＝完全に平行）に描かれていた。
    figure_svg = triangle_with_parallel_svg(
        pa, pb, pc, pd, pe, float(ad) / (float(ad) + float(db)), parallel=False,
        ratio_q=float(ae) / (float(ae) + float(ec)),
        side_labels=[(pa, pd, f"{ad}cm"), (pd, pb, f"{db}cm"),
                     (pa, pe, f"{ae}cm"), (pe, pc, f"{ec}cm")],
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "ae": ae, "ec": ec, "labels": pa + pb + pc + pd + pe},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{ad}cm", f"{db}cm", f"{ae}cm", f"{ec}cm", pa, pb, pc, pd, pe],
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.judge_parallel_from_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l42.find_value Lv3: 3本の平行線l,m,nが2直線を切る比から辺の長さを求める（多段）
# ---------------------------------------------------------------------------
_PARALLEL_LINES_TRANSVERSAL_RATIO_CONCEPTS = ["parallel_segment.transversal_ratio"]


@register_recipe(
    "math.parallel_lines_transversal_ratio",
    provides_concepts=_PARALLEL_LINES_TRANSVERSAL_RATIO_CONCEPTS,
)
def parallel_lines_transversal_ratio_recipe(ctx: CellContext, rng: Rng) -> MR:
    """3本の平行線が2直線と交わってできる線分の比から、辺の長さを求める

    （g3_l42.find_value Lv3・answer-first）。台帳の「3本の直線l,m,nが平行、
    AB=3,BC=x,DE=4,EF=6でxを求める」を一般化した比例配分。三角形内の
    DE∥BCとは別の定理（3本の平行線が2直線を切る比は等しい）を使うため、
    Lv2の math.parallel_segment_ratio_length とは異なる新規solver。
    """
    p = ctx.spec_level.params
    pl1, pl2, pl3, pt1, pt2 = _draw_distinct_lines(5, rng)
    # 図形の頂点はアルファベット順に名づける（実物は「正方形ABCD」「△ABC∽△DEF」）。
    # 無作為に引くと「正方形ERDJ」「三角形JQBと三角形CMH」になる。
    (v,) = _draw_named_figures([6], rng)
    pa, pb, pc, pd, pe, pf = v
    # BC = AB·EF/DE が整数になる組だけを列挙してから引く（前は 105/19 が出ていた）。
    hi = int(p["length_max"])
    cands = [
        (ab, de, ef)
        for de in range(2, hi + 1)
        for ef in range(2, hi + 1)
        if de != ef  # 比が1:1に潰れる退化を避ける
        for ab in range(2, hi + 1)
        if (ab * ef) % de == 0 and 2 <= ab * ef // de <= hi
    ]
    ab, de, ef = cands[int(draw({"int_set": list(range(len(cands)))}, rng))]

    solver = REGISTRY.solver("math.parallel_lines_transversal_ratio")
    sol = cast(Solution, solver(ab, de, ef))
    assert isinstance(sol.answer, SymbolicAnswer)

    # **「右の図で」と書いていたが、このセルは visual: none で図が無い**（D-6）。
    # 交わる順（どの平行線とどの点が対応するか）は「それぞれ」で文が言い切って
    # いるので、図が無くても配置は決まる。図への言及だけを外す。
    statement = (
        f"下の図で、3本の直線{pl1}, {pl2}, {pl3}は平行である。直線{pt1}は"
        f"{pl1}, {pl2}, {pl3}とそれぞれ点{pa}, {pb}, {pc}で交わり、直線{pt2}は"
        f"{pl1}, {pl2}, {pl3}とそれぞれ点{pd}, {pe}, {pf}で交わる。"
        f"{pa}{pb}={ab}cm, {pd}{pe}={de}cm, {pe}{pf}={ef}cm のとき、"
        f"線分{pb}{pc}の長さを求めよ"
    )

    # 上下の間隔は与えられた長さのとおりに（DE:EF）。固定していたので、
    # DE=15cm・EF=12cm（上が長い）でも上を狭く描く＝比が逆向きの図が出ていた。
    figure_svg = three_parallels_svg(
        (pl1, pl2, pl3), (pa, pb, pc), (pd, pe, pf),
        side_labels=[(pa, pb, f"{ab}cm"), (pd, pe, f"{de}cm"), (pe, pf, f"{ef}cm")],
        gap_ratio=float(de) / float(ef),
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={
            "ab": ab, "de": de, "ef": ef,
            "labels": pl1 + pl2 + pl3 + pt1 + pt2 + pa + pb + pc + pd + pe + pf,
        },
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{ab}cm", f"{de}cm", f"{ef}cm", pl1, pl2, pl3, pa, pb, pc, pd, pe, pf],
            elements=[VisualElement(kind="parallel_lines", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.parallel_lines_transversal_ratio"),
    )


# ---------------------------------------------------------------------------
# g3_l43.find_value Lv3: 逆で平行を確かめたうえで辺の長さを多段で求める
# ---------------------------------------------------------------------------
_PARALLEL_RATIO_JUDGE_THEN_LENGTH_CONCEPTS = ["parallel_segment.judge_then_length"]


@register_recipe(
    "math.parallel_ratio_judge_then_length",
    provides_concepts=_PARALLEL_RATIO_JUDGE_THEN_LENGTH_CONCEPTS,
)
def parallel_ratio_judge_then_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """AD:DBとAE:ECの比が等しいことからDE∥BCを確かめたうえで、DEの長さから

    辺BCの長さを求める（g3_l43.find_value Lv3・answer-first）。逆（判定）と
    定理（長さ）を組み合わせた多段構成。既存の math.judge_parallel_from_ratio と
    math.parallel_segment_ratio_length を合成した solver を使う（新しい数学的
    計算は増やさない）。
    """
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pd, pe = v
    # 辺BCの長さが整数になる (AD, DB, DE) だけを組む（前は DE を独立に引いていて
    # 「RB=13cm のとき EM=39/2」のような答えが出ていた）。
    # **三角形として成立する組だけを残す。**
    # AE=AD·k, EC=DB·k と置くので AC = k·AB になり、k を大きく引くと
    # 「QR=20cm, QS=100cm, RS=32cm」（20+32 < 100）という、三角形不等式を
    # 満たさない図が出ていた（6 seed 全部がそうだった）。
    # AB=AD+DB, AC=AE+EC, BC=DE·AB/AD の3辺で不等式を確かめる。
    for _ in range(300):
        ad, db, de, bc = _segment_lengths(
            rng, part_max=int(p["part_max"]), side_max=int(p["side_max"])
        )
        scale = int(draw(p["scale_domain"], rng))
        if scale == 1:  # AE:ECがAD:DBと同じ数字の繰り返しになる退化を避ける
            continue
        ab = ad + db
        ac = scale * ab
        if ab + bc > ac and ab + ac > bc and ac + bc > ab:
            break
    else:
        raise ValueError("parallel_ratio_judge_then_length_recipe: 三角形になる比を構成できず")
    ae, ec = ad * scale, db * scale

    solver = REGISTRY.solver("math.parallel_ratio_judge_then_length")
    sol = cast(Solution, solver(ad, db, ae, ec, de, pa + pb + pc + pd + pe))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図の三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}上に点{pd}, {pe}がある。"
        f"{pa}{pd}={ad}cm, {pd}{pb}={db}cm, {pa}{pe}={ae}cm, {pe}{pc}={ec}cm である。"
        f"{pd}{pe}={de}cm のとき、{pd}{pe}と{pb}{pc}が平行であることを確かめたうえで、"
        f"辺{pb}{pc}の長さを求めよ"
    )
    # 平行かどうかを自分で確かめる問題なので、図には平行の印を出さない。
    figure_svg = triangle_with_parallel_svg(
        pa, pb, pc, pd, pe, float(ad) / (float(ad) + float(db)), parallel=False,
        side_labels=[(pa, pd, f"{ad}cm"), (pd, pb, f"{db}cm"),
                     (pa, pe, f"{ae}cm"), (pe, pc, f"{ec}cm"), (pd, pe, f"{de}cm")],
    )

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"ad": ad, "db": db, "ae": ae, "ec": ec, "de": de, "labels": pa + pb + pc + pd + pe},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{ad}cm", f"{db}cm", f"{ae}cm", f"{ec}cm", f"{de}cm", pa, pb, pc, pd, pe],
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.parallel_ratio_judge_then_length"),
    )


# ---------------------------------------------------------------------------
# g3_l44.find_value Lv2: 中点連結定理で中点を結ぶ線分の長さを求める
# ---------------------------------------------------------------------------
_MIDPOINT_CONNECTOR_LENGTH_CONCEPTS = ["midpoint_connector.length"]


@register_recipe(
    "math.midpoint_connector_length", provides_concepts=_MIDPOINT_CONNECTOR_LENGTH_CONCEPTS
)
def midpoint_connector_length_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三角形の2辺の中点を結ぶ線分の長さを求める（g3_l44.find_value Lv2・answer-first）。"""
    p = ctx.spec_level.params
    (v,) = _draw_named_figures([5], rng)
    pa, pb, pc, pm, pn = v
    # **辺の長さは偶数**（中点連結定理の答えは半分なので、奇数だと 7.5cm になる）。
    bc = 2 * int(draw(p["half_domain"], rng))

    solver = REGISTRY.solver("math.midpoint_connector_length")
    sol = cast(Solution, solver(bc))
    assert isinstance(sol.answer, SymbolicAnswer)

    statement = (
        f"下の図の三角形{pa}{pb}{pc}で、辺{pa}{pb}, {pa}{pc}の中点をそれぞれ{pm}, {pn}とする。"
        f"{pb}{pc}={bc}cm のとき、線分{pm}{pn}の長さを求めよ"
    )
    figure_svg = midpoint_connector_svg(pa, pb, pc, pm, pn, f"{bc}cm")

    sub_question = SubQuestionMR(
        label="(1)", asked="value", answer=sol.answer, steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx), cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0,
        params={"bc": bc},
        given={"condition": statement},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=[f"{bc}cm", pa, pb, pc, pm, pn],
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.midpoint_connector_length"),
    )
