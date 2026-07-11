"""Task10: eval 一式（coverage_scan / dup_rate / level_sep / retry_stats）のテスト。

各プログラムが縦串スライスで合格すること（ok=True・終了コード0）に加え、
**わざと壊す**経路で不合格を検出できること（閾値操作・合成データ）を固定する。
「合格しか通らない eval」は素通りと同じなので、失敗検出の回帰を必ず持つ。
"""
from __future__ import annotations

import pytest

from engine.core.verify.quality_gates import reset_fp_cache
from engine.eval import coverage_scan, dup_rate, level_sep, retry_stats
from engine.eval._harness import make_env


@pytest.fixture(scope="module")
def env():  # type: ignore[no-untyped-def]
    e = make_env()
    reset_fp_cache()
    return e


# ---------------------------------------------------------------------------
# coverage_scan
# ---------------------------------------------------------------------------
def test_coverage_scan_ok_on_slice(env) -> None:  # type: ignore[no-untyped-def]
    report = coverage_scan.run_coverage_scan(env, seeds=5)
    assert report.ok, report.to_json()
    # 5 base セル + 3 remedial 要因
    assert len(report.cells) == 5
    assert len(report.remedial) == 3
    # ゲートが実際に登録されている（素通り防止）
    assert report.gate_counts["mr"] > 0
    assert report.gate_counts["text"] > 0
    assert report.gate_counts["visual"] > 0
    assert report.unreferenced_causes == []


def test_coverage_scan_detects_passthrough(env) -> None:  # type: ignore[no-untyped-def]
    """ゲート0段があれば passthrough として不合格になる（合成 CellResult）。"""
    cr = coverage_scan.CellResult(cell="x", seeds=1, generated=1, passthrough_stages=["mr"])
    assert not cr.ok


def test_coverage_scan_detects_generation_failure() -> None:
    cr = coverage_scan.CellResult(
        cell="x", seeds=1, generated=0, failures=[{"seed": 1, "code": "verification_exhausted"}]
    )
    assert not cr.ok


# ---------------------------------------------------------------------------
# dup_rate（2系統）
# ---------------------------------------------------------------------------
def test_dup_rate_ok_on_slice(env) -> None:  # type: ignore[no-untyped-def]
    report = dup_rate.run_dup_rate(env, seeds=100, threshold=0.20)
    assert report.ok, report.to_json()
    # 各セルの fp は同一 signature ゆえ 1 種（G-FP 安定の傍証）
    for c in report.cells:
        assert c.distinct_fps == 1
    # 署名跨ぎ fp 衝突は無い
    assert report.fp_collisions == []


def test_dup_rate_fails_under_impossible_threshold(env) -> None:  # type: ignore[no-untyped-def]
    """閾値を負にすると dup_rate=0 でも over_threshold=True になり不合格（fail 経路の実証）。"""
    report = dup_rate.run_dup_rate(env, seeds=20, threshold=-1.0)
    assert not report.ok
    assert all(c.over_threshold for c in report.cells)


def test_dup_rate_detects_cross_signature_fp_collision() -> None:
    """署名跨ぎ fp 衝突があれば不合格（合成 FamilyFpCollision）。"""
    report = dup_rate.DupRateReport(
        seeds=1, threshold=0.2, cells=[],
        fp_collisions=[dup_rate.FamilyFpCollision(family="f", fp="deadbeef", signatures=["s1", "s2"])],
    )
    assert not report.ok


# ---------------------------------------------------------------------------
# level_sep
# ---------------------------------------------------------------------------
def test_level_sep_ok_on_slice(env) -> None:  # type: ignore[no-untyped-def]
    report = level_sep.run_level_sep(env, seeds=5)
    assert report.ok, report.to_json()
    # find_value family は 2 レベルで署名・fp とも相異
    fv = [f for f in report.families if f.family == "math.g2_l25.find_value"][0]
    assert fv.signatures_distinct
    assert fv.fp_distinct
    assert len(set(fv.fp_by_signature.values())) == 2


def test_level_sep_detects_fp_collision() -> None:
    """異なる署名が同一 fp を持てば (b) が不合格（合成）。"""
    f = level_sep.FamilyLevelSep(
        family="f", levels=[1, 2], signatures=["s1", "s2"], signatures_distinct=True,
        fp_by_signature={"s1": "same", "s2": "same"},
        fp_collisions=[{"fp": "same", "signatures": ["s1", "s2"]}],
    )
    assert not f.fp_distinct
    assert not f.ok


def test_level_sep_detects_signature_duplication() -> None:
    """レベル間で署名が重複すれば (a) が不合格（合成）。"""
    f = level_sep.FamilyLevelSep(
        family="f", levels=[1, 2], signatures=["dup", "dup"], signatures_distinct=False,
    )
    assert not f.ok


# ---------------------------------------------------------------------------
# retry_stats
# ---------------------------------------------------------------------------
def test_retry_stats_ok_on_slice(env) -> None:  # type: ignore[no-untyped-def]
    report = retry_stats.run_retry_stats(env, seeds=50, threshold=0.05)
    assert report.ok, report.to_json()
    # 縦串の recipe は bounded_retry を宣言せず・発動0・構成失敗0
    for c in report.cells:
        assert not c.declares_bounded_retry
        assert c.retry_invocations == 0
        assert c.construct_failures == 0


def test_retry_stats_detects_construct_failure() -> None:
    cr = retry_stats.CellRetryStats(
        cell="x", seeds=10, declares_bounded_retry=False, retry_invocations=0,
        construct_failures=2, retry_rate=0.0, failure_rate=0.2, over_threshold=False,
    )
    assert not cr.ok


def test_retry_stats_detects_over_threshold() -> None:
    cr = retry_stats.CellRetryStats(
        cell="x", seeds=10, declares_bounded_retry=True, retry_invocations=6,
        construct_failures=0, retry_rate=0.6, failure_rate=0.0, over_threshold=True,
    )
    assert not cr.ok


# ---------------------------------------------------------------------------
# CLI 終了コード
# ---------------------------------------------------------------------------
def test_cli_exit_codes() -> None:
    assert coverage_scan.main(["--seeds", "3"]) == 0
    assert level_sep.main(["--seeds", "3"]) == 0
    assert retry_stats.main(["--seeds", "20"]) == 0
    assert dup_rate.main(["--seeds", "20"]) == 0
    # 不可能閾値で dup_rate が終了コード1を返す
    assert dup_rate.main(["--seeds", "20", "--threshold", "-1"]) == 1
