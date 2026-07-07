"""EventAtom（§18.1）

事象（サイコロ・硬貨・カード・玉・くじ）を表す Atom。樹形図 DSL を内包し、
CalculateProbabilityVerb の入力となる。

**題材忠実性（2026-07-07 Phase B 修正）**:
以前は適合数（favorable）を乱数で選んでいたため「全事象7で適合6→6/7」のように
記述可能な事象条件を持たない無意味な確率を生成していた。本版は具体的な事象条件
（「偶数の目が出る」「赤玉を取り出す」「2つの目の和が7」等）を生成し、実際の
結果空間を列挙して適合数を厳密に数える。条件文 `event_condition["description"]` を
翻訳器へ渡すことで「何の確率か」が定まる。
"""
from __future__ import annotations

import itertools
import random
from typing import Any, ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom

_EVENT_TYPES = ("dice", "coin", "card_draw", "ball_draw", "lottery")


@register_noun
class EventAtom(NounAtom):
    tags: ClassVar[List[str]] = ["probability", "dice", "cards"]

    def __init__(
        self,
        event_type: str = "dice",
        sample_space_size: int = 6,
        event_descriptors: List[Dict[str, Any]] | None = None,
        tree_dsl: Dict[str, Any] | None = None,
        num_trials: int = 1,
        with_replacement: bool = True,
        event_condition: Dict[str, Any] | None = None,
    ) -> None:
        self.event_type: str = event_type
        self.sample_space_size: int = sample_space_size
        self.event_descriptors: List[Dict[str, Any]] = event_descriptors or []
        self.tree_dsl: Dict[str, Any] = tree_dsl or {"nodes": [], "edges": []}
        self.num_trials: int = num_trials
        self.with_replacement: bool = with_replacement
        # {"description": str, "favorable": int}
        self.event_condition: Dict[str, Any] = event_condition or {}

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "EventAtom":
        custom = constraints.custom or {}
        event_type: str = str(custom.get("event_type", rng.choice(_EVENT_TYPES)))
        if event_type not in _EVENT_TYPES:
            event_type = "dice"
        num_trials: int = max(1, int(custom.get("num_trials", rng.randint(1, 2))))
        with_replacement: bool = bool(custom.get("with_replacement", True))

        # 単一試行の結果集合（label と、事象条件判定に使う値）
        if event_type == "dice":
            unit_size = 6
            outcomes = [str(i) for i in range(1, 7)]
            values: List[Any] = list(range(1, 7))
        elif event_type == "coin":
            unit_size = 2
            outcomes = ["表", "裏"]
            values = ["表", "裏"]
        elif event_type == "card_draw":
            unit_size = int(custom.get("card_count", rng.randint(4, 10)))
            outcomes = [f"カード{i}" for i in range(1, unit_size + 1)]
            values = list(range(1, unit_size + 1))
        elif event_type == "ball_draw":
            red = int(custom.get("red_balls", rng.randint(1, 4)))
            white = int(custom.get("white_balls", rng.randint(1, 4)))
            unit_size = red + white
            outcomes = [f"赤{i}" for i in range(1, red + 1)] + [
                f"白{i}" for i in range(1, white + 1)
            ]
            values = ["赤"] * red + ["白"] * white
        else:  # lottery
            unit_size = int(custom.get("lottery_count", rng.randint(5, 12)))
            winners = int(custom.get("winner_count", rng.randint(1, max(1, unit_size // 2))))
            outcomes = [f"当たり{i}" for i in range(1, winners + 1)] + [
                f"はずれ{i}" for i in range(1, unit_size - winners + 1)
            ]
            values = ["当たり"] * winners + ["はずれ"] * (unit_size - winners)

        # 標本空間サイズ（復元 / 非復元）
        if with_replacement:
            sample_space_size = unit_size**num_trials
        else:
            sample_space_size = 1
            for k in range(num_trials):
                size = unit_size - k
                if size <= 0:
                    size = 1
                sample_space_size *= size

        # 事象条件（description）と適合数（favorable）を実結果空間の列挙で厳密に決める
        description, favorable = self._make_condition(
            event_type, num_trials, with_replacement, values, rng
        )

        event_descriptors: List[Dict[str, Any]] = [
            {"trial": i + 1, "outcomes": list(outcomes)} for i in range(num_trials)
        ]

        # 樹形図 DSL（試行1のみ簡易展開）
        nodes: List[Dict[str, Any]] = [{"id": "root", "label": "スタート"}]
        edges: List[Dict[str, Any]] = []
        for idx, outcome in enumerate(outcomes):
            nid = f"n1_{idx}"
            nodes.append({"id": nid, "label": outcome})
            edges.append({"from": "root", "to": nid, "label": f"1/{unit_size}"})
        tree_dsl: Dict[str, Any] = {"nodes": nodes, "edges": edges, "depth": num_trials}

        return EventAtom(
            event_type=event_type,
            sample_space_size=sample_space_size,
            event_descriptors=event_descriptors,
            tree_dsl=tree_dsl,
            num_trials=num_trials,
            with_replacement=with_replacement,
            event_condition={"description": description, "favorable": favorable},
        )

    # ------------------------------------------------------------------
    def _make_condition(
        self,
        event_type: str,
        num_trials: int,
        with_replacement: bool,
        values: List[Any],
        rng: random.Random,
    ) -> Tuple[str, int]:
        """実際の結果空間を列挙し、記述可能な事象条件と適合数を返す。

        戻り値の favorable は必ず 1 以上・標本空間未満（自明でない確率）に収める。
        """
        # 実結果空間（試行ごとの値の tuple 列）
        if with_replacement:
            space = list(itertools.product(values, repeat=num_trials))
        else:
            space = list(itertools.permutations(values, num_trials))
        total = len(space)

        # 候補となる (説明テンプレート, 各試行に対する述語) を用意
        trial_word = self._trial_phrase(event_type, num_trials, with_replacement)
        candidates: List[Tuple[str, Any]] = []

        # 多試行で「各試行が条件を満たす」場合は「すべて」を明示して曖昧さを消す
        allq = "" if num_trials == 1 else "すべて"
        if event_type == "dice":
            if num_trials >= 2:
                # 2個以上は「目の和」条件が最も自然で曖昧さがない
                sums = [s for s in range(num_trials, 6 * num_trials + 1)]
                target = rng.choice(sums)
                candidates.append(
                    (f"{trial_word}、出た目の和が{target}になる", ("tuple", lambda t, s=target: sum(t) == s))
                )
                candidates.append(
                    (f"{trial_word}、出た目が{allq}偶数になる", ("all", lambda v: v % 2 == 0))
                )
            else:
                candidates.append((f"{trial_word}、偶数の目が出る", ("all", lambda v: v % 2 == 0)))
                candidates.append((f"{trial_word}、奇数の目が出る", ("all", lambda v: v % 2 == 1)))
                k = rng.randint(2, 5)
                candidates.append((f"{trial_word}、{k}以上の目が出る", ("all", lambda v, k=k: v >= k)))
                m = rng.choice([2, 3])
                candidates.append(
                    (f"{trial_word}、{m}の倍数の目が出る", ("all", lambda v, m=m: v % m == 0))
                )
        elif event_type == "coin":
            for k in range(1, num_trials + 1):
                desc = (
                    "硬貨を投げて表が出る"
                    if num_trials == 1
                    else f"硬貨を{num_trials}回投げて表がちょうど{k}回出る"
                )
                candidates.append((desc, ("count", lambda v: v == "表", k)))
        elif event_type == "ball_draw":
            candidates.append((f"{trial_word}、{allq}赤玉である", ("all", lambda v: v == "赤")))
            candidates.append((f"{trial_word}、{allq}白玉である", ("all", lambda v: v == "白")))
        elif event_type == "card_draw":
            candidates.append(
                (f"{trial_word}、{allq}偶数の番号のカードである", ("all", lambda v: v % 2 == 0))
            )
            kk = rng.randint(2, max(2, len(values) - 1))
            candidates.append(
                (f"{trial_word}、{allq}{kk}以上の番号のカードである", ("all", lambda v, kk=kk: v >= kk))
            )
        else:  # lottery
            candidates.append((f"{trial_word}、{allq}当たりである", ("all", lambda v: v == "当たり")))

        rng.shuffle(candidates)
        # 自明でない（1 <= fav < total）最初の候補を採用
        for desc, spec in candidates:
            fav = self._count_favorable(space, spec)
            if 1 <= fav < total:
                return desc, fav
        # フォールバック: 最初の結果だけを適合とする（必ず 1）
        return (f"{trial_word}、特定の結果が出る", 1)

    @staticmethod
    def _count_favorable(space: List[Tuple[Any, ...]], spec: Tuple[Any, ...]) -> int:
        kind = spec[0]
        if kind == "tuple":
            pred = spec[1]
            return sum(1 for t in space if pred(t))
        if kind == "all":
            pred = spec[1]
            return sum(1 for t in space if all(pred(v) for v in t))
        if kind == "count":
            pred, k = spec[1], spec[2]
            return sum(1 for t in space if sum(1 for v in t if pred(v)) == k)
        return 0

    @staticmethod
    def _trial_phrase(event_type: str, num_trials: int, with_replacement: bool) -> str:
        names = {
            "dice": "さいころ",
            "coin": "硬貨",
            "card_draw": "カード",
            "ball_draw": "袋から玉",
            "lottery": "くじ",
        }
        name = names.get(event_type, "試行")
        if event_type == "dice":
            return "1つのさいころを投げて" if num_trials == 1 else f"{num_trials}つのさいころを投げて"
        if event_type == "coin":
            return "硬貨を投げて" if num_trials == 1 else f"硬貨を{num_trials}回投げて"
        if num_trials == 1:
            return {"card_draw": "カードを1枚引いて", "ball_draw": "袋から玉を1個取り出して", "lottery": "くじを1本引いて"}.get(event_type, f"{name}を1回")
        mode = "もとに戻しながら" if with_replacement else "続けて"
        return {
            "card_draw": f"カードを{mode}{num_trials}枚引いて",
            "ball_draw": f"袋から玉を{mode}{num_trials}個取り出して",
            "lottery": f"くじを{mode}{num_trials}本引いて",
        }.get(event_type, f"{name}を{num_trials}回")

    def get_symbols(self) -> Dict[str, Any]:  # type: ignore[override]
        return {
            "sample_space_size": sympy.Integer(self.sample_space_size),
            "num_trials": sympy.Integer(self.num_trials),
            "favorable": sympy.Integer(int(self.event_condition.get("favorable", 0)))
            if self.event_condition.get("favorable") is not None
            else None,
            "event_description": self.event_condition.get("description", ""),
            "event_descriptors": self.event_descriptors,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        num_trials = int(custom.get("num_trials", 2))
        return len(_EVENT_TYPES) * max(1, num_trials) * 20
