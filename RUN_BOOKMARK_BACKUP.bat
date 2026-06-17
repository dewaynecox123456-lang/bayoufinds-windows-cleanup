@echo off
title BayouFinds - Back Up Browser Bookmarks
echo.
echo Running Back Up Browser Bookmarks...
echo This copies bookmark files only.
echo Cookies, passwords, browsing history, and extensions are not touched.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0BayouFinds_Windows_Cleanup.ps1" -NoMenu -Mode BackupBookmarks
echo.
pause

