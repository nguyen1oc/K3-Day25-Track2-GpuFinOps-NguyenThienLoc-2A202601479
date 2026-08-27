"""Additional Extension 5 tests; instructor tests are untouched."""
import copy
from pathlib import Path

import pytest

from missions.ex5_carbon_scheduling import analyze, format_report, run
from missions import m5_report


def test_one_job_matches_manual_calculation_and_excludes_non_interruptible():
    jobs = [
        {"job_id": "train", "gpu_type": "H100", "num_gpus": "8",
         "hours_per_day": "20", "days": "14", "interruptible": "1"},
        {"job_id": "skip", "interruptible": "0"},
    ]
    original = copy.deepcopy(jobs)
    result = analyze(jobs, {"H100": {"watts": "700"}})
    assert jobs == original
    assert result["excluded_jobs"] == 1
    assert result["total_energy_wh"] == 1568000
    job = result["jobs"][0]
    assert job["baseline_carbon_g"] == pytest.approx(595840)
    assert job["cleanest_carbon_g"] == pytest.approx(47040)
    assert result["saved_carbon_g"] == pytest.approx(548800)
    assert result["regions"]["europe-north1"]["electricity_usd"] == pytest.approx(141.12)
    assert result["saved_electricity_usd"] == pytest.approx(47.04)


def test_balanced_policy_is_cheapest_region_meeting_explicit_limit():
    default = analyze([], {})
    assert default["cleanest_region"] == "europe-north1"
    assert default["cheapest_region"] == default["balanced_region"] == "us-east-wa"
    assert analyze([], {}, carbon_limit=50)["balanced_region"] == "europe-north1"
    assert analyze([], {}, carbon_limit=20)["balanced_region"] is None


def test_empty_eligible_set_has_zero_savings_without_division_errors():
    result = analyze([], {})
    assert result["total_energy_wh"] == 0
    assert result["saved_carbon_pct"] == result["saved_electricity_pct"] == 0
    assert "Eligible jobs: 0" in format_report(result)


@pytest.mark.parametrize("kwargs", [{"baseline_region": "unknown"}, {"carbon_limit": -1}])
def test_invalid_region_or_policy_is_not_silently_defaulted(kwargs):
    with pytest.raises(ValueError):
        analyze([], {}, **kwargs)


def test_real_jobs_reconcile_with_regional_totals():
    result = run(verbose=False)
    assert len(result["jobs"]) == 5
    assert result["total_energy_wh"] == pytest.approx(1789000)
    assert sum(job["saved_carbon_g"] for job in result["jobs"]) == pytest.approx(result["saved_carbon_g"])
    assert result["saved_carbon_g"] == pytest.approx(626150)
    assert result["saved_electricity_usd"] == pytest.approx(53.67)
    assert len(result["regions"]) == 5
    assert "NOT a normalized month" in format_report(result)


def test_m5_persists_carbon_scenario_without_changing_monthly_savings():
    result = m5_report.run(verbose=False)
    text = (Path(m5_report.ROOT) / "outputs" / "report.md").read_text(encoding="utf-8")
    assert format_report(run(verbose=False)) in text
    assert "Lowest-carbon region: europe-north1" in text
    assert "Lowest electricity-price region: us-east-wa" in text
    assert "Cheapest+cleanest" not in text
    assert "Extension 4" in text
    # Regression: Ex5 is an independent electricity scenario, not a new rental lever.
    assert result["levers"] == {
        "Inference (cascade/cache/batch)": 1212,
        "Purchasing (spot/reserved)": 10040,
        "Right-size util-lies": 655,
        "Kill idle GPUs": 600,
    }
