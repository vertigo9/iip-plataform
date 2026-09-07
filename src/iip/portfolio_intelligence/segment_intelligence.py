"""Segment intelligence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentExposure:
    segment: str
    weight: float
    asset_count: int


def aggregate_segment(holdings) -> tuple[SegmentExposure, ...]:
    grouped = {}
    for holding in holdings:
        if not holding.segment:
            continue
        weight, count = grouped.get(holding.segment, (0.0, 0))
        grouped[holding.segment] = (weight + holding.weight, count + 1)
    return tuple(
        SegmentExposure(segment, round(weight, 12), count)
        for segment, (weight, count) in sorted(
            grouped.items(), key=lambda item: (-item[1][0], item[0])
        )
    )
