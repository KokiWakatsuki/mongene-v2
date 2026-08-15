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
from engine.core.curriculum import load_curriculum
from engine.core.pipeline import _default_families, generate
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


def test_not_implemented_fires_when_a_family_spec_is_missing() -> None:
    """FamilySpec 未制作の座標は `not_implemented`（別種の Problem を返さない）。

    **台帳の座標を1つ名指しにはできない。** 630/630 が実装済みになり、
    「タクソノミーに在るのに FamilySpec が無い」座標はもう1つも残っていない
    （以前ここに置いていた exam_l6.proof Lv3 も実装された）。かといってこのコードは
    死んでいない——**セルを1つ足し忘れた／family を消した**ときに出るべきものだからだ。
    そこで実 curriculum はそのままに、**families から1枚だけ抜いて**発火させる。
    実エンジンの経路を通しつつ、台帳の側に穴を空けておく必要がなくなる。
    """
    families = dict(_default_families())
    withheld = "math.g2_l25.find_value"
    assert withheld in families, f"前提が崩れた: {withheld} が families に無い"
    del families[withheld]

    result = generate(
        GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=2, seed=1),
        families=families,
    )
    assert not isinstance(result, Problem), "FamilySpec が無いのに Problem が返った（F-5 違反）"
    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented", f"code={result.code}"


def test_every_taxonomy_coordinate_has_a_family_spec() -> None:
    """台帳の全座標が実装済みであること（`not_implemented` の裏返し）。

    上のテストが台帳の穴に頼らなくなったぶん、「穴が空いていないこと」は
    ここで正面から固定する。family を消す・レベルを消すと落ちる。
    """
    curriculum = load_curriculum()
    families = _default_families()
    missing: list[str] = []
    for unit, unit_spec in curriculum.units.items():
        for form, form_spec in (unit_spec.get("forms") or {}).items():
            spec = families.get(f"math.{unit}.{form}")
            for level in (form_spec.get("levels") or {}):
                if spec is None or str(level) not in spec.levels:
                    missing.append(f"{unit}.{form}.Lv{level}")
    assert not missing, f"FamilySpec が無い台帳座標: {missing}"


def test_all_m0_reachable_codes_are_covered() -> None:
    """本ファイルが M0 で到達可能な全 Unsupported コードを発火していることの自己検査。"""
    covered = {expected for _, _, expected in _CASES} | {"not_implemented"}
    m0_reachable = {
        "unit_not_found", "form_not_supported", "level_not_supported",
        "purpose_not_supported", "cause_not_found", "not_implemented",
    }
    assert m0_reachable <= covered, f"未被覆コード: {m0_reachable - covered}"
