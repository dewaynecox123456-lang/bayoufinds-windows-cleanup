<# 
Builds the BayouFinds Windows Cleanup Tkinter GUI as a PyInstaller one-file EXE.
Run from the repository root on Windows.
#>

[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$GuiScript = Join-Path -Path $Root -ChildPath "gui\BayouFindsCleanupGUI.py"
$Icon = Join-Path -Path $Root -ChildPath "assets\app_icon.ico"
$CleanupScript = Join-Path -Path $Root -ChildPath "BayouFinds_Windows_Cleanup.ps1"
$Readme = Join-Path -Path $Root -ChildPath "README_GUI_FIRST.txt"
$LicenseSample = Join-Path -Path $Root -ChildPath "LICENSE_SAMPLE.json"
$StartHere = Join-Path -Path $Root -ChildPath "START_HERE.txt"
$AppName = "BayouFindsWindowsCleanup"
$ReleaseDir = Join-Path -Path $Root -ChildPath "release\BayouFindsWindowsCleanup"

if (!(Test-Path -Path $GuiScript)) {
    throw "GUI script not found: $GuiScript"
}

if (!(Test-Path -Path $CleanupScript)) {
    throw "Cleanup PowerShell script not found: $CleanupScript"
}

if (!(Test-Path -Path $Icon)) {
    throw "Icon not found: $Icon"
}

if (!(Test-Path -Path $Readme)) {
    throw "GUI README not found: $Readme"
}

if (!(Test-Path -Path $LicenseSample)) {
    throw "License sample not found: $LicenseSample"
}

if (!(Test-Path -Path $StartHere)) {
    throw "START_HERE.txt not found: $StartHere"
}

Push-Location $Root
try {
    if ($Clean) {
        Remove-Item -Path "build", "dist", "$AppName.spec" -Recurse -Force -ErrorAction SilentlyContinue
    }

    Remove-Item -Path $ReleaseDir -Recurse -Force -ErrorAction SilentlyContinue

    & $Python -m pip install --upgrade pyinstaller customtkinter

    $PyInstallerArgs = @(
        "--onefile",
        "--windowed",
        "--name", $AppName,
        "--icon", $Icon,
        "--add-data", "BayouFinds_Windows_Cleanup.ps1;.",
        "--add-data", "assets\app_icon.ico;assets"
    )

    foreach ($Artwork in @("header_banner.png", "cleanup_mascot.png", "splash.png")) {
        $OptimizedArtworkPath = Join-Path -Path $Root -ChildPath "assets\optimized\$Artwork"
        $ArtworkPath = Join-Path -Path $Root -ChildPath "assets\$Artwork"
        if (Test-Path -Path $OptimizedArtworkPath) {
            $PyInstallerArgs += @("--add-data", "assets\optimized\$Artwork;assets\optimized")
        }
        elseif (Test-Path -Path $ArtworkPath) {
            $PyInstallerArgs += @("--add-data", "assets\$Artwork;assets")
        }
        else {
            Write-Host "Optional artwork not found, skipping: assets\$Artwork"
        }
    }

    & $Python -m PyInstaller @PyInstallerArgs $GuiScript

    New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null

    Copy-Item -Path (Join-Path -Path $Root -ChildPath "dist\$AppName.exe") -Destination (Join-Path -Path $ReleaseDir -ChildPath "BayouFindsWindowsCleanup.exe") -Force
    Copy-Item -Path $CleanupScript -Destination (Join-Path -Path $ReleaseDir -ChildPath "BayouFinds_Windows_Cleanup.ps1") -Force
    Copy-Item -Path $Readme -Destination (Join-Path -Path $ReleaseDir -ChildPath "README_GUI_FIRST.txt") -Force
    Copy-Item -Path $LicenseSample -Destination (Join-Path -Path $ReleaseDir -ChildPath "LICENSE_SAMPLE.json") -Force
    Copy-Item -Path $StartHere -Destination (Join-Path -Path $ReleaseDir -ChildPath "START_HERE.txt") -Force

    Write-Host ""
    Write-Host "Build complete. Customer release folder:"
    Write-Host $ReleaseDir
    Write-Host ""
    Get-ChildItem -Path $ReleaseDir | Select-Object Name, Length | Format-Table -AutoSize
}
finally {
    Pop-Location
}
