import random
from collections.abc import Sequence
from typing import TypeVar

import numpy as np

T = TypeVar("T")


class SimulationRandom:
    """
    Single deterministic random source for a Scenario Run.
    """

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._python = random.Random(seed)
        self._numpy = np.random.default_rng(seed)

    def choice(self, values: Sequence[T]) -> T:
        return self._python.choice(values)

    def randint(self, minimum: int, maximum: int) -> int:
        return self._python.randint(minimum, maximum)

    def uniform(self, minimum: float, maximum: float) -> float:
        return self._python.uniform(minimum, maximum)

    def normal(self, mean: float, stddev: float) -> float:
        return float(self._numpy.normal(mean, stddev))