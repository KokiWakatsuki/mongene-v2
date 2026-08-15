"""product/ground_truth コーパス生成で使う pinned seed ヘルパ。

`{lesson}_{form}_{level_label}` キーから決定論的に seed を導出する。
`build_ground_truth_corpus.py` と `build_product_corpus.py` の両方がこれを使うことで、
GT と product が同一 base_seed で生成され、run_gates.py の 1:1 ゲート比較が
「同じ問題」同士の比較になることを保証する。

**注意**: ここで得られる値は `GenerationRequest.seed`（= base_seed）に注入するもの。
`BlueprintRunner.run()` はリトライ毎に `seed = base_seed + attempt` を使うため、
出力される `mr.seed`（per-attempt seed）はこの pinned seed と異なる場合がある。
ペアリングは常にこの関数が返す base_seed を両側（GT/product）に注入することで行う。
"""
from __future__ import annotations

import zlib


def pinned_seed(lesson: str, form: str, level_label: str) -> int:
    """(lesson, form, level_label) から決定論的な base_seed (1始まり) を導出する。"""
    key = f"{lesson}_{form}_{level_label}"
    return zlib.adler32(key.encode()) % 1_000_000 + 1
