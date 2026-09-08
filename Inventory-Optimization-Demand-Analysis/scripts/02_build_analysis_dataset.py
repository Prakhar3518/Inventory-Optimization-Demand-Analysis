"""
02_build_analysis_dataset.py
============================
Turns the raw CSV into a star schema plus a store-SKU scorecard, ready for
Power BI and Excel.

Every derived column below is computed only from fields that exist in the raw
file. Nothing is fabricated. Policy thresholds live in the PARAMETERS block so
they can be changed in one place and re-run.

Run:  python scripts/02_build_analysis_dataset.py
Input:  data/raw/retail_store_inventory.csv
Output: data/processed/fact_inventory_daily.csv
        data/processed/dim_date.csv
        data/processed/dim_product.csv
        data/processed/dim_store.csv
        data/processed/sku_scorecard.csv
        data/processed/monthly_summary.csv
"""

import numpy as np
import pandas as pd

RAW = "data/raw/retail_store_inventory.csv"
OUT = "data/processed"

# ---------------------------------------------------------------------------
# PARAMETERS
#
# The raw file has no Reorder Level, Lead Time or Unit Cost column, so the
# reorder policy is stated here as an explicit assumption rather than read
# from the data. Thresholds are calibrated to the observed cover distribution
# (25th pct 1.19 days, median 2.00, 75th pct 2.84, max 3.95), which is why the
# bands are set at 1.0 / 1.5 / 3.0 rather than at textbook values.
# ---------------------------------------------------------------------------
CRITICAL_COVER_DAYS = 1.0   # below this, stock covers less than one day of demand
REORDER_COVER_DAYS = 1.5    # reorder point, expressed in days of average demand
TARGET_COVER_DAYS = 3.0     # above this, stock is treated as excess
ROLLING_WINDOW = 28         # days used for the trailing demand rate

# ---------------------------------------------------------------------------
# LOAD AND CLEAN
# ---------------------------------------------------------------------------
df = pd.read_csv(RAW)

# Standardise column names to snake_case so downstream tools stop fighting
# spaces and the "Holiday/Promotion" slash.
df.columns = (df.columns.str.strip()
                        .str.replace("/", "_", regex=False)
                        .str.replace(" ", "_", regex=False))

df["Date"] = pd.to_datetime(df["Date"])
for c in ["Store_ID", "Product_ID", "Category", "Region", "Weather_Condition", "Seasonality"]:
    df[c] = df[c].astype(str).str.strip()

# The profile confirmed zero nulls and zero duplicates. These two lines are
# defensive: they keep the pipeline correct if the source file is ever
# refreshed with dirtier data, and they are a no-op on the current file.
before = len(df)
df = df.drop_duplicates(subset=["Date", "Store_ID", "Product_ID"]).dropna()
if len(df) != before:
    print(f"Removed {before - len(df)} duplicate/null rows")

df = df.sort_values(["Store_ID", "Product_ID", "Date"]).reset_index(drop=True)

# SKU key. Store x Product is the true stock-keeping unit here: one physical
# stock position, tracked daily. Product ID alone is not a stock position
# because the same product sits in 5 stores.
df["SKU_Key"] = df["Store_ID"] + "-" + df["Product_ID"]

# ---------------------------------------------------------------------------
# DERIVED MEASURES
# ---------------------------------------------------------------------------
# Revenue. Price is the shelf price and Discount is a whole-number percent,
# so net revenue applies the discount. There is no cost column, so margin
# cannot be computed and inventory is valued at retail throughout.
df["Net_Price"] = df["Price"] * (1 - df["Discount"] / 100)
df["Revenue"] = df["Units_Sold"] * df["Net_Price"]
df["Inventory_Value"] = df["Inventory_Level"] * df["Price"]

# Average daily demand: a trailing 28-day mean per SKU, which is what a planner
# would actually have on the day. min_periods=7 lets the first weeks compute
# rather than turning into nulls; the SKU's own long-run mean backfills the
# opening days so no row is dropped.
g = df.groupby("SKU_Key")["Units_Sold"]
df["Avg_Daily_Demand"] = (g.transform(lambda s: s.rolling(ROLLING_WINDOW, min_periods=7).mean()))
df["Avg_Daily_Demand"] = df["Avg_Daily_Demand"].fillna(g.transform("mean"))
df["Demand_StdDev"] = g.transform(lambda s: s.rolling(ROLLING_WINDOW, min_periods=7).std())
df["Demand_StdDev"] = df["Demand_StdDev"].fillna(g.transform("std"))

# Days of cover: how many days the current stock would last at the recent
# demand rate. This is the spine of the whole analysis, because it is the one
# dimension in this dataset with genuine variation.
df["Days_of_Cover"] = df["Inventory_Level"] / df["Avg_Daily_Demand"].replace(0, np.nan)

# Reorder point expressed in units, from the policy parameter above.
df["Reorder_Point"] = df["Avg_Daily_Demand"] * REORDER_COVER_DAYS
df["Below_Reorder_Point"] = (df["Inventory_Level"] < df["Reorder_Point"]).astype(int)

# Excess units: stock held above the target cover level, and the capital it
# represents at retail price.
df["Excess_Units"] = (df["Inventory_Level"] - df["Avg_Daily_Demand"] * TARGET_COVER_DAYS).clip(lower=0)
df["Excess_Value"] = df["Excess_Units"] * df["Price"]

# Stockout signals.
#  - Sold_Out: the day ended with every unit gone, so true demand was censored.
#  - Unserved_Units: forecast demand the position could not have covered.
df["Sold_Out"] = (df["Units_Sold"] == df["Inventory_Level"]).astype(int)
df["Unserved_Units"] = (df["Demand_Forecast"] - df["Inventory_Level"]).clip(lower=0)
df["Stockout_Risk"] = (df["Demand_Forecast"] > df["Inventory_Level"]).astype(int)

# Forecast error. Positive = the forecast ran above what actually sold.
df["Forecast_Error"] = df["Demand_Forecast"] - df["Units_Sold"]
df["Abs_Forecast_Error"] = df["Forecast_Error"].abs()

# Order gap: what the order should have been to reach target cover, versus
# what was actually ordered. Quantifies the random-ordering finding per row.
df["Order_Requirement"] = (df["Avg_Daily_Demand"] * TARGET_COVER_DAYS - df["Inventory_Level"]).clip(lower=0)
df["Order_Gap"] = df["Units_Ordered"] - df["Order_Requirement"]


# ---------------------------------------------------------------------------
# CLASSIFICATION
# Four mutually exclusive bands, each mapping to one recommended action.
# Deliberately simple: a manager reads the band, not the formula.
# ---------------------------------------------------------------------------
def classify(cover):
    if cover < CRITICAL_COVER_DAYS:
        return "Critical"
    if cover < REORDER_COVER_DAYS:
        return "Below Reorder"
    if cover <= TARGET_COVER_DAYS:
        return "Healthy"
    return "Excess"


ACTION = {
    "Critical": "REPLENISH NOW",
    "Below Reorder": "REPLENISH",
    "Healthy": "MAINTAIN",
    "Excess": "REDUCE STOCK",
}

df["Stock_Status"] = df["Days_of_Cover"].apply(classify)
df["Recommended_Action"] = df["Stock_Status"].map(ACTION)

# ---------------------------------------------------------------------------
# DIMENSION TABLES
# ---------------------------------------------------------------------------
dates = pd.DataFrame({"Date": pd.date_range(df["Date"].min(), df["Date"].max(), freq="D")})
dates["Date_Key"] = dates["Date"].dt.strftime("%Y%m%d").astype(int)
dates["Year"] = dates["Date"].dt.year
dates["Quarter"] = "Q" + dates["Date"].dt.quarter.astype(str)
dates["Month_Num"] = dates["Date"].dt.month
dates["Month_Name"] = dates["Date"].dt.strftime("%b")
dates["Year_Month"] = dates["Date"].dt.strftime("%Y-%m")
dates["Day_Name"] = dates["Date"].dt.day_name()
dates["Is_Weekend"] = dates["Day_Name"].isin(["Saturday", "Sunday"]).astype(int)
# The panel ends on 2024-01-01, so January 2024 holds a single day. Flagging it
# stops the monthly trend line from showing a fake collapse in the last point.
month_days = dates.groupby("Year_Month")["Date"].transform("size")
dates["Is_Complete_Month"] = (month_days >= 28).astype(int)

# Product dimension. Category is NOT included here: the profile proved it
# varies row to row for the same product, so it is not a product attribute.
# It stays on the fact table as a transaction label.
dim_product = (df.groupby("Product_ID")
                 .agg(Total_Units_Sold=("Units_Sold", "sum"),
                      Avg_Daily_Demand=("Units_Sold", "mean"),
                      Avg_Price=("Price", "mean"))
                 .round(2).reset_index())

dim_store = (df.groupby("Store_ID")
               .agg(Total_Units_Sold=("Units_Sold", "sum"),
                    Avg_Inventory=("Inventory_Level", "mean"),
                    Avg_Daily_Revenue=("Revenue", "sum"))
               .round(2).reset_index())
dim_store["Avg_Daily_Revenue"] = (dim_store["Avg_Daily_Revenue"] / df["Date"].nunique()).round(2)

# ---------------------------------------------------------------------------
# STORE-SKU SCORECARD  (100 rows - the Excel reporting layer)
# ---------------------------------------------------------------------------
sc = (df.groupby(["SKU_Key", "Store_ID", "Product_ID"])
        .agg(Total_Units_Sold=("Units_Sold", "sum"),
             Total_Revenue=("Revenue", "sum"),
             Avg_Daily_Demand=("Units_Sold", "mean"),
             Demand_StdDev=("Units_Sold", "std"),
             Avg_Inventory=("Inventory_Level", "mean"),
             Avg_Inventory_Value=("Inventory_Value", "mean"),
             Avg_Days_of_Cover=("Days_of_Cover", "mean"),
             Days_Critical=("Stock_Status", lambda s: (s == "Critical").sum()),
             Days_Excess=("Stock_Status", lambda s: (s == "Excess").sum()),
             Sold_Out_Days=("Sold_Out", "sum"),
             Stockout_Risk_Days=("Stockout_Risk", "sum"),
             Unserved_Units=("Unserved_Units", "sum"),
             Avg_Excess_Value=("Excess_Value", "mean"),
             Forecast_Bias=("Forecast_Error", "mean"),
             Forecast_MAE=("Abs_Forecast_Error", "mean"),
             Avg_Units_Ordered=("Units_Ordered", "mean"),
             Observation_Days=("Units_Sold", "size"))
        .reset_index())

years = df["Date"].nunique() / 365.25
sc["Inventory_Turnover"] = (sc["Total_Units_Sold"] / sc["Avg_Inventory"] / years).round(2)
sc["Demand_CV"] = (sc["Demand_StdDev"] / sc["Avg_Daily_Demand"]).round(3)
sc["Pct_Days_Critical"] = (100 * sc["Days_Critical"] / sc["Observation_Days"]).round(2)
sc["Pct_Days_Excess"] = (100 * sc["Days_Excess"] / sc["Observation_Days"]).round(2)
sc = sc.round(2)

# ---------------------------------------------------------------------------
# MONTHLY SUMMARY
# ---------------------------------------------------------------------------
df["Year_Month"] = df["Date"].dt.strftime("%Y-%m")
monthly = (df.groupby("Year_Month")
             .agg(Units_Sold=("Units_Sold", "sum"),
                  Revenue=("Revenue", "sum"),
                  Avg_Inventory=("Inventory_Level", "mean"),
                  Avg_Days_of_Cover=("Days_of_Cover", "mean"),
                  Critical_Positions=("Stock_Status", lambda s: (s == "Critical").sum()),
                  Excess_Positions=("Stock_Status", lambda s: (s == "Excess").sum()),
                  Excess_Value=("Excess_Value", "mean"),
                  Forecast_Bias=("Forecast_Error", "mean"),
                  Position_Days=("Units_Sold", "size"))
             .round(2).reset_index())
monthly = monthly.merge(dates.groupby("Year_Month")["Is_Complete_Month"].max().reset_index(),
                        on="Year_Month", how="left")

# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------
fact_cols = [
    "Date", "SKU_Key", "Store_ID", "Product_ID", "Category", "Region",
    "Weather_Condition", "Seasonality", "Holiday_Promotion", "Discount",
    "Inventory_Level", "Units_Sold", "Units_Ordered", "Demand_Forecast",
    "Price", "Net_Price", "Competitor_Pricing", "Revenue", "Inventory_Value",
    "Avg_Daily_Demand", "Days_of_Cover", "Reorder_Point", "Below_Reorder_Point",
    "Excess_Units", "Excess_Value", "Sold_Out", "Stockout_Risk", "Unserved_Units",
    "Forecast_Error", "Abs_Forecast_Error", "Order_Requirement", "Order_Gap",
    "Stock_Status", "Recommended_Action",
]
fact = df[fact_cols].copy()
num = fact.select_dtypes("number").columns
fact[num] = fact[num].round(2)
fact["Date"] = fact["Date"].dt.strftime("%Y-%m-%d")

fact.to_csv(f"{OUT}/fact_inventory_daily.csv", index=False)
dates.drop(columns=["Date"]).assign(Date=dates["Date"].dt.strftime("%Y-%m-%d")).to_csv(
    f"{OUT}/dim_date.csv", index=False)
dim_product.to_csv(f"{OUT}/dim_product.csv", index=False)
dim_store.to_csv(f"{OUT}/dim_store.csv", index=False)
sc.to_csv(f"{OUT}/sku_scorecard.csv", index=False)
monthly.to_csv(f"{OUT}/monthly_summary.csv", index=False)

print(f"fact_inventory_daily : {len(fact):,} rows x {fact.shape[1]} cols")
print(f"dim_date             : {len(dates):,} rows")
print(f"dim_product          : {len(dim_product):,} rows")
print(f"dim_store            : {len(dim_store):,} rows")
print(f"sku_scorecard        : {len(sc):,} rows")
print(f"monthly_summary      : {len(monthly):,} rows")
print("\nStock status distribution:")
print((fact["Stock_Status"].value_counts(normalize=True) * 100).round(2).to_string())
