-- Postgres initialization SQL for schemas, roles, and grants used by the local project environment.

-- Schema layout mirrors the warehouse flow from raw ingestion through dashboard-ready views.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS pbi;
-- audit is reserved for future validation logs and pipeline audit tables.
CREATE SCHEMA IF NOT EXISTS audit;
