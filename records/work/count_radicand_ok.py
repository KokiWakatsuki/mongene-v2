"""「根号の中に上限を置いたら、組が何通り残るか」を先に数える。

FIXES.md の原則⓪の実行に必要な数え上げ。定義域は広いまま、答えの根号の中に上限を
置いて超えたら組み直す——という直し方が成り立つのは、**残る組が dup ≤ 0.20 を通せる
だけある**ときだけ。100 seed の distinct は N(1−(1−1/N)^100) なので、
dup ≤ 0.20 には約250通り要る。

根号の中（＝平方因数を外に出しきったあとの数）は、辺を小さくすることでは下がらない。
`√362`（7,12,13）は辺が小さくても大きい。逆に 3,4,12 は `√169 = 13` で根号が消える。
**上限は辺の大きさではなく「開ける形か」を選ぶ**ので、定義域を狭めずに効く。

実行: .venv/bin/python records/work/count_radicand_ok.py
"""
from __future__ import annotations

import math
from itertools import combinations, product


def squarefree_part(n: int) -> int:
    """√n を簡単にしたあとの根号の中（平方因数を外に出しきった残り）。"""
    r = n
    for d in range(2, int(math.isqrt(n)) + 1):
        while r % (d * d) == 0:
            r //= d * d
    return r


def report(title: str, cases: list[tuple[tuple, int]], caps: tuple[int, ...] = (20, 40, 60, 100)) -> None:
    print(f"\n=== {title} — 全 {len(cases)} 通り ===")
    for cap in caps:
        ok = [c for c in cases if squarefree_part(c[1]) <= cap]
        # 答えの相異数（同じ答えになる組は dup の観点で1通りに見えうるので参考に出す）
        distinct_ans = len({(squarefree_part(v), v) for _, v in ok})
        print(f"  根号の中 ≤ {cap:>3}: {len(ok):>6} 通り / 相異な答え {distinct_ans:>4}")
    small = [c for c in cases if squarefree_part(c[1]) <= 60][:8]
    print("  例:", "  ".join(f"{c[0]}→√{squarefree_part(c[1])}" for c in small))


def main() -> None:
    # ① 直方体の対角線 √(a²+b²+c²)（g3_l55.find_value.Lv2）
    box = [((a, b, c), a * a + b * b + c * c)
           for a, b, c in product(range(2, 16), repeat=3) if a <= b <= c]
    report("直方体の対角線 2〜15", box)

    # ② 直方体を開いた最短経路 √((a+b)² + c²)（g3_l56.find_value.Lv2）
    path = [((a, b, c), (a + b) ** 2 + c * c)
            for a, b, c in product(range(2, 16), repeat=3)]
    report("開いた最短経路 2〜15", path)

    # ③ 2点間の距離 √(dx²+dy²)（g3_l54.find_value.Lv2）
    dist = [((dx, dy), dx * dx + dy * dy)
            for dx, dy in product(range(1, 16), repeat=2)]
    report("2点間の距離 dx,dy 1〜15", dist)

    # ④ 直角三角形の斜辺 √(a²+b²)（g3_l53.find_value.Lv2 の前半）
    hyp = [((a, b), a * a + b * b) for a, b in combinations(range(3, 31), 2)]
    report("直角三角形の斜辺 3〜30", hyp)

    # ⑤ 解の公式の判別式 √(b²−4ac)（g3_l26/l28.calculation）
    disc = [((a, b, c), b * b - 4 * a * c)
            for a, b, c in product(range(1, 6), range(-15, 16), range(-15, 16))
            if b * b - 4 * a * c > 0]
    report("解の公式の判別式 a1〜5・b,c −15〜15", disc)


if __name__ == "__main__":
    main()
