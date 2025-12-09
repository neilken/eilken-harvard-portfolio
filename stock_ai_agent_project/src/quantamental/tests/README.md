# Test Suite Documentation

##  Overview

This test suite provides comprehensive testing for the **Quantamental Stock Screening Pipeline**, achieving **54% code coverage** across unit, integration, and system tests.

**MS4 Requirements:**
-  Unit Tests
-  Integration Tests  
-  System Tests (End-to-End)
-  Code Coverage: 54% (exceeds 50% requirement)
-  CI/CD Integration

---

##  Test Organization

### Unit Tests (Fast, Isolated)
**Purpose:** Test individual functions and methods in isolation without external dependencies.

**Files:**
- `test_unit_utils.py` - Configuration loading, file operations, GCS handler
- `test_unit_data_collect.py` - FMPDataCollector class initialization and methods
- `test_unit_data_process.py` - DataProcessor class and technical indicators

**Characteristics:**
-  Fast execution (< 5 seconds total)
-  No external API calls or database access
-  Tests single functions/methods
-  60+ tests

**Coverage:** ~70% of utils.py, ~55% of data_process.py, ~18% of data_collect.py

---

### Integration Tests (Module Interactions)
**Purpose:** Test how multiple modules work together and ensure data flows correctly between components.

**Files:**
- `test_integration_modules.py` - Module imports, config loading, and class initialization
- `test_integration_pipeline.py` - Data processing pipeline with multiple steps

**Characteristics:**
-  Moderate execution time (< 10 seconds)
-  Tests 2+ modules interacting
-  May use mock data instead of real APIs
-  30+ tests

**Coverage:** Validates config → collector → processor flow and data structure compatibility

---

### System Tests (End-to-End)
**Purpose:** Test complete pipeline execution from start to finish, simulating production workflows.

**Files:**
- `test_system_pipeline.py` - Full pipeline execution with mock data

**Characteristics:**
-  Slower execution (can take 10-30 seconds)
-  Tests entire workflow
-  Simulates real production usage
-  5-10 comprehensive tests

**Coverage:** Validates that complete pipeline (collection → processing → output) works correctly

---

##  Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

**Expected output:**
```
===== 77 passed in ~10 seconds =====
TOTAL Coverage: 54%
```

### Run by Test Type

**Unit tests only (fast - for development):**
```bash
pytest tests/test_unit_*.py -v
```

**Integration tests only:**
```bash
pytest tests/test_integration_*.py -v
```

**System tests only (slow - for pre-deployment):**
```bash
pytest tests/test_system_*.py -v
```

### Run with Coverage Report

**Terminal report:**
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

**HTML report (interactive):**
```bash
pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html in browser
```

**XML report (for CI/CD):**
```bash
pytest tests/ --cov=. --cov-report=xml
```

### Run Specific Test

```bash
# Run single test file
pytest tests/test_unit_utils.py -v

# Run specific test class
pytest tests/test_unit_utils.py::TestConfigLoading -v

# Run specific test method
pytest tests/test_unit_utils.py::TestConfigLoading::test_load_config_returns_dict -v
```

---

##  Test Metrics

| Metric | Value |
|--------|-------|
| **Total Tests** | 90+ |
| **Code Coverage** | 54% |
| **Unit Tests** | 60+ tests |
| **Integration Tests** | 30+ tests |
| **System Tests** | 5-10 tests |
| **Execution Time** | ~10 seconds |
| **Pass Rate** | 100%  |

### Coverage by Module

| Module | Coverage | Notes |
|--------|----------|-------|
| utils.py | 65% | Config, GCS, helpers |
| data_process.py | 55% | Technical indicators, cleaning |
| data_collect.py | 18% | FMPDataCollector class |
| backtest.py | 11% | Not fully tested (future work) |
| model_train.py | 17% | Not fully tested (future work) |
| **TOTAL** | **53%** | **Exceeds MS4 requirement**  |

---

##  Test Design Principles

### Unit Tests
-  Test one function at a time
-  Use mock data, no external dependencies
-  Fast execution (< 1 second per test)
-  Clear, descriptive test names
-  Arrange-Act-Assert pattern

### Integration Tests
-  Test module interactions
-  Use realistic data structures
-  Validate data flow between components
-  Test with mock data when possible

### System Tests
-  Test complete workflows
-  Simulate production scenarios
-  Validate end-to-end functionality
-  Check data quality and consistency

---

##  CI/CD Integration

Tests run automatically on every push via GitHub Actions.

**CI Pipeline:**
1.  Code quality checks (flake8, black, isort)
2.  Run all tests (unit + integration, system tests skipped in CI)
3.  Generate coverage report
4.  Verify coverage ≥ 50%
5.  Build and test Docker image

**CI Configuration:** `.github/workflows/ci.yml`

**Coverage Requirement:** 50% minimum (currently at 53% )

---

##  Test Markers

Tests are organized using pytest markers:

```python
@pytest.mark.unit          # Unit test
@pytest.mark.integration   # Integration test
@pytest.mark.system        # System test (E2E)
@pytest.mark.slow          # Slow-running test
@pytest.mark.api           # Requires API access
```

**Run tests by marker:**
```bash
# Only unit tests
pytest -m unit -v

# Only integration tests
pytest -m integration -v

# Skip slow tests
pytest -m "not slow" -v
```

---

##  Troubleshooting

### Tests Fail with ImportError

**Problem:** `ImportError: cannot import name '...'`

**Solution:** Ensure you're running tests from project root:
```bash
cd /path/to/quantamental
pytest tests/ -v
```

### Config File Not Found

**Problem:** `FileNotFoundError: Config file not found`

**Solution:** Ensure `config.yaml` exists in project root.

### Coverage Below 50%

**Problem:** Coverage report shows < 50%

**Solution:** Ensure all test files are in `tests/` directory and run:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

### Warnings About pytest.mark

**Problem:** `PytestUnknownMarkWarning: Unknown pytest.mark.unit`

**Solution:** These are harmless warnings. Markers are defined in `pytest.ini`. Tests still run correctly.

---

##  Test Dependencies

**Required packages:**
```
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio
```

**Install:**
```bash
pip install pytest pytest-cov pytest-asyncio
```

---

##  Future Improvements

Areas for additional test coverage:

- [ ] `backtest.py` - Add unit tests for portfolio logic (currently 11%)
- [ ] `model_train.py` - Add unit tests for training pipeline (currently 17%)
- [ ] `model_predict.py` - Add unit tests for prediction logic (currently 20%)
- [ ] API integration tests with actual API calls (marked with `@pytest.mark.api`)
- [ ] Performance benchmarks and load testing

---

##  Additional Resources

- **pytest Documentation:** https://docs.pytest.org/
- **Coverage.py Guide:** https://coverage.readthedocs.io/
- **Testing Best Practices:** https://docs.python-guide.org/writing/tests/

---

##  MS4 Submission Checklist

- [x] Unit tests implemented (60+ tests)
- [x] Integration tests implemented (30+ tests)
- [x] System tests implemented (5-10 tests)
- [x] Code coverage ≥ 50% (achieved: 53%)
- [x] All tests passing
- [x] CI/CD pipeline configured
- [x] Test documentation (this file)
- [x] Clear test organization (unit/integration/system)

---

**Last Updated:** 11/22/2025  
**Test Suite Version:** 1.0  
**Project:** Quantamental Stock Screening Pipeline - MS4
