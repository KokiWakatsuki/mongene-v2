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


# 幾何量（面積・体積・表面積・長さ）は 0 以下だと退化（図形がつぶれている）。
_POSITIVE_MAGNITUDE_OPS = frozenset(
    {
        "measure_area",
        "triangle_area",
        "measure_volume",
        "measure_surface_area",
        "cutout",
        "moving_point_area_at_t",
        "moving_point_max_area",
        "pythagorean_hypotenuse",
        "pythagorean_slant_edge",
        "pythagorean_space_diagonal",
        "pythagorean_distance",
        "shortest_path_prism",
        "shortest_path_pyramid",
        "revolution",
    }
)


def is_degenerate_step(operation_name: str, expr: Optional[sympy.Expr]) -> bool:
    """1 つの logic_step が退化（＝ moat は通るが問題として破綻）しているか。

    - 面積/体積/長さ等の正であるべき幾何量が 0 以下（図形がつぶれている。例: 同一切片の
      2 直線で座標軸と作る三角形の面積 0）。
    - 確率が (0, 1) の外（0 や 1、負、1 超）＝自明または不可能。
    """
    if expr is None:
        return False
    try:
        val = sympy.simplify(expr)
    except Exception:
        return False
    if not getattr(val, "is_number", False):
        return False  # 関数式など数値でないものは対象外

    if operation_name in _POSITIVE_MAGNITUDE_OPS:
        try:
            if val <= 0:
                return True
        except TypeError:
            return False
    elif operation_name == "calculate_probability":
        try:
            if val <= 0 or val >= 1:
                return True
        except TypeError:
            return False
    return False


def has_degenerate_step(logic_steps) -> bool:
    """logic_step 群のいずれかが退化していれば True。"""
    for step in logic_steps:
        op = getattr(step, "operation_name", "")
        expr = getattr(step, "sympy_expr", None)
        if is_degenerate_step(op, expr):
            return True
    return False
