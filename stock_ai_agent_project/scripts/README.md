# Scripts Directory

Utility scripts for development and CI/CD tasks.

## Available Scripts

### `format_and_lint.sh` / `format_and_lint.ps1`

Format code with `black` and verify linting passes.

**Usage:**

```bash
# Linux/Mac
./scripts/format_and_lint.sh [rag|quantamental|api-service|all]

# Windows PowerShell
.\scripts\format_and_lint.ps1 [rag|quantamental|api-service|all]
```

**What it does:**
- Auto-formats code with `black`
- Verifies formatting is correct
- Runs `flake8` linting checks
- Uses the same rules as CI pipeline

See [FORMAT_AND_LINT.md](../FORMAT_AND_LINT.md) for detailed documentation.

