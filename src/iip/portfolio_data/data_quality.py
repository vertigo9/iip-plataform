"""Portfolio data quality gates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class DataQuality:
    valid: bool
    errors: tuple[str, ...] = ()


def validate_weight(weight: float) -> DataQuality:
    if not isfinite(weight):
        return DataQuality(False, ("weight_not_finite",))
    if weight < 0 or weight > 1:
        return DataQuality(False, ("weight_out_of_range",))
    return DataQuality(True)
