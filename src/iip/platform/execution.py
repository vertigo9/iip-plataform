"""Production-safe orchestration over the existing IIP provider layer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .contracts import AssetRun, ExecutionState, PortfolioRun, ProviderRun


@dataclass(frozen=True)
class ProviderExecutor:
    provider: str
    callable_name: str
    execute: Callable[..., Any]


class ProviderExecutionEngine:
    """Run explicit provider executors while preserving deterministic fallback."""

    def __init__(self, executors: Mapping[str, ProviderExecutor] | None = None) -> None:
        self.executors = dict(executors or {})

    def run_asset(
        self,
        ticker: str,
        provider_order: tuple[str, ...],
        *args,
        **kwargs,
    ) -> AssetRun:
        runs: list[ProviderRun] = []
        collected = []

        for provider in provider_order:
            executor = self.executors.get(provider)
            if executor is None:
                runs.append(
                    ProviderRun(provider, ExecutionState.SKIPPED, error="no_executor")
                )
                continue

            try:
                value = executor.execute(*args, **kwargs)
                if value is None:
                    value = ()
                if not isinstance(value, (tuple, list)):
                    value = (value,)
                evidence = tuple(value)
                runs.append(
                    ProviderRun(provider, ExecutionState.READY, evidence=evidence)
                )
                collected.extend(evidence)
                if collected:
                    break
            except Exception as exc:  # noqa: BLE001 — isola falha de um provider, permite tentar o proximo
                runs.append(
                    ProviderRun(
                        provider,
                        ExecutionState.FAILED,
                        error=f"{type(exc).__name__}:{exc}",
                    )
                )

        state = (
            ExecutionState.READY
            if collected
            else (
                ExecutionState.FAILED
                if any(r.state == ExecutionState.FAILED for r in runs)
                else ExecutionState.SKIPPED
            )
        )
        return AssetRun(ticker.upper(), state, tuple(runs), tuple(collected))

    def run_portfolio(self, plan: Mapping[str, tuple[str, ...]]) -> PortfolioRun:
        return PortfolioRun(
            tuple(
                self.run_asset(ticker, providers) for ticker, providers in plan.items()
            )
        )
