# Project HoloHand PowerShell Launcher
param(
    [string]$Url = "0",
    [switch]$DryRun,
    [switch]$Test
)

Set-Location -Path "x:\ESP"

if ($Test) {
    Write-Host "[HOLOHAND] Running Automated Validation Test Suite..." -ForegroundColor Cyan
    python holohand_backend.py --test
    exit
}

$argsList = @("holohand_backend.py", "--url", $Url)
if ($DryRun) {
    $argsList += "--dry-run"
}

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  PROJECT HOLOHAND — LAUNCHING AR STUDIO" -ForegroundColor Cyan
Write-Host "  Stream Target: $Url" -ForegroundColor White
Write-Host "  Dry Run: $DryRun" -ForegroundColor White
Write-Host "=======================================================" -ForegroundColor Cyan

python @argsList
