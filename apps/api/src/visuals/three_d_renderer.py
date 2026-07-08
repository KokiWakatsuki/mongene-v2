"""ThreeDRenderer（§17.3, §18.3）

matplotlib の mpl_toolkits.mplot3d を用いて立体を SVG ワイヤフレームとして描画する。

描画スタイル（日本の教科書標準）:
- 見える辺: 実線
- 隠れる辺（A=(0,0,0) から出る 3 辺）: 破線
- 頂点ラベル: テキストのみ（scatter 点なし）
- 寸法ラベル: テキストのみ（scatter 点なし）
"""
from __future__ import annotations

import io
import math
from typing import Dict, Tuple

import numpy as np

from apps.api.src.visuals import _matplotlib_setup  # noqa: F401
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def _is_hidden_edge(
    v_from: Tuple[float, float, float],
    v_to: Tuple[float, float, float],
    eye_dir: Tuple[float, float, float] = (0.75, 0.43, 0.34),
) -> bool:
    """隠れ辺判定: 辺の両端ともに視点方向の dot product が最小の頂点群に属する場合 True。

    簡略化: view_angle (elev=20, azim=30) に対し、
    eye = (cos30·cos20, sin30·cos20, sin20) ≈ (0.75, 0.43, 0.34)
    各頂点の dot product を計算し、最小値付近の頂点から出る辺を破線とする。
    """
    dot_from = sum(v_from[i] * eye_dir[i] for i in range(3))
    dot_to = sum(v_to[i] * eye_dir[i] for i in range(3))
    # 両端とも他の辺の最小 dot 以下なら hidden (ゆるい基準: 0.5 以下)
    return dot_from <= 0.5 and dot_to <= 0.5


def _compute_hidden_edges(
    vertices: Dict[str, Tuple[float, float, float]],
    elev: float,
    azim: float,
) -> set:
    """隠れる辺 ID のセットを返す。

    全頂点の dot product を計算し、最小値の頂点から出る 3 辺を破線と判定する。
    """
    if not vertices:
        return set()
    azim_r = math.radians(azim)
    elev_r = math.radians(elev)
    eye = (
        math.cos(elev_r) * math.cos(azim_r),
        math.cos(elev_r) * math.sin(azim_r),
        math.sin(elev_r),
    )
    dots = {vid: sum(c * eye[i] for i, c in enumerate(coords)) for vid, coords in vertices.items()}
    min_dot = min(dots.values())
    hidden_vids = {vid for vid, d in dots.items() if d <= min_dot + 1e-6}
    return hidden_vids


class ThreeDRenderer(VisualComponent):
    def __init__(
        self,
        show_hidden_lines: bool = True,
        view_angle: Tuple[float, float] = (20, 30),
        image_size: Tuple[int, int] = (500, 450),
    ) -> None:
        self.show_hidden_lines = show_hidden_lines
        self.view_angle = view_angle
        self.image_size = image_size

    def render(self, dsl: VisualDSL) -> str:
        fig = plt.figure(figsize=(self.image_size[0] / 80, self.image_size[1] / 80))
        ax = fig.add_subplot(111, projection="3d")
        ax.view_init(elev=self.view_angle[0], azim=self.view_angle[1])
        ax.set_axis_off()

        # フォントサイズを統一
        plt.rcParams["font.size"] = 11

        # まず全頂点を登録（ラベルとテキストの分離）
        vertices: dict[str, Tuple[float, float, float]] = {}
        vertex_labels: dict[str, str] = {}
        dim_labels: list[dict] = []  # 寸法ラベル（点なし）
        edges_to_draw: list[dict] = []
        vertex_ids_single_char: set[str] = set()  # A-H など頂点 ID

        for el in dsl.elements:
            t = el["type"]
            if t == "vertex":
                coords = tuple(el["coords"])
                vid = el["id"]
                vertices[vid] = coords
                label = el.get("label", "")
                if label:
                    # "cm" が含まれる → 寸法ラベル（点なし）
                    if "cm" in label or "h=" in label or "r=" in label:
                        dim_labels.append({"coords": coords, "label": label})
                    else:
                        # 頂点ラベル（A-H など）
                        vertex_labels[vid] = label
                        vertex_ids_single_char.add(vid)
            elif t == "edge_3d":
                edges_to_draw.append(el)

        # 隠れ辺の判定（寸法ラベルの疑似頂点を除外し、実頂点 A-H のみで最小 dot を求める。
        # 寸法ラベルを混ぜると oy-1.0 等の座標が最小 dot になり奥頂点 A が隠れ判定されず、
        # 破線化が効かなくなる）
        real_vertices = {vid: vertices[vid] for vid in vertex_ids_single_char if vid in vertices}
        hidden_vids = _compute_hidden_edges(real_vertices, self.view_angle[0], self.view_angle[1])

        # 辺を描画
        for el in edges_to_draw:
            vid_from = el["from"]
            vid_to = el["to"]
            p1 = vertices.get(vid_from, (0, 0, 0))
            p2 = vertices.get(vid_to, (0, 0, 0))

            # 隠れ辺判定: 元の dashed フラグ OR 奥（最小 dot）の頂点に接する辺。
            # 教科書標準では奥の頂点から出る 3 辺を破線にする。両端が hidden の辺は
            # 立方体では存在しないため（隣接頂点は可視）、どちらか一端が hidden なら破線。
            is_hidden = el.get("dashed", False) or (
                vid_from in hidden_vids or vid_to in hidden_vids
            )

            if is_hidden:
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="black", linestyle="--", linewidth=0.9, alpha=0.6,
                )
            else:
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="black", linestyle="-", linewidth=1.2,
                )

        # 頂点ラベル（A-H）: 小さな点 + テキスト
        # ラベルは立体の重心から「外向き」にオフセットする。一律 +(0.3,0.3,0.3) だと
        # 原点側の頂点（A など）のラベルが立体の内側へ潜り込んで中央に見えてしまう。
        _vpts = [vertices[v] for v in vertex_ids_single_char if v in vertices]
        if _vpts:
            gx = sum(c[0] for c in _vpts) / len(_vpts)
            gy = sum(c[1] for c in _vpts) / len(_vpts)
            gz = sum(c[2] for c in _vpts) / len(_vpts)
        else:
            gx = gy = gz = 0.0
        for vid in vertex_ids_single_char:
            if vid not in vertices:
                continue
            coords = vertices[vid]
            # 点は非常に小さく（目立たない程度）
            ax.scatter(*coords, color="black", s=10, zorder=5)
            label = vertex_labels[vid]
            dx, dy, dz = coords[0] - gx, coords[1] - gy, coords[2] - gz
            n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            off = 0.5
            ax.text(
                coords[0] + dx / n * off, coords[1] + dy / n * off, coords[2] + dz / n * off,
                label,
                fontsize=13,
                fontweight="bold",
                ha="center", va="center",
            )

        # 寸法ラベル: 点なし、テキストのみ
        for dim in dim_labels:
            coords = dim["coords"]
            ax.text(
                coords[0], coords[1], coords[2],
                dim["label"],
                fontsize=12,
                color="#1a1a8c",  # 濃い青で寸法と区別
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.1", facecolor="white", edgecolor="none", alpha=0.8),
            )

        # sphere_wireframe 要素（教科書スタイル: 赤道線・経線・緯線で球を表す）
        for el in dsl.elements:
            if el.get("type") == "sphere_wireframe":
                cx, cy, cz = el.get("center", [0, 0, 0])
                r = float(el.get("radius", 1))
                color = el.get("color", "black")
                lw = el.get("linewidth", 1.2)
                # 経線（meridians）を 6 本
                for phi in np.linspace(0, np.pi, 7)[1:-1]:
                    theta = np.linspace(0, 2 * np.pi, 60)
                    xs = cx + r * np.sin(theta) * np.cos(phi)
                    ys = cy + r * np.sin(theta) * np.sin(phi)
                    zs = cz + r * np.cos(theta)
                    ax.plot(xs, ys, zs, color=color, linewidth=lw * 0.7, alpha=0.4)
                # 赤道線（equator）
                theta = np.linspace(0, 2 * np.pi, 80)
                ax.plot(cx + r * np.cos(theta), cy + r * np.sin(theta), cz * np.ones_like(theta),
                        color=color, linewidth=lw, alpha=0.7)
                # 垂直な大円（xy 面の円）
                ax.plot(cx + r * np.cos(theta), cy * np.ones_like(theta), cz + r * np.sin(theta),
                        color=color, linewidth=lw, alpha=0.7)
                # 中心点と半径ラベル
                ax.scatter(cx, cy, cz, color=color, s=25, zorder=6)
                ax.text(cx - r * 0.5, cy - r * 0.5, cz + r + 0.3,
                        f"r={_fmt(r)} cm", fontsize=11, color=color)

        # cutout_volume 要素（設計書 §18.3: くり抜く立体を内側に点線で描く）
        for el in dsl.elements:
            if el.get("type") != "cutout_volume":
                continue
            shape = el.get("shape", "pyramid")
            color = "#cc4400"  # 橙赤色で内側のくり抜き形状を区別
            ls = "--"
            lw = 1.2

            if shape == "pyramid":
                base = el.get("base", [])
                apex = el.get("apex", [0, 0, 0])
                if base:
                    for i in range(len(base)):
                        p1, p2 = base[i], base[(i + 1) % len(base)]
                        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                                color=color, linestyle=ls, linewidth=lw, alpha=0.85)
                    for p in base:
                        ax.plot([apex[0], p[0]], [apex[1], p[1]], [apex[2], p[2]],
                                color=color, linestyle=ls, linewidth=lw, alpha=0.85)
                    ax.scatter(*apex, color=color, s=18, zorder=6)
                    s = el.get("base_side", 0)
                    h = el.get("height", 0)
                    if s and h:
                        ax.text(float(apex[0]) + 0.4, float(apex[1]), float(apex[2]) + 0.4,
                                f"底辺{_fmt(float(s))} h={_fmt(float(h))}",
                                fontsize=9, color=color)

            elif shape == "sphere":
                center = el.get("center", [0, 0, 0])
                r = float(el.get("radius", 1))
                ax.scatter(*center, color=color, s=20, zorder=6)
                ax.text(center[0] + 0.2, center[1], center[2] + 0.2,
                        f"r={_fmt(r)}", fontsize=9, color=color)

            elif shape == "prism":
                base = el.get("base", [])
                h = float(el.get("height", 2))
                if base:
                    top = [[p[0], p[1], p[2] + h] for p in base]
                    for pts in [base, top]:
                        for i in range(len(pts)):
                            p1, p2 = pts[i], pts[(i + 1) % len(pts)]
                            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                                    color=color, linestyle=ls, linewidth=1.0, alpha=0.8)
                    for pb, pt in zip(base, top):
                        ax.plot([pb[0], pt[0]], [pb[1], pt[1]], [pb[2], pt[2]],
                                color=color, linestyle=ls, linewidth=1.0, alpha=0.8)

        ax.set_box_aspect([1, 1, 1])

        buf = io.StringIO()
        fig.savefig(buf, format="svg", bbox_inches="tight", dpi=150)
        plt.close(fig)
        return buf.getvalue()
