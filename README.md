<p align="center">
  <img src="https://raw.githubusercontent.com/dewaynecox123456-lang/bayoufinds-windows-cleanup/main/assets/brand/bayoufinds-cleanup-banner.svg" width="700" alt="BayouFinds Windows Cleanup Tool banner"/>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/dewaynecox123456-lang/bayoufinds-windows-cleanup/main/assets/brand/cleanup-terminal-preview.svg" width="700" alt="BayouFinds Windows Cleanup terminal preview"/>
</p>

# BayouFinds Windows Cleanup Tool

> Safe cleanup visibility for Windows PCs. Preview first. Log everything. No mystery registry hacks.

## Project Status

This repository is being repositioned around the safer v1.1 workflow: preview-first cleanup, clear logging, skipped-item visibility, and customer-friendly reporting.

The current public PowerShell script is an early version. Treat it as a development baseline, not the final packaged customer release.

## Get the Ready-to-Run Version

The packaged customer version should include launchers, instructions, sample license files, and safer defaults.

**Download / product page:**  
https://bayoufinds.com/b/y3OJr

## What This Project Is For

BayouFinds Windows Cleanup is designed for home users, small business owners, and light IT support cases where the user needs a practical cleanup tool without turning the machine into a science fair.

Core direction:

- Preview mode before cleanup
- Human-readable logs on the Desktop
- Safe cleanup categories with clear labels
- Browser cache handling that skips running browsers
- Optional cleanup actions separated from default cleanup
- No surprise registry edits
- No silent service disabling
- No aggressive delete behavior without confirmation

## Current Repository Contents

- `BayouFinds_Windows_Cleanup.ps1` — early PowerShell cleanup script
- `assets/brand/` — refreshed BayouFinds artwork for the repository
- README artwork and project copy for the public GitHub page

## Safety Position

Default cleanup should stay conservative. The tool should avoid destructive or performance-questionable behavior unless the user explicitly confirms it.

Actions that should remain optional or disabled by default:

- Windows Update cache reset
- Prefetch cleanup
- Recycle Bin emptying
- DISM/SFC repair runs
- Any service stop/start workflow

## Recommended Customer Workflow

Run PowerShell as Administrator from the project folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\BayouFinds_Windows_Cleanup.ps1 -DryRun
```

Review the output and log file before running cleanup.

## Roadmap

- Add `-Mode Preview`, `-Mode SafeCleanup`, `-Mode LicenseCheck`, and `-Mode BackupBookmarks`
- Add session IDs and structured report output
- Add actual bytes/files cleaned counts
- Add top running apps and memory snapshot
- Add browser bookmark backup
- Add customer-friendly HTML report
- Add simple launcher menu for non-technical users

## Brand

BayouFinds tools should look calm, mature, and trustworthy. The current visual direction uses dark bayou glass, aqua highlights, Louisiana gold accents, and clean operator-style reporting.

## License

Private/commercial licensing details may be handled outside this public repository.
