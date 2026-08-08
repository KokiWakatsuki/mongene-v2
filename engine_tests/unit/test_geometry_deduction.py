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
