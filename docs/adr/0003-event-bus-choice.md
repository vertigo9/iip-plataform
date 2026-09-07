# ADR-0003: Async Event Bus Over Message Queue

**Status:** ACCEPTED
**Date:** 2026-07-18
**Authors:** IIP Team

## Context

Inter-module communication can use message queues (Kafka, RabbitMQ) or async events.

## Decision

Use built-in async Event Bus instead of external message queue for v1.0.

## Consequences

- Zero infrastructure dependencies
- Simpler deployment
- Limited scalability (acceptable for v1.0)
- Can migrate to external MQ in v2.0 if needed
