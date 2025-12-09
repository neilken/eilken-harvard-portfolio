# Continuous Integration Pipeline

## Overview

The RAG component is part of a unified CI/CD pipeline built on GitHub Actions that automatically builds, tests, and validates code changes for RAG, Quantamental, and API-service components. The pipeline ensures code quality, maintains test coverage standards, and provides fast feedback on pull requests and commits.

**Pipeline Location**: `.github/workflows/ci.yml` (unified pipeline for all components)

![Successful Automated Unified CI run on push](../../../docs/Successful%20Automated%20Unified%20CI%20run%20on%20push.png)

*Complete unified CI pipeline run showing all jobs passing*

![Unified CI Test Summary](../../../docs/Unified%20CI%20Test%20Summary.png)

*Unified CI test summary showing combined coverage and individual component breakdown*

## Pipeline Architecture

The unified CI pipeline uses a **matrix strategy** to efficiently test multiple components and test types in parallel. For the RAG component, the pipeline consists of:

```
┌─────────────────┐
│ Detect Changes  │ (Job 1: Determines which components changed)
└────────┬────────┘
         │
         ├───► Build RAG Image (Job 2: Matrix build for changed components)
         │
         └───► RAG Tests (Job 3: Matrix strategy with 3 test types)
               ├───► Lint & Unit Tests (runs in parallel)
               ├───► Integration Tests (runs in parallel)
               └───► System Tests (runs in parallel, conditional)
                     │
                     └───► Test Summary (Job 4: Aggregates results & commits coverage)
```

### Key Design Principles

1. **Unified Pipeline**: Single workflow handles RAG, Quantamental, and API-service components
2. **Conditional Execution**: Only runs tests for components that have changed (saves ~50% time when only one component changes)
3. **Matrix Strategy**: Runs lint-unit, integration, and system tests in parallel for each component
4. **Docker-Based**: All tests run inside Docker containers for consistency
5. **Fast Feedback**: Fails fast with `--maxfail` flags to surface issues quickly
6. **Coverage Tracking**: Enforces minimum 50% code coverage requirement
7. **Unified Coverage**: Combines coverage from all components into a single report

## When the Pipeline Runs

The unified pipeline automatically triggers on:

- **Push events**: When code is pushed to `main`, `develop`, or `Milestone4` branches
- **Pull requests**: When PRs target `main`, `develop`, or `Milestone4` branches
- **Path filtering**: Only runs when files in `src/rag/**`, `src/quantamental/**`, or `src/api-service/**` are modified
- **Manual trigger**: Can be manually triggered via `workflow_dispatch`

**Conditional Execution for RAG**: The RAG component tests only run if:
- Files in `src/rag/**` have been modified, OR
- The workflow is manually triggered (`workflow_dispatch`)

**Concurrency Control**: Only one pipeline runs per branch at a time. New commits cancel in-progress runs.

## Pipeline Jobs

### Job 1: Detect Changed Components

**Purpose**: Determine which components (RAG, Quantamental, API-service) have changed to optimize pipeline execution.

**Steps**:
1. Checkout repository code with full history
2. Use `dorny/paths-filter` action to detect changes in:
   - `src/rag/**` → RAG component
   - `src/quantamental/**` → Quantamental component
   - `src/api-service/**` → API-service component
3. Output boolean flags for each component

**Output**: 
- `rag`: `true` if RAG files changed, `false` otherwise
- `quantamental`: `true` if Quantamental files changed, `false` otherwise
- `api-service`: `true` if API-service files changed, `false` otherwise

**Why This Matters**: Allows the pipeline to skip unchanged components, saving ~50% execution time when only one component changes.

---

### Job 2: Build Docker Images (Matrix Strategy)

**Purpose**: Build Docker images for all changed components in parallel using a matrix strategy.

**RAG-Specific Configuration**:
- **Component**: `rag`
- **Dockerfile**: `./src/rag/Dockerfile`
- **Build Context**: Project root (`.`)
- **Image Name**: `rag-service`
- **Test Path**: `src/rag`

**Steps**:
1. Check if RAG component changed (skip if unchanged and not manual trigger)
2. Checkout repository code
3. Set up Docker Buildx for advanced build features
4. Create dummy GCS key file (if missing) for build context
5. Log in to GitHub Container Registry (GHCR)
6. Build and push Docker image:
   - **Tag**: `ghcr.io/<owner>/<repo>/rag-service:${{ github.sha }}`
   - **Format**: Repository name is automatically lowercased (e.g., `username/csci115-ai-agent`)
   - **Cache**: Uses GitHub Actions cache (`type=gha`) for faster builds
   - **Context**: Project root (`.`)
   - **Dockerfile**: `./src/rag/Dockerfile`
7. Verify image exists and is inspectable

**Timeout**: 10 minutes  
**Conditional**: Only runs if RAG component changed or workflow is manually triggered

**Why This Matters**: Images are pushed to GHCR and pulled by test jobs, enabling better caching and parallel execution.

---

### Job 3: RAG Tests (Matrix Strategy)

**Purpose**: Run all RAG tests (lint, unit, integration, system) in parallel using a matrix strategy.

**Matrix Configuration for RAG**:
- **Component**: `rag`
- **Test Types**: `lint-unit`, `integration`, `system`
- **Image Name**: `rag-service`
- **Test Paths**: 
  - `lint-unit`: `tests/unit/`
  - `integration`: `tests/integration/`
  - `system`: `tests/system/`
- **Coverage Path**: `src/rag/coverage` (for lint-unit only)
- **Python Version**: 3.12
- **Venv Path**: `/.venv/lib/python3.12/site-packages`

**Dependencies**: Requires `build` job to complete

**Conditional Execution**: 
- Only runs if RAG component changed or workflow is manually triggered
- System tests additionally only run on `main`, `develop`, `Milestone4` branches

**Timeout**: 10 minutes per test type

#### Test Type: Lint & Unit Tests

**Purpose**: Ensure code quality and run unit tests with coverage measurement.

**Steps**:
1. Checkout code (for coverage report paths)
2. Log in to GitHub Container Registry
3. Pull RAG Docker image from GHCR
4. Run linting checks:
   - **Black**: Formatting check (`--check` mode, line length 120)
   - **Flake8**: Linting check (max line length 120, ignores specific warnings)
5. Run unit tests with coverage:
   - **Test marker**: `-m unit` (only unit tests)
   - **Coverage tool**: `pytest-cov`
   - **Coverage target**: `--cov=rag`
   - **Coverage reports**: 
     - Terminal output
     - XML: `src/rag/coverage/coverage.xml` (for CI integration)
     - HTML: `src/rag/coverage/htmlcov/` (for detailed browsing)
   - **Fast failure**: `--maxfail=2 -x` (stops after 2 failures)
   - **Quiet mode**: `-q` (minimal output)
6. Verify coverage files were generated and are valid

**Environment Variables**:
```bash
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
VECTOR_COLLECTION=test_collection
GCS_BUCKET_NAME=""
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENABLE_CACHE=0
AUTO_START_CHROMADB=0
GOOGLE_APPLICATION_CREDENTIALS=""
```

**Coverage Requirements**:
- **Minimum**: 50% (enforced by `--cov-fail-under=50`)
- **Current**: ~73% (exceeds requirement)
- **Reports**: Stored in `src/rag/coverage/` and later combined into unified report

**Tools Used**:
- `black --check --line-length 120 rag.py`
- `flake8 --max-line-length=120 --extend-ignore=E203,W503,E501,E722,W504,E402,F401,F841,F811,F821 rag.py`
- `pytest tests/unit/ --cov=rag --cov-branch --cov-report=term --cov-report=xml --cov-report=html -m unit`

#### Test Type: Integration Tests

**Purpose**: Test component interactions with mocked external services.

**Steps**:
1. Pull RAG Docker image from GHCR
2. Run integration tests:
   - **Test marker**: `-m integration` (only integration tests)
   - **Test path**: `tests/integration/`
   - **Fast failure**: `--maxfail=1 -x` (stops after 1 failure)
   - **Quiet mode**: `-q` (minimal output)

**Environment Variables**: Same as unit tests

**What Integration Tests Cover**:
- FastAPI endpoint interactions
- ChromaDB client operations (mocked)
- GCS operations (mocked)
- API request/response handling

#### Test Type: System Tests

**Purpose**: Test the complete system with a running server instance.

**Conditional Execution**: Only runs on:
- `main` branch
- `develop` branch
- `Milestone4` branch
- Manual workflow dispatch

**Steps**:
1. Pull RAG Docker image from GHCR
2. Start RAG server container:
   - **Ports**: 9000 (API), 8000 (ChromaDB)
   - **Environment**: Development mode (`DEV=1`)
   - **Detached mode**: Runs in background
   - **Container name**: `rag-server`
3. Wait for server readiness:
   - Polls `http://localhost:9000/health` endpoint
   - Maximum 10 attempts (20 seconds total)
   - Fails if server doesn't become ready
4. Run system tests:
   - **Test marker**: `-m system` (only system tests)
   - **Test path**: `tests/system/`
   - **Network**: Uses `--network host` to access running server
   - **Fast failure**: `--maxfail=1 -x`
   - **Quiet mode**: `-q` (minimal output)
5. Cleanup: Stop and remove server container (always, even on failure)

**What System Tests Cover**:
- Full API endpoint functionality
- Server startup and health checks
- End-to-end query processing
- Real HTTP requests/responses

**Why Conditional**: System tests are slower and require a running server. Skipping on feature branches speeds up development feedback.

---

### Job 4: Test Summary & Coverage Aggregation

**Purpose**: Aggregate test results, combine coverage reports from all components, and commit unified coverage to repository.

**Dependencies**: Requires all test jobs to complete

**Execution**: Always runs (`if: always()`) to provide summary even if tests fail

**Steps**:
1. Checkout code with write permissions
2. Download coverage XML files from all components:
   - `src/rag/coverage/coverage.xml`
   - `src/quantamental/coverage/coverage.xml` (if exists)
   - `src/api-service/coverage/coverage.xml` (if exists)
3. Combine coverage XML files into unified report:
   - **Output**: `coverage/coverage.xml` (root-level unified report)
   - Uses Python script to merge Cobertura XML format
4. Copy component-specific HTML reports:
   - `coverage/htmlcov_rag/` (from `src/rag/coverage/htmlcov/`)
   - `coverage/htmlcov_quantamental/` (if exists)
   - `coverage/htmlcov_api/` (if exists)
5. Extract coverage metrics from unified XML
6. Generate GitHub Actions summary:
   - Test status table (✅ Passed / ❌ Failed) for all components
   - Coverage percentage (unified and per-component)
   - Links to coverage reports
7. Commit coverage reports to repository:
   - Unified `coverage/coverage.xml`
   - Component-specific HTML directories
   - Commits to the same branch that triggered the workflow

**Output**: 
- GitHub Actions step summary (visible in Actions UI)
- Unified coverage report committed to repository
- Component-specific HTML reports for detailed browsing

---

## Test Types and Coverage

### Unit Tests (`tests/unit/`)

**Purpose**: Test individual functions and classes in isolation.

**Characteristics**:
- Fast execution (~2-3 seconds for 163 tests)
- Heavy use of mocking (no external dependencies)
- High coverage of core logic
- Test files:
  - `test_rag_core.py`: Core RAG functions, internals, utilities
  - `test_rag_ingestion.py`: Ingestion pipeline, PDF processing
  - `test_rag_infrastructure.py`: CLI, GCS sync, Retriever

**Coverage**: ~73% of codebase

### Integration Tests (`tests/integration/`)

**Purpose**: Test component interactions with mocked services.

**Characteristics**:
- Tests API endpoints with mocked ChromaDB/GCS
- Validates request/response handling
- Tests error handling and edge cases
- ~15 tests

**Coverage**: API layer and service integrations

### System Tests (`tests/system/`)

**Purpose**: Test complete system with running server.

**Characteristics**:
- Real HTTP requests to running server
- End-to-end query processing
- Server health and readiness checks
- ~8 tests

**Coverage**: Full system behavior

---

## Coverage Requirements

### Minimum Coverage: 50%

The pipeline enforces a minimum of **50% code coverage** using `--cov-fail-under=50`. If coverage drops below this threshold, the pipeline fails.

### Current Coverage: ~73%

The RAG component currently maintains **~73% code coverage**, significantly exceeding the minimum requirement.

### Coverage Reports

Coverage reports are generated in multiple formats and locations:

**RAG Component Coverage** (generated during tests):
1. **Terminal Output**: Shown in CI logs with missing line numbers
2. **XML Report**: `src/rag/coverage/coverage.xml` - Component-specific coverage
3. **HTML Report**: `src/rag/coverage/htmlcov/index.html` - Detailed per-file coverage

**Unified Coverage** (generated in test-summary job):
1. **Unified XML Report**: `coverage/coverage.xml` - Combined coverage from all components
2. **Component-Specific HTML**: 
   - `coverage/htmlcov_rag/` - RAG component HTML report (copied from `src/rag/coverage/htmlcov/`)
   - `coverage/htmlcov_quantamental/` - Quantamental component HTML report (if exists)
   - `coverage/htmlcov_api/` - API-service component HTML report (if exists)

**Access**: 
- Unified coverage XML and component-specific HTML reports are committed to the repository
- Reports are available in the `coverage/` directory in the repository
- Component-specific reports provide detailed line-by-line coverage for each component

---

## Running Tests Locally

You can run the same tests locally using Docker, matching the CI pipeline configuration:

### Build the Image
```bash
# From project root
docker build -t rag-service:local -f src/rag/Dockerfile .
```

### Run Linting
```bash
docker run --rm rag-service:local sh -c \
  "black --check --line-length 120 rag.py && flake8 --max-line-length=120 --extend-ignore=E203,W503,E501,E722,W504,E402,F401,F841,F811,F821 rag.py"
```

### Run Unit Tests with Coverage
```bash
# Create coverage directory
mkdir -p src/rag/coverage

# Run tests (matching CI configuration)
docker run --rm \
  -v "${PWD}/src/rag/coverage:/workspace/coverage" \
  -e PYTHONPATH="/.venv/lib/python3.12/site-packages:$PYTHONPATH" \
  rag-service:local \
  pytest tests/unit/ --cov=rag --cov-branch --cov-report=term --cov-report=xml:/workspace/coverage/coverage.xml --cov-report=html:/workspace/coverage/htmlcov -m unit
```

### Run Integration Tests
```bash
docker run --rm \
  -e PYTHONPATH="/.venv/lib/python3.12/site-packages:$PYTHONPATH" \
  -e CHROMADB_HOST=localhost \
  -e CHROMADB_PORT=8000 \
  -e VECTOR_COLLECTION=test_collection \
  -e EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \
  -e ENABLE_CACHE=0 \
  -e AUTO_START_CHROMADB=0 \
  rag-service:local \
  pytest tests/integration/ -m integration
```

### Run System Tests
```bash
# Start server (matching CI configuration)
docker run -d --name rag-server -p 9000:9000 -p 8000:8000 \
  -e DEV=1 \
  -e AUTO_START_CHROMADB=0 \
  -e GCS_BUCKET_NAME="" \
  -e VECTOR_COLLECTION=test_collection \
  -e EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \
  -e ENABLE_CACHE=0 \
  rag-service:local

# Wait for server
for i in {1..10}; do
  if curl -f -s --max-time 2 http://localhost:9000/health > /dev/null 2>&1; then
    echo "✅ Server ready"
    break
  fi
  sleep 2
done

# Run tests (matching CI configuration)
docker run --rm --network host \
  -e PYTHONPATH="/.venv/lib/python3.12/site-packages:$PYTHONPATH" \
  rag-service:local \
  pytest tests/system/ -m system

# Cleanup
docker stop rag-server && docker rm rag-server
```

---

## Pipeline Performance

### Typical Execution Times (RAG Component)

- **Detect Changes**: ~10-15 seconds
- **Build RAG Image**: ~2-3 minutes (with cache) / ~4-5 minutes (without cache)
- **Lint & Unit Tests**: ~3-4 minutes (includes coverage analysis)
- **Integration Tests**: ~1-2 minutes (runs in parallel with lint-unit)
- **System Tests**: ~2-3 minutes (runs in parallel, conditional)
- **Test Summary**: ~30-60 seconds (includes coverage combination and commit)

**Total Pipeline Time for RAG**:
- **Full run** (all components): ~8-12 minutes (with cache) / ~12-16 minutes (without cache)
- **RAG only** (when only RAG changes): ~6-9 minutes (with cache) / ~9-12 minutes (without cache)
- **Feature branch** (no system tests): ~4-6 minutes (with cache)

### Optimization Strategies

1. **Conditional Execution**: Only runs tests for changed components (saves ~50% time)
2. **Matrix Strategy**: Runs test types in parallel for faster feedback
3. **Docker Layer Caching**: Uses GitHub Actions cache for Docker layers
4. **GHCR Image Storage**: Images pushed to GHCR for faster pulls in test jobs
5. **Parallel Test Execution**: Lint-unit, integration, and system tests run simultaneously
6. **Fast Failure**: Tests stop early on failures (`--maxfail`, `-x`)
7. **Conditional System Tests**: Only run on main branches
8. **Unified Coverage**: Single coverage report combines all components efficiently

---

## Troubleshooting

### Pipeline Fails on Linting

**Problem**: Black or Flake8 reports formatting/linting errors.

**Solution**:
```bash
# Format code
docker run --rm -v "${PWD}/src/rag:/workspace" rag-service:local \
  black --line-length 120 rag.py

# Check linting
docker run --rm -v "${PWD}/src/rag:/workspace" rag-service:local \
  flake8 --max-line-length=120 rag.py
```

### Coverage Below 50%

**Problem**: Coverage drops below minimum threshold.

**Solution**:
1. Review coverage report to identify uncovered code
2. Add tests for missing coverage
3. Focus on critical paths first
4. Use `pytest --cov=rag --cov-report=html` to see detailed HTML report

### System Tests Fail

**Problem**: System tests fail with connection errors.

**Possible Causes**:
- Server not starting properly
- Health endpoint not responding
- Port conflicts

**Solution**:
1. Check server logs in CI output
2. Verify server starts locally: `docker run -p 9000:9000 rag-service:local`
3. Test health endpoint: `curl http://localhost:9000/health`
4. Review system test logs for specific errors

### Tests Timeout

**Problem**: Tests exceed timeout limits.

**Solution**:
1. Check for infinite loops or hanging operations
2. Review test execution time locally
3. Consider optimizing slow tests
4. Increase timeout if test is legitimately slow

### Docker Build Fails

**Problem**: Docker image build fails.

**Possible Causes**:
- Missing dependencies in `pyproject.toml`
- Dockerfile syntax errors
- Build context issues

**Solution**:
1. Test build locally: `docker build -t rag-service:test -f src/rag/Dockerfile .`
2. Check Dockerfile syntax
3. Verify all dependencies are listed
4. Review build logs for specific errors

---

## CI Configuration Details

### Environment Variables

All test jobs use consistent environment variables to ensure reproducible test execution:

```bash
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
VECTOR_COLLECTION=test_collection
GCS_BUCKET_NAME=""  # Empty to disable GCS operations
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENABLE_CACHE=0  # Disable caching for tests
AUTO_START_CHROMADB=0  # Don't start ChromaDB server
GOOGLE_APPLICATION_CREDENTIALS=""  # No GCS credentials
```

### Pytest Configuration

Tests use configuration from `src/rag/pytest.ini`:

- **Test discovery**: `testpaths = tests`
- **Test patterns**: `test_*.py` files, `Test*` classes, `test_*` functions
- **Markers**: `unit`, `integration`, `system`, `slow`
- **Output**: Verbose with short tracebacks

### Docker Image Tagging

- **CI builds**: `rag-service:${{ github.sha }}` (commit SHA)
- **Local builds**: `rag-service:local` (or any custom tag)

---

## Best Practices

### Before Pushing

1. **Run tests locally**: Ensure all tests pass before pushing
2. **Check formatting**: Run `black` to format code
3. **Verify coverage**: Run with `--cov` to ensure coverage stays above 50%
4. **Review changes**: Make sure changes are focused and well-tested

### Writing Tests

1. **Use appropriate markers**: Mark tests as `@pytest.mark.unit`, `@pytest.mark.integration`, or `@pytest.mark.system`
2. **Mock external dependencies**: Unit tests should not make real network calls
3. **Test edge cases**: Include tests for empty inputs, None values, error conditions
4. **Keep tests fast**: Unit tests should complete in < 1 second each
5. **Maintain coverage**: Add tests when adding new code paths

### Debugging Failed Pipelines

1. **Check job logs**: Each job has detailed logs in GitHub Actions
2. **Download artifacts**: Coverage reports and logs are available as artifacts
3. **Reproduce locally**: Run the same commands locally to debug
4. **Review recent changes**: Check what changed that might have caused the failure

---

## Integration with Development Workflow

### Pull Request Workflow

1. **Create PR**: Push changes to feature branch
2. **CI Runs**: Pipeline automatically runs on PR creation/updates
3. **Review Results**: Check CI status in PR checks
4. **Fix Issues**: Address any failures before requesting review
5. **Merge**: PR can be merged when CI passes

### Commit Workflow

1. **Push to Branch**: Pipeline runs automatically
2. **Monitor Status**: Check Actions tab for pipeline status
3. **Fix if Needed**: Address failures before merging
4. **Deploy**: After merge to main, code is ready for deployment

---

## Future Enhancements

Potential improvements to the unified CI pipeline:

1. **Parallel Test Execution**: Use `pytest-xdist` to run tests in parallel within jobs
2. **Test Caching**: Cache test results for unchanged files
3. **Matrix Testing**: Test against multiple Python versions
4. **Performance Benchmarks**: Track test execution time over time
5. **Security Scanning**: Add security vulnerability scanning
6. **Dependency Updates**: Automatically check for dependency updates
7. **Unified HTML Coverage**: Generate detailed unified HTML report from combined XML (currently summary only)
8. **Coverage Trends**: Track coverage trends over time across all components

---

## Summary

The unified CI pipeline provides the following for the RAG component:

 **Unified Architecture**: Single pipeline handles RAG, Quantamental, and API-service components  
 **Conditional Execution**: Only runs tests for changed components (saves ~50% time)  
 **Matrix Strategy**: Runs test types in parallel for faster feedback  
 **Automated Quality Checks**: Linting, formatting, and style validation  
 **Comprehensive Testing**: Unit, integration, and system tests  
 **Coverage Enforcement**: Minimum 50% coverage requirement (currently ~73%)  
 **Unified Coverage Reports**: Combines coverage from all components into single report  
 **Fast Feedback**: Parallel execution and fast failure modes  
 **Consistent Environment**: Docker-based testing ensures reproducibility  
 **Detailed Reporting**: Component-specific and unified coverage reports  
 **GHCR Integration**: Images stored in GitHub Container Registry for efficient caching  

The pipeline ensures code quality and reliability while providing fast feedback to developers. The unified approach reduces maintenance overhead and provides consistent testing across all components.

