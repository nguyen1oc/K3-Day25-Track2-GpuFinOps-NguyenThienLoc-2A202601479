"""Extension-only coverage; the instructor's original tests remain unchanged."""
import copy
from pathlib import Path

import pytest

from finops.reasoning import analyze_reasoning, budget_report
from missions import m2_inference_levers, m5_report


PRICES = {"small": (0.20, 0.40)}


def request(output=100, reasoning=False, batch=False, cached=0):
    # CSV-shaped input also catches bool("0") mistakes.
    return {"input_tokens": "1000", "output_tokens": str(output),
            "cached_input_tokens": str(cached), "route_tier": "small",
            "is_reasoning": str(int(reasoning)), "is_batch": str(int(batch))}


def test_group_costs_use_cache_batch_and_energy_not_a_dollar_multiplier():
    audit = analyze_reasoning([
        request(), request(output=600, reasoning=True, batch=True, cached=800)], PRICES)
    normal, reasoning = audit["groups"]["normal"], audit["groups"]["reasoning"]
    assert normal["cost_usd"] == pytest.approx(0.00024)
    assert reasoning["cost_usd"] == pytest.approx((0.000056 + 0.00024) * 0.5)
    assert normal["energy_wh"] == pytest.approx(0.33)
    assert reasoning["energy_wh"] == pytest.approx(38.4)
    assert reasoning["same_tokens_normal_wh"] == pytest.approx(0.48)
    assert reasoning["traffic_pct"] == 50
    for metric in ("tokens", "cost_usd", "energy_wh"):
        assert audit["current"][metric] == pytest.approx(normal[metric] + reasoning[metric])


def test_cap_keeps_longest_outputs_and_preserves_input_rows():
    rows = [request(), request(600, True), request(1200, True), request(300, True)]
    original = copy.deepcopy(rows)
    audit = analyze_reasoning(rows, PRICES, cap_fractions=(0.25,))
    capped = audit["scenarios"][0]
    assert rows == original
    assert capped["requests"] == 4  # No dropped traffic.
    assert capped["reasoning_requests"] == 1
    assert capped["rerouted_requests"] == 2
    assert capped["tokens"] == 4000 + 100 + 100 + 1200 + 50
    assert capped["saved_usd"] == pytest.approx(750 * 0.40 / 1e6)
    assert capped["saved_wh"] == pytest.approx(68.955)


@pytest.mark.parametrize("cap", [0.10, 0.50, 1.0])
def test_cap_at_or_above_observed_share_does_not_increase_reasoning(cap):
    rows = [request(600, True)] + [request() for _ in range(9)]
    audit = analyze_reasoning(rows, PRICES, cap_fractions=(cap,))
    capped = audit["scenarios"][0]
    assert capped["reasoning_requests"] == 1
    assert capped["rerouted_requests"] == 0
    assert capped["saved_usd"] == 0
    assert capped["saved_wh"] == 0


def test_zero_cap_preserves_cache_and_batch_and_rounds_up_outputs():
    audit = analyze_reasoning(
        [request(601, True, batch=True, cached=800)], PRICES, cap_fractions=(0.0,))
    capped = audit["scenarios"][0]
    assert capped["reasoning_requests"] == 0
    assert capped["tokens"] == 1101
    assert capped["cost_usd"] == pytest.approx((0.000056 + 101 * 0.4 / 1e6) * 0.5)
    assert capped["energy_wh"] == pytest.approx(1101 * 0.3 / 1000)


@pytest.mark.parametrize("rows", [[], [request()]])
def test_empty_or_normal_only_traffic_has_no_reasoning_savings(rows):
    audit = analyze_reasoning(rows, PRICES)
    assert audit["groups"]["reasoning"]["requests"] == 0
    assert all(scenario["saved_wh"] == 0 for scenario in audit["scenarios"])
    assert all(scenario["saved_usd"] == 0 for scenario in audit["scenarios"])
    assert "Extension 4" in budget_report(audit)


@pytest.mark.parametrize("kwargs", [
    {"cap_fractions": (-0.1,)}, {"cap_fractions": (1.1,)},
    {"cap_fractions": (float("nan"),)}, {"reasoning_output_multiplier": 0},
])
def test_invalid_scenario_parameters_are_rejected(kwargs):
    with pytest.raises(ValueError):
        analyze_reasoning([], PRICES, **kwargs)


def test_real_m2_totals_reconcile_and_m5_persists_extension():
    m2 = m2_inference_levers.run(verbose=False)
    audit = m2["reasoning_budget"]
    assert round(audit["current"]["cost_usd"], 2) == m2["optimized_daily"]
    assert audit["current"]["tokens"] == m2["total_tokens"]
    assert round(audit["current"]["per_million_usd"], 3) == m2["optimized_per_m"]
    m5_report.run(verbose=False)
    path = Path(m5_report.ROOT) / "outputs" / "report.md"
    text = path.read_text(encoding="utf-8")
    assert budget_report(audit) in text
    assert f"${m2['optimized_per_m']:.3f}/1M-token" in text
