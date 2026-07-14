"""分数⇔循環小数の相互変換まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**から答えと steps を導く。純粋・決定論・厳密（整数/
Fraction）演算であること。乱数は引かない。フロートは一切使わない（⑥鉄則）。

C3（g3_l16.calculation・有理数の形）クラスタの2セルを1つのモジュールに集約する。

- Lv1（fraction_to_repeating_decimal）: 既約分数 p/q（q は 2,5 以外の素因数を持ち、
  10 の累乗の約数でない＝小数は必ず循環する）を、長除法の余り追跡アルゴリズムで
  循環小数に変換する。余りが最初に現れたステップを記録し、同じ余りが再出現した
  時点までの商の桁が循環節。フロート変換は使わず、整数の余り・商の桁を1桁ずつ
  厳密に計算する。
- Lv2（repeating_decimal_to_fraction）: 循環小数の仕様（非循環部の桁数・循環節の
  桁）から、標準的な代数的手法 x=10^m(10^n-1)倍の式変形と同値の閉じた式
  frac = (整数部を除いた小数部の情報から) を Fraction で厳密に構成し、既約分数を
  返す（Fraction は自動で既約化する）。

【循環小数の記号の表記規約】（新設・コードベースに既存規約なし・本ソルバで新設）
表示形（display）は「循環節の最初と最後の数字の真上に点を打つ」教科書表記を、
結合文字（COMBINING DOT ABOVE, U+0307）を各該当数字の直後に置くことで再現する。
例: 5/11 = 0.454545... → 循環節「45」→ "0.4̇5̇"（画面表示は 0.4̇5̇）。
循環節が1桁のとき（例 1/3=0.333...）は最初と最後が同じ桁なので点は1つだけ
（"0.3̇" → 0.3̇）。機械比較用の srepr は結合文字を使わない ASCII-only な
正準形 "非循環部.(循環節)"（例 "0.(45)"／整数部なしは "0."を残す）を用いる。
"""
from __future__ import annotations

from fractions import Fraction

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver

_COMBINING_DOT = "̇"


def repeating_decimal_digits(p: int, q: int) -> tuple[str, str]:
    """既約分数 p/q（0<p<q, q に 2,5 以外の素因数あり）の非循環部・循環節を求める。

    長除法を整数の余りだけで進める（フロートは一切使わない・⑥鉄則）。
    余りの列 r_0=p, r_{k+1} = (r_k*10) mod q を追跡し、同じ余りが再出現した
    時点で循環開始位置と循環節の長さが確定する（古典的アルゴリズム）。
    戻り値: (non_repeating_digits, repeating_block)。両方とも "" ではない
    repeating_block を返す（呼び出し側は q が 2,5 以外の素因数を持つことを
    保証していることが前提＝非循環小数の入力は許さない）。
    """
    if not (0 < p < q):
        raise ValueError(f"p/q は 0<p<q の真分数を要求: p={p}, q={q}")
    seen_at: dict[int, int] = {}
    digits: list[str] = []
    r = p
    step = 0
    while r != 0 and r not in seen_at:
        seen_at[r] = step
        r *= 10
        digit, r = divmod(r, q)
        digits.append(str(digit))
        step += 1
    if r == 0:
        raise ValueError(f"p/q={p}/{q} は有限小数（循環しない）: q は 2,5 以外の素因数を持つ必要がある")
    start = seen_at[r]
    non_repeating = "".join(digits[:start])
    repeating = "".join(digits[start:])
    return non_repeating, repeating


def fmt_repeating_decimal(non_repeating: str, repeating: str) -> str:
    """循環小数の教科書表記（循環節の最初と最後の数字に結合点）を作る。"""
    if not repeating:
        raise ValueError("repeating が空: 循環小数ではない")
    if len(repeating) == 1:
        marked = repeating[0] + _COMBINING_DOT
    else:
        marked = repeating[0] + _COMBINING_DOT + repeating[1:-1] + repeating[-1] + _COMBINING_DOT
    return f"0.{non_repeating}{marked}"


def canonical_repeating_decimal(non_repeating: str, repeating: str) -> str:
    """機械比較用の ASCII-only 正準形 "0.<非循環部>(<循環節>)"。"""
    return f"0.{non_repeating}({repeating})"


def fraction_from_repeating_decimal(non_repeating: str, repeating: str) -> Fraction:
    """非循環部 non_repeating・循環節 repeating（共に十進数字の文字列）から厳密な
    Fraction を構成する（Fraction は自動で既約化する）。

    標準的な代数式: 0.d1...dm(e1...en) = (D - d)/(10^m*(10^n-1)) ここで
    D = d1...dm e1...en を1つの整数として読んだもの、d = d1...dm（非循環部のみ、
    空なら 0）、m=非循環部の桁数、n=循環節の桁数。
    """
    if not repeating:
        raise ValueError("repeating が空: 循環小数ではない")
    m = len(non_repeating)
    n = len(repeating)
    d = int(non_repeating) if non_repeating else 0
    big = int(non_repeating + repeating)
    numerator = big - d
    denominator = (10 ** m) * (10 ** n - 1)
    return Fraction(numerator, denominator)


# ---------------------------------------------------------------------------
# math.fraction_to_repeating_decimal（g3_l16.calculation Lv1）
# ---------------------------------------------------------------------------
_FRACTION_TO_DECIMAL_STEPS: list[str] = ["long_division_track_remainders", "identify_repeating_block"]

_FRACTION_TO_DECIMAL_NARRATION: dict[str, str] = {
    "long_division_track_remainders": "分子を分母で割り進め、そのつど現れる余りを記録していく。",
    "identify_repeating_block": "同じ余りが再び現れた区間の商の並びを、循環節として書き出す。",
}

_FRACTION_TO_DECIMAL_PHRASE: dict[str, str] = {
    "long_division_track_remainders": "余りを記録しながら割り進める",
}


@register_solver("math.fraction_to_repeating_decimal")
def fraction_to_repeating_decimal(p: int, q: int) -> Solution:
    """既約分数 p/q を循環小数に変換する（C3 g3_l16.calculation Lv1）。

    p, q（整数）だけから長除法の余り追跡で循環小数を導く（recipe の構成内訳は
    見ない・double-solve）。答えは循環小数の表示を display に、ASCII-only な
    正準形を srepr に持つ SymbolicAnswer（sympy では表現できない値のため、
    srepr は機械比較用の独自正準形の文字列 = 既存パックの sigfig 等と同型の
    プレーン文字列 srepr の前例に倣う）。
    """
    p, q = int(p), int(q)
    non_repeating, repeating = repeating_decimal_digits(p, q)
    disp = fmt_repeating_decimal(non_repeating, repeating)
    srepr = canonical_repeating_decimal(non_repeating, repeating)

    ops = _FRACTION_TO_DECIMAL_STEPS
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _FRACTION_TO_DECIMAL_PHRASE.get(op, ""),
            narration=_FRACTION_TO_DECIMAL_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.repeating_decimal_to_fraction（g3_l16.calculation Lv2）
# ---------------------------------------------------------------------------
_DECIMAL_TO_FRACTION_STEPS: list[str] = ["set_up_algebraic_equation", "solve_for_fraction"]

_DECIMAL_TO_FRACTION_NARRATION: dict[str, str] = {
    "set_up_algebraic_equation": "循環小数を文字でおき、桁をずらした式との差を作って循環部分を消す。",
    "solve_for_fraction": "できた等式を整理し、分数の形に直して約分する。",
}

_DECIMAL_TO_FRACTION_PHRASE: dict[str, str] = {
    "set_up_algebraic_equation": "桁をずらした式の差を作る",
}


@register_solver("math.repeating_decimal_to_fraction")
def repeating_decimal_to_fraction(non_repeating: str, repeating: str) -> Solution:
    """循環小数（非循環部 non_repeating・循環節 repeating の桁文字列）を分数に
    変換する（C3 g3_l16.calculation Lv2）。

    非循環部・循環節の桁だけから Fraction の厳密演算で導く（recipe の構成内訳は
    見ない・double-solve）。答えは既約分数の SymbolicAnswer（srepr は sympy
    Rational の srepr、display は "p/q" 形）。
    """
    frac = fraction_from_repeating_decimal(non_repeating, repeating)
    rational = sympy.Rational(frac.numerator, frac.denominator)
    srepr = sympy.srepr(rational)
    disp = str(rational)

    ops = _DECIMAL_TO_FRACTION_STEPS
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _DECIMAL_TO_FRACTION_PHRASE.get(op, ""),
            narration=_DECIMAL_TO_FRACTION_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "repeating_decimal_digits",
    "fmt_repeating_decimal",
    "canonical_repeating_decimal",
    "fraction_from_repeating_decimal",
    "fraction_to_repeating_decimal",
    "repeating_decimal_to_fraction",
]
