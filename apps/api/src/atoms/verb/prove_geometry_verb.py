"""ProveGeometryVerb（§18.2, §26）"""
from __future__ import annotations

import json
import random
from typing import ClassVar, Dict, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

ProofType = Literal["congruence", "similarity"]
ConditionSet = Literal["SSS", "SAS", "ASA", "RHS", "AA"]


@register_verb
class ProveGeometryVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = ["PolygonAtom", "CircleAtom"]
    tags: ClassVar[List[str]] = ["proof", "geometry"]

    def __init__(
        self,
        proof_type: ProofType = "congruence",
        condition_set: ConditionSet = "SAS",
    ) -> None:
        self.proof_type: ProofType = proof_type
        self.condition_set: ConditionSet = condition_set

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 2:
            return False, "図形 2 つを要求"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        return True, None

    # 頂点ラベルの組み合わせ（多様性のため）
    _LABEL_PAIRS: ClassVar[List[Tuple[str, str]]] = [
        ("ABC", "DEF"),
        ("ABC", "PQR"),
        ("PQR", "STU"),
        ("ABC", "XYZ"),
        ("DEF", "GHI"),
    ]

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        a, b = nouns

        # rng で合同条件・相似条件をランダム選択（難易度・seed ごとに異なる問題）
        available: Dict[str, List[str]] = {
            "congruence": ["SSS", "SAS", "ASA", "RHS"],
            "similarity": ["AA", "SAS", "SSS"],
        }
        cands = available.get(self.proof_type, [self.condition_set])
        chosen_cs = rng.choice(cands)

        # 頂点ラベルをランダム選択
        labels_a, labels_b = rng.choice(self._LABEL_PAIRS)

        proof_output = self._build_proof_output(a, b, chosen_cs, labels_a, labels_b)
        narration = (
            f"{type(a).__name__} と {type(b).__name__} の{self.proof_type}を "
            f"{chosen_cs} で証明"
        )
        return LogicStep(
            operation_name=f"prove_{self.proof_type}",
            operands=[
                type(a).__name__,
                type(b).__name__,
                chosen_cs,
                json.dumps(proof_output, ensure_ascii=False),
            ],
            sympy_expr=sympy.Integer(1),
            narration_hint=narration,
        )

    def _build_proof_output(
        self,
        a: NounAtom,
        b: NounAtom,
        condition_set: str | None = None,
        labels_a: str = "ABC",
        labels_b: str = "DEF",
    ) -> dict:
        cs = condition_set if condition_set is not None else self.condition_set
        condition_text = {
            "SSS": "3 組の辺がそれぞれ等しい",
            "SAS": "2 組の辺とその間の角がそれぞれ等しい",
            "ASA": "1 組の辺とその両端の角がそれぞれ等しい",
            "RHS": "直角三角形の斜辺と他の 1 辺がそれぞれ等しい",
            "AA": "2 組の角がそれぞれ等しい",
        }.get(cs, cs)

        if self.proof_type == "congruence":
            relation = "≡"
            theorem = "合同条件"
        else:
            relation = "∽"
            theorem = "相似条件"

        tri_a = f"△{labels_a}"
        tri_b = f"△{labels_b}"
        return {
            "given": [
                f"{type(a).__name__}_a と {type(b).__name__}_b に関する仮定",
            ],
            "to_prove": f"{tri_a} {relation} {tri_b}",
            "steps": [
                {"step_number": 1, "statement": "対応する辺・角を確認する", "reason": "仮定", "references": []},
                {"step_number": 2, "statement": condition_text, "reason": f"{theorem}({cs})", "references": [1]},
                {"step_number": 3, "statement": f"{tri_a} {relation} {tri_b}", "reason": f"{cs} による", "references": [2]},
            ],
            "conclusion": f"よって {tri_a} {relation} {tri_b} が示された。",
        }
