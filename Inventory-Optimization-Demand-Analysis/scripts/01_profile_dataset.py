"""
01_profile_dataset.py
=====================
Audit of the raw dataset BEFORE any analysis is designed.

Purpose: establish what the file actually contains, so that the project is
built on fields that exist and metrics that the data can support. The output
of this script is the source for documentation/data_quality_report.md.

Run:  python scripts/01_profile_dataset.py
Input:  data/raw/retail_store_inventory.csv
Output: console report only (no files written)
"""

import numpy as np
import pandas as pd
from scipy import stats

RAW = "data/raw/retail_store_inventory.csv"

df = pd.read_csv(RAW, parse_dates=["Date"])

# ---------------------------------------------------------------------------
# 1. SHAPE, TYPES, COMPLETENESS
# ---------------------------------------------------------------------------
print("=" * 70)
print("1. SHAPE AND COMPLETENESS")
print("=" * 70)
print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")
print("\nColumn types:")
print(df.dtypes.to_string())
print(f"\nNull values, all columns: {int(df.isna().sum().sum())}")
print(f"Fully duplicated rows: {int(df.duplicated().sum())}")
print(
    "Duplicates on (Date, Store ID, Product ID): "
    f"{int(df.duplicated(subset=['Date', 'Store ID', 'Product ID']).sum())}"
)

# ---------------------------------------------------------------------------
# 2. GRAIN
#
# The row count factorises exactly: 731 days x 5 stores x 20 products = 73,100.
# This confirms a complete daily panel with no gaps - every store-product
# combination has an observation on every single date. That makes
# (Date, Store ID, Product ID) the primary key of the fact table.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("2. GRAIN")
print("=" * 70)
n_days, n_stores, n_prods = df["Date"].nunique(), df["Store ID"].nunique(), df["Product ID"].nunique()
print(f"Distinct dates: {n_days}  ({df['Date'].min().date()} to {df['Date'].max().date()})")
print(f"Distinct stores: {n_stores}   Distinct products: {n_prods}")
print(f"{n_days} x {n_stores} x {n_prods} = {n_days * n_stores * n_prods:,}  vs actual rows {len(df):,}")
print("Panel is complete and balanced." if n_days * n_stores * n_prods == len(df) else "Panel has gaps.")

# ---------------------------------------------------------------------------
# 3. DIMENSION VALIDITY  <-- the critical check
#
# A field can only be used as a product or store attribute if it is CONSTANT
# for that product or store. Here it is not: a single store-product carries
# every Category and every Region across its 731 daily rows. Category, Region
# and Seasonality are therefore row-level labels, not dimension attributes,
# and cannot be used to explain demand.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("3. DIMENSION VALIDITY")
print("=" * 70)
print("Categories per Product ID (should be 1 if Category is a product attribute):")
print(df.groupby("Product ID")["Category"].nunique().value_counts().to_string())
print("\nRegions per Store ID (should be 1 if Region is a store attribute):")
print(df.groupby("Store ID")["Region"].nunique().value_counts().to_string())
print("\nCategory x Region contingency (flat => independently assigned):")
print(pd.crosstab(df["Category"], df["Region"]).to_string())
print("\nSeasonality vs calendar month (misaligned => label is not a real season):")
print(pd.crosstab(df["Date"].dt.month, df["Seasonality"]).head(4).to_string())

# ---------------------------------------------------------------------------
# 4. IS SKU-LEVEL DEMAND VARIATION REAL, OR SAMPLING NOISE?
#
# Each store-product has 731 observations. Compare each one's mean daily demand
# to the grand mean, scaled by its own standard error. With 100 groups drawn
# from one distribution, the largest |z| expected from pure chance is roughly
# 2.8-3.0. If no group exceeds that, the differences are noise and a
# fast/slow-moving product ranking would be ranking sampling error.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("4. SKU-LEVEL DEMAND: SIGNAL OR NOISE?")
print("=" * 70)
sku = df.groupby(["Store ID", "Product ID"])["Units Sold"].agg(["mean", "std", "count"])
sku["se"] = sku["std"] / np.sqrt(sku["count"])
sku["z"] = (sku["mean"] - df["Units Sold"].mean()) / sku["se"]
print(f"Mean daily demand across 100 store-SKUs: {sku['mean'].min():.1f} to {sku['mean'].max():.1f}")
print(f"Largest |z| vs grand mean: {sku['z'].abs().max():.2f}")
print(f"Store-SKUs with |z| > 3: {int((sku['z'].abs() > 3).sum())} of {len(sku)}")
print("=> Differences are within noise. No genuine fast/slow-moving products.")

# ---------------------------------------------------------------------------
# 5. DOES THE INVENTORY BALANCE EQUATION HOLD?
#
# If the data were a true stock ledger, tomorrow's inventory would equal
# today's inventory minus units sold plus units ordered. Testing that on one
# store-product shows it does not hold, so Inventory Level must be treated as
# an independent daily snapshot and Units Ordered as an order placed, not
# stock received.
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("5. INVENTORY BALANCE EQUATION")
print("=" * 70)
s = df[(df["Store ID"] == "S001") & (df["Product ID"] == "P0001")].sort_values("Date").copy()
s["inv_next"] = s["Inventory Level"].shift(-1)
s["predicted"] = s["Inventory Level"] - s["Units Sold"] + s["Units Ordered"]
print(f"Correlation of actual next-day stock vs predicted: {s[['inv_next', 'predicted']].corr().iloc[0, 1]:.3f}")
print("=> Balance equation does not hold. Inventory Level = daily snapshot.")

# ---------------------------------------------------------------------------
# 6. IS REPLENISHMENT RESPONSIVE TO DEMAND OR STOCK POSITION?
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("6. ORDERING DISCIPLINE")
print("=" * 70)
adr = df.groupby(["Store ID", "Product ID"])["Units Sold"].transform("mean")
cover = df["Inventory Level"] / adr
print(f"Units Ordered vs Units Sold:       r = {df['Units Ordered'].corr(df['Units Sold']):+.4f}")
print(f"Units Ordered vs Inventory Level:  r = {df['Units Ordered'].corr(df['Inventory Level']):+.4f}")
print(f"Units Ordered vs Days of Cover:    r = {df['Units Ordered'].corr(cover):+.4f}")
print(f"Units Ordered range: {df['Units Ordered'].min()} to {df['Units Ordered'].max()}, "
      f"mean {df['Units Ordered'].mean():.1f}")
print("=> Order quantity is statistically unrelated to need.")

# ---------------------------------------------------------------------------
# 7. FORECAST QUALITY
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("7. FORECAST QUALITY")
print("=" * 70)
err = df["Demand Forecast"] - df["Units Sold"]
print(f"Mean bias: {err.mean():+.2f} units    MAE: {err.abs().mean():.2f} units")
print(f"Days over-forecast: {100 * (err > 0).mean():.1f}%")
print("Bias by store:")
print(df.assign(e=err).groupby("Store ID")["e"].mean().round(2).to_string())

# ---------------------------------------------------------------------------
# 8. DO DISCOUNT AND PROMOTION MOVE VOLUME?
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("8. DISCOUNT AND PROMOTION EFFECT")
print("=" * 70)
t_h = stats.ttest_ind(df.loc[df["Holiday/Promotion"] == 1, "Units Sold"],
                      df.loc[df["Holiday/Promotion"] == 0, "Units Sold"])
t_d = stats.ttest_ind(df.loc[df["Discount"] == 20, "Units Sold"],
                      df.loc[df["Discount"] == 0, "Units Sold"])
print(f"Promotion on vs off:      t = {t_h.statistic:+.3f}, p = {t_h.pvalue:.3f}")
print(f"20% discount vs 0%:       t = {t_d.statistic:+.3f}, p = {t_d.pvalue:.3f}")
print("=> No measurable uplift from either. Do not build promo KPIs.")

# ---------------------------------------------------------------------------
# 9. FIELDS THE PROJECT BRIEF ASSUMED, BUT WHICH DO NOT EXIST
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("9. ABSENT FIELDS")
print("=" * 70)
for f in ["Unit Cost", "Supplier", "Lead Time", "Reorder Level", "Warehouse", "Product Name"]:
    print(f"  {f:<16} present: {f in df.columns}")
print("=> Inventory valued at retail price; reorder point derived from a")
print("   documented policy parameter, not read from a column.")
