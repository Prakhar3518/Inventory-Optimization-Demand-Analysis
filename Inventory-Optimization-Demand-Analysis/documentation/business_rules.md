# Business Rules

Every classification and threshold used in this project, with the reasoning behind it. Each rule is stated so it can be defended in one sentence.

---

## 1. The unit of decision is the position-day

A **stock position** is one store holding one product: `Store ID + Product ID`. There are 100.

A **position-day** is one position on one date. There are 73,100.

Classification happens at position-day level, not at product level. This matters, and it's the first thing to explain if asked.

**Why.** Averaged across 731 days, every one of the 100 positions sits near 2.0 days of cover and classifies as Healthy. The variation is entirely *within* positions over time, not *between* positions. A product-level classification would report that nothing is ever wrong, while 18.7% of individual position-days sit below one day of cover.

The exposure is episodic. Classify the episode.

---

## 2. Days of cover — the core metric

```
Days of Cover = Inventory Level ÷ Average Daily Demand
```

Where `Average Daily Demand` is the trailing 28-day mean of units sold for that position.

**Why trailing, not full-period.** A planner making a decision on 2022-06-15 has access to the previous 28 days, not to the following 18 months. Using the full-period mean would leak future information into a past-dated decision — a subtle error that makes backtested results look better than the policy could ever achieve.

**Why 28 days.** Four full weeks, so any day-of-week pattern averages out. Long enough that the mean is stable, short enough to follow a genuine demand shift.

**Why cover rather than raw units.** 200 units means nothing without knowing the demand rate. Cover is comparable across every position and is the language replenishment decisions are actually made in.

---

## 3. Classification bands

Four mutually exclusive bands, each mapping to exactly one action.

| Status | Rule | Action | Share of position-days |
|---|---|---|---|
| **Critical** | Cover < 1.0 day | REPLENISH NOW | 18.7% |
| **Below Reorder** | 1.0 ≤ Cover < 1.5 days | REPLENISH | 15.5% |
| **Healthy** | 1.5 ≤ Cover ≤ 3.0 days | MAINTAIN | 46.7% |
| **Excess** | Cover > 3.0 days | REDUCE STOCK | 19.1% |

### Where the thresholds come from

Calibrated to the observed cover distribution, not to textbook values:

| Percentile | Cover (days) |
|---|---|
| Minimum | 0.34 |
| 25th | 1.19 |
| Median | 2.00 |
| 75th | 2.84 |
| Maximum | 3.95 |

- **1.0 day (critical)** — below one day of cover, a single day of normal demand exhausts the position. Sits just under the 25th percentile.
- **1.5 days (reorder)** — a half-day buffer above critical, giving time to react. Just above the 25th percentile.
- **3.0 days (target)** — just above the 75th percentile, so roughly the top quartile classifies as excess. Also 50% above the median, which is a defensible ceiling for a position turning over every two days.

**All three are parameters, not constants.** They live in `Parameters!B5:B7` in the workbook and as a what-if parameter in Power BI. Changing one re-classifies everything downstream. Anyone who disagrees with the calibration can move the threshold and watch the answer change — which is the honest way to present a judgement call.

### Why not classical safety stock

The textbook reorder point is `demand × lead time + z × σ × √lead time`. It isn't used here, for two reasons:

1. **There is no lead time column.** Any lead time would be invented.
2. **The demand standard deviation is inflated by censoring.** Units Sold never exceeds Inventory Level, so observed demand is truncated on low-stock days. Feeding that σ into a safety-stock formula gives a reorder point above the average inventory level itself, flagging roughly two-thirds of all positions and making the metric useless.

A cover-based rule sidesteps both problems and is easier to explain to a manager.

---

## 4. Service risk rules

### Stockout Risk
```
Stockout Risk = 1 when Demand Forecast > Inventory Level
```
Forecast demand exceeds stock on hand. 2,585 position-days (3.54%).

Uses the forecast rather than actual sales because actual sales are capped by inventory — a position that sells out shows sales exactly equal to stock, which understates the shortfall by construction.

### Sold Out
```
Sold Out = 1 when Units Sold = Inventory Level
```
The position ended with nothing left. 369 position-days (0.50%).

**Important caveat.** On these days true demand is *censored*: it was at least the units sold, possibly more. Every demand figure on a sold-out day is a lower bound. This is why unserved demand is estimated from the forecast rather than from sales.

### Unserved Units
```
Unserved Units = MAX(0, Demand Forecast − Inventory Level)
```
17,294 units across the panel, roughly $952,000 at retail.

---

## 5. Excess capital rules

```
Excess Units = MAX(0, Inventory Level − Average Daily Demand × 3.0)
Excess Value = Excess Units × Price
```

Stock held above the three-day target, valued at retail. Averages about $64,600 per day, or 4.3% of total inventory value.

**Valued at retail, not cost.** The source file contains no cost column. Every inventory value in this project is a retail figure, and the README, the workbook and the dashboard all say so. Presenting a retail figure as though it were cost would overstate tied-up capital by whatever the gross margin is.

---

## 6. Replenishment rules

```
Order Requirement = MAX(0, Average Daily Demand × 3.0 − Inventory Level)
Order Gap         = Units Ordered − Order Requirement
```

`Order Requirement` is what a cover-targeting policy would order. `Order Gap` compares that against what was actually ordered — negative means under-ordering against need, positive means over-ordering.

On the final day of the panel: 14,845 units required across 100 positions, against 11,234 actually ordered — a gap of −3,611 units, while 15 positions simultaneously sat in Excess.

That combination — under-ordering in aggregate *while* ordering into already-overstocked positions — is the signature of an unresponsive process.

---

## 7. The noise-band rule

Before any position is singled out, its exception rate is tested against sampling variation.

```
Standard error = √(p × (1 − p) ÷ 731)
Noise band     = system rate ± 2.8 × standard error
```

Where `p` is the system-wide exception rate and 731 is the observation count per position. The 2.8 multiplier is roughly the largest deviation expected by chance when scanning 100 positions.

| Metric | System rate | Band | Positions outside |
|---|---|---|---|
| % days Critical | 18.68% | 14.64% – 22.72% | 0 of 100 |
| % days Excess | 19.11% | 15.04% – 23.18% | 10 of 100 |

**Rule: a position is flagged for monitoring only if it falls outside the band.** Ninety-five of the hundred classify as Routine.

**Why this rule exists.** Sorting 100 positions by any noisy rate always produces a "worst" one. Without a noise test, that position gets a bullet point, a recommendation, and possibly a purchase-order change — on the strength of nothing. The band makes the distinction between a real outlier and the tail of a random distribution explicit.

It also produces the project's central conclusion: since no position has abnormal stockout exposure, the stockout problem is systemic and belongs to the ordering policy, not to any product or store.

---

## 8. Rules deliberately not implemented

| Rule | Why not |
|---|---|
| ABC / Pareto classification | Requires meaningful revenue concentration. The top position accounts for 1.12% of revenue against 1.00% for a perfectly uniform split, and the top ten hold 10.8% against 10% — there is no Pareto curve here. |
| Fast/slow-moving classification | Demand differences across positions are within sampling noise (max \|z\| = 2.99 over 100 groups). |
| Category-level reorder policy | Category is a transaction label, not a product attribute. |
| Regional allocation rules | Region has the same defect. |
| Promotion-driven demand uplift | Promotion and non-promotion days are statistically indistinguishable (p = 0.92). |
| Supplier scorecard | No supplier column. |
| Economic Order Quantity | Requires ordering cost and holding cost, neither of which exists in the data. |
| Margin-weighted prioritisation | No cost column, so margin cannot be computed. |

Each of these could be implemented and would produce numbers. None of the numbers would mean anything.
