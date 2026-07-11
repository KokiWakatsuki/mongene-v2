"""乱数規律とドメイン記法（H8 / 実装設計 §4.3.1・§5.3）。

- `derive_rng(family, level, purpose, seed)` 以外の乱数源は全リポジトリで禁止
  （ruff カスタムルールで検査）。`issue_seed()` は登録された唯一の例外。
- recipe は `draw` / `draw_many` 以外でドメイン記法を解釈してはならない。

ドメイン記法 v1（閉じた語彙）:
    {int_range: [a, b]}                      a..b の一様整数（両端含む）
    {int_set: [v, ...]}                      集合からの一様選択
    {frac_range: {num: [a,b], den: [c,d]}}   既約分数 num/den（den∉{0,±1}）
    {lattice: {x: <domain>, y: <domain>}}    格子点
  修飾子:
    exclude: [v, ...]                        生成値から除外
    distinct: [axis, ...]                    複数抽選時に当該軸の相異を保証
"""
from __future__ import annotations

import hashlib
import secrets
from math import gcd
from typing import Any

import sympy


class Rng:
    """SHA256 由来の決定論ストリーム。Python 標準 `random` を包む唯一の許可経路。

    直接 `random.Random` を使わず本クラス経由にすることで、乱数規律 ruff ルールが
    `random.` / `numpy.random.` の直接使用だけを禁止対象にできる。
    """

    __slots__ = ("_state", "_counter", "_label")

    def __init__(self, seed_bytes: bytes, label: str = "") -> None:
        self._state = seed_bytes
        self._counter = 0
        self._label = label

    def _next_u64(self) -> int:
        h = hashlib.sha256(self._state + self._counter.to_bytes(8, "big")).digest()
        self._counter += 1
        return int.from_bytes(h[:8], "big")

    def randint(self, lo: int, hi: int) -> int:
        """lo..hi の一様整数（両端含む）。"""
        if hi < lo:
            raise ValueError(f"randint: hi<lo ({lo}, {hi})")
        span = hi - lo + 1
        return lo + self._next_u64() % span

    def choice(self, seq: list[Any]) -> Any:
        if not seq:
            raise ValueError("choice: empty sequence")
        return seq[self._next_u64() % len(seq)]

    def spawn(self, k: int = 0) -> "Rng":
        """独立サブストリーム（有界リトライの attempt などに使う）。"""
        child = hashlib.sha256(self._state + b"|spawn|" + str(k).encode()).digest()
        return Rng(child, label=f"{self._label}/spawn{k}")


def derive_rng(family: str, level: int, purpose: str, seed: int) -> Rng:
    """セル×purpose×seed から独立な決定論ストリームを導出。

    purpose 込み（base と variant が同じ列を引かない）。
    """
    key = f"{family}|{level}|{purpose}|{seed}".encode()
    return Rng(hashlib.sha256(key).digest(), label=f"{family}@{level}/{purpose}#{seed}")


def issue_seed() -> int:
    """乱数禁止規律の登録された唯一の例外（OS エントロピー採番）。"""
    return secrets.randbelow(2**31)


# ---------------------------------------------------------------------------
# ドメイン記法 v1
# ---------------------------------------------------------------------------
_SCALAR_DOMAINS = {"int_range", "int_set", "frac_range", "lattice"}


class DomainError(ValueError):
    """ドメイン記法の spec / 生成エラー。"""


def _iter_int_range(spec: list[Any]) -> tuple[int, int]:
    if not (isinstance(spec, list) and len(spec) == 2):
        raise DomainError(f"int_range は [a, b] であること: {spec!r}")
    a, b = int(spec[0]), int(spec[1])
    if b < a:
        raise DomainError(f"int_range: a<=b であること: {spec!r}")
    return a, b


def validate_domain(spec: Any) -> None:
    """spec_lint R3 の実体。ドメイン記法として妥当か（生成せずに）検査。

    JSON スカラー・配列・登録済みドメイン記法のみを許す。違反は DomainError。
    """
    # スカラー・素の配列は許容（recipe が定数として使う）
    if isinstance(spec, (int, float, str, bool)):
        return
    if isinstance(spec, list):
        for v in spec:
            validate_domain(v)
        return
    if not isinstance(spec, dict):
        raise DomainError(f"未対応の spec 型: {type(spec)}")

    keys = set(spec.keys())
    modifiers = {"exclude", "distinct"}
    core_keys = keys - modifiers
    if len(core_keys) != 1:
        raise DomainError(f"ドメイン記法は主キー1つ（+修飾子）であること: {sorted(keys)}")
    (name,) = core_keys
    if name not in _SCALAR_DOMAINS:
        raise DomainError(f"未登録のドメイン語彙: {name!r}（core registry へ追加が必要）")

    if name == "int_range":
        _iter_int_range(spec["int_range"])
    elif name == "int_set":
        vs = spec["int_set"]
        if not (isinstance(vs, list) and vs):
            raise DomainError("int_set は非空配列であること")
    elif name == "frac_range":
        fr = spec["frac_range"]
        if not (isinstance(fr, dict) and "num" in fr and "den" in fr):
            raise DomainError("frac_range は {num, den} であること")
        _iter_int_range(fr["num"])
        c, d = _iter_int_range(fr["den"])
        if d < 1 or (c <= 1 and d <= 1):
            raise DomainError("frac_range: den は 2 以上を含む正の範囲であること（den∉{0,±1}）")
    elif name == "lattice":
        lat = spec["lattice"]
        if not (isinstance(lat, dict) and "x" in lat and "y" in lat):
            raise DomainError("lattice は {x, y} であること")
        validate_domain(lat["x"])
        validate_domain(lat["y"])

    # exclude で空集合にならないかは spec check（実生成）側で検査する。


def _apply_exclude(value: Any, exclude: list[Any]) -> bool:
    """value が exclude に該当するか。"""
    return any(value == e for e in exclude)


def draw(domain_spec: Any, rng: Rng) -> Any:
    """ドメイン記法から 1 値を抽選。recipe はこの API 以外でドメインを解釈してはならない。

    戻り値: int / sympy.Rational / tuple(格子点) など。
    """
    if isinstance(domain_spec, (int, float, str, bool)):
        return domain_spec
    if isinstance(domain_spec, list):
        # 素の配列は「集合からの一様選択」と解釈
        return rng.choice(list(domain_spec))
    if not isinstance(domain_spec, dict):
        raise DomainError(f"draw: 未対応 spec {type(domain_spec)}")

    exclude = list(domain_spec.get("exclude", []))
    core_keys = set(domain_spec.keys()) - {"exclude", "distinct"}
    (name,) = core_keys

    for _ in range(1000):
        if name == "int_range":
            a, b = _iter_int_range(domain_spec["int_range"])
            val: Any = rng.randint(a, b)
        elif name == "int_set":
            val = rng.choice(list(domain_spec["int_set"]))
        elif name == "frac_range":
            fr = domain_spec["frac_range"]
            na, nb = _iter_int_range(fr["num"])
            da, db = _iter_int_range(fr["den"])
            num = rng.randint(na, nb)
            den = rng.randint(max(da, 1), db)
            if den == 0:
                continue
            r = sympy.Rational(num, den)
            # 既約分数・den∉{0,±1}
            if r.q == 1:
                continue
            val = r
        elif name == "lattice":
            lat = domain_spec["lattice"]
            x = draw(_strip_axis_distinct(lat["x"]), rng)
            y = draw(_strip_axis_distinct(lat["y"]), rng)
            val = (x, y)
        else:
            raise DomainError(f"未登録のドメイン語彙: {name!r}")

        if exclude and _apply_exclude(val, exclude):
            continue
        return val
    raise DomainError(f"draw: exclude 後に候補が枯渇 {domain_spec!r}")


def _strip_axis_distinct(axis_spec: Any) -> Any:
    """lattice 軸内の distinct 修飾子は draw_many 側で扱うため除去。"""
    if isinstance(axis_spec, dict) and "distinct" in axis_spec:
        s = dict(axis_spec)
        s.pop("distinct")
        return s
    return axis_spec


def draw_many(domain_spec: Any, rng: Rng, k: int) -> list[Any]:
    """k 個抽選。distinct 修飾子があれば当該軸の値の相異を保証。

    - lattice の distinct:[x] → x 座標が相異する k 点。
    - 通常ドメインの distinct:[value] → 値そのものが相異。
    """
    distinct_axes: list[str] = []
    if isinstance(domain_spec, dict):
        distinct_axes = list(domain_spec.get("distinct", []))

    if not distinct_axes:
        return [draw(domain_spec, rng) for _ in range(k)]

    results: list[Any] = []
    seen: set[Any] = set()
    for _ in range(2000):
        if len(results) >= k:
            break
        v = draw(domain_spec, rng)
        key = _distinct_key(v, distinct_axes, domain_spec)
        if key in seen:
            continue
        seen.add(key)
        results.append(v)
    if len(results) < k:
        raise DomainError(f"draw_many: distinct を満たす {k} 個を確保できず: {domain_spec!r}")
    return results


def _distinct_key(value: Any, axes: list[str], domain_spec: dict[str, Any]) -> Any:
    """distinct 判定に使うキーを value から抽出。"""
    # lattice の場合、value は (x, y) tuple。axes に軸名（"x"/"y"）。
    if isinstance(domain_spec, dict) and "lattice" in domain_spec and isinstance(value, tuple):
        idx = {"x": 0, "y": 1}
        parts = tuple(value[idx[a]] for a in axes if a in idx)
        return parts if len(parts) > 1 else parts[0]
    # 通常ドメイン: 値そのもの
    return value


__all__ = [
    "Rng", "derive_rng", "issue_seed",
    "DomainError", "validate_domain", "draw", "draw_many",
]
