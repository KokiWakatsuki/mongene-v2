"""Solvability + 「綺麗な解」フィルタ（§12.3, §12.5）"""
from __future__ import annotations

from typing import Optional

import sympy


def is_solvable(expr: Optional[sympy.Expr]) -> bool:
    """SymPy で値が確定するか（None/symbol だらけは False）"""
    if expr is None:
        return False
    try:
        simplified = sympy.simplify(expr)
    except Exception:
        return False
    return simplified is not None


def is_clean(
    expr: Optional[sympy.Expr],
    *,
    max_denominator_digits: int = 3,
    max_radicand: int = 1000,
    max_proof_steps: int = 10,
    forbidden_funcs: tuple = ("log", "exp", "sin", "cos", "tan"),
    **_unused,
) -> bool:
    """綺麗な解の判定（§12.3）

    - 分母桁数の上限
    - 根号中身の上限
    - 中学範囲外関数の不在
    """
    if expr is None:
        return False
    try:
        simplified = sympy.nsimplify(sympy.simplify(expr))
    except Exception:
        try:
            simplified = sympy.simplify(expr)
        except Exception:
            return False

    expr_str = str(simplified).lower()
    for forbidden in forbidden_funcs:
        if forbidden + "(" in expr_str:
            return False

    if simplified.is_Rational:
        denom_digits = len(str(abs(simplified.q)))
        if denom_digits > max_denominator_digits:
            return False
    else:
        try:
            frac = sympy.fraction(sympy.together(simplified))
            denom = frac[1]
            if denom.is_number and denom.is_Integer:
                if len(str(abs(int(denom)))) > max_denominator_digits:
                    return False
        except Exception:
            pass

    for sub in sympy.preorder_traversal(simplified):
        if isinstance(sub, sympy.Pow):
            base, exp_ = sub.as_base_exp()
            if exp_ == sympy.Rational(1, 2) and base.is_Integer:
                if int(base) > max_radicand:
                    return False

    return True
