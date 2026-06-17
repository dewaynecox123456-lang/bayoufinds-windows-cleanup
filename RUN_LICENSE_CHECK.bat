@echo off
title BayouFinds - License Check
echo.
echo Running BayouFinds License Check...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BayouFinds_Windows_Cleanup.ps1" -NoMenu -Mode LicenseCheck
echo.
pause

