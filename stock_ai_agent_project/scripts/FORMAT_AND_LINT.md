# Format and Lint Scripts

Simple scripts to format code with `black` and verify linting passes.

## Usage

### Linux/Mac (Bash)
```bash
# Format and lint all components (runs in parallel)
./scripts/format_and_lint.sh

# Format and lint specific component
./scripts/format_and_lint.sh rag
./scripts/format_and_lint.sh quantamental
./scripts/format_and_lint.sh api-service

# Only process changed files (much faster)
./scripts/format_and_lint.sh all --changed-only
./scripts/format_and_lint.sh rag --changed-only
```

### Windows (PowerShell)
```powershell
# Format and lint all components (runs in parallel)
.\scripts\format_and_lint.ps1

# Format and lint specific component
.\scripts\format_and_lint.ps1 rag
.\scripts\format_and_lint.ps1 quantamental
.\scripts\format_and_lint.ps1 api-service

# Only process changed files (much faster)
.\scripts\format_and_lint.ps1 all -ChangedOnly
.\scripts\format_and_lint.ps1 rag -ChangedOnly
```

## What It Does

1. **Installs dependencies** (if needed):
   - `black` - Code formatter
   - `flake8` - Linter

2. **Formats code** with `black`:
   - RAG: `black --line-length 120 src/rag/rag.py`
   - Quantamental: `black src/quantamental/`
   - API-service: `black src/api-service/`

3. **Verifies formatting** with `black --check`

4. **Runs linting** with `flake8`:
   - Uses the same linting rules as your CI pipeline
   - RAG: `--max-line-length=120 --extend-ignore=E203,W503,E501,E722,W504,E402,F401,F841,F811,F821`
   - Quantamental/API-service: `--max-line-length=127 --max-complexity=10`

## Exit Codes

- `0` - All checks passed
- `1` - One or more checks failed

## Performance Optimizations

The scripts include several optimizations:

1. **Parallel Execution**: When running `all` components, they run in parallel (3x faster)
2. **Changed Files Only**: Use `--changed-only` flag to only process git-changed files (10-100x faster)
3. **Combined Linting**: Single flake8 run instead of multiple passes
4. **Early Exit**: Stops immediately on formatting failures
5. **Timing**: Shows elapsed time per component and total time

**Performance Examples:**
- All components (sequential): ~8-12 seconds
- All components (parallel): ~3-5 seconds
- Changed files only: ~1-2 seconds (depends on changes)

## Integration with CI

You can use this script in your CI pipeline instead of running `black --check` separately. The script will:
- Auto-format any issues
- Verify formatting is correct
- Check linting passes

This ensures code is always properly formatted before tests run.

