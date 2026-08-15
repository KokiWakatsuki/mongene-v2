"""MR ダンプを機械ルールで triage し題材ズレ候補をフラグする（LLMフリー・全体評価）。

`docs/HANDOFF_2026-07-06.md` §17.4 Phase A step2 の実装。`reports/mr_dump/mr_corpus.jsonl`
（`dump_mr_corpus.py` の出力）を決定論ルールでふるいにかけ、Opus が深く見るべきセルを絞る。
**LLM 予算ゼロ**。判定は保守的（高精度）に倒し、疑わしきはフラグして個別評価へ回す。

フラグ規則（rule id）:
  GEN_ERROR    生成失敗（clean solution 枯渇等）。
  ARITH_FOREIGN 非「数と式」ドメインなのに operation が generic arithmetic のみ
                （BasicCalculationStructure フォールバックの臭い＝反比例calcバグと同型）。
  KNOWLEDGE_LEAK form が knowledge 以外なのに operation が knowledge_check のみ。
  DEGENERATE_ANS 非 knowledge/proof form なのに answer が全て None/空。
  FLAT_LEVELS   同一 (lesson,form) の全 lv で operation_names と atom 型が完全一致
                （難易度が構造を変えていない可能性＝WEAK 候補）。

出力: `reports/mr_dump/scan_flags.jsonl`（1行1フラグ）＋ 標準出力にサマリ。
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
IN_PATH = REPO_ROOT / "reports" / "mr_dump" / "mr_corpus.jsonl"
OUT_PATH = REPO_ROOT / "reports" / "mr_dump" / "scan_flags.jsonl"

ARITH_PREFIX = "arithmetic"


def _ops(r: dict[str, Any]) -> list[str]:
    return r.get("operation_names", []) or []


def _atom_types(r: dict[str, Any]) -> tuple[str, ...]:
    atoms = r.get("sampled_atoms") or {}
    return tuple(sorted((a or {}).get("type") or "?" for a in atoms.values()))


def _is_all_arith(ops: list[str]) -> bool:
    return bool(ops) and all(o.startswith(ARITH_PREFIX) for o in ops)


def scan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []

    def flag(r: dict[str, Any], rule: str, detail: str) -> None:
        flags.append(
            {
                "rule": rule,
                "lesson": r["lesson"],
                "form": r["form"],
                "lv": r["lv"],
                "domain": r.get("domain"),
                "title": r.get("title"),
                "blueprint_id": r.get("blueprint_id"),
                "operation_names": _ops(r),
                "detail": detail,
            }
        )

    # 行単位ルール
    for r in rows:
        if r.get("error"):
            flag(r, "GEN_ERROR", r["error"].split("\n")[0][:200])
            continue
        ops = _ops(r)
        # ARITH_FOREIGN: 非「数と式」で generic arithmetic のみ
        if r.get("domain") != "数と式" and _is_all_arith(ops):
            flag(r, "ARITH_FOREIGN", f"domain={r.get('domain')} ops={ops} atoms={_atom_types(r)}")
        # KNOWLEDGE_LEAK
        if r["form"] != "knowledge" and ops and all(o == "knowledge_check" for o in ops):
            flag(r, "KNOWLEDGE_LEAK", f"form={r['form']} だが operation は knowledge_check のみ")
        # DEGENERATE_ANS
        if r["form"] not in ("knowledge", "proof"):
            answers = r.get("answers") or []
            if answers and all(a in (None, "None", "", []) for a in answers):
                flag(r, "DEGENERATE_ANS", f"answers={answers}")

    # (lesson,form) 単位ルール: FLAT_LEVELS
    by_lf: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if not r.get("error"):
            by_lf[(r["lesson"], r["form"])].append(r)
    for (lesson, form), group in by_lf.items():
        if len(group) < 2:
            continue
        sigs = {(tuple(_ops(r)), _atom_types(r)) for r in group}
        if len(sigs) == 1:
            rep = group[0]
            flag(
                rep,
                "FLAT_LEVELS",
                f"{len(group)}レベル全てで ops+atom型が同一 sig={tuple(_ops(rep))}/{_atom_types(rep)}",
            )

    return flags


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", default=str(IN_PATH))
    parser.add_argument("--out", default=str(OUT_PATH))
    args = parser.parse_args()

    rows = [json.loads(l) for l in Path(args.in_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    flags = scan(rows)

    Path(args.out).write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in flags) + "\n", encoding="utf-8"
    )

    by_rule = Counter(f["rule"] for f in flags)
    print(f"総行数: {len(rows)} / フラグ: {len(flags)}")
    print("=== ルール別 ===")
    for rule, n in by_rule.most_common():
        print(f"  {rule:16} {n}")
    # ARITH_FOREIGN の内訳（最重要）
    af = [f for f in flags if f["rule"] == "ARITH_FOREIGN"]
    if af:
        print("\n=== ARITH_FOREIGN 対象レッスン(form) ===")
        seen = set()
        for f in af:
            k = (f["lesson"], f["form"])
            if k in seen:
                continue
            seen.add(k)
            print(f"  {f['lesson']:8} {f['form']:12} {f['domain']}/{f['title']}")
    print(f"\n出力: {Path(args.out).relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
