"""G-SC1（契約）— 場面が読む名前が、ぜんぶ引かれているか。

作業1 で文章題は3層になった（Relation が数、宣言が語彙、Scene が日本語）。
層を分けると**新しい穴が1つ開く**: 場面文が `v["counter"]` と書いているのに
語彙の宣言にその名前が無い、という食い違い。生成すれば KeyError で落ちるが、
落ちるのは**その場面をたまたま引いた seed のときだけ**なので、
セルを1つ足したときに気づかないことがある。ここは静的に全部見る。

## 見るもの

  - 場面（`_scene_*`）が `v[...]` で読む名前が、`_SCENE_VOCAB` の宣言に全部あるか
  - 宣言してあるのに誰も読まない名前が無いか（消し忘れ・書き間違い）
  - 場面が `n[...]` で読む名前が、関係（`_relation_*`）の `numbers={...}` にあるか

対応づけは `SCENE_RENDERERS` / `RELATION_DRAWERS` の辞書リテラルから読む
（関数名の規約ではなく、**実際に登録されている対応**を見る）。

自分自身の検査を持つ（`--self-test`）。合成した違反コードで落ちることを確かめる
——0件を返す走査は、動いていないのと区別がつかない。

実行: .venv/bin/python records/work/check_scene_contract.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from engine_paths import RECIPES_DIR  # エンジンの場所は1か所で解決する

_DIR = RECIPES_DIR
_MODULES = [
    "word_problem_linear.py",
    "word_problem_system.py",
    "word_problem_proportion_frequency.py",
    "word_problem_quadratic.py",
    "word_problem_expression.py",
]


def _dict_of_names(tree: ast.Module, name: str) -> dict[str, str]:
    """`{"kind": _scene_x, ...}` の辞書リテラルを {kind: 関数名} で返す。"""
    # ★注釈つきの代入（`SCENE_RENDERERS: dict[...] = {...}`）は ast.AnnAssign で、
    # ast.Assign では拾えない。ここを見落として「対応づけが読めない」を5 module ぶん
    # 出した——**0件でなく「動いていない疑い」を出す作りにしておいたので気づけた**。
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", None) != name or not isinstance(node.value, ast.Dict):
            continue
        out: dict[str, str] = {}
        for k, v in zip(node.value.keys, node.value.values, strict=True):
            if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                out[str(k.value)] = v.id
        return out
    return {}


def _vocab_declared(tree: ast.Module) -> dict[str, set[str]]:
    """`_SCENE_VOCAB` の宣言から {kind: 出す名前の集合}。"""
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", None) != "_SCENE_VOCAB":
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for k, v in zip(node.value.keys, node.value.values, strict=True):
            if not isinstance(k, ast.Constant):
                continue
            names: set[str] = set()
            for step in getattr(v, "elts", []):
                elts = getattr(step, "elts", [])
                if len(elts) == 3:
                    names |= {
                        str(e.value) for e in getattr(elts[2], "elts", [])
                        if isinstance(e, ast.Constant)
                    }
            out[str(k.value)] = names
    return out


def _subscripts(fn: ast.FunctionDef, var: str) -> set[str]:
    """関数の中の `var["名前"]` の名前を集める。"""
    out: set[str] = set()
    for node in ast.walk(fn):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == var and isinstance(node.slice, ast.Constant)):
            out.add(str(node.slice.value))
    return out


def _numbers_keys(fn: ast.FunctionDef) -> set[str]:
    """関係が出す数の名前。

    ★`numbers={...}` の形だけを見ていたら、いったん `numbers = {...}` に入れてから
    渡している関係（枝で中身が変わる `judge_and_use`）を1つも拾えず、
    「関係が出していない」を4件誤って出した。**代入の形も見る。**
    """
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.keyword) and node.arg == "numbers" \
                and isinstance(node.value, ast.Dict):
            out |= {
                str(k.value) for k in node.value.keys if isinstance(k, ast.Constant)
            }
        if isinstance(node, ast.Assign | ast.AnnAssign):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if getattr(target, "id", None) == "numbers" and isinstance(node.value, ast.Dict):
                out |= {
                    str(k.value) for k in node.value.keys if isinstance(k, ast.Constant)
                }
    return out


def check_source(src: str, label: str) -> list[str]:
    """1 module を見る。返すのは違反の並び（空なら合格）。"""
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    scenes = _dict_of_names(tree, "SCENE_RENDERERS")
    relations = _dict_of_names(tree, "RELATION_DRAWERS")
    declared = _vocab_declared(tree)
    bad: list[str] = []
    if not scenes or not relations:
        return [f"{label}: 対応づけが読めない（場面 {len(scenes)} / 関係 {len(relations)}）"
                "＝検査が動いていない疑い"]
    for kind, fn_name in scenes.items():
        fn = fns.get(fn_name)
        if fn is None:
            bad.append(f"{label}: {kind} の場面 {fn_name} が見つからない")
            continue
        rel = fns.get(relations.get(kind, ""))
        # ★語彙は**場面だけでなく関係も読む**（値段や速さの相場は語彙といっしょに
        # 引かれて Relation に渡る）。場面だけを見て「誰も読まない」を5件誤って出した。
        read_v = _subscripts(fn, "v") | (_subscripts(rel, "v") if rel else set())
        given = declared.get(kind, set())
        for miss in sorted(read_v - given):
            bad.append(f"{label}: {kind} の場面が語彙 {miss!r} を読むが、宣言に無い")
        # `"_"` は「並びの都合で出るが使わない」と宣言した位置（`|` で割った余り）。
        for unused in sorted(given - read_v - {"_"}):
            bad.append(f"{label}: {kind} の語彙 {unused!r} は宣言されているが誰も読まない")
        if rel is not None:
            keys = _numbers_keys(rel)
            for miss in sorted(_subscripts(fn, "n") - keys):
                bad.append(f"{label}: {kind} の場面が数 {miss!r} を読むが、"
                           f"関係が出していない")
    return bad


_BAD_MISSING = '''
_SCENE_VOCAB = {"x": (("one", "item_candidates", ("item",)),)}
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{v['item']}を{v['counter']}買う{n['price']}円")
RELATION_DRAWERS = {"x": _relation_x}
SCENE_RENDERERS = {"x": _scene_x}
'''
_BAD_UNUSED = '''
_SCENE_VOCAB = {"x": (("one", "item_candidates", ("item", "counter")),)}
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{v['item']}を買う{n['price']}円")
RELATION_DRAWERS = {"x": _relation_x}
SCENE_RENDERERS = {"x": _scene_x}
'''
_BAD_NUMBER = '''
_SCENE_VOCAB = {"x": (("one", "item_candidates", ("item",)),)}
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{v['item']}を{n['total']}個買う")
RELATION_DRAWERS = {"x": _relation_x}
SCENE_RENDERERS = {"x": _scene_x}
'''
_GOOD = '''
_SCENE_VOCAB = {"x": (("one", "item_candidates", ("item", "counter")),)}
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{v['item']}を{v['counter']}買う{n['price']}円")
RELATION_DRAWERS = {"x": _relation_x}
SCENE_RENDERERS = {"x": _scene_x}
'''


def self_test() -> int:
    fails = 0
    for name, src, want in [
        ("宣言に無い語彙を読む", _BAD_MISSING, "宣言に無い"),
        ("誰も読まない語彙", _BAD_UNUSED, "誰も読まない"),
        ("関係が出していない数を読む", _BAD_NUMBER, "関係が出していない"),
    ]:
        got = check_source(src, "synthetic")
        ok = any(want in g for g in got)
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成データ「{name}」で落ちる: {got}")
    got = check_source(_GOOD, "synthetic")
    ok = got == []
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}正しいコードは通る: {got}")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        return 1 if self_test() else 0
    bad: list[str] = []
    for name in _MODULES:
        bad += check_source((_DIR / name).read_text(encoding="utf-8"), name)
    if bad:
        print(f"=== 契約の違反 {len(bad)} 件 ===")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"=== 契約は満たされている（見た module {len(_MODULES)}）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
