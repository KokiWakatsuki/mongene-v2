"""証明エンジンの中核（半直線の同一視・円周角）の単体テスト。

ここに書いてあるのは**セルの検証では捕まらない**性質である。check_cell は
「問題が出るか」を見るので、`ray_classes` が壊れても「その構成では問題が作れない」と
いう形でしか現れず、原因が分からない。だから中核だけは直接おさえる。
"""
from __future__ import annotations

import pytest

from engine.packs.math.geometry import constructions_circle  # noqa: F401  登録の副作用
from engine.packs.math.geometry.catalog import CONSTRUCTIONS
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import ang, ang_eq, fact_text, same_arc, seg, seg_eq
from engine.packs.math.geometry.rules import RULES

_PARAMS = {"base": 3.6, "angle": 62.0, "offset": 2.4}


def test_ray_classes_identifies_the_same_ray() -> None:
    """線分の内側にとった点は、その線分の端点と**同じ半直線**を指す。"""
    con = Construction()
    con.free_point("A", 0.0, 0.0)
    con.free_point("B", 4.0, 0.0)
    con.midpoint_of("M", "A", "B")
    classes = con.ray_classes()
    # A から見て M と B は同じ向き。代表は遠いほう（B）。
    assert classes[("A", "M")] == ("B", "M")
    assert classes[("A", "B")] == ("B", "M")
    # B から見た代表は A。
    assert classes[("B", "M")] == ("A", "M")


def test_same_angle_written_two_ways_is_one_fact_after_saturation() -> None:
    """∠BAC と ∠BAM（M は AC の内側）が、同じ導出で登録される。

    ここが効いていないと、円周角 → 相似のような教科書の定番の証明が1つも出てこない
    （角が同じなのに事実として別物になり、規則が前提を引き当てられない）。
    """
    con = Construction()
    con.free_point("A", 0.0, 0.0)
    con.free_point("B", 1.0, 3.0)
    con.free_point("C", 4.0, 0.0)
    con.midpoint_of("M", "A", "C")
    given = frozenset({ang_eq(ang("A", "B", "C"), ang("C", "A", "B"))})
    ded = saturate(con.points, given, rules=RULES, ray_classes=con.ray_classes())
    alias = ang_eq(ang("A", "B", "M"), ang("C", "A", "B"))
    assert alias in ded.why
    # 別名は結論の候補にしない（同じ問題が2つあることになってしまう）。
    assert alias in ded.aliases
    assert alias not in ded.derived()


def test_inscribed_angle_rule_needs_the_same_arc() -> None:
    """円周角の定理は「同じ弧に対する」ときだけ効く。

    弦を挟んで反対側の弧にある円周角どうしは等しくない（和が 180°）。`same_arc` が
    無いのに角の等式が出るなら、それは偽の定理を持っていることになる。
    """
    points = ["A", "B", "C", "D"]
    concl = ang_eq(ang("A", "B", "C"), ang("D", "B", "C"))
    with_arc = saturate(points, frozenset({same_arc(("B", "C"), "A", "D")}), rules=RULES)
    assert concl in with_arc.why
    without_arc = saturate(points, frozenset(), rules=RULES)
    assert concl not in without_arc.why


def test_two_chords_figure_yields_the_angles_a_similarity_proof_needs() -> None:
    """弦の交点の図から、△PAB と △PDC の対応する2組の角の等式が出ている。"""
    con = CONSTRUCTIONS["circle_two_chords"](_PARAMS)
    ded = saturate(
        con.points, frozenset(con.facts), rules=RULES, ray_classes=con.ray_classes()
    )
    assert ang_eq(ang("P", "A", "B"), ang("P", "D", "C")) in ded.why  # 対頂角
    assert ang_eq(ang("A", "B", "P"), ang("D", "P", "C")) in ded.why  # 円周角
    assert con.circles, "円が図に描かれない"


def test_diameter_figure_yields_right_angles_and_equal_radii() -> None:
    """直径の図から「半円の弧に対する円周角は 90°」と「半径は等しい」が出る。"""
    con = CONSTRUCTIONS["circle_diameter"](_PARAMS)
    ded = saturate(
        con.points, frozenset(con.facts), rules=RULES, ray_classes=con.ray_classes()
    )
    from engine.packs.math.geometry.facts import right_angle

    assert right_angle("C", "A", "B") in ded.why
    assert seg_eq(seg("O", "A"), seg("O", "C")) in ded.why


def test_same_arc_rejects_a_degenerate_writing() -> None:
    with pytest.raises(ValueError):
        same_arc(("A", "B"), "A", "C")


def test_fact_text_covers_the_new_predicates() -> None:
    assert fact_text(same_arc(("B", "C"), "A", "D")).startswith("点A と点D は弦BC")
