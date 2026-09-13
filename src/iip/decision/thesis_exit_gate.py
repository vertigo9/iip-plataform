"""Thesis-break gate for long-term fundamental investment decisions.

The gate is deliberately independent from price-only stop-loss rules.

Policy:
- Critical failure in fundamentals, balance sheet, or governance -> BREAK.
- Two or more failed gates -> BREAK.
- One non-critical failure or any ATTENTION -> REVIEW.
- All six gates PASS -> INTACT.
- Remaining UNKNOWN -> INSUFFICIENT_EVIDENCE.
- Opportunity cost alone -> REVIEW, never automatic BREAK.
- UNKNOWN never becomes FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GateStatus(StrEnum):
    PASS = "PASS"
    ATTENTION = "ATTENTION"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ThesisExitState(StrEnum):
    INTACT = "INTACT"
    REVIEW = "REVIEW"
    BREAK = "BREAK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


_GATE_NAMES = (
    "fundamentals",
    "balance_sheet",
    "valuation",
    "dividends",
    "governance",
    "opportunity_cost",
)

_CRITICAL_GATES = frozenset(
    {
        "fundamentals",
        "balance_sheet",
        "governance",
    }
)


@dataclass(frozen=True)
class ThesisExitAssessment:
    fundamentals: GateStatus = GateStatus.UNKNOWN
    balance_sheet: GateStatus = GateStatus.UNKNOWN
    valuation: GateStatus = GateStatus.UNKNOWN
    dividends: GateStatus = GateStatus.UNKNOWN
    governance: GateStatus = GateStatus.UNKNOWN
    opportunity_cost: GateStatus = GateStatus.UNKNOWN

    state: ThesisExitState = ThesisExitState.INSUFFICIENT_EVIDENCE
    failed_gates: tuple[str, ...] = ()
    attention_gates: tuple[str, ...] = ()
    unknown_gates: tuple[str, ...] = ()
    critical_failure: bool = False

    @property
    def should_exit(self) -> bool:
        return self.state is ThesisExitState.BREAK

    @property
    def should_reduce(self) -> bool:
        """Informational flag for REVIEW; it does not force a sale."""
        return (
            self.state is ThesisExitState.REVIEW
            and bool(self.attention_gates or self.failed_gates)
        )


def assess_thesis_exit(
    *,
    fundamentals: GateStatus = GateStatus.UNKNOWN,
    balance_sheet: GateStatus = GateStatus.UNKNOWN,
    valuation: GateStatus = GateStatus.UNKNOWN,
    dividends: GateStatus = GateStatus.UNKNOWN,
    governance: GateStatus = GateStatus.UNKNOWN,
    opportunity_cost: GateStatus = GateStatus.UNKNOWN,
) -> ThesisExitAssessment:
    values = {
        "fundamentals": fundamentals,
        "balance_sheet": balance_sheet,
        "valuation": valuation,
        "dividends": dividends,
        "governance": governance,
        "opportunity_cost": opportunity_cost,
    }

    failed = tuple(
        name for name in _GATE_NAMES if values[name] is GateStatus.FAIL
    )
    attention = tuple(
        name for name in _GATE_NAMES if values[name] is GateStatus.ATTENTION
    )
    unknown = tuple(
        name for name in _GATE_NAMES if values[name] is GateStatus.UNKNOWN
    )

    critical_failure = any(name in _CRITICAL_GATES for name in failed)

    if critical_failure or len(failed) >= 2:
        state = ThesisExitState.BREAK
    elif failed or attention:
        state = ThesisExitState.REVIEW
    elif not unknown:
        state = ThesisExitState.INTACT
    else:
        state = ThesisExitState.INSUFFICIENT_EVIDENCE

    return ThesisExitAssessment(
        fundamentals=fundamentals,
        balance_sheet=balance_sheet,
        valuation=valuation,
        dividends=dividends,
        governance=governance,
        opportunity_cost=opportunity_cost,
        state=state,
        failed_gates=failed,
        attention_gates=attention,
        unknown_gates=unknown,
        critical_failure=critical_failure,
    )