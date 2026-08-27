"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly") -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Lowest-carbon region: {sustainability.get('best_region', 'n/a')}",
        ]
        if "cheapest_region" in sustainability:
            lines.append(f"- Lowest electricity-price region: {sustainability['cheapest_region']}")
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str, baseline_usd: float | None = None) -> str:
    """Write a cost waterfall with four reduction steps plus start/end totals."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return ""
    from textwrap import fill
    from matplotlib.ticker import StrMethodFormatter
    baseline = float(baseline_usd) if baseline_usd is not None else sum(levers.values())
    names = ["Baseline"] + [fill(name, 19) for name in levers] + ["Optimized"]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    ax.bar(0, baseline, color="#23395b", width=0.65)
    ax.annotate(f"${baseline:,.0f}", (0, baseline), xytext=(0, 8),
                textcoords="offset points", ha="center", weight="bold")
    remaining = baseline
    for index, savings in enumerate(levers.values(), start=1):
        next_cost = remaining - savings
        ax.plot([index - 1 + 0.325, index - 0.325], [remaining, remaining],
                color="#9aa5b1", linewidth=1)
        ax.bar(index, savings, bottom=next_cost, color="#36a382", width=0.65)
        ax.annotate(f"-${savings:,.0f}", (index, remaining), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=10)
        remaining = next_cost
    last = len(levers) + 1
    ax.plot([last - 1 + 0.325, last - 0.325], [remaining, remaining], color="#9aa5b1", linewidth=1)
    ax.bar(last, remaining, color="#287b91", width=0.65)
    ax.annotate(f"${remaining:,.0f}", (last, remaining), xytext=(0, 8),
                textcoords="offset points", ha="center", weight="bold")
    ax.set_xticks(range(len(names)), names, fontsize=9)
    ax.set_ylabel("Projected cost (USD / month)")
    ax.set_title("NimbusAI | GPU cost optimization", loc="left", fontsize=15, weight="bold", pad=30)
    ax.text(0, 1.025, "Lab simulation | Four savings levers | Ex4 / Ex5 scenarios excluded",
            transform=ax.transAxes, fontsize=9, color="#53616e")
    ax.yaxis.set_major_formatter(StrMethodFormatter("${x:,.0f}"))
    ax.set_ylim(0, max(baseline, 1) * 1.15)
    ax.yaxis.grid(True, alpha=0.18)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path
