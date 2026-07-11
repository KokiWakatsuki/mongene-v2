"""構造シグネチャ・計算指紋・dup_key（実装設計 §4.4）— H2 の実体。

- `fingerprint(mr)` = MR から機械導出する計算指紋 fp。steps は独立ソルバ由来なので
  recipe 側で偽装しにくい。「別名の署名を貼った実質同一構造」を可視化する接地点。
- `dup_key(mr)` = signature + 正規化 params のハッシュ。重複（F-3/D-1）測定に使う。
  context_slots（variant B の題材差）は算入しない。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from engine.core.contracts import MR


def fingerprint(mr: MR) -> tuple[Any, ...]:
    """計算指紋 fp = (given/asked の型ベクトル, steps の op 列, 小問数)。

    - given の型ベクトル: given キーの並び（型に相当する frame 語彙）。
    - asked の型ベクトル: 各小問の asked を連結。
    - steps の op 列: 各小問の steps の op を連結。
    - 小問数。
    """
    given_types = tuple(sorted(mr.given.keys()))
    asked_vec = tuple(sq.asked for sq in mr.sub_questions)
    op_seq = tuple(tuple(s.op for s in sq.steps) for sq in mr.sub_questions)
    return (given_types, asked_vec, op_seq, len(mr.sub_questions))


def fingerprint_hash(mr: MR) -> str:
    return hashlib.sha256(repr(fingerprint(mr)).encode()).hexdigest()[:16]


def _normalize_scalar(v: Any) -> Any:
    """正規化の既定実装。recipe が params の正規形を別途定義する場合はそちらが勝つ。"""
    # sympy オブジェクトは srepr で正規化
    try:
        import sympy
        if isinstance(v, sympy.Basic):
            return sympy.srepr(v)
    except Exception:  # pragma: no cover
        pass
    if isinstance(v, (list, tuple)):
        return [_normalize_scalar(x) for x in v]
    if isinstance(v, dict):
        return {k: _normalize_scalar(v[k]) for k in sorted(v)}
    return v


def normalize_params(params: dict[str, Any]) -> str:
    """params の正規形を JSON 文字列で返す（順序を確定）。"""
    norm = {k: _normalize_scalar(params[k]) for k in sorted(params)}
    return json.dumps(norm, ensure_ascii=False, sort_keys=True, default=str)


def dup_key(mr: MR) -> str:
    """dup_key = sha256(signature + normalize(params))。context_slots は算入しない。"""
    payload = mr.signature + "|" + normalize_params(mr.params)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


__all__ = ["fingerprint", "fingerprint_hash", "normalize_params", "dup_key"]
