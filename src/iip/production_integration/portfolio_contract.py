"""Production portfolio contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioIdentity:
    portfolio_id: str
    owner_scope: str
    version: int


@dataclass(frozen=True)
class PortfolioContract:
    identity: PortfolioIdentity
    tickers: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return (
            bool(self.identity.portfolio_id)
            and bool(self.identity.owner_scope)
            and self.identity.version > 0
            and len(self.tickers) == len(set(self.tickers))
        )


def normalize(
    identity: PortfolioIdentity, tickers: tuple[str, ...]
) -> PortfolioContract:
    normalized = tuple(
        sorted({ticker.upper().strip() for ticker in tickers if ticker.strip()})
    )
    return PortfolioContract(identity, normalized)
