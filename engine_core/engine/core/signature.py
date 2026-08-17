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


# 表層＝**答えにも解き方にも効かない見た目だけの軸**。dup_key に算入しない。
#
# ここを算入していたので、**数値も場面も完全に同じで頂点名だけ違う問題を別物として
# 数えていた**（コーパスの実測で 26問 / 13組）。点名を params に入れたのは dup_rate を
# 下げるためだったが、下がったのは見かけの数字だけで、生徒には同じ問題が2回出る。
#
# **部分一致で外さない。** `scenario_kind`（問題の型）・`dim_labels`（['7cm','30πcm',…]
# ＝寸法）・`asked_label`（'少ない'＝答えの符号を決める）・`count_at_vertex` は名前に
# label/name を含むが**中身**なので、外すと逆に dup が跳ねる。実物のキーを全部
# 数えて（396種）分類した結果を、明示の集合として置く。
_SURFACE_PARAM_KEYS = frozenset({
    # 図形の点名
    "labels", "labels1", "labels2", "slots", "p_labels", "q_labels", "point_labels",
    "vertex", "vertex_labels", "vertex_labels_prime", "center_label",
    "base_name", "line_name", "transversal_name",
    "name_1", "name_2", "name_a", "name_b", "name_c", "name_h", "name_o", "name_p",
    "names",
    # 文字式・証明で使う文字
    "letters",
    # 人名・品物・色・見出し
    "person", "item_a", "item_b", "items",
    "subject_labels", "subject_caption", "answer_labels", "colors",
})


def dup_key(mr: MR) -> str:
    """dup_key = sha256(signature + normalize(表層を除いた params))。

    context_slots（variant B の題材差）も、表層の params（点名・人名・品物・色）も
    算入しない——どちらも「同じ問題かどうか」を変えないから。
    """
    core = {k: v for k, v in mr.params.items() if k not in _SURFACE_PARAM_KEYS}
    payload = mr.signature + "|" + normalize_params(core)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


__all__ = ["fingerprint", "fingerprint_hash", "normalize_params", "dup_key"]
