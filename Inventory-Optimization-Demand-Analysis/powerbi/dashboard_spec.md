# Power BI Build Specification

Everything needed to build `Inventory_Optimization_Dashboard.pbix`: the data model, then three report pages laid out visual by visual.

> The `.pbix` itself is a binary Power BI file and has to be produced in Power BI Desktop. This spec plus `power_query_M.txt` and `dax_measures.txt` contains every query, measure, relationship and visual placement needed to build it. Expect two to three hours.

---

## 1. Data model

A star schema: one fact table, three dimensions, one disconnected parameter table.

```
                    ┌──────────────┐
                    │   DimDate    │
                    │  731 rows    │
                    └──────┬───────┘
                           │ 1
                           │
                           │ *
┌──────────────┐    ┌──────┴────────┐    ┌──────────────┐
│  DimProduct  │ 1  │ FactInventory │  * │   DimStore   │
│   20 rows    ├───*│  73,100 rows  │*───┤   5 rows     │
└──────────────┘    └───────────────┘  1 └──────────────┘

┌──────────────────┐
│ 'Cover Threshold'│   disconnected — read via SELECTEDVALUE
│   12 rows        │
└──────────────────┘
```

### Relationships

| From | Column | To | Column | Cardinality | Direction | Active |
|---|---|---|---|---|---|---|
| FactInventory | Date_Key | DimDate | Date_Key | Many-to-one | Single | Yes |
| FactInventory | Product_ID | DimProduct | Product_ID | Many-to-one | Single | Yes |
| FactInventory | Store_ID | DimStore | Store_ID | Many-to-one | Single | Yes |

All single-direction. Bidirectional filtering isn't needed here and creates ambiguity as models grow — worth saying out loud if you're asked why.

### Mark the date table

Select DimDate → Table tools → Mark as date table → Date column: `Date`. Skipping this breaks `SAMEPERIODLASTYEAR` and `DATEADD` in the YoY and MoM measures.

### Column data types

| Table | Column | Type | Format |
|---|---|---|---|
| FactInventory | Date | Date | yyyy-mm-dd |
| FactInventory | Date_Key | Whole number | — |
| FactInventory | SKU_Key, Store_ID, Product_ID, Category, Region | Text | — |
| FactInventory | Inventory_Level, Units_Sold, Units_Ordered | Whole number | #,##0 |
| FactInventory | Price, Net_Price, Revenue, Inventory_Value, Excess_Value | Decimal | $#,##0.00 |
| FactInventory | Days_of_Cover, Avg_Daily_Demand, Reorder_Point | Decimal | 0.00 |
| FactInventory | Stock_Status, Recommended_Action | Text | — |
| DimDate | Date | Date | — |
| DimDate | Year, Month_Num, Is_Weekend, Is_Complete_Month | Whole number | — |

### Sort orders

- DimDate[Month_Name] → sort by [Month_Num], otherwise months appear alphabetically.
- Create a `Status_Sort` column on FactInventory so status charts read in severity order rather than alphabetically:

```
Status_Sort =
SWITCH ( FactInventory[Stock_Status],
    "Critical", 1,
    "Below Reorder", 2,
    "Healthy", 3,
    "Excess", 4,
    5 )
```

Then set Stock_Status → Sort by column → Status_Sort.

### Hide from report view

Hide `Date_Key`, `Status_Sort`, and every `SKUProfile` column. They're plumbing, and a clean field list is part of the deliverable.

---

## 2. Theme

Custom theme JSON (View → Themes → Customize):

| Role | Hex | Used for |
|---|---|---|
| Primary | `#1F3864` | Titles, KPI card text |
| Critical | `#C00000` | Critical status, stockout risk |
| Warning | `#ED7D31` | Below Reorder |
| Healthy | `#548235` | Healthy status |
| Excess | `#7F7F7F` | Excess status |
| Background | `#F5F5F5` | Page canvas |

Use the same status colours on all three pages. A manager should learn the colour code once.

Page size: 1280 × 720 (16:9). Font: Segoe UI throughout.

---

## 3. Page 1 — Inventory Overview

*Question this page answers: how healthy is inventory overall, and is it getting better or worse?*

### Layout grid (1280 × 720)

**Row 1 — title bar** (y: 0–60)
- Text box, full width: **"Inventory Optimization & Demand Analysis"**, 24pt, primary colour.
- Right-aligned card: `Latest Date`, label "Data through".

**Row 2 — KPI cards** (y: 70–190, six cards, each 200 × 110, 10px gaps)

| # | Measure | Label | Format |
|---|---|---|---|
| 1 | `Total Revenue` | Total Revenue | $#,##0,, "M" |
| 2 | `Total Units Sold` | Units Sold | #,##0,, "M" |
| 3 | `Inventory Value` | Avg Inventory Value | $#,##0,, "M" |
| 4 | `Avg Days of Cover` | Days of Cover | 0.00 |
| 5 | `Critical Rate %` | Critical Rate | 0.0% |
| 6 | `Service Level %` | Service Level | 0.0% |

Conditional formatting on cards 5 and 6: card 5 red above 15%, card 6 red below 95%.

**Row 3 — trend and breakdown** (y: 200–450)

- **Line chart** (x: 0–640): *Monthly Demand and Cover*
  - X-axis: `DimDate[Year_Month]`
  - Y-axis 1: `Total Units Sold`
  - Y-axis 2 (secondary): `Avg Days of Cover`
  - **Visual-level filter: `DimDate[Is_Complete_Month] = 1`** — without this the single day in January 2024 renders as a cliff and the chart lies.

- **Donut chart** (x: 650–960): *Position-Days by Stock Status*
  - Legend: `Stock_Status`, Values: `COUNTROWS(FactInventory)`
  - Fixed status colours. Detail labels: category + percent.

- **Stacked column** (x: 970–1280): *Stock Status by Store*
  - X-axis: `DimStore[Store_ID]`, Y-axis: count of rows, Legend: `Stock_Status`, 100% stacked.
  - This one is deliberately unremarkable: all five stores land within a point of each other. That flatness is the finding, and it's what tells you the problem isn't location-specific.

**Row 4 — exception counters** (y: 460–580, four cards)

| Measure | Label |
|---|---|
| `Critical Position Days` | Critical Position-Days |
| `Below Reorder Position Days` | Below Reorder |
| `Excess Position Days` | Excess Position-Days |
| `Unserved Revenue at Risk` | Revenue at Risk |

**Row 5 — slicers** (y: 590–700, horizontal strip)
- `DimDate[Date]` — between slicer
- `DimStore[Store_ID]` — dropdown
- `DimProduct[Product_ID]` — dropdown
- `FactInventory[Stock_Status]` — tile

Sync all four slicers across all three pages: View → Sync slicers → tick Sync and Visible for each page.

---

## 4. Page 2 — Demand & Forecast Quality

*Question: how does demand behave, and can we trust the forecast we're planning against?*

**Row 1 — KPI cards** (y: 70–190)

| Measure | Label | Format |
|---|---|---|
| `Avg Daily Demand per SKU` | Avg Daily Demand / SKU | #,##0.0 |
| `Forecast Bias` | Forecast Bias (units) | +0.00;-0.00 |
| `Forecast MAE` | Forecast MAE | 0.00 |
| `Forecast MAPE %` | Forecast MAPE | 0.0% |
| `Over-Forecast Rate %` | Over-Forecast Rate | 0.0% |
| `Revenue YoY %` | Revenue YoY | +0.0%;-0.0% |

Put a text box under the Over-Forecast card: *"A calibrated forecast sits near 50%."* One line of context turns a number into a judgement.

**Row 2** (y: 200–450)

- **Line chart** (x: 0–640): *Actual vs Forecast Demand, Monthly*
  - X-axis: `Year_Month` (filtered to complete months)
  - Lines: `Total Units Sold` and `SUM(Demand_Forecast)`
  - The forecast line sits consistently above actuals. That visible, constant gap is the page's headline.

- **Column chart** (x: 650–1280): *Forecast Bias by Store*
  - X-axis: `Store_ID`, Y-axis: `Forecast Bias`
  - All five bars land near +5.0. Uniform bias across every store points at the forecasting method, not at local behaviour.

**Row 3** (y: 460–650)

- **Scatter chart** (x: 0–640): *Demand vs Inventory by Position*
  - X: `Avg Daily Demand per SKU`, Y: `Avg Inventory Units`, Details: `SKU_Key`
  - The 100 points cluster tightly — the visual proof that no position is a genuine outlier on demand.

- **Table** (x: 650–1280): *Position Demand Profile*
  - Columns: `SKU_Key`, `Avg Daily Demand per SKU`, `Avg Days of Cover`, `Inventory Turnover`, `Critical Rate %`, `Excess Rate %`
  - Sort descending by `Critical Rate %`. Data bars on the two rate columns.

**Optional — Category and Region visuals.** If you add a "Units by Category" bar chart, put a caption on it: *"Category is a transaction label in this dataset, not a product attribute — shown for completeness, not as a demand driver."* Better to leave it out than to leave it uncaptioned; an interviewer who checks will find all five bars equal.

---

## 5. Page 3 — Inventory Risk & Actions

*Question: what do we do tomorrow morning?* This is the page that makes the project a decision tool rather than a report.

**Row 1 — action counters** (y: 70–190, four cards, colour-coded by status)

| Measure | Label | Colour |
|---|---|---|
| `Critical Position Days` filtered to `Date = Latest Date` | Replenish Now | Critical red |
| `Below Reorder Position Days` filtered to Latest Date | Replenish | Warning orange |
| `Healthy Position Days` filtered to Latest Date | Maintain | Healthy green |
| `Excess Position Days` filtered to Latest Date | Reduce Stock | Excess grey |

On 2024-01-01 these read 17 / 20 / 48 / 15.

**Row 2 — the action register** (y: 200–470, full width)

Table visual, filtered to `Date = Latest Date`:

| Column | Source |
|---|---|
| SKU Key | `FactInventory[SKU_Key]` |
| Store | `FactInventory[Store_ID]` |
| Product | `FactInventory[Product_ID]` |
| Inventory | `Inventory_Level` |
| Avg Daily Demand | `Avg_Daily_Demand` |
| Days of Cover | `Days_of_Cover` |
| Order Qty to Target | `Order_Requirement` |
| Units Ordered | `Units_Ordered` |
| Order Gap | `Order_Gap` |
| Inventory Value | `Inventory_Value` |
| Recommended Action | `Recommended_Action` |

- Sort ascending by Days of Cover so the most urgent rows sit at the top.
- Conditional background on Recommended Action, matching the status palette.
- Data bars on Days of Cover.
- Turn on "Show items with no data" = off.

**Row 3 — the capital trade-off** (y: 480–700)

- **What-if slicer** (x: 0–260): `'Cover Threshold'[Cover Threshold]`, 0.5 to 6.0.
- **Card** (x: 270–520): `Excess at Selected Threshold`, label "Capital Above Target Cover".
- **Column chart** (x: 530–900): *Units Ordered by Stock Status*
  - X: `Stock_Status`, Y: `Total Units Ordered`
  - The four bars are nearly equal. That's the random-ordering finding rendered in one visual — and the single most useful chart in the report.
- **Card pair** (x: 910–1280): `Avg Order When Critical` and `Avg Order When Excess` side by side. 110.1 against 110.4.

**Text box footer** (y: 700–720), 9pt grey:

> Inventory valued at retail price; the source data contains no cost column. Reorder point and target cover are policy parameters, not source fields. Category and Region are transaction labels and are not used in any recommendation.

Putting the caveats on the page rather than burying them in the README is the difference between a student dashboard and a professional one.

---

## 6. Interactions and navigation

- **Drill-through**: create a drill-through page keyed on `SKU_Key` showing that position's daily cover line, inventory level, and units ordered over the full 731 days. Right-click any row in the action register to reach it.
- **Bookmarks**: two on page 3 — "All positions" and "Exceptions only" (filtered to Critical + Below Reorder) — wired to buttons.
- **Tooltips**: build a tooltip page (320 × 240) showing days of cover and stock status; attach it to the scatter and the status charts.
- **Edit interactions**: on page 3, set the what-if slicer to *not* filter the action register — it should only drive the excess-capital card. Otherwise moving the slider silently reshuffles the action list.

---

## 7. Build checklist

- [ ] Six Power Query queries created; `pSourcePath` points at your local `data/raw/`
- [ ] `SKUProfile` and `pSourcePath` set to not load
- [ ] FactInventory loads 73,100 rows — verify before continuing
- [ ] Three relationships created, all many-to-one, single direction
- [ ] DimDate marked as a date table
- [ ] `Status_Sort` column added; Stock_Status sorted by it
- [ ] `_Measures` table created; all 28 measures added and folder-organised
- [ ] `Cover Threshold` what-if parameter created
- [ ] Theme applied; status colours consistent across pages
- [ ] Page 1 built; **`Is_Complete_Month = 1` filter applied to the monthly trend**
- [ ] Page 2 built
- [ ] Page 3 built; caveat footer added
- [ ] Slicers synced across pages
- [ ] Drill-through page and bookmarks configured
- [ ] Screenshots of all three pages saved to `screenshots/`
- [ ] `.pbix` saved to `powerbi/Inventory_Optimization_Dashboard.pbix`

---

## 8. Validation targets

After building, these should match. If they don't, the model is wrong somewhere.

| Measure | Expected |
|---|---|
| Row count, FactInventory | 73,100 |
| `Total Units Sold` | 9,975,582 |
| `Total Revenue` | $494,971,375 |
| `Avg Days of Cover` | 2.01 |
| `Critical Position Days` | 13,653 |
| `Excess Position Days` | 13,971 |
| `Stockout Risk Days` | 2,585 |
| `Sold Out Days` | 369 |
| `Unserved Units` | 17,294 |
| `Forecast Bias` | +5.03 |
| `Over-Forecast Rate %` | 66.7% |
| Positions needing action on 2024-01-01 | 37 |
