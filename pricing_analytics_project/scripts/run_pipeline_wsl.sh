#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_DIR}/.venv-wsl"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

step() {
  local current="$1"
  local total="$2"
  local message="$3"
  log "[${current}/${total}] ${message}"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "Missing required command: $1"
    exit 1
  }
}

wait_for_postgres() {
  local tries=30
  local i
  for ((i=1; i<=tries; i++)); do
    if docker exec pricing_postgres pg_isready -U postgres -d pricing >/dev/null 2>&1; then
      log "Postgres is ready"
      return 0
    fi
    sleep 2
  done
  log "Postgres readiness check timed out"
  return 1
}

main() {
  step 1 11 "Checking required commands"
  require_cmd python3
  require_cmd docker

  step 2 11 "Preparing WSL virtual environment"
  if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
  fi
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  python -m pip install -q -r "${PROJECT_DIR}/requirements.txt"

  step 3 11 "Starting Postgres with Docker Compose"
  cd "${PROJECT_DIR}"
  docker compose -f docker/docker-compose.yml up -d

  step 4 11 "Waiting for Postgres readiness"
  wait_for_postgres

  step 5 11 "Generating synthetic ERP and competitor data"
  python -m src.ingest.generate_erp_data
  python -m src.ingest.competitor_simulator

  step 6 11 "Loading raw tables into Postgres"
  python -m src.load.load_raw_to_postgres
  python -m src.load.load_competitor_to_postgres

  step 7 11 "Clearing dbt artifacts"
  rm -rf dbt/target dbt/logs

  step 8 11 "Running analysis modules"
  python -m src.analysis.price_realization
  python -m src.analysis.promo_effectiveness
  python -m src.analysis.elasticity_model
  python -m src.analysis.forecasting
  python -m src.analysis.inventory_pricing_engine
  python -m src.analysis.scenario_simulator
  python -m src.analysis.advanced_pricing_metrics
  python -m src.analysis.generate_memo_figures
  python -m src.analysis.generate_memo_summary
  python -m src.analysis.generate_powerbi_mock_dashboards

  step 9 11 "Running dbt models"
  dbt run --project-dir dbt --profiles-dir dbt --threads 1

  step 10 11 "Running dbt tests"
  dbt test --project-dir dbt --profiles-dir dbt --threads 1

  step 11 11 "Pipeline complete"
  log "Outputs written to data/exports_for_pbi, data/exports_for_memo, and Postgres marts schema"
}

main "$@"
