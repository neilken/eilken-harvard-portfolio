PYTHON ?= python

.PHONY: setup db-up db-down generate-data load-raw load-competitor dbt-deps dbt-run dbt-test analysis export all

setup:
	$(PYTHON) -m pip install -r requirements.txt

db-up:
	docker compose -f docker/docker-compose.yml up -d

db-down:
	docker compose -f docker/docker-compose.yml down

generate-data:
	$(PYTHON) -m src.ingest.generate_erp_data
	$(PYTHON) -m src.ingest.competitor_simulator

load-raw:
	$(PYTHON) -m src.load.load_raw_to_postgres

load-competitor:
	$(PYTHON) -m src.load.load_competitor_to_postgres

dbt-deps:
	$(PYTHON) -m dbt.cli.main deps --project-dir dbt --profiles-dir dbt

dbt-run:
	$(PYTHON) -m dbt.cli.main run --project-dir dbt --profiles-dir dbt

dbt-test:
	$(PYTHON) -m dbt.cli.main test --project-dir dbt --profiles-dir dbt

analysis:
	$(PYTHON) -m src.analysis.price_realization
	$(PYTHON) -m src.analysis.promo_effectiveness
	$(PYTHON) -m src.analysis.elasticity_model
	$(PYTHON) -m src.analysis.forecasting
	$(PYTHON) -m src.analysis.inventory_pricing_engine
	$(PYTHON) -m src.analysis.scenario_simulator

export:
	@echo "Exports are produced by analysis scripts"

all: generate-data load-raw load-competitor dbt-run dbt-test analysis export
