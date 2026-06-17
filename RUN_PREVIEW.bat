@echo off
title BayouFinds - Preview Cleanup
echo.
echo Running Preview Cleanup...
echo Preview checks safe junk without deleting files.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BayouFinds_Windows_Cleanup.ps1" -NoMenu -Mode Preview
echo.
pause

