"""ProveAlgebraicVerb（§18.2, §26）"""
from __future__ import annotations

import json
import random
from typing import Any, ClassVar, Dict, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

m, n = sympy.symbols("m n", integer=True)


def _all_coeffs_even(expr: sympy.Expr) -> bool:
    """expr（m, n の多項式、定数項も可）の全係数が偶数かどうかを SymPy で判定する。"""
    if expr == 0:
        return True
    poly = sympy.Poly(expr, m, n)
    coeffs = poly.coeffs() if poly.gens else [expr]
    return all(int(c) % 2 == 0 for c in coeffs)


def _verify_even(expanded: sympy.Expr) -> None:
    """expanded の全係数が偶数であること（= 2 で割り切れる）を SymPy で検証する（moat）。"""
    half = sympy.expand(expanded / 2)
    if not _all_coeffs_even(expanded):
        raise AssertionError(f"{expanded} は偶数式ではない（係数に奇数あり）")
    # half が整数係数の多項式であることも重ねて確認
    if sympy.expand(2 * half - expanded) != 0:
        raise AssertionError(f"{expanded} の半分 {half} が一致しない")


def _verify_odd(expanded: sympy.Expr) -> None:
    """(expanded - 1) の全係数が偶数であること（= expanded が奇数式）を SymPy で検証する（moat）。"""
    shifted = sympy.expand(expanded - 1)
    if not _all_coeffs_even(shifted):
        raise AssertionError(f"{expanded} は奇数式ではない（{shifted} の係数に奇数あり）")


# even_odd の命題集合
# key -> (to_prove文, expr_a, expr_b, "sum"|"product", "even"|"odd", 表現ラベルa, 表現ラベルb)
_EVEN_ODD_PROPOSITIONS: Dict[str, Dict[str, Any]] = {
    "two_odds_sum": {
        "to_prove": "2つの奇数の和は偶数である",
        "expr_a": 2 * m + 1,
        "expr_b": 2 * n + 1,
        "op": "sum",
        "parity": "even",
        "label_a": "奇数",
        "label_b": "奇数",
        "def_statement": "2つの奇数を 2m+1, 2n+1 と表す。",
    },
    "two_evens_sum": {
        "to_prove": "2つの偶数の和は偶数である",
        "expr_a": 2 * m,
        "expr_b": 2 * n,
        "op": "sum",
        "parity": "even",
        "label_a": "偶数",
        "label_b": "偶数",
        "def_statement": "2つの偶数を 2m, 2n と表す。",
    },
    "even_odd_sum": {
        "to_prove": "偶数と奇数の和は奇数である",
        "expr_a": 2 * m,
        "expr_b": 2 * n + 1,
        "op": "sum",
        "parity": "odd",
        "label_a": "偶数",
        "label_b": "奇数",
        "def_statement": "偶数を 2m、奇数を 2n+1 と表す。",
    },
    "two_odds_product": {
        "to_prove": "2つの奇数の積は奇数である",
        "expr_a": 2 * m + 1,
        "expr_b": 2 * n + 1,
        "op": "product",
        "parity": "odd",
        "label_a": "奇数",
        "label_b": "奇数",
        "def_statement": "2つの奇数を 2m+1, 2n+1 と表す。",
    },
}


@register_verb
class ProveAlgebraicVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["NumberAtom", "PolynomialAtom"]
    tags: ClassVar[List[str]] = ["proof", "algebraic"]

    def __init__(self, proof_type: str = "even_odd") -> None:
        self.proof_type = proof_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "命題は 1 つの Atom に対応"
        n_ = nouns[0]
        if type(n_).__name__ not in self.accepted_noun_types:
            return False, f"{type(n_).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        if self.proof_type == "even_odd":
            return self._solve_even_odd(atom, rng)
        raise ValueError(f"未対応の proof_type: {self.proof_type}")

    def _solve_even_odd(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        chosen_key = rng.choice(list(_EVEN_ODD_PROPOSITIONS.keys()))
        prop = _EVEN_ODD_PROPOSITIONS[chosen_key]

        expr_a = prop["expr_a"]
        expr_b = prop["expr_b"]
        op = prop["op"]
        parity = prop["parity"]

        if op == "sum":
            expr = expr_a + expr_b
            op_word = "和"
            op_reason = "式を整理する"
        else:
            expr = expr_a * expr_b
            op_word = "積"
            op_reason = "式を展開して整理する"

        expanded = sympy.expand(expr)

        # moat: SymPy で検証してから使う
        if parity == "even":
            _verify_even(expanded)
            factored_core = sympy.expand(expanded / 2)
            factored = 2 * factored_core
            parity_word = "偶数"
        else:
            _verify_odd(expanded)
            factored_core = sympy.expand((expanded - 1) / 2)
            factored = 2 * factored_core + 1
            parity_word = "奇数"

        # moat: くくり出し形が元の展開式と一致することを検証
        if sympy.simplify(factored - expanded) != 0:
            raise AssertionError(f"くくり出し形 {factored} が {expanded} と一致しない")

        expr_a_str = str(expr_a)
        expr_b_str = str(expr_b)
        expanded_str = str(expanded)
        factored_core_str = str(factored_core)
        # 表示用: sympy の str() は 2*(m+n) を 2*m+2*n に自動展開してしまうため、
        # くくり出し形は手動で組み立てる（moat 検証自体は sympy の factored 式で行う）。
        if parity == "even":
            factored_str = f"2({factored_core_str})"
        else:
            factored_str = f"2({factored_core_str})+1"

        to_prove = prop["to_prove"]

        step1_statement = prop["def_statement"]
        if op == "sum":
            step2_statement = f"({expr_a_str})+({expr_b_str}) = {expanded_str}"
        else:
            step2_statement = f"({expr_a_str})×({expr_b_str}) = {expanded_str}"
        step3_statement = f"{expanded_str} = {factored_str}"

        if parity == "even":
            step4_statement = f"{factored_core_str} は整数だから 2({factored_core_str}) は偶数である。"
        else:
            step4_statement = f"{factored_core_str} は整数だから 2({factored_core_str})+1 は奇数である。"

        proof_output = {
            "given": ["m, n を整数とする。"],
            "to_prove": to_prove,
            "steps": [
                {
                    "step_number": 1,
                    "statement": step1_statement,
                    "reason": f"{prop['label_a']}の定義" if prop["label_a"] == prop["label_b"] else "偶数・奇数の定義",
                    "references": [],
                },
                {
                    "step_number": 2,
                    "statement": step2_statement,
                    "reason": op_reason,
                    "references": [1],
                },
                {
                    "step_number": 3,
                    "statement": step3_statement,
                    "reason": "2でくくる" if parity == "even" else "2でくくり1を加える",
                    "references": [2],
                },
                {
                    "step_number": 4,
                    "statement": step4_statement,
                    "reason": f"{parity_word}の定義",
                    "references": [3],
                },
            ],
            "conclusion": f"よって{to_prove}。",
        }

        narration = f"{to_prove}（{op_word}, {chosen_key}）"

        return LogicStep(
            operation_name=f"prove_algebraic_{chosen_key}",
            operands=[
                type(atom).__name__,
                "even_odd",
                chosen_key,
                json.dumps(proof_output, ensure_ascii=False),
            ],
            sympy_expr=sympy.Integer(1),
            narration_hint=to_prove,
        )
