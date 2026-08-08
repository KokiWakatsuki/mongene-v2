"""円の規則カタログ（円周角の定理とその周辺・中学3年）。

対象単元: g3_l49（円周角の定理を利用した証明）。

**円周角の定理は「同じ弧に対する」という条件つきの定理である。** 弦を挟んで反対側の
弧にある円周角どうしは等しくない（和が 180° になる）。どちらの弧にあるかは
`same_arc` の事実が持っていて、それは**円周上に点をとった手順（角度）**から出ている
——座標を測って「同じ側に見える」と判定したものではない。

書き方は `rules_congruence.py` に合わせる。`reason` はそのまま証明文の根拠欄に出るので、
教科書の言い回しに固定する。
"""
from __future__ import annotations

import itertools
from collections.abc import Iterable

from engine.packs.math.geometry.facts import (
    Fact,
    Point,
    ang,
    ang_eq,
    right_angle,
    seg,
    seg_eq,
)
from engine.packs.math.geometry.rule_base import Derivation, Rule


def _apply_radius(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """同じ円の半径は等しい。

    中心を図に描いている構成でだけ効く（`on_circle` の事実は中心を描いたときにしか
    出さない）。描かない中心について「OA ＝ OB」と書く証明は、図に無い線分の話になる。
    """
    on = [f for f in facts if f.kind == "on_circle"]
    for f1, f2 in itertools.combinations(on, 2):
        if f1.args[1] != f2.args[1]:
            continue
        center = f1.args[1]
        s1, s2 = seg(center, f1.args[0]), seg(center, f2.args[0])
        if s1 != s2:
            yield seg_eq(s1, s2), (f1, f2)


def _apply_inscribed_angles(
    points: list[Point], facts: frozenset[Fact]
) -> Iterable[Derivation]:
    """同じ弧に対する円周角は等しい。

    弦 AB について同じ側の弧にある2点 P・Q に対し ∠APB ＝ ∠AQB。
    """
    for f in facts:
        if f.kind != "same_arc":
            continue
        (a, b), (p, q) = f.args
        concl = ang_eq(ang(p, a, b), ang(q, a, b))
        if concl.args[0] != concl.args[1]:
            yield concl, (f,)


def _apply_thales(points: list[Point], facts: frozenset[Fact]) -> Iterable[Derivation]:
    """半円の弧に対する円周角は 90°。

    中心 O が線分 AB の中点（＝AB が直径）で、P が同じ円の周上にあれば ∠APB ＝ 90°。
    """
    on = {f.args[0]: f for f in facts if f.kind == "on_circle"}
    for f in facts:
        if f.kind != "midpoint":
            continue
        center, (a, b) = f.args
        if a not in on or b not in on or on[a].args[1] != center:
            continue
        for p in points:
            if p in (a, b, center) or p not in on or on[p].args[1] != center:
                continue
            yield right_angle(p, a, b), (f, on[p])


CIRCLE_RULES: tuple[Rule, ...] = (
    Rule(
        "use_inscribed_angles",
        "同じ弧に対する円周角は等しい",
        _apply_inscribed_angles,
        ("circle",),
    ),
    Rule(
        "use_diameter_angle",
        "半円の弧に対する円周角は 90° である",
        _apply_thales,
        ("circle",),
    ),
    Rule("use_circle_radius", "同じ円の半径は等しい", _apply_radius, ("circle",)),
)

__all__ = ["CIRCLE_RULES"]
