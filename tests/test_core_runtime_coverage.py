"""
Testes de cobertura para iip.core.Runtime (start/stop).

Runtime é um singleton (_instance/_context são atributos de CLASSE,
compartilhados pelo processo inteiro). Por isso o fixture abaixo salva
e restaura esse estado ao redor de cada teste — sem isso, estes testes
poderiam vazar estado para qualquer outro teste da suíte que também
use iip.core.Runtime.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import iip.core as core_module


@pytest.fixture(autouse=True)
def _isolate_runtime_singleton():
    original_instance = core_module.Runtime._instance
    original_context = core_module.Runtime._context
    core_module.Runtime._instance = None
    core_module.Runtime._context = None
    yield
    core_module.Runtime._instance = original_instance
    core_module.Runtime._context = original_context


def test_start_builds_a_new_context_and_wires_health_checks(monkeypatch):
    fake_settings = SimpleNamespace(obsidian_vault="vault/path")
    monkeypatch.setattr(core_module, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(core_module, "setup_logging", MagicMock())

    fake_health_engine = MagicMock()
    monkeypatch.setattr(
        core_module, "HealthEngine", MagicMock(return_value=fake_health_engine)
    )
    monkeypatch.setattr(core_module, "ConfigurationHealthCheck", MagicMock())
    monkeypatch.setattr(core_module, "FileSystemHealthCheck", MagicMock())

    fake_bridge = MagicMock()
    monkeypatch.setattr(
        core_module, "KnowledgeBridge", MagicMock(return_value=fake_bridge)
    )
    fake_adapter = MagicMock()
    monkeypatch.setattr(
        core_module, "KnowledgeEventAdapter", MagicMock(return_value=fake_adapter)
    )

    ctx = core_module.Runtime.start()

    assert ctx.settings is fake_settings
    assert ctx.health_engine is fake_health_engine
    assert ctx.knowledge_bridge is fake_bridge
    assert ctx.knowledge_adapter is fake_adapter
    assert ctx.started is True
    assert fake_health_engine.register.call_count == 2
    fake_adapter.register.assert_called_once()
    assert core_module.Runtime.get_context() is ctx


def test_start_returns_existing_context_without_reinitializing(monkeypatch):
    existing_ctx = SimpleNamespace(started=True)
    core_module.Runtime._context = existing_ctx
    get_settings_spy = MagicMock()
    monkeypatch.setattr(core_module, "get_settings", get_settings_spy)

    result = core_module.Runtime.start()

    assert result is existing_ctx
    get_settings_spy.assert_not_called()


def test_start_reinitializes_when_previous_context_was_stopped(monkeypatch):
    stopped_ctx = SimpleNamespace(started=False)
    core_module.Runtime._context = stopped_ctx

    fake_settings = SimpleNamespace(obsidian_vault="vault/path")
    monkeypatch.setattr(core_module, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(core_module, "setup_logging", MagicMock())
    monkeypatch.setattr(
        core_module, "HealthEngine", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr(core_module, "ConfigurationHealthCheck", MagicMock())
    monkeypatch.setattr(core_module, "FileSystemHealthCheck", MagicMock())
    monkeypatch.setattr(
        core_module, "KnowledgeBridge", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        core_module, "KnowledgeEventAdapter", MagicMock(return_value=MagicMock())
    )

    ctx = core_module.Runtime.start()

    assert ctx is not stopped_ctx
    assert ctx.started is True


def test_stop_unregisters_adapter_and_marks_context_stopped():
    fake_adapter = MagicMock()
    ctx = SimpleNamespace(knowledge_adapter=fake_adapter, started=True)
    core_module.Runtime._context = ctx

    core_module.Runtime.stop()

    fake_adapter.unregister.assert_called_once()
    assert ctx.started is False


def test_stop_is_a_noop_when_context_has_no_adapter():
    ctx = SimpleNamespace(knowledge_adapter=None, started=True)
    core_module.Runtime._context = ctx

    core_module.Runtime.stop()  # não deve levantar exceção

    assert ctx.started is False


def test_stop_is_a_noop_when_there_is_no_context():
    core_module.Runtime._context = None

    core_module.Runtime.stop()  # não deve levantar exceção

    assert core_module.Runtime._context is None


def test_runtime_is_a_singleton():
    first = core_module.Runtime()
    second = core_module.Runtime()

    assert first is second
