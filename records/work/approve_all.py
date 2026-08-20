"""golden を**1プロセスで**全部再承認する。

`for f in ...; do python -m engine.tools.spec_cli approve $f; done` は、
family ごとに `bootstrap()`（pack 登録・curriculum/families の読み込み）を
やり直すので、その固定費だけで 282 回ぶんかかる。ここは bootstrap を1回にして
`_run_approve` を回す。

**同じ family を2つのプロセスが同時に触らない**——ここは family を**重ならないように
配る**のでその条件を満たす（golden は family ごとのディレクトリに書かれ、
family どうしは干渉しない）。禁じているのは「approve_all をまるごと2本走らせる」ほう。

実行: .venv/bin/python records/work/approve_all.py [--jobs N]
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor

from engine.tools.spec_cli import _DEFAULT_GOLDEN_DIR, _run_approve
from engine_paths import GOLDEN_DIR  # エンジンの場所は1か所で解決する

_SKIP = {"__pycache__"}

# 既定の並列数（コア数 -1。1つは親と OS のために空ける）。
_DEFAULT_JOBS = max(1, min(8, (os.cpu_count() or 2) - 1))


def _approve_one(fam: str) -> tuple[str, int, str]:
    """family 1つを承認する（ワーカーで走る）。戻り値は (family, 終了コード, 例外文)。"""
    try:
        return fam, _run_approve(fam, _DEFAULT_GOLDEN_DIR, diff=False), ""
    except Exception as e:  # noqa: BLE001
        return fam, 1, f"{type(e).__name__}: {e}"


def _init_worker() -> None:
    """ワーカーごとに1回 bootstrap する（親の registry は pickle できない）。"""
    from engine.bootstrap import bootstrap

    bootstrap()


def main() -> int:
    jobs = _DEFAULT_JOBS
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
    families = sorted(
        d.name for d in GOLDEN_DIR.iterdir()
        if d.is_dir() and d.name not in _SKIP
    )
    fails: list[str] = []
    done = 0
    if jobs <= 1:
        results = [_approve_one(fam) for fam in families]
    else:
        with ProcessPoolExecutor(max_workers=jobs, initializer=_init_worker) as pool:
            results = []
            for fam, rc, err in pool.map(_approve_one, families, chunksize=4):
                results.append((fam, rc, err))
                done += 1
                if done % 40 == 0:
                    print(f"... {done}/{len(families)}", flush=True)
    for fam, rc, err in results:
        if err:
            print(f"APPROVE-FAIL {fam} {err}", flush=True)
        if rc != 0:
            fails.append(fam)
    print(f"=== approve done ({len(families)} family / 失敗 {len(fails)}) ===", flush=True)
    for f in fails:
        print("FAIL", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
