"""English report analysis and Vietnamese write-up, rendered from mission results.

Edit the narrative here, not the generated outputs: M5 regenerates both files.
Financial results are calculated by the missions, never supplied as constants.
"""
from __future__ import annotations


STUDENT = "Nguyễn Thiên Lộc"
STUDENT_ID = "2A202601479"
COHORT = "Cohort 3 · Track 2"
IDENTITY = f"**Học viên:** {STUDENT}  \n**MSHV:** {STUDENT_ID}  \n**Lớp:** {COHORT}"
REPORT_IDENTITY = f"**Student:** {STUDENT}  \n**Student ID:** {STUDENT_ID}  \n**Class:** {COHORT}"


def build_analysis(r1, r2, r3, r4, carbon, baseline, optimized, levers, catalog, rightsize_map):
    total_savings = baseline - optimized
    stages = r2["lever_breakdown"]
    inference_saved = stages[0]["daily_usd"] - stages[-1]["daily_usd"]
    cascade_share = stages[1]["marginal_savings_usd"] / inference_saved * 100
    idle_monthly = r1["idle_waste_daily"] * 30
    reasoning = r2["reasoning_budget"]["groups"]["reasoning"]
    cap5 = next(s for s in r2["reasoning_budget"]["scenarios"] if s["cap_fraction"] == 0.05)
    lines = [
        "## Technical analysis and recommendations", "",
        "### 1. Scope, data and reporting periods", "",
        "This submission uses synthetic data with seed=25 and the repository's illustrative June 2026 prices. "
        "No models or physical GPUs were deployed and no cloud charges were incurred. Optimization means "
        "comparing modeled cost scenarios; performance, answer quality and emissions have not been measured on hardware.", "",
        "M2 covers one day of requests; M3/M5 normalize costs to 30 days. Ex4 uses the same daily traffic as M2; "
        "Ex5 uses each job's own duration. All monetary values are USD; commas separate thousands and periods mark decimals.", "",
        "### 2. M1 — GPU activity versus useful computation", "",
        "MFU = achieved_tflops / peak_tflops; MBU = achieved_bw_tbs / peak_bw_tbs. "
        "The lab flags GPUs with GPU-Util >=90% but MFU <30%:", "",
        "| GPU | GPU-Util | MFU | MBU | On-demand USD/hour |",
        "|---|---:|---:|---:|---:|",
    ]
    for gpu in r1["lies"]:
        lines.append(f"| {gpu['gpu_id']} | {gpu['gpu_util_pct']:.1f}% | {gpu['mfu']:.1%} | "
                     f"{gpu['mbu']:.1%} | {float(catalog[gpu['gpu_type']]['on_demand_hr']):.2f} |")
    lines += [
        "", "GPU-Util reflects time with GPU activity, not the fraction of useful FLOPs delivered. "
        "An active kernel may perform little computation because it waits for data, handles small tasks, "
        "or does not use tensor cores effectively. These are hypotheses requiring profiling, not root causes "
        "established by this CSV. Low MFU can also be expected for memory-bound work; MFU alone is insufficient for right-sizing.", "",
        f"Idle waste is ${r1['idle_waste_daily']:.2f}/day, or ${idle_monthly:,.0f}/30 days "
        f"({idle_monthly / baseline:.2%} of the M5 baseline budget). This denominator is the lab's combined budget, "
        "not a standalone bill for the telemetry fleet. GPU gpu-h100-5 has 8 idle hours/day. "
        "Rental savings require releasing resources or otherwise stopping their billing, not merely stopping computation.", "",
        "M5 also assumes the following cheaper GPU substitutions for flagged devices:", "",
        "| GPU | Current → sample recommendation | Difference USD/hour | Potential USD/30 days |",
        "|---|---|---:|---:|",
    ]
    for gpu in r1["lies"]:
        cur = gpu["gpu_type"]
        target = rightsize_map.get(cur, cur)
        delta = max(0, float(catalog[cur]["on_demand_hr"]) - float(catalog[target]["on_demand_hr"]))
        lines.append(f"| {gpu['gpu_id']} | {cur} → {target} | {delta:.2f} | {delta * 24 * 30:.2f} |")
    lines += [
        "", "Right-sizing savings are rental-price estimates only. Validate VRAM capacity, bandwidth, "
        "throughput and latency before accepting a substitution; 20% MFU does not imply that 80% of the bill can be removed.", "",
        "### 3. M2 — Contribution of each inference lever", "",
        f"Keep the same {r2['total_tokens']:,} input + output tokens. Apply "
        "baseline → cascade → add cache → add batch; each row introduces one additional lever:", "",
        "| Stage | Cost USD/day | USD/1M-token | Incremental savings USD/day |",
        "|---|---:|---:|---:|",
    ]
    for stage in stages:
        lines.append(f"| {stage['stage']} | {stage['daily_usd']:.4f} | {stage['per_million_usd']:.3f} | "
                     f"{stage['marginal_savings_usd']:.4f} |")
    lines += [
        "", f"Cascade is the largest M2 contributor: ${stages[1]['marginal_savings_usd']:.4f}/day, "
        f"or {cascade_share:.2f}% of inference savings under this attribution order. Small-model prices "
        "are lower and many dataset requests have route_tier=small. Those routing labels are supplied by the "
        "dataset; they do not establish that the small model provides equivalent answer quality.", "",
        "Marginal contributions depend on the application order because cache and batch interact with model prices. "
        "Do not add three standalone percentage estimates. Cache discounts only cached input tokens, while batch "
        "discounts requests marked is_batch. The 0.05 discount_stack factor applies to fully cached input combined "
        "with batch, not a guaranteed 95% discount for every whole request. Avoid batch when deadlines "
        "or interactive response requirements cannot tolerate waiting.", "",
        "### 4. M3 — Purchasing strategy and commitment limits", "",
        f"Modeled GPU rental spend falls from ${r3['on_demand_monthly']:,.0f} to "
        f"${r3['optimized_monthly']:,.0f}/month ({r3['savings_pct']:.1f}%). "
        "Interruptible jobs running less than 24 hours/day use spot; remaining jobs with duty cycle >=55% "
        "use reserved. Spot estimates include checkpoint and rework overhead through the supplied function.", "",
        "The 55% threshold comes from an assumed 45% reserved discount; it is not universal across GPUs. "
        "M3 normalizes every job to 30 days and multiplies reserved rates by workload hours. It does not fully "
        "model obligations across a one-/three-year commitment or unused committed capacity. Before reserving, "
        "evaluate actual duration, forecast utilization and opportunity cost. Use spot only when jobs can "
        "resume from checkpoints and still meet deadlines after interruptions.", "",
        "### 5. M4 — Cost allocation and tag quality", "",
        "| Team | Cost USD/day |", "|---|---:|",
    ]
    for team, cost in sorted(r4["by_team"].items(), key=lambda pair: -pair[1]):
        lines.append(f"| {team} | {cost:.2f} |")
    lines += [
        "", f"Tag coverage is {r4['tag_coverage']:.1%} (rounded to 92% in console output), above the "
        "lab's 80% threshold, so the chargeback gate is open. The assistant team spends the most, but this "
        "does not establish waste without normalization by requests or tokens. Rounding costs by team can "
        "cause cent-level differences from the M2 total.", "",
        "Start with showback, complete missing project tags, then introduce actual chargeback with transparent "
        "rules for untagged spend. focus_export.csv is a 50-row FOCUS-style sample, not an export of all "
        "2,400 requests or certification of complete FOCUS compliance.", "",
        "### 6. M5 — Combined savings, priorities and overlap risks", "",
        f"Projected savings total ${total_savings:,.0f}/month, or {total_savings / baseline:.1%}. "
        "M5 combines 30 days of inference spending with the M3 GPU budget, then subtracts four savings buckets "
        "as implemented in the starter code. M2 uses unrounded totals for USD/1M-token; M5 preserves the starter's "
        "rounding, so recomputing from displayed values may produce small differences.", "",
        "| Lever | Savings USD/month | Share of total savings |", "|---|---:|---:|",
    ]
    for lever, savings in levers.items():
        lines.append(f"| {lever} | {savings:,.0f} | {savings / total_savings:.2%} |")
    lines += [
        "", "**Three priority actions for NimbusAI:**", "",
        "1. **Control idle resources and ownership first:** assign owner/team/project tags and schedule "
        "idle sandbox/GPU reclamation after checking dependencies. Track MFU/MBU and team budgets. "
        "This is a reversible change that can reduce idle waste without changing model quality.",
        "2. **Optimize purchasing:** pilot spot with checkpointing for suitable jobs; verify steady demand "
        "and commitment obligations before reserving. Purchasing is the largest M5 savings opportunity, "
        "but implementation costs are not available to calculate actual ROI.",
        "3. **Evaluate inference and resource changes:** validate quality before expanding cascade; cache "
        "reused prefixes and batch requests that do not require immediate responses. Profile flagged GPUs "
        "before right-sizing; compare answer quality, p95 latency, throughput and USD/1M-token before/after.", "",
        "**These buckets are not audited savings:** the dataset lacks a complete gpu_id → job_id mapping "
        "to rule out overlap between M1 telemetry and M3 workloads. Establish a common cost ledger before "
        "adding purchasing, right-sizing and idle savings in production. M5 also combines token-priced "
        "inference with GPU spending; verify that these are separate charges before applying the model to real bills. "
        "The starter totals are retained for lab comparison, not as evidence of an actual cloud-bill reduction.", "",
        "### 7. Interpretation of the two extensions", "",
        f"**Ex4:** reasoning accounts for {reasoning['traffic_pct']:.3f}% of requests, "
        f"{reasoning['cost_pct']:.2f}% of spend and {reasoning['energy_pct']:.2f}% of modeled energy. "
        f"A 10% cap changes nothing; a 5% cap reroutes {cap5['rerouted_requests']} requests to normal processing, "
        f"saving ${cap5['saved_usd']:.4f}/day ({cap5['cost_savings_pct']:.2f}%) and "
        f"{cap5['saved_wh']:.2f} Wh/day ({cap5['energy_savings_pct']:.2f}%). "
        "The scenario assumes output tokens fall sixfold and removes the 80x energy multiplier after rerouting; "
        "equivalent answer quality is not established. The proposed complexity >=0.8 rule is unvalidated; "
        "the simulation instead uses observed output length as an offline proxy.", "",
        f"**Ex5:** {len(carbon['jobs'])} eligible jobs consume an estimated {carbon['total_energy_wh'] / 1000:,.0f} kWh "
        f"at catalog power. Moving from {carbon['baseline_region']} to {carbon['cleanest_region']} "
        f"avoids {carbon['saved_carbon_g'] / 1000:.2f} kg CO2e ({carbon['saved_carbon_pct']:.2f}%) "
        f"and saves ${carbon['saved_electricity_usd']:.2f} in electricity ({carbon['saved_electricity_pct']:.2f}%). "
        f"{carbon['cheapest_region']} has the lowest price; {carbon['cleanest_region']} has the lowest carbon intensity. "
        f"{carbon['balanced_region']} is the cheapest option below the {carbon['carbon_limit']:g} gCO2e/kWh limit. "
        "Consider latency, data residency, egress, GPU availability and deadlines. Do not add Ex5 electricity "
        "savings to rental savings: electricity may already be included in rent, and the reporting periods differ.", "",
        "Detailed tables and reproducible assumptions for both extensions follow below. The opening "
        "sustainability snapshot represents one 800-token normal query in us-east-1, not the traffic average. "
        "Region names are retained as dataset labels; no geographic mapping or current market-price claim is implied.", "",
        "### 8. Reproduction and source cross-checks", "",
        "```powershell", "python data/generate.py", "python missions/run_all.py",
        "python missions/ex5_carbon_scheduling.py", "python verify.py", "pytest -q", "```", "",
        "M5 regenerates report.md, writeup.md and savings.png; M4 writes focus_export.csv. "
        "Original instructor tests remain unchanged; additional tests are in separate files. "
        "Prices and formulas come from the lab's data/, finops/ and missions/ directories; "
        "submission requirements are cross-checked against README.md, Guide.md and Rubric.md.",
    ]
    return "\n".join(lines)


def build_writeup(r1, r2, r3, r4, carbon, baseline, optimized, levers):
    """Compact Vietnamese write-up covering the five questions in Guide §11."""
    saved = baseline - optimized
    stages = r2["lever_breakdown"]
    inference_saved = stages[0]["daily_usd"] - stages[-1]["daily_usd"]
    group = r2["reasoning_budget"]["groups"]["reasoning"]
    cap = next(s for s in r2["reasoning_budget"]["scenarios"] if s["cap_fraction"] == 0.05)
    lies = "; ".join(f"{g['gpu_id']} (util {g['gpu_util_pct']:.1f}%, MFU {g['mfu']:.1%})" for g in r1["lies"])
    return f"""# Bài viết ngắn — Lab 25: GPU FinOps

{IDENTITY}

## 1. Baseline và kết quả tối ưu

Bài làm dùng dữ liệu tổng hợp seed=25 và giá mô phỏng tháng 6/2026. Kết quả là ước tính theo code lab, không phải hóa đơn hay năng lượng đo trên GPU thực. Ngân sách M5 giảm từ **${baseline:,.0f} xuống ${optimized:,.0f}/tháng**, tiết kiệm **${saved:,.0f} ({saved / baseline:.1%})**. Riêng inference M2 giảm **${r2['baseline_per_m']:.3f} → ${r2['optimized_per_m']:.3f}/1M-token ({r2['savings_pct']:.1f}%)**, giữ nguyên {r2['total_tokens']:,} input + output tokens. Hai tỷ lệ có mẫu số khác nhau, không cộng trực tiếp.

## 2. Biện pháp nào đóng góp nhiều nhất?

| Biện pháp | Tiết kiệm USD/tháng |
|---|---:|
| Inference: cascade/cache/batch | {levers['Inference (cascade/cache/batch)']:,.0f} |
| Purchasing: spot/reserved | {levers['Purchasing (spot/reserved)']:,.0f} |
| Right-sizing theo giả định mẫu | {levers['Right-size util-lies']:,.0f} |
| Loại bỏ idle | {levers['Kill idle GPUs']:,.0f} |

Purchasing đóng góp **{levers['Purchasing (spot/reserved)'] / saved:.1%}** tổng savings vì giảm giá thuê trên lượng GPU-giờ lớn. Trong riêng M2, phân rã theo thứ tự cascade → cache → batch cho mức giảm lần lượt **${stages[1]['marginal_savings_usd']:.4f}, ${stages[2]['marginal_savings_usd']:.4f}, ${stages[3]['marginal_savings_usd']:.4f}/ngày**; cascade chiếm {stages[1]['marginal_savings_usd'] / inference_saved:.1%}. Đóng góp biên phụ thuộc thứ tự, không phải hiệu quả độc lập. Model nhỏ cần được kiểm tra chất lượng; batch chỉ phù hợp khi chấp nhận chờ.

## 3. GPU-Util lie và tác động tài chính

M1 gắn cờ **{lies}**. GPU có hoạt động không có nghĩa đang tận dụng FLOPs hiệu quả: kernel có thể chờ dữ liệu hoặc xử lý công việc quá nhỏ. Đây là giả thuyết cần profiler xác minh; MFU thấp cũng có thể do workload memory-bound. Không thể lấy 1 − MFU làm tỷ lệ hóa đơn cắt được. Idle gây lãng phí **${r1['idle_waste_daily']:.0f}/ngày = ${r1['idle_waste_daily'] * 30:,.0f}/30 ngày**. Khoản right-sizing ${levers['Right-size util-lies']:,.0f}/tháng chỉ có ý nghĩa khi GPU rẻ hơn vẫn đáp ứng VRAM, throughput và latency.

## 4. Hai extensions đã thực hiện

**Ex4 — Ngân sách reasoning:** nhóm này chiếm **{group['traffic_pct']:.3f}% request**, **{group['cost_pct']:.2f}% tiền** và **{group['energy_pct']:.2f}% năng lượng mô phỏng**. Trần 10% không tác động vì tỷ lệ hiện tại đã thấp hơn. Trần 5% chuyển {cap['rerouted_requests']} request sang thường, tiết kiệm **${cap['saved_usd']:.4f}/ngày ({cap['cost_savings_pct']:.2f}%)** và **{cap['saved_wh']:.2f} Wh/ngày ({cap['energy_savings_pct']:.2f}%)**. Mô phỏng giảm output 6 lần và bỏ hệ số năng lượng 80x; không áp hệ số 80x cho tiền. Đề xuất chỉ reasoning khi complexity >=0.8 và còn ngân sách; CSV chưa có score nên dùng độ dài output làm proxy offline. Chất lượng tương đương chưa được chứng minh.

**Ex5 — Chuyển vùng theo carbon:** {len(carbon['jobs'])} job interruptible dùng tổng **{carbon['total_energy_wh'] / 1000:,.0f} kWh** ước tính theo công suất catalog và số ngày riêng của mỗi job. Chuyển từ us-east-1 sang europe-north1 giảm **{carbon['saved_carbon_g'] / 1000:.2f} kg CO2e ({carbon['saved_carbon_pct']:.2f}%)**, đồng thời giảm tiền điện **${carbon['saved_electricity_usd']:.2f} ({carbon['saved_electricity_pct']:.0f}%)**. europe-north1 sạch nhất; us-east-wa rẻ nhất và là lựa chọn rẻ nhất dưới ngưỡng 100 gCO2e/kWh. Phải kiểm tra độ trễ, egress, dữ liệu cư trú và GPU sẵn có. Các số này không phải savings theo tháng và không cộng vào tiền thuê GPU đã có thể bao gồm điện.

## 5. Ba hành động đầu tiên cho NimbusAI

1. **Kiểm soát idle và ownership:** đặt lịch thu hồi tài nguyên idle, hoàn thiện team/project tag và showback. Coverage hiện tại {r4['tag_coverage']:.1%} vượt ngưỡng chargeback 80% của lab, nhưng vẫn cần xử lý phần thiếu tag trước khi tính phí nội bộ.
2. **Thử spot trước khi cam kết:** kiểm chứng checkpoint, khả năng khôi phục và deadline; chỉ mua reserved khi đủ bằng chứng về nhu cầu dài hạn. M3 dùng 30 ngày và policy hòa vốn đơn giản, chưa phản ánh đầy đủ nghĩa vụ trả tiền toàn kỳ cam kết.
3. **Đánh giá rồi mở rộng inference:** ưu tiên cascade, cache và batch có kiểm soát chất lượng; profile util-lie trước đổi GPU. Thử giới hạn reasoning và chuyển vùng như hai kịch bản riêng, theo dõi chất lượng, p95 latency, USD/1M-token và carbon.

**Giới hạn kết luận:** M5 cộng các bucket theo mẫu; chưa có mapping gpu_id → job_id để loại trừ cộng trùng hoặc xác nhận chi phí inference và GPU là hai hóa đơn riêng. Vì vậy {saved / baseline:.1%} là tiềm năng mô phỏng, không phải savings đã kiểm toán. Bảng chi tiết và giả định nằm trong report.md; mã nguồn và tests mới cho phép tái tạo kết quả, tests gốc giữ nguyên.
"""
