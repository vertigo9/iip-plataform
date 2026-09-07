"""Validation matrix for portfolio operational state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationCell:
    asset: str
    criterion: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ValidationMatrix:
    cells: tuple[ValidationCell, ...]

    @property
    def passed(self) -> bool:
        return bool(self.cells) and all(cell.passed for cell in self.cells)

    def failures(self) -> tuple[ValidationCell, ...]:
        return tuple(cell for cell in self.cells if not cell.passed)


def build_matrix(
    assets: tuple[str, ...],
    criteria: tuple[str, ...],
    evaluator,
) -> ValidationMatrix:
    cells = []
    for asset in assets:
        for criterion in criteria:
            result = evaluator(asset, criterion)
            if isinstance(result, tuple):
                passed, detail = result
            else:
                passed, detail = bool(result), ""
            cells.append(ValidationCell(asset, criterion, passed, detail))
    return ValidationMatrix(tuple(cells))
