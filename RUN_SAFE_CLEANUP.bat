@echo off
title BayouFinds - Safe Cleanup
echo.
echo Running Safe Cleanup...
echo Run this only after Preview Cleanup.
echo Personal files are protected.
echo Documents, Pictures, Downloads, and Desktop are not touched.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BayouFinds_Windows_Cleanup.ps1" -NoMenu -Mode SafeCleanup
echo.
pause

