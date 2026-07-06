"""G6 難易度レベル健全性 (difficulty_level_soundness)

spec `docs/phase2_eval_gates_spec.md` §3-G6（2026-07-06 改訂版）:

現行仕様は離散 Lv 制（`mapping.json.difficulty_levels[form]` に Lv1..LvN を定義し、
`target_level` で `/inspect` 生成する）。min/mid/max という連続値の合成スコア単調性検査は
測定軸が誤りだったため廃止した（旧 `g6_difficulty_monotonicity.py` を置換）。

正しい LLM フリー判定は target_level 軸で以下の2つ:

- **G6-b レベル非崩壊 (distinctness)**: 同一 (lesson, form) の Lv 定義が互いに異なるか。
  生成不要・`mapping.json` の静的データだけで判定できる。
  シグネチャ = `{atom_constraints, blueprint_override, verb_config}` を JSON 正規化して比較し、
  重複があれば FAIL。
- **G6-a 制約適合 (conformance)**: 各 (lesson, form, Lv) を `target_level=Lv` で複数 seed 生成し、
  Lv の宣言した atom_constraints（ベース設定へシャローマージ後）が実際に生成物へ反映されているか。
  観測可能な制約（allow_negative / max_value / force_fraction 等）だけを検査し、
  観測不能な制約は N/A とする（偽 FAIL を出さない）。

意味的順序（Lv4 が本当に Lv1 より難しいか）は決定論では判定不能なため、このゲートでは扱わない
（LLM/人手のマイルストーン点検に隔離。spec §3-G6 末尾 / 設計書 §12 Phase5）。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from scripts.eval_gates.common import GateResult

GATE_ID = "G6"

# blueprint_runner.py の _merge_constraints と同じマージ規則をここでも使う。
# ランナー実装から直接 import することで「実挙動に合わせる」（spec §3-G6-a）を保証する。
try:
    from apps.api.src.core.runner.blueprint_runner import _merge_constraints as merge_atom_constraints
except Exception:  # pragma: no cover - import 環境差異のフォールバック
    def merge_atom_constraints(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = {k: dict(v) for k, v in (base or {}).items()}
        for atom_class, params in (patch or {}).items():
            if not isinstance(params, dict):
                for ac_dict in merged.values():
                    ac_dict[atom_class] = params
                continue
            if atom_class in merged:
                merged[atom_class].update(params)
            else:
                merged[atom_class] = dict(params)
        return merged


# ---------------------------------------------------------------------------
# G6-b: レベル非崩壊 (distinctness) — 生成不要・静的データ解析
# ---------------------------------------------------------------------------


def compute_level_signature(lv_def: dict[str, Any]) -> str:
    """Lv 定義のシグネチャを算出する。

    シグネチャ = {atom_constraints, blueprint_override, verb_config} をJSON正規化。
    `description` や `blueprint_params`（例: g1_l44 の knowledge_hint 文言違いのみで
    Lv を分けているケース）は**意図的に含めない**。これらは Blueprint/Atom/Verb の実制約を
    変えないため、同一シグネチャ＝実質的に同じ問題しか生成できない、という判定が spec の意図。
    """
    payload = {
        "atom_constraints": lv_def.get("atom_constraints") or {},
        "blueprint_override": lv_def.get("blueprint_override"),
        "verb_config": lv_def.get("verb_config") or {},
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def check_distinctness(
    lesson_id: str,
    form: str,
    level_defs: list[dict[str, Any]],
) -> GateResult:
    """同一 (lesson, form) の Lv 定義群が互いに異なるシグネチャを持つか判定する。

    重複シグネチャの Lv があれば FAIL（崩壊した Lv 番号を列挙）。
    Lv が1個以下の場合は判定不能として N/A。
    """
    if not level_defs:
        return GateResult(GATE_ID, "N/A", f"{lesson_id}/{form}: difficulty_levels が未定義")
    if len(level_defs) < 2:
        return GateResult(
            GATE_ID,
            "N/A",
            f"{lesson_id}/{form}: Lv が1個のみのため非崩壊判定は不要",
            details={"levels": [lv.get("lv") for lv in level_defs]},
        )

    sig_to_levels: dict[str, list[int]] = {}
    for lv_def in level_defs:
        sig = compute_level_signature(lv_def)
        sig_to_levels.setdefault(sig, []).append(lv_def.get("lv"))

    collapsed_groups = [lvs for lvs in sig_to_levels.values() if len(lvs) > 1]

    if collapsed_groups:
        total_levels = len(level_defs)
        distinct_sigs = len(sig_to_levels)
        groups_desc = "; ".join(
            "Lv" + "=Lv".join(str(lv) for lv in sorted(group)) for group in collapsed_groups
        )
        return GateResult(
            GATE_ID,
            "FAIL",
            f"{lesson_id}/{form}: レベル定義が崩壊 ({total_levels}Lv定義中 {distinct_sigs} 種類のみ区別可能)。"
            f" 重複グループ: {groups_desc}",
            details={
                "total_levels": total_levels,
                "distinct_signatures": distinct_sigs,
                "collapsed_groups": collapsed_groups,
            },
        )

    return GateResult(
        GATE_ID,
        "PASS",
        f"{lesson_id}/{form}: 全 {len(level_defs)} Lv が相異なる設定を持つ",
        details={"total_levels": len(level_defs)},
    )


# ---------------------------------------------------------------------------
# G6-a: 制約適合 (conformance) — 生成あり・LLMフリー（/inspect 複数seed）
# ---------------------------------------------------------------------------


def _iter_operand_tokens(sample: dict[str, Any]) -> list[str]:
    """ground truth (inspect結果) からオペランドの文字列トークンを全て集める。"""
    tokens: list[str] = []
    for sq in sample.get("sub_questions", []) or []:
        for step in sq.get("logic_steps", []) or []:
            for operand in step.get("operands", []) or []:
                tokens.append(str(operand))
    return tokens


def _to_float(token: str) -> Optional[float]:
    try:
        if "/" in token:
            num, den = token.split("/", 1)
            return float(num) / float(den)
        return float(token)
    except (ValueError, ZeroDivisionError):
        return None


def _check_allow_negative_false(samples: list[dict[str, Any]]) -> Optional[str]:
    """allow_negative=false のとき、全サンプルで負のオペランドが出ないか。違反があれば理由文字列を返す。"""
    for idx, sample in enumerate(samples):
        for tok in _iter_operand_tokens(sample):
            val = _to_float(tok)
            if val is not None and val < 0:
                return f"allow_negative=false 宣言だが seed#{idx} で負のオペランド {tok!r} が出現"
    return None


def _check_max_value(samples: list[dict[str, Any]], max_value: float) -> Optional[str]:
    for idx, sample in enumerate(samples):
        for tok in _iter_operand_tokens(sample):
            val = _to_float(tok)
            if val is not None and abs(val) > max_value + 1e-9:
                return (
                    f"max_value={max_value} 宣言だが seed#{idx} で絶対値 {abs(val)} "
                    f"(オペランド {tok!r}) が上限超過"
                )
    return None


def _check_max_terms(samples: list[dict[str, Any]], max_terms: int) -> Optional[str]:
    for idx, sample in enumerate(samples):
        for sq in sample.get("sub_questions", []) or []:
            for step in sq.get("logic_steps", []) or []:
                n_terms = len(step.get("operands", []) or [])
                if n_terms > max_terms:
                    return (
                        f"max_terms={max_terms} 宣言だが seed#{idx} で項数 {n_terms} "
                        "が上限超過"
                    )
    return None


def _check_force_fraction_true(samples: list[dict[str, Any]]) -> Optional[str]:
    """force_fraction=true のとき、少なくとも1サンプルで分数が現れるか。

    全サンプル中に一度も分数が出なければ違反（制約がランナーに効いていない）。
    """
    for sample in samples:
        for tok in _iter_operand_tokens(sample):
            if "/" in tok:
                return None
        # answer 側にも分数が現れうる（オペランドではなく計算結果として）
        for sq in sample.get("sub_questions", []) or []:
            answer = sq.get("answer") or {}
            for key in ("sympy_form", "text_form"):
                v = answer.get(key)
                if v is not None and "/" in str(v):
                    return None
    return "force_fraction=true 宣言だが全サンプルを通じて分数が一度も出現しなかった"


# 観測可能な制約チェッカーの登録。ここに無いパラメータは N/A（観測不能）として扱う。
_OBSERVABLE_CHECKERS = {
    "allow_negative": lambda samples, value: (
        _check_allow_negative_false(samples) if value is False else None
    ),
    "max_value": lambda samples, value: _check_max_value(samples, value),
    "max_terms": lambda samples, value: _check_max_terms(samples, value),
    "force_fraction": lambda samples, value: (
        _check_force_fraction_true(samples) if value is True else None
    ),
}


def _flatten_expected_constraints(merged_constraints: dict[str, Any]) -> dict[str, Any]:
    """{AtomClass: {param: value}} 形式を {param: value} にフラット化する。

    複数 Atom クラスに同名パラメータが異なる値で宣言されるケースは稀だが、
    その場合は最初に見つかった値を採用する（ベストエフォート）。
    """
    flat: dict[str, Any] = {}
    for _atom_class, params in (merged_constraints or {}).items():
        if not isinstance(params, dict):
            continue
        for k, v in params.items():
            flat.setdefault(k, v)
    return flat


def check_conformance(
    lesson_id: str,
    form: str,
    lv: int,
    lv_def: dict[str, Any],
    base_atom_constraints: dict[str, Any],
    samples: list[dict[str, Any]],
) -> GateResult:
    """target_level=lv で複数 seed 生成したサンプル群が宣言制約を満たすか判定する。

    - 期待制約 = base_atom_constraints に lv_def["atom_constraints"] をシャローマージしたもの
      （blueprint_runner._merge_constraints と同じ規則）。
    - 観測可能な制約のみ判定。観測不能なパラメータは無視（N/A 扱いで偽FAILを避ける）。
    - samples が空（生成失敗等）の場合は N/A。
    """
    if not samples:
        return GateResult(
            GATE_ID,
            "N/A",
            f"{lesson_id}/{form}/Lv{lv}: 生成サンプルが無いため判定不能",
        )

    merged = merge_atom_constraints(base_atom_constraints or {}, lv_def.get("atom_constraints") or {})
    flat_expected = _flatten_expected_constraints(merged)

    violations: list[str] = []
    checked_params: list[str] = []
    for param, value in flat_expected.items():
        checker = _OBSERVABLE_CHECKERS.get(param)
        if checker is None:
            continue  # 観測不能なパラメータ（N/A 対象）
        checked_params.append(param)
        reason = checker(samples, value)
        if reason:
            violations.append(reason)

    if not checked_params:
        return GateResult(
            GATE_ID,
            "N/A",
            f"{lesson_id}/{form}/Lv{lv}: 宣言制約に観測可能なパラメータが無い"
            f"（宣言: {sorted(flat_expected.keys())}）",
            details={"declared_params": sorted(flat_expected.keys())},
        )

    if violations:
        return GateResult(
            GATE_ID,
            "FAIL",
            f"{lesson_id}/{form}/Lv{lv}: 制約違反 " + " / ".join(violations),
            details={"checked_params": checked_params, "violations": violations},
        )

    return GateResult(
        GATE_ID,
        "PASS",
        f"{lesson_id}/{form}/Lv{lv}: 観測可能な制約 {checked_params} を全サンプルで充足",
        details={"checked_params": checked_params, "n_samples": len(samples)},
    )


def check(product: Optional[dict[str, Any]], ground_truth: dict[str, Any]) -> GateResult:
    """§2a の共通契約 `check(product, ground_truth) -> GateResult` に合わせたラッパー。

    G6 は本質的に「1問」を判定する他ゲートと形が異なる（G6-b は Lv 定義群、G6-a は複数サンプル）
    ため、`check_distinctness` / `check_conformance` を直接呼ぶことを推奨する。
    このラッパーは他ゲートと同じ規約で誤って呼ばれた場合の N/A フォールバックとして用意する。
    """
    return GateResult(
        GATE_ID,
        "N/A",
        "G6 は check_distinctness（Lv定義群）または check_conformance（複数seedサンプル）"
        " を直接呼ぶこと。単一 product/ground_truth のペアでは判定できない。",
    )
