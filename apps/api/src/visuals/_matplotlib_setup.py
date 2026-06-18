"""matplotlib の日本語対応セットアップ（モジュール初回 import 時に実行）"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def _setup_japanese_font() -> None:
    """OS 上で利用可能な日本語フォントを matplotlib のデフォルトに設定する"""
    candidates = [
        "Hiragino Sans",
        "Hiragino Maru Gothic Pro",
        "Noto Sans CJK JP",
        "IPAGothic",
        "Yu Gothic",
        "Meiryo",
        "TakaoGothic",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            # font.family と font.sans-serif の両方を設定
            plt.rcParams["font.family"] = ["sans-serif"]
            plt.rcParams["font.sans-serif"] = [c] + plt.rcParams.get("font.sans-serif", [])
            plt.rcParams["axes.unicode_minus"] = False
            # フォントのパス参照を明示
            try:
                font_path = next(
                    (f.fname for f in fm.fontManager.ttflist if f.name == c),
                    None,
                )
                if font_path:
                    # path 化することで cairosvg のフォント解決に依存せず描画できる
                    plt.rcParams["svg.fonttype"] = "path"
            except Exception:
                pass
            return
    # 見つからなければデフォルト維持（DejaVu Sans）


_setup_japanese_font()
