# Comprehensive Deployment Testing Script for Stock Busters
# Tests all endpoints and verifies deployment functionality

param(
    [string]$APP_URL = "http://34.60.47.248.sslip.io",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$TestResults = @()

function Write-TestResult {
    param(
        [string]$TestName,
        [bool]$Passed,
        [string]$Message = ""
    )
    
    $status = if ($Passed) { "PASS" } else { "FAIL" }
    $color = if ($Passed) { "Green" } else { "Red" }
    
    Write-Host "[$status] $TestName" -ForegroundColor $color
    if ($Message) {
        Write-Host "   $Message" -ForegroundColor Gray
    }
    
    $script:TestResults += @{
        Test = $TestName
        Passed = $Passed
        Message = $Message
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stock Busters Deployment Testing" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Testing application at: $APP_URL" -ForegroundColor Yellow
Write-Host ""

$API_BASE = "$APP_URL/api-service"
$MODEL = "gemini"  # Default model

# ========================================
# 1. Frontend Tests
# ========================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. Frontend Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $APP_URL -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    Write-TestResult -TestName "Frontend Accessibility" -Passed ($response.StatusCode -eq 200) -Message "HTTP $($response.StatusCode)"
} catch {
    Write-TestResult -TestName "Frontend Accessibility" -Passed $false -Message $_.Exception.Message
}

# ========================================
# 2. API Root Tests
# ========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "2. API Root Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Test API root
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $content = $response.Content | ConvertFrom-Json
    $passed = ($response.StatusCode -eq 200) -and ($content.message -like "*Stockbusters*")
    Write-TestResult -TestName "API Root Endpoint" -Passed $passed -Message "HTTP $($response.StatusCode), Message: $($content.message)"
} catch {
    Write-TestResult -TestName "API Root Endpoint" -Passed $false -Message $_.Exception.Message
}

# Test square root endpoint
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/square_root/?x=3&y=4" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $result = [float]($response.Content)
    $expected = [Math]::Sqrt(3*3 + 4*4)  # Should be 5
    $passed = ($response.StatusCode -eq 200) -and ([Math]::Abs($result - $expected) -lt 0.01)
    Write-TestResult -TestName "Square Root Endpoint" -Passed $passed -Message "Result: $result (expected: $expected)"
} catch {
    Write-TestResult -TestName "Square Root Endpoint" -Passed $false -Message $_.Exception.Message
}

# ========================================
# 3. Stock Details Tests
# ========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "3. Stock Details Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Test stock details endpoint
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/details/AAPL" -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
    $content = $response.Content | ConvertFrom-Json
    $hasProfile = $null -ne $content.company_profile
    $hasQuantData = $null -ne $content.quant_data
    $hasOHLCV = $null -ne $content.ohlcv_data
    $passed = ($response.StatusCode -eq 200) -and ($hasProfile -or $hasQuantData -or $hasOHLCV)
    Write-TestResult -TestName "Stock Details (AAPL)" -Passed $passed -Message "HTTP $($response.StatusCode), Has data: Profile=$hasProfile, Quant=$hasQuantData, OHLCV=$hasOHLCV"
} catch {
    Write-TestResult -TestName "Stock Details (AAPL)" -Passed $false -Message $_.Exception.Message
}

# Test another ticker
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/details/GOOGL" -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
    $passed = $response.StatusCode -eq 200
    Write-TestResult -TestName "Stock Details (GOOGL)" -Passed $passed -Message "HTTP $($response.StatusCode)"
} catch {
    Write-TestResult -TestName "Stock Details (GOOGL)" -Passed $false -Message $_.Exception.Message
}

# Test invalid ticker
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/details/INVALIDTICKER123" -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $passed = $response.StatusCode -eq 200  # Should still return 200, but with empty/missing data
    Write-TestResult -TestName "Stock Details (Invalid Ticker)" -Passed $passed -Message "HTTP $($response.StatusCode) - Handled gracefully"
} catch {
    # 404 or other error is acceptable for invalid ticker
    Write-TestResult -TestName "Stock Details (Invalid Ticker)" -Passed $true -Message "Error handled: $($_.Exception.Message)"
}

# ========================================
# 4. Chat Endpoints Tests
# ========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "4. Chat Endpoints Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$SESSION_ID = "test-session-$(Get-Date -Format 'yyyyMMddHHmmss')"
$headers = @{
    "X-Session-ID" = $SESSION_ID
    "Content-Type" = "application/json"
}

# Test get chats (empty initially)
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats" -Headers $headers -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $content = $response.Content | ConvertFrom-Json
    $passed = ($response.StatusCode -eq 200) -and ($null -ne $content)
    Write-TestResult -TestName "Get Chats (Empty List)" -Passed $passed -Message "HTTP $($response.StatusCode), Chats: $($content.Count)"
} catch {
    Write-TestResult -TestName "Get Chats (Empty List)" -Passed $false -Message $_.Exception.Message
}

# Test start chat
$chatId = $null
try {
    $body = @{
        message = "Hello, I'm testing the deployment"
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats" -Method POST -Headers $headers -Body $body -TimeoutSec 30 -UseBasicParsing -ErrorAction Stop
    $content = $response.Content | ConvertFrom-Json
    $chatId = $content.chat_id
    $passed = ($response.StatusCode -eq 200) -and ($null -ne $chatId)
    Write-TestResult -TestName "Start Chat" -Passed $passed -Message "HTTP $($response.StatusCode), Chat ID: $chatId"
} catch {
    Write-TestResult -TestName "Start Chat" -Passed $false -Message $_.Exception.Message
}

# Test get specific chat
if ($chatId) {
    try {
        $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats/$chatId" -Headers $headers -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
        $content = $response.Content | ConvertFrom-Json
        $passed = ($response.StatusCode -eq 200) -and ($null -ne $content.chat_id)
        Write-TestResult -TestName "Get Chat by ID" -Passed $passed -Message "HTTP $($response.StatusCode), Chat ID: $($content.chat_id)"
    } catch {
        Write-TestResult -TestName "Get Chat by ID" -Passed $false -Message $_.Exception.Message
    }
    
    # Test continue chat
    try {
        $body = @{
            message = "What stocks should I invest in?"
        } | ConvertTo-Json
        
        $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats/$chatId" -Method POST -Headers $headers -Body $body -TimeoutSec 30 -UseBasicParsing -ErrorAction Stop
        $content = $response.Content | ConvertFrom-Json
        $passed = ($response.StatusCode -eq 200) -and ($null -ne $content.message)
        Write-TestResult -TestName "Continue Chat" -Passed $passed -Message "HTTP $($response.StatusCode), Response received: $($null -ne $content.message)"
    } catch {
        Write-TestResult -TestName "Continue Chat" -Passed $false -Message $_.Exception.Message
    }
}

# Test get chats with limit
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats?limit=5" -Headers $headers -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $passed = $response.StatusCode -eq 200
    Write-TestResult -TestName "Get Chats with Limit" -Passed $passed -Message "HTTP $($response.StatusCode)"
} catch {
    Write-TestResult -TestName "Get Chats with Limit" -Passed $false -Message $_.Exception.Message
}

# ========================================
# 5. Report Endpoints Tests
# ========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "5. Report Endpoints Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Test get report with preferences
try {
    # Endpoint expects a Python literal dict string that can be parsed by ast.literal_eval
    # Format: "{'key': value, 'key2': value2}"
    # Required fields: long_term, short_term, low_risk, high_risk (all booleans)
    $userPref = "{'long_term': True, 'short_term': False, 'low_risk': True, 'high_risk': False}"
    $encodedPref = [System.Web.HttpUtility]::UrlEncode($userPref)
    $response = Invoke-WebRequest -Uri "$API_BASE/report?user_pref=$encodedPref" -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
    $passed = $response.StatusCode -eq 200
    Write-TestResult -TestName "Get Report by Preferences" -Passed $passed -Message "HTTP $($response.StatusCode)"
} catch {
    Write-TestResult -TestName "Get Report by Preferences" -Passed $false -Message $_.Exception.Message
}

# Test get reports list
try {
    $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/reports" -Headers $headers -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
    $content = $response.Content | ConvertFrom-Json
    $passed = ($response.StatusCode -eq 200) -and ($null -ne $content)
    Write-TestResult -TestName "Get Reports List" -Passed $passed -Message "HTTP $($response.StatusCode), Reports: $($content.Count)"
} catch {
    Write-TestResult -TestName "Get Reports List" -Passed $false -Message $_.Exception.Message
}

# Test generate report (if we have a chat ID)
if ($chatId) {
    try {
        # Endpoint expects user_pref dict with all 4 required boolean keys:
        # long_term, short_term, low_risk, high_risk
        $body = @{
            user_pref = @{
                short_term = $true
                long_term = $true
                low_risk = $true
                high_risk = $false
            }
        } | ConvertTo-Json -Depth 3
        
        $response = Invoke-WebRequest -Uri "$API_BASE/$MODEL/chats/$chatId/report" -Method POST -Headers $headers -Body $body -TimeoutSec 60 -UseBasicParsing -ErrorAction Stop
        $content = $response.Content | ConvertFrom-Json
        # Response structure: {success: bool, report: {report_id: ...}, message: ...}
        $reportId = $content.report.report_id
        $hasReportId = $null -ne $reportId
        $hasSuccess = $content.success -eq $true
        $passed = ($response.StatusCode -eq 200) -and ($hasSuccess -or $hasReportId)
        $message = "HTTP $($response.StatusCode)"
        if ($hasReportId) {
            $message += ", Report ID: $reportId"
        } else {
            $message += ", Response: $($response.Content.Substring(0, [Math]::Min(150, $response.Content.Length)))"
        }
        Write-TestResult -TestName "Generate Report" -Passed $passed -Message $message
    } catch {
        Write-TestResult -TestName "Generate Report" -Passed $false -Message $_.Exception.Message
    }
}

# ========================================
# Summary
# ========================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$total = $TestResults.Count
$passed = ($TestResults | Where-Object { $_.Passed }).Count
$failed = $total - $passed

Write-Host "Total Tests: $total" -ForegroundColor White
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($failed -gt 0) {
    Write-Host "Failed Tests:" -ForegroundColor Red
    $TestResults | Where-Object { -not $_.Passed } | ForEach-Object {
        Write-Host "  - $($_.Test): $($_.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "Application URL: $APP_URL" -ForegroundColor Cyan
Write-Host "API Base URL: $API_BASE" -ForegroundColor Cyan
Write-Host ""
Write-Host "To test manually:" -ForegroundColor Yellow
Write-Host "  Frontend: $APP_URL" -ForegroundColor White
Write-Host "  API Root: $API_BASE/" -ForegroundColor White
Write-Host "  Stock Details: $API_BASE/details/AAPL" -ForegroundColor White
Write-Host "  Chats: $API_BASE/$MODEL/chats" -ForegroundColor White
Write-Host ""

if ($failed -eq 0) {
    Write-Host "All tests passed! Deployment is working correctly." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some tests failed. Review the output above." -ForegroundColor Yellow
    exit 1
}

