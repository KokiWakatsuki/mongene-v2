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
a, b, c = sympy.symbols("a b c", integer=True)


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


def _is_multiple_of(expr: sympy.Expr, k: int) -> bool:
    """expr（複数変数の多項式、定数項も可）の全係数が k の倍数かどうかを SymPy で判定する。"""
    expr = sympy.expand(expr)
    free_syms = sorted(expr.free_symbols, key=str)
    if not free_syms:
        return int(expr) % k == 0
    poly = sympy.Poly(expr, *free_syms)
    coeffs = poly.coeffs()
    return all(int(c) % k == 0 for c in coeffs)


def _verify_multiple_of(expanded: sympy.Expr, k: int) -> sympy.Expr:
    """expanded が k の倍数式であることを SymPy で検証し（moat）、core = expanded/k を返す。"""
    if not _is_multiple_of(expanded, k):
        raise AssertionError(f"{expanded} は{k}の倍数式ではない（係数に{k}の倍数でないものあり）")
    factored_core = sympy.expand(expanded / k)
    if sympy.simplify(k * factored_core - expanded) != 0:
        raise AssertionError(f"{expanded} の{k}分の1 {factored_core} が一致しない")
    return factored_core


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
        if self.proof_type == "consecutive_two_sum":
            return self._solve_consecutive_two_sum(atom, rng)
        if self.proof_type == "consecutive_three_sum":
            return self._solve_consecutive_three_sum(atom, rng)
        if self.proof_type == "consecutive_two_odds_sum":
            return self._solve_consecutive_two_odds_sum(atom, rng)
        if self.proof_type == "square_diff_consecutive":
            return self._solve_square_diff_consecutive(atom, rng)
        if self.proof_type == "digit_two":
            return self._solve_digit_two(atom, rng)
        if self.proof_type == "digit_three":
            return self._solve_digit_three(atom, rng)
        if self.proof_type == "quadratic_formula":
            return self._solve_quadratic_formula(atom, rng)
        if self.proof_type == "cube_diagonal":
            return self._solve_cube_diagonal(atom, rng)
        if self.proof_type == "box_diagonal":
            return self._solve_box_diagonal(atom, rng)
        if self.proof_type == "square_pyramid_height":
            return self._solve_square_pyramid_height(atom, rng)
        if self.proof_type == "tetrahedron_height":
            return self._solve_tetrahedron_height(atom, rng)
        if self.proof_type == "pythagorean_square":
            return self._solve_pythagorean_square(atom, rng)
        if self.proof_type == "pythagorean_trapezoid":
            return self._solve_pythagorean_trapezoid(atom, rng)
        if self.proof_type == "pythagorean_coordinate":
            return self._solve_pythagorean_coordinate(atom, rng)
        if self.proof_type == "pythagorean_converse":
            return self._solve_pythagorean_converse(atom, rng)
        raise ValueError(f"未対応の proof_type: {self.proof_type}")

    @staticmethod
    def _var_logic_step(atom: NounAtom, proof_type: str, given: List[str],
                        to_prove: str, steps: List[Dict[str, Any]], conclusion: str) -> LogicStep:
        """可変長ステップの proof_output を組み立てる（三平方の証明群で使用）。"""
        proof_output = {"given": given, "to_prove": to_prove, "steps": steps, "conclusion": conclusion}
        return LogicStep(
            operation_name=f"prove_algebraic_{proof_type}",
            operands=[type(atom).__name__, proof_type, proof_type,
                      json.dumps(proof_output, ensure_ascii=False)],
            sympy_expr=sympy.Integer(1),
            narration_hint=to_prove,
        )

    def _solve_pythagorean_square(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """1辺(a+b)の正方形に直角三角形4つを並べる分割で a²+b²=c² を証明する。"""
        sa, sb, sc = sympy.symbols("a b c", positive=True)
        # moat: 大正方形の面積 = 三角形4つ + 内側正方形。両辺から2abを引くと a²+b²=c²
        if sympy.expand((sa + sb) ** 2) != sympy.expand(sa**2 + 2 * sa * sb + sb**2):
            raise AssertionError("(a+b)^2 の展開が誤り")
        if sympy.expand((sa + sb) ** 2 - 4 * (sa * sb / 2)) != sympy.expand(sa**2 + sb**2):
            raise AssertionError("正方形分割の恒等式が成り立たない")
        return self._var_logic_step(
            atom, "pythagorean_square",
            given=[r"直角をはさむ2辺が $a, b$、斜辺が $c$ の直角三角形"],
            to_prove=r"$a^2 + b^2 = c^2$",
            steps=[
                {"step_number": 1, "statement": r"1辺 $a+b$ の正方形の中にこの直角三角形を4つ並べると、内側に1辺 $c$ の正方形ができる", "reason": "図形の構成", "references": []},
                {"step_number": 2, "statement": r"大きい正方形の面積は $(a+b)^2 = a^2 + 2ab + b^2$", "reason": "正方形の面積", "references": [1]},
                {"step_number": 3, "statement": r"それは直角三角形4つ $4 \times \dfrac{1}{2}ab = 2ab$ と内側の正方形 $c^2$ の和に等しく $a^2 + 2ab + b^2 = 2ab + c^2$", "reason": "面積の分割", "references": [2]},
                {"step_number": 4, "statement": r"両辺から $2ab$ を引いて $a^2 + b^2 = c^2$", "reason": "式を整理する", "references": [3]},
            ],
            conclusion=r"よって $a^2 + b^2 = c^2$ が成り立つ。",
        )

    def _solve_pythagorean_trapezoid(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """上底a・下底b・高さ(a+b)の台形の面積計算（ガーフィールドの証明）で a²+b²=c² を示す。"""
        sa, sb, sc = sympy.symbols("a b c", positive=True)
        # moat: 台形面積 ½(a+b)² = 三角形2つ(ab) + 直角二等辺三角形(½c²) → a²+b²=c²
        if sympy.expand(2 * (sympy.Rational(1, 2) * (sa + sb) ** 2)) != sympy.expand((sa + sb) ** 2):
            raise AssertionError("台形面積の2倍が誤り")
        if sympy.expand((sa + sb) ** 2 - 2 * sa * sb) != sympy.expand(sa**2 + sb**2):
            raise AssertionError("台形分割の恒等式が成り立たない")
        return self._var_logic_step(
            atom, "pythagorean_trapezoid",
            given=[r"直角をはさむ2辺が $a, b$、斜辺が $c$ の直角三角形"],
            to_prove=r"$a^2 + b^2 = c^2$",
            steps=[
                {"step_number": 1, "statement": r"上底 $a$、下底 $b$、高さ $a+b$ の台形をつくると、その面積は $\dfrac{1}{2}(a+b)(a+b) = \dfrac{1}{2}(a+b)^2$", "reason": "台形の面積", "references": []},
                {"step_number": 2, "statement": r"この台形は直角三角形2つ（合計 $ab$）と直角二等辺三角形1つ（$\dfrac{1}{2}c^2$）に分けられ、面積は $ab + \dfrac{1}{2}c^2$", "reason": "面積の分割", "references": [1]},
                {"step_number": 3, "statement": r"$\dfrac{1}{2}(a+b)^2 = ab + \dfrac{1}{2}c^2$ より $(a+b)^2 = 2ab + c^2$", "reason": "両辺を2倍する", "references": [2]},
                {"step_number": 4, "statement": r"$a^2 + 2ab + b^2 = 2ab + c^2$ の両辺から $2ab$ を引いて $a^2 + b^2 = c^2$", "reason": "式を整理する", "references": [3]},
            ],
            conclusion=r"よって $a^2 + b^2 = c^2$ が成り立つ。",
        )

    def _solve_pythagorean_coordinate(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """直角の頂点を原点、2辺を座標軸上にとり、斜辺の長さを2点間の距離で求めて示す。"""
        sa, sb, sc = sympy.symbols("a b c", positive=True)
        # moat: (a,0) と (0,b) の距離の2乗 = a²+b²
        if sympy.expand((sa - 0) ** 2 + (0 - sb) ** 2) != sympy.expand(sa**2 + sb**2):
            raise AssertionError("2点間の距離の2乗が a²+b² にならない")
        return self._var_logic_step(
            atom, "pythagorean_coordinate",
            given=[r"直角をはさむ2辺が $a, b$、斜辺が $c$ の直角三角形"],
            to_prove=r"$c^2 = a^2 + b^2$",
            steps=[
                {"step_number": 1, "statement": r"直角の頂点を原点に、2辺を $x$ 軸・$y$ 軸上にとると、他の頂点は $(a, 0)$ と $(0, b)$ になる", "reason": "座標の設定", "references": []},
                {"step_number": 2, "statement": r"斜辺の長さ $c$ は2点 $(a,0)$, $(0,b)$ の距離で $c^2 = (a-0)^2 + (0-b)^2$", "reason": "2点間の距離", "references": [1]},
                {"step_number": 3, "statement": r"$c^2 = a^2 + b^2$", "reason": "式を整理する", "references": [2]},
            ],
            conclusion=r"よって $c^2 = a^2 + b^2$ が成り立つ。",
        )

    def _solve_pythagorean_converse(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """三平方の定理の逆: a²+b²=c² ならば直角三角形であることを合同を用いて証明する。"""
        sa, sb, sc = sympy.symbols("a b c", positive=True)
        # moat: 直角をはさむ2辺a,bの直角三角形の斜辺は √(a²+b²)、仮定 a²+b²=c² より c に等しい
        if sympy.simplify(sympy.sqrt(sa**2 + sb**2) ** 2 - (sa**2 + sb**2)) != 0:
            raise AssertionError("構成した直角三角形の斜辺の2乗が a²+b² にならない")
        return self._var_logic_step(
            atom, "pythagorean_converse",
            given=[r"3辺の長さが $a, b, c$ で $a^2 + b^2 = c^2$ を満たす三角形 ABC"],
            to_prove=r"三角形 ABC は直角三角形である（$c$ を斜辺とする直角をもつ）",
            steps=[
                {"step_number": 1, "statement": r"直角をはさむ2辺が $a, b$ の直角三角形 A'B'C' をつくると、その斜辺の長さは $\sqrt{a^2+b^2}$", "reason": "三平方の定理", "references": []},
                {"step_number": 2, "statement": r"仮定 $a^2 + b^2 = c^2$ より、A'B'C' の斜辺は $\sqrt{c^2} = c$", "reason": "仮定", "references": [1]},
                {"step_number": 3, "statement": r"三角形 ABC と A'B'C' は3辺がそれぞれ $a, b, c$ で等しいので合同である", "reason": "3辺相等（SSS）", "references": [2]},
                {"step_number": 4, "statement": r"合同な図形の対応する角は等しいから、ABC の $c$ に対する角も直角である", "reason": "合同な図形の対応する角", "references": [3]},
            ],
            conclusion=r"よって三角形 ABC は直角三角形である。",
        )

    # --- 空間図形の導出証明（三平方の定理の反復適用・SymPy で moat 検証）---
    def _solve_cube_diagonal(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """1辺 a の立方体の対角線が √3·a であることを導出する。"""
        s = sympy.Symbol("a", positive=True)
        face = sympy.sqrt(s**2 + s**2)      # 面の対角線
        space = sympy.sqrt(face**2 + s**2)  # 空間対角線
        # moat: 面対角線^2=2a^2、空間対角線=√3 a
        if sympy.simplify(face**2 - 2 * s**2) != 0:
            raise AssertionError("立方体の面対角線が 2a^2 にならない")
        if sympy.simplify(space - sympy.sqrt(3) * s) != 0:
            raise AssertionError("立方体の空間対角線が √3·a にならない")
        return self._build_logic_step(
            atom, "cube_diagonal",
            given=[r"1 辺の長さが $a$ の立方体"],
            to_prove=r"立方体の対角線の長さは $\sqrt{3}\,a$ である",
            step1=r"面の対角線を $f$ とすると $f^2 = a^2 + a^2 = 2a^2$",
            step2=r"$f = \sqrt{2}\,a$",
            step3=r"対角線を $d$ とすると $d^2 = f^2 + a^2 = 2a^2 + a^2 = 3a^2$",
            step4=r"$d = \sqrt{3}\,a$",
            step1_reason="底面の直角三角形に三平方の定理を用いる",
            step2_reason="正の平方根をとる",
            step3_reason="面対角線と高さがつくる直角三角形に三平方の定理を用いる",
            step4_reason="正の平方根をとる",
            conclusion=r"よって立方体の対角線の長さは $\sqrt{3}\,a$ である。",
        )

    def _solve_box_diagonal(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """3辺 a, b, c の直方体の対角線が √(a²+b²+c²) であることを導出する。"""
        sa, sb, sc = sympy.symbols("a b c", positive=True)
        d1 = sympy.sqrt(sa**2 + sb**2)
        d = sympy.sqrt(d1**2 + sc**2)
        if sympy.simplify(d - sympy.sqrt(sa**2 + sb**2 + sc**2)) != 0:
            raise AssertionError("直方体の対角線が √(a^2+b^2+c^2) にならない")
        return self._build_logic_step(
            atom, "box_diagonal",
            given=[r"3 辺の長さが $a, b, c$ の直方体"],
            to_prove=r"直方体の対角線の長さは $\sqrt{a^2+b^2+c^2}$ である",
            step1=r"底面の対角線を $f$ とすると $f^2 = a^2 + b^2$",
            step2=r"$f = \sqrt{a^2+b^2}$",
            step3=r"対角線を $d$ とすると $d^2 = f^2 + c^2 = a^2 + b^2 + c^2$",
            step4=r"$d = \sqrt{a^2+b^2+c^2}$",
            step1_reason="底面の直角三角形に三平方の定理を用いる",
            step2_reason="正の平方根をとる",
            step3_reason="底面対角線と高さがつくる直角三角形に三平方の定理を用いる",
            step4_reason="正の平方根をとる",
            conclusion=r"よって直方体の対角線の長さは $\sqrt{a^2+b^2+c^2}$ である。",
        )

    def _solve_square_pyramid_height(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """底面が 1 辺 a の正方形、側稜 l の正四角錐の高さが √(l²−a²/2) であることを導出する。"""
        sa, sl = sympy.symbols("a l", positive=True)
        half_diag = sa / sympy.sqrt(2)  # 底面の対角線の半分
        h = sympy.sqrt(sl**2 - half_diag**2)
        if sympy.simplify(h**2 + half_diag**2 - sl**2) != 0:
            raise AssertionError("正四角錐の高さの関係式が成り立たない")
        if sympy.simplify(h - sympy.sqrt(sl**2 - sa**2 / 2)) != 0:
            raise AssertionError("正四角錐の高さが √(l^2−a^2/2) にならない")
        return self._build_logic_step(
            atom, "square_pyramid_height",
            given=[r"底面が 1 辺 $a$ の正方形、側稜の長さが $l$ の正四角錐"],
            to_prove=r"この正四角錐の高さは $\sqrt{l^2-\dfrac{a^2}{2}}$ である",
            step1=r"底面の対角線は $\sqrt{2}\,a$ で、その半分は $\dfrac{a}{\sqrt{2}}$",
            step2=r"頂点・底面の中心・底面の頂点がつくる直角三角形で $l^2 = h^2 + \left(\dfrac{a}{\sqrt{2}}\right)^2$",
            step3=r"$h^2 = l^2 - \dfrac{a^2}{2}$",
            step4=r"$h = \sqrt{l^2 - \dfrac{a^2}{2}}$",
            step1_reason="底面の正方形に三平方の定理を用いる",
            step2_reason="高さ・底面中心からの距離・側稜がつくる直角三角形に三平方の定理を用いる",
            step3_reason="式を整理する",
            step4_reason="正の平方根をとる",
            conclusion=r"よって正四角錐の高さは $\sqrt{l^2-\dfrac{a^2}{2}}$ である。",
        )

    def _solve_tetrahedron_height(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """1辺 a の正三角錐（正四面体）の高さが a·√(2/3) であることを導出する。"""
        sa = sympy.Symbol("a", positive=True)
        r = sa / sympy.sqrt(3)  # 底面（正三角形）の重心から頂点までの距離
        h = sympy.sqrt(sa**2 - r**2)
        if sympy.simplify(h**2 + r**2 - sa**2) != 0:
            raise AssertionError("正四面体の高さの関係式が成り立たない")
        if sympy.simplify(h - sa * sympy.sqrt(sympy.Rational(2, 3))) != 0:
            raise AssertionError("正四面体の高さが a·√(2/3) にならない")
        return self._build_logic_step(
            atom, "tetrahedron_height",
            given=[r"すべての辺の長さが $a$ の正三角錐（正四面体）"],
            to_prove=r"この正四面体の高さは $a\sqrt{\dfrac{2}{3}}$ である",
            step1=r"底面の正三角形の重心から頂点までの距離は $r = \dfrac{a}{\sqrt{3}}$",
            step2=r"頂点・底面の重心・底面の頂点がつくる直角三角形で $a^2 = h^2 + r^2$",
            step3=r"$h^2 = a^2 - \dfrac{a^2}{3} = \dfrac{2}{3}a^2$",
            step4=r"$h = a\sqrt{\dfrac{2}{3}}$",
            step1_reason="正三角形の重心の性質（外接円の半径）を用いる",
            step2_reason="高さ・重心からの距離・辺がつくる直角三角形に三平方の定理を用いる",
            step3_reason="式を整理する",
            step4_reason="正の平方根をとる",
            conclusion=r"よって正四面体の高さは $a\sqrt{\dfrac{2}{3}}$ である。",
        )

    def _solve_quadratic_formula(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        """2次方程式 ax²+bx+c=0 (a≠0) の解の公式を平方完成で導出する。

        moat: (1)平方完成の恒等式、(2)右辺の一致、(3)両根の逆代入=0 を SymPy で
        検証してから証明ステップを組み立てる。
        """
        x = sympy.Symbol("x")
        disc = b**2 - 4 * a * c

        # --- moat 検証（証明の各変形が恒等的に正しいことを SymPy で確認）---
        # (1) 平方完成: (x + b/2a)^2 == x^2 + (b/a)x + b^2/4a^2
        if sympy.expand((x + b / (2 * a)) ** 2 - (x**2 + (b / a) * x + b**2 / (4 * a**2))) != 0:
            raise AssertionError("平方完成の恒等式が成り立たない")
        # (2) 右辺の整理: b^2/4a^2 - c/a == (b^2-4ac)/4a^2
        if sympy.simplify((b**2 / (4 * a**2) - c / a) - disc / (4 * a**2)) != 0:
            raise AssertionError("平方完成の右辺が一致しない")
        # (3) 逆代入: 両根が元の方程式を満たす
        for sign in (1, -1):
            root = (-b + sign * sympy.sqrt(disc)) / (2 * a)
            if sympy.simplify(a * root**2 + b * root + c) != 0:
                raise AssertionError(f"導出した解 (sign={sign}) が方程式を満たさない")

        to_prove = r"2次方程式 $ax^2+bx+c=0$（$a \neq 0$）の解は $x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$ である"
        return self._build_logic_step(
            atom,
            "quadratic_formula",
            given=[r"$a, b, c$ を定数、$a \neq 0$ とする 2 次方程式 $ax^2+bx+c=0$"],
            to_prove=to_prove,
            step1=r"$x^2 + \dfrac{b}{a}x + \dfrac{c}{a} = 0$",
            step2=r"$x^2 + \dfrac{b}{a}x = -\dfrac{c}{a}$",
            step3=r"$\left(x + \dfrac{b}{2a}\right)^2 = \dfrac{b^2-4ac}{4a^2}$",
            step4=r"$x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$",
            step1_reason=r"両辺を $a$ で割る",
            step2_reason="定数項を右辺に移項する",
            step3_reason=r"両辺に $\left(\dfrac{b}{2a}\right)^2$ を加えて左辺を平方完成する",
            step4_reason=r"両辺の平方根をとり $\dfrac{b}{2a}$ を移項する",
            conclusion=r"よって解の公式 $x = \dfrac{-b \pm \sqrt{b^2-4ac}}{2a}$ が得られる。",
        )

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

    @staticmethod
    def _build_logic_step(
        atom: NounAtom,
        proof_type: str,
        given: List[str],
        to_prove: str,
        step1: str,
        step2: str,
        step3: str,
        step4: str,
        step1_reason: str,
        step2_reason: str,
        step3_reason: str,
        step4_reason: str,
        conclusion: str,
    ) -> LogicStep:
        proof_output = {
            "given": given,
            "to_prove": to_prove,
            "steps": [
                {"step_number": 1, "statement": step1, "reason": step1_reason, "references": []},
                {"step_number": 2, "statement": step2, "reason": step2_reason, "references": [1]},
                {"step_number": 3, "statement": step3, "reason": step3_reason, "references": [2]},
                {"step_number": 4, "statement": step4, "reason": step4_reason, "references": [3]},
            ],
            "conclusion": conclusion,
        }
        return LogicStep(
            operation_name=f"prove_algebraic_{proof_type}",
            operands=[
                type(atom).__name__,
                proof_type,
                proof_type,
                json.dumps(proof_output, ensure_ascii=False),
            ],
            sympy_expr=sympy.Integer(1),
            narration_hint=to_prove,
        )

    def _solve_consecutive_two_sum(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "連続する2つの整数の和は奇数である"
        expr = n + (n + 1)
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expr - 1, 2)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "consecutive_two_sum",
            given=["n を整数とする。"],
            to_prove=to_prove,
            step1="連続する2つの整数を n, n+1 と表す。",
            step2=f"n+(n+1) = {expanded_str}",
            step3=f"{expanded_str} = 2({core_str})+1",
            step4=f"{core_str} は整数だから 2({core_str})+1 は奇数である。",
            step1_reason="整数の表し方",
            step2_reason="式を整理する",
            step3_reason="2でくくり1を加える",
            step4_reason="奇数の定義",
            conclusion="よって連続する2つの整数の和は奇数である。",
        )

    def _solve_consecutive_three_sum(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "連続する3つの整数の和は3の倍数である"
        expr = n + (n + 1) + (n + 2)
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expr, 3)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "consecutive_three_sum",
            given=["n を整数とする。"],
            to_prove=to_prove,
            step1="連続する3つの整数を n, n+1, n+2 と表す。",
            step2=f"n+(n+1)+(n+2) = {expanded_str}",
            step3=f"{expanded_str} = 3({core_str})",
            step4=f"{core_str} は整数だから 3({core_str}) は3の倍数である。",
            step1_reason="整数の表し方",
            step2_reason="式を整理する",
            step3_reason="3でくくる",
            step4_reason="3の倍数の定義",
            conclusion="よって連続する3つの整数の和は3の倍数である。",
        )

    def _solve_consecutive_two_odds_sum(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "連続する2つの奇数の和は4の倍数である"
        expr = (2 * n + 1) + (2 * n + 3)
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expr, 4)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "consecutive_two_odds_sum",
            given=["n を整数とする。"],
            to_prove=to_prove,
            step1="連続する2つの奇数を 2n+1, 2n+3 と表す。",
            step2=f"(2n+1)+(2n+3) = {expanded_str}",
            step3=f"{expanded_str} = 4({core_str})",
            step4=f"{core_str} は整数だから 4({core_str}) は4の倍数である。",
            step1_reason="奇数の表し方",
            step2_reason="式を整理する",
            step3_reason="4でくくる",
            step4_reason="4の倍数の定義",
            conclusion="よって連続する2つの奇数の和は4の倍数である。",
        )

    def _solve_square_diff_consecutive(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "連続する2つの整数で、大きい方の2乗から小さい方の2乗をひいた差は奇数である"
        expr = (n + 1) ** 2 - n ** 2
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expanded - 1, 2)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "square_diff_consecutive",
            given=["n を整数とする。"],
            to_prove=to_prove,
            step1="連続する2つの整数を n, n+1 と表す。",
            step2=f"(n+1)^2 - n^2 = {expanded_str}",
            step3=f"{expanded_str} = 2({core_str})+1",
            step4=f"{core_str} は整数だから 2({core_str})+1 は奇数である。",
            step1_reason="整数の表し方",
            step2_reason="式を展開して整理する",
            step3_reason="2でくくり1を加える",
            step4_reason="奇数の定義",
            conclusion="よって差は奇数である。",
        )

    def _solve_digit_two(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "2けたの自然数と、十の位と一の位を入れかえた数の和は11の倍数である"
        expr = (10 * a + b) + (10 * b + a)
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expr, 11)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "digit_two",
            given=["a, b を整数とする（a は十の位、b は一の位）。"],
            to_prove=to_prove,
            step1="2けたの自然数を 10a+b、入れかえた数を 10b+a と表す。",
            step2=f"(10a+b)+(10b+a) = {expanded_str}",
            step3=f"{expanded_str} = 11({core_str})",
            step4=f"{core_str} は整数だから 11({core_str}) は11の倍数である。",
            step1_reason="整数の表し方",
            step2_reason="式を整理する",
            step3_reason="11でくくる",
            step4_reason="11の倍数の定義",
            conclusion="よって2けたの自然数と入れかえた数の和は11の倍数である。",
        )

    def _solve_digit_three(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        to_prove = "3けたの自然数と、百の位と一の位を入れかえた数の差は99の倍数である"
        expr = (100 * a + 10 * b + c) - (100 * c + 10 * b + a)
        expanded = sympy.expand(expr)
        core = _verify_multiple_of(expr, 99)
        core_str = str(sympy.expand(core))
        expanded_str = str(expanded)
        return self._build_logic_step(
            atom,
            "digit_three",
            given=["a, b, c を整数とする。"],
            to_prove=to_prove,
            step1="3けたの自然数を 100a+10b+c、百の位と一の位を入れかえた数を 100c+10b+a と表す。",
            step2=f"(100a+10b+c)-(100c+10b+a) = {expanded_str}",
            step3=f"{expanded_str} = 99({core_str})",
            step4=f"{core_str} は整数だから 99({core_str}) は99の倍数である。",
            step1_reason="整数の表し方",
            step2_reason="式を整理する",
            step3_reason="99でくくる",
            step4_reason="99の倍数の定義",
            conclusion="よって3けたの自然数と入れかえた数の差は99の倍数である。",
        )
