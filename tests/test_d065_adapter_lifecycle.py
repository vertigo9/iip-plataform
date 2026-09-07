from __future__ import annotations

from iip.knowledge.event_adapter import KnowledgeEventAdapter


def test_knowledge_event_adapter_has_runtime_lifecycle() -> None:
    assert callable(getattr(KnowledgeEventAdapter, "register", None))
    assert callable(getattr(KnowledgeEventAdapter, "unregister", None))


def test_runtime_can_start_and_stop_without_adapter_contract_error() -> None:
    from iip.core import Runtime

    ctx = Runtime.start()
    assert ctx.started is True
    assert ctx.knowledge_adapter is not None

    Runtime.stop()
