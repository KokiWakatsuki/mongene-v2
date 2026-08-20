#!/usr/bin/env python3
"""G-WK（世界知識ゲート）の突き合わせ — 読み手の判定を機械が採点する。

`wk_dump.py` が書き出した問題群を読み手（LLM）が読み、`records/work/wk/verdicts.tsv` に

    wk-001<TAB>ok
    wk-002<TAB>該当<TAB>語の対<TAB>美術館なのに「入園料」（館なら入館料）

と書く。ここはそれを読み、**3つを順に見る**。

  1. **形式** — 全問そろっているか。知らない項目名を使っていないか
  2. **対照** — 混ぜた「過去に実際に出た悪い例」を捕まえられているか
  3. **実物** — 実際の問題に該当があったか

★**2 が落ちたら 3 は読まない。** 対照を見落とす読み手の「該当なし」は、
問題が無いのか見ていないのかを区別できない。合成データで落ちる側を持たない走査を
信用しないのと同じ理由で、ここで打ち切る。

実行:
  PYTHONPATH=records/work .venv/bin/python records/work/wk_check.py
  PYTHONPATH=records/work .venv/bin/python records/work/wk_check.py --self-test
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

_OUT = Path("records/work/wk")
_CATALOG = Path("records/work/failure_catalog.yaml")


def score(
    key: list[dict], verdicts: dict[str, tuple[str, str, str]], kinds: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """(形式の誤り, 見落とした対照, 実物の該当) を返す。"""
    form_errors: list[str] = []
    missed: list[str] = []
    hits: list[str] = []

    ids = {it["id"] for it in key}
    for missing in sorted(ids - set(verdicts)):
        form_errors.append(f"{missing}: 判定が書かれていない")
    for extra in sorted(set(verdicts) - ids):
        form_errors.append(f"{extra}: 出していない問の判定がある")

    for it in key:
        v = verdicts.get(it["id"])
        if v is None:
            continue
        verdict, kind, note = v
        if verdict not in ("ok", "該当"):
            form_errors.append(f"{it['id']}: 判定が 'ok' でも '該当' でもない: {verdict!r}")
            continue
        if verdict == "該当":
            if kind not in kinds:
                form_errors.append(
                    f"{it['id']}: 項目名が判定の項目に無い: {kind!r}（項目={sorted(kinds)}）"
                )
            if not note.strip():
                form_errors.append(f"{it['id']}: 該当と書いたのに、どこがなぜ悪いかが空")

        if it["kind"] == "対照":
            if verdict != "該当":
                missed.append(f"{it['id']}（{it['source']}）: {it['text'][:34]}…")
        elif verdict == "該当":
            hits.append(f"{it['source']}: [{kind}] {note}")

    return form_errors, missed, hits


def _read_verdicts(path: Path) -> dict[str, tuple[str, str, str]]:
    out: dict[str, tuple[str, str, str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        cols = line.rstrip("\n").split("\t")
        pid = cols[0].strip()
        verdict = cols[1].strip() if len(cols) > 1 else ""
        kind = cols[2].strip() if len(cols) > 2 else ""
        note = cols[3].strip() if len(cols) > 3 else ""
        out[pid] = (verdict, kind, note)
    return out


def self_test() -> int:
    """★落ちる側（対照の見落とし・形式の誤り）と通る側の両方を持つ。"""
    key = [
        {"id": "wk-001", "kind": "対照", "source": "fee_name_matches_place",
         "text": "美術館の入園料は、大人1人900円…"},
        {"id": "wk-002", "kind": "実物", "source": "g1_l25.word_problem.Lv2#3",
         "text": "1個90円のみかん…"},
    ]
    kinds = {"語の対", "実在する値の集合"}
    cases = [
        ("対照を捕まえ、実物は ok",
         {"wk-001": ("該当", "語の対", "館なら入館料"), "wk-002": ("ok", "", "")},
         (0, 0, 0)),
        ("★対照を見落とした",
         {"wk-001": ("ok", "", ""), "wk-002": ("ok", "", "")},
         (0, 1, 0)),
        ("実物に該当があった",
         {"wk-001": ("該当", "語の対", "館なら入館料"),
          "wk-002": ("該当", "実在する値の集合", "その額面は無い")},
         (0, 0, 1)),
        ("判定が1問足りない",
         {"wk-001": ("該当", "語の対", "館なら入館料")},
         (1, 0, 0)),
        ("知らない項目名",
         {"wk-001": ("該当", "なんとなく変", "館なら入館料"), "wk-002": ("ok", "", "")},
         (1, 0, 0)),
        ("該当と書いたのに理由が空",
         {"wk-001": ("該当", "語の対", ""), "wk-002": ("ok", "", "")},
         (1, 0, 0)),
    ]
    fails = 0
    for name, verdicts, want in cases:
        got = tuple(len(x) for x in score(key, verdicts, kinds))
        ok = got == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: (形式, 見落とし, 該当)={got}"
              + ("" if ok else f" ← 期待 {want}"))
    return fails


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return 1 if self_test() else 0

    key_path = _OUT / "key.json"
    v_path = (Path(argv[argv.index("--verdicts") + 1]) if "--verdicts" in argv
              else _OUT / "verdicts.tsv")
    if not key_path.exists():
        print(f"先に wk_dump.py を回すこと（{key_path} が無い）")
        return 1
    if not v_path.exists():
        print(f"読み手の判定が無い（{v_path}）")
        return 1

    key = json.loads(key_path.read_text())
    catalog = yaml.safe_load(_CATALOG.read_text())
    kinds = {str(e["種類"]) for e in catalog}
    verdicts = _read_verdicts(v_path)

    form_errors, missed, hits = score(key, verdicts, kinds)
    controls = sum(1 for it in key if it["kind"] == "対照")
    print(f"問 {len(key)}（対照 {controls}）／判定 {len(verdicts)}")

    if form_errors:
        print(f"=== 判定の形式に誤り {len(form_errors)} 件 ===")
        for e in form_errors[:20]:
            print(f"  {e}")
        return 1

    print(f"対照 {controls} 件中 {controls - len(missed)} 件を捕まえた")
    if missed:
        print("=== ★対照を見落とした＝この回の判定は採用しない ===")
        for m in missed:
            print(f"  {m}")
        return 1

    if hits:
        print(f"=== 実物の該当 {len(hits)} 件 ===")
        for h in hits:
            print(f"  {h}")
        return 1
    print("=== 実物に該当なし（対照は全部捕まえている＝読み手は見ている）===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
