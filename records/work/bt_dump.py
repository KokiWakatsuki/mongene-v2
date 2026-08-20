"""G-BT（逆翻訳ゲート）の入力を作る — **問題文だけ**を書き出す。

## なぜ要るか（`docs/llm_template_expansion.md` §2）

文章題の double-solve checker は `recipe が使ったのと同じ FORMULATION_BUILDERS` を
呼び直している。検証しているのは **数値 → 立式 → 解** の連鎖であって、
**日本語の場面文が本当にその数式を意味しているか**ではない。だから次はゲートを全部通る:

```
「横が縦より6cm短い長方形の面積は55cm²。縦を x cm とするとき、縦の長さを求めよ」
    式 x(x + 6) = 55   ← 本当は x(x − 6) = 55
    答え 5cm           ← 本当は 11cm
```

数式と解は完全に整合し、数値も本文に出ているので、どのゲートも落とせない。

## この道具の役割

**逆翻訳する読み手に、答えも式も見せない。** ここでは問題文（と問い）だけを
`records/work/bt/problems.md` に書き出す。読み手は `records/work/bt/answers.tsv` に
`セル<TAB>seed<TAB>立てた式` を書く。`bt_check.py` がエンジンの式と突き合わせる。

**読み手が recipe を読んでしまうと独立でなくなる。** 書き出すのは日本語だけ。

実行:
  .venv/bin/python records/work/bt_dump.py [--seeds N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, make_env

_OUT_DIR = Path("records/work/bt")


def main() -> int:
    seeds = 2
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    lines: list[str] = [
        "# 逆翻訳の入力（問題文だけ）",
        "",
        "各問について、**この日本語だけを読んで**方程式（または連立方程式）を立て、",
        "`answers.tsv` に `id<TAB>式` の形で書く。答えは求めなくてよい。",
        "文字の置き方は問題文の指示に従う（指示が無ければ x）。",
        "",
    ]

    for coord in capability_cells(env):
        # 文章題（立式が要るもの）だけを対象にする。
        if coord.form not in ("word_problem",):
            continue
        for seed in range(1, seeds + 1):
            res = generate(
                cell_request(coord, seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
            pid = f"{cell}#{seed}"
            asks = " / ".join(sq.prompt_text or "" for sq in res.sub_questions)
            rows.append({
                "id": pid, "unit": coord.unit, "form": coord.form,
                "level": coord.level, "seed": seed,
            })
            lines.append(f"## {pid}")
            lines.append("")
            lines.append(res.problem_text.strip())
            if asks.strip():
                lines.append(f"（問い） {asks.strip()}")
            lines.append("")

    (_OUT_DIR / "problems.md").write_text("\n".join(lines), encoding="utf-8")
    (_OUT_DIR / "index.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(rows)} 問を records/work/bt/problems.md に書き出した（{seeds} seed/セル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
