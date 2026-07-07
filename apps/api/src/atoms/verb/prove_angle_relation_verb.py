"""ProveAngleRelationVerb（§18.2）

平行線と交線がつくる角（錯角・同位角・同側内角）の性質を、平行線の同位角の性質と
対頂角・一直線の角を根拠に演繹的に証明する Verb。中2「対頂角・同位角・錯角」（g2_l31）
の proof form に用いる。

moat: LineAngleAtom の known_angle と relation_type から SymPy で目標角を計算し、
証明の主張（等しい／和が180°）が数値的に成り立つことを検証してからステップ化する。
"""
from __future__ import annotations

import json
import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class ProveAngleRelationVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["LineAngleAtom"]
    tags: ClassVar[List[str]] = ["angle_proof", "parallel_lines"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "ProveAngleRelationVerb は Noun を 1 つだけ受け取る"
        if type(nouns[0]).__name__ != "LineAngleAtom":
            return False, f"{type(nouns[0]).__name__} は ProveAngleRelationVerb に渡せない"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        sym = atom.get_symbols()
        known = sym["known_angle"]
        target = sym["target_angle"]
        relation = getattr(atom, "relation_type", "alternate")
        a = int(known)

        if relation == "corresponding":
            # moat: 同位角は等しい
            if sympy.simplify(target - known) != 0:
                raise AssertionError("同位角が等しくない")
            to_prove = "平行な2直線に1つの直線が交わるとき、同位角は等しい"
            steps = [
                {"step_number": 1,
                 "statement": f"仮定より2直線は平行で、一方の同位角は ${a}^\\circ$ である",
                 "reason": "仮定", "references": []},
                {"step_number": 2,
                 "statement": f"平行線の同位角の性質より、もう一方の同位角も ${a}^\\circ$ である",
                 "reason": "平行線の同位角の性質", "references": [1]},
            ]
            conclusion = f"よって同位角は等しく、ともに ${a}^\\circ$ である。"
        elif relation == "co_interior":
            # moat: 同側内角の和は180
            if sympy.simplify(target - (sympy.Integer(180) - known)) != 0:
                raise AssertionError("同側内角が補角になっていない")
            if sympy.simplify(known + target - 180) != 0:
                raise AssertionError("同側内角の和が180°でない")
            b = 180 - a
            to_prove = "平行な2直線に1つの直線が交わるとき、同側内角の和は180°である"
            steps = [
                {"step_number": 1,
                 "statement": f"仮定より2直線は平行で、一方の角は ${a}^\\circ$ である",
                 "reason": "仮定", "references": []},
                {"step_number": 2,
                 "statement": f"平行線の同位角の性質より、対応する同位角は ${a}^\\circ$ である",
                 "reason": "平行線の同位角の性質", "references": [1]},
                {"step_number": 3,
                 "statement": f"同側内角はこの同位角と一直線をなすから ${180}^\\circ - {a}^\\circ = {b}^\\circ$ である",
                 "reason": "一直線の角は180°", "references": [2]},
                {"step_number": 4,
                 "statement": f"よって同側内角の和は ${a}^\\circ + {b}^\\circ = 180^\\circ$ である",
                 "reason": "式を整理する", "references": [3]},
            ]
            conclusion = "よって同側内角の和は180°である。"
        else:  # alternate（錯角）
            if sympy.simplify(target - known) != 0:
                raise AssertionError("錯角が等しくない")
            to_prove = "平行な2直線に1つの直線が交わるとき、錯角は等しい"
            steps = [
                {"step_number": 1,
                 "statement": f"仮定より2直線は平行で、一方の角は ${a}^\\circ$ である",
                 "reason": "仮定", "references": []},
                {"step_number": 2,
                 "statement": f"平行線の同位角の性質より、対応する同位角は ${a}^\\circ$ である",
                 "reason": "平行線の同位角の性質", "references": [1]},
                {"step_number": 3,
                 "statement": f"錯角はこの同位角と対頂角の関係にあるから ${a}^\\circ$ である",
                 "reason": "対頂角は等しい", "references": [2]},
            ]
            conclusion = f"よって錯角は等しく、ともに ${a}^\\circ$ である。"

        proof_output = {
            "given": ["平行な2直線 $\\ell$, $m$ と、それらに交わる1つの直線"],
            "to_prove": to_prove,
            "steps": steps,
            "conclusion": conclusion,
        }
        return LogicStep(
            operation_name=f"prove_angle_{relation}",
            operands=[
                type(atom).__name__,
                relation,
                str(a),
                json.dumps(proof_output, ensure_ascii=False),
            ],
            sympy_expr=sympy.Integer(1),
            narration_hint=to_prove,
        )
