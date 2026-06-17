@echo off
setlocal

title BayouFinds Windows Cleanup Tool GUI
set "SCRIPT=%~dp0BayouFinds_Windows_Cleanup_GUI.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%SCRIPT%"

endlocal
