"""三平方の定理を面積で証明する／その逆で直角を説明する（form: proof）— g3_l51 / g3_l52。

**問題を手で書かない。** 証明は「型（どの図でどう分割するか）＋パラメータ（文字・
頂点の記号・図の形）」で持ち、面積の式変形は sympy に実際にやらせる。
`solvers.number_proof` が「数の集まりの表し方 → 演算 → 展開 → 性質の判定」で
命題を作るのに対し、こちらは
  「図の分け方 → 同じ面積の2通りの表し方 → 展開 → 共通項を消す」
で証明を作る。**a² + b² = c² を人が式として書き下す場面はどこにもない**——
2通りの面積の式の差を sympy に取らせ、それが a² + b² - c² の定数倍であることを
確かめて初めて「その図で定理が示せる」と判定する（`_verify_area_identity`）。

## 面積証明の型（`_AREA_TEMPLATES`）
    outer_square           1辺 a+b の正方形 ＝ 直角三角形4つ ＋ 1辺 c の正方形
    outer_square_subtract  1辺 c の正方形 ＝ 1辺 a+b の正方形 － 直角三角形4つ
    inner_square           1辺 c の正方形 ＝ 直角三角形4つ ＋ 1辺 b-a の正方形
    inner_square_subtract  1辺 b-a の正方形 ＝ 1辺 c の正方形 － 直角三角形4つ
    trapezoid              台形（Garfield）＝ 直角三角形2つ ＋ 直角二等辺三角形1つ
型が返すのは「日本語の言い方」と「2通りの面積の式」だけで、展開・共通項の消去・
両辺の倍率（台形だけ 2 倍が要る）は共有のコード（`_reduce`）が式から導く。

## 三平方の定理の逆（`_CONVERSE_CONTEXTS`）
ピタゴラス数を (m, n) から (m²-n², 2mn, m²+n²) と倍数で生成する。3辺の長さから
a² + b² と c² を実際に計算し、一致することを確かめてから「直角である」と結論する。

## 検証
どちらも
  1. 恒等式の検査（sympy）— 面積の差が a²+b²-c² の定数倍か／3辺が a²+b²=c² を満たすか
  2. 具体の直角三角形（3:4:5 など）を代入した数値の検算
の2つを通す。①だけだと式の写し間違いが素通りするので、②を独立に置く。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
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

    `solvers.number_proof._disp` と同じ規約（教材表記）。あちらの実装には触らない
    約束なので、同じ規約をここに置く（import して共有すると、あちらの都合で
    表記が変わったときにこちらの図と食い違う）。
    """
    s = str(sympy.sstr(expr))
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_SUPERSCRIPT), s)
    return s.replace("*", "")


def _sq(display: str, atomic: bool) -> str:
    """平方の表示。**裸の文字以外は必ずかっこで囲む**（`a + b` を `a + b²` と書かない）。"""
    return f"{display}²" if atomic else f"({display})²"


# ---------------------------------------------------------------------------
# 式の「辺」（項の列として持つ）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Term:
    """面積の式の1項。表示形と sympy 式を組で持つ。

    表示を sympy の printer に任せないのは、`(1/2)ab × 4`（直角三角形4つ分）のような
    **計算の途中を残した書き方**が教材の言い方だからである（sympy は 2ab と書く）。
    展開した形だけは printer に任せる（`_disp`）。
    """

    expr: sympy.Expr
    display: str
    sign: int = 1


@dataclass(frozen=True)
class Side:
    """等式の片側（項の列）。"""

    terms: tuple[Term, ...]

    def display(self, *, expanded: bool = False) -> str:
        out = ""
        for i, t in enumerate(self.terms):
            body = _disp(sympy.expand(t.expr)) if expanded else t.display
            if expanded and t.sign < 0 and sympy.expand(t.expr).is_Add:
                body = f"({body})"
            if i == 0:
                out = body if t.sign > 0 else f"-{body}"
            else:
                out += f" + {body}" if t.sign > 0 else f" - {body}"
        return out


def _side_value(side: Side) -> sympy.Expr:
    return sympy.expand(sympy.Add(*[t.sign * t.expr for t in side.terms]))


# ---------------------------------------------------------------------------
# 図形の記号（頂点の名前）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FigureNames:
    """図の頂点につける記号。誘導ありのときだけ使う（誘導なしは図を言葉で述べる）。"""

    outer: str   # 外側の四角形の4頂点（例 "ABCD"）
    inner: str   # 内側の四角形の4頂点（例 "EFGH"）。台形では先頭1文字だけ使う


# ---------------------------------------------------------------------------
# 面積証明の型
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AreaProof:
    """1つの面積証明（型＋パラメータから組み立てた結果）。"""

    proof_id: str
    letters: tuple[str, str, str]      # (直角をはさむ辺, もう一方, 斜辺)
    names: FigureNames | None
    quantity: str                      # 「正方形 ABCD の面積」（2通りに表す対象）
    first: Side
    first_reason: str
    second: Side
    second_reason: str
    arrangement: str                   # 図の説明（誘導ありでは問題文、なしでは証明の1行目）
    arrangement_reason: str
    guided_setup: str                  # 誘導ありの問題文（内側の図形の記号もここで名づける）
    split_fact: str                    # 「大きい正方形の各辺は a と b に分かれる」
    split_reason: str
    inner_fact: str                    # 「内側の四角形は1辺 c の正方形である」
    inner_reason: str
    figure_kind: str                   # 図を描くときの型（visuals 側の分岐）
    flip: bool                         # 結論を c² = a² + b² の向きで書くか
    equal_legs_ok: bool = False        # a = b でも成り立つ型か（内側の正方形は潰れる）
    numbers: dict[str, int] = field(default_factory=dict)

    @property
    def conclusion_display(self) -> str:
        a, b, c = self.letters
        left, right = f"{a}² + {b}²", f"{c}²"
        return f"{right} = {left}" if self.flip else f"{left} = {right}"


AreaBuilder = Callable[[tuple[str, str, str], FigureNames | None], dict[str, Any]]


def _phrases(names: FigureNames | None, kind: str) -> tuple[str, str]:
    """(外側の図形の呼び方, 内側の図形の呼び方)。誘導なしでは記号を使わず言葉で呼ぶ。

    記号を付けるときは**空白を入れない**（「正方形ABCDの面積」）。この呼び方は
    直後に「の面積」「は」が続くので、`正方形 ABCD` と空けると語の途中に空白が入る。
    エンジンの幾何側の出力（「四角形ABCDに対角線ACを引き」）とも揃う。
    """
    if names is None:
        if kind == "trapezoid":
            return "台形", "直角二等辺三角形"
        if kind == "outer":
            return "大きい正方形", "内側の正方形"
        return "大きい正方形", "内側の小さい正方形"
    if kind == "trapezoid":
        e = names.inner[0]
        o = names.outer
        return f"台形{o}", f"△{o[1]}{e}{o[2]}"
    return f"正方形{names.outer}", f"正方形{names.inner}"


def _guided_setup(arrangement: str, names: FigureNames | None, naming: str) -> str:
    """誘導あり（Lv3）の問題文に置く図の設定。

    誘導ありの証明は内側の図形を**記号で**呼ぶ（「正方形EFGHの面積は c²」）。
    問題文がその記号を導入していないと、答えに出どころのない記号が現れる。
    並べ方の説明に「内側にできる四角形EFGHは…になる」を続けて、
    **証明が使う記号をすべて問題文の側で名づける**。
    誘導なしでは記号を使わない（`_phrases` が言葉で呼ぶ）ので、そのまま返す。
    """
    return arrangement if names is None else f"{arrangement}。{naming}"


def _triangles_term(a: str, b: str, sym_a: sympy.Expr, sym_b: sympy.Expr, n: int) -> Term:
    """直角三角形 n 個分の面積（`(1/2)ab × 4` の形で書く）。"""
    return Term(sympy.Rational(n, 2) * sym_a * sym_b, f"(1/2){a}{b} × {n}")


def _build_outer_square(
    letters: tuple[str, str, str], names: FigureNames | None
) -> dict[str, Any]:
    a, b, c = letters
    sa, sb, sc = (sympy.Symbol(x) for x in letters)
    outer_ph, inner_ph = _phrases(names, "outer")
    arrangement = (
        f"直角をはさむ2辺の長さが {a}、{b}、斜辺の長さが {c} である合同な直角三角形を"
        f"4つ並べて、1辺の長さが {a} + {b} の{outer_ph}をつくる"
    )
    return {
        "quantity": f"{outer_ph}の面積",
        "first": Side((Term((sa + sb) ** 2, _sq(f"{a} + {b}", atomic=False)),)),
        "first_reason": f"{outer_ph}は1辺の長さが {a} + {b} だから",
        "second": Side((_triangles_term(a, b, sa, sb, 4), Term(sc**2, _sq(c, atomic=True)))),
        "second_reason": f"{outer_ph}は合同な直角三角形4つと{inner_ph}に分けられるから",
        "arrangement": arrangement,
        "guided_setup": _guided_setup(
            arrangement,
            names,
            f"このとき、内側にできる四角形{names.inner if names else ''}は、"
            f"1辺の長さが {c} の正方形になる",
        ),
        "arrangement_reason": "面積を2通りに表せるように、直角三角形を組み合わせた図をつくる",
        "split_fact": f"{outer_ph}の各辺は、長さ {a} の部分と長さ {b} の部分に分かれる",
        "split_reason": "合同な直角三角形の直角をはさむ2辺が、それぞれ1辺の上に並ぶように置いたから",
        "inner_fact": f"{inner_ph}は、1辺の長さが {c} の正方形である",
        "inner_reason": (
            f"4つの辺はどれも斜辺だから長さは {c} で等しく、"
            "直角三角形の直角以外の2つの角の和は 90° だから内角も 90° になる"
        ),
        "figure_kind": "outer_square",
    }


def _build_outer_square_subtract(
    letters: tuple[str, str, str], names: FigureNames | None
) -> dict[str, Any]:
    a, b, c = letters
    sa, sb, sc = (sympy.Symbol(x) for x in letters)
    base = _build_outer_square(letters, names)
    outer_ph, inner_ph = _phrases(names, "outer")
    base.update(
        {
            "quantity": f"{inner_ph}の面積",
            "first": Side((Term(sc**2, _sq(c, atomic=True)),)),
            "first_reason": f"{inner_ph}は1辺の長さが {c} だから",
            "second": Side(
                (
                    Term((sa + sb) ** 2, _sq(f"{a} + {b}", atomic=False)),
                    Term(sympy.Integer(2) * sa * sb, f"(1/2){a}{b} × 4", sign=-1),
                )
            ),
            "second_reason": f"{inner_ph}は{outer_ph}から合同な直角三角形4つを除いた残りだから",
        }
    )
    return base


def _build_inner_square(
    letters: tuple[str, str, str], names: FigureNames | None
) -> dict[str, Any]:
    a, b, c = letters
    sa, sb, sc = (sympy.Symbol(x) for x in letters)
    outer_ph, inner_ph = _phrases(names, "inner")
    arrangement = (
        f"直角をはさむ2辺の長さが {a}、{b}（{a} < {b}）、斜辺の長さが {c} である"
        f"合同な直角三角形4つを、斜辺がそれぞれ1辺になるように並べて、"
        f"1辺の長さが {c} の{outer_ph}をつくる"
    )
    return {
        "quantity": f"{outer_ph}の面積",
        "first": Side((Term(sc**2, _sq(c, atomic=True)),)),
        "first_reason": f"{outer_ph}は1辺の長さが {c} だから",
        "second": Side(
            (
                _triangles_term(a, b, sa, sb, 4),
                Term((sb - sa) ** 2, _sq(f"{b} - {a}", atomic=False)),
            )
        ),
        "second_reason": f"{outer_ph}は合同な直角三角形4つと{inner_ph}に分けられるから",
        "arrangement": arrangement,
        "guided_setup": _guided_setup(
            arrangement,
            names,
            f"このとき、内側にできる四角形{names.inner if names else ''}は、"
            f"1辺の長さが {b} - {a} の正方形になる",
        ),
        "arrangement_reason": "面積を2通りに表せるように、斜辺を外側にして直角三角形を並べた図をつくる",
        "split_fact": f"{outer_ph}の各辺は、長さ {c} の斜辺そのものである",
        "split_reason": "合同な直角三角形を、斜辺がそれぞれ1辺の上にくるように置いたから",
        "inner_fact": f"{inner_ph}は、1辺の長さが {b} - {a} の正方形である",
        "inner_reason": (
            f"内側にできる四角形の1辺は、長さ {b} の辺から長さ {a} の辺を除いた残りで、"
            "4つの内角はどれも 90° になる"
        ),
        "figure_kind": "inner_square",
    }


def _build_inner_square_subtract(
    letters: tuple[str, str, str], names: FigureNames | None
) -> dict[str, Any]:
    a, b, c = letters
    sa, sb, sc = (sympy.Symbol(x) for x in letters)
    base = _build_inner_square(letters, names)
    outer_ph, inner_ph = _phrases(names, "inner")
    base.update(
        {
            "quantity": f"{inner_ph}の面積",
            "first": Side((Term((sb - sa) ** 2, _sq(f"{b} - {a}", atomic=False)),)),
            "first_reason": f"{inner_ph}は1辺の長さが {b} - {a} だから",
            "second": Side(
                (
                    Term(sc**2, _sq(c, atomic=True)),
                    Term(sympy.Integer(2) * sa * sb, f"(1/2){a}{b} × 4", sign=-1),
                )
            ),
            "second_reason": f"{inner_ph}は{outer_ph}から合同な直角三角形4つを除いた残りだから",
        }
    )
    return base


def _build_trapezoid(
    letters: tuple[str, str, str], names: FigureNames | None
) -> dict[str, Any]:
    """台形（Garfield の証明）。上底 a・下底 b・高さ a + b の台形を3つの三角形に分ける。"""
    a, b, c = letters
    sa, sb, sc = (sympy.Symbol(x) for x in letters)
    outer_ph, inner_ph = _phrases(names, "trapezoid")
    # **点をとる位置は「上底のある側から b」。** 上底の側の直角三角形は、上底を1辺
    # （長さ a）にするので、もう1辺が b でないと直角をはさむ2辺が a、b にならない。
    # ここを a にすると2辺が a、a の三角形になり、真ん中の三角形が直角二等辺でなくなる
    # （a=3, b=4 で FI=√18、IG=√32 と長さが合わない）。面積の恒等式は分け方の抽象しか
    # 見ないので、この取り違えは検証を素通りする。
    if names is None:
        spot = f"高さにあたる辺を、上底のある側から長さ {b}、{a} に分ける点をとる"
        vertices = "台形"
    else:
        o, e = names.outer, names.inner[0]
        spot = f"辺 {o[0]}{o[3]} 上に {o[0]}{e} = {b} となる点 {e} をとる"
        vertices = f"台形{o}"
    arrangement = (
        f"直角をはさむ2辺の長さが {a}、{b}、斜辺の長さが {c} である合同な直角三角形を"
        f"2つ並べて、上底が {a}、下底が {b}、高さが {a} + {b} の{vertices}をつくり、"
        f"{spot}"
    )
    return {
        "quantity": f"{outer_ph}の面積",
        "first": Side(
            (
                Term(
                    sympy.Rational(1, 2) * (sa + sb) * (sa + sb),
                    f"(1/2)({a} + {b})({a} + {b})",
                ),
            )
        ),
        "first_reason": f"{outer_ph}は上底が {a}、下底が {b}、高さが {a} + {b} の台形だから",
        "second": Side(
            (
                _triangles_term(a, b, sa, sb, 2),
                Term(sympy.Rational(1, 2) * sc**2, f"(1/2){c}²"),
            )
        ),
        "second_reason": f"{outer_ph}は合同な直角三角形2つと{inner_ph}に分けられるから",
        "arrangement": arrangement,
        "guided_setup": _guided_setup(
            arrangement,
            names,
            f"このとき、{inner_ph}は、等しい2辺の長さが {c} の直角二等辺三角形になる",
        ),
        "arrangement_reason": "面積を2通りに表せるように、直角三角形を2つ並べた台形をつくる",
        "split_fact": f"高さにあたる辺は、長さ {a} の部分と長さ {b} の部分に分かれる",
        "split_reason": f"合同な直角三角形の直角をはさむ2辺が {a}、{b} だから",
        "inner_fact": f"残りの三角形は、等しい2辺の長さが {c} の直角二等辺三角形である",
        "inner_reason": (
            "2つの斜辺の長さはどちらも等しく、"
            "直角三角形の直角以外の2つの角の和は 90° だから、その間の角は 90° になる"
        ),
        "figure_kind": "trapezoid",
    }


_AREA_BUILDERS: dict[str, AreaBuilder] = {
    "outer_square": _build_outer_square,
    "outer_square_subtract": _build_outer_square_subtract,
    "inner_square": _build_inner_square,
    "inner_square_subtract": _build_inner_square_subtract,
    "trapezoid": _build_trapezoid,
}

AREA_PROOF_IDS = tuple(_AREA_BUILDERS)

# a = b でも図が潰れない型（内側の正方形が (b-a)² の型は a < b が要る）。
_ALLOWS_EQUAL_LEGS = {"outer_square", "outer_square_subtract", "trapezoid"}


# ---------------------------------------------------------------------------
# 検証（恒等式 + 数値）
# ---------------------------------------------------------------------------
# 検算に使う実際の直角三角形（3辺の長さ）。図の比とは無関係に、**式が本当に
# 同じ面積を表しているか**を数で確かめるためだけに使う。
_CHECK_TRIPLES = ((3, 4, 5), (5, 12, 13), (8, 15, 17), (20, 21, 29))


def _verify_area_identity(proof: AreaProof) -> sympy.Rational | None:
    """2通りの面積の式の差が a² + b² - c² の定数倍かを確かめ、その定数を返す。

    ここが「その図で三平方の定理が示せる」の定義そのものである。定理の式を人が
    書いて突き合わせるのではなく、**面積の式の差を取ったら定理が出てきた**という
    順序にしてある（出てこない分け方は型として成立しない＝None を返す）。
    """
    sa, sb, sc = (sympy.Symbol(x) for x in proof.letters)
    diff = _side_value(proof.first) - _side_value(proof.second)
    target = sa**2 + sb**2 - sc**2
    quotient = sympy.simplify(sympy.together(diff / target))
    if not quotient.is_Rational or quotient == 0:
        return None
    if sympy.expand(diff - quotient * target) != 0:
        return None
    return quotient


def _numeric_check(proof: AreaProof) -> bool:
    """具体の直角三角形を代入して、2通りの面積が実際に等しいかを数で確かめる。

    恒等式の検査（sympy の式変形）とは独立な経路の検算。項の写し間違い
    （三角形4つのはずが2つ、など）はここで数として落ちる。
    """
    sa, sb, sc = (sympy.Symbol(x) for x in proof.letters)
    for a, b, c in _CHECK_TRIPLES:
        for legs in ((a, b), (b, a)):
            if legs[0] >= legs[1] and not proof.equal_legs_ok and legs[0] > legs[1]:
                # a < b を要する型では、大きい方を b に取った並びだけを見る。
                continue
            subs = {sa: legs[0], sb: legs[1], sc: c}
            lhs = _side_value(proof.first).subs(subs)
            rhs = _side_value(proof.second).subs(subs)
            if sympy.simplify(lhs - rhs) != 0:
                return False
    return True


def build_area_proof(
    proof_id: str,
    letters: tuple[str, str, str],
    names: FigureNames | None,
    *,
    flip: bool,
) -> AreaProof | None:
    """型＋パラメータから面積証明を組み立てる。検証に落ちたら None。"""
    raw = _AREA_BUILDERS[proof_id](letters, names)
    proof = AreaProof(
        proof_id=proof_id,
        letters=letters,
        names=names,
        flip=flip,
        equal_legs_ok=proof_id in _ALLOWS_EQUAL_LEGS,
        **raw,
    )
    if _verify_area_identity(proof) is None:
        return None
    if not _numeric_check(proof):
        return None
    if _reduce(proof) is None:
        return None
    return proof


# ---------------------------------------------------------------------------
# 展開 → 共通項の消去 → 両辺の倍率（式から導く）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Reduction:
    """「両辺から 2ab をひく」「両辺を2倍する」という最後のひと手の中身。"""

    common: sympy.Expr        # 両辺から消える共通の項（0 なら消去なし）
    factor: sympy.Rational    # 両辺に掛ける数（1 なら不要）
    left: sympy.Expr          # 整理後の左辺
    right: sympy.Expr         # 整理後の右辺


def _add_terms(expr: sympy.Expr) -> list[sympy.Expr]:
    return list(expr.args) if expr.is_Add else [expr]


def _reduce(proof: AreaProof) -> Reduction | None:
    """展開した両辺から、共通項と倍率を**式に聞いて**求める。

    「2ab をひく」と書いてから式を合わせるのではなく、展開した両辺に共通して
    現れる項を取り、残りが a² + b² と c² の同じ定数倍になることを確かめる。
    台形の型だけ倍率 2 が要る（両辺に 1/2 が掛かっている）が、それも
    ここで自動的に出てくる——型ごとに手で書き分ける必要がない。
    """
    sa, sb, sc = (sympy.Symbol(x) for x in proof.letters)
    left, right = _side_value(proof.first), _side_value(proof.second)
    remaining = _add_terms(right)
    common_terms: list[sympy.Expr] = []
    for t in _add_terms(left):
        if t in remaining:
            remaining.remove(t)
            common_terms.append(t)
    common = sympy.Add(*common_terms)
    lhs = sympy.expand(left - common)
    rhs = sympy.expand(right - common)

    goal_sum, goal_sq = sa**2 + sb**2, sc**2
    for factor in (sympy.Integer(1), sympy.Rational(1, 2), sympy.Integer(2)):
        scaled = (sympy.expand(factor * lhs), sympy.expand(factor * rhs))
        if scaled in ((goal_sum, goal_sq), (goal_sq, goal_sum)):
            return Reduction(common=common, factor=factor, left=scaled[0], right=scaled[1])
    return None


# ---------------------------------------------------------------------------
# 証明文の組み立て（面積証明）
# ---------------------------------------------------------------------------
# **Lv の差はここに出る。** 誘導あり（Lv3）は図と並べ方が問題文に与えられるので
# 面積を2通りに表すところから始まり、誘導なし（Lv4）は「どの図を使うか・どう分けるか」を
# 自分で立てる3行が先頭に付く。op 列が変わる＝ level_sep の材料になる。
_GUIDED_AREA_OPS = (
    "express_area_first",
    "express_area_second",
    "equate_areas",
    "expand_both_sides",
    "simplify_equation",
    "conclude_theorem",
)
_OPEN_AREA_OPS = ("choose_figure", "place_triangles", "justify_inner_square", *_GUIDED_AREA_OPS)

_AREA_NARRATION = {
    "choose_figure": "面積を2通りに表せる図を、自分で決めてかく。",
    "place_triangles": "並べた直角三角形から、図の辺の長さを読み取る。",
    "justify_inner_square": "内側にできる図形がどんな形かを確かめる。",
    "express_area_first": "着目した図形の面積を、その形の公式で表す。",
    "express_area_second": "同じ面積を、分けた部分の面積の和（差）で表し直す。",
    "equate_areas": "同じ面積を表す2つの式を等号で結ぶ。",
    "expand_both_sides": "両辺のかっこをはずして展開する。",
    "simplify_equation": "両辺に共通する項を消して式を整理する。",
    "conclude_theorem": "整理した式が三平方の定理そのものであることを述べる。",
}


def _reduction_reason(reduction: Reduction) -> str:
    """整理のひと手を日本語にする（何をひいたか・何倍したか）。"""
    parts: list[str] = []
    if reduction.common != 0:
        poly = sympy.Poly(reduction.common)
        if all(int(co) > 0 for co in poly.coeffs()):
            parts.append(f"両辺から {_disp(reduction.common)} をひく")
        else:
            parts.append(f"両辺に {_disp(-reduction.common)} を加える")
    if reduction.factor != 1:
        parts.append(f"両辺を {_disp(1 / reduction.factor)} でわる" if reduction.factor < 1
                     else f"両辺を {_disp(reduction.factor)} 倍する")
    if not parts:
        parts.append("式を整理する")
    return "、".join(parts)


def area_proof_lines(proof: AreaProof, guided: bool) -> list[ProofStep]:
    """面積による証明の行。**行の列がそのまま採点粒度と op 列になる。**"""
    reduction = _reduce(proof)
    assert reduction is not None, "検証を通った証明が整理できないのはあり得ない"
    a, b, c = proof.letters

    lines: list[ProofStep] = []
    if not guided:
        lines.append(
            ProofStep(claim=f"{proof.arrangement}。", reason=proof.arrangement_reason,
                      op="choose_figure")
        )
        lines.append(
            ProofStep(claim=f"{proof.split_fact}。", reason=proof.split_reason,
                      op="place_triangles")
        )
        lines.append(
            ProofStep(claim=f"{proof.inner_fact}。", reason=proof.inner_reason,
                      op="justify_inner_square")
        )
    lines.append(
        ProofStep(claim=f"{proof.quantity}は {proof.first.display()}",
                  reason=proof.first_reason, op="express_area_first")
    )
    lines.append(
        ProofStep(claim=f"{proof.quantity}は {proof.second.display()}",
                  reason=proof.second_reason, op="express_area_second")
    )
    lines.append(
        ProofStep(claim=f"{proof.first.display()} = {proof.second.display()}",
                  reason=f"どちらも{proof.quantity}を表しているから", op="equate_areas")
    )
    lines.append(
        ProofStep(
            claim=f"{proof.first.display(expanded=True)} = {proof.second.display(expanded=True)}",
            reason="両辺のかっこをはずして展開する",
            op="expand_both_sides",
        )
    )
    lines.append(
        ProofStep(claim=f"{_disp(reduction.left)} = {_disp(reduction.right)}",
                  reason=_reduction_reason(reduction), op="simplify_equation")
    )
    lines.append(
        ProofStep(
            claim=(
                f"したがって、直角三角形の直角をはさむ2辺の長さを {a}、{b}、"
                f"斜辺の長さを {c} とすると、{proof.conclusion_display} が成り立つ。"
            ),
            reason="",
            op="conclude_theorem",
        )
    )
    return lines


def render_proof_text(lines: list[ProofStep]) -> str:
    """行から証明文を組む（根拠を「〜から、」の形で前に置く）。"""
    out: list[str] = []
    for line in lines:
        if line.reason:
            out.append(f"{line.reason}、{line.claim}")
        else:
            out.append(line.claim)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 三平方の定理の逆（g3_l52）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConverseCase:
    """3辺の長さから直角であることを説明する1問。"""

    context: str
    names: str                 # 頂点の記号（例 "ABCD"）
    legs: tuple[int, int]      # 直角をはさむ2辺の長さ（提示順）
    hypotenuse: int
    unit: str
    premises: str
    conclusion: str
    leg_names: tuple[str, str]
    hyp_name: str
    right_vertex: str
    triangle: str


# 場面（どんな図の中で3辺が与えられるか）。3辺の数値そのものはピタゴラス数の
# 生成器が作るので、ここにあるのは**言い方**だけである。
_CONVERSE_CONTEXTS = ("triangle", "quadrilateral", "field")

# 頂点の記号。三角形の場面では先頭3文字だけ使う。
CONVERSE_NAME_SETS = ("ABCD", "PQRS", "KLMN", "DEFG", "EFGH", "STUV")

# ピタゴラス数の生成（原始三角形の (m, n) と倍数）。m > n、互いに素、偶奇が異なる。
_MN_PAIRS = ((2, 1), (3, 2), (4, 1), (4, 3), (5, 2), (5, 4), (6, 1), (6, 5), (7, 2), (7, 4), (7, 6))
_MAX_HYPOTENUSE = 90


def primitive_triples() -> list[tuple[int, int, int]]:
    """(m, n) から原始ピタゴラス数 (m²-n², 2mn, m²+n²) を作る（小さい脚を先に）。"""
    out: list[tuple[int, int, int]] = []
    for m, n in _MN_PAIRS:
        p, q, r = m * m - n * n, 2 * m * n, m * m + n * n
        legs = (min(p, q), max(p, q))
        out.append((legs[0], legs[1], r))
    return out


def scaled_triples() -> list[tuple[int, int, int]]:
    """原始ピタゴラス数とその倍数（斜辺が扱える大きさに収まるものだけ）。"""
    out: list[tuple[int, int, int]] = []
    for a, b, c in primitive_triples():
        k = 1
        while c * k <= _MAX_HYPOTENUSE:
            out.append((a * k, b * k, c * k))
            k += 1
    return out


TRIPLES = tuple(scaled_triples())


def build_converse_case(
    context: str, names: str, triple_index: int, swap: bool, name_index: int
) -> ConverseCase | None:
    """場面＋3辺から「直角であることの説明」1問を組む。検証に落ちたら None。"""
    a, b, c = TRIPLES[triple_index % len(TRIPLES)]
    legs = (b, a) if swap else (a, b)
    if legs[0] == legs[1]:  # pragma: no cover - ピタゴラス数に等しい脚は無い
        return None
    if a * a + b * b != c * c:  # pragma: no cover - 生成器が壊れたときだけ
        return None
    if math.isqrt(c * c) ** 2 != c * c:  # pragma: no cover - 同上
        return None

    p0, p1, p2, p3 = names
    unit = "m" if context == "field" else "cm"
    # 直角になるのは「2辺のあいだの頂点」。斜辺は残りの2点を結ぶ辺である。
    leg1, leg2 = f"{p0}{p1}", f"{p1}{p2}"
    hyp = f"{p0}{p2}"
    right_vertex = f"∠{p0}{p1}{p2}"
    triangle = f"△{p0}{p1}{p2}"

    if context == "triangle":
        premises = (
            f"{triangle} で、{leg1} = {legs[0]}{unit}、{leg2} = {legs[1]}{unit}、"
            f"{hyp} = {c}{unit} である"
        )
    elif context == "quadrilateral":
        premises = (
            f"四角形 {names} で、{leg1} = {legs[0]}{unit}、{leg2} = {legs[1]}{unit}、"
            f"対角線 {hyp} = {c}{unit} である"
        )
    else:
        premises = (
            f"運動場に3本のロープを張って、{leg1} = {legs[0]}{unit}、"
            f"{leg2} = {legs[1]}{unit}、{hyp} = {c}{unit} となる3点 {p0}、{p1}、{p2} をとった"
        )
    return ConverseCase(
        context=context,
        names=names,
        legs=legs,
        hypotenuse=c,
        unit=unit,
        premises=premises,
        conclusion=f"{right_vertex} が直角である",
        leg_names=(leg1, leg2),
        hyp_name=hyp,
        right_vertex=right_vertex,
        triangle=triangle,
    )


_CONVERSE_OPS = (
    "cite_side_lengths",
    "compute_squares_of_legs",
    "compute_square_of_hypotenuse",
    "compare_two_values",
    "conclude_right_angle",
)

_CONVERSE_NARRATION = {
    "cite_side_lengths": "与えられた3辺のうち、いちばん長い辺がどれかを確かめる。",
    "compute_squares_of_legs": "残り2辺それぞれの平方を求め、その和を計算する。",
    "compute_square_of_hypotenuse": "いちばん長い辺の平方を計算する。",
    "compare_two_values": "2つの計算の結果を見くらべ、等しいことを確かめる。",
    "conclude_right_angle": "三平方の定理の逆を使って、どの角が直角かを結論づける。",
}


def converse_proof_lines(case: ConverseCase) -> list[ProofStep]:
    """「三平方の定理の逆で直角を説明する」記述の行。"""
    (x, y), z = case.legs, case.hypotenuse
    n1, n2 = case.leg_names
    h = case.hyp_name
    unit = case.unit
    return [
        ProofStep(
            claim=f"3辺のうち、もっとも長い辺は {h}（{z}{unit}）である。",
            reason=f"{x}{unit}、{y}{unit}、{z}{unit} の大きさをくらべると",
            op="cite_side_lengths",
        ),
        ProofStep(
            claim=f"{n1}² + {n2}² = {x}² + {y}² = {x * x + y * y}",
            reason="残りの2辺の平方の和を求めると",
            op="compute_squares_of_legs",
        ),
        ProofStep(
            claim=f"{h}² = {z}² = {z * z}",
            reason="もっとも長い辺の平方を求めると",
            op="compute_square_of_hypotenuse",
        ),
        ProofStep(
            claim=f"{n1}² + {n2}² = {h}²",
            reason=f"どちらも {z * z} で等しいから",
            op="compare_two_values",
        ),
        ProofStep(
            claim=(
                f"三平方の定理の逆より、{case.triangle} は {h} を斜辺とする直角三角形である。"
                f"したがって、{case.conclusion}。"
            ),
            reason="",
            op="conclude_right_angle",
        ),
    ]


# ---------------------------------------------------------------------------
# solver（double-solve の再計算経路）
# ---------------------------------------------------------------------------
def _steps(lines: list[ProofStep], narration: dict[str, str]) -> list[Step]:
    return [
        Step(op=ln.op, args=[], result_srepr="", result_display=ln.claim,
             narration=narration[ln.op])
        for ln in lines
    ]


@register_solver("math.pythagoras_area_proof")
def pythagoras_area_proof(
    proof_id: object, letters: object, names: object, flip: object, guided: object
) -> Solution:
    """型＋パラメータだけから、面積による証明をもう一度組み立て直す。

    答えの文字列は params に入っていないので、checker はここを呼ぶだけで
    「同じ図で、同じ筋道に到達するか」を独立に確かめられる（G-Q1）。
    """
    letters_t = tuple(str(x) for x in (letters or ()))  # type: ignore[union-attr]
    if len(letters_t) != 3:
        raise ValueError(f"letters は3文字であること: {letters_t!r}")
    fig_names = None
    if names:
        pair = [str(x) for x in names]  # type: ignore[union-attr]
        fig_names = FigureNames(outer=pair[0], inner=pair[1])
    proof = build_area_proof(
        str(proof_id), (letters_t[0], letters_t[1], letters_t[2]), fig_names, flip=bool(flip)
    )
    if proof is None:
        raise ValueError(f"面積証明を組み直せなかった: {proof_id!r} {letters_t}")
    is_guided = bool(guided)
    lines = area_proof_lines(proof, is_guided)
    expected = _GUIDED_AREA_OPS if is_guided else _OPEN_AREA_OPS
    assert tuple(ln.op for ln in lines) == expected, "op 列が宣言と食い違った"
    return Solution(
        answer=ProofAnswer(text=render_proof_text(lines), lines=lines),
        steps=_steps(lines, _AREA_NARRATION),
    )


@register_solver("math.pythagoras_converse_proof")
def pythagoras_converse_proof(
    context: object, names: object, triple_index: object, swap: object
) -> Solution:
    """3辺の長さから「直角である」ことの説明をもう一度組み立て直す。"""
    case = build_converse_case(
        str(context), str(names), int(triple_index), bool(swap), 0  # type: ignore[arg-type]
    )
    if case is None:
        raise ValueError(f"逆の説明を組み直せなかった: {context!r} {names!r} {triple_index!r}")
    lines = converse_proof_lines(case)
    assert tuple(ln.op for ln in lines) == _CONVERSE_OPS, "op 列が宣言と食い違った"
    return Solution(
        answer=ProofAnswer(text=render_proof_text(lines), lines=lines),
        steps=_steps(lines, _CONVERSE_NARRATION),
    )


__all__ = [
    "AREA_PROOF_IDS",
    "AreaProof",
    "CONVERSE_NAME_SETS",
    "ConverseCase",
    "FigureNames",
    "TRIPLES",
    "area_proof_lines",
    "build_area_proof",
    "build_converse_case",
    "converse_proof_lines",
    "primitive_triples",
    "pythagoras_area_proof",
    "pythagoras_converse_proof",
    "render_proof_text",
    "scaled_triples",
]
