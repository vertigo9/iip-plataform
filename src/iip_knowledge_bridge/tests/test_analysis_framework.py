from iip.analysis import AnalysisReport, Pillar, PillarScore


def test_pillar_enum_exists():
    assert Pillar.BUSINESS_MODEL.value == "business_model"
    assert Pillar.MOAT.value == "moat"
    assert len(list(Pillar)) == 9


def test_pillar_score_creation():
    score = PillarScore(
        pillar=Pillar.BUSINESS_MODEL, score=75.0, weight=0.15, indicators={"ROIC": 12.0}
    )
    assert score.pillar == Pillar.BUSINESS_MODEL
    assert score.score == 75.0
    assert score.weighted_score() == 11.25


def test_analysis_report_initialization():
    report = AnalysisReport(asset_symbol="PETR4.SA", asset_type="equity")
    assert report.asset_symbol == "PETR4.SA"
    assert report.asset_type == "equity"
    assert report.overall_score == 0.0


def test_add_pillar_to_report():
    report = AnalysisReport(asset_symbol="VALE3.SA", asset_type="equity")
    score = PillarScore(pillar=Pillar.GROWTH, score=80.0, weight=0.12)
    report.add_pillar(score)
    assert len(report.pillar_scores) == 1
    assert report.pillar_scores[0].score == 80.0


def test_calculate_overall_score():
    report = AnalysisReport(asset_symbol="ABCD3.SA", asset_type="equity")
    report.add_pillar(
        PillarScore(pillar=Pillar.BUSINESS_MODEL, score=100.0, weight=0.5)
    )
    report.add_pillar(PillarScore(pillar=Pillar.MOAT, score=50.0, weight=0.5))
    overall = report.calculate_overall()
    assert overall == 75.0


def test_set_recommendation_strong_buy():
    report = AnalysisReport(asset_symbol="STRONG.SA", asset_type="equity")
    report.add_pillar(PillarScore(pillar=Pillar.BUSINESS_MODEL, score=90.0, weight=1.0))
    report.calculate_overall()
    report.set_recommendation()
    assert report.recommendation == "Strong Buy"
    assert report.risk_level == "Low"


def test_set_recommendation_sell():
    report = AnalysisReport(asset_symbol="WEAK.SA", asset_type="equity")
    report.add_pillar(PillarScore(pillar=Pillar.BUSINESS_MODEL, score=20.0, weight=1.0))
    report.calculate_overall()
    report.set_recommendation()
    assert report.recommendation == "Sell"
    assert report.risk_level == "High"


def test_report_to_dict():
    report = AnalysisReport(asset_symbol="TEST.SA", asset_type="equity")
    report.add_pillar(
        PillarScore(pillar=Pillar.BUSINESS_MODEL, score=80.0, weight=0.15)
    )
    report.calculate_overall()
    report.set_recommendation()

    data = report.to_dict()
    assert data["asset_symbol"] == "TEST.SA"
    assert data["asset_type"] == "equity"
    assert "overall_score" in data
    assert "recommendation" in data
    assert "pillar_scores" in data
    assert len(data["pillar_scores"]) == 1
