"""Release-grade scenario certification."""

from __future__ import annotations

from dataclasses import dataclass

from .validation_gate import ValidationGate


@dataclass(frozen=True)
class ScenarioCertification:
    scenarios_executed: int
    gates_passed: int
    minimum_pass_rate: float
    actual_pass_rate: float

    @property
    def certified(self) -> bool:
        return (
            self.scenarios_executed > 0
            and self.gates_passed == self.scenarios_executed
            and self.actual_pass_rate >= self.minimum_pass_rate
        )


def certify(
    gates: tuple[ValidationGate, ...],
    minimum_pass_rate: float = 1.0,
) -> ScenarioCertification:
    total = len(gates)
    passed = sum(gate.passed for gate in gates)
    rate = passed / total if total else 0.0
    return ScenarioCertification(total, passed, minimum_pass_rate, rate)
