BayouFinds Cleanup Assistant v1.5.0
===================================

Purchase link
-------------

  https://bayoufinds.com/b/y3OJr

Customer setup
--------------

1. Copy the BayouFindsWindowsCleanup release folder to the Windows PC.
2. Open the release folder.
3. Double-click BayouFindsWindowsCleanup.exe.
4. If Windows SmartScreen appears, choose More info, then Run anyway only if
   the file came directly from BayouFinds.
5. If you received a license file, click Import License and select
   license.json.
6. If you need a license, click Purchase License.

Trial mode
----------

Trial mode and missing-license mode allow:

- Scan My PC
- Reports
- Open Latest Report
- Open Reports / Logs

Trial mode and missing-license mode do not allow:

- Run Safe Cleanup
- Deep Windows Check
- Repair Windows Files
- Recovery tracking from cleanup runs

The app shows License Required when cleanup is locked. Scan and reports remain
available so customers can review recoverable space before purchasing.

Paid mode
---------

An active license allows:

- Scan My PC
- Reports
- Run Safe Cleanup
- Deep Windows Check
- Repair Windows Files
- Recovery tracking

Activation
----------

1. Click Import License.
2. Select your BayouFinds license.json file.
3. Confirm the dashboard shows Active.

If activation is needed, click Purchase License:

  https://bayoufinds.com/b/y3OJr

Recommended customer flow
-------------------------

1. Import License
2. Scan My PC
3. Review results
4. Run Safe Cleanup

Start with Scan My PC. The scan creates a report without deleting files. After
the scan completes, review the on-screen results or click Open Latest Report.
Run Safe Cleanup only after reviewing the scan results and activating a paid
license.

Dashboard metrics
-----------------

The top dashboard cards show:

- Recoverable Space
  Space found during Scan My PC. Preview mode does not delete files.

- Recovered This Run
  Space cleaned during the current Safe Cleanup run.

- Total Recovered
  Total space recovered across completed Safe Cleanup runs.

- PC Health Score
  A simple 0-100 score based on safe cleanup findings. Higher is better.

Dashboard statistics are saved in:

  Desktop\BayouFinds_Cleanup_Logs\cleanup_stats.json

Results dashboard
-----------------

After Scan My PC, the app shows:

  Scan Complete -- Recoverable Space Found

After Run Safe Cleanup, the app shows:

  Cleanup Complete -- Space Recovered

The on-screen breakdown groups cleanup results into simple customer categories:

- Windows Temp
- Browser Cache
- Discord Cache
- Teams Cache
- Slack Cache
- Zoom Cache
- Recycle Bin when applicable
- Total

Raw technical logs are still available from Open Reports / Logs.

License dashboard
-----------------

- Active
  Cleanup is enabled.

- Trial
  Scan and reports are enabled. Cleanup is locked until activation.

- License Required
  No active license was found. Purchase or import a license to clean and recover
  space.

Safety guardrails
-----------------

Protected by default:

- Documents are not deleted by default.
- Pictures are not deleted by default.
- Downloads are not deleted by default.
- Desktop files are not deleted by default.
- Videos are not deleted by default.
- Music is not deleted by default.
- Registry cleaning is not included.
- Driver cleanup is not included.

Safe cleanup categories
-----------------------

Safe Cleanup may include temporary files and app caches for Windows, browsers,
Discord, Microsoft Teams, Slack, and Zoom. These categories are limited to
cache, temp, log, and crash-report folders.

BayouFinds skips each communication app if that app is running. It does not
delete app settings, downloads, documents, credentials, message history, saved
sessions, workspaces, or application configuration.

Buttons
-------

- Import License
  Installs your BayouFinds license file.

- Purchase License
  Opens https://bayoufinds.com/b/y3OJr.

- Scan My PC
  Runs preview mode and creates a report without deleting files.

- Run Safe Cleanup
  Requires an active license. Cleans safe temporary files and app caches only.

- Deep Windows Check
  Requires an active license. Runs Safe Cleanup with additional Windows file
  checks. This may take longer.

- Repair Windows Files
  Requires an active license. Runs the Windows repair/check workflow for
  DISM/SFC support.

- License Status
  Checks the installed license.

- Open Latest Report
  Opens the newest HTML report from the reports folder.

- Open Reports Folder
  Opens Desktop\BayouFinds_Cleanup_Logs.

- Exit
  Closes the app.

Reports
-------

Reports and logs are saved here:

  Desktop\BayouFinds_Cleanup_Logs

Each scan or cleanup run creates an HTML report, JSON report, and log file. The
dashboard totals are stored in cleanup_stats.json in the same folder.

Developer source launch
-----------------------

From the repository root:

  python gui\BayouFindsCleanupGUI.py

PyInstaller build
-----------------

Run from the repository root on Windows:

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build-windows-gui.ps1

The build script creates a one-file Windows executable and a customer release
folder at:

  release\BayouFindsWindowsCleanup

The release folder contains:

- BayouFindsWindowsCleanup.exe
- BayouFinds_Windows_Cleanup.ps1
- README_GUI_FIRST.txt
- LICENSE_SAMPLE.json
- START_HERE.txt

The PowerShell cleanup script is copied beside the EXE so support can inspect
or replace it without rebuilding the GUI.

Artwork
-------

Optional GUI artwork:

- assets\header_banner.png
- assets\cleanup_mascot.png
- assets\splash.png

Original artwork files should stay in assets\. Runtime-optimized copies are
written to assets\optimized\ and are safe to regenerate.

To create optimized artwork:

  python scripts\optimize-artwork.py

The GUI loads assets\optimized\ first, then falls back to assets\. If an artwork
file is missing, the GUI falls back to branded text and continues running.
