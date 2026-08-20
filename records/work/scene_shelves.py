"""場面の棚がどこにあるかを**1か所で**答える。

## なぜ要るか

棚は module ごとに分かれている。1元1次は `scenes.SCENES`、2次は
`word_problem_quadratic.SCENE_SHELF`——分かれているのは、場面の型
（`SceneText` / `QuadScene`）が「未知数と答えがいくつあるか」で違うためで、
これは畳めない。

★**しかし「どこに棚があるか」を各検査が自分で持つと必ず取りこぼす。**
このプロジェクトで一番起きている事故がそれで、charter §6 の4 に
「同じ規約を複数の場所に複製しない」と書いてある（頂点名から `I` を外す作業で
4か所に散っていて、1か所直して作り直しても消えなかった）。

実際に起きた: 作業3 で1元1次の場面を `scenes.py` の棚へ移したとき、
**G-SC1（語彙の契約）の走査対象に `scenes.py` が入っていなかった**。
`word_problem_linear.py` 側は通るので、6場面が一度も検査されないまま
「契約の違反 0 件」と出ていた。棚を足すたびに同じことが起きる。

だから棚の一覧はここだけに置き、検査はここから引く。

    from scene_shelves import shelves, shelf_files

## 棚に置ける場面の最小条件

`id` / `vocab` / `render` を持つこと。`requires` / `forbids` / `limits` は
無ければ空として扱う（棚が育つ途中でも検査が動くようにする）。
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, NamedTuple


class Shelf(NamedTuple):
    """1つの棚。"""

    label: str          # 検査の出力に出す名前（`scenes.py` など）
    path: Path          # ソースの場所（ast で読む検査が使う）
    attr: str           # 棚の変数名（`SCENES` / `SCENE_SHELF`）
    specs: tuple[Any, ...]   # 場面の並び


# ★棚を足したらここに1行足す。**検査の側には何も足さない。**
_SHELVES: tuple[tuple[str, str, str], ...] = (
    # (module 名, 棚の変数名, 説明)
    ("scenes", "SCENES", "1元1次（未知数1つ・答え1つ）"),
    ("word_problem_quadratic", "SCENE_SHELF", "2次（答えが2つになりうる）"),
)


def shelves() -> tuple[Shelf, ...]:
    """棚を全部集める。**1つも見つからなければ落とす。**

    ★0件を黙って返すと、検査が「違反 0 件」を出して合格に見える
    （charter §6 の5）。ここで落とす。
    """
    import importlib  # noqa: PLC0415

    from engine_paths import RECIPES_DIR  # noqa: PLC0415

    out: list[Shelf] = []
    missing: list[str] = []
    for mod_name, attr, _why in _SHELVES:
        mod = importlib.import_module(f"engine.packs.math.recipes.{mod_name}")
        specs = getattr(mod, attr, None)
        if not specs:
            missing.append(f"{mod_name}.{attr}")
            continue
        out.append(Shelf(f"{mod_name}.py", RECIPES_DIR / f"{mod_name}.py", attr, tuple(specs)))
    if missing:
        raise ValueError(
            "棚が見つからない: " + ", ".join(missing)
            + "\n（名前を変えたなら records/work/scene_shelves.py の _SHELVES を直すこと）"
        )
    if not out:
        raise ValueError("棚が1つも無い＝検査が動いていない")
    return tuple(out)


def all_specs() -> Iterator[tuple[str, Any]]:
    """(棚の名前, 場面) を全部。"""
    for sh in shelves():
        for sp in sh.specs:
            yield sh.label, sp


def shelf_files() -> tuple[Path, ...]:
    """棚が書かれているソースの場所（ast で読む検査が使う）。"""
    return tuple(sh.path for sh in shelves())


def phrases_by_scene() -> dict[str, tuple[tuple[tuple[str, ...], ...], tuple[str, ...]]]:
    """{場面の名前: (requires, forbids)}。棚をまたいで集める。

    ★**名前が衝突したら落とす。** 別の棚に同じ `id` があると、どちらの宣言を
    当てているのか分からなくなる（黙って上書きすると、片方の場面が
    もう片方の宣言で検査される＝検査しているつもりで別物を見る）。
    """
    out: dict[str, tuple] = {}
    owner: dict[str, str] = {}
    clash: list[str] = []
    for label, sp in all_specs():
        if sp.id in out:
            clash.append(f"{sp.id}（{owner[sp.id]} と {label}）")
        out[sp.id] = (getattr(sp, "requires", ()), getattr(sp, "forbids", ()))
        owner[sp.id] = label
    if clash:
        raise ValueError("場面の名前が棚をまたいで衝突: " + ", ".join(sorted(set(clash))))
    return out


if __name__ == "__main__":
    for sh in shelves():
        print(f"{sh.label:32} {sh.attr:12} 場面 {len(sh.specs)} 個")
        for sp in sh.specs:
            req = getattr(sp, "requires", ())
            fb = getattr(sp, "forbids", ())
            lim = getattr(sp, "limits", {})
            print(f"    {sp.id:22} 役割の型 {len(sp.render)} / requires {len(req)}"
                  f" / forbids {len(fb)}{' / limits あり' if lim else ''}")
    print(f"\n合計 {sum(len(s.specs) for s in shelves())} 場面")
