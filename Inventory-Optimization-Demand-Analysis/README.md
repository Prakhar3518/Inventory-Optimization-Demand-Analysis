# Inventory Optimization & Demand Analysis

**Power BI · Excel · Power Query · VBA · DAX · Python**

An inventory analytics project on a 73,100-row retail panel covering five stores, twenty products and two years of daily observations. It classifies every stock position by days of cover, quantifies stockout exposure and excess capital, and produces a daily replenishment action list.

The central finding: **the replenishment process orders without reference to need.** Order quantity correlates with demand at r = −0.0009 and with stock on hand at r = 0.0011. Positions in critical shortage receive an average order of 110.1 units; positions already overstocked receive 110.4. Everything else in the analysis follows from that.

---

## Contents

- [Business problem](#business-problem)
- [Dataset](#dataset)
- [Data quality findings](#data-quality-findings)
- [Approach](#approach)
- [Key findings](#key-findings)
- [Recommendations](#recommendations)
- [Technical implementation](#technical-implementation)
- [Project structure](#project-structure)
- [How to run](#how-to-run)
- [Limitations](#limitations)

---

## Business problem

A five-store retail chain wants to know which stock positions are overstocked, which are at risk of running out, and where replenishment effort should go.

The questions the analysis answers:

1. Which positions need replenishment today, and how many units?
2. Which positions carry excess stock, and what capital is tied up?
3. How often does stock fall below one day of cover?
4. Can the demand forecast currently in use be trusted?
5. Does the ordering process respond to actual need?
6. Are stockouts concentrated in particular products or stores, or systemic?

---

## Dataset

`data/raw/retail_store_inventory.csv` — 73,100 rows × 15 columns.

| Property | Value |
|---|---|
| Date range | 2022-01-01 to 2024-01-01 (731 consecutive days) |
| Stores | 5 (S001–S005) |
| Products | 20 (P0001–P0020) |
| Stock positions | 100 (store × product) |
| Grain | One row per date × store × product |
| Missing values | 0 |
| Duplicate rows | 0 |

731 × 5 × 20 = 73,100 exactly: a complete balanced panel with no gaps.

### Source columns

| Column | Type | Notes |
|---|---|---|
| Date | Date | 731 consecutive days |
| Store ID | Text | S001–S005 |
| Product ID | Text | P0001–P0020 |
| Category | Text | 5 values — ⚠️ see below |
| Region | Text | 4 values — ⚠️ see below |
| Inventory Level | Integer | Units on hand, daily snapshot |
| Units Sold | Integer | Never exceeds Inventory Level |
| Units Ordered | Integer | 20–200, uncorrelated with need |
| Demand Forecast | Decimal | Carries a +5.03 unit systematic bias |
| Price | Decimal | Shelf price, ~$10–$100 |
| Discount | Integer | 0, 5, 10, 15 or 20 percent |
| Weather Condition | Text | 4 values, no measurable demand effect |
| Holiday/Promotion | Binary | No measurable demand effect (p = 0.92) |
| Competitor Pricing | Decimal | r = 0.994 with Price — dropped |
| Seasonality | Text | 4 values, not aligned to calendar months |

**Fields the dataset does not contain:** Unit Cost, Supplier, Lead Time, Reorder Level, Warehouse, Product Name. None were fabricated. Inventory is valued at retail throughout, and the reorder point is a documented policy parameter rather than a source field.

---

## Data quality findings

The dataset is clean by conventional measures and carries four structural defects that invalidate several obvious analyses. Full detail in [`documentation/data_quality_report.md`](documentation/data_quality_report.md).

**1. Category, Region and Seasonality are not dimension attributes.** Store S001 / Product P0001 appears under all five categories and all four regions across its 731 rows. They're transaction labels, not attributes — so `DimProduct` excludes Category, `DimStore` excludes Region, and no recommendation rests on either.

**2. The inventory balance equation does not hold.** Next-day inventory doesn't follow from today's inventory, sales and orders (r = 0.025). `Inventory Level` is treated as an independent daily snapshot; `Units Ordered` as an order placed, never as stock received.

**3. Demand differences between positions are sampling noise.** Mean daily demand across the 100 positions runs 126.6 to 149.2 units. With 731 observations each, the largest |z| against the grand mean is 2.99 — exactly what chance produces across 100 groups. **No fast/slow-moving classification was built**, because it would rank sampling error.

**4. Discount, promotion, weather and competitor pricing carry no signal.** Promotion days average 136.4 units against 136.5 on non-promotion days (p = 0.92). Discount tiers are flat (p = 0.46). No uplift or elasticity measures were built.

---

## Approach

### The unit of decision is the position-day

Classification happens per store-product **per day**, not per product.

Averaged across 731 days, all 100 positions sit near 2.0 days of cover and classify as healthy. The variation is entirely within positions over time. A product-level classification would report that nothing is ever wrong, while 18.7% of individual position-days sit below one day of cover.

### Days of cover

```
Days of Cover = Inventory Level ÷ Average Daily Demand (trailing 28 days)
```

Trailing rather than full-period, because a planner deciding on 2022-06-15 has the previous 28 days, not the following 18 months. Using the full-period mean would leak future information into a past-dated decision.

### Classification bands

| Status | Rule | Action | Share of position-days |
|---|---|---|---|
| Critical | Cover < 1.0 day | REPLENISH NOW | 18.7% |
| Below Reorder | 1.0–1.5 days | REPLENISH | 15.5% |
| Healthy | 1.5–3.0 days | MAINTAIN | 46.7% |
| Excess | Cover > 3.0 days | REDUCE STOCK | 19.1% |

Thresholds are calibrated to the observed cover distribution (25th percentile 1.19, median 2.00, 75th percentile 2.84) and exposed as editable parameters in both the workbook and the dashboard.

### The noise band

Before any position is singled out, its exception rate is tested against sampling variation:

```
Noise band = system rate ± 2.8 × √(p(1−p) ÷ 731)
```

| Metric | System rate | Band | Positions outside |
|---|---|---|---|
| % days Critical | 18.68% | 14.64% – 22.72% | **0 of 100** |
| % days Excess | 19.11% | 15.04% – 23.18% | **10 of 100** |

Only positions outside the band are flagged. Ninety-five of the hundred classify as Routine. Full reasoning in [`documentation/business_rules.md`](documentation/business_rules.md).

---

## Key findings

Full detail with supporting figures in [`documentation/insights_and_recommendations.md`](documentation/insights_and_recommendations.md).

### 1. Replenishment is statistically unrelated to need

| Relationship | Correlation |
|---|---|
| Units Ordered vs Units Sold | −0.0009 |
| Units Ordered vs Inventory Level | +0.0011 |
| Units Ordered vs Days of Cover | +0.0011 |

| Position status when ordered | Avg units ordered |
|---|---|
| Critical (< 1 day cover) | 110.1 |
| Below Reorder | 109.8 |
| Healthy | 109.9 |
| Excess (> 3 days cover) | 110.4 |

**1,541,709 units — roughly $85.5M at retail — were ordered into positions already classified as Excess.**

### 2. The demand forecast is systematically inflated

Mean error +5.03 units per position-day. MAE 8.34, so most of the error is systematic rather than random. The forecast exceeds actual sales on 66.7% of days; a calibrated forecast sits near 50%. The bias is identical across all five stores (+4.98 to +5.13), pointing at the method rather than local behaviour.

### 3. Inventory sits at both extremes at once

A third of position-days sit at or below the reorder point while a fifth sit above target cover.

| Metric | Value |
|---|---|
| Stockout-risk position-days | 2,585 (3.54%) |
| Sold-out position-days | 369 (0.50%) |
| Unserved units | 17,294 |
| Retail value of unserved demand | $951,717 |
| Implied service level | 96.5% |
| Avg daily inventory value (retail) | $1,516,383 |
| Avg daily value above 3-day cover | $64,602 (4.3%) |

### 4. The problem is systemic, not product-specific

Not one of the 100 positions has stockout exposure distinguishable from the system average. Across the five stores, critical rates span just 0.50 percentage points (18.41% to 18.91%) and excess rates 1.53 points. Five independent stores behaving this similarly is one shared process, not five local habits.

### 5. Demand is flat, and four planned drivers explain nothing

Year-on-year: −0.42% units, −1.03% revenue. No trend, no seasonality, no day-of-week effect. Stationary demand removes the usual excuse for stock imbalance — when demand is this predictable and a third of positions still sit below the reorder point, the fault is in the replenishment rule.

---

## Recommendations

1. **Replace fixed-quantity ordering with a cover-targeting rule.** `Order = MAX(0, Avg Daily Demand × 3 − Current Inventory)`. On the final day of the panel this produces 14,845 units allocated by need against 11,234 allocated at random. Verify by tracking the correlation between Units Ordered and Days of Cover — currently 0.001, and it should turn strongly negative.
2. **Subtract the measured forecast bias.** One arithmetic step moves the over-forecast rate from 66.7% toward 50%. Recompute the bias monthly so it self-corrects.
3. **Review exceptions daily at position level**, using the Action Register. On 2024-01-01: 17 REPLENISH NOW, 20 REPLENISH, 48 MAINTAIN, 15 REDUCE STOCK. Don't build a fixed problem-product watchlist — finding 4 shows there aren't any.
4. **Treat target cover as a tunable lever.** The what-if parameter quantifies the capital-versus-service trade-off. The right threshold depends on holding cost and stockout cost, and this dataset contains neither — so the analysis presents the trade-off rather than asserting an optimum it can't support.
5. **Monitor the ten genuine excess-exposure positions, and only those.**
6. **Fix the data model before extending the analysis:** stable category/region per entity, a reconciling inventory ledger, and a unit cost column.

---

## Technical implementation

### Python — profiling and preparation

`scripts/01_profile_dataset.py` audits the raw file: grain, dimension validity, the balance-equation test, the signal-versus-noise test, forecast quality and significance tests on the demand drivers.

`scripts/02_build_analysis_dataset.py` builds the star schema and 14 derived columns — days of cover, reorder point, excess units and value, stockout flags, unserved units, forecast error, order requirement and gap, status and action. Policy thresholds sit in one parameter block at the top.

`scripts/03_build_excel_workbook.py` generates the workbook.

### Excel — reporting layer

`excel/inventory_analysis.xlsx`, nine sheets, 1,594 live formulas:

| Sheet | Purpose |
|---|---|
| README | Legend, assumptions, why classification is per-day |
| Parameters | Editable thresholds (yellow input cells) plus the derived noise band |
| Action_Register | 100 positions on the latest date, with live status and order quantities |
| SKU_Scorecard | Exception frequency per position with the noise-band test |
| Monthly_Summary | 25 periods, with a partial-month flag |
| Store_Summary | Store roll-up via SUMIF / AVERAGEIF / COUNTIFS |
| KPI_Dashboard | 22 formula-driven KPIs in six groups |
| Data_Dictionary | All 32 source and derived fields |
| Raw_Sample | First 500 source rows |

Change a threshold on Parameters and the Action Register re-prioritises, the scorecard re-flags, and the KPIs update. Nothing is hardcoded.

### Power Query — transformation

`powerbi/power_query_M.txt` — six queries with a full transformation log: header promotion, explicit typing, text standardisation, blank-key removal, de-duplication on the composite grain, key generation, a merge for per-SKU demand statistics, 14 derived columns, classification, renaming, and column removal.

The cleaning steps remove zero rows from the current file. They exist so the pipeline survives a dirtier refresh, and the row count is asserted after each stage.

### VBA — automation

`vba/inventory_automation.bas`, two macros:

- **`ConsolidateMonthlyFiles`** — folder picker, loops every monthly CSV, validates each file's shape before importing, stacks into `Master_Data` with a source-file tag, then trims text, coerces dates, drops incomplete keys and de-duplicates on the composite grain.
- **`BuildActionRegister`** — reads `Master_Data` into an array in one pass, computes average demand and days of cover per position, classifies against the thresholds on the Parameters sheet, writes a formatted register sorted most-urgent-first with colour-coded status.

Both have error handling, restore application state on failure, and read thresholds from the worksheet so macro and formulas can never disagree.

### Power BI — model and dashboard

`powerbi/dashboard_spec.md` and `powerbi/dax_measures.txt`.

Star schema: `FactInventory` (73,100 rows) with `DimDate` (731), `DimProduct` (20), `DimStore` (5), all many-to-one and single-direction, plus a disconnected what-if parameter table.

28 DAX measures in seven folders: sales and demand, inventory position, stock status counts, service risk, forecast quality, replenishment discipline, helpers. Each with its formula and a note on why it's written that way — including why inventory value uses `AVERAGEX` over dates rather than `SUM` (it's a stock measure, not a flow; summing across 731 days overstates it 731-fold).

Three pages: Inventory Overview, Demand & Forecast Quality, Inventory Risk & Actions. The third carries the action register, the what-if capital trade-off, and the two cards showing average order size when critical against when excess.

> **Note on the `.pbix`:** the binary must be produced in Power BI Desktop. The spec contains every query, measure, relationship, visual placement and interaction setting needed, plus a validation table of twelve figures to check the build against.

---

## Project structure

```
Inventory-Optimization-Demand-Analysis/
│
├── data/
│   ├── raw/
│   │   └── retail_store_inventory.csv        73,100 x 15, unmodified
│   └── processed/
│       ├── fact_inventory_daily.csv          73,100 x 34
│       ├── dim_date.csv                      731 rows
│       ├── dim_product.csv                   20 rows
│       ├── dim_store.csv                     5 rows
│       ├── sku_scorecard.csv                 100 positions
│       └── monthly_summary.csv               25 periods
│
├── scripts/
│   ├── 01_profile_dataset.py                 Audit and statistical tests
│   ├── 02_build_analysis_dataset.py          Star schema + derived columns
│   └── 03_build_excel_workbook.py            Workbook generation
│
├── excel/
│   └── inventory_analysis.xlsx               9 sheets, 1,594 formulas
│
├── vba/
│   └── inventory_automation.bas              2 macros
│
├── powerbi/
│   ├── power_query_M.txt                     6 queries + transformation log
│   ├── dax_measures.txt                      28 measures
│   └── dashboard_spec.md                     Model + 3-page build spec
│
├── documentation/
│   ├── data_quality_report.md                Audit and four defects
│   ├── business_rules.md                     Thresholds and reasoning
│   └── insights_and_recommendations.md       Findings with figures
│
├── screenshots/
└── README.md
```

---

## How to run

**Requirements:** Python 3.9+ with pandas, numpy, scipy, openpyxl · Excel 2016+ · Power BI Desktop

```bash
git clone <repo-url>
cd Inventory-Optimization-Demand-Analysis
pip install pandas numpy scipy openpyxl

python scripts/01_profile_dataset.py          # audit — read this output first
python scripts/02_build_analysis_dataset.py   # builds data/processed/
python scripts/03_build_excel_workbook.py     # builds the workbook
```

**Excel:** open `excel/inventory_analysis.xlsx`, start at the README sheet, edit thresholds on Parameters, read the Action Register.

**VBA:** open the workbook → Alt+F11 → File → Import File → `vba/inventory_automation.bas` → save as `.xlsm` → Alt+F8 to run.

**Power BI:** follow `powerbi/dashboard_spec.md`. Build the six queries from `power_query_M.txt`, create the relationships, add the 28 measures from `dax_measures.txt`, then build the three pages. Check your build against the validation table at the end of the spec.

---

## Limitations

Stated plainly, because the limits are part of the result.

1. **True demand on sold-out days is censored.** Units Sold never exceeds Inventory Level, so demand on 369 position-days is a lower bound.
2. **Excess inventory can't be costed.** Without holding cost, "4.3% above target" can't become a dollar cost of carrying it.
3. **Stockout cost is unknown.** The $951,717 of unserved demand assumes it's lost rather than deferred.
4. **Lead time is unavailable** — no field, and the inventory ledger doesn't reconcile, so it can't be inferred either.
5. **This is synthetic data.** Twenty products with statistically identical demand distributions doesn't happen in real retail. The methods transfer; the specific conclusions about product behaviour don't.

---

## What this project deliberately does not do

Each of the following appeared in the original plan and was dropped once the data was profiled. Being able to explain why is the point.

| Not built | Reason |
|---|---|
| Fast/slow-moving product ranking | Differences within sampling noise (max \|z\| = 2.99 over 100 groups) |
| Category and regional demand analysis | Category and Region are transaction labels, not entity attributes |
| Promotion uplift, discount elasticity | No measurable effect (p = 0.92, p = 0.46) |
| Gross margin, COGS-based turnover | No cost column |
| Supplier scorecard, lead-time variance | No supplier or lead-time column |
| ABC / Pareto classification | Top position holds 1.12% of revenue against 1.00% for uniform — no Pareto curve |
| Economic Order Quantity | Requires ordering and holding costs, neither present |
| Machine learning demand forecasting | Demand is stationary with no usable predictors; a mean is the correct model |

Each would produce numbers. None of the numbers would mean anything.
