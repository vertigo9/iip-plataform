from iip.config import get_settings
from iip.metrics import MetricsEngine


def test_increment_counter():
    MetricsEngine.increment("test_counter_2")
    assert MetricsEngine.get_counter("test_counter_2") == 1
    MetricsEngine.increment("test_counter_2", 5)
    assert MetricsEngine.get_counter("test_counter_2") == 6
    MetricsEngine.reset_counters()


def test_decrement_counter():
    MetricsEngine.increment("test_counter_3")
    MetricsEngine.decrement("test_counter_3")
    assert MetricsEngine.get_counter("test_counter_3") == 0
    MetricsEngine.reset_counters()


def test_gauge_set_get():
    MetricsEngine.gauge("test_gauge_2", 42.5)
    assert MetricsEngine.get_gauge("test_gauge_2") == 42.5
    MetricsEngine.gauge("test_gauge_2", 100)
    assert MetricsEngine.get_gauge("test_gauge_2") == 100


def test_architecture_metrics_structure():
    settings = get_settings()
    metrics = MetricsEngine.architecture_metrics(settings)
    assert "source_files" in metrics
    assert "total_lines" in metrics
    assert "test_files" in metrics
    assert isinstance(metrics["source_files"], int)


def test_operational_metrics_structure():
    ops = MetricsEngine.operational_metrics()
    assert "counters" in ops
    assert "gauges" in ops
    assert isinstance(ops["counters"], dict)
    assert isinstance(ops["gauges"], dict)


def test_summary_complete():
    settings = get_settings()
    summary = MetricsEngine.summary(settings)
    assert "architecture" in summary
    assert "operational" in summary
    assert "platform_version" in summary
