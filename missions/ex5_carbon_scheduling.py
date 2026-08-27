"""Extension 5: compare modeled electricity cost and carbon across regions.

Run: python missions/ex5_carbon_scheduling.py
Read-only: does not change workloads, existing missions, or report.md.
"""
from __future__ import annotations

import math
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from finops import sustainability
from missions._common import catalog_by_type, load_csv


def analyze(workloads: list[dict], catalog: dict, baseline_region: str = "us-east-1",
            carbon_limit: float = 100.0) -> dict:
    """Estimate GPU-only energy over each eligible job's actual duration.

    Balanced policy: minimize electricity price subject to carbon intensity
    <= carbon_limit gCO2e/kWh. This is a proposed policy, not a measured optimum.
    """
    regions = sorted(set(sustainability.REGION_CARBON) & set(sustainability.REGION_PRICE_KWH))
    if baseline_region not in regions:
        raise ValueError("Baseline region must have both price and carbon data")
    if not math.isfinite(carbon_limit) or carbon_limit < 0:
        raise ValueError("carbon_limit must be finite and nonnegative")
    cleanest = min(regions, key=lambda region: sustainability.REGION_CARBON[region])
    cheapest = min(regions, key=lambda region: sustainability.REGION_PRICE_KWH[region])
    eligible_regions = [region for region in regions
                        if sustainability.REGION_CARBON[region] <= carbon_limit]
    balanced = min(eligible_regions, key=lambda region: sustainability.REGION_PRICE_KWH[region]) if eligible_regions else None

    jobs = []
    for job in workloads:
        if int(job["interruptible"]) != 1:
            continue
        watts = float(catalog[job["gpu_type"]]["watts"])
        count = int(job["num_gpus"])
        hours = float(job["hours_per_day"])
        days = float(job["days"])
        if any(not math.isfinite(value) or value < 0 for value in (watts, count, hours, days)):
            raise ValueError("Power, GPU count and duration must be finite and nonnegative")
        # Use the job's own days, not M3's 30-day normalization.
        energy_wh = watts * count * hours * days
        baseline_carbon = sustainability.carbon_g(energy_wh, baseline_region)
        cleanest_carbon = sustainability.carbon_g(energy_wh, cleanest)
        jobs.append({
            "job_id": job["job_id"], "gpu_type": job["gpu_type"],
            "num_gpus": count, "hours_per_day": hours, "days": days,
            "energy_wh": energy_wh, "baseline_carbon_g": baseline_carbon,
            "cleanest_carbon_g": cleanest_carbon,
            "saved_carbon_g": baseline_carbon - cleanest_carbon,
        })

    total_wh = sum(job["energy_wh"] for job in jobs)
    totals = {
        region: {"price_per_kwh": sustainability.REGION_PRICE_KWH[region],
                 "carbon_per_kwh": sustainability.REGION_CARBON[region],
                 "electricity_usd": sustainability.energy_cost_usd(total_wh, region),
                 "carbon_g": sustainability.carbon_g(total_wh, region)}
        for region in regions
    }
    base, clean = totals[baseline_region], totals[cleanest]
    saved_carbon = base["carbon_g"] - clean["carbon_g"]
    saved_electricity = base["electricity_usd"] - clean["electricity_usd"]
    return {
        "jobs": jobs, "excluded_jobs": len(workloads) - len(jobs),
        "total_energy_wh": total_wh, "regions": totals,
        "baseline_region": baseline_region, "cleanest_region": cleanest,
        "cheapest_region": cheapest, "balanced_region": balanced,
        "carbon_limit": carbon_limit, "saved_carbon_g": saved_carbon,
        "saved_carbon_pct": 100 * saved_carbon / base["carbon_g"] if base["carbon_g"] else 0.0,
        "saved_electricity_usd": saved_electricity,
        "saved_electricity_pct": 100 * saved_electricity / base["electricity_usd"] if base["electricity_usd"] else 0.0,
    }


def format_report(result: dict) -> str:
    """Render results without rounding until display; all amounts are estimates."""
    lines = [
        "## Extension 5 - Carbon-aware scheduling", "",
        f"Eligible jobs: {len(result['jobs'])}; excluded non-interruptible jobs: {result['excluded_jobs']}.",
        "Period: each job's own duration (days column), NOT a normalized month.",
        "Energy = catalog watts x GPU count x hours/day x job days.",
        f"Total estimated GPU energy: {result['total_energy_wh'] / 1000:,.2f} kWh.", "",
        f"### Per-job carbon: {result['baseline_region']} -> {result['cleanest_region']}", "",
        "| Job | Days | Energy kWh | Baseline gCO2e | Cleanest gCO2e | Saved gCO2e |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for job in result["jobs"]:
        lines.append(
            f"| {job['job_id']} | {job['days']:g} | {job['energy_wh'] / 1000:,.2f} | "
            f"{job['baseline_carbon_g']:,.2f} | {job['cleanest_carbon_g']:,.2f} | {job['saved_carbon_g']:,.2f} |")
    lines += ["", "### Same eligible jobs in all five catalog regions", "",
              "| Region | USD/kWh | gCO2e/kWh | Electricity USD | Carbon gCO2e |",
              "|---|---:|---:|---:|---:|"]
    for region, total in result["regions"].items():
        lines.append(
            f"| {region} | {total['price_per_kwh']:.3f} | {total['carbon_per_kwh']:g} | "
            f"{total['electricity_usd']:.4f} | {total['carbon_g']:,.2f} |")
    lines += [
        "", f"Moving all eligible jobs from {result['baseline_region']} to {result['cleanest_region']}:",
        f"- Estimated carbon avoided: {result['saved_carbon_g']:,.2f} gCO2e ({result['saved_carbon_pct']:.2f}%).",
        f"- Estimated electricity savings: ${result['saved_electricity_usd']:.2f} ({result['saved_electricity_pct']:.2f}%).",
        "", "### Recommendations", "",
        f"- Lowest electricity price: {result['cheapest_region']}.",
        f"- Lowest carbon intensity: {result['cleanest_region']}.",
        f"- Balanced policy: cheapest region with carbon <= {result['carbon_limit']:g} gCO2e/kWh: "
        f"{result['balanced_region'] or 'no qualifying region'}.",
        "- The balanced choice may equal the cheapest choice; a third distinct region is not required.",
        "", "### Assumptions and limits", "",
        "- Model GPU power as constant catalog watts; retain GPU type, count, runtime and workload across regions. "
        "This is not measured power or a forecast of real billing.",
        "- Assume every eligible job initially runs in the baseline region. The CSV has no actual region column.",
        "- Treat interruptible=1 as eligibility for this scenario, not proof that a job is portable. "
        "Verify GPU availability, data residency, dependencies and deadlines before moving it.",
        "- Exclude CPU, networking, storage, cooling/PUE, migration and checkpoint overhead; regional rates are lab snapshots.",
        "- A cleaner region can be farther from users or data, increasing latency and transfer cost. "
        "No latency measurements are available; prefer flexible batch jobs and validate end-to-end runtime.",
        "- Electricity savings are separate from GPU rental savings: rental prices may already include electricity. "
        "Do not add these estimates to M3/M5 savings, especially with different time periods.",
    ]
    return "\n".join(lines)


def run(verbose: bool = True) -> dict:
    result = analyze(load_csv("workloads.csv"), catalog_by_type())
    if verbose:
        print(format_report(result))
    return result


if __name__ == "__main__":
    run()
