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


def accidental_coincidences(
    instances: list[Construction], ded: Deduction
) -> list[str]:
    """図が**たまたま**見せている性質を弾く（構成をゆらして確かめる）。

    最初は「図に見えるのに導けない性質」を全部弾いていたが、それは厳しすぎた——
    平行四辺形の対角が等しいことは真で、対角線をもう1本引けば証明できる。図が
    「導けないが真であること」を見せるのは普通のことで、問題なのは
    **その instance でしか成り立たないこと**を見せてしまう場合である
    （たこ形がたまたま AB≈BC でひし形に見える、など）。

    そこで、**同じ作図手順を別のパラメータで組み直して**（＝ゆらして）、性質が
    残るかどうかで判定する。ゆらしても残るなら構成が強制している性質なので図に
    出てよい。1つの instance でしか成り立たないなら、それは偶然であり、生徒が
    図から読み取ると誤る。

    `instances` は同じ手順・違うパラメータで作った構成の並び（先頭が本番の図）。
    """
    if len(instances) < 2:
        raise ValueError("ゆらすには2つ以上の instance が要る")
    base = instances[0]
    problems: list[str] = []

    def equal_pairs(con: Construction) -> set:
        out = set()
        lengths = {}
        for p, q in itertools.combinations(con.points, 2):
            (x1, y1), (x2, y2) = con.coords[p], con.coords[q]
            lengths[seg(p, q)] = math.hypot(x2 - x1, y2 - y1)
        for s1, s2 in itertools.combinations(sorted(lengths), 2):
            l1, l2 = lengths[s1], lengths[s2]
            if abs(l1 - l2) / max(l1, l2) <= _LENGTH_TOL:
                out.add(("seg", s1, s2))
        angles = {}
        for v in con.points:
            for p, q in itertools.combinations([x for x in con.points if x != v], 2):
                angles[ang(v, p, q)] = _angle_between(con.coords[p], con.coords[v], con.coords[q])
        for a1, a2 in itertools.combinations(sorted(angles), 2):
            if abs(angles[a1] - angles[a2]) <= _ANGLE_TOL:
                out.add(("ang", a1, a2))
        return out

    persistent = equal_pairs(base)
    for other in instances[1:]:
        persistent &= equal_pairs(other)
    for kind, x, y in sorted(equal_pairs(base) - persistent):
        if kind == "seg":
            problems.append(f"{x[0]}{x[1]} と {y[0]}{y[1]} がたまたま等しく見えている")
        else:
            problems.append(f"∠{x[1]}{x[0]}{x[2]} と ∠{y[1]}{y[0]}{y[2]} がたまたま等しく見えている")
    return problems


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
    "accidental_coincidences",
    "select_goal",
]
