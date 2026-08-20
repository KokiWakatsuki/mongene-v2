"""G-BT（逆翻訳）の入力を **(関係 × 場面) の全組** で作る — 問題文だけを書き出す。

## 既存の bt_dump.py との違い

`bt_dump.py` は**セル × seed** で書き出す。セルは「単元・form・Lv」なので、
1つのセルが複数の場面を持つ場合（`variant` で比例と反比例が分かれる、
言い方が3通りある）に、**どの場面が出たかは seed 任せ**になる。
場面を量産したあとは「新しく足した場面が一度も読まれていない」が起こる。

ここは **(recipe, 関係, 場面の枝) を鍵にして、それぞれ N 問**そろえる。
そろわなかった組は**名前を挙げて報告する**（黙って通すと「全部読んだ」に見える）。

## 読み手に渡すのは問題文だけ

出すのは `records/work/bt/scenes.md`（日本語だけ）。答え・式・params・場面のコードは
渡さない（引きずられる）。読み手は `records/work/bt/answers*.tsv` に
`id<TAB>立てた式または答え` を書き、`bt_check.py` がエンジンと突き合わせる。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/bt_dump_scenes.py [--per 5] [--budget 400]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import build_mr, make_env

sys.path.insert(0, "records/work")

_OUT = Path("records/work/bt")
# 場面の枝を表す params の鍵（数ではない構成フラグ・言い方の選び）。
_BRANCH_KEYS = ("variant", "phrasing", "guided")


def _declared_kinds() -> set[tuple[str, str]]:
    """層に割れた recipe が持つ (recipe, 関係) の全部。"""
    from engine.packs.math.recipes import (  # noqa: PLC0415
        word_problem_expression,
        word_problem_linear,
        word_problem_proportion_frequency,
        word_problem_quadratic,
        word_problem_system,
    )

    out: set[tuple[str, str]] = set()
    for mod in (word_problem_linear, word_problem_system,
                word_problem_proportion_frequency, word_problem_quadratic,
                word_problem_expression):
        out |= {(mod.RECIPE_NAME, kind) for kind in mod.SCENE_RENDERERS}
    return out


def _branch(params: dict) -> str:
    """場面の枝（`variant` / `phrasing` / `guided`）を1つの文字にする。"""
    parts = []
    for key in _BRANCH_KEYS:
        if key in params:
            parts.append(f"{key}={params[key]}")
        elif isinstance(params.get("slots"), dict) and key in params["slots"]:
            parts.append(f"{key}={params['slots'][key]}")
    return ",".join(parts)


def main(argv: list[str]) -> int:
    bootstrap()
    from build_corpus import load_cells  # noqa: PLC0415

    per = int(argv[argv.index("--per") + 1]) if "--per" in argv else 5
    # 1セルにつき引く seed の上限。★はじめ 400 にして「全部そろったら抜ける」条件を
    # セルをまたいで書いたので、どのセルでも 400 引いてしまい2分で終わらなかった。
    # 打ち切りは**そのセルの中で**判定する。
    budget = int(argv[argv.index("--budget") + 1]) if "--budget" in argv else 60
    env = make_env()
    declared = _declared_kinds()

    picked: dict[tuple[str, str, str], list[tuple[str, int]]] = {}
    for unit, form, level, _c, _e, _f in load_cells():
        if form != "word_problem":
            continue
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        here: set[tuple[str, str, str]] = set()
        for seed in range(1, budget + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            key = (r.mr.provenance.recipe,
                   str(r.mr.params.get("scenario_kind", "")),
                   _branch(dict(r.mr.params)))
            if (key[0], key[1]) not in declared:
                break           # 層に割っていない recipe のセルは丸ごと対象外
            here.add(key)
            slot = picked.setdefault(key, [])
            if len(slot) < per:
                slot.append((f"{unit}.{form}.Lv{level}", seed))
            # そのセルで見えた枝が全部そろったら打ち切る（seed 20 までは見る
            # ——枝は seed で振られるので、早く抜けると片方しか見ない）。
            if seed >= 20 and all(len(picked[k]) >= per for k in here):
                break

    rows: list[dict[str, object]] = []
    lines: list[str] = [
        "# 逆翻訳の入力（問題文だけ）",
        "",
        "各問について、**この日本語だけを読んで**方程式（または連立方程式）を立て、",
        "`answers.tsv` に `id<TAB>式` の形で書く。答えを出せるなら答えでもよい。",
        "文字の置き方は問題文の指示に従う（指示が無ければ x）。",
        "",
    ]
    for key in sorted(picked):
        for cell, seed in picked[key]:
            unit, form, lv = cell.split(".")
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=int(lv.removeprefix("Lv")), seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            pid = f"{cell}#{seed}"
            rows.append({"id": pid, "unit": unit, "form": form,
                         "level": int(lv.removeprefix("Lv")), "seed": seed})
            # 誘導ありのセルは問いが本文に入っていて prompt_text が空。
            # 「（問い） /」だけの行を読み手に見せない（読む邪魔になる）。
            asks = " / ".join(
                t for t in (sq.prompt_text or "" for sq in res.sub_questions) if t.strip()
            )
            lines.append(f"## {pid}")
            lines.append("")
            lines.append(res.problem_text.strip())
            if asks.strip():
                lines.append(f"（問い） {asks.strip()}")
            lines.append("")

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "scenes.md").write_text("\n".join(lines), encoding="utf-8")
    (_OUT / "scenes.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    found = {(k[0], k[1]) for k in picked}
    missing = sorted(declared - found)
    short = sorted(f"{k[1]}[{k[2]}]" for k, v in picked.items() if len(v) < per)
    print(f"{len(rows)} 問 / (関係, 枝) {len(picked)} 組 / 関係 {len(found)}"
          f"（宣言 {len(declared)}）→ records/work/bt/scenes.md")
    if missing:
        print(f"★一度も出なかった関係 {len(missing)} 件（読み手に渡っていない）:")
        for recipe, kind in missing:
            print(f"    {kind}  ({recipe})")
    if short:
        print(f"★{per} 問そろわなかった組 {len(short)} 件: {', '.join(short)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
