"""engine.tools.generate（1問生成 CLI）の最小テスト。

Problem を返す座標は exit 0、未対応座標（F-5）は exit 2 になることを固定する。
図つきセルは --svg-out に SVG を書き出す。
"""
from __future__ import annotations

from pathlib import Path

from engine.tools.generate import main


def test_generate_cli_valid_cell_exits_zero(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main(["g2_l25", "find_value", "2", "--seed", "7"])
    assert code == 0
    out = capsys.readouterr().out
    assert "math.g2_l25.find_value" in out
    assert "答え:" in out


def test_generate_cli_unsupported_exits_two(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main(["zzz", "find_value", "2", "--seed", "1"])
    assert code == 2
    out = capsys.readouterr().out
    assert "unit_not_found" in out


def test_generate_cli_writes_svg_for_graph_table(tmp_path: Path) -> None:
    svg = tmp_path / "fig.svg"
    code = main(["g2_l25", "graph_table", "2", "--seed", "3", "--svg-out", str(svg)])
    assert code == 0
    assert svg.exists()
    assert svg.read_text(encoding="utf-8").startswith("<svg")


def test_generate_cli_remedial(capsys) -> None:  # type: ignore[no-untyped-def]
    code = main([
        "g2_l25", "find_value", "2", "--seed", "9",
        "--purpose", "remedial", "--cause", "lf.substitution_error",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "remedial" in out
    assert "g2_l24" in out  # 戻り先に解決
