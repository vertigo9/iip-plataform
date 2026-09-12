from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iip.analysis import AnalysisReport


class ReportExporter:
    """Export analysis reports to various formats."""

    @staticmethod
    def to_json(report: AnalysisReport, output_path: str | None = None) -> str:
        """Export report to JSON format."""
        data = report.to_dict()
        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_str)

        return json_str

    @staticmethod
    def to_html(report: AnalysisReport, output_path: str | None = None) -> str:
        """Export report to styled HTML (printable as PDF)."""
        score_color = ReportExporter._get_score_color(report.overall_score)
        rec_bg = ReportExporter._get_recommendation_bg(report.recommendation)

        html = (
            """<html>
<head>
    <meta charset="UTF-8">
    <title>Atlas Monitor Report - """
            + report.asset_symbol
            + """</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f0f0f0;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .header .subtitle { opacity: 0.9; font-size: 14px; }
        .score-section {
            display: flex;
            justify-content: space-around;
            align-items: center;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        .score-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border: 5px solid """
            + score_color
            + """;
        }
        .score-number {
            font-size: 42px;
            font-weight: bold;
            color: """
            + score_color
            + """;
        }
        .score-label { font-size: 12px; color: #666; margin-top: 5px; }
        .recommendation { text-align: center; padding: 20px; }
        .recommendation-badge {
            display: inline-block;
            padding: 10px 30px;
            border-radius: 25px;
            font-size: 18px;
            font-weight: bold;
            color: white;
            background: """
            + rec_bg
            + """;
        }
        .risk-level { text-align: center; margin-top: 15px; color: #666; }
        .pillars-section { padding: 30px; }
        .pillar-item {
            margin-bottom: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .pillar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .pillar-name { font-weight: 600; font-size: 16px; color: #333; }
        .pillar-score { font-size: 20px; font-weight: bold; }
        .progress-bar {
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 4px;
        }
        .indicators {
            margin-top: 10px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }
        .indicator {
            font-size: 12px;
            color: #666;
            background: white;
            padding: 5px 10px;
            border-radius: 4px;
        }
        .footer {
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 12px;
            background: #f8f9fa;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>"""
            + report.asset_symbol
            + """</h1>
            <div class="subtitle">"""
            + report.asset_type.upper()
            + """ - Atlas Monitor V11.0</div>
        </div>
        
        <div class="score-section">
            <div class="score-circle">
                <span class="score-number">"""
            + str(round(report.overall_score, 1))
            + """</span>
                <span class="score-label">SCORE GLOBAL</span>
            </div>
            <div style="flex: 1; margin-left: 40px;">
                <div class="recommendation">
                    <div class="recommendation-badge">"""
            + report.recommendation
            + """</div>
                </div>
                <div class="risk-level">
                    <strong>Risco:</strong> """
            + report.risk_level
            + """
                </div>
            </div>
        </div>
        
        <div class="pillars-section">
            <h2 style="margin-bottom: 20px; color: #333;">Analysis by Pillar</h2>
"""
        )

        # Add pillars
        for ps in report.pillar_scores:
            pillar_color = ReportExporter._get_pillar_color(ps.score)
            indicators_html = "".join(
                [
                    f'<div class="indicator"><strong>{k}:</strong> {v}</div>'
                    for k, v in ps.indicators.items()
                ]
            )

            pillar_name = ps.pillar.value.replace("_", " ").title()
            html += f"""
            <div class="pillar-item" style="border-left-color: {pillar_color};">
                <div class="pillar-header">
                    <span class="pillar-name">{pillar_name}</span>
                    <span class="pillar-score" style="color: {pillar_color};">{ps.score:.1f}/100</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {ps.score}%; background: {pillar_color};"></div>
                </div>
                <div class="indicators">{indicators_html}</div>
            </div>"""

        html += f"""
        </div>
        
        <div class="footer">
            Report generated at {datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")}<br>
            IIP Platform - Institutional Investment Platform v2.0.0
        </div>
    </div>
</body>
</html>"""

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        return html

    @staticmethod
    def to_csv(report: AnalysisReport, output_path: str | None = None) -> str:
        """Export report to CSV format."""
        lines = [
            "Attribute,Value",
            f'"Asset Symbol",{report.asset_symbol}',
            f'"Asset Type",{report.asset_type}',
            f'"Overall Score",{report.overall_score}',
            f'"Recommendation",{report.recommendation}',
            f'"Risk Level",{report.risk_level}',
            "",
            "Pillar,Score,Weight,Details",
        ]

        for ps in report.pillar_scores:
            details = "; ".join([f"{k}={v}" for k, v in ps.indicators.items()])
            lines.append(f'"{ps.pillar.value}",{ps.score},{ps.weight},"{details}"')

        csv_str = "\n".join(lines)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(csv_str)

        return csv_str

    @staticmethod
    def _get_score_color(score: float) -> str:
        if score >= 80:
            return "#28a745"
        elif score >= 65:
            return "#17a2b8"
        elif score >= 50:
            return "#ffc107"
        elif score >= 35:
            return "#fd7e14"
        else:
            return "#dc3545"

    @staticmethod
    def _get_recommendation_bg(rec: str) -> str:
        colors = {
            "Strong Buy": "#28a745",
            "Buy": "#17a2b8",
            "Hold": "#ffc107",
            "Reduce": "#fd7e14",
            "Sell": "#dc3545",
        }
        return colors.get(rec, "#6c757d")

    @staticmethod
    def _get_pillar_color(score: float) -> str:
        if score >= 70:
            return "#28a745"
        elif score >= 50:
            return "#ffc107"
        else:
            return "#dc3545"


class BatchExporter:
    """Batch export multiple reports."""

    @staticmethod
    def export_all(reports, directory: str = "reports") -> dict:
        Path(directory).mkdir(exist_ok=True)

        results: dict[str, list[str]] = {"json": [], "html": [], "csv": []}

        for report in reports:
            symbol = report.asset_symbol.replace(".", "_").replace("/", "_")

            json_path = f"{directory}/{symbol}_analysis.json"
            ReportExporter.to_json(report, json_path)
            results["json"].append(json_path)

            html_path = f"{directory}/{symbol}_analysis.html"
            ReportExporter.to_html(report, html_path)
            results["html"].append(html_path)

            csv_path = f"{directory}/{symbol}_analysis.csv"
            ReportExporter.to_csv(report, csv_path)
            results["csv"].append(csv_path)

        return results
