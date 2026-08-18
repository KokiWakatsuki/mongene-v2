"""図形の証明セルの recipe（docs/proof_engine_design_2026-08-08.md）。

**問題を手で書かない。** 作図手順で図を組み（`geometry/construct.py`）、前向き推論で
導ける事実を飽和させ（`geometry/deduce.py`）、そこから Lv に合う結論を選んで
（`geometry/naturalness.py`）証明文を組む（`geometry/render_text.py`）。
だから「解き方が違う問題」は、**構成カタログと規則カタログを増やすこと**で増える。

構成カタログは params の `construction` で選ぶ。図そのものは
`geometry/constructions_*.py` にあり、`geometry/catalog.py` に名前で登録されている
——**この recipe に構成を書き足さない**（単元クラスタごとに別ファイルで進められる
ようにしてある）。パラメータ（角度・長さ）は rng で引き、**同じ手順を別のパラメータで
もう一度組んで**、図がたまたま見せている性質が無いかを確かめる
（`accidental_coincidences`）。
"""
from __future__ import annotations

import re
from typing import Any

from engine.core.contracts import (
    MR,
    CellContext,
    ProofAnswer,
    ProofStep,
    Provenance,
    Step,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.geometry import (  # noqa: F401  登録の副作用で構成が入る
    constructions_area,
    constructions_circle,
    constructions_congruence,
    constructions_parallelogram,
    constructions_right_triangle,
    constructions_similarity,
)
from engine.packs.math.geometry.catalog import CONSTRUCTIONS, topics_of
from engine.packs.math.geometry.construct import Construction, figure_quality_problems
from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import (
    fact_text,
    goal_text,
    right_angle,
    seg_text,
)
from engine.packs.math.geometry.naturalness import accidental_coincidences, select_goal
from engine.packs.math.geometry.rules import RULES
from engine.packs.math.geometry.render_text import (
    build_proof_lines,
    compared_triangles,
    render_proof,
)
from engine.packs.math.visuals.geometry_figure import render_construction_svg

# family が topic_set を書かないときの既定（合同の単元群）。
DEFAULT_TOPIC_SET = "congruence"
TOPICS_CONGRUENCE = topics_of(DEFAULT_TOPIC_SET)


# 図をゆらすときのパラメータの動かし方（偶然の一致を見つけるため）。
_PERTURBATIONS = ({"base": 0.8, "angle": 1.15, "offset": 1.25}, {"base": 1.2, "angle": 0.85, "offset": 0.8})

_MAX_TRIES = 24


def build_problem(
    kind: str,
    params: dict[str, Any],
    *,
    level: int,
    topic_set: str = DEFAULT_TOPIC_SET,
    exclude_rules: tuple[str, ...] = (),
    depth: int | None = None,
    prefer: str | None = "tri_cong",
):
    """構成 → 推論 → 結論 → 証明 を一息に行う（recipe と checker が共有する単一の真実）。

    `exclude_rules` は**証明したい定理そのものを規則から外す**ために要る。
    「二等辺三角形の底角は等しいことを証明せよ」というセルで、その定理を規則として
    使えてしまうと1手で終わってしまい、証明にならない（循環）。単元ごとに、
    その単元で「これから示すこと」を外す。

    `topic_set` は**その単元で習っている定理の範囲**（`catalog.TOPIC_SETS`）。
    範囲外の定理を使う証明はここで落ちる。

    戻り値は (構成, 導出, 選ばれた結論, 証明の行) の組。質のフィルタに落ちたら None。
    """
    builder = CONSTRUCTIONS[kind]
    con = builder(params)
    rules = tuple(r for r in RULES if r.name not in exclude_rules)
    ded = saturate(
        con.points,
        # 「間にある」は作図の手順が持っている事実（`Construction.between_facts`）。
        # 対頂角の規則が「本当に交わっているか」を見るのに要る。
        frozenset(con.facts) | con.between_facts(),
        rules=rules,
        ray_classes=con.ray_classes(),
    )
    goal = select_goal(
        ded, level=level, allowed_topics=topics_of(topic_set), prefer=prefer, depth=depth
    )
    if goal is None:
        return None
    if figure_quality_problems(con):
        return None
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERTURBATIONS]
    if accidental_coincidences([con, *others], ded):
        return None
    # 「問題文が述べている事実か」を渡す。作図の手順が持つだけの事実を
    # 「仮定より」と書かないため（`build_proof_lines` の docstring を見よ）。
    stated_here = frozenset(_stated_facts(con, con.description or "", goal.fact))

    def _is_stated(f: Any) -> bool:
        return f in stated_here

    return con, ded, goal, build_proof_lines(ded, goal.fact, stated=_is_stated)


# **family が使う概念IDはすべてここに載せる。** 載せ忘れると lint R6 が落ち、
# check_cell は通るのに capabilities に出ない（台帳に載らない）——既知の罠。
_PROOF_CONCEPTS = [
    "congruence_proof.triangle_congruence",
    "congruence_proof.choose_condition",
    "congruence_proof.corresponding_parts",
    "isosceles_proof.property_by_congruence",
    # 横展開（構成カタログ＋規則カタログを増やして開く単元群）
    "isosceles_proof.condition_two_angles",
    "isosceles_proof.condition_construct",
    "equilateral_proof.property_and_condition",
    "equilateral_proof.construct",
    "right_triangle_proof.hypotenuse_angle",
    "right_triangle_proof.hypotenuse_side",
    "right_triangle_proof.construct",
    "parallelogram_proof.property_opposite_sides",
    "parallelogram_proof.property_diagonals",
    "parallelogram_proof.property_construct",
    "parallelogram_proof.condition_given",
    "parallelogram_proof.condition_choose",
    "parallelogram_proof.apply_condition",
    "parallelogram_proof.apply_via_congruence",
    "parallelogram_proof.apply_construct",
    "special_quad_proof.condition_given",
    "special_quad_proof.condition_choose",
    "similarity_proof.direct_condition",
    "similarity_proof.two_step",
    "similarity_proof.construct",
    "parallel_ratio_proof.ratio_from_similarity",
    "parallel_ratio_proof.converse",
    "midline_proof.direct",
    "midline_proof.auxiliary",
    "circle_proof.inscribed_direct",
    "circle_proof.two_step",
    "circle_proof.construct",
    "parallel_lines.judge_from_angle",
    "parallel_angle_property.rule_recall",
    "equal_area_proof.parallel_direct",
    "equal_area_proof.chain",
]


@register_recipe("math.geometry_proof", provides_concepts=_PROOF_CONCEPTS)
def geometry_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """図形の証明（推論器が問題そのものを作る・answer-first ではなく search-first）。

    質のフィルタに落ちる構成があるので、パラメータを引き直す有界リトライを回す。
    落ちた構成は「人が作らない図」なので、捨てるのが正しい。
    """
    p = ctx.spec_level.params
    kind = str(p["construction"])
    topic_set = str(p.get("topic_set") or DEFAULT_TOPIC_SET)
    level = int(ctx.level)
    for _ in range(_MAX_TRIES):
        params = {
            "base": int(draw(p["base_domain"], rng)) / 10.0,
            "angle": int(draw(p["angle_domain"], rng)),
            "offset": int(draw(p["offset_domain"], rng)) / 10.0,
        }
        built = build_problem(
            kind, params, level=level, topic_set=topic_set,
            exclude_rules=tuple(str(x) for x in p.get("exclude_rules", ())),
            depth=int(p["proof_depth"]) if p.get("proof_depth") is not None else None,
            prefer=str(p["prefer"]) if p.get("prefer") else None,
        )
        if built is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは定義域が悪いとき
        raise ValueError(f"{kind}: 質のフィルタを通る構成を引けなかった")

    con, ded, goal, lines = built
    targets = compared_triangles(ded, goal.fact)
    text = render_proof(lines, targets=targets)
    # 「下の図で、AB ＝ AD、BC ＝ CD である」の形にする（条件を並べるだけだと
    # 文にならない）。構成が自前の言い方を持つならそれを使う（「平行四辺形ABCDで」）。
    # **図の印より先に組む。** 印をつけてよいのは「この文が述べている事実」だけで、
    # 判定にこの文字列が要る（`_stated_facts`）。
    premise_text = con.description or (
        "下の図で、" + "、".join(fact_text(f) for f in con.givens) + " である"
    )
    svg = render_construction_svg(
        {
            "coords": con.coords,
            "segments": con.segments,
            "circles": con.circles,
            "equal_groups": _equal_groups(con, premise_text, goal.fact),
            "parallel_groups": _parallel_groups(con, premise_text, goal.fact),
            "right_angles": _right_angles(con, premise_text, goal.fact),
        }
    )
    answer = ProofAnswer(
        text=text,
        lines=[
            ProofStep(
                claim=line.claim, reason=line.reason, number=line.number,
                refs=list(line.refs), op=line.op,
            )
            for line in lines
        ],
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=level,
        purpose=ctx.purpose, seed=0,
        params={
            "construction": kind,
            "numbers": {k: str(v) for k, v in params.items()},
            # checker が同じ条件で探索し直せるように、探索の条件も params に置く。
            "topic_set": topic_set,
            "exclude_rules": [str(x) for x in p.get("exclude_rules", ())],
            "proof_depth": int(p["proof_depth"]) if p.get("proof_depth") is not None else None,
            "prefer": str(p["prefer"]) if p.get("prefer") else None,
        },
        given={"premises": premise_text, "conclusion": goal_text(goal.fact)},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="proof_text", answer=answer,
                # **証明の各行がそのまま steps になる。** ここを空にすると op 列が消え、
                # Lv 間で fingerprint が同じになって level_sep が壊れる（eval が検出した）。
                # 採点の粒度としても、証明は「行ごとに何を根拠にしたか」が単位である。
                steps=_steps_from_lines(lines),
                concept_tags=list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=VisualPlan(
            style="plane",
            labels=sorted(con.coords),
            elements=[VisualElement(kind="figure_given", attrs={})],
        ),
        context_slots={"figure_svg": svg},
        provenance=Provenance(recipe="math.geometry_proof"),
    )


# 証明の行の種類ごとの言い方（解説・ヒントに出る）。
_STEP_NARRATION: dict[str, str] = {
    "cite_hypothesis": "仮定から、等しい辺（角）を書き出す。",
    "cite_common": "2つの三角形が共有している辺を確かめる。",
}


def _claim_tail(claim: str) -> str:
    """その行で**何が分かるか**を、主張の形から決める。

    以前はどの行も「次がいえる。」で締めていた。解説の接続詞は
    「次に、」が自動で付くので、証明の途中は「次に、…ことから、次がいえる。」が
    4行も続き、何が分かったのかを括弧の中まで読まないと分からなかった。
    """
    if "≡" in claim:
        return "2つの三角形が合同だと分かる。"
    if "∽" in claim:
        return "2つの三角形が相似だと分かる。"
    if "∥" in claim:
        return "2直線が平行だと分かる。"
    if "⊥" in claim:
        return "2直線が垂直だと分かる。"
    if "：" in claim or ":" in claim:
        return "辺の比が等しいと分かる。"
    if "°" in claim:
        return "角の大きさが分かる。"
    if "∠" in claim:
        return "等しい角が分かる。"
    if "＝" in claim or "=" in claim:
        # **三角形どうしの「＝」は面積の等しさ。** 教科書も面積を「△ABC ＝ △DBC」と
        # 書くので、辺の等式と同じ扱いにすると「等しい辺が分かる」と言ってしまう
        # （等積変形の証明 17 問がそうなっていた）。
        if claim.count("△") >= 2:
            return "面積が等しいと分かる。"
        return "等しい辺が分かる。"
    # 「四角形ABCD は平行四辺形である」のような**図形の種類**の結論。
    # 「次のことが分かる。」では何を示したのかが読めない。
    for name in ("平行四辺形", "長方形", "ひし形", "正方形"):
        if name in claim:
            return f"{name}であると分かる。"
    if "二等辺三角形" in claim:
        return "二等辺三角形であると分かる。"
    if "中点" in claim:
        return "中点であると分かる。"
    return "次のことが分かる。"


def _hypothesis_narration(claim: str, *, from_construction: bool = False) -> str:
    """仮定の行の言い方を、**その仮定が何であるか**から決める。

    どの仮定も「仮定から、等しい辺（角）を書き出す。」で括っていたので、
    「O は AC の中点」「四角形ABCD は平行四辺形である」にまで
    **辺でも角でもないものに「等しい辺（角）」と言っていた**（11 問）。
    """
    # 問題文が述べていない（作図の手順が持つ）事実は「仮定から」と言わない。
    head = "図のかき方から、" if from_construction else "仮定から、"
    if "中点" in claim:
        return f"{head}中点であることを書き出す。"
    if any(k in claim for k in ("平行四辺形", "長方形", "ひし形", "正方形")):
        return f"{head}四角形の種類を書き出す。"
    if "∥" in claim:
        return f"{head}平行な直線を書き出す。"
    if "⊥" in claim:
        return f"{head}垂直な直線を書き出す。"
    if "°" in claim:
        return f"{head}角の大きさを書き出す。"
    if "∠" in claim:
        return f"{head}等しい角を書き出す。"
    if "：" in claim or ":" in claim:
        return f"{head}辺の比を書き出す。"
    if "＝" in claim or "=" in claim:
        return f"{head}等しい辺を書き出す。"
    return f"{head}与えられていることを書き出す。"


#: 「仮定から、○を書き出す。」の○に、二度目であることを差しこむ言い方。
#: 数字は使わない——narration はヒントに流れるので、算用数字を入れると
#: G-Q5t が答え由来の値と衝突を起こしうる（鉄則①）。
_SECOND_TIME_HYPOTHESIS = {
    "等しい辺": "もう一組の等しい辺",
    "等しい角": "もう一組の等しい角",
    "平行な直線": "もう一組の平行な直線",
    "垂直な直線": "もう一組の垂直な直線",
    "辺の比": "もう一組の辺の比",
    "中点であること": "もう一つの中点であること",
    "角の大きさ": "もう一つの角の大きさ",
    "四角形の種類": "もう一つの四角形の種類",
    "与えられていること": "ほかに与えられていること",
}


def _mark_repeat(narration: str, nth: int) -> str:
    """同じ言い方が続くとき、何度目かが分かるようにする。

    **同じ文が2回続くと、ヒントが2行とも同じ文になる。** 実物を読むと
    「仮定から、等しい辺を書き出す。／仮定から、等しい辺を書き出す。」
    「平行線の錯角は等しいことから、等しい角が分かる。」×2 が 23 セルに出ていた。
    生徒には二度目が別の組についての話だと分からない。

    仮定の行は目的語に「もう一組の」を差しこみ、規則の行は頭に「別の組でも、」を
    置く。文の骨組みは変えない（level_sep は op 列で測るので影響しない）。
    """
    if nth <= 1:
        return narration
    if narration.startswith("仮定から、"):
        for obj, replaced in _SECOND_TIME_HYPOTHESIS.items():
            head = f"仮定から、{obj}"
            if narration.startswith(head):
                lead = "さらに" if nth >= 3 else ""
                return f"仮定から、{lead}{replaced}" + narration[len(head):]
        return narration
    lead = "さらに別の組でも、" if nth >= 3 else "別の組でも、"
    return lead + narration


def _steps_from_lines(lines) -> list[Step]:
    """証明の行を採点粒度の Step にする（op 列＝level_sep の材料になる）。"""
    out: list[Step] = []
    seen: dict[str, int] = {}
    for line in lines:
        narration = _STEP_NARRATION.get(line.op)
        if line.op == "cite_hypothesis":
            # **証明の本文と解説で、根拠の言い方をそろえる。** 本文を
            # 「図のかき方から」に直したのに、解説だけ「仮定から〜書き出す」の
            # ままだと、同じ行の説明が2通りになる。
            narration = _hypothesis_narration(
                line.claim, from_construction=(line.reason == "図のかき方から")
            )
        if narration is None:
            if not line.reason:
                narration = "図から読み取る。"
            elif line.reason.endswith("だから"):
                # 定義を開く行（「O は AD の中点だから」）はそのまま続ける。
                narration = f"{line.reason}、{_claim_tail(line.claim)}"
            else:
                narration = f"{line.reason}ことから、{_claim_tail(line.claim)}"
        # **数えるのは「続けて」でなく「この証明の中で」。** 間に別の行がはさまっても
        # 同じ文が二度出れば、ヒントの並びとしては同じ読みにくさになる。
        seen[narration] = seen.get(narration, 0) + 1
        narration = _mark_repeat(narration, seen[narration])
        out.append(
            Step(op=line.op, args=[], result_srepr="", result_display=line.claim,
                 narration=narration)
        )
    return out


def _stated_facts(con: Construction, premise_text: str, goal_fact: Any = None) -> list[Any]:
    """**問題文が述べている事実だけ**を返す。

    図に印をつける基準はこれ1つ。理由は2つある。

    1. 結論を漏らさない。「このとき AB ＝ CD であることを証明せよ」の AB ＝ CD に
       印をつけたら答えを図が言ってしまう（幾何的リーク規則）。
    2. 取りこぼさない。仮定は `con.givens` に入っているとは限らない——構成が自前の
       言い方を持つとき（「AB ＝ AC ＝ BC である」「∠OAP ＝ ∠OBP ＝ 90° である」）は
       `con.description` に書かれていて givens は空だった。**最初は givens だけを
       見ていて、40枚中9枚で印が付かなかった。**

    `premise_text` には結論が入らない（結論は「このとき、〜を証明せよ」として
    別に足される）ので、ここに出ている事実は必ず仮定である。

    ★**文字列一致だけでは足りない。** 本文は事実を別の言い方で書く:
      「点Oはそれぞれの中点である」  ← `O は AD の中点` とは書かれていない
      「頂点Bから辺ACに垂線BDをひく」← `BD ⊥ AC` とは書かれていない
      「DE ∥ BC」                    ← 事実の側は `BC ∥ DE` の順で正規化されている
    一致だけを見ていたときは 40 枚中 17 枚で印が付かなかった。言い方も見る。
    """
    return [
        f for f in con.facts
        # **結論そのものは絶対に印にしない。** 本文の言い方を吸収する側（`_mentioned_in`）は
        # 「垂線」の一語で perp をすべて拾うので、結論が垂直な回に漏れる道が残る。
        if f != goal_fact and (
            f in con.givens
            or _mentioned_in(f, premise_text)
            or _restates_stated(f, con, premise_text)
        )
    ]


def _restates_stated(f: Any, con: Construction, text: str) -> bool:
    """本文が述べていることの**言い換え**になっている事実か。

    教科書はこれらを1行で書くので、証明でも「仮定より」と書いてよい。
    図だけを見て言っているのではない。

      「AD ⊥ BC」        → 「∠ADB ＝ ∠ADC（＝ 90°）」
      「線分ABは円Oの直径」 → 「O は AB の中点」

    ここを見ずに「図のかき方から」と書くと、**本文がはっきり述べている条件を
    図から読み取ったことにしてしまう**。
    """
    if f.kind == "ang_eq" and ("⊥" in text or "垂線" in text):
        a1, a2 = f.args
        if a1[0] == a2[0] and all(
            right_angle(a[0], a[1], a[2]) in con.facts for a in (a1, a2)
        ):
            return True
    if f.kind == "midpoint" and "直径" in text:
        mid = f.args[0]
        xy = con.coords.get(mid)
        if xy is not None and any(
            abs(cx - xy[0]) < 1e-9 and abs(cy - xy[1]) < 1e-9
            for (cx, cy), _r in con.circles
        ):
            return True
    return False


def _mentioned_in(f: Any, text: str) -> bool:
    """事実 f が、この本文で述べられているか（言い方の違いを吸収する）。"""
    if fact_text(f) in text:
        return True
    if f.kind == "seg_eq" and _in_equality_chain(f, text):
        return True
    if f.kind == "midpoint":
        return "中点" in text
    if f.kind in ("parallel", "parallel_dir"):
        a, b = seg_text(f.args[0]), seg_text(f.args[1])
        return any(s in text for s in (f"{a} ∥ {b}", f"{b} ∥ {a}", f"{a}∥{b}", f"{b}∥{a}"))
    if f.kind in ("perp", "right_angle"):
        return "垂線" in text or "⊥" in text or "90°" in text
    return False


#: 「AB ＝ AC ＝ BC」のような、＝ でつないだ辺の連なり。
_EQ_CHAIN = re.compile(r"[A-Z]{2}(?:\s*＝\s*[A-Z]{2}){2,}")


def _in_equality_chain(f: Any, text: str) -> bool:
    """`AB ＝ BC` が「AB ＝ AC ＝ BC」のような連鎖の中で述べられているか。

    ★**文字列一致だけでは足りない**（`_stated_facts` の注意書きの続き）。
    正三角形の本文は3辺を1本の式でつないで書くので、`AB ＝ BC` は
    そのままの形では本文に出てこない。ここを見落としていたために、
    問題文がはっきり述べている仮定を「図のかき方から」と書いてしまった。
    """
    a, b = seg_text(f.args[0]), seg_text(f.args[1])
    for chain in _EQ_CHAIN.findall(text):
        members = {t.strip() for t in chain.split("＝")}
        # 線分は向きを問わない（AB と BA は同じ）。
        if {a, a[::-1]} & members and {b, b[::-1]} & members:
            return True
    return False


def _equal_groups(con: Construction, premise_text: str = "", goal_fact: Any = None) -> list[list[tuple[str, str]]]:
    """図に付ける等長の印。本文が述べている「辺が等しい」を組にする。

    `midpoint` も等長の言い方である（「点 O は AD の中点」→ AO と OD に印）。
    """
    groups: list[list[tuple[str, str]]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for f in (_stated_facts(con, premise_text, goal_fact) if premise_text else con.givens):
        if f.kind == "seg_eq" and f.args[0] != f.args[1]:
            pair = (tuple(f.args[0]), tuple(f.args[1]))
        elif f.kind == "midpoint":
            m, (a, b) = f.args[0], f.args[1]
            pair = ((a, m), (m, b))
        else:
            continue
        if pair not in seen:
            seen.add(pair)
            groups.append(list(pair))
    return groups


def _parallel_groups(con: Construction, premise_text: str, goal_fact: Any = None) -> list[list[tuple[str, str]]]:
    """図に付ける平行の印。本文が述べている「2直線が平行」を組にする。"""
    groups: list[list[tuple[str, str]]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for f in _stated_facts(con, premise_text, goal_fact):
        if f.kind in ("parallel", "parallel_dir"):
            pair = (tuple(f.args[0]), tuple(f.args[1]))
            if pair not in seen:
                seen.add(pair)
                groups.append(list(pair))
    return groups


def _right_angles(con: Construction, premise_text: str, goal_fact: Any = None) -> list[tuple[str, str, str]]:
    """図に付ける直角の印（頂点, 辺1の先, 辺2の先）。

    `right_angle`（∠ABC ＝ 90°）はそのまま頂点が分かる。`perp`（AD ⊥ BC）は
    2直線の交点が頂点なので、共有している点を探して頂点にする
    （共有点が無い＝図の上で交わっていないときは印を付けない）。
    """
    out: list[tuple[str, str, str]] = []
    for f in _stated_facts(con, premise_text, goal_fact):
        if f.kind == "right_angle":
            v, a1, a2 = f.args[0]
            out.append((v, a1, a2))
        elif f.kind == "perp":
            (p, q), (r, s) = f.args[0], f.args[1]
            shared = {p, q} & {r, s}
            if len(shared) != 1:
                continue
            v = shared.pop()
            out.append((v, q if v == p else p, s if v == r else r))
    return sorted(set(out))
