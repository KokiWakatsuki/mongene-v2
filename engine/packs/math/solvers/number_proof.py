"""文字式で数の性質を説明する（form: proof）— 命題の生成器と説明の組み立て。

**問題を手で書かない。** 命題は「型（テンプレート）＋パラメータ」で持ち、
説明の式変形は sympy で実際に展開・整理して組み立てる。示すべき性質
（「11 の倍数」「奇数」「ある整数の2乗」）すらここでは書かず、
**展開した式から導く**（`derive_goal`）——係数の最大公約数が 2 以上なら
その数の倍数、1 なら平方数か奇数か、を式そのものに聞く。だから
「連続する3つの偶数の和は6の倍数」を人が入力する場面はどこにもない。

図形の証明（`geometry_proof`）が「構成 → 前向き推論 → 結論の選択」で問題を
作るのに対し、こちらは「数の集まりの表し方 → 演算 → 展開 → 性質の判定」で作る。
どちらも共通しているのは、**答えを先に書いてから問題文を作る（answer-first）の
逆をやる**ことである。

## 増やし方
`_TEMPLATES` に型を1つ足せば、その型のパラメータ軸の直積だけ問題が増える。
型が返すのは「日本語の言い方」と「sympy の式」だけで、説明文の骨格
（`proof_lines` / `render_proof_text`）と性質の判定（`derive_goal`）は共有する。

## 検証
`build_proposition` は
  1. 恒等式の検査（`content * quotient == expanded` を sympy で）
  2. 数値代入による検算（文字に整数を入れて、実際に割り切れる／平方数である／奇数である）
の2つを必ず通す。①だけだと導出の写し間違いが素通りするので、②を独立に置く。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable

import sympy

from engine.core.contracts import ProofAnswer, ProofStep, Solution, Step
from engine.core.registry import register_solver

# ---------------------------------------------------------------------------
# 表示（教材表記）
# ---------------------------------------------------------------------------
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _disp(expr: sympy.Expr) -> str:
    """展開済みの式の表示形（`*` を落とし、冪を上付きにする）。

    例: `4*n**2 + 4*n + 1` -> "4n² + 4n + 1"。sympy の既定順序は
    「次数の高い順・同次数は辞書順」なので、**文字は辞書順に並べて引く**
    （`recipes.number_proof` が letters を sorted で渡す）ことで、
    手で組んだ表示（10a + b）と展開結果（11a + 11b）の並びが食い違わない。
    """
    s = str(sympy.sstr(expr))
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_SUPERSCRIPT), s)
    return s.replace("*", "")


def _lin_disp(coef: int, var: str, const: int) -> str:
    """1次式の表示（例 coef=2, var="n", const=-1 -> "2n - 1"）。"""
    head = var if coef == 1 else f"{coef}{var}"
    if const == 0:
        return head
    return f"{head} + {const}" if const > 0 else f"{head} - {-const}"


def _paren(display: str, expr: sympy.Expr) -> str:
    """和の形（項が2つ以上）ならかっこで囲む。単項ならそのまま。"""
    return f"({display})" if expr.is_Add else display


def _sq_disp(display: str, expr: sympy.Expr) -> str:
    """平方の表示（`(2n + 1)²` / `(2n)²` / `n²`）。

    **裸の文字以外は必ずかっこで囲む。** `2n` を `2n²` と書くと 2×n² と読めてしまう
    （最初の実装がこれを出していた）。
    """
    return f"{display}²" if expr.is_Symbol else f"({display})²"


def _mul_disp(da: str, ea: sympy.Expr, db: str, eb: sympy.Expr) -> str:
    """積の表示。`2n(2n + 2)` のように書けるときだけ並置し、それ以外は `×` を使う。

    かっこの付いた式のうしろに単項式を並置する（`(2n - 2)2n`）と読み違えるので、
    その形は作らない。
    """
    if ea.is_Add and eb.is_Add:
        return f"({da})({db})"
    if eb.is_Add:
        return f"{da}({db})"
    return f"{_paren(da, ea)} × {db}"


# ---------------------------------------------------------------------------
# 示すべき性質（式から導く）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Goal:
    """展開した式が満たす性質。**人が書くのではなく式から導く。**"""

    kind: str            # "multiple" | "square" | "odd"
    modulus: int         # multiple/odd のとき割り切れる数（square は 0）
    phrase: str          # 「11の倍数」「偶数」「奇数」「ある整数の2乗」
    form_display: str    # 「11(a + b)」「(2n + 1)²」「2 × n + 1」
    witness: sympy.Expr  # 整数であることを言う相手（商・平方の底）
    witness_display: str


def derive_goal(expanded: sympy.Expr) -> Goal | None:
    """展開した式が主張できる性質を判定する（できなければ None）。

    判定の順序に意味がある。係数の最大公約数（content）が 2 以上ならまず
    「その数の倍数」——`4n²` は「4 の倍数」であって「ある整数の2乗」ではない、
    というのが教科書の言い方だからである（台帳の g3_l13 の例がまさにこれ）。
    content が 1 のときだけ、平方数か奇数かを見る。
    """
    if not expanded.free_symbols:
        return None
    poly = sympy.Poly(expanded)
    coeffs: list[int] = []
    for c in poly.coeffs():
        if not c.is_Integer:
            return None
        coeffs.append(int(c))
    if not coeffs:
        return None

    content = 0
    for c in coeffs:
        content = math.gcd(content, abs(c))

    if content >= 2:
        quotient = sympy.expand(expanded / content)
        if sympy.expand(content * quotient - expanded) != 0:
            return None
        phrase = "偶数" if content == 2 else f"{content}の倍数"
        q_disp = _disp(quotient)
        form = f"{content}({q_disp})" if quotient.is_Add else f"{content} × {q_disp}"
        return Goal("multiple", content, phrase, form, quotient, q_disp)

    factored = sympy.factor(expanded)
    if factored.is_Pow and factored.exp == 2:
        base = sympy.expand(factored.base)
        if sympy.expand(base**2 - expanded) != 0:
            return None
        b_disp = _disp(base)
        return Goal("square", 0, "ある整数の2乗", _sq_disp(b_disp, base), base, b_disp)

    rest = sympy.expand(expanded - 1)
    if rest != 0 and rest.free_symbols:
        rest_poly = sympy.Poly(rest)
        if all(c.is_Integer and int(c) % 2 == 0 for c in rest_poly.coeffs()):
            quotient = sympy.expand(rest / 2)
            if sympy.expand(2 * quotient + 1 - expanded) != 0:
                return None
            q_disp = _disp(quotient)
            form = f"2 × ({q_disp}) + 1" if quotient.is_Add else f"2 × {q_disp} + 1"
            return Goal("odd", 2, "奇数", form, quotient, q_disp)
    return None


# ---------------------------------------------------------------------------
# 命題（型が組み立てて返すもの）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Proposition:
    prop_id: str
    letters: tuple[str, ...]       # 実際に使った文字（params に載る＝dup_key の材料）
    numbers: dict[str, int]        # 実際に使った軸の値（正規化済み・params に載る）
    letter_decl: str               # 「n を整数とする」
    representation: str            # 「連続する2つの奇数は 2n - 1、2n + 1 と表される」
    subject: str                   # 「連続する2つの奇数の和」
    combination_intro: str         # 「この2数の和は」
    combination_display: str       # 「(2n - 1) + (2n + 1)」
    intermediate_display: str      # 「4n² - 1 + 1」（要らなければ空）
    expr: sympy.Expr
    goal: Goal

    @property
    def letter_intro(self) -> str:
        return f"{self.letter_decl}と"

    @property
    def letters_phrase(self) -> str:
        return "、".join(self.letters)

    @property
    def statement(self) -> str:
        """命題そのもの（問題文に出る「〜になる」）。"""
        joint = "は、" if self.goal.kind == "square" else "は"
        return f"{self.subject}{joint}{self.goal.phrase}になる"


@dataclass(frozen=True)
class PropTemplate:
    prop_id: str
    n_letters: int
    axes: dict[str, tuple[int, ...]]
    build: Callable[[tuple[str, ...], dict[str, int]], dict[str, Any] | None]


# ---------------------------------------------------------------------------
# 型①: 連続する整数・偶数・奇数・k の倍数の和（g2_l7）
# ---------------------------------------------------------------------------
# (刻み k, 奇数フラグ, 個数)。**和が自明にならない組だけを載せる。**
# 除いた組の例:
#   (2,0,2) 連続する2つの偶数の和は偶数 … 結論が刻みそのままで、示す意味がない
#   (3,0,2) 連続する2つの3の倍数の和は3の倍数 … 同上（3の倍数どうしの和なので当たり前）
# 残した組は、結論の倍数が刻み k より大きくなる（＝式変形で初めて分かる）ものだけ。
_CONSEC_VARIANTS: tuple[tuple[int, int, int], ...] = (
    (1, 0, 2), (1, 0, 3), (1, 0, 4), (1, 0, 5),
    (2, 1, 2), (2, 1, 3), (2, 1, 4),
    (2, 0, 3), (2, 0, 4), (2, 0, 5),
    (3, 0, 3),
    (4, 0, 3),
    (5, 0, 3),
)


def _consec_noun(k: int, parity: int, count: int) -> str:
    if k == 1:
        base = "整数"
    elif k == 2:
        base = "奇数" if parity else "偶数"
    else:
        base = f"{k}の倍数"
    return f"連続する{count}つの{base}"


def _build_consecutive_sum(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    variant = numbers["variant"] % len(_CONSEC_VARIANTS)
    k, parity, count = _CONSEC_VARIANTS[variant]
    offset = numbers["offset"] % count           # 何番目を基準に置くか（表し方の違い）
    var = letters[0]
    sym = sympy.Symbol(var)

    exprs = []
    disps = []
    for i in range(count):
        const = parity + k * (i - offset)
        exprs.append(k * sym + const)
        disps.append(_lin_disp(k, var, const))
    noun = _consec_noun(k, parity, count)
    combination = " + ".join(_paren(d, e) for d, e in zip(disps, exprs, strict=True))
    return {
        "letters": letters[:1],
        "numbers": {"variant": variant, "offset": offset},
        "letter_decl": f"{var} を整数とする",
        "representation": f"{noun}は {'、'.join(disps)} と表される",
        "subject": f"{noun}の和",
        "combination_intro": "この2数の和は" if count == 2 else "これらの数の和は",
        "combination_display": combination,
        "intermediate_display": "",
        "expr": sum(exprs, sympy.Integer(0)),
    }


# ---------------------------------------------------------------------------
# 型②: 偶数・奇数どうしの和／差／積（g2_l7）
# ---------------------------------------------------------------------------
_PAIR_OPS = ("和", "差", "積")


def _build_parity_pair(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    p1, p2 = numbers["first"] % 2, numbers["second"] % 2
    op = numbers["op"] % 3
    x, y = letters[0], letters[1]
    ex = 2 * sympy.Symbol(x) + p1
    ey = 2 * sympy.Symbol(y) + p2
    dx, dy = _lin_disp(2, x, p1), _lin_disp(2, y, p2)
    n1 = "奇数" if p1 else "偶数"
    n2 = "奇数" if p2 else "偶数"
    pair_noun = f"2つの{n1}" if p1 == p2 else f"{n1}と{n2}"

    if op == 0:
        expr = ex + ey
        combination = f"{_paren(dx, ex)} + {_paren(dy, ey)}"
        subject = f"{pair_noun}の和"
    elif op == 1:
        expr = ex - ey
        combination = f"{_paren(dx, ex)} - {_paren(dy, ey)}"
        subject = f"{pair_noun}の差" if p1 == p2 else f"{n1}から{n2}をひいた差"
    else:
        expr = ex * ey
        combination = _mul_disp(dx, ex, dy, ey)
        subject = f"{pair_noun}の積"

    if p1 == p2:
        representation = f"2つの{n1}は {dx}、{dy} と表される"
    else:
        representation = f"{n1}は {dx}、{n2}は {dy} と表される"
    return {
        "letters": letters[:2],
        "numbers": {"first": p1, "second": p2, "op": op},
        "letter_decl": f"{x}、{y} を整数とする",
        "representation": representation,
        "subject": subject,
        "combination_intro": f"この2数の{_PAIR_OPS[op]}は",
        "combination_display": combination,
        # 積でも途中式は出さない（1回の展開で最終形になるため、書くと同じ式が2度出る）。
        "intermediate_display": "",
        "expr": expr,
    }


# ---------------------------------------------------------------------------
# 型③: 2けた・3けたの自然数と位を入れかえた数（g2_l8）
# ---------------------------------------------------------------------------
_PLACE_NAMES = {2: ("十の位", "一の位"), 3: ("百の位", "十の位", "一の位")}


def _digit_decl(letters: tuple[str, ...], digits: int) -> str:
    names = _PLACE_NAMES[digits]
    body = "、".join(f"{nm}を {ltr}" for nm, ltr in zip(names, letters, strict=True))
    return f"もとの数の{body} とする"


def _digit_expr(letters: tuple[str, ...], digits: int) -> tuple[sympy.Expr, str]:
    """位取りの式（例 2けた -> (10a + b, "10a + b")）。"""
    expr = sympy.Integer(0)
    parts: list[str] = []
    for i, ltr in enumerate(letters):
        weight = 10 ** (digits - 1 - i)
        expr += weight * sympy.Symbol(ltr)
        parts.append(ltr if weight == 1 else f"{weight}{ltr}")
    return expr, " + ".join(parts)


def _build_digit_swap(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    digits = 3 if numbers["digits"] % 2 else 2
    op = numbers["op"] % 2
    if digits == 3:
        op = 1  # 3けたの「和」は倍数にならない（101a + 20b + 101c）ので差だけ扱う
    letters = letters[:digits]
    original, orig_disp = _digit_expr(letters, digits)
    swapped_letters = (letters[-1], *letters[1:-1], letters[0])
    swapped, swap_disp = _digit_expr(swapped_letters, digits)

    head, tail = _PLACE_NAMES[digits][0], _PLACE_NAMES[digits][-1]
    if op == 0:
        expr = original + swapped
        combination = f"({orig_disp}) + ({swap_disp})"
        subject = f"{digits}けたの自然数と、その{head}と{tail}を入れかえてできる数の和"
        intro = "この2数の和は"
    else:
        expr = original - swapped
        combination = f"({orig_disp}) - ({swap_disp})"
        subject = f"{digits}けたの自然数から、その{head}と{tail}を入れかえてできる数をひいた差"
        intro = "もとの数から入れかえた数をひいた差は"
    return {
        "letters": letters,
        "numbers": {"digits": digits, "op": op},
        "letter_decl": _digit_decl(letters, digits),
        "representation": f"もとの数は {orig_disp}、入れかえた数は {swap_disp} と表される",
        "subject": subject,
        "combination_intro": intro,
        "combination_display": combination,
        "intermediate_display": "",
        "expr": expr,
    }


def _build_digit_minus_digitsum(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    digits = 3 if numbers["digits"] % 2 else 2
    letters = letters[:digits]
    original, orig_disp = _digit_expr(letters, digits)
    digit_sum = sum((sympy.Symbol(x) for x in letters), sympy.Integer(0))
    sum_disp = " + ".join(letters)
    return {
        "letters": letters,
        "numbers": {"digits": digits},
        "letter_decl": _digit_decl(letters, digits),
        "representation": f"もとの数は {orig_disp}、各位の数の和は {sum_disp} と表される",
        "subject": f"{digits}けたの自然数から、その各位の数の和をひいた差",
        "combination_intro": "もとの数から各位の数の和をひいた差は",
        "combination_display": f"({orig_disp}) - ({sum_disp})",
        "intermediate_display": "",
        "expr": original - digit_sum,
    }


# ---------------------------------------------------------------------------
# 型④: 積に数を加えた数（g3_l13・展開が要る）
# ---------------------------------------------------------------------------
def _build_product_plus(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    mode = numbers["mode"] % 4
    var = letters[0]
    sym = sympy.Symbol(var)

    if mode == 0:
        # **軸には「値」ではなく「番号」を残す。** 値（2/4/6）を残すと、その値を
        # もう一度この関数に食わせたとき別の問題になる（params からの組み直しが
        # 壊れ、問題文と説明が食い違う）。
        gap_i = numbers["gap"] % 3
        gap = (2, 4, 6)[gap_i]
        add = (gap // 2) ** 2
        a, b = sym, sym + gap
        da, db = _lin_disp(1, var, 0), _lin_disp(1, var, gap)
        noun = f"差が{gap}である2つの整数"
        used = {"mode": mode, "gap": gap_i}
    elif mode == 1:
        offset = numbers["offset"] % 2
        add = 1
        c1, c2 = 1 - 2 * offset, 3 - 2 * offset
        a, b = 2 * sym + c1, 2 * sym + c2
        da, db = _lin_disp(2, var, c1), _lin_disp(2, var, c2)
        noun = "連続する2つの奇数"
        used = {"mode": mode, "offset": offset}
    elif mode == 2:
        offset = numbers["offset"] % 2
        add = 1
        c1, c2 = -2 * offset, 2 - 2 * offset
        a, b = 2 * sym + c1, 2 * sym + c2
        da, db = _lin_disp(2, var, c1), _lin_disp(2, var, c2)
        noun = "連続する2つの偶数"
        used = {"mode": mode, "offset": offset}
    else:
        offset = numbers["offset"] % 2
        c1, c2 = -offset, 1 - offset
        a, b = sym + c1, sym + c2
        da, db = _lin_disp(1, var, c1), _lin_disp(1, var, c2)
        noun = "連続する2つの整数"
        used = {"mode": mode, "offset": offset}
        expr = a * b + b
        combination = f"{_mul_disp(da, a, db, b)} + {_paren(db, b)}"
        return {
            "letters": letters[:1],
            "numbers": used,
            "letter_decl": f"{var} を整数とする",
            "representation": f"{noun}は {da}、{db} と表される",
            "subject": f"{noun}の積に大きい方の数を加えた数",
            "combination_intro": "この2数の積に大きい方の数を加えた数は",
            "combination_display": combination,
            "intermediate_display": f"{_disp(sympy.expand(a * b))} + {_paren(db, b)}",
            "expr": expr,
        }

    expr = a * b + add
    combination = f"{_mul_disp(da, a, db, b)} + {add}"
    return {
        "letters": letters[:1],
        "numbers": used,
        "letter_decl": f"{var} を整数とする",
        "representation": f"{noun}は {da}、{db} と表される",
        "subject": f"{noun}の積に{add}を加えた数",
        "combination_intro": f"この2数の積に{add}を加えた数は",
        "combination_display": combination,
        "intermediate_display": f"{_disp(sympy.expand(a * b))} + {add}",
        "expr": expr,
    }


# ---------------------------------------------------------------------------
# 型⑤: 平方の差（g3_l13）
# ---------------------------------------------------------------------------
def _build_square_difference(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    kind = numbers["kind"] % 3
    offset = numbers["offset"] % 2
    var = letters[0]
    sym = sympy.Symbol(var)

    if kind == 0:
        gap_i = numbers["gap"] % 4          # 値ではなく番号を残す（組み直しの安定性）
        gap = (1, 2, 3, 4)[gap_i]
        small_c, big_c = -offset, gap - offset
        small, big = sym + small_c, sym + big_c
        ds, db = _lin_disp(1, var, small_c), _lin_disp(1, var, big_c)
        noun = "連続する2つの整数" if gap == 1 else f"差が{gap}である2つの整数"
        used = {"kind": kind, "gap": gap_i, "offset": offset}
    else:
        parity = 1 if kind == 2 else 0
        small_c, big_c = parity - 2 * offset, parity + 2 - 2 * offset
        small, big = 2 * sym + small_c, 2 * sym + big_c
        ds, db = _lin_disp(2, var, small_c), _lin_disp(2, var, big_c)
        noun = "連続する2つの奇数" if parity else "連続する2つの偶数"
        used = {"kind": kind, "offset": offset}

    expr = big**2 - small**2
    combination = f"{_sq_disp(db, big)} - {_sq_disp(ds, small)}"
    big_ex, small_ex = sympy.expand(big**2), sympy.expand(small**2)
    intermediate = f"{_paren(_disp(big_ex), big_ex)} - {_paren(_disp(small_ex), small_ex)}"
    return {
        "letters": letters[:1],
        "numbers": used,
        "letter_decl": f"{var} を整数とする",
        "representation": f"{noun}は {ds}、{db} と表される",
        "subject": f"{noun}について、大きい方の平方から小さい方の平方をひいた差",
        "combination_intro": "大きい方の数の平方から小さい方の数の平方をひいた差は",
        "combination_display": combination,
        "intermediate_display": intermediate,
        "expr": expr,
    }


# ---------------------------------------------------------------------------
# 型⑥: 平方の和（g3_l13）
# ---------------------------------------------------------------------------
def _build_square_sum(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    kind = numbers["kind"] % 3
    offset = numbers["offset"] % 2
    var = letters[0]
    sym = sympy.Symbol(var)
    if kind == 0:
        c1, c2 = -offset, 1 - offset
        a, b = sym + c1, sym + c2
        da, db = _lin_disp(1, var, c1), _lin_disp(1, var, c2)
        noun = "連続する2つの整数"
    else:
        parity = 1 if kind == 2 else 0
        c1, c2 = parity - 2 * offset, parity + 2 - 2 * offset
        a, b = 2 * sym + c1, 2 * sym + c2
        da, db = _lin_disp(2, var, c1), _lin_disp(2, var, c2)
        noun = "連続する2つの奇数" if parity else "連続する2つの偶数"

    expr = a**2 + b**2
    combination = f"{_sq_disp(da, a)} + {_sq_disp(db, b)}"
    a_ex, b_ex = sympy.expand(a**2), sympy.expand(b**2)
    intermediate = f"{_paren(_disp(a_ex), a_ex)} + {_paren(_disp(b_ex), b_ex)}"
    return {
        "letters": letters[:1],
        "numbers": {"kind": kind, "offset": offset},
        "letter_decl": f"{var} を整数とする",
        "representation": f"{noun}は {da}、{db} と表される",
        "subject": f"{noun}の平方の和",
        "combination_intro": "この2数の平方の和は",
        "combination_display": combination,
        "intermediate_display": intermediate,
        "expr": expr,
    }


# ---------------------------------------------------------------------------
# 型⑦: 2けたの自然数と入れかえた数の平方の差（g3_l13）
# ---------------------------------------------------------------------------
def _build_digit_swap_square_difference(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    letters = letters[:2]
    original, orig_disp = _digit_expr(letters, 2)
    swapped, swap_disp = _digit_expr((letters[1], letters[0]), 2)
    expr = original**2 - swapped**2
    o_ex, s_ex = sympy.expand(original**2), sympy.expand(swapped**2)
    intermediate = f"{_paren(_disp(o_ex), o_ex)} - {_paren(_disp(s_ex), s_ex)}"
    return {
        "letters": letters,
        "numbers": {},
        "letter_decl": _digit_decl(letters, 2),
        "representation": f"もとの数は {orig_disp}、入れかえた数は {swap_disp} と表される",
        "subject": "2けたの自然数の平方から、その十の位と一の位を入れかえてできる数の平方をひいた差",
        "combination_intro": "もとの数の平方から入れかえた数の平方をひいた差は",
        "combination_display": f"({orig_disp})² - ({swap_disp})²",
        "intermediate_display": intermediate,
        "expr": expr,
    }


# ---------------------------------------------------------------------------
# 型のカタログ
# ---------------------------------------------------------------------------
_TEMPLATES: dict[str, PropTemplate] = {
    t.prop_id: t
    for t in (
        PropTemplate(
            "consecutive_sum", 1,
            {"variant": tuple(range(len(_CONSEC_VARIANTS))), "offset": (0, 1, 2, 3, 4)},
            _build_consecutive_sum,
        ),
        PropTemplate(
            "parity_pair_op", 2,
            {"first": (0, 1), "second": (0, 1), "op": (0, 1, 2)},
            _build_parity_pair,
        ),
        PropTemplate(
            "digit_swap", 3,
            {"digits": (0, 1), "op": (0, 1)},
            _build_digit_swap,
        ),
        PropTemplate(
            "digit_minus_digitsum", 3,
            {"digits": (0, 1)},
            _build_digit_minus_digitsum,
        ),
        PropTemplate(
            "product_plus", 1,
            {"mode": (0, 1, 2, 3), "gap": (0, 1, 2), "offset": (0, 1)},
            _build_product_plus,
        ),
        PropTemplate(
            "square_difference", 1,
            {"kind": (0, 1, 2), "gap": (0, 1, 2, 3), "offset": (0, 1)},
            _build_square_difference,
        ),
        PropTemplate(
            "square_sum", 1,
            {"kind": (0, 1, 2), "offset": (0, 1)},
            _build_square_sum,
        ),
        PropTemplate(
            "digit_swap_square_difference", 2,
            {},
            _build_digit_swap_square_difference,
        ),
    )
}

TEMPLATES = _TEMPLATES


# ---------------------------------------------------------------------------
# 命題の組み立て（＋2重の検証）
# ---------------------------------------------------------------------------
_CHECK_VALUES = (-7, -3, -1, 0, 1, 2, 5, 8, 13)


def _numeric_check(expr: sympy.Expr, goal: Goal, letters: tuple[str, ...]) -> bool:
    """文字に整数を入れて、主張した性質が実際に成り立つかを数値で確かめる。

    恒等式の検査（sympy の式変形）とは**独立な経路**の検算。式変形の写し間違いや、
    性質の判定の取り違えは、ここで数値として落ちる。
    """
    syms = [sympy.Symbol(x) for x in letters]
    for i, v0 in enumerate(_CHECK_VALUES):
        subs = {s: _CHECK_VALUES[(i + j * 3) % len(_CHECK_VALUES)] for j, s in enumerate(syms)}
        subs[syms[0]] = v0
        value = sympy.expand(expr).subs(subs)
        if not getattr(value, "is_Integer", False):
            return False
        n = int(value)
        if goal.kind == "multiple":
            if n % goal.modulus != 0:
                return False
        elif goal.kind == "odd":
            if n % 2 != 1:
                return False
        else:  # square
            if n < 0 or math.isqrt(n) ** 2 != n:
                return False
    return True


def _assert_round_trip(
    tpl: PropTemplate, letters: tuple[str, ...], raw: dict[str, Any]
) -> None:
    """正規化した軸の値を食わせ直しても**同じ命題**になることを確かめる。

    ここが崩れると、recipe が作った命題（問題文に出る）と、checker が params から
    組み直した命題（模範解答に出る）が食い違う——「差が2である2つの整数」と
    問題文が言っているのに説明は「差が6」で始まる、という事故が実際に起きた。
    G-Q1 は recipe と checker のどちらも組み直し側を見るので、この食い違いを
    捕まえられない。だから生成器の側で閉じる。
    """
    again = tpl.build(letters, dict(raw["numbers"]))
    if again is None:
        raise ValueError(f"{tpl.prop_id}: 正規化した軸の値で命題を組み直せない: {raw['numbers']}")
    if dict(again["numbers"]) != dict(raw["numbers"]) or sympy.expand(
        again["expr"] - raw["expr"]
    ) != 0:
        raise ValueError(
            f"{tpl.prop_id}: 軸の正規化が安定していない"
            f"（{raw['numbers']} -> {again['numbers']}）。軸には値でなく番号を残すこと。"
        )


def build_proposition(
    prop_id: str, letters: tuple[str, ...], numbers: dict[str, int]
) -> Proposition | None:
    """型＋パラメータから命題を組み立てる。質・検証に落ちたら None。"""
    tpl = _TEMPLATES[prop_id]
    raw = tpl.build(tuple(letters), dict(numbers))
    if raw is None:
        return None
    _assert_round_trip(tpl, tuple(letters), raw)
    expr = sympy.expand(raw["expr"])
    goal = derive_goal(expr)
    if goal is None:
        return None
    used_letters = tuple(raw["letters"])
    if not used_letters:
        return None
    if not _numeric_check(expr, goal, used_letters):
        return None
    return Proposition(
        prop_id=prop_id,
        letters=used_letters,
        numbers=dict(raw["numbers"]),
        letter_decl=raw["letter_decl"],
        representation=raw["representation"],
        subject=raw["subject"],
        combination_intro=raw["combination_intro"],
        combination_display=raw["combination_display"],
        intermediate_display=raw["intermediate_display"],
        expr=expr,
        goal=goal,
    )


# ---------------------------------------------------------------------------
# 説明文の組み立て
# ---------------------------------------------------------------------------
# **Lv の差はここに出る。** 誘導あり（Lv2）は「どう文字でおくか」を問題文が与えるので
# 説明は式を書き出すところから始まり、誘導なし（Lv3）は文字のおき方と表し方を
# 自分で構成する2行が先頭に付く。op 列が変わる＝ level_sep の材料になる。
_GUIDED_OPS = ("form_expression", "expand_expression", "rewrite_to_goal_form", "conclude_property")
_OPEN_OPS = ("choose_letters", "represent_numbers", *_GUIDED_OPS)

_NARRATION = {
    "choose_letters": "説明したい数を、どの文字を使って表すかを決める。",
    "represent_numbers": "決めた文字を使って、対象の数をそれぞれ式で表す。",
    "form_expression": "問題が問うている計算を、文字式のまま書き出す。",
    "expand_expression": "かっこをはずして計算し、同類項をまとめる。",
    "rewrite_to_goal_form": "示したい性質が読み取れる形に、式を書き直す。",
    "conclude_property": "文字が整数であることを確かめ、示したい性質が成り立つと結論づける。",
}


def _conclusion_sentence(prop: Proposition) -> str:
    goal = prop.goal
    lead = f"{prop.letters_phrase} は整数だから"
    if goal.witness.is_Symbol:
        body = f"{lead}、{goal.form_display} は{goal.phrase}である。"
    else:
        body = (
            f"{lead}、{goal.witness_display} も整数であり、"
            f"{goal.form_display} は{goal.phrase}である。"
        )
    return f"{body}したがって、{prop.statement}。"


def _chain_segments(prop: Proposition) -> list[str]:
    """式変形の連鎖（左から順に等号でつなぐ断片）。**同じ式を2度書かない。**

    「2a + 2b = 2a + 2b = 2(a + b)」のように、書き出した式がすでに整理済みだと
    同じ式が続けて出る。読み手には無意味な行なので、連続する重複は落とす。
    """
    segments = [prop.combination_display]
    if prop.intermediate_display:
        segments.append(prop.intermediate_display)
    segments.append(_disp(prop.expr))
    segments.append(prop.goal.form_display)
    out: list[str] = []
    for s in segments:
        if not out or out[-1] != s:
            out.append(s)
    return out


def proof_lines(prop: Proposition, guided: bool) -> list[ProofStep]:
    """証明（説明）の行。**行の列がそのまま採点粒度と op 列になる。**"""
    expanded = _disp(prop.expr)
    chain = f"= {expanded}"
    if prop.intermediate_display and prop.intermediate_display != expanded:
        chain = f"= {prop.intermediate_display} = {expanded}"

    lines: list[ProofStep] = []
    if not guided:
        lines.append(
            ProofStep(claim=f"{prop.letter_decl}。", reason="", op="choose_letters")
        )
        lines.append(
            ProofStep(claim=f"{prop.representation}。", reason="", op="represent_numbers")
        )
    lines.append(
        ProofStep(
            claim=prop.combination_display,
            reason=prop.combination_intro,
            op="form_expression",
        )
    )
    lines.append(
        ProofStep(claim=chain, reason="かっこをはずして計算する", op="expand_expression")
    )
    lines.append(
        ProofStep(
            claim=f"= {prop.goal.form_display}",
            reason=f"{prop.goal.phrase}の形に表す",
            op="rewrite_to_goal_form",
        )
    )
    lines.append(
        ProofStep(claim=_conclusion_sentence(prop), reason="", op="conclude_property")
    )
    return lines


def render_proof_text(prop: Proposition, guided: bool) -> str:
    """行から説明文を組む。誘導ありは問題文の書き出しに続く形（式から始まる）。"""
    parts: list[str] = []
    if not guided:
        parts.append(f"{prop.letter_intro}、{prop.representation}。")
        parts.append(prop.combination_intro)
    parts.append(" = ".join(_chain_segments(prop)))
    parts.append(_conclusion_sentence(prop))
    return "\n".join(parts)


def guided_premises(prop: Proposition) -> str:
    """誘導あり（Lv2）で問題文に置く「書き出し」。"""
    return f"{prop.letter_intro}、{prop.representation}。{prop.combination_intro}……"


# ---------------------------------------------------------------------------
# solver（double-solve の再計算経路）
# ---------------------------------------------------------------------------
@register_solver("math.number_property_proof")
def number_property_proof(
    prop_id: object, letters: object, numbers: object, guided: object
) -> Solution:
    """型＋パラメータだけから、説明（証明）をもう一度組み立て直す。

    答えの文字列は params に入っていないので、checker はここを呼ぶだけで
    「同じ命題・同じ筋道に到達するか」を独立に確かめられる（G-Q1）。
    """
    letters_t = tuple(str(x) for x in (letters or ()))  # type: ignore[union-attr]
    numbers_d = {str(k): int(v) for k, v in dict(numbers or {}).items()}  # type: ignore[arg-type]
    prop = build_proposition(str(prop_id), letters_t, numbers_d)
    if prop is None:
        raise ValueError(f"命題を組み直せなかった: {prop_id!r} {letters_t} {numbers_d}")
    is_guided = bool(guided)
    lines = proof_lines(prop, is_guided)
    expected_ops = _GUIDED_OPS if is_guided else _OPEN_OPS
    assert tuple(ln.op for ln in lines) == expected_ops, "op 列が宣言と食い違った"

    answer = ProofAnswer(text=render_proof_text(prop, is_guided), lines=lines)
    steps = [
        Step(
            op=ln.op,
            args=[],
            result_srepr="",
            result_display=ln.claim,
            narration=_NARRATION[ln.op],
        )
        for ln in lines
    ]
    return Solution(answer=answer, steps=steps)


__all__ = [
    "Goal",
    "Proposition",
    "PropTemplate",
    "TEMPLATES",
    "build_proposition",
    "derive_goal",
    "guided_premises",
    "number_property_proof",
    "proof_lines",
    "render_proof_text",
]
