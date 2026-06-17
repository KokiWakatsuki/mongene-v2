"""ThreeDRenderer（§17.3, §18.3）

matplotlib の mpl_toolkits.mplot3d を用いて立体を SVG ワイヤフレームとして描画する。
"""
from __future__ import annotations

import io
from typing import Tuple

import matplotlib

matplotlib.use("Agg")  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL


class ThreeDRenderer(VisualComponent):
    def __init__(
        self,
        show_hidden_lines: bool = True,
        view_angle: Tuple[float, float] = (20, 30),
        image_size: Tuple[int, int] = (400, 400),
    ) -> None:
        self.show_hidden_lines = show_hidden_lines
        self.view_angle = view_angle
        self.image_size = image_size

    def render(self, dsl: VisualDSL) -> str:
        fig = plt.figure(figsize=(self.image_size[0] / 100, self.image_size[1] / 100))
        ax = fig.add_subplot(111, projection="3d")
        ax.view_init(elev=self.view_angle[0], azim=self.view_angle[1])
        ax.set_axis_off()

        vertices: dict[str, Tuple[float, float, float]] = {}
        for el in dsl.elements:
            t = el["type"]
            if t == "vertex":
                vertices[el["id"]] = tuple(el["coords"])
                ax.scatter(*el["coords"], color="black", s=20)
                if el.get("label"):
                    ax.text(*el["coords"], el["label"], fontsize=10)
            elif t == "edge_3d":
                p1 = vertices.get(el["from"]) or tuple(el.get("p1", (0, 0, 0)))
                p2 = vertices.get(el["to"]) or tuple(el.get("p2", (1, 1, 1)))
                style = "--" if el.get("dashed") else "-"
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="black", linestyle=style, linewidth=1,
                )
            elif t == "face":
                vids = el.get("vertices", [])
                pts = [vertices.get(v, (0, 0, 0)) for v in vids]
                if len(pts) >= 3:
                    xs = [p[0] for p in pts + [pts[0]]]
                    ys = [p[1] for p in pts + [pts[0]]]
                    zs = [p[2] for p in pts + [pts[0]]]
                    ax.plot(xs, ys, zs, color="black", linewidth=1)

        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
