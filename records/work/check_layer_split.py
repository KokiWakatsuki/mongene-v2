"""層に割れているかを機械で見る（作業1 の合否判定）。

charter §4 の作業1 は、生成物が同一であること（golden）に加えて次の2つを条件にしている。

  - **Scene のコードに数の抽選が無い**（`draw` を呼ばない・`rng` を受け取らない）
  - **Relation のコードに日本語が無い**（出力に混ざる文字列を持たない）

「分けたつもりで Relation に日本語が残る」のがいちばん起きやすいので、目視ではなく
ここで見る。層の見分けは**関数名の規約**で行う（`_relation_*` / `_scene_*`）。

★日本語の判定から docstring は外す。この repo のコメントと docstring は日本語で
書かれているので、それを禁じるのは意味がない。禁じたいのは**出力に流れる文字列**。

自分自身の検査も持つ（`--self-test`）。合成した違反コードを与えて、ちゃんと落ちることを
確かめる——0件を返す走査は、動いていないのと区別がつかない。

実行: .venv/bin/python records/work/check_layer_split.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from engine_paths import RECIPES_DIR  # エンジンの場所は1か所で解決する

_DIR = RECIPES_DIR
# 層に割り終えた module（割るたびにここへ足す）
_SPLIT = [
    "word_problem_linear.py",
    "word_problem_system.py",
    "word_problem_proportion_frequency.py",
    "word_problem_quadratic.py",
    "word_problem_expression.py",
]

_JA = re.compile(r"[぀-ヿ一-鿿]")


def _is_relation(name: str) -> bool:
    return name.startswith("_relation_") or name.endswith("_candidates")


def _is_scene(name: str) -> bool:
    return name.startswith("_scene_")


def _string_literals(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    """docstring を除いた文字列リテラル（行番号つき）。"""
    body = list(fn.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    out: list[tuple[int, str]] = []
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append((node.lineno, node.value))
    return out


def _draw_calls(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    """抽選の呼び出し（名前に draw を含むもの）。"""
    out: list[tuple[int, str]] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
        if "draw" in name:
            out.append((node.lineno, name))
    return out


def check_source(src: str, label: str) -> list[str]:
    """1 module を見る。返すのは違反の並び（空なら合格）。"""
    bad: list[str] = []
    tree = ast.parse(src)
    n_rel = n_scene = 0
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        if _is_relation(fn.name):
            n_rel += 1
            for lineno, text in _string_literals(fn):
                if _JA.search(text):
                    bad.append(f"{label}:{lineno} Relation に日本語: "
                               f"{fn.name} → {text[:40]!r}")
        elif _is_scene(fn.name):
            n_scene += 1
            args = [a.arg for a in fn.args.args]
            if "rng" in args:
                bad.append(f"{label}:{fn.lineno} Scene が rng を受け取っている: {fn.name}")
            for lineno, name in _draw_calls(fn):
                bad.append(f"{label}:{lineno} Scene が抽選している: {fn.name} → {name}()")
    if not n_rel or not n_scene:
        bad.append(f"{label}: 層が見つからない（Relation {n_rel} / Scene {n_scene}）"
                   "＝検査が動いていない疑い")
    return bad


_BAD_RELATION = '''
def _relation_x(p, rng):
    label = "代金の合計"
    return label
def _scene_x(n, v):
    return "文"
'''
_BAD_SCENE = '''
def _relation_x(p, rng):
    return 1
def _scene_x(n, v, rng):
    item = draw(list(p["item_candidates"]), rng)
    return item
'''


def self_test() -> int:
    """合成した違反コードで、**落ちる場合が出る**ことを確かめる。"""
    fails = 0
    for name, src, want in [
        ("Relation に日本語", _BAD_RELATION, "Relation に日本語"),
        ("Scene が抽選", _BAD_SCENE, "Scene が抽選"),
    ]:
        got = check_source(src, "synthetic")
        ok = any(want in g for g in got)
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成データ「{name}」で落ちる: {got}")
    clean = check_source(
        'def _relation_x(p, rng):\n    """日本語の説明。"""\n    return 1\n'
        'def _scene_x(n, v):\n    return "代金"\n', "synthetic")
    ok = clean == []
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}正しいコードは通る: {clean}")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        return 1 if self_test() else 0
    bad: list[str] = []
    for name in _SPLIT:
        bad += check_source((_DIR / name).read_text(encoding="utf-8"), name)
    if bad:
        print(f"=== 層の違反 {len(bad)} 件 ===")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"=== 層は割れている（見た module {len(_SPLIT)}: {', '.join(_SPLIT)}）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
