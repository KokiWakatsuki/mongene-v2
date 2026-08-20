"""G-SC1（契約）— 場面が読む名前が、ぜんぶ引かれているか。

作業1 で文章題は3層になった（Relation が数、宣言が語彙、Scene が日本語）。
層を分けると**新しい穴が1つ開く**: 場面文が `v["counter"]` と書いているのに
語彙の宣言にその名前が無い、という食い違い。生成すれば KeyError で落ちるが、
落ちるのは**その場面をたまたま引いた seed のときだけ**なので、
セルを1つ足したときに気づかないことがある。ここは静的に全部見る。

## 見るもの

  - 場面（`_scene_*`）が `v[...]` で読む名前が、語彙の宣言に全部あるか
  - 宣言してあるのに誰も読まない名前が無いか（消し忘れ・書き間違い）
  - 場面が `n[...]` で読む名前が、関係（`_relation_*`）の `numbers={...}` にあるか

## 宣言の形が2つある

  - **棚**（`SCENES` / `SCENE_SHELF`）: 場面ごとに `vocab` と `render` を隣に持つ。
    棚に移した module（`scenes.py`・`word_problem_quadratic.py`）はこちら
  - **関係で引く形**（`_SCENE_VOCAB` ＋ `SCENE_RENDERERS`）: まだ棚に移していない module

どちらの形も見る。**両方無いときだけ「読めない＝検査が動いていない疑い」を出す。**
見る file の一覧は `scene_shelves.py` から引く（★棚を足したとき走査対象に
入れ忘れる事故を防ぐ。作業3 で実際に `scenes.py` の6場面が外れていた）。

自分自身の検査を持つ（`--self-test`）。合成した違反コードで落ちることを確かめる
——0件を返す走査は、動いていないのと区別がつかない。

実行: .venv/bin/python records/work/check_scene_contract.py
"""
from __future__ import annotations

import ast
import sys
from collections.abc import Mapping
from typing import cast
from engine_paths import RECIPES_DIR  # エンジンの場所は1か所で解決する

_DIR = RECIPES_DIR

# 関係で引く形（`_SCENE_VOCAB` ＋ `SCENE_RENDERERS`）を持つ module。
_RELATION_MODULES = [
    "word_problem_linear.py",
    "word_problem_system.py",
    "word_problem_proportion_frequency.py",
    "word_problem_quadratic.py",
    "word_problem_expression.py",
]


def _modules() -> list[str]:
    """見る module。**棚のある file は `scene_shelves.py` から引く。**

    ★以前ここは上の並びを直に返していて、`scenes.py` が入っていなかった。
    作業3 で1元1次の6場面を棚へ移したとき、**その6場面が検査対象から
    外れたことに誰も気づかなかった**（`word_problem_linear.py` の残りが
    通るので「違反 0 件」と出る）。棚を足すたびに同じことが起きるので、
    棚の在り処は1か所（`scene_shelves.py`）から引く。
    """
    from scene_shelves import shelf_files  # noqa: PLC0415

    out = list(_RELATION_MODULES)
    for path in shelf_files():
        if path.name not in out:
            out.append(path.name)
    return out


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


def _shelf_declared(tree: ast.Module) -> dict[str, tuple[set[str], list[str]]]:
    """棚（`SCENES` / `SCENE_SHELF`）から {場面の名前: (出す語彙, 書き手の関数名)}。

    ★棚の形は関係で引く形（`_SCENE_VOCAB` ＋ `SCENE_RENDERERS`）と**鍵が違う**。
    棚は場面ごとに `vocab` と `render` を隣に持つので、対応づけが1か所で読める。

    ★この関数が無かったせいで、作業3 で `scenes.py` の棚へ移した6場面は
    **一度も語彙の契約を検査されていなかった**（走査対象に `scenes.py` が
    入っておらず、`word_problem_linear.py` 側は通るので「違反 0 件」と出ていた）。
    """
    out: dict[str, tuple[set[str], list[str]]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", None) not in ("SCENES", "SCENE_SHELF"):
            continue
        for call in getattr(node.value, "elts", []):
            if not isinstance(call, ast.Call):
                continue
            kw = {k.arg: k.value for k in call.keywords if k.arg}
            sid = kw.get("id")
            if not isinstance(sid, ast.Constant):
                continue
            # `vocab=(("one", _CANDIDATES, ("item", "counter")), ...)` の3つめ。
            names: set[str] = set()
            for step in getattr(kw.get("vocab"), "elts", []):
                elts = getattr(step, "elts", [])
                if len(elts) == 3:
                    names |= {
                        str(e.value) for e in getattr(elts[2], "elts", [])
                        if isinstance(e, ast.Constant)
                    }
            # `render={ROLES_X: _scene_x, ...}` の値が書き手、鍵が役割の型。
            render = kw.get("render")
            fns = [
                v.id for v in getattr(render, "values", []) if isinstance(v, ast.Name)
            ]
            roles = [
                k.id for k in getattr(render, "keys", []) if isinstance(k, ast.Name)
            ]
            out[str(sid.value)] = (names, fns, roles)
    return out


def _relations_by_roles(tree: ast.Module) -> dict[str, list[str]]:
    """`_RELATION_ROLES` から {役割の型の識別子: [関係の名前, ...]}。

    ★**語彙は場面だけでなく関係も読む。** 値段や速さの相場は語彙といっしょに
    1回で引かれて関係へ渡るので（`v["price"]` / `v["speed_lo"]`）、場面の書き手だけを
    見ると「宣言されているが誰も読まない」を誤って出す。
    関係で引く形の側には同じ注意書きが既にあった——**棚に移すときに同じ罠を踏んだ**
    （文字の式で5件出した）。棚のどの場面がどの関係と組むかは、役割の型で分かる。
    """
    out: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", None) != "_RELATION_ROLES":
            continue
        for k, v in zip(getattr(node.value, "keys", []),
                        getattr(node.value, "values", []), strict=False):
            if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                out.setdefault(v.id, []).append(str(k.value))
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


def _world(sources: Mapping[str, str]) -> dict[str, object]:
    """**module をまたいだ対応づけ**を1つに集める。

    ★棚は module をまたぐ。`word_problem_linear.py` の8関係はすべて
    `scenes.py` の棚から場面を引くので、**1ファイルだけ見ると対応づけが読めない**
    （実際に「棚 0 / 場面 0 / 関係 8」と出た。検査が黙って通らなかったのは正しい）。
    語彙の契約は「場面の書き手」と「その場面と組む関係」の両方を見ないと判定できない
    ので、ファイル単位をやめてプログラム全体で持つ。
    """
    rel_by_roles: dict[str, list[str]] = {}
    rel_fns: dict[str, ast.FunctionDef] = {}
    for label, src in sources.items():
        tree = ast.parse(src)
        fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        drawers = _dict_of_names(tree, "RELATION_DRAWERS")
        for role_id, kinds in _relations_by_roles(tree).items():
            rel_by_roles.setdefault(role_id, []).extend(kinds)
        for kind, fn_name in drawers.items():
            fn = fns.get(fn_name)
            if fn is not None:
                # ★同じ関係の名前が2つの module にあることがある
                # （`price_count_diff` は1元1次と連立の両方）。**上書きせず両方持つ**
                # ——片方だけ見ると、もう片方が読む語彙を「誰も読まない」と誤る。
                rel_fns.setdefault(f"{label}:{kind}", fn)
    return {"rel_by_roles": rel_by_roles, "rel_fns": rel_fns}


def check_source(src: str, label: str, world: Mapping[str, object] | None = None) -> list[str]:
    """1 module を見る。返すのは違反の並び（空なら合格）。

    `world` があれば、棚の場面と組む関係を**module をまたいで**探す
    （無ければその file の中だけ＝自己検査の合成データ用）。
    """
    tree = ast.parse(src)
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    scenes = _dict_of_names(tree, "SCENE_RENDERERS")
    relations = _dict_of_names(tree, "RELATION_DRAWERS")
    declared = _vocab_declared(tree)
    shelf = _shelf_declared(tree)
    bad: list[str] = []

    # --- 棚の形（場面ごとに vocab と render が隣にある）------------------------
    if world is not None:
        rel_by_roles = cast("dict[str, list[str]]", world["rel_by_roles"])
        world_fns = cast("dict[str, ast.FunctionDef]", world["rel_fns"])
    else:
        rel_by_roles = _relations_by_roles(tree)
        world_fns = {}
    for sid, (given, fn_names, roles) in sorted(shelf.items()):
        if not fn_names:
            bad.append(f"{label}: 場面 {sid} に書き手が無い（render が空）")
            continue
        read_v: set[str] = set()
        for fn_name in fn_names:
            fn = fns.get(fn_name)
            if fn is None:
                bad.append(f"{label}: 場面 {sid} の書き手 {fn_name} が見つからない")
                continue
            read_v |= _subscripts(fn, "v")
        # ★その場面と組む関係が読む語彙も数える（相場は語彙と1回で引かれる）。
        for role_id in roles:
            for kind in rel_by_roles.get(role_id, []):
                rel_fn = fns.get(relations.get(kind, ""))
                if rel_fn is None:
                    # 別の module にある関係（棚は module をまたぐ）。
                    for key, fn2 in world_fns.items():
                        if key.endswith(f":{kind}"):
                            read_v |= _subscripts(fn2, "v")
                else:
                    read_v |= _subscripts(rel_fn, "v")
        for miss in sorted(read_v - given):
            bad.append(f"{label}: 場面 {sid} が語彙 {miss!r} を読むが、宣言に無い")
        for unused in sorted(given - read_v - {"_"}):
            bad.append(f"{label}: 場面 {sid} の語彙 {unused!r} は宣言されているが誰も読まない")
        # ★場面が `n[...]` で読む数が、組む関係の `numbers` に在るか。
        # **この検査は棚の形では効いていなかった**（関係で引く形にしか無かった）。
        # 棚に移すたびに 33 場面ぶんの穴が広がっていた——生成すれば KeyError で
        # 落ちるが、落ちるのは**その場面をたまたま引いた seed のとき**だけ。
        rel_numbers: set[str] = set()
        seen_rel = False
        for role_id in roles:
            for kind in rel_by_roles.get(role_id, []):
                rel_fn = fns.get(relations.get(kind, ""))
                if rel_fn is None:
                    for key, fn2 in world_fns.items():
                        if key.endswith(f":{kind}"):
                            rel_numbers |= _numbers_keys(fn2)
                            seen_rel = True
                else:
                    rel_numbers |= _numbers_keys(rel_fn)
                    seen_rel = True
        if seen_rel:
            read_n: set[str] = set()
            for fn_name in fn_names:
                fn = fns.get(fn_name)
                if fn is not None:
                    read_n |= _subscripts(fn, "n")
            for miss in sorted(read_n - rel_numbers):
                bad.append(f"{label}: 場面 {sid} が数 {miss!r} を読むが、"
                           f"組む関係が出していない")

    # --- 関係で引く形（棚に移していない module）-------------------------------
    # ★3通りのどれかで覆われていればよい。
    #   ① 自分の file に棚がある（`scenes.py` / 各 module の `SCENE_SHELF`）
    #   ② 関係で引く形を持っている（`SCENE_RENDERERS` ＋ `RELATION_DRAWERS`）
    #   ③ 関係を持ち、その関係が**別 file の棚に配線されている**
    #      （`word_problem_linear.py` の8関係は `scenes.py` の棚から引く）
    # どれでもないときだけ「読めない」＝**検査が動いていない疑い**を出す。
    wired = bool(relations) and any(
        kind in kinds for kinds in rel_by_roles.values() for kind in relations
    )
    if not shelf and not (scenes and relations) and not wired:
        return [f"{label}: 対応づけが読めない"
                f"（棚 {len(shelf)} / 場面 {len(scenes)} / 関係 {len(relations)}）"
                "＝検査が動いていない疑い"]
    if not scenes or not relations:
        return bad
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


# --- 棚の形（`SCENES` / `SCENE_SHELF`）------------------------------------
# ★棚の形は鍵が「場面の名前」なので、関係で引く形とは別に試す必要がある。
# 棚を読めるようにした直後、**実物の走査は 0 件を返した**——通ったのではなく
# 棚を1つも読んでいなかった、という可能性を消せないので、ここで押さえる。
_SHELF_BAD_MISSING = '''
def _scene_x(n, v):
    return S(f"{v['item']}を{v['counter']}買う")
SCENES = (
    SceneSpec(id="x", vocab=(("one", CANDS, ("item",)),), render={ROLES: _scene_x}),
)
'''
_SHELF_BAD_UNUSED = '''
def _scene_x(n, v):
    return S(f"{v['item']}を買う")
SCENES = (
    SceneSpec(id="x", vocab=(("one", CANDS, ("item", "counter")),), render={ROLES: _scene_x}),
)
'''
_SHELF_NO_WRITER = '''
SCENES = (
    SceneSpec(id="x", vocab=(), render={}),
)
'''
_SHELF_LOST_WRITER = '''
SCENES = (
    SceneSpec(id="x", vocab=(), render={ROLES: _scene_missing}),
)
'''
_SHELF_GOOD = '''
def _scene_x(n, v):
    return S(f"{v['item']}を{v['counter']}買う")
SCENES = (
    SceneSpec(id="x", vocab=(("one", CANDS, ("item", "counter")),), render={ROLES: _scene_x}),
)
'''


# ★棚の形で「場面が読む数」を見ているかの合成データ。
# 関係で引く形にはこの検査があったのに、棚の形には無かった（33場面ぶんの穴）。
_SHELF_BAD_NUMBER = '''
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{n['total']}個買う")
RELATION_DRAWERS = {"x": _relation_x}
_RELATION_ROLES = {"x": ROLES}
SCENES = (
    SceneSpec(id="x", vocab=(), render={ROLES: _scene_x}),
)
'''
_SHELF_GOOD_NUMBER = '''
def _relation_x(p, rng):
    return R(numbers={"price": 1})
def _scene_x(n, v):
    return S(f"{n['price']}円")
RELATION_DRAWERS = {"x": _relation_x}
_RELATION_ROLES = {"x": ROLES}
SCENES = (
    SceneSpec(id="x", vocab=(), render={ROLES: _scene_x}),
)
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

    for name, src, want in [
        ("宣言に無い語彙を読む", _SHELF_BAD_MISSING, "宣言に無い"),
        ("誰も読まない語彙", _SHELF_BAD_UNUSED, "誰も読まない"),
        ("書き手が無い（render が空）", _SHELF_NO_WRITER, "書き手が無い"),
        ("書き手が見つからない", _SHELF_LOST_WRITER, "見つからない"),
    ]:
        got = check_source(src, "synthetic")
        ok = any(want in g for g in got)
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}棚「{name}」で落ちる: {got}")
    got = check_source(_SHELF_GOOD, "synthetic")
    ok = got == []
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}正しい棚は通る: {got}")

    got = check_source(_SHELF_BAD_NUMBER, "synthetic")
    ok = any("組む関係が出していない" in g for g in got)
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}棚「関係が出していない数を読む」で落ちる: {got}")
    got = check_source(_SHELF_GOOD_NUMBER, "synthetic")
    ok = got == []
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}棚「関係が出している数を読む」は通る: {got}")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        return 1 if self_test() else 0
    bad: list[str] = []
    modules = _modules()
    sources = {name: (_DIR / name).read_text(encoding="utf-8") for name in modules}
    # ★棚は module をまたぐので、対応づけは全体で持つ（`_world` の説明を見る）。
    world = _world(sources)
    for name in modules:
        bad += check_source(sources[name], name, world)
    if bad:
        print(f"=== 契約の違反 {len(bad)} 件 ===")
        for b in bad:
            print(f"  {b}")
        return 1
    print(f"=== 契約は満たされている（見た module {len(modules)}: "
          f"{', '.join(modules)}）===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
