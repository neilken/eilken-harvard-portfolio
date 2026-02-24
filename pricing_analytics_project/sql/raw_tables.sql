-- Raw schema DDL. Defines source tables loaded from generated ERP and competitor CSV files.

-- Product master data used for category, family, and lifecycle enrichment in pricing models.
CREATE TABLE IF NOT EXISTS raw.products (
    sku TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    product_family TEXT NOT NULL,
    brand TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL,
    launch_date DATE
);

-- Customer master data used for segment, region, channel, and price-tier analysis.
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id TEXT PRIMARY KEY,
    segment TEXT NOT NULL,
    region TEXT NOT NULL,
    channel TEXT NOT NULL,
    price_tier TEXT NOT NULL
);

-- Transaction-level sales lines are the main pricing fact source for dbt and Python analysis modules.
-- Composite primary key preserves order line uniqueness required by downstream tests.
CREATE TABLE IF NOT EXISTS raw.sales_order_lines (
    order_id TEXT NOT NULL,
    line_id INTEGER NOT NULL,
    order_date DATE NOT NULL,
    sku TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    units INTEGER NOT NULL,
    list_price NUMERIC(12,2) NOT NULL,
    transaction_price NUMERIC(12,2) NOT NULL,
    discount_pct NUMERIC(8,4),
    promo_flag BOOLEAN,
    promo_id TEXT,
    cogs_unit NUMERIC(12,2),
    freight_unit NUMERIC(12,2),
    payment_fees_unit NUMERIC(12,2),
    returned_flag BOOLEAN,
    PRIMARY KEY (order_id, line_id)
);

-- Inventory snapshots are loaded at snapshot_date x sku grain and later normalized to weekly grain in dbt.
CREATE TABLE IF NOT EXISTS raw.inventory_snapshots (
    snapshot_date DATE NOT NULL,
    sku TEXT NOT NULL,
    on_hand_units INTEGER,
    on_order_units INTEGER,
    backorder_units INTEGER,
    unit_cost NUMERIC(12,2),
    PRIMARY KEY (snapshot_date, sku)
);

-- Competitor snapshots retain captured_at plus normalized snapshot_date for daily and weekly rollups.
-- Primary key enforces one normalized record per snapshot_date x competitor x sku after simulator aggregation.
CREATE TABLE IF NOT EXISTS raw.competitor_snapshots (
    captured_at TIMESTAMP NOT NULL,
    snapshot_date DATE NOT NULL,
    competitor_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    competitor_price NUMERIC(12,2) NOT NULL,
    competitor_shipping NUMERIC(12,2),
    in_stock BOOLEAN,
    promo_flag BOOLEAN,
    url TEXT,
    match_score NUMERIC(4,2),
    PRIMARY KEY (snapshot_date, competitor_id, sku)
);
