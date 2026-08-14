"""eval 一式の統合エントリ（実装設計 §8.3・§8.4・Task10）。

`python -m engine.eval` で coverage_scan / dup_rate / level_sep / retry_stats /
text_quality / answer_size / statement_size をまとめて実行し、単一の JSON レポートと終了コード（いずれか失敗で 1）を
返す。CI の nightly ジョブ（§8.4）はこれを1コマンドで叩ける。個別実行は各モジュールの
`python -m engine.eval.coverage_scan` 等を使う。

`text_quality` は 2026-08-10 に足した5つ目のゲート。前の4つはどれも**構造**しか見て
おらず、「その問題が教材としてありうるか」を測るものが無かった（`scratchpad/corpus/
EVALUATION.md` の「足りないゲート」）。記号の食い違い（D-10）と中身のないヒント
（D-17）は走査としては動いていたので、回帰の歯止めとしてゲートに上げた。

`answer_size` は 2026-08-13 に足した6つ目のゲート。`scratchpad/scan_big_numbers.py` は
「問題文と答えに出る最大の数」を並べるだけで**合否の基準を持っていなかった**（道具の説明
自身が「数が大きいこと自体は欠陥ではない」と書いている）。基準になるのは問題文の数ではなく
**答えの形**（分母・分子・根号の中）で、超えるセルは `dup_rate_max` と同じく family YAML に
理由つきで宣言する。初回の実測で 56 セルが上限超えだった（`√1202`・`225/2 cm³`・`185/2%`・
四分位数 `27/2`・`(1/12)³ = 1/1728` ほか）。

`statement_size` は 2026-08-13 に足した7つ目のゲート。`answer_size` が**答え**を測るのに対し、
こちらは**問題文**を単位ごとに測る。「1辺445cmの正三角形」「3辺が 220cm, 1200cm, 1220cm の
三角形」は、答えが正しく割り切れていても教材にならない（3mの正三角形は作図もできない）。
定義域は狭めず、`pipeline` が**出来上がった問題文を測って組み直す**。記録・母集団・測定値
のように大きいのが正しいセルは YAML に宣言する。初回の実測で 31 セルが上限超えだった。

使い方:
  python -m engine.eval [--seeds N] [--dup-seeds N] [--text-seeds N] [--size-seeds N]
                        [--json] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.eval._harness import make_env
from engine.eval.answer_size import _format_text as _fmt_size
from engine.eval.answer_size import run_answer_size
from engine.eval.coverage_scan import _format_text as _fmt_cov
from engine.eval.coverage_scan import run_coverage_scan
from engine.eval.dup_rate import _format_text as _fmt_dup
from engine.eval.dup_rate import run_dup_rate
from engine.eval.level_sep import _format_text as _fmt_lvl
from engine.eval.level_sep import run_level_sep
from engine.eval.retry_stats import _format_text as _fmt_retry
from engine.eval.retry_stats import run_retry_stats
from engine.eval.statement_size import _format_text as _fmt_stmt
from engine.eval.statement_size import run_statement_size
from engine.eval.text_quality import _format_text as _fmt_text
from engine.eval.text_quality import run_text_quality


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engine.eval", description="eval 一式（§8.3）を一括実行")
    parser.add_argument("--seeds", type=int, default=5, help="coverage_scan / level_sep の seed 数")
    parser.add_argument("--dup-seeds", type=int, default=100, help="dup_rate / retry_stats の seed 数")
    parser.add_argument("--text-seeds", type=int, default=5, help="text_quality の seed 数")
    parser.add_argument("--size-seeds", type=int, default=10, help="answer_size の seed 数")
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
    size = run_answer_size(env, seeds=args.size_seeds)
    stmt = run_statement_size(env, seeds=args.size_seeds)

    overall_ok = (
        coverage.ok and dup.ok and level.ok and retry.ok and text.ok and size.ok and stmt.ok
    )

    payload = {
        "ok": overall_ok,
        "coverage_scan": coverage.to_json(),
        "dup_rate": dup.to_json(),
        "level_sep": level.to_json(),
        "retry_stats": retry.to_json(),
        "text_quality": text.to_json(),
        "answer_size": size.to_json(),
        "statement_size": stmt.to_json(),
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
        print(_fmt_size(size))
        print()
        print(_fmt_stmt(stmt))
        print()
        print(f"=== eval 一式: {'OK' if overall_ok else 'FAIL'} ===")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
