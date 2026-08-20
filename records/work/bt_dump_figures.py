"""G-BT（逆翻訳・**図つき**）の入力を作る — 問題文と図だけを書き出す。

## なぜ要るか（word_problem だけでは届かない）

`bt_dump_scenes.py` は word_problem を対象にしている。理由は、G-BT が塞ぐ穴
（「日本語の場面文が本当にその数式を意味しているか」）が**日本語を式に翻訳する段**に
しか無いからで、そこは正しい。

しかし **`find_value` と `graph_table` には「日本語と図が食い違う」欠陥がありえる**。
既存の `check_figure_matches_givens.py` は構成の facts（等長・等角・直角）を座標で
突き合わせるが、それは**図の中に書かれた事実**だけを見る。問題文が言っている条件が
図に描かれていない・図の値と本文の値が違う、という食い違いは誰も見ていない。

過去の回で図つきセルを「問題文だけ」で読ませたら、読み手が図を見ずに答えて
食い違いが積み上がった（実測 100件の大半）。**あれは engine の欠陥ではなく、
読み手に材料が渡っていなかっただけ**である。だから図を一緒に渡す。

## 渡すもの・渡さないもの

渡す: 問題文・問い・**図（PNG）**
渡さない: 答え・解説・params・recipe のコード

## 対象の form

`find_value` と `graph_table`（答えが値・点なので機械で突き合わせられる）。
`proof` は答えが証明文、`construction` は答えが作図なので、値の比較が成り立たない
——そこは別の検査（`check_figure_matches_givens` と目視）に任せる。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/bt_dump_figures.py [--per 1] [--limit N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

sys.path.insert(0, "records/work")

_OUT = Path("records/work/bt")
_FIGS = _OUT / "figs"
_FORMS = ("find_value", "graph_table")


def main(argv: list[str]) -> int:
    bootstrap()
    from build_corpus import load_cells  # noqa: PLC0415

    try:
        import cairosvg  # noqa: PLC0415
    except ImportError:
        print("cairosvg が無いので図を PNG に焼けない（読み手は図を見られない）")
        return 1

    per = int(argv[argv.index("--per") + 1]) if "--per" in argv else 1
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 0
    env = make_env()
    _FIGS.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    lines: list[str] = [
        "# 逆翻訳の入力（問題文と図だけ）",
        "",
        "各問について、**この日本語と図だけを読んで**答えを出す。",
        "図は `（図）` の後のパスを開いて見る（画像として読める）。",
        "答えは値だけを書く（単位は書かない）。読み取れないものは `?` と書く。",
        "",
    ]
    n_nofig = 0
    for unit, form, level, _c, _e, _f in load_cells():
        if form not in _FORMS:
            continue
        for seed in range(1, per + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            if not res.visual_svg:
                n_nofig += 1
                continue        # 図が無いセルは word_problem 側の検査で足りる
            pid = f"{unit}.{form}.Lv{level}#{seed}"
            png = _FIGS / f"{unit}_{form}_Lv{level}_{seed}.png"
            cairosvg.svg2png(bytestring=res.visual_svg.encode("utf-8"),
                             write_to=str(png), output_width=560)
            rows.append({"id": pid, "unit": unit, "form": form,
                         "level": level, "seed": seed})
            asks = " / ".join(
                t for t in (sq.prompt_text or "" for sq in res.sub_questions) if t.strip()
            )
            lines.append(f"## {pid}")
            lines.append("")
            lines.append(res.problem_text.strip())
            if asks.strip():
                lines.append(f"（問い） {asks.strip()}")
            lines.append(f"（図） {png.resolve()}")
            lines.append("")
            if limit and len(rows) >= limit:
                break
        if limit and len(rows) >= limit:
            break

    (_OUT / "figures.md").write_text("\n".join(lines), encoding="utf-8")
    (_OUT / "figures.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(rows)} 問（図つき）→ records/work/bt/figures.md")
    print(f"図が無くて外したセル: {n_nofig}")
    if not rows:
        print("=== 1問も出ていない＝検査が動いていない ===")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
