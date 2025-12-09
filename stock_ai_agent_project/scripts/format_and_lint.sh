#!/bin/bash
# Format code with black and verify linting passes (optimized version)
# Usage: ./scripts/format_and_lint.sh [component] [--changed-only]
#   component: rag, quantamental, api-service, or all (default: all)
#   --changed-only: Only format/lint files changed in git (faster)

set -e  # Exit on error

COMPONENT="${1:-all}"
CHANGED_ONLY=false

# Parse --changed-only flag
if [[ "$1" == "--changed-only" ]] || [[ "$2" == "--changed-only" ]]; then
    CHANGED_ONLY=true
    if [[ "$1" == "--changed-only" ]]; then
        COMPONENT="${2:-all}"
    fi
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "[INFO] Formatting and linting code..."

# Check if black is installed (only once)
# Try python -m black first (more reliable cross-platform)
# Use explicit Python command that works in both bash and PowerShell
PYTHON_CMD="python"
if ! command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python3"
fi

if $PYTHON_CMD -m black --version >/dev/null 2>&1; then
    BLACK_CMD="$PYTHON_CMD -m black"
elif command -v black >/dev/null 2>&1; then
    BLACK_CMD="black"
else
    echo -e "${YELLOW}[WARN] black not found. Attempting to install (max 30s)...${NC}"
    # Use timeout if available, otherwise try background install with kill
    if command -v timeout >/dev/null 2>&1; then
        timeout 30 $PYTHON_CMD -m pip install black >/dev/null 2>&1 || true
    else
        # Fallback: run in background and kill after timeout
        ($PYTHON_CMD -m pip install black >/dev/null 2>&1) &
        INSTALL_PID=$!
        sleep 30
        kill $INSTALL_PID 2>/dev/null || true
        wait $INSTALL_PID 2>/dev/null || true
    fi
    if $PYTHON_CMD -m black --version >/dev/null 2>&1; then
        BLACK_CMD="$PYTHON_CMD -m black"
    elif command -v black >/dev/null 2>&1; then
        BLACK_CMD="black"
    else
        echo -e "${RED}[ERROR] Could not find or install black.${NC}"
        echo -e "${YELLOW}[INFO] Please install manually: $PYTHON_CMD -m pip install black${NC}"
        echo -e "${YELLOW}[INFO] On Windows, consider using: .\\scripts\\format_and_lint.ps1${NC}"
        exit 1
    fi
fi

# Check if flake8 is installed (only once)
# Try python -m flake8 first (more reliable cross-platform)
if $PYTHON_CMD -m flake8 --version >/dev/null 2>&1; then
    FLAKE8_CMD="$PYTHON_CMD -m flake8"
elif command -v flake8 >/dev/null 2>&1; then
    FLAKE8_CMD="flake8"
else
    echo -e "${YELLOW}[WARN] flake8 not found. Attempting to install (max 30s)...${NC}"
    if command -v timeout >/dev/null 2>&1; then
        timeout 30 $PYTHON_CMD -m pip install flake8 >/dev/null 2>&1 || true
    else
        ($PYTHON_CMD -m pip install flake8 >/dev/null 2>&1) &
        INSTALL_PID=$!
        sleep 30
        kill $INSTALL_PID 2>/dev/null || true
        wait $INSTALL_PID 2>/dev/null || true
    fi
    if $PYTHON_CMD -m flake8 --version >/dev/null 2>&1; then
        FLAKE8_CMD="$PYTHON_CMD -m flake8"
    elif command -v flake8 >/dev/null 2>&1; then
        FLAKE8_CMD="flake8"
    else
        echo -e "${RED}[ERROR] Could not find or install flake8.${NC}"
        echo -e "${YELLOW}[INFO] Please install manually: $PYTHON_CMD -m pip install flake8${NC}"
        echo -e "${YELLOW}[INFO] On Windows, consider using: .\\scripts\\format_and_lint.ps1${NC}"
        exit 1
    fi
fi

# Function to get changed Python files for a component
get_changed_files() {
    local component=$1
    if [ "$CHANGED_ONLY" = true ] && command -v git &> /dev/null; then
        case "$component" in
            rag)
                git diff --name-only --diff-filter=ACMR HEAD | grep -E "^src/rag/.*\.py$" || true
                ;;
            quantamental)
                git diff --name-only --diff-filter=ACMR HEAD | grep -E "^src/quantamental/.*\.py$" || true
                ;;
            api-service)
                git diff --name-only --diff-filter=ACMR HEAD | grep -E "^src/api-service/.*\.py$" || true
                ;;
        esac
    fi
}

# Function to format and lint RAG
format_lint_rag() {
    local start_time=$(date +%s)
    echo ""
    echo "========================================"
    echo "[RAG] Component"
    echo "========================================"
    
    if [ ! -f "src/rag/rag.py" ]; then
        echo -e "${YELLOW}[WARN] RAG file not found, skipping...${NC}"
        return 0
    fi
    
    # Check if we should only process changed files
    if [ "$CHANGED_ONLY" = true ]; then
        local changed_files=$(get_changed_files rag)
        if [ -z "$changed_files" ]; then
            echo -e "${BLUE}[INFO] No RAG files changed, skipping...${NC}"
            return 0
        fi
        echo -e "${BLUE}[INFO] Processing changed files only${NC}"
    fi
    
    echo "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests), exclude archived files
    if ! $BLACK_CMD --line-length 120 --exclude '/(__pycache__|\.venv|venv|_archived)/' src/rag/ 2>/dev/null; then
        echo -e "${RED}[FAIL] RAG formatting failed${NC}"
        return 1
    fi
    
    echo "[INFO] Running flake8 linting..."
    # Match CI: lint entire directory (including tests), exclude archived files
    if $FLAKE8_CMD --max-line-length=120 --extend-ignore=E203,W503,E501,E722,W504,E402,F401,F841,F811,F821,F541,E231 --exclude=_archived src/rag/ 2>/dev/null; then
        local elapsed=$(( $(date +%s) - start_time ))
        echo -e "${GREEN}[OK] RAG passed (${elapsed}s)${NC}"
        return 0
    else
        echo -e "${RED}[FAIL] RAG linting failed${NC}"
        return 1
    fi
}

# Function to format and lint Quantamental
format_lint_quantamental() {
    local start_time=$(date +%s)
    echo ""
    echo "========================================"
    echo "[QUANTAMENTAL] Component"
    echo "========================================"
    
    if [ ! -d "src/quantamental" ]; then
        echo -e "${YELLOW}[WARN] Quantamental directory not found, skipping...${NC}"
        return 0
    fi
    
    # Check if we should only process changed files
    if [ "$CHANGED_ONLY" = true ]; then
        local changed_files=$(get_changed_files quantamental)
        if [ -z "$changed_files" ]; then
            echo -e "${BLUE}[INFO] No Quantamental files changed, skipping...${NC}"
            return 0
        fi
        echo -e "${BLUE}[INFO] Processing changed files only${NC}"
    fi
    
    echo "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests)
    if ! $BLACK_CMD --exclude '/(__pycache__|\.venv|venv)/' src/quantamental/ 2>/dev/null; then
        echo -e "${RED}[FAIL] Quantamental formatting failed${NC}"
        return 1
    fi
    
    echo "[INFO] Running flake8 linting..."
    # Match CI: two separate flake8 runs (entire directory including tests)
    # First run: strict errors (E9,F63,F7,F82)
    if ! $FLAKE8_CMD --count --select=E9,F63,F7,F82 --show-source --statistics src/quantamental/ 2>/dev/null; then
        echo -e "${RED}[FAIL] Quantamental linting failed (strict errors)${NC}"
        return 1
    fi
    # Second run: warnings with exit-zero (matches CI behavior)
    if $FLAKE8_CMD --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics src/quantamental/ 2>/dev/null; then
        local elapsed=$(( $(date +%s) - start_time ))
        echo -e "${GREEN}[OK] Quantamental passed (${elapsed}s)${NC}"
        return 0
    else
        echo -e "${RED}[FAIL] Quantamental linting failed${NC}"
        return 1
    fi
}

# Function to format and lint API-service
format_lint_api_service() {
    local start_time=$(date +%s)
    echo ""
    echo "========================================"
    echo "[API-SERVICE] Component"
    echo "========================================"
    
    if [ ! -d "src/api-service" ]; then
        echo -e "${YELLOW}[WARN] API-service directory not found, skipping...${NC}"
        return 0
    fi
    
    # Check if we should only process changed files
    if [ "$CHANGED_ONLY" = true ]; then
        local changed_files=$(get_changed_files api-service)
        if [ -z "$changed_files" ]; then
            echo -e "${BLUE}[INFO] No API-service files changed, skipping...${NC}"
            return 0
        fi
        echo -e "${BLUE}[INFO] Processing changed files only${NC}"
    fi
    
    echo "[INFO] Formatting with black..."
    # Match CI: format entire directory (including tests)
    if ! $BLACK_CMD --exclude '/(__pycache__|\.venv|venv)/' src/api-service/ 2>/dev/null; then
        echo -e "${RED}[FAIL] API-service formatting failed${NC}"
        return 1
    fi
    
    echo "[INFO] Running flake8 linting..."
    # Match CI: two separate flake8 runs (entire directory including tests)
    # First run: strict errors (E9,F63,F7,F82)
    if ! $FLAKE8_CMD --count --select=E9,F63,F7,F82 --show-source --statistics src/api-service/ 2>/dev/null; then
        echo -e "${RED}[FAIL] API-service linting failed (strict errors)${NC}"
        return 1
    fi
    # Second run: warnings with exit-zero (matches CI behavior)
    if $FLAKE8_CMD --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics src/api-service/ 2>/dev/null; then
        local elapsed=$(( $(date +%s) - start_time ))
        echo -e "${GREEN}[OK] API-service passed (${elapsed}s)${NC}"
        return 0
    else
        echo -e "${RED}[FAIL] API-service linting failed${NC}"
        return 1
    fi
}

# Main execution
ERRORS=0
TOTAL_START=$(date +%s)

case "$COMPONENT" in
    rag)
        format_lint_rag || ERRORS=$((ERRORS + 1))
        ;;
    quantamental)
        format_lint_quantamental || ERRORS=$((ERRORS + 1))
        ;;
    api-service)
        format_lint_api_service || ERRORS=$((ERRORS + 1))
        ;;
    all)
        # Run components in parallel for maximum efficiency
        echo -e "${BLUE}[INFO] Running all components in parallel...${NC}"
        (
            format_lint_rag || echo "rag_failed" > /tmp/format_errors.$$
        ) &
        PID_RAG=$!
        
        (
            format_lint_quantamental || echo "quant_failed" >> /tmp/format_errors.$$
        ) &
        PID_QUANT=$!
        
        (
            format_lint_api_service || echo "api_failed" >> /tmp/format_errors.$$
        ) &
        PID_API=$!
        
        # Wait for all background jobs
        wait $PID_RAG
        wait $PID_QUANT
        wait $PID_API
        
        # Check for errors
        if [ -f /tmp/format_errors.$$ ]; then
            ERRORS=$(wc -l < /tmp/format_errors.$$)
            rm -f /tmp/format_errors.$$
        fi
        ;;
    *)
        echo -e "${RED}[FAIL] Invalid component: $COMPONENT${NC}"
        echo "Usage: ./scripts/format_and_lint.sh [rag|quantamental|api-service|all] [--changed-only]"
        exit 1
        ;;
esac

TOTAL_ELAPSED=$(( $(date +%s) - TOTAL_START ))

echo ""
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}[OK] All checks passed! (Total: ${TOTAL_ELAPSED}s)${NC}"
    exit 0
else
    echo -e "${RED}[FAIL] $ERRORS component(s) failed (Total: ${TOTAL_ELAPSED}s)${NC}"
    exit 1
fi
