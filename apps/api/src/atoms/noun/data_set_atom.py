"""DataSetAtom（§18.1）

統計データ（数値リスト・度数分布）を表す Atom。
AnalyzeDataVerb の入力となり、平均・中央値・最頻値・四分位数を保持する。
"""
from __future__ import annotations

import random
import statistics
from typing import Any, ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_DISTRIBUTION_TYPES = ("uniform", "normal", "skewed")


@register_noun
class DataSetAtom(NounAtom):
    tags: ClassVar[List[str]] = ["statistics", "data_analysis"]

    def __init__(
        self,
        values: List[sympy.Expr] | None = None,
        frequency_distribution: List[Tuple[float, float, int]] | None = None,
        mean: sympy.Expr | None = None,
        median: sympy.Expr | None = None,
        mode: sympy.Expr | None = None,
        q1: sympy.Expr | None = None,
        q3: sympy.Expr | None = None,
        distribution_type: str = "uniform",
    ) -> None:
        self.values: List[sympy.Expr] = values or []
        self.frequency_distribution: List[Tuple[float, float, int]] = (
            frequency_distribution or []
        )
        self.mean: sympy.Expr = sympy.Integer(0) if mean is None else mean
        self.median: sympy.Expr = sympy.Integer(0) if median is None else median
        self.mode: sympy.Expr = sympy.Integer(0) if mode is None else mode
        self.q1: sympy.Expr = sympy.Integer(0) if q1 is None else q1
        self.q3: sympy.Expr = sympy.Integer(0) if q3 is None else q3
        self.distribution_type: str = distribution_type

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "DataSetAtom":
        custom = constraints.custom or {}
        data_size: int = int(custom.get("data_size", 20))
        data_size = max(10, min(100, data_size))
        value_range: Tuple[int, int] = tuple(custom.get("value_range", (0, 100)))  # type: ignore[assignment]
        lo, hi = int(value_range[0]), int(value_range[1])
        if hi <= lo:
            hi = lo + 10
        distribution_type: str = str(custom.get("distribution_type", "uniform"))
        if distribution_type not in _DISTRIBUTION_TYPES:
            distribution_type = "uniform"

        raw_values: List[int] = []
        if distribution_type == "uniform":
            raw_values = [rng.randint(lo, hi) for _ in range(data_size)]
        elif distribution_type == "normal":
            mu = (lo + hi) / 2.0
            sigma = max(1.0, (hi - lo) / 6.0)
            for _ in range(data_size):
                v = int(round(rng.gauss(mu, sigma)))
                v = max(lo, min(hi, v))
                raw_values.append(v)
        else:  # skewed
            for _ in range(data_size):
                # 右に裾を引く分布（一様の最小を多用）
                u = rng.random() ** 2
                v = int(round(lo + u * (hi - lo)))
                raw_values.append(v)

        values = [sympy.Integer(v) for v in raw_values]

        mean_val = sympy.Rational(sum(raw_values), len(raw_values))
        median_val = sympy.Rational(statistics.median(raw_values)).limit_denominator(1000)
        try:
            mode_val = sympy.Integer(statistics.mode(raw_values))
        except statistics.StatisticsError:
            mode_val = sympy.Integer(raw_values[0])

        sorted_vals = sorted(raw_values)
        n = len(sorted_vals)
        # 四分位数（Tukey 流の簡易計算）
        def _quantile(arr: List[int], q: float) -> sympy.Expr:
            idx = q * (len(arr) - 1)
            lo_i = int(idx)
            hi_i = min(lo_i + 1, len(arr) - 1)
            frac = idx - lo_i
            return sympy.Rational(arr[lo_i]) + sympy.Rational(frac).limit_denominator(1000) * (
                sympy.Rational(arr[hi_i]) - sympy.Rational(arr[lo_i])
            )

        q1_val = _quantile(sorted_vals, 0.25)
        q3_val = _quantile(sorted_vals, 0.75)

        # 度数分布（5 階級程度）
        num_bins = 5
        bin_width = (hi - lo) / num_bins if hi > lo else 1.0
        freq_dist: List[Tuple[float, float, int]] = []
        for i in range(num_bins):
            bin_lo = lo + i * bin_width
            bin_hi = bin_lo + bin_width
            if i == num_bins - 1:
                count = sum(1 for v in raw_values if bin_lo <= v <= bin_hi)
            else:
                count = sum(1 for v in raw_values if bin_lo <= v < bin_hi)
            freq_dist.append((float(bin_lo), float(bin_hi), count))

        return DataSetAtom(
            values=values,
            frequency_distribution=freq_dist,
            mean=mean_val,
            median=median_val,
            mode=mode_val,
            q1=q1_val,
            q3=q3_val,
            distribution_type=distribution_type,
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "mean": self.mean,
            "median": self.median,
            "mode": self.mode,
            "q1": self.q1,
            "q3": self.q3,
            "size": sympy.Integer(len(self.values)),
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        data_size = int(custom.get("data_size", 20))
        value_range = tuple(custom.get("value_range", (0, 100)))
        spread = max(1, int(value_range[1]) - int(value_range[0]))
        return spread**min(data_size, 5) * len(_DISTRIBUTION_TYPES)
