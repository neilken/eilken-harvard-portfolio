-- Postgres initialization SQL for schemas, roles, and grants used by the local project environment.

DO $$
BEGIN
    -- pricing_app is the pipeline service user for loaders, dbt, and analysis table writes.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pricing_app') THEN
        CREATE ROLE pricing_app LOGIN PASSWORD 'pricing_app_pw';
    END IF;
    -- pricing_ro is the read-only user intended for BI imports.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pricing_ro') THEN
        CREATE ROLE pricing_ro LOGIN PASSWORD 'pricing_ro_pw';
    END IF;
END $$;

-- pricing_app needs create and temporary privileges because dbt materializations create and swap relations.
GRANT CONNECT, CREATE, TEMPORARY ON DATABASE pricing TO pricing_app;
GRANT CONNECT ON DATABASE pricing TO pricing_ro;

GRANT USAGE ON SCHEMA raw, staging, intermediate, marts, pbi, audit TO pricing_app;
-- pricing_ro only needs marts and pbi for Power BI imports.
GRANT USAGE ON SCHEMA marts, pbi TO pricing_ro;
GRANT CREATE ON SCHEMA raw, staging, intermediate, marts, pbi, audit TO pricing_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA raw TO pricing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA staging TO pricing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA intermediate TO pricing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA marts TO pricing_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA pbi TO pricing_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw TO pricing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA staging TO pricing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA intermediate TO pricing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA marts TO pricing_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA pbi TO pricing_app;

GRANT SELECT ON ALL TABLES IN SCHEMA pbi TO pricing_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO pricing_ro;

-- Default privileges keep future dbt and analysis tables available to the intended roles.
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pricing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pricing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA intermediate GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pricing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pricing_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA pbi GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pricing_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA pbi GRANT SELECT ON TABLES TO pricing_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO pricing_ro;
