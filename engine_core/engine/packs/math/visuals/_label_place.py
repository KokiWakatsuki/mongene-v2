"""頂点の名前を、**図の外側へ**逃がして置く。

どの図も長らく「右上へ 6px」の決め打ちで頂点名を置いていた。図がその向きへ
広がっていると、名前は必ず辺の上に乗る（走査で 75 件。立方体の見取図では
K・G・M・A・N・B の6つが辺に切られていた）。

置き方は1つだけ:
  **その頂点から図の重心へ向かう向きの、反対側**へ離す。
凸でない図形でも、頂点は重心から見て外向きにあるので、この向きへ逃がせば
辺に当たりにくい。真横に近いときは行の高さぶん、真上下に近いときは字幅ぶん、
余分に離す（文字の箱は横長なので）。
"""
from __future__ import annotations

import math


def outward(
    px: float, py: float, cx: float, cy: float, *, dist: float = 12.0
) -> tuple[float, float, str]:
    """点 (px, py) の名前を置く位置と text-anchor を返す。

    (cx, cy) は図の重心。戻り値の y は baseline なので、上に逃がすときは
    文字の高さぶん余計に上げる。
    """
    dx, dy = px - cx, py - cy
    norm = math.hypot(dx, dy)
    if norm < 1e-6:
        dx, dy, norm = 0.0, -1.0, 1.0
    ux, uy = dx / norm, dy / norm
    x = px + ux * dist
    # baseline 補正: 上へ逃がすなら文字の高さぶん上、下へ逃がすなら少し下。
    y = py + uy * dist + (-2.0 if uy < -0.3 else (9.0 if uy > 0.3 else 4.0))
    anchor = "start" if ux > 0.3 else ("end" if ux < -0.3 else "middle")
    return x, y, anchor


def haloed_text(
    x: float, y: float, s: str, *, size: float, anchor: str = "middle", halo: float = 3.0
) -> str:
    """文字を、**白い縁取りの上に**置く（下の線を切らずに読めるようにする）。

    白い矩形を敷くと、下を通る線がそこで途切れて「描き落とし」に見える。
    同じ文字を白で太らせて先に描き、その上に黒で重ねると、線は文字の外側で
    つながったまま、文字だけが浮く。

    `paint-order="stroke"` は cairosvg が解さない（白が黒の上に来て文字が消える）
    ので、**2枚重ねで書く**。<text> は増えるが G-Q5v は集合で照合するので通る。
    """
    common = f'font-size="{size:g}" text-anchor="{anchor}"'
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" {common} stroke="#ffffff" '
        f'stroke-width="{halo:g}" stroke-linejoin="round" fill="#ffffff">{s}</text>'
        f'<text x="{x:.2f}" y="{y:.2f}" {common} fill="#000000">{s}</text>'
    )


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return 0.0, 0.0
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))
