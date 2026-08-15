"""G6 難易度レベル健全性 (difficulty_level_soundness)

spec `docs/phase2_eval_gates_spec.md` §3-G6（2026-07-06 生成ベース再改訂版）:

現行仕様は離散 Lv 制（`mapping.json.difficulty_levels[form]` に Lv1..LvN を定義し、
`target_level` で `/inspect` 生成する）。min/mid/max という連続値の合成スコア単調性検査は
測定軸が誤りだったため廃止した（旧 `g6_difficulty_monotonicity.py` を置換）。

正しい LLM フリー判定は target_level 軸で以下の2つ:

- **G6-b レベル非崩壊 (distinctness)**: 同一 (lesson, form) の Lv 定義が互いに異なる問題を
  生成するか。**生成ベース**判定（2026-07-06 再設計。旧版は静的シグネチャのみで判定しており、
  knowledge/construction 系（差異が `blueprint_params.knowledge_hint` や `construction_type` 等、
  静的シグネチャに含めていないフィールドにしか現れない）を偽陽性で崩壊扱いしていた）。
  - 効率のため「静的シグネチャが同一の Lv ペア」を崩壊候補としてプレフィルタする
    （`compute_level_signature` を流用）。
  - 候補ペアについて、各 Lv を `target_level=Lv` で M 回 `/inspect` 生成し（LLMフリー）、
    各サンプルから**生成内容フィンガープリント**（`build_generation_fingerprint`）を作る。
  - 両 Lv のフィンガープリント集合が完全一致（M 回生成しても一度も区別できない）なら FAIL。
    集合が異なれば（knowledge_hint 文言違い等）静的シグネチャが同一でも PASS。
  - 静的シグネチャが最初から異なる Lv ペアは生成を待たずに PASS 扱い（プレフィルタで除外）。
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


def _static_signature_groups(level_defs: list[dict[str, Any]]) -> dict[str, list[int]]:
    """静的シグネチャが一致する Lv 番号をグルーピングする（プレフィルタ用）。"""
    sig_to_levels: dict[str, list[int]] = {}
    for lv_def in level_defs:
        sig = compute_level_signature(lv_def)
        sig_to_levels.setdefault(sig, []).append(lv_def.get("lv"))
    return sig_to_levels


# ---------------------------------------------------------------------------
# 生成内容フィンガープリント（G6-b 生成ベース判定の核）
# ---------------------------------------------------------------------------


def _is_numeric_token(token: Any) -> bool:
    return _to_float(str(token)) is not None


def build_generation_fingerprint(sample: dict[str, Any]) -> tuple:
    """`/inspect` の1サンプルから、問題文に現れる差異を表す不変フィンガープリントを作る。

    静的 config（atom_constraints 等）ではなく**実際に生成された内容**から作るのが肝。
    含める要素（すべて Lv/Blueprint/Atom/Verb の宣言に由来し、seed 乱数では変わらないもの）:
    - answer.type（knowledge/proof/numeric 等の答えの種別）
    - 各 logic_step の operation_name
    - 各 logic_step の**数値でない** operand（construction_type・証明対象の図形種別ラベル等の
      固定文字列。knowledge_hint 文言はここか narration_hint に verbatim で乗る）
    - 各 logic_step の operand 個数（項数。max_terms 等 Lv 宣言で変わりうる構造情報）
    - narration_hint（knowledge_hint 本文や作図手順の説明文などの固定文言が乗る）

    **意図的に除外**するもの: 数値オペランドの具体値・符号・答えの数値（text_form の数値部分）。
    これらは同じ Lv 内でも seed ごとの乱数で決まり、M回のサンプリングでは分布の全体像を
    観測しきれない（=たまたま重ならないだけで「区別できた」と誤判定する偽PASSの原因になる）。
    Lv 間の数値制約差（allow_negative/max_value 等）の適否は G6-a（conformance）の管轄であり、
    G6-b は「問題の型・文言が Lv ごとに変わるか」だけを見る。これにより、乱数使用済みの
    真の崩壊（例: g1_l33 の全Lv同一乱数加算）は M 回生成しても常に同一フィンガープリントに
    収束し FAIL、knowledge_hint/construction_type の文言差は毎回のサンプルに verbatim で
    含まれるため必ず PASS になる。
    """
    sq_prints: list[tuple] = []
    for sq in sample.get("sub_questions", []) or []:
        answer = sq.get("answer") or {}
        step_prints: list[tuple] = []
        for step in sq.get("logic_steps", []) or []:
            operands = step.get("operands", []) or []
            non_numeric = tuple(str(op) for op in operands if not _is_numeric_token(op))
            step_prints.append(
                (
                    step.get("operation_name"),
                    len(operands),
                    non_numeric,
                    str(step.get("narration_hint") or ""),
                )
            )
        sq_prints.append(
            (
                answer.get("type"),
                tuple(step_prints),
            )
        )
    return tuple(sq_prints)


def _fingerprint_set(
    lesson_id: str,
    form: str,
    lv: int,
    sample_fn: Any,
    n_samples: int,
) -> Optional[frozenset]:
    """target_level=lv で n_samples 回生成し、フィンガープリントの集合を作る。

    生成が1件も成功しなければ None（判定不能）を返す。一部失敗は無視して続行する
    （NoCompatibleBlueprintError 等、能力ギャップは G6-a/生成失敗集計側の関心事のため）。
    """
    prints: set[tuple] = set()
    n_ok = 0
    for _ in range(n_samples):
        try:
            sample = sample_fn(lesson_id, form, lv)
        except Exception:  # noqa: BLE001 - 生成失敗は無視して続行（精度優先）
            continue
        if sample is None:
            continue
        n_ok += 1
        prints.add(build_generation_fingerprint(sample))
    if n_ok == 0:
        return None
    return frozenset(prints)


def check_distinctness(
    lesson_id: str,
    form: str,
    level_defs: list[dict[str, Any]],
    sample_fn: Optional[Any] = None,
    n_samples: int = 6,
) -> GateResult:
    """同一 (lesson, form) の Lv 定義群が互いに異なる問題を生成するか判定する（生成ベース）。

    - `sample_fn` が None の場合: 生成器が無い環境向けのフォールバックとして、静的シグネチャの
      重複のみで判定する（後方互換・単体テストの一部で使用）。
    - `sample_fn(lesson_id, form, lv) -> ground_truth_dict` が渡された場合:
      1) 静的シグネチャが同一の Lv をプレフィルタで候補ペアとしてグルーピング。
      2) 候補グループについてのみ、各 Lv を n_samples 回 `/inspect` 相当で生成し、
         フィンガープリント集合を作る。
      3) 集合が完全一致（=生成しても一度も区別できない）なら FAIL。
         集合が異なれば（静的シグネチャは同じでも実際は区別可能）PASS 扱いでそのグループは除外。
      4) 生成が全滅（None）した Lv を含むグループは判定不能として除外（偽 FAIL を避ける）。

    Lv が1個以下、または difficulty_levels 未定義の場合は N/A。
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

    sig_to_levels = _static_signature_groups(level_defs)
    candidate_groups = [lvs for lvs in sig_to_levels.values() if len(lvs) > 1]

    if not candidate_groups:
        return GateResult(
            GATE_ID,
            "PASS",
            f"{lesson_id}/{form}: 全 {len(level_defs)} Lv が静的シグネチャの時点で相異なる",
            details={"total_levels": len(level_defs)},
        )

    if sample_fn is None:
        # フォールバック: 生成器が渡されない場合は静的シグネチャの重複のみで判定する。
        total_levels = len(level_defs)
        distinct_sigs = len(sig_to_levels)
        groups_desc = "; ".join(
            "Lv" + "=Lv".join(str(lv) for lv in sorted(group)) for group in candidate_groups
        )
        return GateResult(
            GATE_ID,
            "FAIL",
            f"{lesson_id}/{form}: レベル定義が崩壊 ({total_levels}Lv定義中 {distinct_sigs} 種類のみ区別可能、"
            "静的シグネチャのみで判定・生成未実施)。"
            f" 重複グループ: {groups_desc}",
            details={
                "total_levels": total_levels,
                "distinct_signatures": distinct_sigs,
                "collapsed_groups": candidate_groups,
                "mode": "static_only",
            },
        )

    # --- 生成ベース判定 ---
    fp_cache: dict[int, Optional[frozenset]] = {}

    def _get_fp(lv: int) -> Optional[frozenset]:
        if lv not in fp_cache:
            fp_cache[lv] = _fingerprint_set(lesson_id, form, lv, sample_fn, n_samples)
        return fp_cache[lv]

    truly_collapsed_groups: list[list[int]] = []
    inconclusive_groups: list[list[int]] = []

    for group in candidate_groups:
        fps = {lv: _get_fp(lv) for lv in group}
        if any(fp is None for fp in fps.values()):
            # いずれかの Lv が1件も生成できなかった → 判定不能（偽FAILを避けるため除外）
            inconclusive_groups.append(sorted(group))
            continue
        distinct_fp_values = {fp for fp in fps.values()}
        if len(distinct_fp_values) == 1:
            # 全 Lv のフィンガープリント集合が完全一致 = 生成しても区別できない = 真の崩壊
            truly_collapsed_groups.append(sorted(group))

    if truly_collapsed_groups:
        total_levels = len(level_defs)
        groups_desc = "; ".join(
            "Lv" + "=Lv".join(str(lv) for lv in group) for group in truly_collapsed_groups
        )
        detail: dict[str, Any] = {
            "total_levels": total_levels,
            "collapsed_groups": truly_collapsed_groups,
            "mode": "generation_based",
            "n_samples": n_samples,
        }
        if inconclusive_groups:
            detail["inconclusive_groups"] = inconclusive_groups
        return GateResult(
            GATE_ID,
            "FAIL",
            f"{lesson_id}/{form}: レベル定義が崩壊 ({n_samples}回生成しても区別不能な Lv 群あり)。"
            f" 崩壊グループ: {groups_desc}",
            details=detail,
        )

    note = ""
    if inconclusive_groups:
        groups_desc = "; ".join(
            "Lv" + "=Lv".join(str(lv) for lv in group) for group in inconclusive_groups
        )
        note = f"（判定不能グループあり・生成失敗のため除外: {groups_desc}）"

    return GateResult(
        GATE_ID,
        "PASS",
        f"{lesson_id}/{form}: 静的シグネチャ重複候補は生成内容で区別可能{note}",
        details={
            "total_levels": len(level_defs),
            "mode": "generation_based",
            "n_samples": n_samples,
            "inconclusive_groups": inconclusive_groups,
        },
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
