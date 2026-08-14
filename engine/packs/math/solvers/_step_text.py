"""解説の途中の手に入れる**式そのもの**を組むための共有ヘルパ（面③）。

解説の括弧（`Step.result_display`）には「その手で得たもの」を入れる。以前は
「和の符号を先に決める」のような**指示の言い直し**が入っていて、読んでも新しい
ことが1つも増えなかった。値を入れるには、途中の式を solver 側で組み直す必要がある
——solver は問題パラメータ（与式の文字列）しか受け取らないため。

**`narration` に数字を書かない規約はそのまま。** ヒントは narration しか見ない
（`engine/core/render/t1_template.py` の `_build_hints`）ので、括弧に値を書いても
答えの先出しにはならない。

ここには「どの solver でも要る」ものだけを置く（式の順序を保った分解と、
符号のついた並べ方）。mode ごとの中身は各 solver が持つ。
"""
from __future__ import annotations

import re

import sympy

_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def top_level_parts(s: str, ops: str) -> list[tuple[str, str]]:
    """深さ0の演算子で式の文字列を分ける。戻り値は (直前の演算子, 項)。

    **書かれた順序を保つ**ために sympy でなく文字列で分ける（sympy の
    `Add.args` は書かれた順とは限らないので、`(x+5)² - (x+8)(x-6)` の解説が
    入れかわって出る）。`**` は演算子として分けない（`(6)**2` は1つの因数）。
    """
    parts: list[tuple[str, str]] = []
    depth = 0
    cur = ""
    op = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch in ops and cur and not (
            ch == "*" and (s[i + 1 : i + 2] == "*" or s[i - 1 : i] == "*")
        ):
            parts.append((op, cur))
            op, cur = ch, ""
            i += 1
            continue
        cur += ch
        i += 1
    parts.append((op, cur))
    return parts


def wrapped_in_parens(s: str) -> bool:
    """式全体が1組のかっこで囲まれているか（`(a)*(b)` は False）。"""
    if not (s.startswith("(") and s.endswith(")")):
        return False
    depth = 0
    for i, ch in enumerate(s):
        depth += (ch == "(") - (ch == ")")
        if depth == 0:
            return i == len(s) - 1
    return False


def flatten_factors(s: str) -> list[tuple[str, str]]:
    """積・商を**かっこの入れ子を越えて**因数の列にする。

    `((-12x²y)/((-3/2)x))*(6xy)` → `[("", "-12x²y"), ("/", "(-3/2)x"), ("*", "6xy")]`。
    「÷ を逆数のかけ算に直す」手のように、**元の式に出てくる因数を1つずつ**
    見せたいときに使う（`top_level_parts` だけだと商がひとかたまりで残る）。
    """
    out: list[tuple[str, str]] = []
    for op, t in top_level_parts(s, "*/"):
        inner = t.strip()
        # **かっこの中まで割るのは、その中に ÷ があるときだけ。** そうしないと
        # 単項式 `(-12)*x**2*y` まで因数に割れて「(-12) × (x²) × (y)」になる。
        if wrapped_in_parens(inner):
            body = inner[1:-1]
            if any(o == "/" for o, _ in top_level_parts(body, "*/")):
                sub = flatten_factors(body)
                out.append((op, sub[0][1]))
                out.extend(sub[1:])
                continue
        out.append((op, t))
    return out


def fmt_expr(expr: sympy.Expr) -> str:
    """式の教材表記（`*` を落とし、冪を上付きに）。`2*(x - 12)` -> `2(x - 12)`。"""
    s = str(sympy.sstr(expr))
    s = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_SUPERSCRIPT), s)
    return s.replace("*", "")


def join_signed(terms: list[sympy.Expr]) -> str:
    """項を書かれた順に並べる（`y² - 6y + 4y - 24`）。

    `sympy.Add` にして表示すると**同類項が勝手にまとまってしまう**ので、
    「まとめる前」を見せるこの手では、項の列のまま並べる。
    """
    out = ""
    for i, t in enumerate(terms):
        s = fmt_expr(t)
        if i == 0:
            out = s
        elif s.startswith("-"):
            out += f" - {s[1:]}"
        else:
            out += f" + {s}"
    return out


__all__ = [
    "top_level_parts",
    "flatten_factors",
    "wrapped_in_parens",
    "fmt_expr",
    "join_signed",
]
