"""前向き推論と、導出からの証明の切り出し（docs/proof_engine_design_2026-08-08.md §5）。

仮定の集合に規則カタログを**適用できる限り繰り返す**（飽和させる）。各事実には
「どの規則で、どの前提から出たか」と「深さ」を記録する＝導出 DAG。
問題の難易度は**この深さ**で決まり、模範解答は**最短導出**を取り出して作る。

飽和が止まる理由: 事実は正規形で重複しないうえ、図の点は有限なので作れる線分・角・
三角形の組も有限。だから新しい事実が出なくなった時点で止まる。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.packs.math.geometry.facts import Fact, ang, ang_eq
from engine.packs.math.geometry.rules import RULES, Rule

# 暴走の歯止め（飽和しないことは無い）。**深さではなく事実の数が本当の歯止めである**
# ——12 にしていたとき、二等辺三角形の辺の上に点を2つとった図（143 個の事実・最大
# 深さ 15）が「飽和しない」で落ちていた。等式が鎖のようにつながる図では、事実が
# 増えなくても深さだけが伸びる。数えてみると 143 個で 0.4 秒なので、暴走とは桁が違う。
_MAX_ROUNDS = 24


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
    # 同じ角を別の点の名前で書いただけの控え（`saturate` の docstring を見よ）。
    # 規則が引き当てるためだけに持つので、**結論の候補にはしない**。
    aliases: set[Fact] = field(default_factory=set)
    # 「頂点から見て同じ半直線の上にある点」の組。**結論の資格の判定にも要る**
    # ので持ち回る（∠BAC と ∠BAN が同じ角かどうかは、これが無いと分からない）。
    ray_classes: dict[tuple[str, str], tuple[str, ...]] = field(default_factory=dict)

    def same_angle(self, a1: tuple[str, str, str], a2: tuple[str, str, str]) -> bool:
        """2つの角が、**同じ角を別の点の名前で書いたもの**か。"""
        return bool(set(_angle_writings(a1, self.ray_classes))
                    & set(_angle_writings(a2, self.ray_classes)))

    @property
    def facts(self) -> frozenset[Fact]:
        return frozenset(self.why)

    def derived(self) -> list[Fact]:
        """仮定でない（＝導出された）事実を、深さの浅い順に並べて返す。"""
        return sorted(
            (
                f
                for f, j in self.why.items()
                if j.rule is not None and f not in self.aliases
            ),
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


def _angle_writings(
    a: tuple[str, str, str], ray_classes: dict[tuple[str, str], tuple[str, ...]]
) -> list[tuple[str, str, str]]:
    """1つの角を、同じ半直線を指す別の点の名前で書いた全通り（先頭が代表）。"""
    v, x, y = a
    out: list[tuple[str, str, str]] = []
    for nx in ray_classes.get((v, x), (x,)):
        for ny in ray_classes.get((v, y), (y,)):
            if nx == ny:
                continue
            out.append(ang(v, nx, ny))
    return out or [a]


def _writings(
    f: Fact, ray_classes: dict[tuple[str, str], tuple[str, ...]]
) -> list[Fact]:
    """事実の書き方の全通り（先頭が代表）。角を含まない述語はそのまま1通り。"""
    if not ray_classes:
        return [f]
    if f.kind == "ang_eq":
        out = []
        for a1 in _angle_writings(f.args[0], ray_classes):
            for a2 in _angle_writings(f.args[1], ray_classes):
                g = ang_eq(a1, a2)
                if g.args[0] != g.args[1] and g not in out:
                    out.append(g)
        return out or [f]
    if f.kind == "right_angle":
        return [Fact("right_angle", (a,)) for a in _angle_writings(f.args[0], ray_classes)]
    return [f]


def saturate(
    points: list[str],
    given: frozenset[Fact],
    *,
    rules=RULES,
    ray_classes: dict[tuple[str, str], tuple[str, ...]] | None = None,
) -> Deduction:
    """仮定から、規則を適用できる限り繰り返して事実を飽和させる。

    同じ事実が複数の経路で出ることがあるので、**先に出た（＝深さの浅い）導出を残す**。
    これで `proof_chain` が自動的に最短導出になる（遠回りな模範解答を出さない）。

    `ray_classes` は「頂点から見て同じ半直線の上にある点」の組
    （`Construction.ray_classes`）。**同じ角を別の点の名前で書いてしまう問題**を
    ここで吸収する——弦 AC と BD の交点を P とした図で、円周角の定理が出すのは
    ∠BAC だが、△PAB の頂点 A の角は ∠BAP と書く。同じ角なのに事実としては別物
    なので、そろえないと教科書の定番の証明（円周角 → 相似）が1つも出てこない。

    そろえ方は「別の書き方も**同じ導出で**登録する」。代表（頂点から最も遠い点で
    書いたもの）以外は `aliases` に入れて、**結論の候補からは外す**——結論が
    ∠BAP と ∠BAC の2通り出てくると、同じ問題が2つあることになってしまう。
    """
    ray_classes = ray_classes or {}
    ded = Deduction(given=given, ray_classes=dict(ray_classes))
    for f in given:
        for i, g in enumerate(_writings(f, ray_classes)):
            if g in ded.why:
                continue
            ded.why[g] = Justification(rule=None, premises=(), depth=0)
            if i:
                ded.aliases.add(g)

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
                just = Justification(rule=rule, premises=tuple(premises), depth=depth)
                # 代表は `_writings` の先頭（規則がどの書き方で出したかによらない）。
                for i, g in enumerate(_writings(concl, ray_classes)):
                    if g in ded.why:
                        continue
                    ded.why[g] = just
                    if i:
                        ded.aliases.add(g)
                added = True
        if not added:
            return ded
    raise RuntimeError("飽和しなかった（規則が事実を無限に作っている疑い）")


__all__ = ["Deduction", "Justification", "saturate"]
