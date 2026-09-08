# Data Quality Report

Audit of `retail_store_inventory.csv` performed before any analysis was designed. Every figure here is reproducible by running `scripts/01_profile_dataset.py`.

The point of this document: this dataset is clean in the conventional sense — no nulls, no duplicates, no gaps — and simultaneously carries four structural defects that make several obvious analyses invalid. Finding those before building is the difference between a project that survives questioning and one that doesn't.

---

## 1. Completeness — clean

| Check | Result |
|---|---|
| Rows | 73,100 |
| Columns | 15 |
| Null values, all columns | 0 |
| Fully duplicated rows | 0 |
| Duplicates on (Date, Store ID, Product ID) | 0 |
| Date range | 2022-01-01 to 2024-01-01 |
| Distinct dates | 731, consecutive, no gaps |

## 2. Grain — confirmed

731 days × 5 stores × 20 products = 73,100. The row count factorises exactly, so this is a **complete balanced panel**: every store-product combination has an observation on every single date.

The primary key is `(Date, Store ID, Product ID)`. The stock position key is `Store ID + Product ID` — 100 positions. `Product ID` alone is not a stock position, since the same product sits in all five stores.

---

## 3. Defect 1 — Category, Region and Seasonality are not dimension attributes

**Severity: high.** This invalidates category-level and region-level analysis.

A field can only serve as a product or store attribute if it's constant for that product or store. These aren't.

Store S001, Product P0001, across its 731 daily rows:

| Category | Rows |
|---|---|
| Groceries | 164 |
| Furniture | 154 |
| Clothing | 143 |
| Toys | 141 |
| Electronics | 129 |

The same physical stock position is labelled with all five categories. Every one of the 100 positions behaves this way, and Region does the same across its four values. The Category × Region contingency table is flat, which is what independent random assignment produces.

`Seasonality` fails a different test: its four values are distributed evenly across all twelve calendar months, so "Winter" appears as often in July as in January. It isn't a season.

**Consequence.** These three fields are transaction labels, not attributes. They're kept on the fact table and available as descriptive slicers, but no classification, KPI or recommendation in this project rests on them. `DimProduct` deliberately excludes Category; `DimStore` deliberately excludes Region.

---

## 4. Defect 2 — the inventory balance equation does not hold

**Severity: medium.** This changes how two source columns must be interpreted.

In a true stock ledger, tomorrow's inventory equals today's inventory minus units sold plus units received. Testing that on S001-P0001:

| Date | Inventory | Sold | Ordered | Actual next-day | Predicted |
|---|---|---|---|---|---|
| 2022-01-01 | 231 | 127 | 55 | 116 | 159 |
| 2022-01-02 | 116 | 81 | 104 | 154 | 139 |
| 2022-01-03 | 154 | 5 | 189 | 85 | 338 |
| 2022-01-04 | 85 | 58 | 193 | 238 | 220 |

Correlation between actual and predicted next-day inventory: **r = 0.025**. The relationship is absent.

**Consequence.** `Inventory Level` is treated as an independent daily snapshot, not a running balance. `Units Ordered` is treated as an order *placed*, never as stock *received*. No measure in this project chains inventory across days.

---

## 5. Defect 3 — demand differences between positions are statistical noise

**Severity: high.** This invalidates fast/slow-moving product classification.

Mean daily demand across the 100 store-SKUs runs from 126.6 to 149.2 units — a spread that looks meaningful until it's tested against sampling error.

Each position has 731 observations. With a pooled standard deviation of 108.9 units, the standard error on a position's mean is 108.9 / √731 ≈ 4.03 units. Across 100 groups drawn from one distribution, the largest |z| expected by chance is roughly 2.8 to 3.0.

**Observed maximum |z| = 2.99. Positions exceeding |z| > 3: 0 of 100.**

The observed spread is exactly what pure noise produces.

**Consequence.** No fast-moving or slow-moving product ranking is produced. Ranking these positions by demand would be ranking sampling error and presenting it as insight. The project instead classifies **inventory position** (days of cover), which does vary genuinely — from 0.34 to 3.95 days.

The same test applied to exception rates:

| Metric | System rate | Noise band (±2.8 SE) | Observed range | Positions outside band |
|---|---|---|---|---|
| % days Critical | 18.68% | 14.64% – 22.72% | 16.14% – 21.61% | **0 of 100** |
| % days Excess | 19.11% | 15.04% – 23.18% | 12.04% – 24.49% | **10 of 100** |

Stockout exposure is uniform across every position — no position is structurally starved. Excess exposure shows a weak real signal: ten positions fall outside the band, more than the ~0.5 expected by chance. Those ten, and only those ten, are flagged for monitoring in the scorecard.

**This is the finding that shapes the project.** The problem is not located in particular products or stores. It's in the process.

---

## 6. Defect 4 — discount, promotion, weather and competitor pricing carry no signal

**Severity: medium.** This removes four planned analyses.

| Variable | Test | Result |
|---|---|---|
| Holiday/Promotion | t-test, promo vs non-promo units sold | t = −0.10, **p = 0.92** |
| Discount | t-test, 20% vs 0% discount | t = +0.75, **p = 0.46** |
| Weather Condition | mean units sold by condition | 135.2 to 138.0 — a 2% spread |
| Seasonality | mean units sold by label | 135.4 to 137.8 — a 2% spread |
| Competitor Pricing | correlation with Price | **r = 0.994** |

Promotion days average 136.4 units against 136.5 on non-promotion days. There is no uplift to measure.

Competitor Pricing is a near-perfect copy of Price, so it carries no independent information and is dropped in Power Query.

**Consequence.** No promotion-uplift, discount-elasticity, weather-impact or competitive-pricing measures. Each would return a plausible-looking number describing nothing.

---

## 7. Absent fields

The original project brief assumed several fields this dataset doesn't contain. None were fabricated.

| Assumed field | Present | How it was handled |
|---|---|---|
| Unit Cost | No | Inventory valued at **retail price** throughout. Margin, COGS-based turnover and cost-based excess valuation are not computed. |
| Reorder Level | No | Derived as `Avg Daily Demand × reorder cover parameter`, exposed as an editable parameter and documented as policy, not data. |
| Lead Time | No | No lead-time or safety-stock-from-lead-time measures. The reorder point is cover-based instead. |
| Supplier | No | No supplier performance analysis. |
| Warehouse | No | Store is the only genuine location field, and it is used. |
| Product Name | No | Product ID used directly; a display label is generated in DimProduct. |

---

## 8. What the data does support

After the four defects, plenty remains — and it's more interesting than the original brief.

| Finding | Evidence | Strength |
|---|---|---|
| Ordering is unresponsive to need | Units Ordered vs demand r = −0.0009; vs inventory r = +0.0011; vs cover r = +0.0011 | Very strong |
| Forecast carries systematic upward bias | Mean error +5.03 units; 66.7% of days over-forecast; MAE 8.34 | Very strong |
| Inventory position varies genuinely | Days of cover 0.34 to 3.95; 18.7% of position-days critical, 19.1% excess | Strong |
| Service risk is quantifiable | 2,585 position-days with forecast above stock; 17,294 unserved units; 369 sold-out days | Strong |
| Excess capital is quantifiable | ~$64,600 average daily value above 3-day cover, 4.3% of inventory value | Strong |
| Demand is flat year-on-year | −0.42% units, −1.03% revenue, 2022 vs 2023 | Moderate |

---

## 9. Handling notes for downstream steps

1. **January 2024 holds one day.** The panel ends 2024-01-01, so that month has 100 position-days against ~3,000 for a normal month. `DimDate[Is_Complete_Month]` flags it, and every trend visual must filter on it.
2. **Units Sold never exceeds Inventory Level** — 0 rows in 73,100. Sales are inventory-capped, so on the 369 sold-out days true demand was censored and is unobservable. Demand estimates on those days are lower bounds.
3. **Trailing 28-day demand, not full-period demand.** `Avg_Daily_Demand` uses a trailing 28-day window because that's what a planner would actually have available on the day. Using the full-period mean would leak future information into a past-dated decision.
4. **Cleaning steps are defensive no-ops.** The de-duplication and null-handling steps in both the Python pipeline and Power Query remove zero rows from the current file. They exist so the pipeline survives a dirtier refresh, and the row count is asserted after each stage to prove it.
