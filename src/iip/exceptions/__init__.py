"""IIP Exception Framework."""

from __future__ import annotations


class IIPException(Exception):
    """Base exception for all IIP errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - {self.details}"
        return self.message


class ConfigurationException(IIPException):
    pass


class ModuleException(IIPException):
    def __init__(
        self, message: str, *, module: str | None = None, details: str | None = None
    ) -> None:
        super().__init__(message, details=details)
        self.module = module


class ValidationException(IIPException):
    def __init__(
        self, message: str, *, field: str | None = None, details: str | None = None
    ) -> None:
        super().__init__(message, details=details)
        self.field = field


class EventException(IIPException):
    pass


class HealthException(IIPException):
    pass


class InfrastructureException(IIPException):
    pass
