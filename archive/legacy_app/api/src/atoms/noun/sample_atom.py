"""SampleAtom（§18.1）

標本調査データを表す Atom。EstimatePopulationVerb の入力となり、
標本抽出数から母集団推定値を保持する。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class SampleAtom(NounAtom):
    tags: ClassVar[List[str]] = ["sampling_survey"]

    def __init__(
        self,
        population_size: int = 1000,
        sample_size: int = 100,
        sample_count: int = 0,
        target_attribute: str = "不良品割合",
        population_estimate: sympy.Expr | None = None,
    ) -> None:
        self.population_size: int = population_size
        self.sample_size: int = sample_size
        self.sample_count: int = sample_count
        self.target_attribute: str = target_attribute
        self.population_estimate: sympy.Expr = (
            sympy.Integer(0) if population_estimate is None else population_estimate
        )

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "SampleAtom":
        custom = constraints.custom or {}
        population_size: int = int(custom.get("population_size", rng.randint(500, 5000)))
        sample_size: int = int(custom.get("sample_size", rng.randint(30, 200)))
        if sample_size > population_size:
            sample_size = max(1, population_size // 10)
        target_attribute: str = str(custom.get("target_attribute", "不良品割合"))

        # 該当属性をもつ標本の数（sample_size より小さい正整数）
        if "sample_count" in custom:
            sample_count = int(custom["sample_count"])
            sample_count = max(0, min(sample_size, sample_count))
        else:
            # 1〜sample_size/2 程度のレンジで抽出
            upper = max(1, sample_size // 2)
            sample_count = rng.randint(1, upper)

        # 母集団推定値: population_size * (sample_count / sample_size)
        population_estimate = sympy.Rational(population_size * sample_count, sample_size)

        return SampleAtom(
            population_size=population_size,
            sample_size=sample_size,
            sample_count=sample_count,
            target_attribute=target_attribute,
            population_estimate=population_estimate,
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "population_size": sympy.Integer(self.population_size),
            "sample_size": sympy.Integer(self.sample_size),
            "sample_count": sympy.Integer(self.sample_count),
            "population_estimate": self.population_estimate,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        population_size = int(custom.get("population_size", 1000))
        sample_size = int(custom.get("sample_size", 100))
        return population_size * sample_size
