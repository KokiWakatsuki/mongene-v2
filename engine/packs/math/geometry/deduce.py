"""前向き推論と、導出からの証明の切り出し（docs/proof_engine_design_2026-08-08.md §5）。

仮定の集合に規則カタログを**適用できる限り繰り返す**（飽和させる）。各事実には
「どの規則で、どの前提から出たか」と「深さ」を記録する＝導出 DAG。
問題の難易度は**この深さ**で決まり、模範解答は**最短導出**を取り出して作る。

飽和が止まる理由: 事実は正規形で重複しないうえ、図の点は有限なので作れる線分・角・
三角形の組も有限。だから新しい事実が出なくなった時点で止まる。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.packs.math.geometry.facts import Fact
from engine.packs.math.geometry.rules import RULES, Rule

_MAX_ROUNDS = 12  # 飽和しないことは無いが、暴走の歯止め


@dataclass(frozen=True)
class Justification:
    """ある事実が「どう出たか」。仮定は rule=None。"""

    rule: Rule | None
    premises: tuple[Fact, ...]
    depth: int  # 仮定は 0。前提の最大深さ + 1


@dataclass
class Deduction:
    """飽和させた結果。事実 → その事実の（最短の）導出。"""

    given: frozenset[Fact]
    why: dict[Fact, Justification] = field(default_factory=dict)

    @property
    def facts(self) -> frozenset[Fact]:
        return frozenset(self.why)

    def derived(self) -> list[Fact]:
        """仮定でない（＝導出された）事実を、深さの浅い順に並べて返す。"""
        return sorted(
            (f for f, j in self.why.items() if j.rule is not None),
            key=lambda f: (self.why[f].depth, f.kind, f.args),
        )

    def depth_of(self, fact: Fact) -> int:
        return self.why[fact].depth

    def proof_chain(self, goal: Fact) -> list[Fact]:
        """`goal` に至る最短導出を、証明文に書く順（前提が先）で返す。

        仮定はここには含めない（証明文では「仮定より」の行として別に書く）。
        同じ事実を2度書かないよう、既に出したものは飛ばす。
        """
        if goal not in self.why:
            raise KeyError(f"導けていない事実を要求された: {goal}")
        order: list[Fact] = []
        seen: set[Fact] = set()

        def walk(f: Fact) -> None:
            if f in seen:
                return
            seen.add(f)
            just = self.why[f]
            for p in just.premises:
                walk(p)
            if just.rule is not None:
                order.append(f)

        walk(goal)
        return order

    def premises_of(self, fact: Fact) -> tuple[Fact, ...]:
        return self.why[fact].premises

    def rule_of(self, fact: Fact) -> Rule | None:
        return self.why[fact].rule


def saturate(points: list[str], given: frozenset[Fact], *, rules=RULES) -> Deduction:
    """仮定から、規則を適用できる限り繰り返して事実を飽和させる。

    同じ事実が複数の経路で出ることがあるので、**先に出た（＝深さの浅い）導出を残す**。
    これで `proof_chain` が自動的に最短導出になる（遠回りな模範解答を出さない）。
    """
    ded = Deduction(given=given)
    for f in given:
        ded.why[f] = Justification(rule=None, premises=(), depth=0)

    for _round in range(_MAX_ROUNDS):
        current = frozenset(ded.why)
        added = False
        for rule in rules:
            for concl, premises in rule.apply(points, current):
                if concl in ded.why:
                    continue
                if any(p not in ded.why for p in premises):
                    continue
                depth = max((ded.why[p].depth for p in premises), default=0) + 1
                ded.why[concl] = Justification(rule=rule, premises=tuple(premises), depth=depth)
                added = True
        if not added:
            return ded
    raise RuntimeError("飽和しなかった（規則が事実を無限に作っている疑い）")


__all__ = ["Deduction", "Justification", "saturate"]
