from pathlib import Path
from types import SimpleNamespace

from iip.core import ApplicationContext, Runtime
from iip.export import BatchExporter, ReportExporter


def fake_report():
    pillar = lambda value, score, weight, indicators: SimpleNamespace(
        pillar=SimpleNamespace(value=value),
        score=score,
        weight=weight,
        indicators=indicators,
    )
    return SimpleNamespace(
        asset_symbol="CPFE3",
        asset_type="equity",
        overall_score=82.4,
        recommendation="Strong Buy",
        risk_level="low",
        pillar_scores=(
            pillar("business_model", 85, 0.5, {"ROIC": 20}),
            pillar("growth", 60, 0.5, {"Growth": 10}),
        ),
        to_dict=lambda: {
            "asset_symbol": "CPFE3",
            "overall_score": 82.4,
        },
    )


def test_score_color_all_bands():
    assert ReportExporter._get_score_color(90) == "#28a745"
    assert ReportExporter._get_score_color(70) == "#17a2b8"
    assert ReportExporter._get_score_color(55) == "#ffc107"
    assert ReportExporter._get_score_color(40) == "#fd7e14"
    assert ReportExporter._get_score_color(20) == "#dc3545"


def test_recommendation_and_pillar_colors():
    assert ReportExporter._get_recommendation_bg("Strong Buy") == "#28a745"
    assert ReportExporter._get_recommendation_bg("Unknown") == "#6c757d"
    assert ReportExporter._get_pillar_color(70) == "#28a745"
    assert ReportExporter._get_pillar_color(50) == "#ffc107"
    assert ReportExporter._get_pillar_color(10) == "#dc3545"


def test_json_export_and_write(tmp_path):
    report = fake_report()
    path = tmp_path / "r.json"
    result = ReportExporter.to_json(report, str(path))
    assert '"CPFE3"' in result
    assert path.read_text(encoding="utf-8") == result


def test_html_export_and_write(tmp_path):
    report = fake_report()
    path = tmp_path / "r.html"
    result = ReportExporter.to_html(report, str(path))
    assert "<html>" in result
    assert "CPFE3" in result
    assert "Strong Buy" in result
    assert path.read_text(encoding="utf-8") == result


def test_csv_export_and_write(tmp_path):
    report = fake_report()
    path = tmp_path / "r.csv"
    result = ReportExporter.to_csv(report, str(path))
    assert '"Asset Symbol",CPFE3' in result
    assert "business_model" in result
    assert path.read_text(encoding="utf-8") == result


def test_batch_export(tmp_path):
    result = BatchExporter.export_all([fake_report()], str(tmp_path / "reports"))
    assert len(result["json"]) == 1
    assert len(result["html"]) == 1
    assert len(result["csv"]) == 1
    assert Path(result["json"][0]).exists()
    assert Path(result["html"][0]).exists()
    assert Path(result["csv"][0]).exists()


def test_application_context_health():
    expected = object()
    ctx = ApplicationContext(
        settings=object(),
        health_engine=SimpleNamespace(run_all=lambda: expected),
        started=False,
    )
    assert ctx.health() is expected


def test_runtime_singleton_access():
    Runtime._instance = None
    Runtime._context = None
    first = Runtime()
    second = Runtime()
    assert first is second
    assert Runtime.get_context() is None
