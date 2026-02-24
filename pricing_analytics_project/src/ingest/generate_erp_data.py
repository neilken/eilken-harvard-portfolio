"""Generate synthetic ERP-style product, customer, sales, and inventory datasets for the project pipeline."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.config import load_params
from src.utils.logging import StepLogger, log_info
from src.utils.validation import basic_sales_sanity


def generate_products(rng: np.random.Generator, n_skus: int) -> pd.DataFrame:
    """Generate products."""
    # Category and family assignments are randomized but constrained to realistic pricing portfolio groupings.
    categories = ["fuel", "intake", "exhaust", "efi", "ignition", "accessories"]
    families = ["street", "race", "oem_plus", "classic", "pro", "builder"]
    brands = ["AutoCore", "AccelType", "FlowLine", "TrackCore"]
    lifecycle = rng.choice(["active", "active", "active", "end_of_life"], size=n_skus)
    launch_dates = pd.to_datetime("2020-01-01") + pd.to_timedelta(rng.integers(0, 1800, n_skus), unit="D")
    return pd.DataFrame(
        {
            "sku": [f"SKU{i+1:05d}" for i in range(n_skus)],
            "product_name": [f"Product {i+1}" for i in range(n_skus)],
            "category": rng.choice(categories, size=n_skus),
            "product_family": rng.choice(families, size=n_skus),
            "brand": rng.choice(brands, size=n_skus),
            "lifecycle_stage": lifecycle,
            "launch_date": pd.Series(launch_dates).dt.date.astype(str),
        }
    )


def generate_customers(rng: np.random.Generator, n_customers: int) -> pd.DataFrame:
    """Generate customers."""
    # Customer attributes drive pricing behavior later in the analytics modules and recommendation rules.
    segments = ["retail", "wholesale", "dealer", "ecommerce"]
    regions = ["Northeast", "South", "Midwest", "West"]
    channels = ["direct", "distributor", "marketplace"]
    tiers = ["A", "B", "C"]
    return pd.DataFrame(
        {
            "customer_id": [f"C{i+1:06d}" for i in range(n_customers)],
            "segment": rng.choice(segments, size=n_customers),
            "region": rng.choice(regions, size=n_customers),
            "channel": rng.choice(channels, size=n_customers),
            "price_tier": rng.choice(tiers, size=n_customers, p=[0.2, 0.5, 0.3]),
        }
    )


def generate_sales(rng: np.random.Generator, products: pd.DataFrame, customers: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Generate sales."""
    # Base SKU price and demand anchors are created once, then daily variation is applied around those anchors.
    dates = pd.date_range(start, end, freq="D")
    sku_to_price = {sku: float(rng.uniform(20, 600)) for sku in products["sku"]}
    sku_demand = {sku: int(rng.integers(5, 70)) for sku in products["sku"]}
    customer_tier = customers.set_index("customer_id")["price_tier"].to_dict()
    tier_discount = {"A": 0.12, "B": 0.07, "C": 0.03}
    rows = []
    order_counter = 1

    for d in dates:
        # Seasonality is injected at the day level so weekly rollups exhibit recurring demand patterns.
        season_mult = 1.0 + 0.15 * np.sin(2 * np.pi * (d.dayofyear / 365.25))
        n_lines = int(rng.integers(25, 60))
        skus = rng.choice(products["sku"], size=n_lines, replace=True)
        custs = rng.choice(customers["customer_id"], size=n_lines, replace=True)
        for line_id, (sku, customer_id) in enumerate(zip(skus, custs), start=1):
            list_price = max(0.01, sku_to_price[sku] * (1 + rng.normal(0, 0.01)))
            # Promotion and tier discounts are combined, then clipped to prevent unrealistic discounting.
            promo_flag = bool(rng.random() < 0.08)
            promo_id = f"PROMO{d.strftime('%Y%m')}" if promo_flag else ""
            promo_disc = rng.uniform(0.05, 0.18) if promo_flag else 0.0
            discount_pct = float(np.clip(tier_discount[customer_tier[customer_id]] + promo_disc + rng.normal(0, 0.01), 0.0, 0.35))
            transaction_price = round(max(0.01, list_price * (1 - discount_pct)), 2)
            # Poisson demand preserves integer unit behavior while allowing seasonality and SKU-level variation.
            units = int(max(0, rng.poisson(max(1, sku_demand[sku] * season_mult / 8))))
            cogs_unit = round(list_price * rng.uniform(0.45, 0.72), 2)
            rows.append(
                {
                    "order_id": f"O{order_counter:09d}",
                    "line_id": line_id,
                    "order_date": d.date().isoformat(),
                    "sku": sku,
                    "customer_id": customer_id,
                    "units": units,
                    "list_price": round(list_price, 2),
                    "transaction_price": transaction_price,
                    "discount_pct": round(discount_pct, 4),
                    "promo_flag": promo_flag,
                    "promo_id": promo_id,
                    "cogs_unit": cogs_unit,
                    "freight_unit": round(list_price * rng.uniform(0.01, 0.04), 2),
                    "payment_fees_unit": round(transaction_price * rng.uniform(0.01, 0.03), 2),
                    "returned_flag": bool(rng.random() < 0.015),
                }
            )
            order_counter += 1
    return pd.DataFrame(rows)


def generate_inventory(rng: np.random.Generator, sales: pd.DataFrame) -> pd.DataFrame:
    """Generate inventory."""
    sales = sales.copy()
    sales["order_date"] = pd.to_datetime(sales["order_date"])
    weekly = (
        sales.groupby([pd.Grouper(key="order_date", freq="W-MON"), "sku"], as_index=False)["units"]
        .sum()
        .rename(columns={"order_date": "snapshot_date", "units": "weekly_units"})
    )
    # Weekly sales are used as the anchor so inventory levels roughly scale with observed demand.
    return pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(weekly["snapshot_date"]).dt.date.astype(str),
            "sku": weekly["sku"],
            "on_hand_units": (weekly["weekly_units"] * rng.integers(8, 28, size=len(weekly)) + rng.integers(-20, 25, size=len(weekly))).clip(lower=0).astype(int),
            "on_order_units": (weekly["weekly_units"] * rng.integers(1, 8, size=len(weekly))).clip(lower=0).astype(int),
            "backorder_units": rng.integers(0, 10, size=len(weekly)),
            "unit_cost": np.round(rng.uniform(10, 350, size=len(weekly)), 2),
        }
    )


def main() -> None:
    """Run the module workflow from input preparation through output writing."""
    params = load_params()
    raw_dir = Path(params["paths"]["raw_generated"])
    raw_dir.mkdir(parents=True, exist_ok=True)
    # Fixed seed supports reproducibility for portfolio demos and validation checks.
    rng = np.random.default_rng(int(params.get("seed", 42)))
    step = StepLogger(total_steps=6, task_name="generate_erp_data")

    step.step("Loading configuration")
    n_skus = int(params["generation"]["n_skus"])
    n_customers = int(params["generation"]["n_customers"])
    start = params["date"]["start"]
    end = params["date"]["end"]

    step.step("Generating products")
    products = generate_products(rng, n_skus)
    log_info(f"products rows={len(products):,}")

    step.step("Generating customers")
    customers = generate_customers(rng, n_customers)
    log_info(f"customers rows={len(customers):,}")

    step.step("Generating sales_order_lines")
    sales = generate_sales(rng, products, customers, start, end)
    # Sanity checks catch invalid synthetic rows before downstream loads and dbt transformations.
    basic_sales_sanity(sales)
    log_info(f"sales_order_lines rows={len(sales):,}")

    step.step("Generating inventory_snapshots")
    inventory = generate_inventory(rng, sales)
    log_info(f"inventory_snapshots rows={len(inventory):,}")

    step.step("Writing CSV outputs")
    products.to_csv(raw_dir / "products.csv", index=False)
    customers.to_csv(raw_dir / "customers.csv", index=False)
    sales.to_csv(raw_dir / "sales_order_lines.csv", index=False)
    inventory.to_csv(raw_dir / "inventory_snapshots.csv", index=False)
    log_info(f"CSV outputs written to {raw_dir.resolve()}")


if __name__ == "__main__":
    main()
