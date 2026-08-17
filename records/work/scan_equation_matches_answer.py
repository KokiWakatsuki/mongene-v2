"""解説に出てくる方程式を解いて、答えと合うかを確かめる。

## なぜ要るか

`g3_l31.word_problem.Lv3` の解説が「（8x = 288）」と出していた。面積は 8x² なので
本当は 8x² = 288 で、答えは 6秒後。**表示された式を解くと x = 36** で答えと合わない。
答えも図も正しく、狂っていたのは解説の式1本だけなので、7つのゲートは全部通っていた。

読めば見つかるが、1220問を毎回読むことはできない。**式は機械が解ける**ので、
解いて答えと突き合わせる。

## 何を見て、何を見ないか

見るのは「文字が1つだけの等式」で、答えが数のときだけ。
`140x + 140y = 1680`（文字2つ）や `y = 8x²`（定義の式）は見ない。
だから**取りこぼしはある**——挙がったものを人が読む道具であって、
0 件を合格の根拠にはしない。

## 使い方

    PYTHONPATH=engine_core .venv/bin/python records/work/scan_equation_matches_answer.py
"""
from __future__ import annotations

import argparse
import re
import sys

import sympy

from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, make_env

#: 「… = …」の形で、両側が数式に見えるもの。
_EQ = re.compile(r"^\s*([0-9a-zA-Z²³\s+\-*/().]+?)\s*=\s*([0-9a-zA-Z²³\s+\-*/().]+?)\s*$")
#: 答えから数を1つ取り出す（「6秒後」「x = 6」「6cm」）。
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def _to_sympy(text: str) -> sympy.Expr | None:
    """教材の書き方（`8x²`・`2x`）を sympy が読める形にする。"""
    t = text.replace("²", "**2").replace("³", "**3").replace(" ", "")
    # `8x` → `8*x`、`x(` → `x*(`、`)(` → `)*(`
    t = re.sub(r"(\d)([a-zA-Z(])", r"\1*\2", t)
    t = re.sub(r"([a-zA-Z)])(\()", r"\1*\2", t)
    try:
        return sympy.sympify(t)
    except (sympy.SympifyError, TypeError, SyntaxError, ValueError):
        return None


def _numbers(text: str) -> set[sympy.Rational]:
    """文字列に出てくる数をすべて拾う。

    ★**最初の1つだけ**を答えとみていたら、「2つの整数は 25 と 27」の
    先頭の「2」を答えだと思って3件の誤検出を出した。助数詞の数と答えの数は
    見分けられないので、**全部を候補に入れる**（見逃す側に倒す）。
    """
    out: set[sympy.Rational] = set()
    for tok in _NUM.findall(text or ""):
        try:
            out.add(sympy.Rational(tok))
        except (TypeError, ValueError):
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    env = make_env()
    checked = 0
    bad: dict[str, str] = {}

    for coord in capability_cells(env):
        assert isinstance(coord, Coordinate)
        for seed in range(1, args.seeds + 1):
            res = generate(
                GenerateRequest(
                    subject=coord.subject, unit=coord.unit, form=coord.form,
                    level=coord.level, seed=seed,
                ),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            for sq in res.sub_questions:
                answer_text = getattr(sq.answer, "display", "") or ""
                target = _numbers(answer_text)
                if not target:
                    continue
                # **答えそのものが式の小問は見ない**（「式をつくれ」＝立式が答え）。
                # ここを見ていて3件の誤検出を出した。
                if _EQ.match(answer_text):
                    continue
                steps = list(sq.solution_steps)
                for idx, st in enumerate(steps):
                    m = _EQ.match(st.result_display or "")
                    if m is None:
                        continue
                    lhs, rhs = _to_sympy(m.group(1)), _to_sympy(m.group(2))
                    if lhs is None or rhs is None:
                        continue
                    free = (lhs - rhs).free_symbols
                    if len(free) != 1:
                        continue
                    sym = next(iter(free))
                    # 「y = 8x²」のような定義の式（左辺が文字1つ）は解く対象でない。
                    if lhs.is_Symbol or rhs.is_Symbol:
                        continue
                    try:
                        roots = sympy.solve(sympy.Eq(lhs, rhs), sym)
                    except (NotImplementedError, TypeError, ValueError):
                        continue
                    # 無理数の解（`-6 + sqrt(38)`）は、答えの表示と数で比べられない。
                    if not roots or any(not r.is_Rational for r in roots):
                        continue
                    checked += 1
                    # **途中の式の解は、答えでなく後の手の値になる。**
                    # 「その解が、この先どこにも出てこない」ときだけ挙げる
                    # （最初の版は答えとだけ比べ、5件の誤検出を出した）。
                    downstream = set(target)
                    for later in steps[idx + 1:]:
                        downstream |= _numbers(later.result_display or "")
                        downstream |= _numbers(later.detail or "")
                    if not any(
                        r.is_number and any(sympy.simplify(r - d) == 0 for d in downstream)
                        for r in roots
                    ):
                        cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
                        bad.setdefault(
                            cell,
                            f"式「{st.result_display}」→ 解 {roots} / この先に出てこない"
                            f"（答え「{answer_text[:40]}」）",
                        )

    # **0 件を信じる前に、何本の式を解いたかを出す。**
    print(f"解いた式: {checked} 本")
    print(f"■ 解説の式を解くと答えにならない: {len(bad)} セル")
    for cell, why in sorted(bad.items()):
        print(f"    {cell}  {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
