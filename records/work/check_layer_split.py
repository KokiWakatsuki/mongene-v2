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


def _targets() -> list[str]:
    """見る file。**棚のある file は `scene_shelves.py` から引く。**

    ★棚を足したとき走査対象に入れ忘れる事故を防ぐ（G-SC1 で実際に起きた）。
    """
    from scene_shelves import shelf_files  # noqa: PLC0415

    out = list(_SPLIT)
    for path in shelf_files():
        if path.name not in out:
            out.append(path.name)
    return out

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


def _shelf_writers(tree: ast.Module) -> set[str]:
    """棚（`SCENES` / `SCENE_SHELF`）の `render` に載っている関数の名前。

    ★**名前の規約だけでは棚の書き手が見えない。** `scenes.py` の書き手は
    `_shopping_total` / `_admission_diff` のような名前で `_scene_*` ではないので、
    層の検査は **16個の書き手を1つも見ていなかった**（`word_problem_linear.py` 側の
    `_scene_*` が通るので「層は割れている」と出る）。
    棚に載っている関数は、名前が何であれ場面の書き手である——**登録されている
    事実を見る**（G-SC1 が対応づけを辞書リテラルから読むのと同じ理由）。

    ★`pick_scene` は `draw` を呼ぶが、棚の `render` には載らないので当たらない
    （場面を選ぶのは場面の仕事ではない）。
    """
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", None) not in ("SCENES", "SCENE_SHELF"):
            continue
        for call in getattr(node.value, "elts", []):
            if not isinstance(call, ast.Call):
                continue
            for kw in call.keywords:
                if kw.arg == "render":
                    out |= {
                        v.id for v in getattr(kw.value, "values", [])
                        if isinstance(v, ast.Name)
                    }
    return out


def check_source(src: str, label: str) -> list[str]:
    """1 module を見る。返すのは違反の並び（空なら合格）。"""
    bad: list[str] = []
    tree = ast.parse(src)
    writers = _shelf_writers(tree)
    n_rel = n_scene = 0
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        if _is_relation(fn.name):
            n_rel += 1
            for lineno, text in _string_literals(fn):
                if _JA.search(text):
                    bad.append(f"{label}:{lineno} Relation に日本語: "
                               f"{fn.name} → {text[:40]!r}")
        elif _is_scene(fn.name) or fn.name in writers:
            n_scene += 1
            args = [a.arg for a in fn.args.args]
            if "rng" in args:
                bad.append(f"{label}:{fn.lineno} Scene が rng を受け取っている: {fn.name}")
            for lineno, name in _draw_calls(fn):
                bad.append(f"{label}:{lineno} Scene が抽選している: {fn.name} → {name}()")
    # ★棚だけの module（`scenes.py`）は Relation を持たない——場面しか置いていないから。
    # そこで Relation の不在を違反にすると、正しい形が落ちる。
    # 見るべきは「**何も見ていない**のに通っていないか」なので、両方0のときだけ疑う。
    if not n_rel and not n_scene:
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

# ★棚の書き手は `_scene_*` という名前ではない（`scenes.py` は `_shopping_total` 等）。
# 名前の規約だけを見ていたときは **16個の書き手を1つも見ていなかった**ので、
# 「名前が規約から外れた書き手でも当たる」ことをここで押さえる。
_BAD_SHELF_WRITER = '''
def _relation_x(p, rng):
    return 1
def _shopping_total(n, v, rng):
    item = draw(list(p["item_candidates"]), rng)
    return item
SCENES = (
    SceneSpec(id="shopping", vocab=(), render={ROLES: _shopping_total}),
)
'''
_GOOD_SHELF_WRITER = '''
def _relation_x(p, rng):
    return 1
def _shopping_total(n, v):
    return f"{v['item']}を買う"
SCENES = (
    SceneSpec(id="shopping", vocab=(), render={ROLES: _shopping_total}),
)
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
    for name, src, want in [
        ("棚の書き手が rng を受け取る", _BAD_SHELF_WRITER, "rng を受け取っている"),
        ("棚の書き手が抽選する", _BAD_SHELF_WRITER, "抽選している"),
    ]:
        got = check_source(src, "synthetic")
        ok = any(want in g for g in got)
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成データ「{name}」で落ちる: {got}")
    got = check_source(_GOOD_SHELF_WRITER, "synthetic")
    ok = got == []
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}正しい棚の書き手は通る: {got}")

    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        return 1 if self_test() else 0
    bad: list[str] = []
    targets = _targets()
    for name in targets:
        bad += check_source((_DIR / name).read_text(encoding="utf-8"), name)
    if bad:
        print(f"=== 層の違反 {len(bad)} 件 ===")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"=== 層は割れている（見た module {len(targets)}: {', '.join(targets)}）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
