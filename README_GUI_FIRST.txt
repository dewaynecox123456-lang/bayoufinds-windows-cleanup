BayouFinds Cleanup Assistant v1.3.0 Beta
========================================

Customer setup
--------------

1. Copy the BayouFindsWindowsCleanup release folder to the Windows PC.
2. Open the release folder.
3. Double-click BayouFindsWindowsCleanup.exe.
4. If Windows SmartScreen appears, choose More info, then Run anyway only if
   the file came directly from BayouFinds.
5. If you received a license file, click Import License and select
   license.json.

Recommended customer flow
-------------------------

1. Import License
2. Scan My PC
3. Review results
4. Run Safe Cleanup

Start with Scan My PC. The scan creates a report without deleting files. After
the scan completes, review the on-screen results or click Open Latest Report.
Run Safe Cleanup only after reviewing the scan results.

Safety guardrails
-----------------

- Documents are not deleted by default.
- Pictures are not deleted by default.
- Desktop files are not deleted by default.
- Videos are not deleted by default.
- Music is not deleted by default.
- Downloads are not deleted by default.
- Registry cleaning is not included.
- Driver cleanup is not included.

Buttons
-------

- Import License
  Installs your BayouFinds license file.

- Scan My PC
  Runs preview mode and creates a report without deleting files.

- Run Safe Cleanup
  Cleans safe temporary/cache locations only.

- Deep Windows Check
  Runs Safe Cleanup with additional Windows file checks. This may take longer.

- Repair Windows Files
  Runs the Windows repair/check workflow for DISM/SFC support.

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

Each scan or cleanup run creates an HTML report, JSON report, and log file.

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
