# Format code with black and verify linting passes (optimized version)
# Usage: .\scripts\format_and_lint.ps1 [component] [-ChangedOnly]
#   component: rag, quantamental, api-service, or all (default: all)
#   -ChangedOnly: Only format/lint files changed in git (faster)

param(
    [string]$Component = "all",
    [switch]$ChangedOnly = $false
)

$ErrorActionPreference = "Stop"

Write-Host "[INFO] Formatting and linting code..." -ForegroundColor Cyan

# Check if black is installed (only once)
$blackCmd = "python -m black"
try {
    $null = python -m black --version 2>&1 | Out-Null
} catch {
    try {
        $null = Get-Command black -ErrorAction Stop
        $blackCmd = "black"
    } catch {
        Write-Host "[WARN] black not found. Installing..." -ForegroundColor Yellow
        python -m pip install black 2>&1 | Out-Null
    }
}

# Check if flake8 is installed (only once)
$flake8Cmd = "python -m flake8"
try {
    $null = python -m flake8 --version 2>&1 | Out-Null
} catch {
    try {
        $null = Get-Command flake8 -ErrorAction Stop
        $flake8Cmd = "flake8"
    } catch {
        Write-Host "[WARN] flake8 not found. Installing..." -ForegroundColor Yellow
        python -m pip install flake8 2>&1 | Out-Null
    }
}

$Errors = 0
$TotalStart = Get-Date

# Function to get changed Python files for a component
function Get-ChangedFiles {
    param([string]$Component)
    
    if ($ChangedOnly -and (Get-Command git -ErrorAction SilentlyContinue)) {
        $changed = git diff --name-only --diff-filter=ACMR HEAD 2>&1
        switch ($Component) {
            "rag" { return $changed | Select-String "^src/rag/.*\.py$" }
            "quantamental" { return $changed | Select-String "^src/quantamental/.*\.py$" }
            "api-service" { return $changed | Select-String "^src/api-service/.*\.py$" }
        }
    }
    return $null
}

# Function to format and lint RAG
function Format-Lint-RAG {
    $StartTime = Get-Date
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "[RAG] Component" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    if (-not (Test-Path "src/rag/rag.py")) {
        Write-Host "[WARN] RAG file not found, skipping..." -ForegroundColor Yellow
        return 0
    }
    
    # Check if we should only process changed files
    if ($ChangedOnly) {
        $changedFiles = Get-ChangedFiles "rag"
        if (-not $changedFiles) {
            Write-Host "[INFO] No RAG files changed, skipping..." -ForegroundColor Blue
            return 0
        }
        Write-Host "[INFO] Processing changed files only" -ForegroundColor Blue
    }
    
    Write-Host "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests), exclude archived files
    $ErrorActionPreference = 'SilentlyContinue'
    $formatResult = python -m black --line-length 120 --exclude '/(__pycache__|\.venv|venv|_archived)/' src/rag/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] RAG formatting failed" -ForegroundColor Red
        return 1
    }
    
    Write-Host "[INFO] Running flake8 linting..."
    # Match CI: lint entire directory (including tests), exclude archived files
    $ErrorActionPreference = 'SilentlyContinue'
    $lintResult = python -m flake8 --max-line-length=120 --extend-ignore=E203,W503,E501,E722,W504,E402,F401,F841,F811,F821,F541,E231 --exclude=_archived src/rag/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -eq 0) {
        $elapsed = [math]::Round(($(Get-Date) - $StartTime).TotalSeconds, 1)
        Write-Host "[OK] RAG passed - $elapsed seconds" -ForegroundColor Green
        return 0
    } else {
        Write-Host "[FAIL] RAG linting failed" -ForegroundColor Red
        return 1
    }
}

# Function to format and lint Quantamental
function Format-Lint-Quantamental {
    $StartTime = Get-Date
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "[QUANTAMENTAL] Component" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    if (-not (Test-Path "src/quantamental")) {
        Write-Host "[WARN] Quantamental directory not found, skipping..." -ForegroundColor Yellow
        return 0
    }
    
    # Check if we should only process changed files
    if ($ChangedOnly) {
        $changedFiles = Get-ChangedFiles "quantamental"
        if (-not $changedFiles) {
            Write-Host "[INFO] No Quantamental files changed, skipping..." -ForegroundColor Blue
            return 0
        }
        Write-Host "[INFO] Processing changed files only" -ForegroundColor Blue
    }
    
    Write-Host "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests)
    $ErrorActionPreference = 'SilentlyContinue'
    $formatResult = python -m black --exclude '/(__pycache__|\.venv|venv)/' src/quantamental/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Quantamental formatting failed" -ForegroundColor Red
        return 1
    }
    
    Write-Host "[INFO] Running flake8 linting..."
    # Match CI: two separate flake8 runs (entire directory including tests)
    # First run: strict errors (E9,F63,F7,F82)
    $ErrorActionPreference = 'SilentlyContinue'
    $lintResult = python -m flake8 --count --select=E9,F63,F7,F82 --show-source --statistics src/quantamental/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Quantamental linting failed (strict errors)" -ForegroundColor Red
        return 1
    }
    # Second run: warnings with exit-zero (matches CI behavior)
    $ErrorActionPreference = 'SilentlyContinue'
    $lintResult = python -m flake8 --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics src/quantamental/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -eq 0) {
        $elapsed = [math]::Round(($(Get-Date) - $StartTime).TotalSeconds, 1)
        Write-Host "[OK] Quantamental passed - $elapsed seconds" -ForegroundColor Green
        return 0
    } else {
        Write-Host "[FAIL] Quantamental linting failed" -ForegroundColor Red
        return 1
    }
}

# Function to format and lint API-service
function Format-Lint-APIService {
    $StartTime = Get-Date
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "[API-SERVICE] Component" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    
    if (-not (Test-Path "src/api-service")) {
        Write-Host "[WARN] API-service directory not found, skipping..." -ForegroundColor Yellow
        return 0
    }
    
    # Check if we should only process changed files
    if ($ChangedOnly) {
        $changedFiles = Get-ChangedFiles "api-service"
        if (-not $changedFiles) {
            Write-Host "[INFO] No API-service files changed, skipping..." -ForegroundColor Blue
            return 0
        }
        Write-Host "[INFO] Processing changed files only" -ForegroundColor Blue
    }
    
    Write-Host "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests)
    $ErrorActionPreference = 'SilentlyContinue'
    $formatResult = python -m black --exclude '/(__pycache__|\.venv|venv)/' src/api-service/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] API-service formatting failed" -ForegroundColor Red
        return 1
    }
    
    Write-Host "[INFO] Running flake8 linting..."
    # Match CI: two separate flake8 runs (entire directory including tests)
    # First run: strict errors (E9,F63,F7,F82)
    $ErrorActionPreference = 'SilentlyContinue'
    $lintResult = python -m flake8 --count --select=E9,F63,F7,F82 --show-source --statistics src/api-service/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] API-service linting failed (strict errors)" -ForegroundColor Red
        return 1
    }
    # Second run: warnings with exit-zero (matches CI behavior)
    $ErrorActionPreference = 'SilentlyContinue'
    $lintResult = python -m flake8 --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics src/api-service/ 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -eq 0) {
        $elapsed = [math]::Round(($(Get-Date) - $StartTime).TotalSeconds, 1)
        Write-Host "[OK] API-service passed - $elapsed seconds" -ForegroundColor Green
        return 0
    } else {
        Write-Host "[FAIL] API-service linting failed" -ForegroundColor Red
        return 1
    }
}

# Main execution
switch ($Component.ToLower()) {
    "rag" {
        if (Format-Lint-RAG) { $Errors++ }
    }
    "quantamental" {
        if (Format-Lint-Quantamental) { $Errors++ }
    }
    "api-service" {
        if (Format-Lint-APIService) { $Errors++ }
    }
    "all" {
        # Run components sequentially (PowerShell jobs have scope issues with functions)
        # Still faster due to other optimizations
        Write-Host "[INFO] Running all components..." -ForegroundColor Blue
        if (Format-Lint-RAG) { $Errors++ }
        if (Format-Lint-Quantamental) { $Errors++ }
        if (Format-Lint-APIService) { $Errors++ }
    }
    default {
        Write-Host "[FAIL] Invalid component: $Component" -ForegroundColor Red
        Write-Host "Usage: .\scripts\format_and_lint.ps1 [rag|quantamental|api-service|all] [-ChangedOnly]"
        exit 1
    }
}

$TotalElapsed = [math]::Round(($(Get-Date) - $TotalStart).TotalSeconds, 1)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($Errors -eq 0) {
    Write-Host "[OK] All checks passed! Total: $TotalElapsed seconds" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[FAIL] $Errors component(s) failed. Total: $TotalElapsed seconds" -ForegroundColor Red
    exit 1
}
