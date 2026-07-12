"""goal_progress（ゴール仕様 §3.5 の進捗実測）の整合性テスト。

台帳の網羅性（分類漏れゼロ）と集計の内部整合を検証する。総数 630 のような
データ依存の定数は固定しない（分母は units.generated.yaml に自動追従＝仕様 R-IN6）。
"""
from __future__ import annotations

import json

from engine.tools.goal_progress import _GROUP_LABELS, build_report, classify


def test_goal_progress_report_consistency() -> None:
    report = build_report()

    # 台帳の網羅性: 分類漏れセルはゼロ（新 section 追加時はここが落ちて同時更新を強制する）
    assert report["unmapped"] == []

    # 集計の内部整合: グループ合計 = 学年合計 = 総数、被覆は総数以下
    assert sum(g["total"] for g in report["groups"]) == report["total"]
    assert sum(g["covered"] for g in report["groups"]) == report["covered"]
    assert sum(st["total"] for st in report["grades"].values()) == report["total"]
    assert sum(st["covered"] for st in report["grades"].values()) == report["covered"]
    assert 0 <= report["covered"] <= report["total"]
    assert report["total"] > 0

    # グループ ID はゴール仕様 §3.4 の C1〜C16 に一致
    assert {g["id"] for g in report["groups"]} == set(_GROUP_LABELS)

    # CI 連携（--json）のため JSON 直列化可能であること
    json.dumps(report, ensure_ascii=False)


def test_classify_form_precedence() -> None:
    # 横断形式（word_problem/proof/construction）は section・学年に関係なく優先される
    assert classify("g2_l17", "中学2年 ／ 数と式 ／ 連立方程式", "word_problem") == "C14"
    assert classify("exam_l6", "中学3年 ／ 入試対策 ／ 入試対策", "proof") == "C15"
    assert classify("g1_l41", "中学1年 ／ 図形 ／ 平面図形", "construction") == "C16"
    # exam の T1 形式は C13
    assert classify("exam_l1", "中学3年 ／ 入試対策 ／ 入試対策", "find_value") == "C13"
    # 未知の section は None（＝レポートで unmapped として異常検出）
    assert classify("g1_l1", "中学1年 ／ 未知の新領域", "calculation") is None
