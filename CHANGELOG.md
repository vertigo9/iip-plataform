# Changelog

All notable changes to IIP Platform will be documented in this file.

## [0.1.0-final] — 2026-07-19

### Added
- Core Runtime (lifecycle, singleton, ApplicationContext)
- Configuration Manager (pydantic-settings, env vars, .env files)
- Structured Logging (structlog JSON format)
- Exception Framework (hierarchical error classes)
- Event Bus (async pub/sub pattern)
- Module Registry (automatic module discovery)
- Blueprint Manager (capability declarations)
- Version Manager (semantic versioning)
- Metrics Engine (architecture + operational metrics)
- Replication Engine (RFC→ADR→Replicate→Certify pipeline)
- Synchronization Engine (consistency detection)
- Health Engine (7 health checks)
- CLI (version, health, status, modules commands)
- Complete test suite (28 tests, 68% coverage)
- Docker support (production-ready)
- Documentation (README, docs/, ADRs)

### Fixed
- Asyncio event loop issues in tests
- Module registry registration without blocking
- Health check aggregation
- CLI command routing

### Changed
- Simplified Event Bus for better testability
- Removed blocking async calls from synchronous paths
- Improved error messages and logging

## [0.1.0-beta] — 2026-07-18

### Added
- Initial project structure
- pyproject.toml with all dependencies
- Basic exception hierarchy
- First version of configuration manager

## [0.1.0-alpha] — 2026-07-17

### Added
- Project skeleton created via PowerShell script
- First 2 tests passing
