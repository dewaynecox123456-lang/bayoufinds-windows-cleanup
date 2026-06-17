BayouFinds Windows Cleanup v1.2 - Tkinter GUI
=============================================

Recommended customer launch:

  Double-click BayouFindsWindowsCleanup.exe.

Developer source launch:

  python gui\BayouFindsCleanupGUI.py

The GUI is a professional dark-theme desktop app for BayouFinds Windows
Cleanup. It runs the existing PowerShell cleanup script without blocking the UI
and streams live output into the status window.

Buttons
-------

- Quick Cleanup
  Runs BayouFinds_Windows_Cleanup.ps1 in SafeCleanup mode.

- Deep Cleanup
  Runs SafeCleanup mode with SFC enabled.

- Windows Health Check
  Runs Preview mode to inspect/report without deleting cleanup targets.

- Repair Windows Files
  Runs SafeCleanup mode with SFC enabled for DISM/SFC repair workflow.

- License Status
  Runs LicenseCheck mode.

- Open Log Folder
  Opens Desktop\BayouFinds_Cleanup_Logs.

- Exit
  Closes the GUI.

PyInstaller Build
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

Place optional GUI artwork here before building:

- assets\header_banner.png
- assets\cleanup_mascot.png
- assets\splash.png

Original artwork files should stay in assets\. Runtime-optimized copies are
written to assets\optimized\ and are safe to regenerate.

To create optimized artwork:

  python scripts\optimize-artwork.py

Optimization targets:

- header_banner.png: 900px wide
- cleanup_mascot.png: 340px max height
- splash.png: 720px wide max

The GUI loads these files automatically when present:

- header_banner.png displays across the top of the main window.
- cleanup_mascot.png displays in the dashboard/action area.
- splash.png displays for about 2.4 seconds on startup.

The GUI looks in assets\optimized\ first, then falls back to assets\. If an
artwork file is missing, the GUI falls back to branded text and continues
running. The PyInstaller build script bundles optimized artwork when present,
then falls back to original artwork.

Files Added
-----------

- gui\BayouFindsCleanupGUI.py
- assets\app_icon.ico
- scripts\build-windows-gui.ps1
- scripts\optimize-artwork.py
- README_GUI_FIRST.txt
