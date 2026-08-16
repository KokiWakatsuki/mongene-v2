"""eval のセル走査を複数プロセスに分ける（測るものは変えない）。

## なぜ要るか

eval 一式は 630 セルを 1 プロセスで回していて、`dup_rate` と `retry_stats`
（どちらも 100 seed）だけで実時間の大半を使っていた。8 コアの機械で 1 コアしか
使っていないので、待ち時間がそのまま作業の速度を決めてしまう。

## なぜセル単位で分けてよいか

`cell_dup_rate` / `cell_retry_stats` は **セル 1 つの中で閉じている**。
seed から MR を組み、その中で dup_key を数えるだけで、他のセルの結果も
グローバルな状態も見ない。したがってセルを配ってもゲートが測るものは変わらない
（同じ seed からは同じ MR が出る＝`derive_rng` は family/level/purpose/seed だけの関数）。

親から `EvalEnv` を渡さないのは、registry が関数を持っていて pickle できないため。
**各ワーカーが起動時に自分で `make_env()` する**（bootstrap は数秒・ワーカーごとに1回）。
"""
from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from typing import Any, TypeVar

from engine.eval._harness import EvalEnv, make_env

_T = TypeVar("_T")

# ワーカー1つが持つ環境（初期化子で1回だけ作る）。
_ENV: EvalEnv | None = None


def default_jobs() -> int:
    """既定の並列数。**コア数 -1**（1つは親と OS のために空ける）。"""
    return max(1, min(8, (os.cpu_count() or 2) - 1))


def _init_worker() -> None:
    global _ENV  # noqa: PLW0603
    _ENV = make_env()


def _run(payload: tuple[Callable[..., Any], tuple[Any, ...]]) -> Any:
    fn, args = payload
    assert _ENV is not None, "_init_worker が走っていない"
    return fn(_ENV, *args)


def pmap(
    fn: Callable[..., _T],
    arg_tuples: Sequence[tuple[Any, ...]],
    *,
    jobs: int | None = None,
) -> list[_T]:
    """`fn(env, *args)` を各ワーカーで実行し、**入力の順序どおり**に結果を返す。

    `fn` はモジュール直下の関数であること（pickle されるため）。
    `jobs<=1` なら親プロセスでそのまま回す（デバッグ・小さな走査用）。
    """
    n = jobs if jobs is not None else default_jobs()
    if n <= 1 or len(arg_tuples) <= 1:
        env = make_env()
        return [fn(env, *args) for args in arg_tuples]
    with ProcessPoolExecutor(max_workers=n, initializer=_init_worker) as pool:
        # chunksize は「セル1つの重さ」に対して十分小さく取る（重いセルが
        # 1つのワーカーに固まらないように）。
        return list(pool.map(_run, [(fn, args) for args in arg_tuples], chunksize=4))
