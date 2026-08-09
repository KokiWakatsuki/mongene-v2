"""証明エンジンの中核（事実・規則・前向き推論・証明文）のテスト。

設計は docs/proof_engine_design_2026-08-08.md。ここで守るのは次の4点:
  1. 事実が正規形になっている（同じ主張が2件入らない＝推論が飽和する前提）
  2. 合同の対応が6通りの書き方に増えない（最初の実装で踏んだ）
  3. 飽和が止まり、目標に至る導出が**最短**で取れる
  4. 証明文が教科書の型（△…において／仮定より／①②③より、…なので／結論）で出る
"""
from __future__ import annotations

import pytest

from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import (
    ang,
    ang_eq,
    collinear,
    fact_text,
    midpoint,
    seg,
    seg_eq,
    tri,
    tri_cong,
)
from engine.packs.math.geometry.render_text import build_proof_lines, render_proof
from engine.packs.math.geometry.rules import RULES_BY_NAME


# ---------------------------------------------------------------------------
# 1. 正規形
# ---------------------------------------------------------------------------
def test_segment_and_angle_are_normalized():
    assert seg("B", "A") == seg("A", "B")
    assert ang("A", "C", "B") == ang("A", "B", "C")  # ∠BAC と ∠CAB は同じ角
    assert seg_eq(seg("A", "B"), seg("C", "D")) == seg_eq(seg("D", "C"), seg("B", "A"))
    assert ang_eq(ang("A", "B", "C"), ang("D", "E", "F")) == ang_eq(
        ang("D", "F", "E"), ang("A", "C", "B")
    )


def test_congruence_writing_collapses_to_one_fact():
    """△ABC≡△ADC の6通りの書き方が1つの事実になる（推論が6倍に膨らまない）。"""
    base = tri_cong(tri("A", "B", "C"), tri("A", "D", "C"))
    equivalents = [
        tri_cong(tri("B", "C", "A"), tri("D", "C", "A")),
        tri_cong(tri("C", "A", "B"), tri("C", "A", "D")),
        tri_cong(tri("A", "C", "B"), tri("A", "C", "D")),
        tri_cong(tri("A", "D", "C"), tri("A", "B", "C")),  # 左右の入れかえ
    ]
    for e in equivalents:
        assert e == base
    # 対応が違うものは別の事実（B↔C と D↔C を混ぜない）。
    assert tri_cong(tri("A", "B", "C"), tri("A", "C", "D")) != base


def test_common_segment_reads_as_common():
    """同じ線分どうしの等号は「AC は共通」と書く（「AC ＝ AC」と書かない）。"""
    assert fact_text(seg_eq(seg("A", "C"), seg("A", "C"))) == "AC は共通"


# ---------------------------------------------------------------------------
# 2. 前向き推論（凧形＝合同の定番の図）
# ---------------------------------------------------------------------------
def _kite():
    points = ["A", "B", "C", "D"]
    given = frozenset({
        seg_eq(seg("A", "B"), seg("A", "D")),
        seg_eq(seg("B", "C"), seg("D", "C")),
        seg_eq(seg("A", "C"), seg("A", "C")),  # 対角線は共通
    })
    return points, given


def test_kite_derives_congruence_at_depth_one():
    points, given = _kite()
    ded = saturate(points, given)
    goal = tri_cong(tri("A", "B", "C"), tri("A", "D", "C"))
    assert goal in ded.facts
    assert ded.depth_of(goal) == 1
    assert ded.rule_of(goal) is RULES_BY_NAME["apply_sss"]


def test_kite_derives_angle_bisection_at_depth_two():
    """合同から「対応する角が等しい」が深さ2で出る＝Lv3 の材料になる。"""
    points, given = _kite()
    ded = saturate(points, given)
    goal = ang_eq(ang("A", "B", "C"), ang("A", "C", "D"))  # ∠BAC ＝ ∠CAD
    assert goal in ded.facts
    assert ded.depth_of(goal) == 2


def test_saturation_terminates_and_is_finite():
    points, given = _kite()
    ded = saturate(points, given)
    # 飽和して止まる（例外を出さない）。事実の数は図の点数で押さえられる。
    assert 0 < len(ded.derived()) < 100


def test_midpoint_rule_gives_equal_halves():
    ded = saturate(["A", "B", "M"], frozenset({midpoint("M", seg("A", "B"))}))
    assert seg_eq(seg("A", "M"), seg("M", "B")) in ded.facts


def test_vertical_angles_rule():
    """2直線が O で交わるとき、対頂角が等しいことが出る。"""
    given = frozenset({collinear("A", "O", "C"), collinear("B", "O", "D")})
    ded = saturate(["A", "B", "C", "D", "O"], given)
    assert ang_eq(ang("O", "A", "B"), ang("O", "C", "D")) in ded.facts


def test_isosceles_rules_are_two_way():
    """底角が等しい／2角が等しければ二等辺、の両向きが規則として入っている。"""
    ded1 = saturate(["A", "B", "C"], frozenset({seg_eq(seg("A", "B"), seg("A", "C"))}))
    assert ang_eq(ang("B", "A", "C"), ang("C", "A", "B")) in ded1.facts
    ded2 = saturate(["A", "B", "C"], frozenset({ang_eq(ang("B", "A", "C"), ang("C", "A", "B"))}))
    assert seg_eq(seg("A", "B"), seg("A", "C")) in ded2.facts


# ---------------------------------------------------------------------------
# 3. 証明文
# ---------------------------------------------------------------------------
def test_proof_text_matches_textbook_shape():
    points, given = _kite()
    ded = saturate(points, given)
    goal = tri_cong(tri("A", "B", "C"), tri("A", "D", "C"))
    lines = build_proof_lines(ded, goal)
    text = render_proof(lines, targets=goal.args)

    # 冒頭は「△… と △… において」。
    assert text.splitlines()[0] == "（証明）△ABC と △ADC において"
    # 仮定の行が番号つきで並び、共通の辺が「共通」として出る。
    assert "仮定より　　AB ＝ AD　…①" in text
    assert "AC は共通　…③" in text
    # 結論の直前に、引いた番号と根拠が並ぶ。
    assert "①、②、③より、3組の辺がそれぞれ等しいので" in text
    assert text.splitlines()[-1].strip() == "△ABC ≡ △ADC"
    # op 列（level_sep の材料）。結論の行は規則名になる。
    assert [line.op for line in lines] == [
        "cite_hypothesis", "cite_hypothesis", "cite_common", "apply_sss",
    ]


def test_proof_chain_is_shortest():
    """同じ事実が複数経路で出ても、証明文は最短導出だけを書く。"""
    points, given = _kite()
    ded = saturate(points, given)
    goal = ang_eq(ang("C", "A", "B"), ang("C", "A", "D"))  # ∠ACB ＝ ∠ACD
    chain = ded.proof_chain(goal)
    # 合同 →（対応する角）の2手だけ。遠回りな行が混ざらない。
    assert len(chain) == 2
    assert chain[0].kind == "tri_cong"
    assert chain[-1] == goal


def test_proof_chain_rejects_unreachable_goal():
    points, given = _kite()
    ded = saturate(points, given)
    with pytest.raises(KeyError):
        ded.proof_chain(seg_eq(seg("A", "B"), seg("B", "C")))


# ---------------------------------------------------------------------------
# 4. 構成生成器と質のフィルタ
# ---------------------------------------------------------------------------
from engine.packs.math.geometry.construct import (  # noqa: E402
    Construction,
    figure_quality_problems,
)
from engine.packs.math.geometry.naturalness import (  # noqa: E402
    DEPTH_BY_LEVEL,
    goal_candidates,
    accidental_coincidences,
    select_goal,
)
from engine.packs.math.geometry.render_text import compared_triangles  # noqa: E402

_CONGRUENCE_TOPICS = frozenset(
    {"congruence", "congruence_property", "isosceles", "midpoint", "angle"}
)


def _kite_construction(*, angle: float = 75.0, offset: float = -3.4, b: float = 3.0) -> Construction:
    """たこ形（AB=AD・CB=CD）に対角線 AC を引いた構成。"""
    c = Construction()
    c.free_point("A", 0.0, 0.0)
    c.free_point("B", b, 0.0)
    c.point_on_circle("D", "A", "B", angle_deg=angle)
    c.point_on_perpendicular_bisector("C", "B", "D", offset=offset)
    for p, q in (("A", "B"), ("A", "D"), ("B", "C"), ("D", "C")):
        c.connect(p, q)
    c.connect("A", "C", shared=True)
    return c


def test_construction_emits_facts_from_steps_not_coordinates():
    """事実は手順が持つ（円の上にとった＝距離が等しい）。座標を測って作らない。"""
    c = _kite_construction()
    assert seg_eq(seg("A", "B"), seg("A", "D")) in c.facts   # 円の上にとった
    assert seg_eq(seg("C", "B"), seg("C", "D")) in c.facts   # 垂直二等分線の上にとった
    assert seg_eq(seg("A", "C"), seg("A", "C")) in c.facts   # 対角線は共通
    # 与えられた条件として問題文に書くのは、この2つだけ（共通は証明の中で書く）。
    assert c.givens == [
        seg_eq(seg("A", "B"), seg("A", "D")),
        seg_eq(seg("C", "B"), seg("C", "D")),
    ]


def test_figure_quality_rejects_degenerate_shapes():
    """つぶれた三角形・近すぎる点を弾く。

    **辺を実際に引くこと。** 検査は「図に描かれている線でできる角」だけを見るので、
    点を置いただけでは何も検査されない（描かれていない角はつぶれて見えようがない）。
    点を置くだけで弾けると書いていたころのテストは、フィルタが描画基準に変わった
    あとも通っているように見えていた——`pytest -q` が engine_tests を集めて
    いなかったため、誰も落ちているところを見ていなかった。
    """
    assert figure_quality_problems(_kite_construction()) == []
    flat = Construction()
    flat.free_point("A", 0.0, 0.0)
    flat.free_point("B", 3.0, 0.0)
    flat.free_point("C", 6.0, 0.05)  # ほぼ一直線
    flat.connect("A", "B")
    flat.connect("A", "C")
    assert figure_quality_problems(flat)


def test_figure_quality_ignores_angles_that_are_not_drawn():
    """線として描かれていない角は、つぶれていても図の問題ではない。

    上のテストと対にしておく（辺を引かなければ弾かれない、が仕様である）。
    これを固定しておかないと、「描かれた角だけを見る」という判断が、
    次に誰かがフィルタを触ったときに黙って戻る。
    """
    bare = Construction()
    bare.free_point("A", 0.0, 0.0)
    bare.free_point("B", 3.0, 0.0)
    bare.free_point("C", 6.0, 0.05)
    assert figure_quality_problems(bare) == []


def test_collinear_points_are_not_called_degenerate():
    """一直線に並べたことが構成の意図なら、つぶれた三角形とは呼ばない（X字型で踏んだ）。"""
    c = Construction()
    c.free_point("O", 0.0, 0.0)
    c.free_point("A", -2.6, 1.5)
    c.free_point("B", -1.4, -2.0)
    c.reflected_point("D", "A", "O")
    c.reflected_point("C", "B", "O")
    assert figure_quality_problems(c) == []


def test_midpoint_line_is_folded_into_one_textbook_line():
    """「Oは中点だから AO＝DO」を1行で書く（2行に分けると教科書と違う）。"""
    c = Construction()
    c.free_point("O", 0.0, 0.0)
    c.free_point("A", -2.6, 1.5)
    c.free_point("B", -1.4, -2.0)
    c.reflected_point("D", "A", "O")
    c.reflected_point("C", "B", "O")
    ded = saturate(c.points, frozenset(c.facts))
    goal = select_goal(ded, level=3, allowed_topics=_CONGRUENCE_TOPICS, prefer="tri_cong")
    assert goal is not None and goal.fact.kind == "tri_cong"
    text = render_proof(
        build_proof_lines(ded, goal.fact), targets=compared_triangles(ded, goal.fact)
    )
    assert "O は AD の中点だから　　AO ＝ DO　…①" in text
    assert "対頂角は等しいから　　∠AOB ＝ ∠COD" in text
    # 「一直線上にある」は仮定の行として書かない（図を見れば分かる）。
    assert "一直線上" not in text
    # 2組の辺とその間の角＝SAS で結ぶ（たこ形の SSS とは別の解き方になっている）。
    assert "2組の辺とその間の角がそれぞれ等しいので" in text


def test_accidental_coincidence_is_detected_by_perturbation():
    """図が**たまたま**見せている性質を、構成をゆらして弾く。

    最初は「図に見えるのに導けない性質」を全部弾いたが、それは厳しすぎた——平行四辺形の
    対角が等しいのは真で、対角線をもう1本引けば証明できる。問題なのは
    **その instance でしか成り立たない**ことを見せる場合（たこ形がたまたま AB≈BC で
    ひし形に見える）なので、パラメータを変えて組み直し、残るかどうかで判定する。
    """
    bad = _kite_construction(angle=58.0, offset=-2.6)
    other = _kite_construction(angle=58.0, offset=-2.6, b=2.2)
    ded_bad = saturate(bad.points, frozenset(bad.facts))
    assert any("たまたま" in m for m in accidental_coincidences([bad, other], ded_bad))

    good = _kite_construction()
    good2 = _kite_construction(angle=64.0, offset=-4.1, b=2.4)
    ded_good = saturate(good.points, frozenset(good.facts))
    assert accidental_coincidences([good, good2], ded_good) == []


def test_goal_selection_is_deterministic_and_level_aware():
    """同じ構成から、Lv ごとに別の結論が選ばれる（＝同じ図で解き方が変わる）。"""
    c = _kite_construction()
    ded = saturate(c.points, frozenset(c.facts))
    lv2 = select_goal(ded, level=2, allowed_topics=_CONGRUENCE_TOPICS, prefer="tri_cong")
    lv3 = select_goal(ded, level=3, allowed_topics=_CONGRUENCE_TOPICS)
    assert lv2 is not None and lv3 is not None
    assert lv2.fact != lv3.fact
    assert lv2.depth == DEPTH_BY_LEVEL[2] and lv3.depth == DEPTH_BY_LEVEL[3]
    assert lv2.fact.kind == "tri_cong"
    # 何度呼んでも同じ（生成が決定論であるため）。
    assert select_goal(ded, level=2, allowed_topics=_CONGRUENCE_TOPICS, prefer="tri_cong") == lv2


def test_goal_candidates_exclude_trivia():
    """仮定そのまま・「AC は共通」は結論にしない。"""
    c = _kite_construction()
    ded = saturate(c.points, frozenset(c.facts))
    goals = {g.fact for g in goal_candidates(ded)}
    assert seg_eq(seg("A", "B"), seg("A", "D")) not in goals   # 仮定そのまま
    assert seg_eq(seg("A", "C"), seg("A", "C")) not in goals   # 同じ線分どうし


def test_goal_is_rejected_when_topic_is_out_of_unit():
    """単元に合わない定理を使う証明は選ばれない。"""
    c = _kite_construction()
    ded = saturate(c.points, frozenset(c.facts))
    assert select_goal(ded, level=2, allowed_topics=frozenset({"circle"})) is None


def test_proof_header_uses_the_compared_triangles_even_for_angle_goals():
    """目標が角でも、冒頭は「△… と △… において」になる（教科書の書き方）。"""
    c = _kite_construction()
    ded = saturate(c.points, frozenset(c.facts))
    goal = select_goal(ded, level=3, allowed_topics=_CONGRUENCE_TOPICS)
    assert goal is not None and goal.fact.kind != "tri_cong"
    targets = compared_triangles(ded, goal.fact)
    assert targets == (("A", "B", "C"), ("A", "D", "C"))
    text = render_proof(build_proof_lines(ded, goal.fact), targets=targets)
    assert text.splitlines()[0] == "（証明）△ABC と △ADC において"
