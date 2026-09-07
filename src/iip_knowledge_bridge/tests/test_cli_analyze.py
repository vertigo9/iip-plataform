import json

from click.testing import CliRunner

from iip.cli.main import cli


def test_analyze_template_generates_valid_json(tmp_path):
    runner = CliRunner()
    out_file = tmp_path / "template.json"
    result = runner.invoke(
        cli, ["analyze-template", "--type", "fii", "-o", str(out_file)]
    )

    assert result.exit_code == 0
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["symbol"] == "TICKER11"
    assert "occupancy_rate" in data["financials"]


def test_analyze_template_covers_all_asset_types():
    runner = CliRunner()
    for asset_type in ("equity", "fii", "infra", "agro"):
        result = runner.invoke(cli, ["analyze-template", "--type", asset_type])
        assert result.exit_code == 0
        assert "financials" in result.output


def test_analyze_runs_end_to_end_table_format(tmp_path):
    runner = CliRunner()
    data_file = tmp_path / "asset.json"
    data_file.write_text(
        json.dumps(
            {
                "sector": "Logística",
                "industry": "Galpões",
                "financials": {"occupancy_rate": 0.97, "dividend_yield": 0.09},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli, ["analyze", "HGLG11", "--type", "fii", "--data-file", str(data_file)]
    )

    assert result.exit_code == 0
    assert "HGLG11" in result.output
    assert "Overall score" in result.output
    assert "Recommendation" in result.output


def test_analyze_json_format_is_valid_and_saveable(tmp_path):
    runner = CliRunner()
    data_file = tmp_path / "asset.json"
    data_file.write_text(
        json.dumps({"sector": "S", "industry": "I", "financials": {}}), encoding="utf-8"
    )
    out_file = tmp_path / "report.json"

    result = runner.invoke(
        cli,
        [
            "analyze",
            "TEST01",
            "--type",
            "equity",
            "--data-file",
            str(data_file),
            "--format",
            "json",
            "--output",
            str(out_file),
        ],
    )

    assert result.exit_code == 0
    report = json.loads(out_file.read_text(encoding="utf-8"))
    assert report["asset_symbol"] == "TEST01"
    assert report["asset_type"] == "equity"
    assert "overall_score" in report


def test_analyze_rejects_invalid_json(tmp_path):
    runner = CliRunner()
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    result = runner.invoke(
        cli, ["analyze", "X", "--type", "equity", "--data-file", str(bad_file)]
    )

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_analyze_rejects_missing_required_fields(tmp_path):
    runner = CliRunner()
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"financials": {}}), encoding="utf-8")

    result = runner.invoke(
        cli, ["analyze", "X", "--type", "equity", "--data-file", str(incomplete)]
    )

    assert result.exit_code == 1
    assert "Missing required field" in result.output
