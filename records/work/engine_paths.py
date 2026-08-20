"""エンジンの実体がどこにあるかを**1か所で**答える。

## なぜ要るか

エンジンのコードは `mongene-engine` に移り、この repo（mongene-v2）は
**記録と走査だけ**を持つ。走査は engine を import して動かすが、
`units.generated.yaml` や family YAML の**ファイルそのもの**を読む道具も多い。

移す前は 45 箇所が `Path("engine_core/engine/...")` と直書きしていた。
★**この形が、このプロジェクトでいちばん事故を起こしている**（頂点名から I を
外す作業で4か所に散っていて、1か所直しても消えなかった／往復の距離の上限が
2か所にあって片方だけ直っていた）。移すついでに1か所へ集約する。

## どうやって場所を知るか

**インストールされた `engine` パッケージの位置から引く。** パスを書かない。
`pip install -e ../mongene-engine` でも、通常の install でも同じように解決する。

    from engine_paths import ENGINE_DIR, FAMILIES_DIR, UNITS_YAML, RECIPES_DIR, TESTS_DIR
"""
from __future__ import annotations

from pathlib import Path

import engine as _engine_pkg

# エンジンのパッケージが置かれている場所（editable install なら
# ../mongene-engine/engine、通常の install なら site-packages の中）。
ENGINE_DIR = Path(_engine_pkg.__file__).resolve().parent

CURRICULUM_DIR = ENGINE_DIR / "curriculum" / "math"
FAMILIES_DIR = CURRICULUM_DIR / "families"
UNITS_YAML = CURRICULUM_DIR / "units.generated.yaml"
PACKS_DIR = ENGINE_DIR / "packs" / "math"
RECIPES_DIR = PACKS_DIR / "recipes"

# テストと golden はエンジン側にある（清書リポジトリの中）。
# ★通常の install（site-packages）には tests が入らないので、check() では検査しない。
#   使う側が `TESTS_DIR.exists()` を見て、無ければその場で落とすこと。
TESTS_DIR = ENGINE_DIR.parent / "tests"
GOLDEN_DIR = TESTS_DIR / "golden"


def check() -> None:
    """★場所が本当に在るか確かめる。無ければここで落とす。

    直書きを消した代わりに、解決を1か所に集めた。ここが黙って外れると
    **全部の走査が「0件」を返す**（見ていないのに合格に見える）ので、
    存在の確認まで持つ。
    """
    missing = [str(p) for p in (FAMILIES_DIR, UNITS_YAML, RECIPES_DIR) if not p.exists()]
    if missing:
        raise SystemExit(
            "エンジンの実体が見つからない:\n  " + "\n  ".join(missing)
            + "\n\n`pip install -e ../mongene-engine` を済ませているか確認すること。"
        )


if __name__ == "__main__":
    check()
    print(f"engine     {ENGINE_DIR}")
    print(f"families   {FAMILIES_DIR}（{len(list(FAMILIES_DIR.glob('*.yaml')))} 枚）")
    print(f"units      {UNITS_YAML}")
    print(f"recipes    {RECIPES_DIR}（{len(list(RECIPES_DIR.glob('*.py')))} 本）")
    print(f"tests      {TESTS_DIR}（{'在り' if TESTS_DIR.exists() else '無し'}）")
    print(f"golden     {GOLDEN_DIR}（{'在り' if GOLDEN_DIR.exists() else '無し'}）")
