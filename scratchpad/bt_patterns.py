"""G-BT（逆翻訳）の対象を、**文型で数え上げる**。

7回目に読んだのは 130 問＝「セルごとに数 seed」。文型がいくつあるかを数えて
いないので、**読んでいない文型がいくつ残っているか**が誰にも分からなかった。
ここで文型を数え、まだ読んでいないものだけを書き出す。

## 文型の作り方

問題文から
  ・数（整数・小数・分数）        → `#`
  ・params の文字列の値（人名・品物・場面）→ `＠`
を伏せる。残ったものが文型。**同じ文型なら、日本語と数式の対応は同じ理屈で
決まる**（同じテンプレートが組み立てている）ので、1つ読めばその文型は見たことになる。

人名や品物を伏せるのは、それが「中身」であって骨格ではないから。伏せずに数えると
g2_l16 の果物の組み合わせだけで 40 通りになり、読む価値のない重複で埋まる。

実行:
  PYTHONPATH=. .venv/bin/python scratchpad/bt_patterns.py [--seeds N] [--forms word_problem,find_value]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import build_mr, capability_cells, cell_request, make_env

_DIR = Path("scratchpad/bt")
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


_POINT_NAME = re.compile(r"(?<![a-z])[A-Z]['′]?(?![a-z])")
# 変数に使う文字（x でも a でも骨格は同じ）。`cm` `kg` のような単位は2文字以上なので残る。
_VAR_LETTER = re.compile(r"(?<![A-Za-z])[a-z](?![A-Za-z])")
# 「#、#、#、#」のような並び（データの列）。個数の違いは文型の違いではない。
_RUN = re.compile(r"([#＠])(?:([、,／/ ])[#＠]){2,}")


def _values(obj):
    """params の中の文字列を全部。**入れ子の dict も辿る**。

    params は `{"slots": {"item": "消しゴム"}}` のように入れ子になっている。
    浅くしか見ないと、品物名が伏せられず、同じ文型が品物の数だけ増える。
    """
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _values(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _values(v)


def _skeleton(text: str, params: dict) -> str:
    """文型。数・場面の言葉・点の名前を伏せる。

    点の名前（J・L・M…）は seed ごとに引き直される**中身**で、骨格ではない。
    伏せずに数えると「2直線の交点をJ…」と「…をG…」が別の文型になり、
    exam_l1 の1セルだけで 24 通りに膨れる（最初にこれを踏んだ）。
    """
    out = text
    # 1文字の値も伏せる（「白」「緑」＝玉の色）。長いものから順に置きかえないと
    # 「白玉」の「白」だけが先に消えて別の文型になる。
    fillers = sorted(
        {v for v in _values(params) if v and not v.isascii()}, key=len, reverse=True,
    )
    for f in fillers:
        out = out.replace(f, "＠")
    out = _VAR_LETTER.sub("＠", _POINT_NAME.sub("＠", _NUM.sub("#", out)))
    # データの並び（`#、#、#、…`）は、**個数が違っても同じ文型**。
    return _RUN.sub(r"\1…", out)


def _already_read() -> set[str]:
    """すでに読んだ問題の id（`cell#seed`）。"""
    done: set[str] = set()
    for p in sorted(_DIR.glob("answers*.tsv")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or "\t" not in line:
                continue
            done.add(line.split("\t", 1)[0].strip())
    return done


def main() -> int:
    seeds = 24
    forms = ("word_problem",)
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    if "--forms" in sys.argv:
        forms = tuple(sys.argv[sys.argv.index("--forms") + 1].split(","))

    env = make_env()
    _DIR.mkdir(parents=True, exist_ok=True)
    done_ids = _already_read()

    # 文型 → 代表（cell, seed, 本文, 問い）と、その文型が既読かどうか
    patterns: dict[str, dict[str, object]] = {}
    for coord in capability_cells(env):
        if coord.form not in forms:
            continue
        cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception:  # noqa: BLE001
                continue
            if isinstance(res, Unsupported):
                continue
            mr = build_mr(coord, seed, env).mr
            key = cell + "|" + _skeleton(res.problem_text, dict(mr.params) if mr else {})
            pid = f"{cell}#{seed}"
            row = patterns.setdefault(key, {
                "cell": cell, "seed": seed, "id": pid, "n": 0, "read": False,
                "unit": coord.unit, "form": coord.form, "level": coord.level,
                "text": res.problem_text.strip(),
                "ask": " / ".join(sq.prompt_text or "" for sq in res.sub_questions).strip(),
            })
            row["n"] = int(row["n"]) + 1  # type: ignore[arg-type]
            if pid in done_ids:
                row["read"] = True
                row["id"] = pid
                row["seed"] = seed
                row["text"] = res.problem_text.strip()

    unread = [r for r in patterns.values() if not r["read"]]
    lines = [
        "# 逆翻訳の入力（まだ読んでいない文型だけ）",
        "",
        "**この日本語だけを読んで**答えを出し、`answers3.tsv` に `id<TAB>答え` で書く。",
        "式でも答えでもよい（`bt_check.py` は数を値で突き合わせる）。図が要るものは N/A。",
        "",
    ]
    for r in sorted(unread, key=lambda r: str(r["id"])):
        lines.append(f"## {r['id']}")
        lines.append("")
        lines.append(str(r["text"]))
        if r["ask"]:
            lines.append(f"（問い） {r['ask']}")
        lines.append("")

    (_DIR / "problems3.md").write_text("\n".join(lines), encoding="utf-8")
    (_DIR / "patterns.json").write_text(
        json.dumps(list(patterns.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"文型 {len(patterns)} 種 / 既読 {len(patterns) - len(unread)} / "
          f"未読 {len(unread)} → scratchpad/bt/problems3.md（{seeds} seed/セル）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
