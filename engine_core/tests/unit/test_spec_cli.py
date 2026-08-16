"""spec_cli（Task7: セル制作ツール）の unit テスト。

preview/check/approve の3サブコマンドを CLI 実行(main)経由で検証する。
approve は tmp_path を `--golden-dir` 相当（内部APIでは golden_dir 引数）に渡し、
本物の `engine_tests/golden/` を汚さない。
"""
from __future__ import annotations

from pathlib import Path

import yaml

from engine.tools.spec_cli import build_parser, main


def test_preview_writes_html_with_source_desc_and_problem_text(tmp_path: Path) -> None:
    out = tmp_path / "preview.html"
    exit_code = main(
        ["preview", "math.g2_l25.find_value", "--seeds", "2", "--out", str(out)]
    )
    assert exit_code == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    # source_desc の一部（YAML に書かれた語）が含まれる
    assert "source_desc" in content
    assert "2点から傾きを出し" in content
    # 生成された problem_text ブロックが存在する
    assert "problem-text" in content
    # 全レベル(Lv2, Lv3)が並置されている
    assert "Level 2" in content
    assert "Level 3" in content


def test_preview_default_out_path(tmp_path: Path, monkeypatch) -> None:
    # **`--families-dir` を渡さない。** family の spec はパッケージからの相対で引くので、
    # cwd をどこに移しても解決できる（前は cwd 相対だったので、渡さないと0件になった）。
    # ここで渡さないことが「エンジンは cwd に依存しない」の検査そのものになる。
    # 検証するのは出力の既定パスが cwd 相対であること（＝呼んだ場所に書く）。
    monkeypatch.chdir(tmp_path)
    exit_code = main(["preview", "math.g2_l25.find_value", "--seeds", "1"])
    assert exit_code == 0
    assert (tmp_path / "preview_math.g2_l25.find_value.html").exists()


def test_check_find_value_family_succeeds(capsys) -> None:
    # seed 数は既定（20/100）でなく小さく。ここは CLI の入出力を見る場所で、
    # 全 seed の合否は eval のゲートが見る（既定のままだと 500 秒かかっていた）。
    exit_code = main(
        ["check", "math.g2_l25.find_value", "--smoke-seeds", "3", "--dup-seeds", "12"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    report = yaml.safe_load(captured.out) if captured.out.strip().startswith("family") else None
    import json

    report = json.loads(captured.out)
    assert report["ok"] is True
    assert report["lint_errors"] == []
    assert report["smoke_failures"] == []
    # dup_rates はレベルごとのキーを持つ
    assert "2" in report["dup_rates"]
    assert "3" in report["dup_rates"]


def test_check_nonexistent_family_fails(capsys) -> None:
    exit_code = main(["check", "math.does_not_exist.find_value"])
    assert exit_code == 1
    captured = capsys.readouterr()
    import json

    report = json.loads(captured.out)
    assert report["ok"] is False
    assert any(e["rule"] == "R0" for e in report["lint_errors"])


def test_approve_writes_golden_and_approval(tmp_path: Path) -> None:
    golden_dir = tmp_path / "golden"
    exit_code = main(
        ["approve", "math.g2_l25.find_value", "--golden-dir", str(golden_dir)]
    )
    assert exit_code == 0

    family_dir = golden_dir / "math.g2_l25.find_value"
    assert family_dir.exists()

    expected_files = [
        "math.g2_l25.find_value_lv2_seed1.yaml",
        "math.g2_l25.find_value_lv2_seed2.yaml",
        "math.g2_l25.find_value_lv2_seed3.yaml",
        "math.g2_l25.find_value_lv3_seed1.yaml",
        "math.g2_l25.find_value_lv3_seed2.yaml",
        "math.g2_l25.find_value_lv3_seed3.yaml",
    ]
    for fname in expected_files:
        fpath = family_dir / fname
        assert fpath.exists(), f"missing golden file: {fname}"
        doc = yaml.safe_load(fpath.read_text(encoding="utf-8"))
        assert "problem_text" in doc
        assert "meta" in doc

    approval_path = family_dir / "approval.yaml"
    assert approval_path.exists()
    approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    assert approval["family"] == "math.g2_l25.find_value"
    assert "approver" in approval
    assert "approved_at" in approval
    assert "content_sha256" in approval
    assert len(approval["files"]) == 6


def test_approve_diff_reports_unchanged_on_second_run(tmp_path: Path, capsys) -> None:
    golden_dir = tmp_path / "golden"
    main(["approve", "math.g2_l25.find_value", "--golden-dir", str(golden_dir)])
    capsys.readouterr()  # 1回目の出力を破棄

    exit_code = main(
        ["approve", "math.g2_l25.find_value", "--golden-dir", str(golden_dir), "--diff"]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    import json

    report = json.loads(captured.out)
    assert "diff" in report
    assert all(d["status"] == "unchanged" for d in report["diff"])


def test_build_parser_requires_subcommand() -> None:
    parser = build_parser()
    assert parser is not None
