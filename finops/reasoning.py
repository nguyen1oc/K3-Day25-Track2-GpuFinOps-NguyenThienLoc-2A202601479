"""Extension 4: reasoning spend/energy audit and deterministic budget scenarios.

All costs use the lab's optimized routing, cache and batch prices. Energy is
modeled, not measured. The counterfactual output multiplier comes from
data/generate.py (reasoning outputs are generated as 6x ordinary outputs).
"""
from __future__ import annotations

import math

from finops import pricing, sustainability


def _summary(rows: list[dict], model_prices: dict) -> dict:
    result = {"requests": len(rows), "tokens": 0, "cost_usd": 0.0,
              "energy_wh": 0.0, "same_tokens_normal_wh": 0.0}
    for row in rows:
        tokens = row["input_tokens"] + row["output_tokens"]
        pin, pout = model_prices[row["route_tier"]]
        result["tokens"] += tokens
        result["cost_usd"] += pricing.request_cost(
            row["input_tokens"], row["output_tokens"], pin, pout,
            cached_in=row["cached_input_tokens"], batch=row["is_batch"])
        result["energy_wh"] += sustainability.wh_per_query(
            tokens, is_reasoning=row["is_reasoning"])
        result["same_tokens_normal_wh"] += sustainability.wh_per_query(tokens)
    result["per_million_usd"] = pricing.dollars_per_million(
        result["cost_usd"], result["tokens"])
    return result


def analyze_reasoning(rows: list[dict], model_prices: dict,
                      cap_fractions: tuple = (0.10, 0.05),
                      reasoning_output_multiplier: float = 6.0) -> dict:
    """Compare current traffic with caps on reasoning request count.

    Keep reasoning for the requests with the largest observed output counts,
    using input order to break ties. This is an offline proxy only: the dataset
    has no complexity/confidence scores for a real online routing decision.
    Overflow requests stay on the same model tier with the same input, cache,
    and batch settings, but use normal energy and output / multiplier tokens
    (rounded up). No request is dropped and caller data is not changed.
    """
    if not math.isfinite(reasoning_output_multiplier) or reasoning_output_multiplier < 1:
        raise ValueError("reasoning_output_multiplier must be finite and >= 1")
    if any(not math.isfinite(cap) or not 0 <= cap <= 1 for cap in cap_fractions):
        raise ValueError("cap fractions must be finite and between 0 and 1")

    normalized = []
    for row in rows:
        normalized.append({
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
            "cached_input_tokens": int(row["cached_input_tokens"]),
            "is_batch": bool(int(row["is_batch"])),
            "is_reasoning": bool(int(row["is_reasoning"])),
            "route_tier": row["route_tier"],
        })
    current = _summary(normalized, model_prices)
    groups = {}
    for name, flag in (("normal", False), ("reasoning", True)):
        group = _summary([row for row in normalized if row["is_reasoning"] == flag], model_prices)
        for metric, share in (("requests", "traffic_pct"), ("cost_usd", "cost_pct"),
                              ("energy_wh", "energy_pct")):
            group[share] = 100 * group[metric] / current[metric] if current[metric] else 0.0
        groups[name] = group

    ranked = sorted(
        (i for i, row in enumerate(normalized) if row["is_reasoning"]),
        key=lambda i: (-normalized[i]["output_tokens"], i))
    scenarios = []
    for cap in cap_fractions:
        limit = math.floor(len(normalized) * cap)
        rerouted = set(ranked[limit:])
        adjusted = []
        for index, row in enumerate(normalized):
            updated = dict(row)
            if index in rerouted:
                updated["is_reasoning"] = False
                updated["output_tokens"] = math.ceil(row["output_tokens"] / reasoning_output_multiplier)
            adjusted.append(updated)
        scenario = _summary(adjusted, model_prices)
        remaining = len(ranked) - len(rerouted)
        scenario.update({
            "cap_fraction": cap, "reasoning_limit": limit,
            "reasoning_requests": remaining, "rerouted_requests": len(rerouted),
            "reasoning_traffic_pct": 100 * remaining / len(normalized) if normalized else 0.0,
            "saved_usd": current["cost_usd"] - scenario["cost_usd"],
            "saved_wh": current["energy_wh"] - scenario["energy_wh"],
        })
        for metric, saved, pct in (("cost_usd", "saved_usd", "cost_savings_pct"),
                                   ("energy_wh", "saved_wh", "energy_savings_pct")):
            scenario[pct] = 100 * scenario[saved] / current[metric] if current[metric] else 0.0
        scenarios.append(scenario)
    return {"current": current, "groups": groups, "scenarios": scenarios,
            "reasoning_output_multiplier": reasoning_output_multiplier}


def budget_report(audit: dict) -> str:
    """Render the same audit in M2 output and the regenerated M5 report."""
    current, groups = audit["current"], audit["groups"]
    reasoning = groups["reasoning"]
    extra_wh = reasoning["energy_wh"] - reasoning["same_tokens_normal_wh"]
    lines = [
        "## Extension 4 - Reasoning budget", "",
        "Daily traffic; costs include existing model routing, cache and batch discounts.",
        "Energy values are estimates from the lab model, not hardware measurements.", "",
        "| Group | Requests | Traffic % | Tokens | Cost USD | Cost % | Energy Wh | Energy % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, group in groups.items():
        lines.append(
            f"| {name} | {group['requests']:,} | {group['traffic_pct']:.3f} | "
            f"{group['tokens']:,} | {group['cost_usd']:.4f} | {group['cost_pct']:.2f} | "
            f"{group['energy_wh']:.2f} | {group['energy_pct']:.2f} |")
    lines += [
        "", f"Reasoning represents {reasoning['traffic_pct']:.3f}% of requests, "
        f"{reasoning['cost_pct']:.2f}% of spend and {reasoning['energy_pct']:.2f}% of energy.",
        f"At the SAME token count, normal processing of the reasoning group would use "
        f"{reasoning['same_tokens_normal_wh']:.2f} Wh versus {reasoning['energy_wh']:.2f} Wh: "
        f"an estimated {extra_wh:.2f} Wh reasoning overhead. The lab's "
        f"{sustainability.REASONING_ENERGY_MULTIPLIER:g}x multiplier applies only to energy; "
        "there is no separate reasoning price multiplier in request_cost().", "",
        "### Counterfactual caps (relative to current optimized M2 traffic)", "",
        "| Scenario | Reasoning requests | Rerouted | Cost USD/day | Saved USD/day | Saved cost % | Energy Wh/day | Saved Wh/day | Saved energy % |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| Current | {reasoning['requests']} | 0 | {current['cost_usd']:.4f} | 0.0000 | 0.00 | {current['energy_wh']:.2f} | 0.00 | 0.00 |",
    ]
    for scenario in audit["scenarios"]:
        lines.append(
            f"| Cap {scenario['cap_fraction']:.0%} | {scenario['reasoning_requests']} | "
            f"{scenario['rerouted_requests']} | {scenario['cost_usd']:.4f} | "
            f"{scenario['saved_usd']:.4f} | {scenario['cost_savings_pct']:.2f} | "
            f"{scenario['energy_wh']:.2f} | {scenario['saved_wh']:.2f} | {scenario['energy_savings_pct']:.2f} |")
    lines += ["", "### Routing rule and assumptions", "",
        "- Proposed online rule: use normal processing by default; allow reasoning only "
        "when an independently calibrated complexity score is >= 0.8 and the daily "
        "reasoning budget has room. The threshold is a proposal, not measured in this dataset.",
        "- Offline simulation: retain reasoning for requests with the largest observed output "
        "counts (ties follow CSV order). Output length is only a proxy and is unavailable "
        "before an online request; no complexity/confidence or quality labels are provided.",
        f"- Keep every request, model tier, input, cached input and batch flag unchanged. "
        f"For rerouted requests, divide output tokens by {audit['reasoning_output_multiplier']:g} "
        "(round up), following data/generate.py, and use normal energy. This assumption "
        "reduces the number of delivered tokens; equivalent answer quality is NOT established.",
        "- Cost savings come from fewer billed output tokens; energy savings additionally "
        "remove the reasoning multiplier. These are separate effects, not an 80x dollar discount.",
        "- A cap above the observed reasoning share changes nothing. Caps apply to request "
        "count, not token count. The 5% scenario is a sensitivity check, not a validated policy.",
        "- Evaluate answer quality, latency and fallback rate before adopting a tighter cap. "
        "Scenario savings are NOT added to M5's existing savings totals or chart.",
    ]
    return "\n".join(lines)
