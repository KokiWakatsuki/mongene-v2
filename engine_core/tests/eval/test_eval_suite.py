"""Task10: eval 一式（coverage_scan / dup_rate / level_sep / retry_stats）のテスト。

各プログラムが縦串スライスで合格すること（ok=True・終了コード0）に加え、
**わざと壊す**経路で不合格を検出できること（閾値操作・合成データ）を固定する。
「合格しか通らない eval」は素通りと同じなので、失敗検出の回帰を必ず持つ。

## ここは「スライス」で回す（全630セルは回さない）

関数名は最初から `*_ok_on_slice` だったのに、`env` を丸ごと渡していて全セルを
走らせていた。その結果 **`python -m engine.eval` と同じ計算を pytest がもう一度
やっていて**、テスト全走 23分のうち 14分43秒をここが使っていた（実測）。

全セルの保証は CI の別ステップ（`python -m engine.eval`）が持つ。ここが見るのは
**ゲートの仕組みが動くこと**——合格を出せること、そしてわざと壊したときに
不合格を出せること。だから代表的な縦串（`_SLICE`）で足りる。
"""
from __future__ import annotations

import pytest

from engine.core.verify.quality_gates import reset_fp_cache
from engine.eval import coverage_scan, dup_rate, level_sep, retry_stats
from engine.eval._harness import make_env, select_cells


# 縦串スライス（29セル）。calculation / knowledge / word_problem / find_value /
# graph_table / proof が全部入り、g1・g2・g3・exam をまたぐ単元を選んである。
_SLICE = r"^(g1_l21|g1_l33|g2_l16|g2_l20|g2_l25|g2_l41|g3_l25|g3_l43|exam_l1)\."

# **テストの中では並列にしない**（`jobs=1`）。pytest はすでに `-n 7` で走っていて、
# その中で eval がさらに7プロセス起こすと、プロセス数がコア数の何倍にもなるうえ、
# ワーカーごとの bootstrap がテストの数だけ積み上がる。スライスは数十セルなので
# 逐次で十分速い（実測 5分47秒 → 1分台）。
_JOBS = 1


@pytest.fixture(scope="module")
def env():  # type: ignore[no-untyped-def]
    e = make_env()
    reset_fp_cache()
    return e


# ---------------------------------------------------------------------------
# coverage_scan
# ---------------------------------------------------------------------------
def test_coverage_scan_ok_on_slice(env) -> None:  # type: ignore[no-untyped-def]
    from engine.eval._harness import remedial_cases

    report = coverage_scan.run_coverage_scan(env, seeds=5, only=_SLICE, jobs=_JOBS)
    assert report.ok, report.to_json()
    # セル数は capabilities と一致（横展開でセルが増えても追随する動的検査）。
    # **全セルは `python -m engine.eval` が見る**ので、ここはスライスの中で確かめる。
    assert len(report.cells) == len(select_cells(env, _SLICE))
    assert len(report.cells) > 20, "スライスが痩せすぎ（縦串の代表になっていない）"
    assert len(report.remedial) == len(remedial_cases(env))
    # M0 縦串 + 横展開の代表セルが含まれる
    cell_names = {c.cell for c in report.cells}
    assert {"g2_l25.find_value.Lv2", "g2_l20.find_value.Lv1"} <= cell_names
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
    report = dup_rate.run_dup_rate(env, seeds=100, threshold=0.20, only=_SLICE, jobs=_JOBS)
    assert report.ok, report.to_json()
    # 各セルの fp は同一 signature ゆえ 1 種（G-FP 安定の傍証）
    for c in report.cells:
        assert c.distinct_fps == 1
    # 署名跨ぎ fp 衝突は無い
    assert report.fp_collisions == []


def test_dup_rate_fails_under_impossible_threshold(env) -> None:  # type: ignore[no-untyped-def]
    """閾値を負にすると dup_rate=0 でも over_threshold=True になり不合格（fail 経路の実証）。

    **`dup_rate_max` を宣言したセルは別扱い。** 宣言があるセルは外から渡した閾値では
    なく宣言値で判定する（`dup_rate._threshold_for`）——それが宣言の意味なので、
    「負の閾値なら全セルが不合格」は成り立たない。宣言セルについては
    **宣言値で判定されていること**を確かめて、宣言が黙って効かなくなる回帰を止める。
    """
    report = dup_rate.run_dup_rate(env, seeds=20, threshold=-1.0, only=_SLICE, jobs=_JOBS)
    assert not report.ok

    declared: dict[str, float] = {}
    for name, spec in env.families.items():
        unit, form = name.removeprefix("math.").rsplit(".", 1)
        for lv, level in spec.levels.items():
            value = getattr(level, "dup_rate_max", None)
            if value is not None:
                declared[f"{unit}.{form}.Lv{lv}"] = float(value)
    assert declared, "dup_rate_max を宣言したセルが無い（この検査が空回りしている）"

    for c in report.cells:
        if c.cell in declared:
            assert c.over_threshold == (c.dup_rate > declared[c.cell]), c
        else:
            assert c.over_threshold, c


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
    report = level_sep.run_level_sep(env, seeds=5, only=_SLICE, jobs=_JOBS)
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
    report = retry_stats.run_retry_stats(env, seeds=50, threshold=0.05, only=_SLICE, jobs=_JOBS)
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
    """CLI が正しい終了コードを返すこと。**走査はスライスで足りる**。

    ここは「入口が動くか」を見るテストで、全セルの合否を見るのは
    `python -m engine.eval`（CI の別ステップ）の仕事。全セルを回していたせいで
    このテスト1本だけで 360 秒かかっていた（実測）。
    """
    sl = ["--only", _SLICE, "--jobs", "1"]
    assert coverage_scan.main(["--seeds", "3", *sl]) == 0
    assert level_sep.main(["--seeds", "3", *sl]) == 0
    assert retry_stats.main(["--seeds", "20", *sl]) == 0
    assert dup_rate.main(["--seeds", "20", *sl]) == 0
    # 不可能閾値で dup_rate が終了コード1を返す
    assert dup_rate.main(["--seeds", "20", "--threshold", "-1", *sl]) == 1
