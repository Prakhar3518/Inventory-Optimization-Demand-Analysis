# Insights & Recommendations

Every figure below is computed from `retail_store_inventory.csv` and reproducible from `scripts/01_profile_dataset.py` and `scripts/02_build_analysis_dataset.py`. Nothing is estimated, extrapolated or assumed.

---

## Executive summary

Across 73,100 position-days spanning two years, five stores and twenty products:

- **The replenishment process does not respond to need.** Order quantity correlates with demand at r = −0.0009, with stock on hand at r = 0.0011, and with days of cover at r = 0.0011. Positions in critical shortage receive an average order of 110.1 units; positions already overstocked receive 110.4.
- **The demand forecast is systematically inflated by 5.03 units per position-day** and runs above actual sales on 66.7% of days.
- **Consequences are visible in both directions at once.** 18.7% of position-days sit below one day of cover, while 19.1% sit above three days — 2,585 position-days of stockout exposure alongside an average $64,600 of daily excess capital.
- **No individual product or store is responsible.** Stockout exposure across all 100 positions falls entirely within the statistical noise band. This is a process problem.

---

## Insight 1 — Replenishment is statistically unrelated to need

**The finding.** `Units Ordered` is uniformly distributed between 20 and 200 units and shows no relationship to any measure of requirement.

| Relationship | Correlation |
|---|---|
| Units Ordered vs Units Sold | −0.0009 |
| Units Ordered vs Inventory Level | +0.0011 |
| Units Ordered vs Days of Cover | +0.0011 |

The clearest expression of it:

| Position status when the order was placed | Average units ordered |
|---|---|
| Critical (under 1 day of cover) | **110.1** |
| Below Reorder | 109.8 |
| Healthy | 109.9 |
| Excess (over 3 days of cover) | **110.4** |

A responsive process would show a steep decline across those four rows. These four numbers are indistinguishable.

**What it costs.** Across the two years, **1,541,709 units were ordered into positions already classified as Excess** — roughly $85.5 million at retail. On the final day of the panel, 100 positions needed 14,845 units to reach target cover but received 11,234, a shortfall of 3,611 units — while 15 of those same positions were simultaneously overstocked.

**Why this is the headline.** Every other problem in this dataset is downstream of it. Fix the ordering rule and both the stockout exposure and the excess capital move at once.

---

## Insight 2 — The demand forecast is systematically biased upward

**The finding.** Forecast minus actual averages **+5.03 units** per position-day. Mean absolute error is 8.34 units, so the majority of the total error is systematic bias rather than random noise. The forecast exceeds actual sales on **66.7%** of position-days; a calibrated forecast would sit near 50%.

The bias is identical across all five stores:

| Store | Mean forecast bias (units) |
|---|---|
| S001 | +5.01 |
| S002 | +5.02 |
| S003 | +4.98 |
| S004 | +5.02 |
| S005 | +5.13 |

**What it means.** A bias that uniform across independent stores points at the forecasting method itself, not at local behaviour. It's a constant offset, which also means it's the easiest kind of error to fix: subtract it.

**What it costs.** At 5.03 units per position-day across 73,100 position-days, the forecast overstates cumulative demand by roughly 368,000 units. Any ordering policy driven by this forecast inherits a permanent upward push, which is consistent with the 19.1% of position-days sitting in excess.

**Caveat worth stating.** On the 369 sold-out days actual demand was censored — it was at least the units sold and possibly more. Those days slightly *understate* the true error in the other direction. At 0.5% of the panel the effect is immaterial, but it's the kind of thing worth knowing before quoting the number.

---

## Insight 3 — Inventory sits at both extremes simultaneously

**The finding.** Days of cover ranges from 0.34 to 3.95 days, with a median of 2.00.

| Status | Position-days | Share |
|---|---|---|
| Critical (< 1 day) | 13,653 | 18.7% |
| Below Reorder (1–1.5 days) | 11,335 | 15.5% |
| Healthy (1.5–3 days) | 34,141 | 46.7% |
| Excess (> 3 days) | 13,971 | 19.1% |

**A third of all position-days sit at or below the reorder point, while a fifth sit above target cover.** Total inventory isn't the problem — it's the allocation of it.

**Service consequences:**

| Metric | Value |
|---|---|
| Position-days where forecast demand exceeded stock | 2,585 (3.54%) |
| Position-days ending fully sold out | 369 (0.50%) |
| Unserved units | 17,294 |
| Retail value of unserved demand | $951,717 |
| Implied service level | 96.5% |

**Capital consequences:**

| Metric | Value |
|---|---|
| Average daily inventory value (retail) | $1,516,383 |
| Average daily value above 3-day cover | $64,602 |
| Excess as share of inventory value | 4.3% |

---

## Insight 4 — The problem is systemic, not product-specific

**The finding.** Each position has 731 daily observations, so an exception rate has a binomial standard error near 1.45pp. Across 100 positions, chance alone produces deviations up to ±2.8 standard errors.

| Metric | System rate | Noise band | Observed range | Positions outside |
|---|---|---|---|---|
| % days Critical | 18.68% | 14.64% – 22.72% | 16.14% – 21.61% | **0 of 100** |
| % days Excess | 19.11% | 15.04% – 23.18% | 12.04% – 24.49% | **10 of 100** |

Not one position has stockout exposure distinguishable from the system average. Ten positions show excess exposure outside the band — more than the ~0.5 expected by chance, so a weak real signal, and those ten are the only ones flagged for monitoring.

The same holds at store level:

| Store | % days critical | % days excess | Avg days of cover |
|---|---|---|---|
| S001 | 18.4% | 19.9% | 2.06 |
| S002 | 18.9% | 19.2% | 2.04 |
| S003 | 18.4% | 18.4% | 2.03 |
| S004 | 18.9% | 19.3% | 2.04 |
| S005 | 18.7% | 18.8% | 2.04 |

Critical rates span 0.50 percentage points across the five stores and excess rates 1.53 points. Five independent stores landing that close together is not five stores with the same local habits. It's one shared process.

**Why this matters more than a "worst products" list.** The obvious deliverable would rank the ten worst positions and recommend attention there. That list would be sampling noise, and acting on it would consume attention while changing nothing. The finding that *no position is abnormal* is more useful than any ranking, because it points at where the fix actually is.

---

## Insight 5 — Demand is flat, and four planned drivers explain nothing

| Comparison | Result |
|---|---|
| 2023 vs 2022 units sold | −0.42% |
| 2023 vs 2022 revenue | −1.03% |
| Promotion vs non-promotion days | 136.4 vs 136.5 units, p = 0.92 |
| 20% discount vs no discount | 136.6 vs 135.7 units, p = 0.46 |
| Best vs worst weather condition | 138.0 vs 135.2 units (2% spread) |
| Best vs worst seasonality label | 137.8 vs 135.4 units (2% spread) |

**Demand is stationary.** No trend, no seasonality, no day-of-week pattern (the spread across weekdays is 135.1 to 137.3 units).

**Two implications.** First, no demand-driver analysis is worth building on this data — promotion uplift, discount elasticity and weather impact would all return noise dressed as findings. Second, and more useful: **stationary demand removes the usual excuse for stock imbalance.** When demand is volatile, misallocation is understandable. When demand is this predictable and a third of positions still sit below the reorder point, the fault is squarely in the replenishment rule.

---

# Recommendations

Ordered by impact against implementation effort. Each traces to a specific finding above.

## 1. Replace fixed-quantity ordering with a cover-targeting rule

**Findings 1 and 3.**

Order to a target rather than by habit:

```
Order Quantity = MAX(0, Average Daily Demand × Target Cover − Current Inventory)
```

With target cover at 3.0 days and demand from a trailing 28-day mean. On the final day of the panel this rule produces 14,845 units allocated by need, against 11,234 units allocated at random.

**Expected effect.** Directly eliminates orders into overstocked positions — 1.54 million units over the two-year period — and redirects that volume to the positions actually short. It's a change to one formula in the ordering system, not a new system.

**How to verify it worked.** Track the correlation between Units Ordered and Days of Cover. It currently sits at 0.001. Under a cover-targeting rule it should turn strongly negative. That single number is the whole test.

## 2. Remove the constant bias from the demand forecast

**Finding 2.**

Subtract the measured bias before the forecast reaches the ordering process:

```
Adjusted Forecast = Demand Forecast − 5.03
```

**Expected effect.** Moves the over-forecast rate from 66.7% toward 50% and removes the permanent upward push on order quantities. Recalculate the bias monthly rather than fixing the constant, so it self-corrects if the underlying method changes.

**Effort: minimal.** One arithmetic step. It's the highest return-per-hour item on this list.

## 3. Set daily exception review at the position level, not the product level

**Findings 3 and 4.**

Since no position is chronically bad but 18.7% of position-days are critical, the review has to be daily and position-level. The Action Register in `excel/inventory_analysis.xlsx` and page 3 of the dashboard produce exactly this: on 2024-01-01, 17 positions marked REPLENISH NOW, 20 REPLENISH, 48 MAINTAIN, 15 REDUCE STOCK.

**What not to do.** Don't build a watchlist of "problem products." Finding 4 shows there aren't any — every position takes its turn in the critical band. A fixed watchlist would monitor the wrong positions on most days.

## 4. Treat target cover as a tunable lever, not a fixed number

**Finding 3.**

Excess capital above 3-day cover averages $64,600 daily, 4.3% of inventory value. Lowering target cover releases capital and raises stockout exposure; raising it does the reverse. The what-if parameter on dashboard page 3 quantifies that trade-off live.

**The point.** The right threshold depends on holding cost versus stockout cost, and this dataset contains neither — no cost column exists. So the analysis presents the trade-off and leaves the choice to whoever knows those numbers, rather than asserting an optimum it can't support.

## 5. Monitor the ten genuine excess-exposure positions, and only those

**Finding 4.**

Ten of 100 positions show excess exposure beyond the noise band. They're flagged "Watch — excess capital" in the scorecard's Monitoring Priority column. The remaining 90 classify as Routine and need no individual attention.

**Why the restraint matters.** Flagging all hundred would bury the ten that matter. Ninety-five percent of positions behaving indistinguishably from average is a legitimate result, and reporting it as such is more useful than manufacturing a ranking.

## 6. Fix the data model before extending the analysis

**Data quality report, defects 1 and 2.**

Three problems limit what any future analysis can do:

- **Category, Region and Seasonality don't persist per entity.** The same store-product carries all five categories and all four regions across its daily rows. Until each product has one stable category and each store one stable region, category and regional analysis is impossible.
- **Inventory doesn't reconcile.** Next-day stock doesn't follow from today's stock, sales and orders (r = 0.025), so `Units Ordered` can't be linked to stock received. Capturing goods-receipt dates would enable lead-time analysis, which is currently impossible.
- **No cost column.** Every valuation here is at retail. Adding unit cost would enable margin analysis, COGS-based turnover, and a genuine holding-cost-versus-stockout-cost optimisation — which is what Recommendation 4 needs to move from a trade-off display to an actual answer.

---

## What this analysis cannot tell you

Stated plainly, because the limits are part of the result.

1. **True demand on sold-out days.** Units Sold never exceeds Inventory Level, so demand on the 369 sold-out position-days is censored. Every demand figure on those days is a lower bound.
2. **Whether excess inventory is actually expensive.** Without holding cost, "4.3% of inventory value above target" can't be converted into a cost. It could be trivial or serious.
3. **Whether stockouts lose sales or defer them.** The $951,717 of unserved demand assumes it's lost. If customers return the next day, the real cost is far lower.
4. **Anything about lead times.** No lead-time field, and the inventory ledger doesn't reconcile, so replenishment latency can't be inferred either.
5. **Whether the products differ in any way that matters.** Twenty products with statistically identical demand distributions is unusual for real retail. This is a synthetic dataset, and conclusions about product-level behaviour shouldn't be transferred to a real assortment.
