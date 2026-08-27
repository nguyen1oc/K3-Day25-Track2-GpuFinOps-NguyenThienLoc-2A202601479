"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability, reasoning, submission
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing, m4_allocation, ex5_carbon_scheduling

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    r4 = m4_allocation.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
        "cheapest_region": min(sustainability.REGION_PRICE_KWH, key=sustainability.REGION_PRICE_KWH.get),
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust)
    heading, body = md.split("\n", 1)
    md = heading + "\n\n" + submission.REPORT_IDENTITY + "\n" + body
    md += "\n\nSustainability snapshot: one illustrative 800-token normal query at us-east-1; not the traffic-wide average."
    md += (
        "\n\n## Inference unit economics (M2)\n\n"
        f"Baseline: ${r2['baseline_per_m']:.3f}/1M-token; "
        f"optimized: ${r2['optimized_per_m']:.3f}/1M-token "
        f"({r2['savings_pct']:.1f}% saved). Both use the same "
        f"{r2['total_tokens']:,} daily input + output tokens.\n\n"
    )
    # Ex5 uses each job's own duration and electricity costs, not M5's monthly
    # rental budget. Keep this scenario separate to avoid double counting.
    carbon_scenario = ex5_carbon_scheduling.run(verbose=False)
    md += submission.build_analysis(r1, r2, r3, r4, carbon_scenario, baseline, optimized,
                                    levers, cat, RIGHTSIZE_MAP) + "\n\n"
    md += reasoning.budget_report(r2["reasoning_budget"]) + "\n"
    md += "\n" + ex5_carbon_scheduling.format_report(carbon_scenario) + "\n"
    md += "\n## Savings chart\n\n![GPU cost savings waterfall](savings.png)\n"
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(ROOT, "outputs", "writeup.md"), "w", encoding="utf-8") as f:
        f.write(submission.build_writeup(r1, r2, r3, r4, carbon_scenario, baseline, optimized, levers))
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"), baseline_usd=baseline)

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print("\nWritten: outputs/report.md + outputs/writeup.md" + (" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
