"""G-BT（逆翻訳ゲート）の突き合わせ — 読み手の答えとエンジンの答えを比べる。

`bt_dump.py` が書き出した**問題文だけ**を読み手（別の LLM。ここでは Claude 自身）が
読み、日本語だけから答えを出して `records/work/bt/answers.tsv` に書く:

```
g1_l25.word_problem.Lv2#1<TAB>5
g2_l18.word_problem.Lv3#1<TAB>500, 100
```

この道具は同じ問題をエンジンで作り直し、**エンジンの答え**と突き合わせる。
食い違ったものだけを出す。

## なぜ答えを比べるので足りるのか

日本語が数式と食い違っていれば（「6cm短い」なのに `x(x+6)`）、日本語だけから解いた
答えとエンジンの答えは**必ずずれる**。逆に一致すれば、少なくともその seed について
日本語と数式は同じことを言っている。`recipe` も `checker` も見ずに解くので、
**同じ立式関数を再利用している既存の double-solve では塞げない穴**をここだけが塞ぐ。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/bt_check.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_DIR = Path("records/work/bt")
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def _values(text: str) -> set[float]:
    """比較用に数を**値**として取り出す（表記の違いを吸収する）。

    `0.3a` と `3a/10`、`1/20` と `0.05`、`1.5x` と `3/2x` は同じことを言っている。
    文字列で比べると全部「食い違い」になるので、値の集合で比べる。
    符号は語順で変わる（「12%の食塩水は500g」）ので絶対値で見る。
    """
    out: set[float] = set()
    # 分数に文字が挟まる形（`3a/10`・`12x/100`）は、文字を落とすと分数として読める。
    # 落とす前と後の両方から数を採る（`0.3a` と `3a/10` を同じ値にするため）。
    # `a/8` は 1/8。分母の直前の文字は係数 1 とみなす（`0.125a` と合わせるため）。
    unit_coeff = re.sub(r"(?<![\d.])[A-Za-z](?=/\d)", "1", text)
    for source in (text, re.sub(r"[A-Za-z]", "", text), unit_coeff):
        for token in _NUM.findall(source):
            try:
                if "/" in token:
                    num, _, den = token.partition("/")
                    out.add(abs(float(num) / float(den)))
                else:
                    out.add(abs(float(token)))
            except (ValueError, ZeroDivisionError):
                continue
    return out


def main() -> int:
    # id → (unit, form, level, seed)。`index.json`（7回目）と `patterns.json`（9回目・
    # 文型ごとの代表）の両方を混ぜる。読み手の答えも `answers*.tsv` を全部読む。
    rows: dict[str, dict] = {}
    # `scenes.json`（10回目・(関係×場面) の全組×5seed）も混ぜる。
    # id の付け方は同じ（`unit.form.Lv<n>#<seed>`）なので、前の回の答えは生きたまま。
    for name in ("index.json", "patterns.json", "scenes.json", "figures.json"):
        p = _DIR / name
        if p.exists():
            for r in json.loads(p.read_text(encoding="utf-8")):
                rows[str(r["id"])] = r
    # ★過去の回の答えは**そのときの engine の出力**に対するもの。engine を直したあとは
    # 同じ seed が別の問題になっているので、混ぜると「食い違い」が積み上がる
    # （実測 373問中100件がそれ）。回を指定して見られるようにする。
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    mine: dict[str, str] = {}
    for path in sorted(_DIR.glob(only or "answers*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            pid, _, ans = line.partition("\t")
            mine[pid.strip()] = ans.strip()

    env = make_env()
    checked = skipped = uncomparable = 0
    unindexed: list[str] = []
    mismatches: list[tuple[str, str, str]] = []
    for pid, ans in mine.items():
        if ans in ("", "-", "N/A"):
            skipped += 1
            continue
        r = rows.get(pid)
        if r is None:
            # 7回目に読んだぶんのうち、その時の index が残っていない id。
            # 読み直せば戻せるが、**黙って落とすと「全部見た」と読めてしまう**。
            unindexed.append(pid)
            continue
        # id は `unit.form.Lv<n>#<seed>`。index に unit/form/level が無い行
        # （patterns.json の古い版）でも、id から復元できる。
        cell = str(r.get("cell") or pid.split("#")[0])
        unit, form, lv = cell.rsplit(".", 2)
        level = int(lv.removeprefix("Lv"))
        res = generate(
            GenerateRequest(
                subject="math", unit=str(r.get("unit") or unit),
                form=str(r.get("form") or form),
                level=int(r.get("level") or level), seed=int(r["seed"]),
            ),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        engine_ans = " ／ ".join(
            str(getattr(sq.answer, "display", None) or getattr(sq.answer, "correct", ""))
            for sq in res.sub_questions
        )
        checked += 1
        # **読み手の値がエンジンの答えに1つも欠けていなければ通す。**
        # エンジン側は単位や見出し（「12%の食塩水は500g」）で数が増えるので、
        # 集合の一致では測れない。日本語が数式と食い違っていれば、読み手の値の
        # どれかが必ずエンジンの答えから外れる。
        engine_values = _values(engine_ans)
        if not engine_values:
            # 記号だけを答えさせるセル（「AとBのどちらか」）。エンジンは数を出さない
            # ので、読み手が途中で出した代表値は**突き合わせようがない**。
            # 「合った」と数えるのも「食い違い」と数えるのも嘘なので、別に数える。
            checked -= 1
            uncomparable += 1
            continue
        missing = {v for v in _values(ans) if not any(abs(v - w) < 1e-9 for w in engine_values)}
        if missing:
            mismatches.append((pid, f"{ans}  ← 合わない値 {sorted(missing)}", engine_ans))

    print(f"突き合わせ {checked} 問 / 読み手が保留 {skipped} 問 / "
          f"数で比べられない {uncomparable} 問 / 食い違い {len(mismatches)} 問")
    if unindexed:
        print(f"（index が残っていないため突き合わせできなかった過去分 {len(unindexed)} 問）")
    print()
    for pid, ans, engine_ans in mismatches:
        print(f"■ {pid}")
        print(f"    読み手: {ans}")
        print(f"    エンジン: {engine_ans}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
