#!/usr/bin/env python3
"""mongene-v2（開発）から mongene-engine（清書）へ、エンジンを一方向で写す。

## なぜ道具にするか

2つのリポジトリで同じコードを持つと、**片方だけ直る**。今日1日で3回踏んだ根で、
いちばん重かったのは「家から公園まで片道45km」を一度直したのに、
同じ規約のもう1か所（往復の方程式側）に歯止めが無く 12km が出ていた件。

だから写す作業を手でやらない。**向きは常に v2 → engine の一方向**で、
逆向き（engine 側で直す）を機械が拒む。

    v2 (開発)                          engine (清書)
    engine_core/engine/   ──写す──▶   engine/
    engine_core/tests/    ──写す──▶   tests/
                                       app/ README.md Dockerfile pyproject.toml
                                       ↑ engine 側にしか無い。写す対象ではない

## 使い方

    PYTHONPATH=engine_core .venv/bin/python records/work/export_engine.py [--dest PATH] [--yes]

`--yes` が無ければ、何が変わるかを出すだけで書き込まない（既定は空振り）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SRC = Path("engine_core")
# (v2 側, engine 側)。**この表がすべて。** 増やすときはここだけ触る。
_PAIRS = (("engine", "engine"), ("tests", "tests"))
_DEST_ONLY = ("app", "README.md", "Dockerfile", "pyproject.toml", ".gitignore", ".dockerignore")


def _git(dest: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(dest), *args],
                          capture_output=True, text=True, check=True).stdout


def local_edits(dest: Path, would_overwrite: set[str]) -> list[str]:
    """★清書側の手入れのうち、**これから上書きして消えるもの**だけを挙げる。

    「未コミットの変更がある」だけで止めてはいけない——**前回この道具が写した変更**も
    未コミットとして見えるので、毎回鳴って、いずれ無視されるようになる。
    危ないのは「清書側で直した」かつ「これから上書きされる」ものだけ。
    すでに v2 と同じ中身なら、写しても何も失われない。
    """
    dirty = {line[3:].strip() for line in _git(dest, "status", "--porcelain").splitlines()}
    return sorted(p for p in dirty
                  if any(p.startswith(f"{d}/") for _s, d in _PAIRS) and p in would_overwrite)


def main(argv: list[str]) -> int:
    dest = Path(argv[argv.index("--dest") + 1] if "--dest" in argv
                else Path.home() / "workspace" / "mongene-engine")
    apply = "--yes" in argv

    if not (dest / ".git").is_dir():
        print(f"清書リポジトリが無い: {dest}")
        return 1
    for name in _DEST_ONLY:
        if not (dest / name).exists():
            print(f"★清書側にあるはずのものが無い: {name}（写す先を間違えている可能性）")
            return 1

    def _rsync(src: Path, dst: Path, *, dry: bool) -> list[str]:
        # ★`-i`（変更の明細）は**両方の場合に付ける**。付けないと rsync は成功時に
        # 何も出さず、数え上げが常に 0 になる——「写した 0 件」と表示されて、
        # 写せていないのか出力が無いのかを区別できなかった（実際に一度そうなった）。
        cmd = ["rsync", "-ai", "--delete",
               "--exclude=__pycache__", "--exclude=*.pyc", "--exclude=.pytest_cache",
               f"{src}/", f"{dst}/"]
        if dry:
            cmd.insert(2, "--dry-run")
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return [line for line in out.splitlines() if line.strip()]

    # 先に空振りして「これから上書きされるもの」を確定させる（守りの判定に要る）。
    plan: dict[str, list[str]] = {}
    would: set[str] = set()
    for src_name, dest_name in _PAIRS:
        lines = _rsync(_SRC / src_name, dest / dest_name, dry=True)
        plan[dest_name] = lines
        would |= {f"{dest_name}/{line.split(None, 1)[1]}" for line in lines
                  if len(line.split(None, 1)) == 2}

    edits = local_edits(dest, would)
    if edits:
        print("=== ★清書側で直したものを、これから上書きしようとしている ===")
        for p in edits[:20]:
            print(f"  {p}")
        print("\nエンジンの修正は **mongene-v2 側で行う**。"
              "清書側の変更を v2 に戻してから、もう一度この道具を回すこと。")
        return 1

    for src_name, dest_name in _PAIRS:
        lines = plan[dest_name] if not apply else _rsync(_SRC / src_name, dest / dest_name, dry=False)
        head = "写した" if apply else "写す予定"
        print(f"{_SRC / src_name} → {dest / dest_name}: {head} {len(lines)} 件")
        for line in lines[:10]:
            print(f"    {line}")
        if len(lines) > 10:
            print(f"    …ほか {len(lines) - 10} 件")

    if not apply:
        print("\n（空振り。実際に書くには --yes を付ける）")
    else:
        print(f"\n清書側で確認すること:  cd {dest} && pytest -q -n7")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
