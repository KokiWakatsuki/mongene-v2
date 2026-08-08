"""F-5（未対応座標の明示拒否・現行最大の欠陥）の完全被覆 — 実エンジンで全コード発火。

要件 F-5: 供給できない座標は理由コード付きで拒否し、**受理して別種の問題を返すことを
禁止**（別形式・別題材の問題が返るケース0件）。M0 DoD の MUST。

`bootstrap()` 後の実 curriculum/families で各 Unsupported コードを発火させ、
いずれも Problem ではなく Unsupported を返す（＝別種を返さない）ことを固定する。

M0 スコープ外のコード:
- `verification_exhausted`: ゲート全滅（test_generate_end_to_end.py がダミーゲートで固定）。
- `supply_exhausted`: variant/avoid の再抽選枯渇（機構は M1・§5.3）。
"""
from __future__ import annotations

import pytest

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateOptions, GenerateRequest, Problem, Unsupported
from engine.core.pipeline import generate
from engine.core.verify.quality_gates import reset_fp_cache


@pytest.fixture(autouse=True)
def _engine() -> None:
    bootstrap()
    reset_fp_cache()


# (label, request, expected_code)
_CASES = [
    (
        "unit_not_found",
        GenerateRequest(subject="math", unit="zzz_nonexistent", form="find_value", level=1, seed=1),
        "unit_not_found",
    ),
    (
        "form_not_supported",
        GenerateRequest(subject="math", unit="g2_l25", form="calculation", level=1, seed=1),
        "form_not_supported",
    ),
    (
        "level_not_supported",
        GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=99, seed=1),
        "level_not_supported",
    ),
    (
        # タクソノミーには在るが FamilySpec 未制作。ここが実装されたら、まだ未制作の
        # 別セルに差し替える（exam_l1.find_value Lv3 は C13 で実装済みになった）。
        # proof form は frame ごと未実装なので、当面いちばん動かない座標である。
        "not_implemented",
        GenerateRequest(subject="math", unit="exam_l6", form="proof", level=3, seed=1),
        "not_implemented",
    ),
    (
        "purpose_not_supported",  # variant は M0 未対応（黙って base を返さない）
        GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=2, purpose="variant", seed=1),
        "purpose_not_supported",
    ),
    (
        "cause_not_found_missing",  # remedial なのに cause_id 無し
        GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=2, purpose="remedial", seed=1),
        "cause_not_found",
    ),
    (
        "cause_not_found_unknown",  # 実在しない cause_id
        GenerateRequest(
            subject="math", unit="g2_l25", form="find_value", level=2, purpose="remedial", seed=1,
            options=GenerateOptions(cause_id="lf.nonexistent_cause"),
        ),
        "cause_not_found",
    ),
]


@pytest.mark.parametrize("label,req,expected", _CASES, ids=[c[0] for c in _CASES])
def test_unsupported_code_fires_and_never_returns_a_problem(
    label: str, req: GenerateRequest, expected: str
) -> None:
    result = generate(req)
    # F-5 の核: 未対応座標に別種の Problem を返さない
    assert not isinstance(result, Problem), f"{label}: 別種の Problem が返った（F-5 違反）"
    assert isinstance(result, Unsupported)
    assert result.code == expected, f"{label}: code={result.code} (期待 {expected})"


def test_all_m0_reachable_codes_are_covered() -> None:
    """本ファイルが M0 で到達可能な全 Unsupported コードを発火していることの自己検査。"""
    covered = {expected for _, _, expected in _CASES}
    m0_reachable = {
        "unit_not_found", "form_not_supported", "level_not_supported",
        "purpose_not_supported", "cause_not_found", "not_implemented",
    }
    assert m0_reachable <= covered, f"未被覆コード: {m0_reachable - covered}"
