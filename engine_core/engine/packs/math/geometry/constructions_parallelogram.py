"""平行四辺形とその仲間の構成カタログ（g2_l46/l47/l48/l49）。

**平行四辺形の性質を証明する単元では、平行だけを仮定する構成を使う。**
`constructions_congruence.py` の "parallelogram" は平行移動で作るので、対辺の長さが
等しいことが仮定に入ってしまう——それは g2_l46 で証明したいことそのものである。
ここの構成は **定義（2組の対辺が平行）だけ**を事実として持ち、対辺が等しいことも
対角線が中点で交わることも持たない。示すべきことを仮定に入れないためである。

逆に g2_l47/l48（なるための条件）の構成は、**平行四辺形であるという事実を持たない**
（持たせたら示すことが無くなる）。g2_l49 は平行四辺形であることを仮定して、そこから
長方形・ひし形であることを示す。

登録は `@register_construction("名前")`。関数は `base` / `angle` / `offset` を受ける
（recipe が同じ手順を別のパラメータで組み直して、図がたまたま見せている性質を弾く）。

**図の一部として平行な線分を宣言することについて。** 「AB∥DC のとき、辺AB上の点Mと
辺DC上の点Nについて MB∥DN」は、**点をどこに置いたかという手順が保証している**
（座標を測って平行と判定したのではない）。engine は平行を「図を見れば分かること」
として扱う（`render_text._STRUCTURAL_KINDS`）ので、構成が宣言するのが筋である。
"""
from __future__ import annotations

import itertools
import math
from typing import Any

from engine.packs.math.geometry.catalog import register_construction
from engine.packs.math.geometry.construct import Construction
from engine.packs.math.geometry.facts import (
    Point,
    ang,
    ang_eq,
    ang_text,
    collinear,
    parallel_dir,
    parallelogram,
    right_angle,
    seg,
    seg_eq,
)

Coord = tuple[float, float]


# ---------------------------------------------------------------------------
# 共通の下ごしらえ
# ---------------------------------------------------------------------------
def _pgram_coords(p: dict[str, Any]) -> dict[Point, Coord]:
    """平行四辺形 ABCD の頂点（A が左下・AB が底辺・AD が `angle` の向き）。

    教科書の平行四辺形の図は例外なくこの置き方（底辺が水平で、頂点を反時計回りに
    A、B、C、D と読む）なので、そろえる。
    """
    b, t = float(p["base"]), float(p["offset"])
    th = math.radians(float(p["angle"]))
    dx, dy = t * math.cos(th), t * math.sin(th)
    return {"A": (0.0, 0.0), "B": (b, 0.0), "C": (b + dx, dy), "D": (dx, dy)}


def _place(c: Construction, coords: dict[Point, Coord]) -> None:
    for name, xy in coords.items():
        c.coords[name] = xy


def _connect_quad(c: Construction, quad: tuple[Point, Point, Point, Point]) -> None:
    for i in range(4):
        c.connect(quad[i], quad[(i + 1) % 4])


def _parallel_sides(c: Construction, quad: tuple[Point, Point, Point, Point]) -> None:
    """四角形 ABCD の2組の対辺が平行であること（＝平行四辺形の定義）。"""
    a, b, cc, d = quad
    c.facts.add(parallel_dir((a, b), (d, cc)))
    c.facts.add(parallel_dir((a, d), (b, cc)))


def _is_parallelogram(c: Construction, quad: tuple[Point, Point, Point, Point]) -> None:
    """「四角形ABCDは平行四辺形である」を仮定として持たせる。"""
    f = parallelogram(*quad)
    c.facts.add(f)
    c.givens.append(f)


def _collinear_chain(c: Construction, names: list[Point]) -> None:
    """この順に一直線に並べたことを事実として持たせる（間にあることも記録する）。

    3点が一直線に並んでいることは、図の質の検査に「つぶれた角」と誤解されないために要る。
    並び（どちらが遠いか）は `ray_classes` が使う——同じ半直線を別の点で呼んだ角
    （∠ABE と ∠ABD）を1つの角としてそろえるのに要る。
    """
    for triple in itertools.combinations(names, 3):
        c.facts.add(collinear(*triple))
        c.collinear_order.append(triple)


def _foot_on_line(pt: Coord, a: Coord, b: Coord) -> tuple[Coord, float]:
    """点 pt から直線 ab へ下ろした垂線の足と、その足の a→b 上での位置（媒介変数）。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    s = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / n2
    return (a[0] + s * dx, a[1] + s * dy), s


# ---------------------------------------------------------------------------
# g2_l46 平行四辺形の性質とその証明
# ---------------------------------------------------------------------------
@register_construction("pgram_definition_diagonal")
def pgram_definition_diagonal(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDに対角線ACを引いた図（**仮定は平行だけ**）。

    「2組の対辺はそれぞれ等しい」を証明するための図なので、その性質を事実として
    持たせてはいけない（`exclude_rules` で規則の側も外す）。錯角 → 1組の辺と
    その両端の角 → 合同 → 対応する辺、という教科書そのままの筋道になる。
    """
    c = Construction()
    _place(c, _pgram_coords(p))
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("A", "C", shared=True)
    c.description = "平行四辺形ABCDで、対角線ACをひいた"
    return c


@register_construction("pgram_diagonals_crossing")
def pgram_diagonals_crossing(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDに対角線ACとBDを引き、その交点をOとした図。

    「対角線はそれぞれの中点で交わる」を証明するための図。対辺が等しいことは
    Lv2 で証明済みなので規則として使ってよいが、対角線の性質そのものは外す。
    """
    c = Construction()
    _place(c, _pgram_coords(p))
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("A", "C")
    c.connect("B", "D")
    c.intersection("O", ("A", "C"), ("B", "D"))
    c.description = "平行四辺形ABCDで、対角線ACとBDの交点をOとした"
    return c


@register_construction("pgram_line_through_center")
def pgram_line_through_center(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの対角線の交点Oを通る直線が、辺ABと辺DCを切る図。

    対角線の性質（中点で交わる）・対辺が平行であること（錯角）・対頂角の3つを
    組み合わせて合同を示す。**性質を複数使わないと閉じない**ので Lv4 にあたる。
    """
    c = Construction()
    coords = _pgram_coords(p)
    _place(c, coords)
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("A", "C")
    c.connect("B", "D")
    c.intersection("O", ("A", "C"), ("B", "D"))
    # 辺AB上に点Eをとり、O について反対側の辺DC上の点をFとする。E の位置は
    # `angle` から連続的に決める（**中点にはしない**——中点にすると OE ＝ OF が
    # 図の対称性から自明になってしまう）。
    ax, ay = coords["A"]
    bx, by = coords["B"]
    s = 0.24 + (float(p["angle"]) % 10.0) / 50.0  # 辺ABを 0.24〜0.44 のところで切る
    ex, ey = ax + (bx - ax) * s, ay + (by - ay) * s
    ox, oy = c.coords["O"]
    c.coords["E"] = (ex, ey)
    c.coords["F"] = (2 * ox - ex, 2 * oy - ey)
    c.connect("E", "F")
    _collinear_chain(c, ["A", "E", "B"])
    _collinear_chain(c, ["D", "F", "C"])
    _collinear_chain(c, ["E", "O", "F"])
    c.description = (
        "平行四辺形ABCDで、対角線ACとBDの交点をOとし、"
        "点Oを通る直線が辺AB、辺DCと交わる点をそれぞれE、Fとした"
    )
    return c


# ---------------------------------------------------------------------------
# g2_l47 平行四辺形になるための条件
# ---------------------------------------------------------------------------
@register_construction("quad_bisecting_diagonals")
def quad_bisecting_diagonals(p: dict[str, Any]) -> Construction:
    """四角形ABCDの対角線が、点Oでそれぞれの中点で交わっている図。

    **平行四辺形であることは仮定しない**（それを示すのがこの単元）。点対称の位置に
    点をとる手順そのものが「Oはそれぞれの中点」を保証する。
    """
    c = Construction()
    coords = _pgram_coords(p)
    ox = (coords["A"][0] + coords["C"][0]) / 2
    oy = (coords["A"][1] + coords["C"][1]) / 2
    c.free_point("O", ox, oy)
    c.free_point("A", *coords["A"])
    c.free_point("B", *coords["B"])
    c.reflected_point("C", "A", "O")
    c.reflected_point("D", "B", "O")
    _connect_quad(c, ("A", "B", "C", "D"))
    c.connect("A", "C")
    c.connect("B", "D")
    c.description = (
        "下の図の四角形ABCDで、対角線ACとBDは点Oで交わっていて、点Oはそれぞれの中点である"
    )
    return c


@register_construction("quad_one_parallel_and_angle")
def quad_one_parallel_and_angle(p: dict[str, Any]) -> Construction:
    """四角形ABCDで、AB∥DC と ∠ADB ＝ ∠CBD だけが与えられている図（対角線BD入り）。

    平行が**1組しか**与えられていないので、条件をそのまま当てることはできない。
    錯角と合同を経由して対辺が等しいことを出し、そこで初めて条件に持ち込む
    ——「満たす条件を自分で選ぶ」（Lv3）にあたる。∠ADB ＝ ∠CBD は、AD と BC を
    平行に置いた手順が保証している（錯角）。
    """
    c = Construction()
    _place(c, _pgram_coords(p))
    _connect_quad(c, ("A", "B", "C", "D"))
    c.facts.add(parallel_dir(("A", "B"), ("D", "C")))
    bisect = ang_eq(ang("D", "A", "B"), ang("B", "C", "D"))
    c.facts.add(bisect)
    c.givens.append(bisect)
    c.connect("B", "D", shared=True)
    c.description = "下の図の四角形ABCDで、AB∥DC、∠ADB ＝ ∠CBD であり、対角線BDをひいた"
    return c


# ---------------------------------------------------------------------------
# g2_l48 平行四辺形になるための条件を使った証明
# ---------------------------------------------------------------------------
@register_construction("pgram_side_midpoints")
def pgram_side_midpoints(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの辺AB、DCの中点をM、Nとした図。

    「等しい線分の半分どうしは等しい」→「1組の対辺が平行でその長さが等しい」の2段。
    MB∥DN は、M と N を辺AB・辺DC の上にとった手順が保証している。
    """
    c = Construction()
    _place(c, _pgram_coords(p))
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.midpoint_of("M", "A", "B")
    c.midpoint_of("N", "D", "C")
    c.connect("M", "D")
    c.connect("B", "N")
    c.facts.add(parallel_dir(("M", "B"), ("D", "N")))
    c.description = "平行四辺形ABCDで、辺AB、辺DCの中点をそれぞれM、Nとした"
    return c


@register_construction("pgram_perpendicular_feet")
def pgram_perpendicular_feet(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの頂点A、Cから対角線BDにひいた垂線の足をP、Qとした図。

    直角三角形の合同条件（斜辺と1つの鋭角）で AP ＝ CQ を出し、AP∥QC と合わせて
    「1組の対辺が平行でその長さが等しい」に持ち込む＝補助線と合同を使う2段階。
    """
    c = Construction()
    coords = _pgram_coords(p)
    _place(c, coords)
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("B", "D")
    (px, py), sp = _foot_on_line(coords["A"], coords["B"], coords["D"])
    (qx, qy), sq = _foot_on_line(coords["C"], coords["B"], coords["D"])
    c.coords["P"] = (px, py)
    c.coords["Q"] = (qx, qy)
    c.connect("A", "P")
    c.connect("C", "Q")
    order = ["B"] + [n for _, n in sorted([(sp, "P"), (sq, "Q")])] + ["D"]
    _collinear_chain(c, order)
    for foot, vertex in (("P", "A"), ("Q", "C")):
        for arm in ("B", "D"):
            f = right_angle(foot, vertex, arm)
            c.facts.add(f)
    c.givens.append(right_angle("P", "A", "B"))
    c.givens.append(right_angle("Q", "C", "D"))
    # AP と QC は、どちらも BD に垂直で A と C が BD の反対側にあるので同じ向きに平行。
    c.facts.add(parallel_dir(("A", "P"), ("Q", "C")))
    c.description = (
        "平行四辺形ABCDで、頂点A、Cから対角線BDにひいた垂線と"
        "対角線BDとの交点を、それぞれP、Qとした"
    )
    return c


@register_construction("pgram_diagonal_equal_points")
def pgram_diagonal_equal_points(p: dict[str, Any]) -> Construction:
    """平行四辺形ABCDの対角線BD上に、BE ＝ DF となる2点E、Fをとった図。

    合同を**2回**組んで2組の対辺が等しいことを出す。どの条件をどう満たすかを
    自分で決めないと閉じないので Lv4 にあたる。
    """
    c = Construction()
    coords = _pgram_coords(p)
    _place(c, coords)
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("B", "D")
    bx, by = coords["B"]
    dx, dy = coords["D"]
    s = 0.22 + (float(p["angle"]) % 8.0) / 60.0  # BD を 0.22〜0.35 のところで切る
    c.coords["E"] = (bx + (dx - bx) * s, by + (dy - by) * s)
    c.coords["F"] = (dx + (bx - dx) * s, dy + (by - dy) * s)
    c.connect("A", "E")
    c.connect("A", "F")
    c.connect("C", "E")
    c.connect("C", "F")
    _collinear_chain(c, ["B", "E", "F", "D"])
    f = seg_eq(seg("B", "E"), seg("D", "F"))
    c.facts.add(f)
    c.givens.append(f)
    c.description = "平行四辺形ABCDの対角線BD上に、BE ＝ DF となる2点E、Fをとった"
    return c


# ---------------------------------------------------------------------------
# g2_l49 長方形・ひし形・正方形の性質と条件
# ---------------------------------------------------------------------------
@register_construction("pgram_equal_diagonals")
def pgram_equal_diagonals(p: dict[str, Any]) -> Construction:
    """対角線の長さが等しい平行四辺形ABCD（＝図としては長方形）。

    **図は本当の形で描く。** 対角線が等しい平行四辺形は長方形なのだから、
    ゆがんだ平行四辺形に「対角線が等しい」と印を付けた図は、図として嘘になる。
    角度のパラメータは形を決めない（長方形は2辺の長さで決まる）が、辺の長さ2つが
    ゆれるので、図がたまたま見せる性質（正方形に見える等）は弾ける。
    """
    c = Construction()
    b, t = float(p["base"]), float(p["offset"])
    _place(c, {"A": (0.0, 0.0), "B": (b, 0.0), "C": (b, t), "D": (0.0, t)})
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("A", "C")
    c.connect("B", "D")
    f = seg_eq(seg("A", "C"), seg("B", "D"))
    c.facts.add(f)
    c.givens.append(f)
    c.description = "平行四辺形ABCDで、対角線ACとBDの長さが等しい"
    return c


@register_construction("pgram_isosceles_diagonal")
def pgram_isosceles_diagonal(p: dict[str, Any]) -> Construction:
    """対角線ACについて ∠BAC ＝ ∠BCA である平行四辺形ABCD（＝図としてはひし形）。

    2つの角が等しい三角形は二等辺三角形 → となり合う辺が等しい平行四辺形はひし形、
    の2段。どの条件を選ぶかは与えられていない（Lv3）。
    """
    c = Construction()
    side = float(p["base"])
    th = math.radians(float(p["angle"]))
    dx, dy = side * math.cos(th), side * math.sin(th)
    _place(c, {"A": (0.0, 0.0), "B": (side, 0.0), "C": (side + dx, dy), "D": (dx, dy)})
    _connect_quad(c, ("A", "B", "C", "D"))
    _parallel_sides(c, ("A", "B", "C", "D"))
    _is_parallelogram(c, ("A", "B", "C", "D"))
    c.connect("A", "C")
    f = ang_eq(ang("A", "B", "C"), ang("C", "A", "B"))
    c.facts.add(f)
    c.givens.append(f)
    # 事実は ang_eq(ang("A","B","C"), ang("C","A","B")) ＝ ∠BAC と ∠ACB。
    # 手書きの「∠BCA」だけ並びが違っていた。
    c.description = (
        "平行四辺形ABCDで、対角線ACをひいたところ、"
        f"{ang_text(ang('A', 'B', 'C'))} ＝ {ang_text(ang('C', 'A', 'B'))} であった"
    )
    return c
