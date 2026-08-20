#!/usr/bin/env python3
"""量産のとき、**誰がどこを書いたか**を差分で見る（関門②＝経路の独立）。

## なぜ要るか

このエンジンの品質の土台は「解く経路が2本あって一致する」ことにある
（recipe が組み、checker が独立に解き直す）。ところが**数式と checker を
同じ手が1回で書くと、同じ誤解が2本に入って一致してしまう**。
しかも①解ける ②二重解き ③逆翻訳 の検査は全部通る——2本とも同じ間違いをしているから。

前例がある。checker が立式コードを再利用していたために「日本語だけが違う問題」が
7回のセッションを生き延びた（g3_l37「2等分」なのに解いているのは等積）。
見つけたのは、**問題文だけを読んで解き直す**経路だった。

人が書いていたときは1人が両方を書いても事故は稀だったが、AI に量産させると
**系統的に**起きる。だから運用の規約ではなく、差分で見る。

## 役割ごとに触ってよい場所

    author   数式パーツ・文型パーツ・recipe・設計書（family YAML）
             → **checker と golden は触らない**
    checker  checker とそのテスト
             → **recipe と設計書は触らない**（書き手の実装を見ずに書くため）

★この2つを別のセッションに割り、差分が**重ならない**ことを確かめる。
重なった時点で、その回の二重解きは検査として死んでいる。

実行:
  .venv/bin/python records/work/check_write_scope.py --role author
  .venv/bin/python records/work/check_write_scope.py --role checker --range HEAD~1..HEAD
  .venv/bin/python records/work/check_write_scope.py --self-test
"""
from __future__ import annotations

import subprocess
import sys

# 役割 -> (触ってよい接頭辞, 触ってはいけない接頭辞)
# ★禁止側を「触ってよいの否定」にしない。**両方を書く**——許可の書き漏れが
# 「禁止していない」に化けるのを防ぐ（許可に無い新しい場所は下の「宣言外」で鳴る）。
_ROLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "author": (
        (
            "engine_core/engine/packs/math/recipes/",
            "engine_core/engine/packs/math/parts/",
            "engine_core/engine/curriculum/math/families/",
            "records/work/failure_catalog.yaml",
        ),
        (
            "engine_core/engine/packs/math/checkers/",
            "engine_core/tests/",
        ),
    ),
    "checker": (
        (
            "engine_core/engine/packs/math/checkers/",
            "engine_core/tests/unit/",
        ),
        (
            "engine_core/engine/packs/math/recipes/",
            "engine_core/engine/packs/math/parts/",
            "engine_core/engine/curriculum/math/families/",
            "engine_core/tests/golden/",
        ),
    ),
}


def findings(role: str, paths: list[str]) -> list[str]:
    allowed, forbidden = _ROLES[role]
    out: list[str] = []
    for p in sorted(paths):
        if p.startswith(forbidden):
            out.append(f"{role} が触ってはいけない場所を書いた: {p}")
        elif not p.startswith(allowed):
            out.append(f"{role} の宣言に無い場所: {p}（許可も禁止もされていない）")
    return out


def overlap(author_paths: list[str], checker_paths: list[str]) -> list[str]:
    """2つの役割が同じファイルを書いていないか（経路が混ざった証拠）。"""
    both = sorted(set(author_paths) & set(checker_paths))
    return [f"両方の役割が同じファイルを書いた: {p}" for p in both]


def _changed(rng: str | None) -> list[str]:
    cmd = ["git", "diff", "--name-only"] + ([rng] if rng else [])
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    if not rng:
        out += subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
    return [line for line in out.splitlines() if line.strip()]


def self_test() -> int:
    """★通る側と落ちる側の両方を持つ。"""
    cases = [
        ("author が場面パーツを書いた", "author",
         ["engine_core/engine/packs/math/recipes/scenes.py"], 0),
        ("author が設計書を書いた", "author",
         ["engine_core/engine/curriculum/math/families/g1_l25.word_problem.yaml"], 0),
        ("★author が checker を書いた", "author",
         ["engine_core/engine/packs/math/checkers/word_problem_linear.py"], 1),
        ("★author が golden を書き換えた", "author",
         ["engine_core/tests/golden/math.g1_l25.word_problem/approval.yaml"], 1),
        ("checker が checker を書いた", "checker",
         ["engine_core/engine/packs/math/checkers/word_problem_linear.py"], 0),
        ("★checker が recipe を書いた", "checker",
         ["engine_core/engine/packs/math/recipes/word_problem_linear.py"], 1),
        ("★宣言に無い場所", "author", ["engine_core/engine/core/pipeline.py"], 1),
    ]
    fails = 0
    for name, role, paths, want in cases:
        got = findings(role, paths)
        ok = len(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")

    got = overlap(["a/x.py", "a/y.py"], ["a/y.py"])
    ok = len(got) == 1
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}合成「両方が同じファイルを書いた」: {got or '合格'}")
    got = overlap(["a/x.py"], ["b/y.py"])
    ok = not got
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}合成「重なっていない」: {got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return 1 if self_test() else 0
    if "--role" not in argv:
        print(f"usage: check_write_scope.py --role {{{'|'.join(_ROLES)}}} [--range A..B]")
        return 2
    role = argv[argv.index("--role") + 1]
    if role not in _ROLES:
        print(f"知らない役割: {role!r}（{', '.join(_ROLES)}）")
        return 2
    rng = argv[argv.index("--range") + 1] if "--range" in argv else None

    paths = _changed(rng)
    print(f"役割 {role} / 変更 {len(paths)} ファイル（{rng or '作業ツリー'}）")
    if not paths:
        print("★1ファイルも変わっていない＝何も書いていないか、範囲の指定が違う")
        return 1
    bad = findings(role, paths)
    if bad:
        print(f"=== 役割からはみ出した書き込み {len(bad)} 件 ===")
        for b in bad:
            print(f"  {b}")
        return 1
    print("=== 役割の中だけを書いている ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
