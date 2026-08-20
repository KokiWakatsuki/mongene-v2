"""問題文が**いくつ聞いているか**と、答えの数が合っているかを見る。

逆翻訳（G-BT）で見つかった欠陥の一つが「問題文は2つ聞いているのに答えは1つ」だった
（円錐の『中心角を求め、表面積を求めよ』が表面積しか答えていない）。
これは既存のどのゲートも見ていない——答えは正しく、日本語も自然で、
**問いと答えの数だけが合っていない**。

数え方は1つ:
  問題文の中の「求めよ／求めなさい／答えよ／表せ／かけ」を数え、
  小問（sub_questions）の数と比べる。
番号つき小問（`(1)` `(2)`）がある問題は、その数を小問数とみなす。

**この道具は欠陥を出すのではなく、読む先を絞る。** 小問が1つでも、答えが
「内角の和 540°、1つの内角 108°」のように**両方を含んでいれば正しい**。
含んでいるかどうかは日本語を読まないと分からないので、ここで出たものを
逆翻訳（`bt_patterns.py` → `bt_check.py`）にかけて確かめる。
2026-08-14 の走査では 21 セルが出て、実物の欠陥は逆翻訳が見つけた2件だけだった。

実行: .venv/bin/python records/work/scan_asks_vs_answers.py [--seeds N]
"""
from __future__ import annotations

import re
import sys
from collections import Counter

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, make_env

# 「〜を求め、〜を求めよ」の前半のように、**途中の手**として書かれた依頼も拾ってしまう。
# 連用形（求め／答え）と終止形（求めよ／求めなさい）を分けて数える。
# 文の終わりに来る依頼だけを数える。`かけ` を裸で数えると「追いかけた」に当たる。
_ASK_FINAL = re.compile(
    r"(求めよ|求めなさい|答えよ|答えなさい|表せ|表しなさい|かけ|かきなさい|選べ|示せ)(?=[。\n]|$)")
_ASK_MID = re.compile(r"(を求め、|を答え、|を求めたうえで|を数え、)")
_NUMBERED = re.compile(r"\((\d)\)")


def main() -> int:
    seeds = 2
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    tally: Counter[str] = Counter()
    found: list[str] = []
    for coord in capability_cells(env):
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception:  # noqa: BLE001
                continue
            if isinstance(res, Unsupported):
                continue
            text = res.problem_text
            n_sub = len(res.sub_questions)
            numbered = {int(m) for m in _NUMBERED.findall(text)}
            asks = len(numbered) if numbered else len(_ASK_FINAL.findall(text))
            mids = len(_ASK_MID.findall(text))
            cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
            if not numbered and asks + mids > n_sub:
                tally[cell] += 1
                if tally[cell] == 1:
                    found.append(f"{cell} seed{seed}: 問い {asks}+途中の依頼 {mids} / 小問 {n_sub}\n"
                                 f"    {text.strip()[:150]}")
    print(f"問いの数と小問の数が合わないセル {len(tally)} 種")
    for line in found:
        print("■ " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
