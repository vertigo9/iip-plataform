"""Change-control contracts for model and rule evolution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ChangeType(StrEnum):
    CODE = "code"
    RULE = "rule"
    WEIGHT = "weight"
    SOURCE = "source"
    DATA_SCHEMA = "data_schema"


@dataclass(frozen=True)
class ChangeRequest:
    change_id: str
    change_type: ChangeType
    description: str
    approved: bool = False
    tested: bool = False


def can_promote(change: ChangeRequest) -> bool:
    return bool(change.approved and change.tested)
