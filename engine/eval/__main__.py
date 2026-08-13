"""eval 一式の統合エントリ（実装設計 §8.3・§8.4・Task10）。

`python -m engine.eval` で coverage_scan / dup_rate / level_sep / retry_stats /
text_quality をまとめて実行し、単一の JSON レポートと終了コード（いずれか失敗で 1）を
返す。CI の nightly ジョブ（§8.4）はこれを1コマンドで叩ける。個別実行は各モジュールの
`python -m engine.eval.coverage_scan` 等を使う。

`text_quality` は 2026-08-10 に足した5つ目のゲート。前の4つはどれも**構造**しか見て
おらず、「その問題が教材としてありうるか」を測るものが無かった（`scratchpad/corpus/
EVALUATION.md` の「足りないゲート」）。記号の食い違い（D-10）と中身のないヒント
（D-17）は走査としては動いていたので、回帰の歯止めとしてゲートに上げた。

使い方:
  python -m engine.eval [--seeds N] [--dup-seeds N] [--text-seeds N] [--json] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.eval._harness import make_env
from engine.eval.coverage_scan import _format_text as _fmt_cov
from engine.eval.coverage_scan import run_coverage_scan
from engine.eval.dup_rate import _format_text as _fmt_dup
from engine.eval.dup_rate import run_dup_rate
from engine.eval.level_sep import _format_text as _fmt_lvl
from engine.eval.level_sep import run_level_sep
from engine.eval.retry_stats import _format_text as _fmt_retry
from engine.eval.retry_stats import run_retry_stats
from engine.eval.text_quality import _format_text as _fmt_text
from engine.eval.text_quality import run_text_quality


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engine.eval", description="eval 一式（§8.3）を一括実行")
    parser.add_argument("--seeds", type=int, default=5, help="coverage_scan / level_sep の seed 数")
    parser.add_argument("--dup-seeds", type=int, default=100, help="dup_rate / retry_stats の seed 数")
    parser.add_argument("--text-seeds", type=int, default=5, help="text_quality の seed 数")
    parser.add_argument("--json", action="store_true", help="統合 JSON レポートを出力")
    parser.add_argument("--out", type=Path, default=None, help="統合 JSON レポートの保存先")
    args = parser.parse_args(argv)

    # bootstrap + curriculum/families を一度だけ読んで4プログラムで共有する。
    env = make_env()

    coverage = run_coverage_scan(env, seeds=args.seeds)
    dup = run_dup_rate(env, seeds=args.dup_seeds)
    level = run_level_sep(env, seeds=args.seeds)
    retry = run_retry_stats(env, seeds=args.dup_seeds)
    text = run_text_quality(env, seeds=args.text_seeds)

    overall_ok = coverage.ok and dup.ok and level.ok and retry.ok and text.ok

    payload = {
        "ok": overall_ok,
        "coverage_scan": coverage.to_json(),
        "dup_rate": dup.to_json(),
        "level_sep": level.to_json(),
        "retry_stats": retry.to_json(),
        "text_quality": text.to_json(),
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_fmt_cov(coverage))
        print()
        print(_fmt_dup(dup))
        print()
        print(_fmt_lvl(level))
        print()
        print(_fmt_retry(retry))
        print()
        print(_fmt_text(text))
        print()
        print(f"=== eval 一式: {'OK' if overall_ok else 'FAIL'} ===")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
