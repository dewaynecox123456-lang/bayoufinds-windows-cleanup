@echo off
setlocal

set "SCRIPT=%~dp0BayouFinds_Windows_Cleanup.ps1"
set "REPORTS=Desktop\BayouFinds_Cleanup_Logs"

:menu
cls
title BayouFinds Windows Cleanup Tool
echo.
echo BayouFinds Windows Cleanup Tool v1.1 - Sean Dev Test
echo ====================================================
echo.
echo Reports will be saved to:
echo   %REPORTS%
echo.
echo Choose an option:
echo.
echo   1. Check license
echo   2. Preview cleanup
echo   3. Back up browser bookmarks
echo   4. Run safe cleanup
echo   5. Exit
echo.
choice /c 12345 /n /m "Enter 1, 2, 3, 4, or 5: "

if errorlevel 5 goto done
if errorlevel 4 goto safe_cleanup
if errorlevel 3 goto bookmark_backup
if errorlevel 2 goto preview
if errorlevel 1 goto license_check

:license_check
cls
echo.
echo Running BayouFinds License Check...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -NoMenu -Mode LicenseCheck
echo.
echo Reports are saved to:
echo   %REPORTS%
echo.
pause
goto menu

:preview
cls
echo.
echo Running Preview Cleanup...
echo Preview checks safe junk without deleting files.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -NoMenu -Mode Preview
echo.
echo Reports are saved to:
echo   %REPORTS%
echo.
pause
goto menu

:bookmark_backup
cls
echo.
echo Running Back Up Browser Bookmarks...
echo This copies bookmark files only.
echo Cookies, passwords, browsing history, and extensions are not touched.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -NoMenu -Mode BackupBookmarks
echo.
echo Reports are saved to:
echo   %REPORTS%
echo.
pause
goto menu

:safe_cleanup
cls
echo.
echo Running Safe Cleanup...
echo Run this only after Preview Cleanup.
echo Personal files are protected.
echo Documents, Pictures, Downloads, and Desktop are not touched.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -NoMenu -Mode SafeCleanup
echo.
echo Reports are saved to:
echo   %REPORTS%
echo.
pause
goto menu

:done
endlocal
