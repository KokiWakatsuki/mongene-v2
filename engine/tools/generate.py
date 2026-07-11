"""1問生成の簡易 CLI（人が手元でエンジンを試すための入口）。

`engine.tools` は core/packs/curriculum を「読むだけ」の利用者（§5.5）。本ファイルは
`bootstrap()` してから `generate()` を1回呼び、結果を人間が読める形で表示する。
図つきセル（graph_table）は SVG をファイルに保存してパスを表示する。

使い方:
  python -m engine.tools.generate <unit> <form> <level> [--seed N]
  python -m engine.tools.generate g2_l25 find_value 2
  python -m engine.tools.generate g2_l25 graph_table 2 --svg-out fig.svg
  python -m engine.tools.generate g2_l25 find_value 2 --purpose remedial --cause lf.substitution_error
  python -m engine.tools.generate g2_l25 find_value 2 --json

seed 省略時はランダム採番し、再現用に必ず表示する（F-2）。
未対応座標は理由コード付きで拒否される（F-5）——それも試せる。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateOptions, GenerateRequest, Problem, Unsupported
from engine.core.pipeline import generate
from engine.core.rng import issue_seed


def _format_problem(problem: Problem, svg_out: Path | None) -> str:
    m = problem.meta
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(
        f"math.{m.resolved.unit}.{m.resolved.form}  Lv{m.resolved.level}  "
        f"(seed={m.seed}, purpose={m.purpose})"
    )
    if m.requested != m.resolved:
        lines.append(
            f"  ↳ remedial: 要求 {m.requested.unit}.{m.requested.form}.Lv{m.requested.level} "
            f"→ 戻り先 {m.resolved.unit}.{m.resolved.form}.Lv{m.resolved.level}"
        )
    lines.append(f"signature={m.signature}  problem_ref={problem.problem_ref}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("【問題】")
    lines.append(f"  {problem.problem_text}")
    lines.append("")

    for sq in problem.sub_questions:
        lines.append(f"{sq.label} {sq.prompt_text}")
        answer_display = getattr(sq.answer, "display", None) or getattr(sq.answer, "correct", "")
        lines.append(f"    答え: {answer_display}")
        if sq.explanation:
            lines.append(f"    解説: {sq.explanation}")
        if sq.hints:
            lines.append("    ヒント:")
            for i, h in enumerate(sq.hints, 1):
                lines.append(f"      {i}. {h}")
        if sq.concept_tags:
            lines.append(f"    概念: {', '.join(sq.concept_tags)}")
        lines.append("")

    if problem.visual_svg:
        if svg_out is None:
            svg_out = Path(f"problem_{m.resolved.unit}_{m.resolved.form}_seed{m.seed}.svg")
        svg_out.write_text(problem.visual_svg, encoding="utf-8")
        lines.append(f"【図】 SVG を保存しました → {svg_out}（ブラウザで開くと座標平面が見えます）")
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="engine.tools.generate", description="問題を1問生成して表示する（手元で試す用）"
    )
    parser.add_argument("unit", help="単元 ID（例: g2_l25）")
    parser.add_argument("form", help="形式（例: find_value / graph_table）")
    parser.add_argument("level", type=int, help="難易度レベル（例: 2）")
    parser.add_argument("--seed", type=int, default=None, help="省略時はランダム（表示される）")
    parser.add_argument("--purpose", default="base", choices=["base", "remedial"])
    parser.add_argument("--cause", default=None, help="remedial 時の誤答要因 ID")
    parser.add_argument("--svg-out", type=Path, default=None, help="図の保存先（graph_table 用）")
    parser.add_argument("--json", action="store_true", help="Problem/Unsupported を JSON で出力")
    args = parser.parse_args(argv)

    bootstrap()

    seed = args.seed if args.seed is not None else issue_seed()
    options = GenerateOptions(cause_id=args.cause) if args.cause else GenerateOptions()
    req = GenerateRequest(
        subject="math", unit=args.unit, form=args.form, level=args.level,
        purpose=args.purpose, seed=seed, options=options,
    )

    result = generate(req)

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0 if isinstance(result, Problem) else 2

    if isinstance(result, Unsupported):
        print(f"✗ 拒否（F-5 明示拒否）: code={result.code}")
        print(f"  detail: {result.detail}")
        print("  → 別種の問題は返しません（未対応座標は理由付きで拒否）。")
        return 2

    print(_format_problem(result, args.svg_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
