"""CalculateArithmeticVerb（§17.2, §18.2）

数値・文字式の四則演算を SymPy で実行する Verb。
- NumberAtom:    get_symbols()["value"] → 整数・分数
- PolynomialAtom: get_symbols()["expression"] → 多項式
- SquareRootAtom: get_symbols()["expression"] → 根号式
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Operation = Literal["+", "-", "*", "/"]


def _get_expr(noun: NounAtom) -> sympy.Expr:
    """Atom の種類に応じて主たる SymPy 式を取得する"""
    sym = noun.get_symbols()
    # NumberAtom → "value", PolynomialAtom/SquareRootAtom → "expression"
    return sym.get("value") or sym.get("expression") or sympy.Integer(0)


# 演算の種類と問題文における操作の対応（Atom 型別）
_OP_NARRATION: Dict[str, Dict[Operation, str]] = {
    "NumberAtom":   {"+": "和を計算する", "-": "差を計算する", "*": "積を計算する", "/": "商を計算する"},
    "PolynomialAtom": {"+": "式の加法", "-": "式の減法", "*": "単項式と多項式の乗法", "/": "多項式の除法"},
    "SquareRootAtom": {"+": "根号を含む加法", "-": "根号を含む減法", "*": "根号を含む乗法", "/": "根号を含む除法"},
}


@register_verb
class CalculateArithmeticVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "NumberAtom",
        "PolynomialAtom",
        "SquareRootAtom",
    ]
    tags: ClassVar[List[str]] = ["arithmetic"]

    def __init__(self, operation: Optional[Operation] = None) -> None:
        self.operation: Optional[Operation] = operation

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) < 2:
            return False, "CalculateArithmeticVerb は 2 つ以上の Noun を必要とする"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は CalculateArithmeticVerb に渡せない"
        if self.operation == "/":
            for n in nouns[1:]:
                v = _get_expr(n)
                if v is not None and sympy.simplify(v) == 0:
                    return False, "ゼロ除算"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom_type = type(nouns[0]).__name__

        # 型に応じた演算リストを決定
        if atom_type == "NumberAtom":
            op_choices: List[Operation] = ["+", "-", "*"]
        elif atom_type == "PolynomialAtom":
            op_choices = ["*", "-", "+"]  # 展開・乗法が中心
        elif atom_type == "SquareRootAtom":
            op_choices = ["+", "-", "*"]  # 根号の加減乗算
        else:
            op_choices = ["+", "-", "*"]

        op: Operation = self.operation or rng.choice(op_choices)

        values = [_get_expr(n) for n in nouns]
        result: sympy.Expr = values[0]
        for v in values[1:]:
            if op == "+":
                result = result + v
            elif op == "-":
                result = result - v
            elif op == "*":
                result = result * v
            elif op == "/":
                # 除算: 多項式 / 単項式 = 各項を割る
                if v != 0:
                    result = sympy.simplify(result / v)
                else:
                    result = result  # ゼロ除算は validate で弾くので到達しない

        simplified = sympy.expand(sympy.simplify(result))

        narrations = _OP_NARRATION.get(atom_type, _OP_NARRATION["NumberAtom"])
        narration = narrations.get(op, "計算する")

        return LogicStep(
            operation_name=f"arithmetic_{op}",
            operands=[str(v) for v in values],
            sympy_expr=simplified,
            narration_hint=narration,
        )
