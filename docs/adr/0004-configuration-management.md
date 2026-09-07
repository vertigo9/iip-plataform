# ADR-0004: pydantic-settings for Configuration

**Status:** ACCEPTED
**Date:** 2026-07-17
**Authors:** IIP Team

## Context

Configuration can use environment variables, .env files, YAML, or databases.

## Decision

Use pydantic-settings for unified configuration management.

## Consequences

- Type-safe configuration
- Environment variable support
- .env file compatibility
- Validation at startup
