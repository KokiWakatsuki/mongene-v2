"""TableChartRenderer（§17.3, §18.3）

度数分布表（HTML テーブル）+ ヒストグラム/箱ひげ図（SVG）を生成。
"""
from __future__ import annotations

import io
from typing import Literal

from apps.api.src.visuals import _matplotlib_setup  # noqa: F401
import matplotlib.pyplot as plt  # noqa: E402

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL

ChartType = Literal["table", "histogram", "boxplot"]


class TableChartRenderer(VisualComponent):
    def __init__(self, chart_type: ChartType = "table") -> None:
        self.chart_type: ChartType = chart_type

    def render(self, dsl: VisualDSL) -> str:
        # 要素から描画モードを自動選択（constructor の chart_type 固定は無視）:
        # quartiles があれば箱ひげ図、bins があればヒストグラム、それ以外は HTML table。
        types = {el.get("type") for el in dsl.elements}
        if "quartiles" in types:
            return self._render_boxplot(dsl)
        if "bins" in types:
            return self._render_histogram(dsl)
        return self._render_table(dsl)

    def _render_table(self, dsl: VisualDSL) -> str:
        rows: list[str] = []
        for el in dsl.elements:
            t = el["type"]
            if t == "header_row":
                cells = "".join(f"<th>{c}</th>" for c in el["cells"])
                rows.append(f"<tr>{cells}</tr>")
            elif t == "data_row":
                cells = "".join(f"<td>{c}</td>" for c in el["cells"])
                rows.append(f"<tr>{cells}</tr>")
        return f"<table border='1'>{''.join(rows)}</table>"

    def _render_histogram(self, dsl: VisualDSL) -> str:
        fig, ax = plt.subplots(figsize=(4, 3))
        for el in dsl.elements:
            if el["type"] != "bins":
                continue
            bins = el["bins"]
            mids = [(lo + hi) / 2 for lo, hi, _ in bins]
            heights = [c for _, _, c in bins]
            widths = [(hi - lo) for lo, hi, _ in bins]
            ax.bar(mids, heights, width=widths, edgecolor="black", color="lightgray")
        ax.set_xlabel("階級")
        ax.set_ylabel("度数")
        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()

    def _render_boxplot(self, dsl: VisualDSL) -> str:
        fig, ax = plt.subplots(figsize=(4, 3))
        for el in dsl.elements:
            if el["type"] != "quartiles":
                continue
            q = el["quartiles"]
            ax.boxplot(
                [[q["min"], q["q1"], q["median"], q["q3"], q["max"]]],
                vert=False,
            )
        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
