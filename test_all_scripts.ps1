# Test script to verify that all scripts work correctly

# Test format scripts
Write-Host "Testing format scripts..." -ForegroundColor Cyan
Write-Host "------------------------"

Write-Host "Testing format.ps1..."
try {
    & .\format.ps1
    Write-Host "Success: format.ps1 executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: format.ps1 failed to execute: $_" -ForegroundColor Red
}

Write-Host "`nTesting format.bat..."
try {
    & .\format.bat
    Write-Host "Success: format.bat executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: format.bat failed to execute: $_" -ForegroundColor Red
}

# Test black scripts
Write-Host "`n`nTesting black scripts..." -ForegroundColor Cyan
Write-Host "-----------------------"

Write-Host "Testing black.ps1..."
try {
    & .\black.ps1 --version
    Write-Host "Success: black.ps1 executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: black.ps1 failed to execute: $_" -ForegroundColor Red
}

Write-Host "`nTesting black.bat..."
try {
    & .\black.bat --version
    Write-Host "Success: black.bat executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: black.bat failed to execute: $_" -ForegroundColor Red
}

# Test isort scripts
Write-Host "`n`nTesting isort scripts..." -ForegroundColor Cyan
Write-Host "-----------------------"

Write-Host "Testing isort.ps1..."
try {
    & .\isort.ps1 --version
    Write-Host "Success: isort.ps1 executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: isort.ps1 failed to execute: $_" -ForegroundColor Red
}

Write-Host "`nTesting isort.bat..."
try {
    & .\isort.bat --version
    Write-Host "Success: isort.bat executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: isort.bat failed to execute: $_" -ForegroundColor Red
}

# Test ruff scripts
Write-Host "`n`nTesting ruff scripts..." -ForegroundColor Cyan
Write-Host "-----------------------"

Write-Host "Testing ruff.ps1..."
try {
    & .\ruff.ps1 --version
    Write-Host "Success: ruff.ps1 executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: ruff.ps1 failed to execute: $_" -ForegroundColor Red
}

Write-Host "`nTesting ruff.bat..."
try {
    & .\ruff.bat --version
    Write-Host "Success: ruff.bat executed correctly" -ForegroundColor Green
} catch {
    Write-Host "Error: ruff.bat failed to execute: $_" -ForegroundColor Red
}

Write-Host "`n`nTest completed. If all tests passed, all scripts should work correctly." -ForegroundColor Cyan