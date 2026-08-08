"""問題として成立するかの判定（docs/proof_engine_design_2026-08-08.md §4）。

**探索は「解けるが人が作らない問題」を出す。** ここが質の本体で、次を弾く:

  1. 聞く価値のない結論（仮定そのまま・自明・同じものどうしの等号）
  2. 単元に合わない定理を使う証明（二等辺の単元で円周角を使う等）
  3. 難易度が合わない導出（Lv2 なのに3手かかる等）
  4. 読めない図（`construct.figure_quality_problems`）

弾く条件を「なんとなく」ではなく**述語として書く**のは、後で市販問題集と突き合わせて
基準を直すときに、どこを直せばよいかが一意に決まるようにするため。
"""
from __future__ import annotations

from dataclasses import dataclass

import itertools
import math

from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.deduce import Deduction
from engine.packs.math.geometry.facts import Fact, ang, ang_eq, is_common_segment, seg, seg_eq

# Lv → 導出の深さ（docs の §1「難易度と補助線の機械的な定義」）。
DEPTH_BY_LEVEL: dict[int, int] = {2: 1, 3: 2, 4: 3}


@dataclass(frozen=True)
class GoalCandidate:
    """問題の結論の候補と、その証明の性質。"""

    fact: Fact
    depth: int
    rule_names: tuple[str, ...]
    topics: frozenset[str]


def goal_candidates(ded: Deduction) -> list[GoalCandidate]:
    """導出された事実のうち、結論として出す資格のあるものを返す。"""
    out: list[GoalCandidate] = []
    for f in ded.derived():
        if not _is_worth_asking(f, ded):
            continue
        chain = ded.proof_chain(f)
        rules = tuple(ded.rule_of(c).name for c in chain if ded.rule_of(c) is not None)
        topics: set[str] = set()
        for c in chain:
            rule = ded.rule_of(c)
            if rule is not None:
                topics |= set(rule.topics)
        out.append(
            GoalCandidate(fact=f, depth=ded.depth_of(f), rule_names=rules, topics=frozenset(topics))
        )
    return out


def _is_worth_asking(f: Fact, ded: Deduction) -> bool:
    """「聞く価値のある命題か」。

    - 仮定そのままは結論にしない（証明することがない）
    - 「AC ＝ AC」のような同じものどうしの等号は結論にしない
    - 同じ三角形どうしの合同（△ABC≡△ABC）は結論にしない
    """
    if f in ded.given:
        return False
    if is_common_segment(f):
        return False
    if f.kind in ("seg_eq", "ang_eq", "tri_cong", "tri_sim") and f.args[0] == f.args[1]:
        return False
    return True


def select_goal(
    ded: Deduction, *, level: int, allowed_topics: frozenset[str], prefer: str | None = None
) -> GoalCandidate | None:
    """Lv と単元に合う結論を1つ選ぶ。無ければ None（＝この構成では問題を作らない）。

    `prefer` に述語の種類（"tri_cong" など）を渡すと、それを優先する。
    同じ深さの候補が複数あるときは、**証明の手数が少なく、事実の並びが安定する順**で
    決める（同じ構成から毎回同じ問題が出るように＝生成が決定論であるため）。
    """
    want_depth = DEPTH_BY_LEVEL.get(level)
    if want_depth is None:
        return None
    cands = [
        c
        for c in goal_candidates(ded)
        if c.depth == want_depth and c.topics <= allowed_topics
    ]
    if prefer is not None:
        preferred = [c for c in cands if c.fact.kind == prefer]
        cands = preferred or cands
    if not cands:
        return None
    return sorted(cands, key=lambda c: (len(c.rule_names), c.fact.kind, c.fact.args))[0]


# 図の見た目で「偶然そろってしまった」と判定する許容差。
_LENGTH_TOL = 0.04   # 長さの相対差
_ANGLE_TOL = 2.0     # 角の差（度）


def misleading_coincidences(con: Construction, ded: Deduction) -> list[str]:
    """**図が、証明できない性質を見せてしまっていないか**を検査する。

    探索で作った図は、座標のめぐり合わせで「与えてもいないのに辺の長さが等しく見える」
    「偶然直角に見える」ことがある。数学的には嘘ではないが、**生徒は図から条件を読む**
    ので、図が示す性質と証明できる事実がズレていると教材として成立しない。
    たこ形が偶然ひし形に見えてしまう、がその典型（最初に生成した図がそうだった）。

    座標を測って判定するのはここだけである（事実は構成が持つ、という原則は保つ。
    これは「事実を作る」のではなく「**図の見え方を検査する**」ため）。
    """
    problems: list[str] = []
    names = con.points
    lengths = {}
    for p, q in itertools.combinations(names, 2):
        (x1, y1), (x2, y2) = con.coords[p], con.coords[q]
        lengths[seg(p, q)] = math.hypot(x2 - x1, y2 - y1)

    for s1, s2 in itertools.combinations(sorted(lengths), 2):
        l1, l2 = lengths[s1], lengths[s2]
        if abs(l1 - l2) / max(l1, l2) > _LENGTH_TOL:
            continue
        if seg_eq(s1, s2) in ded.facts:
            continue
        problems.append(f"{s1[0]}{s1[1]} と {s2[0]}{s2[1]} が等しく見えるが、そうとは限らない")

    angles = {}
    for v in names:
        for p, q in itertools.combinations([x for x in names if x != v], 2):
            angles[ang(v, p, q)] = _angle_between(con.coords[p], con.coords[v], con.coords[q])
    for a1, a2 in itertools.combinations(sorted(angles), 2):
        if abs(angles[a1] - angles[a2]) > _ANGLE_TOL:
            continue
        if ang_eq(a1, a2) in ded.facts:
            continue
        problems.append(f"∠{a1[1]}{a1[0]}{a1[2]} と ∠{a2[1]}{a2[0]}{a2[2]} が等しく見えるが、そうとは限らない")
    return sorted(set(problems))


def _angle_between(p, vertex, q) -> float:
    ax, ay = p[0] - vertex[0], p[1] - vertex[1]
    bx, by = q[0] - vertex[0], q[1] - vertex[1]
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    cosv = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
    return math.degrees(math.acos(cosv))


__all__ = [
    "DEPTH_BY_LEVEL",
    "GoalCandidate",
    "goal_candidates",
    "misleading_coincidences",
    "select_goal",
]
