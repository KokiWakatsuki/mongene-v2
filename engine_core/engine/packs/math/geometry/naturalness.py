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
from engine.packs.math.geometry.facts import (
    Fact, ang, ang_eq, fact_text, is_common_segment, seg, seg_eq,
)

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


def _restates_something_already_written(f: Fact, ded: Deduction) -> bool:
    """結論が、**その証明の途中ですでに書いた行**の言い直しになっていないか。

    証明文に出るのは Fact そのものではなく `fact_text` の日本語なので、
    **同じ文が2度出るかどうか**で見る。種類が違っても同じ文になる組があり
    （`parallel` と `parallel_dir` はどちらも「BC ∥ MN」と書かれる）、
    Fact の同一性だけでは捕まらない。

    これを見ていなかったので、g3_l44.proof.Lv2 が

        ①、②より、中点連結定理が成り立つので  BC ∥ MN  …③
        ③より、平行線の同位角は等しいので     ∠ABC ＝ ∠AMN  …④
        ④より、錯角が等しいので               BC ∥ MN        ← ③の言い直し

    という**循環論法**を出していた（③で証明は終わっている）。深さを稼ぐために
    「いちど示した結論をもう一度導く」枝を選んでしまうのが原因。
    """
    claim = fact_text(f)
    if any(fact_text(g) == claim for g in ded.given):
        return True
    return any(fact_text(c) == claim for c in ded.proof_chain(f) if c != f)


def _is_worth_asking(f: Fact, ded: Deduction) -> bool:
    """「聞く価値のある命題か」。

    - 仮定そのままは結論にしない（証明することがない）
    - 「AC ＝ AC」のような同じものどうしの等号は結論にしない
    - 同じ三角形どうしの合同（△ABC≡△ABC）は結論にしない
    - **途中ですでに書いた行の言い直しは結論にしない**（循環論法）
    """
    if f in ded.given:
        return False
    if is_common_segment(f):
        return False
    if (
        f.kind in ("seg_eq", "ang_eq", "tri_cong", "tri_sim", "tri_area_eq")
        and f.args[0] == f.args[1]
    ):
        return False
    # **同じ角を別の点の名前で書いただけの等式**は、証明することが無い。
    # 引き算では捕まらない（∠BAC と ∠BAN はタプルとして別物）ので、
    # 半直線の組（ray_classes）で見る。△ABC の辺AC上に N をとった図で
    # 「∠BAC ＝ ∠BAN であることを証明せよ」という問題が出ていた。
    if f.kind == "ang_eq" and ded.same_angle(f.args[0], f.args[1]):
        return False
    if _restates_something_already_written(f, ded):
        return False
    return True


def select_goal(
    ded: Deduction,
    *,
    level: int,
    allowed_topics: frozenset[str],
    prefer: str | None = None,
    depth: int | None = None,
) -> GoalCandidate | None:
    """Lv と単元に合う結論を1つ選ぶ。無ければ None（＝この構成では問題を作らない）。

    `depth` を渡すと Lv からの既定の深さを上書きする。**Lv と深さの対応は単元ごとに
    違う**からである——「合同を直接示す」単元の Lv2 は深さ1だが、「合同を示してから
    対応する辺が等しいと結論する」単元の Lv2 は最初から深さ2になる。

    `prefer` に述語の種類（"tri_cong" など）を渡すと、それを優先する。
    同じ深さの候補が複数あるときは、**証明の手数が少なく、事実の並びが安定する順**で
    決める（同じ構成から毎回同じ問題が出るように＝生成が決定論であるため）。
    """
    want_depth = depth if depth is not None else DEPTH_BY_LEVEL.get(level)
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
        # **図に描かれているものだけを見る。** 生徒が図から読み取れるのは、線として
        # 引かれた線分の長さと、その線分どうしがつくる角だけである。描かれていない
        # 線分の長さがたまたまそろっていても、誰もそれを読み取らない。
        # ここを全点の組に広げていたせいで、中点連結定理の図・ピラミッド型・
        # 平行四辺形の辺の中点の図が、**見えない線の偶然**を理由に全部落ちていた。
        drawn = {frozenset(s) for s in con.segments}
        out = set()
        lengths = {}
        for p, q in itertools.combinations(con.points, 2):
            if frozenset({p, q}) not in drawn:
                continue
            (x1, y1), (x2, y2) = con.coords[p], con.coords[q]
            lengths[seg(p, q)] = math.hypot(x2 - x1, y2 - y1)
        for s1, s2 in itertools.combinations(sorted(lengths), 2):
            l1, l2 = lengths[s1], lengths[s2]
            if abs(l1 - l2) / max(l1, l2) <= _LENGTH_TOL:
                out.add(("seg", s1, s2))
        angles = {}
        for v in con.points:
            arms = [x for x in con.points if x != v and frozenset({v, x}) in drawn]
            for p, q in itertools.combinations(arms, 2):
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
