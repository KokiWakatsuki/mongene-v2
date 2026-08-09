"""仮定と結論の証明・反例による否定（form: proof・g2_l38）— 命題の生成器と筋道の組み立て。

**問題を手で書かない。** 命題は「型＋パラメータ」で持ち、
  - 真偽の判定は展開した式の係数に聞き（`holds_always`）、
  - 偽のときの反例は「仮定を満たす数」を小さい順に当たって見つける（`find_counterexample`）。
どちらもコードがやる。「n が偶数ならば n + 2 は偶数である」も「連続する2つの整数の和は
奇数である」も、文字列としてはこのファイルのどこにも書かれていない——
**数の類（modulus, residue）と演算のパラメータから組み上がる**。

## `number_proof`（g2_l7 / g2_l8 / g3_l13）との違い
あちらは「必ず正しい命題」を作り、**示すべき性質を式から導いて**（`derive_goal`）
説明を書かせる。こちらは g2_l38＝「仮定と結論、証明の進め方の基本（反例による否定を含む）」
なので仕事が逆になる:
  - 仮定と結論がはっきり分かれた形（P ならば Q）を作り、1段の筋道で結ぶ
  - **正しくない命題も作る**（Lv3 は真偽の判断が先に来て、偽なら反例1つで終わる）
だから中心にあるのは「性質を導く」ではなく「**与えた性質が成り立つか判定する**」である。

## 増やし方
`_TEMPLATES` に型を1つ足せば、その型の軸の直積だけ命題が増える。型が返すのは
「日本語の言い方」と「sympy の式」と「仮定を満たす具体の数の作り方」だけで、
真偽の判定・反例の探索・筋道の組み立て（`proof_lines`）は共有する。

## 退化の封じ方（質のフィルタ）
1. **どれか1つでも仮定が働いていない命題を捨てる。** 各型は「仮定を1つ外した式」を
   仮定の数だけ返し（`weakened_exprs`）、そのどれかが結論の性質を常に満たすなら退ける。
   これで
   「n が偶数ならば 2n は偶数である」（n が何であれ真＝仮定が働いていない）、
   「連続する2つの偶数の和は偶数である」（連続性を使っていない）、
   「m が10の倍数、p が9の倍数ならば mp は10の倍数である」（p の仮定が要らない）
   が自動で落ちる。`number_proof` が手で並べた除外表（`_CONSEC_VARIANTS`）を、
   判定に置き換えたもの。
2. **仮定と結論が同じ文になる組を捨てる**（n が3の倍数ならば n は3の倍数である）。
3. **結論の式が対象そのもの（a=1, c=0）のときは、真の命題のときだけ許す**
   （「n が6の倍数ならば n は3の倍数である」は良いが、偽の側は言いがかりになる）。

## 検証
`build_proposition` は
  1. 係数による真偽の判定（`holds_always`）
  2. **数値代入による独立の検算**（真なら仮定を満たす数を並べて実際に性質を確かめ、
     偽なら見つけた反例が本当に仮定を満たし結論を満たさないことを確かめる）
  3. 軸の正規化の往復（`_assert_round_trip`）
の3つを必ず通す。①だけだと判定の取り違えが素通りするので、②を独立に置く。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Callable

import sympy

from engine.core.contracts import ProofAnswer, ProofStep, Solution, Step
from engine.core.registry import register_solver

# 表示は number_proof と揃える（同じ form の教材表記を2通り持たないため）。
from engine.packs.math.solvers.number_proof import _disp, _lin_disp, _paren

# ---------------------------------------------------------------------------
# 数の類（「偶数」「3の倍数」＝ modulus で割った余りが residue の整数）
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NumberClass:
    """整数の類。日本語の言い方も、文字での表し方も、判定もここが持つ。

    「偶数」「奇数」「k の倍数」を別々のものとして扱うと、仮定にも結論にも同じ語彙を
    2度書くことになる。(modulus, residue) 1つにまとめると、仮定・結論・連続する数の
    基底を**同じ型**で書けて、真偽の判定も1本で済む。
    """

    modulus: int
    residue: int

    @property
    def phrase(self) -> str:
        if self.modulus == 1:
            return "整数"
        if self.modulus == 2:
            return "奇数" if self.residue else "偶数"
        return f"{self.modulus}の倍数"

    def represent(self, letter: str) -> tuple[sympy.Expr, str]:
        """この類の数を1つの文字で表した式と、その表示（例 偶数 -> (2m, "2m")）。"""
        return self.modulus * sympy.Symbol(letter) + self.residue, _lin_disp(
            self.modulus, letter, self.residue
        )

    def contains(self, value: int) -> bool:
        return value % self.modulus == self.residue % self.modulus


# 仮定に置ける類（「整数である」は仮定にならないので入れない）。
_HYP_CLASSES: tuple[NumberClass, ...] = (
    NumberClass(2, 0), NumberClass(2, 1),
    NumberClass(3, 0), NumberClass(4, 0), NumberClass(5, 0),
    NumberClass(6, 0), NumberClass(8, 0), NumberClass(9, 0), NumberClass(10, 0),
)
# 結論に置ける類。
_TARGET_CLASSES: tuple[NumberClass, ...] = (
    NumberClass(2, 0), NumberClass(2, 1),
    NumberClass(3, 0), NumberClass(4, 0), NumberClass(5, 0),
    NumberClass(6, 0), NumberClass(8, 0), NumberClass(9, 0),
    NumberClass(10, 0), NumberClass(12, 0),
)
# 「連続する〜」の基底になる類（こちらは「整数」を含む）。
_BASE_CLASSES: tuple[NumberClass, ...] = (
    NumberClass(1, 0), NumberClass(2, 0), NumberClass(2, 1),
    NumberClass(3, 0), NumberClass(4, 0), NumberClass(5, 0),
)


# ---------------------------------------------------------------------------
# 真偽の判定と、目標の形
# ---------------------------------------------------------------------------
def holds_always(expr: sympy.Expr, cls: NumberClass) -> bool:
    """`expr` が（文字にどんな整数を入れても）`cls` に属するか。

    展開した式の**係数**を見る。文字の付いた項の係数がすべて modulus で割り切れ、
    定数項の余りが residue に一致すれば、文字の値によらず余りは residue になる。
    """
    const = 0
    for monomial, coefficient in sympy.expand(expr).as_coefficients_dict().items():
        if not coefficient.is_Integer:
            return False
        c = int(coefficient)
        if monomial == sympy.S.One:
            const = c
        elif c % cls.modulus != 0:
            return False
    return const % cls.modulus == cls.residue % cls.modulus


def goal_form(expr: sympy.Expr, cls: NumberClass) -> tuple[str, sympy.Expr, str] | None:
    """`cls` に属することが読み取れる形（例 "2(m + 1)"）と、整数であることを言う相手。"""
    quotient = sympy.expand((expr - cls.residue) / cls.modulus)
    if sympy.expand(cls.modulus * quotient + cls.residue - expr) != 0:
        return None
    if not quotient.free_symbols:
        return None
    q_disp = _disp(quotient)
    if cls.residue == 0:
        form = f"{cls.modulus}({q_disp})" if quotient.is_Add else f"{cls.modulus} × {q_disp}"
    else:
        body = f"({q_disp})" if quotient.is_Add else q_disp
        form = f"{cls.modulus} × {body} + {cls.residue}"
    return form, quotient, q_disp


def _evaluator(expr: sympy.Expr, syms: tuple[sympy.Symbol, ...]) -> Callable[[tuple[int, ...]], int]:
    """整数値だけを速く求めるための評価器（sympy の subs を反例探索の内側で回さない）。"""
    terms = [
        (tuple(int(e) for e in monomial), int(coefficient))
        for monomial, coefficient in sympy.Poly(sympy.expand(expr), *syms).terms()
    ]

    def evaluate(values: tuple[int, ...]) -> int:
        total = 0
        for monomial, coefficient in terms:
            term = coefficient
            for value, exponent in zip(values, monomial, strict=True):
                if exponent:
                    term *= value**exponent
            total += term
        return total

    return evaluate


# 反例を探す範囲（文字に入れる値）。余りは modulus の周期でしか変わらないので、
# 最大の modulus（12）の2倍あれば「仮定を満たす正の数」の中に必ず全部の余りが出る。
_SEARCH_RANGE = 26


def find_counterexample(
    expr: sympy.Expr,
    target: NumberClass,
    subject_exprs: tuple[sympy.Expr, ...],
    aux_syms: tuple[sympy.Symbol, ...],
) -> tuple[tuple[int, ...], int] | None:
    """仮定を満たす**正の**数のうち、結論を満たさないものを小さい順に探す。

    「仮定を満たす」は構成で保証されている（subject は仮定の類の表し方そのもの）ので、
    ここで見るのは「結論を満たさないこと」と「具体の数として自然（正）であること」だけ。

    2つの数を使う命題では、**まず相異なる2数で探す**（`m = 1、w = 1` のような、同じ数を
    2度使う反例は正しいけれども「2数が違ってもよい」ことが伝わらない）。見つからなければ
    同じ数を許して探し直す——反例が1つも無いことにするより、弱い反例を出すほうがよい。
    """
    value_of = _evaluator(expr, aux_syms)
    subject_of = [_evaluator(e, aux_syms) for e in subject_exprs]
    grid = sorted(
        itertools.product(range(_SEARCH_RANGE), repeat=len(aux_syms)),
        key=lambda t: (sum(t), t),
    )
    for require_distinct in (True, False):
        for values in grid:
            subject_values = tuple(f(values) for f in subject_of)
            if any(v <= 0 for v in subject_values):
                continue
            if require_distinct and len(set(subject_values)) != len(subject_values):
                continue
            result = value_of(values)
            if not target.contains(result):
                return subject_values, result
    return None


# ---------------------------------------------------------------------------
# 命題（型が組み立てて返すもの）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Proposition:
    """1つの命題と、その筋道を書くのに要るものすべて。"""

    prop_id: str
    letters: tuple[str, ...]          # 実際に使った文字（params に載る＝ dup_key の材料）
    numbers: dict[str, int]           # 実際に使った軸の値（正規化済み・params に載る）
    aux_letters: tuple[str, ...]      # 「整数だから」と言う相手の文字
    statement: str                    # 命題そのもの（問題文に出る）
    representation: str               # 「n = 2m（m は整数）と表される」
    representation_reason: str        # 「仮定より、n は偶数だから」
    guided_premise: str               # 誘導（Lv2 の問題文に置く「〜とおいて」）
    combination_display: str          # 「n + 2」「n + (n + 1)」
    combination_reason: str           # 「仮定の式を代入して計算する」
    conclusion_noun: str              # 「n + 2」「その和」（反例の側で値を指す言い方）
    expanded_display: str             # 「2m + 2」
    target: NumberClass
    is_true: bool
    # 真のときだけ埋まる
    goal_display: str = ""
    quotient_display: str = ""
    quotient_is_symbol: bool = False
    # 偽のときだけ埋まる
    counter_assignment: str = ""      # 「n = 6」「m = 4、n = 3」「3、4」
    counter_combination: str = ""     # 「6 + 2」「4 × 3」「3 + 4」
    counter_value: int = 0
    instance_noun: str = ""           # 「連続する2つの整数」（名前の無い型のときだけ）

    @property
    def instance_claim(self) -> str:
        """反例に使う具体の数を、仮定を満たすものとして言う。"""
        if self.instance_noun:
            return f"{self.instance_noun}として {self.counter_assignment} をとる"
        return f"{self.counter_assignment} は仮定を満たす"


@dataclass(frozen=True)
class PropTemplate:
    prop_id: str
    n_subject: int                    # 命題文に名前で出る文字の数（連続〜型は 0）
    n_aux: int                        # 「整数」として置く文字の数
    axes: dict[str, tuple[int, ...]]
    build: Callable[[tuple[str, ...], dict[str, int]], dict[str, Any] | None] = field(repr=False)

    @property
    def n_letters(self) -> int:
        return self.n_subject + self.n_aux


# ---------------------------------------------------------------------------
# 具体の数の見せ方（反例の側）
# ---------------------------------------------------------------------------
def _num_lin_disp(coef: int, value: int, const: int) -> str:
    """具体の数を入れた1次式の表示（例 coef=2, value=5, const=-1 -> "2 × 5 - 1"）。

    文字のときの `_lin_disp` をそのまま使うと "25" になってしまうので、具体の数のときは
    必ず × を書く（最初の実装がこれを出していた）。
    """
    head = str(value) if coef == 1 else f"{coef} × {value}"
    if const == 0:
        return head
    return f"{head} + {const}" if const > 0 else f"{head} - {-const}"


def _named_assignment(labels: tuple[str, ...], values: tuple[int, ...]) -> str:
    return "、".join(f"{lab} = {val}" for lab, val in zip(labels, values, strict=True))


# ---------------------------------------------------------------------------
# 型①: 仮定が1つ（g2_l38 台帳 Lv2 example の型）
#   「n が偶数ならば、n + 2 は偶数である」
# ---------------------------------------------------------------------------
_COEF_CHOICES = (1, 2, 3, 4, 5, 6)
_CONST_CHOICES = tuple(range(-6, 13))  # -6..12


def _build_conditional_class(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    hyp_i = numbers["hyp"] % len(_HYP_CLASSES)
    coef_i = numbers["coef"] % len(_COEF_CHOICES)
    const_i = numbers["const"] % len(_CONST_CHOICES)
    target_i = numbers["target"] % len(_TARGET_CLASSES)
    hyp, target = _HYP_CLASSES[hyp_i], _TARGET_CLASSES[target_i]
    coef, const = _COEF_CHOICES[coef_i], _CONST_CHOICES[const_i]

    var, aux = letters[0], letters[1]
    rep_expr, rep_disp = hyp.represent(aux)
    combination = _lin_disp(coef, var, const)
    used = {"hyp": hyp_i, "coef": coef_i, "const": const_i, "target": target_i}
    return {
        "letters": (var, aux),
        "aux_letters": (aux,),
        "numbers": used,
        "statement": f"{var} が{hyp.phrase}ならば、{combination} は{target.phrase}である",
        "representation": f"{var} = {rep_disp}（{aux} は整数）と表される",
        "representation_reason": f"仮定より、{var} は{hyp.phrase}だから",
        "guided_premise": f"{var} = {rep_disp}（{aux} は整数）とおいて",
        "combination_display": combination,
        "combination_reason": "仮定の式を代入して計算する",
        "conclusion_noun": combination,
        "expr": coef * rep_expr + const,
        # 仮定を外した式（var が任意の整数のとき）。これが結論を常に満たすなら、
        # 仮定が働いていない＝命題として成立していないので退ける。
        "weakened_exprs": (coef * sympy.Symbol(var) + const,),
        "subject_exprs": (rep_expr,),
        "subject_labels": (var,),
        "instance_noun": "",
        "numeric_combination": lambda vals: _num_lin_disp(coef, vals[0], const),
        # 対象そのもの（a=1, c=0）は、真の命題のときだけ許す。
        "true_only": coef == 1 and const == 0,
        # 仮定と結論が同じ文になる組は捨てる。
        "degenerate": coef == 1 and const == 0 and hyp == target,
        "target": target,
    }


# ---------------------------------------------------------------------------
# 型②: 仮定が2つ（2つの数の和・差・積）
#   「m が偶数、n が奇数ならば、m + n は奇数である」
# ---------------------------------------------------------------------------
_PAIR_OPS = ("+", "-", "×")


def _build_pair_condition(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    h1_i = numbers["hyp1"] % len(_HYP_CLASSES)
    h2_i = numbers["hyp2"] % len(_HYP_CLASSES)
    op_i = numbers["op"] % len(_PAIR_OPS)
    target_i = numbers["target"] % len(_TARGET_CLASSES)
    h1, h2 = _HYP_CLASSES[h1_i], _HYP_CLASSES[h2_i]
    target = _TARGET_CLASSES[target_i]

    v1, v2, a1, a2 = letters[0], letters[1], letters[2], letters[3]
    e1, d1 = h1.represent(a1)
    e2, d2 = h2.represent(a2)
    s1, s2 = sympy.Symbol(v1), sympy.Symbol(v2)

    # weakened は「片方の仮定だけを外した式」。**2つとも要る命題**しか採らないための材料
    # （これが無いと「m が10の倍数、p が9の倍数ならば mp は10の倍数」のように、
    #  片方の仮定が飾りになっている命題が出る）。
    if op_i == 0:
        expr, combination = e1 + e2, f"{v1} + {v2}"
        weakened = (s1 + e2, e1 + s2)
        numeric = lambda vals: f"{vals[0]} + {vals[1]}"          # noqa: E731
    elif op_i == 1:
        expr, combination = e1 - e2, f"{v1} - {v2}"
        weakened = (s1 - e2, e1 - s2)
        numeric = lambda vals: f"{vals[0]} - {vals[1]}"          # noqa: E731
    else:
        expr, combination = e1 * e2, f"{v1}{v2}"
        weakened = (s1 * e2, e1 * s2)
        numeric = lambda vals: f"{vals[0]} × {vals[1]}"          # noqa: E731

    used = {"hyp1": h1_i, "hyp2": h2_i, "op": op_i, "target": target_i}
    return {
        "letters": (v1, v2, a1, a2),
        "aux_letters": (a1, a2),
        "numbers": used,
        "statement": (
            f"{v1} が{h1.phrase}、{v2} が{h2.phrase}ならば、"
            f"{combination} は{target.phrase}である"
        ),
        "representation": f"{v1} = {d1}、{v2} = {d2}（{a1}、{a2} は整数）と表される",
        "representation_reason": f"仮定より、{v1} は{h1.phrase}、{v2} は{h2.phrase}だから",
        "guided_premise": f"{v1} = {d1}、{v2} = {d2}（{a1}、{a2} は整数）とおいて",
        "combination_display": combination,
        "combination_reason": "仮定の2つの式を代入して計算する",
        "conclusion_noun": combination,
        "expr": expr,
        "weakened_exprs": weakened,
        "subject_exprs": (e1, e2),
        "subject_labels": (v1, v2),
        "instance_noun": "",
        "numeric_combination": numeric,
        "true_only": False,
        "degenerate": False,
        "target": target,
    }


# ---------------------------------------------------------------------------
# 型③: 連続する数の和（g2_l38 台帳 Lv3 example の型）
#   「連続する2つの整数の和は奇数である」
# ---------------------------------------------------------------------------
_COUNT_CHOICES = (2, 3, 4, 5)


def _build_consecutive_sum(
    letters: tuple[str, ...], numbers: dict[str, int]
) -> dict[str, Any] | None:
    base_i = numbers["base"] % len(_BASE_CLASSES)
    count_i = numbers["count"] % len(_COUNT_CHOICES)
    target_i = numbers["target"] % len(_TARGET_CLASSES)
    base, target = _BASE_CLASSES[base_i], _TARGET_CLASSES[target_i]
    count = _COUNT_CHOICES[count_i]

    var = letters[0]
    sym = sympy.Symbol(var)
    exprs = tuple(base.modulus * sym + base.residue + base.modulus * i for i in range(count))
    disps = tuple(
        _lin_disp(base.modulus, var, base.residue + base.modulus * i) for i in range(count)
    )
    noun = f"連続する{count}つの{base.phrase}"
    combination = " + ".join(_paren(d, e) for d, e in zip(disps, exprs, strict=True))

    # 仮定（＝連続していること）を外した式: 同じ類の数を count 個、独立にとった和。
    free_syms = sympy.symbols(f"_c0:{count}")
    weakened = (
        sum((base.modulus * s + base.residue for s in free_syms), sympy.Integer(0)),
    )

    used = {"base": base_i, "count": count_i, "target": target_i}
    return {
        "letters": (var,),
        "aux_letters": (var,),
        "numbers": used,
        "statement": f"{noun}の和は{target.phrase}である",
        "representation": f"{noun}は {'、'.join(disps)}（{var} は整数）と表される",
        "representation_reason": f"もっとも小さい数を {disps[0]} とおくと",
        "guided_premise": f"もっとも小さい数を {disps[0]}（{var} は整数）とおいて",
        "combination_display": combination,
        "combination_reason": "これらの数の和を計算する",
        "conclusion_noun": "その和",
        "expr": sum(exprs, sympy.Integer(0)),
        "weakened_exprs": weakened,
        "subject_exprs": exprs,
        "subject_labels": ("",) * count,
        "instance_noun": noun,
        "numeric_combination": lambda vals: " + ".join(str(v) for v in vals),
        "true_only": False,
        "degenerate": False,
        "target": target,
    }


# ---------------------------------------------------------------------------
# 型のカタログ
# ---------------------------------------------------------------------------
_TEMPLATES: dict[str, PropTemplate] = {
    t.prop_id: t
    for t in (
        PropTemplate(
            "conditional_class", 1, 1,
            {
                "hyp": tuple(range(len(_HYP_CLASSES))),
                "coef": tuple(range(len(_COEF_CHOICES))),
                "const": tuple(range(len(_CONST_CHOICES))),
                "target": tuple(range(len(_TARGET_CLASSES))),
            },
            _build_conditional_class,
        ),
        PropTemplate(
            "pair_condition", 2, 2,
            {
                "hyp1": tuple(range(len(_HYP_CLASSES))),
                "hyp2": tuple(range(len(_HYP_CLASSES))),
                "op": tuple(range(len(_PAIR_OPS))),
                "target": tuple(range(len(_TARGET_CLASSES))),
            },
            _build_pair_condition,
        ),
        PropTemplate(
            "consecutive_sum_claim", 0, 1,
            {
                "base": tuple(range(len(_BASE_CLASSES))),
                "count": tuple(range(len(_COUNT_CHOICES))),
                "target": tuple(range(len(_TARGET_CLASSES))),
            },
            _build_consecutive_sum,
        ),
    )
}

TEMPLATES = _TEMPLATES


# ---------------------------------------------------------------------------
# 命題の組み立て（＋3つの検証）
# ---------------------------------------------------------------------------
_CHECK_VALUES = (0, 1, 2, 3, 5, 7, 11, 14, 20)


def _numeric_check_true(
    expr: sympy.Expr, target: NumberClass, aux_syms: tuple[sympy.Symbol, ...]
) -> bool:
    """真だと判定した命題を、文字に整数を入れて**独立に**検算する。

    係数による判定（`holds_always`）と経路が違うので、判定の取り違えはここで落ちる。
    """
    value_of = _evaluator(expr, aux_syms)
    for i in range(len(_CHECK_VALUES)):
        values = tuple(
            _CHECK_VALUES[(i + j * 3) % len(_CHECK_VALUES)] for j in range(len(aux_syms))
        )
        if not target.contains(value_of(values)):
            return False
    return True


def _assert_round_trip(
    tpl: PropTemplate, letters: tuple[str, ...], raw: dict[str, Any]
) -> None:
    """正規化した軸の値を食わせ直しても**同じ命題**になることを確かめる。

    ここが崩れると、recipe が作った命題（問題文に出る）と checker が params から
    組み直した命題（模範解答に出る）が食い違う。**軸には値でなく番号を残す**という
    規律（number_proof で踏んだ罠）が守られているかの機械検査でもある。
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
    prop_id: str,
    letters: tuple[str, ...],
    numbers: dict[str, int],
    want_true: bool | None = None,
) -> Proposition | None:
    """型＋パラメータから命題を組み立てる。質・検証に落ちたら None。

    `want_true` は**生成側の都合**（Lv2 は正しい命題だけを使う）で、params には載らない。
    指定と真偽が食い違ったらそこで打ち切る——反例の探索は真偽が決まってからでよいので、
    要らない探索をしないための早期打ち切りでもある。
    """
    tpl = _TEMPLATES[prop_id]
    raw = tpl.build(tuple(letters), dict(numbers))
    if raw is None:
        return None
    target: NumberClass = raw["target"]
    if raw["degenerate"]:
        return None
    # 仮定を1つ外しても結論が成り立つなら、その仮定は飾りで、命題として成立していない。
    if any(holds_always(sympy.expand(w), target) for w in raw["weakened_exprs"]):
        return None

    expr = sympy.expand(raw["expr"])
    aux_letters = tuple(raw["aux_letters"])
    aux_syms = tuple(sympy.Symbol(x) for x in aux_letters)
    if not expr.free_symbols:
        return None

    is_true = holds_always(expr, target)
    if want_true is not None and is_true != want_true:
        return None
    if raw["true_only"] and not is_true:
        return None
    _assert_round_trip(tpl, tuple(letters), raw)

    common: dict[str, Any] = {
        "prop_id": prop_id,
        "letters": tuple(raw["letters"]),
        "numbers": dict(raw["numbers"]),
        "aux_letters": aux_letters,
        "statement": raw["statement"],
        "representation": raw["representation"],
        "representation_reason": raw["representation_reason"],
        "guided_premise": raw["guided_premise"],
        "combination_display": raw["combination_display"],
        "combination_reason": raw["combination_reason"],
        "conclusion_noun": raw["conclusion_noun"],
        "expanded_display": _disp(expr),
        "target": target,
        "is_true": is_true,
    }

    if is_true:
        formed = goal_form(expr, target)
        if formed is None:
            return None
        display, quotient, q_disp = formed
        if not _numeric_check_true(expr, target, aux_syms):
            return None
        return Proposition(
            **common,
            goal_display=display,
            quotient_display=q_disp,
            quotient_is_symbol=bool(quotient.is_Symbol),
        )

    found = find_counterexample(expr, target, tuple(raw["subject_exprs"]), aux_syms)
    if found is None:
        return None
    subject_values, value = found
    # 見つけた反例を、判定とは別経路で確かめる（結論を満たしていないこと）。
    if target.contains(value):
        raise ValueError(f"{prop_id}: 反例が結論を満たしてしまっている: {subject_values}")
    labels = tuple(raw["subject_labels"])
    assignment = (
        "、".join(str(v) for v in subject_values)
        if raw["instance_noun"]
        else _named_assignment(labels, subject_values)
    )
    return Proposition(
        **common,
        counter_assignment=assignment,
        counter_combination=raw["numeric_combination"](subject_values),
        counter_value=value,
        instance_noun=raw["instance_noun"],
    )


# ---------------------------------------------------------------------------
# 筋道の組み立て
# ---------------------------------------------------------------------------
# **Lv の差はここに出る。** Lv2（誘導あり）は文字のおき方を問題文が与えるので
# 「仮定を式で書く → 結論の式を作る → 目標の形にする → 結論づける」の4手。
# Lv3（誘導なし）は**真偽の判断が先頭に付いて**5手になり、しかも真の枝と偽の枝で
# **同じ op 列**を通る（op 列が枝で変わると同一 signature の fp が揺れて G-FP が落ちる）。
_PROVE_OPS = (
    "state_hypothesis",
    "form_conclusion_expression",
    "rewrite_to_goal_form",
    "conclude_property",
)
_JUDGE_OPS = (
    "judge_truth",
    "set_representation",
    "form_conclusion_expression",
    "test_conclusion",
    "conclude_judgement",
)

_NARRATION_PROVE = {
    "state_hypothesis": "仮定が述べている性質を、問題が指示した文字のおき方で式に書き直す。",
    "form_conclusion_expression": "結論が述べている数を、いま書いた式を使って表し、整理する。",
    "rewrite_to_goal_form": "示したい性質が読み取れる形に、式を書き直す。",
    "conclude_property": "文字が整数であることを確かめ、結論が成り立つと述べて証明を閉じる。",
}
_NARRATION_JUDGE_TRUE = {
    "judge_truth": "仮定を満たす数をいくつか試して、命題が正しいかどうかの見当をつける。",
    "set_representation": "正しいと判断したので、仮定を満たす数を文字を使って一般的に表す。",
    "form_conclusion_expression": "結論が述べている数を、いま書いた式を使って表し、整理する。",
    "test_conclusion": "示したい性質が読み取れる形に書き直して、結論が成り立つことを確かめる。",
    "conclude_judgement": "文字が整数であることを確かめ、命題は正しいと結論づける。",
}
_NARRATION_JUDGE_FALSE = {
    "judge_truth": "仮定を満たす数をいくつか試して、命題が正しいかどうかの見当をつける。",
    "set_representation": "正しくないと判断したので、仮定を満たす数を1つ選ぶ。",
    "form_conclusion_expression": "選んだ数について、結論が述べている数の値を実際に計算する。",
    "test_conclusion": "その値が、結論の述べている性質を満たしていないことを確かめる。",
    "conclude_judgement": "反例が1つあれば命題は正しくないと言えるので、それを述べて閉じる。",
}


def _conclusion_sentence(prop: Proposition, closing: str) -> str:
    lead = f"{'、'.join(prop.aux_letters)} は整数だから"
    if not prop.quotient_is_symbol:
        lead = f"{lead}、{prop.quotient_display} も整数であり"
    return f"{lead}、{prop.goal_display} は{prop.target.phrase}である。{closing}"


def _refutation_sentence(prop: Proposition) -> str:
    return f"よって、{prop.counter_assignment} は反例である。したがって、この命題は正しくない。"


def _chain_display(prop: Proposition) -> str:
    """式変形の連鎖。**同じ式を2度書かない**（整理済みの式がそのまま目標の形のとき）。"""
    segments = [prop.combination_display, prop.expanded_display, prop.goal_display]
    out: list[str] = []
    for s in segments:
        if not out or out[-1] != s:
            out.append(s)
    return " = ".join(out)


def proof_lines(prop: Proposition, mode: str) -> list[ProofStep]:
    """証明（または反例）の行。**行の列がそのまま採点粒度と op 列になる。**"""
    if mode == "prove":
        if not prop.is_true:
            raise ValueError(f"{prop.prop_id}: 誘導つきの証明に、正しくない命題は使えない")
        return [
            ProofStep(
                claim=f"{prop.representation}。",
                reason=prop.representation_reason,
                op="state_hypothesis",
            ),
            ProofStep(
                claim=f"{prop.combination_display} = {prop.expanded_display}",
                reason=prop.combination_reason,
                op="form_conclusion_expression",
            ),
            ProofStep(
                claim=f"= {prop.goal_display}",
                reason=f"{prop.target.phrase}の形に表す",
                op="rewrite_to_goal_form",
            ),
            ProofStep(
                claim=_conclusion_sentence(prop, f"したがって、{prop.statement}。"),
                reason="",
                op="conclude_property",
            ),
        ]

    if prop.is_true:
        body = [
            ProofStep(
                claim=f"{prop.representation}。",
                reason=prop.representation_reason,
                op="set_representation",
            ),
            ProofStep(
                claim=f"{prop.combination_display} = {prop.expanded_display}",
                reason=prop.combination_reason,
                op="form_conclusion_expression",
            ),
            ProofStep(
                claim=f"= {prop.goal_display}",
                reason=f"{prop.target.phrase}の形に表す",
                op="test_conclusion",
            ),
            ProofStep(
                claim=_conclusion_sentence(prop, "したがって、この命題は正しい。"),
                reason="",
                op="conclude_judgement",
            ),
        ]
        head = ProofStep(claim="この命題は正しい。", reason="仮定から結論が導けるかを調べる", op="judge_truth")
        return [head, *body]

    body = [
        ProofStep(
            claim=f"{prop.instance_claim}。",
            reason="仮定を満たす数を1つとる",
            op="set_representation",
        ),
        ProofStep(
            claim=f"{prop.counter_combination} = {prop.counter_value}",
            # 式のあとには空白を置く（「3r + 7 の値」）。「その和」のような言葉のときは
            # 置かない（「その和 の値」になる）。
            reason=(
                f"{prop.conclusion_noun}の値を求める"
                if prop.instance_noun
                else f"{prop.conclusion_noun} の値を求める"
            ),
            op="form_conclusion_expression",
        ),
        ProofStep(
            claim=f"{prop.counter_value} は{prop.target.phrase}ではない",
            reason="結論が成り立つかどうかを確かめる",
            op="test_conclusion",
        ),
        ProofStep(claim=_refutation_sentence(prop), reason="", op="conclude_judgement"),
    ]
    head = ProofStep(
        claim="この命題は正しくない。",
        reason="仮定を満たすのに結論が成り立たない例がないかを調べる",
        op="judge_truth",
    )
    return [head, *body]


def render_proof_text(prop: Proposition, mode: str) -> str:
    """行から答案の文を組む。誘導ありは問題文の書き出しに続く形になる。"""
    parts: list[str] = []
    if mode == "judge":
        parts.append("この命題は正しい。" if prop.is_true else "この命題は正しくない。")
    if prop.is_true:
        reason = prop.representation_reason
        parts.append(f"{reason}、{prop.representation}。" if reason else f"{prop.representation}。")
        parts.append(_chain_display(prop))
        closing = (
            "したがって、この命題は正しい。"
            if mode == "judge"
            else f"したがって、{prop.statement}。"
        )
        parts.append(_conclusion_sentence(prop, closing))
    else:
        parts.append(
            f"{prop.instance_claim}。{prop.counter_combination} = {prop.counter_value} で、"
            f"{prop.counter_value} は{prop.target.phrase}ではない。"
        )
        parts.append(_refutation_sentence(prop))
    return "\n".join(parts)


def guided_premises(prop: Proposition) -> str:
    """誘導あり（Lv2）で問題文に置く「〜とおいて」。"""
    return prop.guided_premise


# ---------------------------------------------------------------------------
# solver（double-solve の再計算経路）
# ---------------------------------------------------------------------------
@register_solver("math.conditional_statement_proof")
def conditional_statement_proof(
    prop_id: object, letters: object, numbers: object, mode: object
) -> Solution:
    """型＋パラメータだけから、証明（または反例）をもう一度組み立て直す。

    答えの文字列も真偽も params に入っていないので、checker はここを呼ぶだけで
    「同じ判断に、同じ筋道で到達するか」を独立に確かめられる（G-Q1）。
    """
    letters_t = tuple(str(x) for x in (letters or ()))  # type: ignore[union-attr]
    numbers_d = {str(k): int(v) for k, v in dict(numbers or {}).items()}  # type: ignore[arg-type]
    mode_s = str(mode)
    if mode_s not in ("prove", "judge"):
        raise ValueError(f"未知の mode: {mode_s!r}（prove / judge のいずれか）")
    prop = build_proposition(str(prop_id), letters_t, numbers_d)
    if prop is None:
        raise ValueError(f"命題を組み直せなかった: {prop_id!r} {letters_t} {numbers_d}")

    lines = proof_lines(prop, mode_s)
    expected_ops = _PROVE_OPS if mode_s == "prove" else _JUDGE_OPS
    assert tuple(ln.op for ln in lines) == expected_ops, "op 列が宣言と食い違った"

    if mode_s == "prove":
        narration = _NARRATION_PROVE
    else:
        narration = _NARRATION_JUDGE_TRUE if prop.is_true else _NARRATION_JUDGE_FALSE

    answer = ProofAnswer(text=render_proof_text(prop, mode_s), lines=lines)
    steps = [
        Step(
            op=ln.op,
            args=[],
            result_srepr="",
            result_display=ln.claim,
            narration=narration[ln.op],
        )
        for ln in lines
    ]
    return Solution(answer=answer, steps=steps)


__all__ = [
    "NumberClass",
    "PropTemplate",
    "Proposition",
    "TEMPLATES",
    "build_proposition",
    "conditional_statement_proof",
    "find_counterexample",
    "goal_form",
    "guided_premises",
    "holds_always",
    "proof_lines",
    "render_proof_text",
]
