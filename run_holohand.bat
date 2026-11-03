@echo off
title PROJECT HOLOHAND — Launcher
cls
echo =======================================================
echo   PROJECT HOLOHAND — AR GESTURE STUDIO LAUNCHER
echo =======================================================
echo.
echo Select launch mode:
echo   [1] Connect to ESP32-CAM Wi-Fi Stream (Default)
echo   [2] Connect to Local Camera (Index 0 - Instant Test)
echo   [3] Connect to ESP32-CAM in DRY-RUN Mode (Safe Testing)
echo   [4] Run Automated Validation Test Suite
echo.
set /p choice="Enter option (1-4) [Default: 2]: "

if "%choice%"=="" set choice=2
if "%choice%"=="1" goto esp32
if "%choice%"=="2" goto webcam
if "%choice%"=="3" goto dryrun
if "%choice%"=="4" goto testsuite

:esp32
set /p esp_ip="Enter ESP32-CAM IP (e.g. 192.168.1.100): "
if "%esp_ip%"=="" set esp_ip=192.168.1.100
echo Launching HoloHand on http://%esp_ip%/stream ...
python holohand_backend.py --url http://%esp_ip%/stream
goto end

:webcam
echo Launching HoloHand on Local Camera (Index 0) ...
python holohand_backend.py --url 0
goto end

:dryrun
set /p esp_ip="Enter ESP32-CAM IP (e.g. 192.168.1.100) or 0 for webcam: "
if "%esp_ip%"=="" set esp_ip=0
if "%esp_ip%"=="0" (
    python holohand_backend.py --url 0 --dry-run
) else (
    python holohand_backend.py --url http://%esp_ip%/stream --dry-run
)
goto end

:testsuite
python holohand_backend.py --test
pause
goto end

:end
