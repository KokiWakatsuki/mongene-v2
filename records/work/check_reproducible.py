"""同じ seed から同じ問題が出るかを、**ハッシュ種を変えて**確かめる。

## なぜハッシュ種を変えるか

Python の `hash()` は起動ごとに変わる（`PYTHONHASHSEED` が random のとき）。
集合や辞書を**並べ替えずに**使っている場所があると、同じ seed でも実行ごとに
別の問題が出る。golden は1つのハッシュ種でしか回らないので、これは golden を
通り抜ける——実際に proof の15セルが実行ごとに変わっていたのを、この測り方で見つけた。

## 何を突き合わせるか

全セル × seed 1..N の「問題文・問い・答え・図」を1本のハッシュに畳んで、
ハッシュ種を変えた3つの実行で比べる。合わないセルは名前で列挙する
（合計のハッシュだけだと、どこが違うのか分からない）。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/check_reproducible.py          # 3種で比べる
  PYTHONPATH=engine_core .venv/bin/python records/work/check_reproducible.py --dump    # 1回ぶんを出す
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

_SEEDS = 3
_HASH_SEEDS = ("0", "1", "12345")


def dump() -> None:
    """セルごとの digest を1行1件で出す（この process のハッシュ種で）。"""
    sys.path.insert(0, "records/work")
    from build_corpus import load_cells  # noqa: PLC0415

    from engine.core.contracts import Coordinate, GenerateRequest, Unsupported  # noqa: PLC0415
    from engine.core.pipeline import generate  # noqa: PLC0415
    from engine.eval._harness import make_env  # noqa: PLC0415

    env = make_env()
    for unit, form, level, _c, _e, _f in load_cells():
        parts: list[str] = []
        for seed in range(1, _SEEDS + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form, level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                parts.append(f"unsupported:{res.code}")
                continue
            parts.append(json.dumps(
                [res.problem_text,
                 [s.prompt_text for s in res.sub_questions],
                 [getattr(s.answer, "display", "") or getattr(s.answer, "text", "")
                  for s in res.sub_questions],
                 res.visual_svg or ""],
                ensure_ascii=False, default=str,
            ))
        digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:16]
        print(f"{unit}.{form}.Lv{level}\t{digest}")
        _ = Coordinate  # 参照だけ（型の import を無駄にしない）


def main() -> int:
    if "--dump" in sys.argv:
        dump()
        return 0
    runs: list[dict[str, str]] = []
    for hs in _HASH_SEEDS:
        env = {**os.environ, "PYTHONHASHSEED": hs, "PYTHONPATH": "engine_core"}
        print(f"--- PYTHONHASHSEED={hs} で走らせる ---", flush=True)
        out = subprocess.run(  # noqa: S603
            [".venv/bin/python", str(Path(__file__)), "--dump"],
            capture_output=True, text=True, env=env, check=False,
        )
        if out.returncode:
            print(out.stderr[-2000:])
            return 1
        rows = dict(
            line.split("\t") for line in out.stdout.splitlines() if "\t" in line
        )
        print(f"    セル {len(rows)}")
        runs.append(rows)

    base = runs[0]
    bad: list[str] = []
    for cell, digest in base.items():
        for i, other in enumerate(runs[1:], start=1):
            if other.get(cell) != digest:
                bad.append(f"{cell}: 種{_HASH_SEEDS[0]}={digest} / "
                           f"種{_HASH_SEEDS[i]}={other.get(cell)}")
                break
    print(f"\n比べたセル {len(base)} / ハッシュ種 {len(_HASH_SEEDS)} 通り × seed 1..{_SEEDS}")
    if bad:
        print(f"=== 実行ごとに変わるセル {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== どの種でも同じ（再現性 OK）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
