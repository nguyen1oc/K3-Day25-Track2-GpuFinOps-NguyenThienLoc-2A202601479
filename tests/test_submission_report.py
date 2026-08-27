"""Additional checks for reproducible submission artifacts; original tests unchanged."""
from pathlib import Path
import unicodedata

import pytest

from finops import report, submission
from missions import m2_inference_levers, m5_report


def test_sequential_attribution_reconciles_with_existing_m2_totals():
    result = m2_inference_levers.run(verbose=False)
    stages = result["lever_breakdown"]
    assert round(stages[0]["daily_usd"], 2) == result["baseline_daily"]
    assert round(stages[-1]["daily_usd"], 2) == result["optimized_daily"]
    assert sum(s["marginal_savings_usd"] for s in stages) == pytest.approx(
        stages[0]["daily_usd"] - stages[-1]["daily_usd"])
    for before, after in zip(stages, stages[1:]):
        assert after["daily_usd"] <= before["daily_usd"]
        assert after["per_million_usd"] == pytest.approx(after["daily_usd"] / result["total_tokens"] * 1e6)


def test_m5_regenerates_identified_report_and_writeup_with_analysis():
    result = m5_report.run(verbose=False)
    directory = Path(m5_report.ROOT) / "outputs"
    report_text = (directory / "report.md").read_text(encoding="utf-8")
    writeup = (directory / "writeup.md").read_text(encoding="utf-8")
    for text in (report_text, writeup):
        assert f"${result['baseline_monthly']:,.0f}" in text
        assert f"${result['optimized_monthly']:,.0f}" in text
    assert submission.REPORT_IDENTITY in report_text
    assert submission.IDENTITY in writeup
    assert "Technical analysis and recommendations" in report_text
    assert "Incremental savings USD/day" in report_text
    assert "## Savings chart" in report_text
    # Preserve the student's accented name, but prevent Vietnamese prose from
    # reappearing in the English report when M5 regenerates it.
    prose = report_text.replace(submission.STUDENT, "")
    assert not any(ord(char) > 127 and "LATIN" in unicodedata.name(char, "") for char in prose)
    assert "Ba hành động đầu tiên" in writeup
    assert "Ex4" in writeup and "Ex5" in writeup


def test_waterfall_reductions_start_at_previous_total(monkeypatch, tmp_path):
    from matplotlib.axes import Axes
    original = Axes.bar
    bars = []

    def record_bar(self, x, height, *args, **kwargs):
        bars.append((x, height, kwargs.get("bottom", 0)))
        return original(self, x, height, *args, **kwargs)

    monkeypatch.setattr(Axes, "bar", record_bar)
    levers = {"inference": 100, "purchasing": 200, "right-size": 30, "idle": 20}
    target = tmp_path / "waterfall.png"
    assert report.savings_waterfall(levers, str(target), baseline_usd=1000) == str(target)
    assert target.is_file()
    assert bars == [(0, 1000, 0), (1, 100, 900), (2, 200, 700),
                    (3, 30, 670), (4, 20, 650), (5, 650, 0)]
