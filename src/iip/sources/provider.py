"""Contracts for IIP document providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .registry import AssetRef


class DocumentProvider(ABC):
    """Base contract for provider-specific document ingestion."""

    provider_name: str

    @abstractmethod
    def supports(self, asset: AssetRef) -> bool:
        """Return whether this provider handles the given asset."""

    @abstractmethod
    def discover(self, asset: AssetRef, years: range):
        """Discover documents for an asset and year range."""
