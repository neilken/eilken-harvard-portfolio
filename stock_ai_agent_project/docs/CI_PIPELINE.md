# CI Pipeline Documentation

## Overview

The Unified CI Pipeline is a comprehensive continuous integration system that automatically builds, tests, and validates three main components of the Stock Busters application:

- **RAG (Retrieval-Augmented Generation)**: Handles document processing, embedding, and retrieval
- **Quantamental**: Provides quantitative analysis and stock prediction models
- **API-service**: FastAPI-based service that exposes endpoints for chatbot and stock details

The pipeline uses Docker containers for isolation, runs multiple test types (lint, unit, integration, system), generates code coverage reports, and combines them into a unified report.

**Continuous Deployment**: After the CI pipeline completes successfully on `main`, `develop`, or `Milestone5` branches, the CD (Continuous Deployment) pipeline automatically triggers to build Docker images, push them to GCP Artifact Registry, and deploy the application to Google Kubernetes Engine (GKE) using Pulumi. See the [CD Pipeline Documentation](CD_PIPELINE.md) for complete details.

![Successful Automated Unified CI run on push](Successful%20Automated%20Unified%20CI%20run%20on%20push.png)

*Example: Successful CI pipeline execution triggered by a push event*

## Table of Contents

1. [Pipeline Architecture](#pipeline-architecture)
2. [Workflow Triggers](#workflow-triggers)
3. [Jobs Overview](#jobs-overview)
4. [Component Details](#component-details)
5. [Test Types](#test-types)
6. [Coverage Reporting](#coverage-reporting)
7. [Optimization Features](#optimization-features)
8. [Docker Images](#docker-images)
9. [Troubleshooting](#troubleshooting)

---

## Pipeline Architecture

The CI pipeline consists of 4 main jobs that run in sequence:

```
detect-changes → build → tests → test-summary
```

### Job Flow

1. **detect-changes**: Analyzes which components have changed
2. **build**: Builds Docker images for changed components (parallel matrix)
3. **tests**: Runs tests for changed components (parallel matrix: component × test-type)
4. **test-summary**: Combines coverage reports and generates summary

---

## Workflow Triggers

The pipeline runs automatically on:

- **Push events** to `main`, `develop`, or `Milestone5` branches when files in:
  - `src/rag/**`
  - `src/quantamental/**`
  - `src/api-service/**`
  - `.github/workflows/ci.yml`
  are modified

- **Pull request events** targeting `main`, `develop`, or `Milestone5` branches with the same path filters

- **Manual dispatch** via GitHub Actions UI (`workflow_dispatch`)

### Concurrency

The pipeline uses concurrency groups to prevent multiple runs for the same branch:
- Only one workflow run per branch at a time
- New runs cancel in-progress runs for the same branch

### Continuous Deployment Trigger

**Important**: Upon successful completion of the CI pipeline on `main`, `develop`, or `Milestone5` branches, the CD (Continuous Deployment) pipeline automatically triggers. The CD pipeline:

1. Builds Docker images for all components
2. Pushes images to GCP Artifact Registry
3. Deploys the application to Google Kubernetes Engine (GKE) using Pulumi
4. Verifies deployment health and pod readiness

This ensures that only code that passes all tests and coverage requirements is automatically deployed to production.

📖 **For detailed CD pipeline documentation, see**: [CD Pipeline Documentation](CD_PIPELINE.md)

---

## Jobs Overview

### 1. detect-changes Job

**Purpose**: Identifies which components have changed to optimize build and test execution.

**How it works**:
- Uses `dorny/paths-filter@v2` action to detect file changes
- Checks paths: `src/rag/**`, `src/quantamental/**`, `src/api-service/**`
- Outputs boolean flags: `rag`, `quantamental`, `api-service`

**Outputs**:
- `rag`: `"true"` if RAG files changed
- `quantamental`: `"true"` if Quantamental files changed
- `api-service`: `"true"` if API-service files changed

**Optimization**: Subsequent jobs skip unchanged components, saving ~50% execution time when only one component changes.

---

### 2. build Job

**Purpose**: Builds Docker images for each component that changed.

**Strategy**: Matrix strategy with 3 components (rag, quantamental, api-service)

**Steps**:
1. **Check if component changed**: Skips build if component didn't change (unless manual dispatch)
2. **Checkout code**: Retrieves repository code
3. **Set up Docker Buildx**: Configures Docker for multi-platform builds
4. **Set up QEMU**: Enables cross-platform builds if needed
5. **Prepare secrets**: Creates dummy service account JSON if not present (for CI)
6. **Build and push Docker image**: 
   - Builds image using component-specific Dockerfile
   - Tags with: `ghcr.io/<repo>/<image-name>:<commit-sha>`
   - Pushes to GitHub Container Registry (GHCR)
   - Uses GitHub Actions cache for faster builds

**Docker Images**:
- `rag-service`: Built from `./src/rag/Dockerfile`
- `quantamental-service`: Built from `src/quantamental/Dockerfile`
- `api-service`: Built from `src/api-service/Dockerfile`

**Caching**: Each component has its own cache scope to prevent conflicts.

**Outputs**:
- `image-tag`: Full image tag for pulling
- `image-digest`: Image digest for verification

---

### 3. tests Job

**Purpose**: Runs linting, unit tests, integration tests, and system tests for each component.

**Strategy**: Matrix strategy with:
- **Components**: rag, quantamental, api-service
- **Test types**: lint-unit, integration, system

**Total matrix combinations**: 9 (3 components × 3 test types)

**Conditional Execution**:
- Skips if component didn't change (unless manual dispatch)
- System tests only run on `main`, `develop`, `Milestone5` branches (or manual dispatch)

#### Test Types

##### lint-unit

**Purpose**: Validates code quality and runs unit tests with coverage.

**Steps**:
1. Creates coverage directory
2. **Linting**:
   - **RAG**: `black --check` and `flake8` on `rag.py`
   - **Quantamental/API-service**: `black --check` and `flake8` on entire codebase
3. **Unit tests with coverage**:
   - **RAG**: `pytest tests/unit/ --cov=rag --cov-branch --cov-report=xml --cov-report=html -m unit`
   - **Quantamental**: `pytest tests/ --cov=. --cov-branch --cov-report=xml --cov-report=html -m unit`
   - **API-service**: `pytest tests/ --cov=api --cov-branch --cov-report=xml --cov-report=html -m unit`
4. **Verification**: Validates coverage XML file was generated and is well-formed

**Coverage Output**:
- XML: `src/<component>/coverage/coverage.xml`
- HTML: `src/<component>/coverage/htmlcov/`

**Special handling for API-service**:
- Overrides Docker entrypoint to prevent server from starting
- Runs as root user to avoid permission issues with mounted volumes
- Uses `python -m pytest` instead of direct `pytest` command

##### integration

**Purpose**: Tests component interactions and integration with external services.

**Steps**:
1. Runs integration tests using Docker container
2. Tests marked with `@pytest.mark.integration`
3. No coverage collection (unit tests handle coverage)

**Special handling for API-service**:
- Overrides Docker entrypoint to prevent server from starting
- Runs as root user

##### system

**Purpose**: End-to-end tests that require running services.

**Steps**:
1. **Start service**:
   - **RAG**: Starts server on ports 9000 (API) and 8000 (ChromaDB)
   - **API-service**: Starts Uvicorn server on port 9000
   - **Quantamental**: No server required
2. **Wait for service**: Polls health endpoint until ready (max 10 attempts, 2s intervals)
3. **Run system tests**: Executes tests marked with `@pytest.mark.system`
4. **Cleanup**: Stops and removes server container

**Special handling for API-service**:
- Starts server in detached container with custom entrypoint
- Runs tests in separate container with network access

**Environment Variables**:
- `CHROMADB_HOST`, `CHROMADB_PORT`: ChromaDB connection
- `VECTOR_COLLECTION`: Vector collection name
- `EMBEDDING_MODEL`: Embedding model identifier
- `FMP_API_KEY`, `WANDB_API_KEY`: API keys (from secrets)
- `GCS_BUCKET_NAME`: Google Cloud Storage bucket (from secrets)

---

### 4. test-summary Job

**Purpose**: Combines coverage reports, calculates combined metrics, and generates a summary.

**Dependencies**: `needs: [tests]`

**Steps**:

#### Step 1: Combine Coverage Reports

**Purpose**: Merges individual component coverage reports into a unified report.

**Process**:
1. Checks for coverage files: `src/rag/coverage/coverage.xml`, `src/quantamental/coverage/coverage.xml`, `src/api-service/coverage/coverage.xml`
2. **If multiple components**: Uses Python script to combine:
   - Sums `lines-covered` and `lines-valid` from all components
   - Sums `branches-covered` and `branches-valid` from all components
   - Calculates combined rates: `line_rate = total_lines_covered / total_lines_valid`
   - Preserves package-level data with component prefixes (`rag/`, `quantamental/`, `api-service/`)
3. **If single component**: Copies coverage file directly
4. **Verification**: Validates unified XML is well-formed and non-empty
5. **HTML Reports**: Copies HTML coverage to `coverage/htmlcov/` (or component-specific subdirectories)

**Output**: `coverage/coverage.xml` (unified report)

#### Step 2: Extract Coverage from Files

**Purpose**: Extracts coverage percentages for individual components and combined total.

**Process**:
1. Tries to read from individual component coverage files first
2. Falls back to unified `coverage/coverage.xml` if individual files not found
3. Extracts:
   - Line coverage percentage
   - Branch coverage percentage
   - Lines covered/valid counts
   - Branches covered/valid counts

**Outputs**:
- `rag_coverage`, `rag_branch`
- `quant_coverage`, `quant_branch`
- `api_coverage`, `api_branch`

#### Step 3: Calculate Combined Coverage

**Purpose**: Calculates combined coverage from individual component metrics.

**Process**:
1. Reads `lines-covered` and `lines-valid` from each component's coverage file
2. Sums totals: `TOTAL_LINES_COV = RAG_LINES_COV + QUANT_LINES_COV + API_LINES_COV`
3. Calculates percentage: `COMBINED_COV = (TOTAL_LINES_COV / TOTAL_LINES_TOT) × 100`
4. Falls back to unified `coverage/coverage.xml` if individual files unavailable

**Outputs**:
- `unified_coverage`: Combined coverage percentage (e.g., "62%")
- `unified_coverage_pct`: Combined coverage as float (e.g., "62.35")

**Note**: Combined coverage is a **weighted average** based on total lines, not a simple average of percentages.

#### Step 4: Check Combined Coverage Threshold

**Purpose**: Validates that combined coverage meets the 50% threshold.

**Process**:
- Compares `unified_coverage_pct` against 50.0%
- Fails workflow if below threshold
- Uses `awk` for reliable floating-point comparison

#### Step 5: Commit Unified Coverage Report

**Purpose**: Commits the unified coverage report to the repository.

**Process**:
1. Configures git user
2. Pulls latest changes with rebase (handles concurrent commits)
3. Stages `coverage/coverage.xml` and `coverage/htmlcov/`
4. Commits with message: "Update unified coverage report [skip ci]"
5. Pushes to the same branch

**Triggers**: Runs on `push` and `pull_request` events

**Skip CI**: Uses `[skip ci]` in commit message to prevent infinite loops

#### Step 6: Print Summary

**Purpose**: Generates a markdown summary displayed in GitHub Actions.

**Summary includes**:
- **Combined Coverage Report**:
  - Combined coverage percentage with threshold status (✅ or ❌)
- **Component Breakdown**:
  - 🔍 RAG Component: Coverage %, Branch Coverage %
  - 📊 Quantamental Component: Coverage %, Branch Coverage %
  - 🚀 API-service Component: Coverage %, Branch Coverage %
- **Test Status**: Overall test result (🎉 All tests passed! or ⚠️ Some tests failed)
- **Coverage Reports**: Links to unified XML and HTML reports

**Example Summary Format**:
```
📊 Unified CI Pipeline Results

📈 Combined Coverage Report

Combined Coverage: 70% ✅ (meets 50% threshold)

Component Breakdown

🔍 RAG Component
Coverage: 73%
Branch Coverage: 67%

📊 Quantamental Component
Coverage: 62%
Branch Coverage: 46%

🚀 API-service Component
Coverage: 78%
Branch Coverage: 67%

Test Status

🎉 All tests passed!

📁 Coverage Reports

Unified coverage report available at: coverage/coverage.xml
HTML reports available in: coverage/htmlcov/ (or component-specific subdirectories)
```

![Unified CI Test Summary](Unified%20CI%20Test%20Summary.png)

*Example: CI pipeline test summary showing combined coverage (70%) and individual component breakdown*

---

## Component Details

### RAG Component

**Location**: `src/rag/`

**Docker Image**: `rag-service`

**Python Version**: 3.12

**Test Structure**:
- `tests/unit/`: Unit tests
- `tests/integration/`: Integration tests
- `tests/system/`: System tests

**Coverage Source**: `--cov=rag` (covers `rag.py` module)

**Special Features**:
- Uses ChromaDB for vector storage
- Requires GCS bucket for document storage
- Server runs on ports 9000 (API) and 8000 (ChromaDB)

### Quantamental Component

**Location**: `src/quantamental/`

**Docker Image**: `quantamental-service`

**Python Version**: 3.11

**Test Structure**:
- `tests/`: All tests (unit, integration, system use same directory with markers)

**Coverage Source**: `--cov=.` (covers entire codebase)

**Special Features**:
- Uses FMP API for financial data
- Uses Weights & Biases (W&B) for experiment tracking
- No server required (library component)

### API-service Component

**Location**: `src/api-service/`

**Docker Image**: `api-service`

**Python Version**: 3.12

**Test Structure**:
- `tests/`: All tests (unit, integration, system use same directory with markers)

**Coverage Source**: `--cov=api` (covers `api/` directory)

**Special Features**:
- FastAPI-based REST API
- Uses LangChain/LangGraph for chatbot
- Requires GCS for data storage
- Server runs on port 9000
- **Entrypoint override**: Tests override Docker entrypoint to prevent automatic server startup

---

## Test Types

### Unit Tests

**Purpose**: Test individual functions and classes in isolation.

**Marker**: `@pytest.mark.unit`

**Coverage**: Collected during unit tests only.

**Execution**: Fast, runs in seconds.

**Isolation**: Uses mocks for external dependencies (GCS, APIs, LLMs).

### Integration Tests

**Purpose**: Test component interactions and integration with external services.

**Marker**: `@pytest.mark.integration`

**Coverage**: Not collected (unit tests handle coverage).

**Execution**: Moderate speed, may involve network calls to mocked services.

**Isolation**: May use test databases or mock services.

### System Tests

**Purpose**: End-to-end tests that require running services.

**Marker**: `@pytest.mark.system`

**Coverage**: Not collected.

**Execution**: Slower, requires service startup and teardown.

**Branch Restriction**: Only runs on `main`, `develop`, `Milestone5` branches (or manual dispatch).

**Isolation**: Uses real service instances in Docker containers.

---

## Coverage Reporting

### Coverage Calculation

**Combined Coverage Formula**:
```
Combined Coverage = (Total Lines Covered / Total Lines Valid) × 100
```

Where:
- `Total Lines Covered = RAG_lines_covered + QUANT_lines_covered + API_lines_covered`
- `Total Lines Valid = RAG_lines_valid + QUANT_lines_valid + API_lines_valid`

**Important**: This is a **weighted average** based on actual line counts, not a simple average of percentages. A component with more lines has more influence on the combined percentage.

### Coverage Threshold

**Requirement**: Combined coverage must be ≥ 50%

**Enforcement**: Pipeline fails if threshold not met.

**Current Performance**: 70% combined coverage (exceeds threshold by 20 percentage points)

**Individual Components**: No individual thresholds (only combined threshold).

### Coverage Reports

**Unified Coverage Reports** (root level):
- **Location**: `coverage/`
- **XML Report**: `coverage/coverage.xml` (Cobertura format, combines all components)
- **HTML Reports**: `coverage/htmlcov/` (browseable HTML, combines all components)

**Component-Specific Reports**:
- **RAG**:
  - XML: `src/rag/coverage/coverage.xml`
  - HTML: `src/rag/coverage/htmlcov/`
- **Quantamental**:
  - XML: `src/quantamental/coverage/coverage.xml`
  - HTML: `src/quantamental/coverage/htmlcov/`
- **API-service**:
  - XML: `src/api-service/coverage/coverage.xml`
  - HTML: `src/api-service/coverage/htmlcov/`

**Note**: The unified coverage report in `coverage/` is automatically committed to the repository after each CI run. Component-specific reports are generated during test execution but may not be committed (only the unified report is committed).

**Branch Coverage**: Collected and reported alongside line coverage.

### Coverage Metrics

**Line Coverage**: Percentage of executable lines covered by tests.

**Branch Coverage**: Percentage of code branches (if/else, loops) covered by tests.

**Package-Level Data**: Preserved in unified report with component prefixes.

---

## Optimization Features

### 1. Path-Based Conditional Execution

**Benefit**: Skips unchanged components, saving ~50% execution time.

**Implementation**:
- `detect-changes` job identifies changed components
- `build` and `tests` jobs skip unchanged components
- Manual dispatch always runs all components

### 2. Matrix Strategy

**Benefit**: Parallel execution of multiple test types and components.

**Implementation**:
- Build job: 3 parallel builds (one per component)
- Tests job: Up to 9 parallel test runs (3 components × 3 test types)

### 3. Docker Image Caching

**Benefit**: Faster builds by reusing cached layers.

**Implementation**:
- Uses GitHub Actions cache (`type=gha`)
- Component-specific cache scopes prevent conflicts
- Cache mode: `max` (preserves all layers)

### 4. System Test Branch Restriction

**Benefit**: Faster CI on feature branches (skips slow system tests).

**Implementation**:
- System tests only run on `main`, `develop`, `Milestone5`
- Feature branches skip system tests automatically

### 5. Fail-Fast Strategy

**Benefit**: Quick feedback on failures.

**Implementation**:
- `fail-fast: false` in matrix (all jobs run even if one fails)
- `--maxfail=1` or `--maxfail=2` in pytest (stops after first/second failure)
- `-x` flag in pytest (exit on first failure)

---

## Docker Images

### Image Naming

**Format**: `ghcr.io/<repository>/<image-name>:<commit-sha>`

The repository name is automatically lowercased from `${{ github.repository }}`.

**Examples**:
- `ghcr.io/<owner>/<repo>/rag-service:<commit-sha>`
- `ghcr.io/<owner>/<repo>/quantamental-service:<commit-sha>`
- `ghcr.io/<owner>/<repo>/api-service:<commit-sha>`

Where `<owner>/<repo>` is your GitHub repository (e.g., `username/csci115-ai-agent`).

### Image Tags

**Primary Tag**: Commit SHA (`${{ github.sha }}`)

**Registry**: GitHub Container Registry (GHCR)

### Image Pulling

Tests pull images by commit SHA:
```bash
docker pull ghcr.io/<owner>/<repo>/<image-name>:<commit-sha>
```

For example:
```bash
docker pull ghcr.io/<owner>/<repo>/rag-service:abc123def456
docker pull ghcr.io/<owner>/<repo>/quantamental-service:abc123def456
docker pull ghcr.io/<owner>/<repo>/api-service:abc123def456
```

### Image Caching

- Build cache: GitHub Actions cache (component-scoped)
- Pull cache: Docker layer caching
- Cache keys: Component name + commit SHA

---

## Troubleshooting

### Coverage Not Showing

**Symptom**: Component shows "N/A" in summary.

**Possible Causes**:
1. Component didn't change (skipped)
2. Coverage file not generated
3. Coverage file not found at expected path

**Solution**:
- Check if component changed in `detect-changes` job
- Verify coverage file exists: `src/<component>/coverage/coverage.xml`
- Check test job logs for coverage generation errors

### Tests Hanging

**Symptom**: Test job runs indefinitely.

**Possible Causes**:
1. Server not starting (system tests)
2. Network timeout
3. Missing environment variables

**Solution**:
- Check system test logs for server startup
- Verify health endpoint is accessible
- Check environment variables in test job

### Permission Denied Errors

**Symptom**: `Permission denied` when writing coverage files.

**Possible Causes**:
1. Docker container user lacks write permissions
2. Mounted volume permissions

**Solution**:
- API-service tests run as `root` user
- Verify volume mount paths are correct

### Combined Coverage Calculation

**Symptom**: Combined coverage seems incorrect.

**Clarification**: Combined coverage is a **weighted average**, not a simple average.

**Example**:
- RAG: 73% (1000 lines) → 730 lines covered
- Quantamental: 62% (2000 lines) → 1240 lines covered
- API-service: 78% (500 lines) → 390 lines covered
- **Combined**: (730 + 1240 + 390) / (1000 + 2000 + 500) = 2360 / 3500 = **67.4%**

Not: (73 + 62 + 78) / 3 = **71%** (simple average - incorrect method)

**Current Actual Values**:
- Combined Coverage: **70%** ✅
- RAG: 73% coverage, 67% branch coverage
- Quantamental: 62% coverage, 46% branch coverage
- API-service: 78% coverage, 67% branch coverage

### Coverage Report Not Committed

**Symptom**: `coverage/coverage.xml` not in repository.

**Possible Causes**:
1. Git push failed (remote changes)
2. Permission issues
3. `.gitignore` blocking coverage files

**Solution**:
- Check `.gitignore` for coverage exclusions
- Verify git permissions in workflow
- Check commit step logs for errors

---

## Best Practices

### Adding New Components

1. Add component to `detect-changes` filters
2. Add component to `build` matrix
3. Add component to `tests` matrix
4. Update coverage combination script
5. Update summary display

### Writing Tests

1. Use appropriate markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.system`
2. Mock external dependencies in unit tests
3. Use fixtures for common setup
4. Keep tests fast and isolated

### Coverage Goals

1. Aim for ≥ 50% combined coverage (enforced)
2. Focus on critical paths
3. Balance unit vs integration tests
4. Review coverage reports regularly

---

## Summary

The Unified CI Pipeline provides:

 **Automated testing** for 3 components  
 **Code quality checks** (linting)  
 **Coverage reporting** with unified metrics  
 **Optimized execution** (skips unchanged components)  
 **Parallel execution** (matrix strategy)  
 **Docker-based isolation**  
 **GitHub Actions integration**  

The pipeline ensures code quality, test coverage, and deployment readiness for all components of the Stock Busters application.

