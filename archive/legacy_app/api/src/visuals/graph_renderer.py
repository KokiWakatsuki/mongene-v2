"""GraphRenderer（§17.3, §18.3）

一次関数・二次関数・反比例のグラフを SVG で描画する。
"""
from __future__ import annotations

import io
from typing import Optional, Tuple

from apps.api.src.visuals import _matplotlib_setup  # noqa: F401
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sympy  # noqa: E402

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL


class GraphRenderer(VisualComponent):
    def __init__(
        self,
        x_range: Tuple[float, float] = (-10, 10),
        y_range: Optional[Tuple[float, float]] = None,
        show_intersection: bool = False,
        image_size: Tuple[int, int] = (400, 400),
    ) -> None:
        self.x_range = x_range
        self.y_range = y_range
        self.show_intersection = show_intersection
        self.image_size = image_size

    def render(self, dsl: VisualDSL) -> str:
        fig, ax = plt.subplots(figsize=(self.image_size[0] / 100, self.image_size[1] / 100))
        ax.axhline(0, color="gray", linewidth=0.5)
        ax.axvline(0, color="gray", linewidth=0.5)
        ax.grid(True, linestyle=":", linewidth=0.3)

        xs = np.linspace(self.x_range[0], self.x_range[1], 200)
        x_sym = sympy.Symbol("x")
        for el in dsl.elements:
            t = el["type"]
            if t == "function":
                try:
                    expr = sympy.sympify(el["expr"])
                    f = sympy.lambdify(x_sym, expr, "numpy")
                    domain = el.get("domain", self.x_range)
                    xs_local = np.linspace(domain[0], domain[1], 200)
                    ys = f(xs_local)
                    ax.plot(xs_local, ys, color=el.get("color", "black"), linewidth=1)
                except Exception:
                    continue
            elif t == "point_on_graph":
                ax.scatter([el["x"]], [el["y"]], color="black", s=40)
                if el.get("label"):
                    ax.annotate(
                        el["label"],
                        (el["x"], el["y"]),
                        textcoords="offset points",
                        xytext=(8, 8),
                        fontsize=14,
                    )
            elif t == "filled_region":
                verts = el["vertices"]
                xs_v = [v[0] for v in verts]
                ys_v = [v[1] for v in verts]
                ax.fill(
                    xs_v,
                    ys_v,
                    color=el.get("color", "#cccccc"),
                    alpha=el.get("alpha", 0.35),
                    zorder=0,
                )
            elif t == "intersection_point":
                ax.scatter([el["x"]], [el["y"]], color="black", s=45, zorder=5)
                if el.get("label"):
                    ax.annotate(
                        el["label"],
                        (el["x"], el["y"]),
                        textcoords="offset points",
                        xytext=(8, -12),
                        fontsize=12,
                        zorder=6,
                    )
            elif t == "axis_label":
                if el["axis"] == "x":
                    ax.set_xlabel(el["label"])
                else:
                    ax.set_ylabel(el["label"])

        ax.set_xlim(*self.x_range)
        if self.y_range:
            ax.set_ylim(*self.y_range)
        else:
            # y_range 未指定なら x と同じ範囲の正方ウィンドウにする。
            # 縦横で縮尺が違うと傾き・長さ・角度が視覚的に嘘になる（1次関数の傾きや
            # 座標幾何で致命的）ため、既定は縦横同一範囲＝同一縮尺にする。
            ax.set_ylim(self.x_range[0], self.x_range[1])
        # 1 目盛りを縦横で等しくする（傾き・距離・角度を忠実に描く）。
        # 範囲外に出る急な直線は正しい傾きのままクリップされる（縮尺を歪めるより誠実）。
        ax.set_aspect("equal", adjustable="box")

        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue()
